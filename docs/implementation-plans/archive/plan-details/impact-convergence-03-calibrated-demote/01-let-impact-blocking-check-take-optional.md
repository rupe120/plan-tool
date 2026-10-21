> **Auto-archived**: this plan was swept on 2026-08-03 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 1 — Isolate the existing impact-blocking decision

## Summary

Refactor `plan_tool/convergence.py:is_blocking_impact` to isolate its current severity-or-high-impact decision without changing its signature or result. Add characterization coverage in `tests/test_convergence.py` before changing the helper, then keep that coverage unchanged after the refactor. The next feature step adds a bounded demotion extension to this isolated seam.

## Table of Contents

- [Summary](#summary) — The step’s behavior-preserving helper change.
- [Why](#why) — Why the shared predicate needs an extension point.
- [Input](#input) — The recommendation fields and existing predicate contract this step reads.
- [Files (creates vs edits)](#files-creates-vs-edits) — The two in-scope files and their changes.
- [Implementation](#implementation) — The optional demotion-rule contract and safety ordering.
- [Tests](#tests) — Characterization and extension-point coverage.
- [Acceptance criteria](#acceptance-criteria) — Observable helper behavior required on completion.
- [Deferred](#deferred) — Later lookup construction and caller adoption.

## Why

`plan_tool/convergence.py:is_blocking_impact` currently combines severity blocking with high-impact promotion in one expression. Isolating that unchanged decision first gives the feature step a small, characterized seam and proves that no live caller behavior changes before calibrated demotion exists.

## Input

- **Recommendation contract:** `plan_tool/convergence.py:is_blocking_impact` reads `plan_tool/review.py:Recommendation.severity` and `.impact` through its existing type-only import. Preserve that dependency direction; `plan_tool/review.py` already imports convergence helpers.
- **Current policy:** `plan_tool/convergence.py:is_blocking` remains the severity-only baseline, and existing no-argument `is_blocking_impact(rec)` callers must retain their current result.

## Files (creates vs edits)

- **New files:** None.

- **Existing files (edits only):**
  - `plan_tool/convergence.py` — Extract and name the existing severity-or-high-impact decision while retaining `is_blocking_impact(rec)` exactly.
  - `tests/test_convergence.py` — Add characterization tests for the existing contract.

## Implementation

- **Extract only the current decision:** Factor the existing `rec.impact == "high" or is_blocking(rec.severity)` expression into a named private baseline helper (or equivalent local seam), with `is_blocking_impact(rec)` delegating to it. Do not add parameters, callbacks, calibration imports, or alternate outcomes in this step.

- **Preserve the safety order exactly:** High-impact advisory recommendations continue to block, existing severity-based blocks continue to block, and `nit`/`info` with non-high impact remain advisory.

- **Preserve the public seam:** Retain `is_blocking(severity)` as the severity-only predicate for uses that are not convergence demotion decisions, including `plan_tool/convergence_diagnosis.py` and the deterministic gates in `plan_tool/cli/completeness_cmd.py`.

## Tests

- `test_is_blocking_impact_preserves_current_augment` — High-impact `nit` and `info` still block, while every existing severity result is retained.

### Test-creation order (refactor step)

Write `test_is_blocking_impact_preserves_current_augment` first to pin the current contract. Keep it green and unmodified after extracting the baseline helper.

## Acceptance criteria

- `is_blocking_impact(rec)` retains the current result for every recommendation.
- High-impact recommendations remain blocking, and advisory `nit` and `info` findings retain their existing non-blocking behavior otherwise.
- `tests/test_convergence.py` passes with the characterization tests unchanged after the helper update.
- `plan_tool/convergence.py` does not import telemetry, persistence, CLI, or calibration-analysis modules.

## Deferred

- **Bounded demotion extension** — Step 2 adds the optional rule and its fixed low-impact, medium-severity guard.
- **Evidence-backed eligibility lookup** — Step 3 builds the calibration-based rule from `FindingClassDriftSignal` evidence.
- **Loop adoption** — Steps 4 and 5 supply one operation-scoped rule to reconcile and audit materiality.
