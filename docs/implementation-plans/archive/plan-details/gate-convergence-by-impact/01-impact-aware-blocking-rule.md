> **Auto-archived**: this plan was swept on 2026-08-03 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 1 — Add the impact-aware blocking rule

## Summary

Add `is_blocking_impact()` to `plan_tool/convergence.py` as an augment-only predicate for `Recommendation` inputs. It promotes only high-impact advisory recommendations and retains every severity-based block. Cover the real parser-supported promotion shapes: high-impact `nit` and `info`; keep `LOW`, which normalizes to `medium`, as the severity-blocking control case.

## Table of Contents

- [Summary](#summary) — Predicate outcome.
- [Why](#why) — Why the severity rule needs an augment.
- [Input](#input) — Existing recommendation contract.
- [Files (creates vs edits)](#files-creates-vs-edits) — Source and test files.
- [Implementation](#implementation) — Required predicate behavior.
- [Tests](#tests) — Focused coverage.
- [Acceptance criteria](#acceptance-criteria) — Observable checks.
- [Deferred](#deferred) — Work left to later steps.

## Why

`is_blocking` reads severity only. A parsed `nit` or `info` recommendation can be advisory by severity while carrying `impact="high"`, so later continuation paths need one monotonic predicate to recognize it without weakening the established severity floor.

## Input

- `plan_tool/review.py:Recommendation` supplies the existing `severity` and optional `impact` fields. Do not change its shape, parser, prompts, or saved-data contract.
- `plan_tool/convergence.py:is_blocking` and `BLOCKING_SEVERITIES` remain the source of truth for severity-based blocks.
- Step 1 evidence establishes normalized high-impact `nit` and `info` candidates; `LOW` normalizes to `medium` and is not an advisory-promotion example.

## Files (creates vs edits)

- **New files:** None.

- **Existing files (edits only):**
  - `plan_tool/convergence.py` — Add the impact-aware predicate beside `is_blocking`.
  - `tests/test_convergence.py` — Add Recommendation-based predicate tests.

## Implementation

- Define `is_blocking_impact(rec: Recommendation) -> bool` beside `is_blocking`. Return `rec.impact == "high" or is_blocking(rec.severity)`.
- Preserve the severity floor: medium, high, and critical severity block regardless of absent, low, or medium impact.
- Promote only `impact == "high"`; absent, low, and medium impact must not make a non-blocking severity block.
- Keep the type-only `Recommendation` boundary so `plan_tool/convergence.py` does not introduce a runtime import cycle with `plan_tool/review.py`.
- Leave all caller adoption to step 2. Keep deterministic/reporting gates and `plan_tool/convergence_diagnosis.py` severity-based.

## Tests

- `test_high_impact_nit_blocks` — A normalized `nit` recommendation with high impact blocks despite advisory severity.
- `test_high_impact_info_blocks` — A normalized `info` recommendation with high impact blocks despite advisory severity.
- `test_medium_or_higher_severity_remains_blocking` — Medium, high, and critical severity block with absent, low, or medium impact; include normalized `LOW`/`medium` as the control.
- `test_missing_impact_falls_back_to_severity_rule` — An untagged recommendation matches `is_blocking(rec.severity)`.
- `test_low_and_medium_impact_do_not_promote_advisories` — Advisory `nit` and `info` recommendations remain non-blocking without high impact.

## Acceptance criteria

- The predicate promotes normalized high-impact `nit` and `info` recommendations.
- The predicate returns true for every recommendation whose severity already passes `is_blocking`.
- Missing, low, and medium impact retain the severity result.
- The implementation adds no runtime import cycle and changes no parser, prompt, or `Recommendation` contract.

## Deferred

- Loop wiring belongs to step 2.
- Impact-only demotion remains blocked on #154 calibration.
- Prompt, parsing, schema, and completeness-plumbing changes are outside this plan.
