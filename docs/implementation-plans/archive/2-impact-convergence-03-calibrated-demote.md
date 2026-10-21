> **Auto-archived**: this plan was swept on 2026-08-03 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

---
title: Impact Convergence 03 Calibrated Demote
status: completed
priority: medium
enforce_step_tests: true
steps:
- id: 1
  title: Isolate the existing impact-blocking decision
  files:
  - plan_tool/convergence.py
  - tests/test_convergence.py
  complexity: low
  change_type: refactor
  detail: docs/implementation-plans/plan-details/impact-convergence-03-calibrated-demote/01-let-impact-blocking-check-take-optional.md
  status: done
- id: 2
  title: Add the bounded low-impact demotion extension
  files:
  - plan_tool/convergence.py
  - tests/test_convergence.py
  complexity: low
  change_type: feature
  depends_on:
  - 1
  detail: docs/implementation-plans/plan-details/impact-convergence-03-calibrated-demote/02-add-bounded-low-impact-demotion.md
  status: done
- id: 3
  title: Build the evidence-backed low-impact demotion lookup
  files:
  - plan_tool/telemetry_analysis.py
  - tests/test_telemetry_analysis.py
  complexity: medium
  change_type: feature
  detail: docs/implementation-plans/plan-details/impact-convergence-03-calibrated-demote/03-build-evidence-backed-low-impact.md
  status: done
- id: 4
  title: Use one calibration lookup in reconcile iteration
  files:
  - plan_tool/cli/reconcile.py
  - tests/test_cli.py
  complexity: medium
  change_type: feature
  depends_on:
  - 2
  - 3
  detail: docs/implementation-plans/plan-details/impact-convergence-03-calibrated-demote/04-use-one-calibration-lookup-reconcile.md
  status: done
- id: 5
  title: Use one calibration lookup for audit materiality
  files:
  - plan_tool/review.py
  - tests/test_review.py
  complexity: medium
  change_type: feature
  depends_on:
  - 2
  - 3
  detail: docs/implementation-plans/plan-details/impact-convergence-03-calibrated-demote/05-use-one-calibration-lookup-audit.md
  status: done
- id: 6
  title: 'Mark the calibrated #152 demotion as shipped'
  files:
  - BACKLOG.md
  - CLAUDE.md
  - docs/AUDIT_FLOW.md
  complexity: low
  change_type: non-code
  depends_on:
  - 4
  - 5
  detail: docs/implementation-plans/plan-details/impact-convergence-03-calibrated-demote/06-mark-calibrated-152-demotion-shipped.md
  status: done
---
# Impact Convergence 03 Calibrated Demote

## Overview

Implement #152 as a conservative, calibration-based exception to the existing severity floor. An explicit `impact=low`, `severity=medium` recommendation may be demoted only when read-only class-drift evidence meets the resolved-observation and confirmed-rate thresholds; high-impact promotion remains unchanged. Calibration is read once per operation and supplied to the reachable reconcile and audit-materiality loops without changing their other behavior.

## Problem statement

The remaining #152 demotion needs a narrow, evidence-backed path for low-impact medium-severity recommendations while preserving the current safety floor for all other recommendations. Without this exception, recommendations with sufficiently reliable low-confirmation calibration evidence remain blocking despite their measured class behavior.

## Architecture

Classify each live recommendation with `telemetry_analysis.classify_calibration_recommendation` and evaluate only the existing read-only `FindingClassDriftSignal` evidence. Demotion is allowed exclusively for explicit `impact=low`, `severity=medium` recommendations whose matching class has `confirmed + cleared >= 10` and `confirmed_rate <= 0.10`; all missing, unknown, legacy, insufficient, unresolved-only, or over-threshold evidence remains blocking.

Read calibration once per operation, then pass an immutable lookup or predicate into the existing reachable reconcile and audit-materiality loops. This preserves the existing flow while preventing per-finding history reads or persisted calibration state.

## Input

Consume the existing read-only `FindingClassDriftSignal` calibration evidence and classify live recommendations with `telemetry_analysis.classify_calibration_recommendation`. Correctness depends on the matching class row's `confirmed` and `cleared` observations, its `confirmed_rate`, and provenance sufficient to distinguish unknown or legacy evidence; absent, unresolved-only, insufficient, or over-threshold data must remain non-permissive.

## References

- [dataclasses — Python documentation](https://docs.python.org/3/library/dataclasses.html) — Covers frozen dataclasses for representing immutable calibration evidence and lookup inputs safely.
- [types.MappingProxyType — Python documentation](https://docs.python.org/3/library/types.html#types.MappingProxyType) — Defines the standard read-only mapping wrapper suitable for passing one operation-scoped calibration lookup.
- [unittest.mock — Python documentation](https://docs.python.org/3/library/unittest.mock.html) — Documents call assertions and patching needed to prove calibration history is read exactly once per operation.
- [Parametrizing tests — pytest documentation](https://docs.pytest.org/en/stable/example/parametrize.html) — Shows the supported pytest approach for the strict threshold and safety-boundary test matrix.
- [Monkeypatching/mocking modules and environments — pytest documentation](https://docs.pytest.org/en/stable/how-to/monkeypatch.html) — Explains scoped dependency replacement for testing fallback evidence and read-count behavior without mutating persisted state.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

- Changing high-impact promotion or #158's separate impact-recurrence structural stop; they remain unchanged. The audit loop's materiality decision deliberately adopts this same narrow calibrated-demotion policy, while its deduplication, low-yield floor, budgets, and all non-qualifying continuation behavior remain unchanged.
- Adding a CLI flag or mutating plan, config, or telemetry; the calibration evidence is existing and read-only.

## Risks

- Incorrectly applying the exception outside explicit `impact=low`, `severity=medium` recommendations could weaken the severity floor; `high` and `critical` must always block, while `nit` and `info` retain existing advisory behavior.
- Missing, legacy, or insufficient calibration evidence could be treated as permissive; these cases, including unresolved-only cohorts and rates above the threshold, must remain blocking.
- Repeated calibration reads could add unnecessary history access; calibration must be read once per operation.

## Testing

Required proof covers the strict threshold boundary matrix, high/critical safety, unknown-evidence fallback, one-read-per-operation behavior, stable existing augment behavior, and absence of plan/config/telemetry mutation.

**Per-step test strategy** (derived from each step's `change_type`):

- step 1 (refactor) — characterization tests pinned before the change; pass unchanged after.
- steps 2–5 (feature) — unit tests added with the implementation; green before completion.
- step 6 (non-code) — verification appropriate to the artifacts; no test-ordering directive.

## Acceptance criteria

- Only an explicit `impact=low`, `severity=medium` recommendation is eligible for demotion.
- A matching class is demoted only when `confirmed + cleared >= 10` and `confirmed_rate <= 0.10`.
- `high` and `critical` severity recommendations always block, and `nit` and `info` retain existing advisory behavior.
- Missing class rows, unknown/legacy provenance, insufficient evidence, unresolved-only cohorts, and rates above `0.10` remain blocking.
- Live recommendations are classified with `telemetry_analysis.classify_calibration_recommendation` using only existing read-only `FindingClassDriftSignal` evidence.
- Calibration is read once per operation and supplied to the reachable reconcile and audit-materiality loops without per-finding history reads or persisted cache.
- High-impact promotion and #158's separate impact-recurrence structural stop are unchanged; audit materiality deliberately changes only for qualifying calibrated demotions.
- The change does not add a CLI flag or mutate plan, config, or telemetry.

## Deferred

- Persisting calibration across operations — postponed to preserve this change's operation-scoped, read-only evidence contract.
