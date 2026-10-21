> **Auto-archived**: this plan was swept on 2026-08-05 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

---
title: Convergence Resolved Recurrence
intent: Ensure convergence guidance preserves genuine structural recurrence while
  avoiding destructive re-decompose recommendations for findings that are resolved
  or no longer current.
status: completed
priority: medium
enforce_step_tests: true
steps:
- id: 1
  title: Make an absent or applied latest finding end recurrence
  intent: Stops a finding absent from its newest series run, or applied in that
    run, from making the diagnostic claim that the audit loop is still spinning.
  files:
  - plan_tool/convergence_diagnosis.py
  - tests/test_convergence_diagnosis.py
  - tests/cli/test_convergence_cmd.py
  complexity: medium
  change_type: feature
  detail: docs/implementation-plans/plan-details/convergence-resolved-recurrence/01-make-missing-latest-finding-end.md
  status: done
- id: 2
  title: Limit re-decompose advice to structural findings
  intent: Prevents claim and premise findings from suggesting a destructive re-seed
    while retaining that advice for unresolved structural evidence.
  files:
  - plan_tool/convergence_diagnosis.py
  - plan_tool/split_criteria.py
  - plan_tool/telemetry_analysis.py
  - docs/ARCHITECTURE.md
  - tests/test_convergence_diagnosis.py
  - tests/test_split_criteria.py
  - tests/cli/test_convergence_cmd.py
  - tests/test_telemetry_analysis.py
  complexity: medium
  change_type: feature
  depends_on:
  - 1
  detail: docs/implementation-plans/plan-details/convergence-resolved-recurrence/02-limit-re-decompose-advice-structural.md
  status: done
- id: 3
  title: Clear the fixed convergence risk from the backlogs
  intent: Keeps the resolved risk and the remaining audit-trajectory roadmap accurate.
  files:
  - BUG_BACKLOG.md
  - BACKLOG.md
  complexity: medium
  change_type: non-code
  depends_on:
  - 1
  - 2
  detail: docs/implementation-plans/plan-details/convergence-resolved-recurrence/03-clear-fixed-convergence-risk-backlogs.md
  status: done
---
# Convergence Resolved Recurrence

## Overview

Update convergence diagnosis so a finding missing from its newest series audit, or marked applied there, is no longer treated as recurring. Keep genuine unresolved structural recurrence behavior while ensuring nonstructural findings do not receive a destructive re-decompose recommendation.

## Problem statement

The first RISK in BUG_BACKLOG.md identifies that convergence can recommend re-decomposition after a recurring finding is absent from the newest audit or already applied there. This can produce a destructive recommendation for a resolved finding or a finding that concerns a claim or premise rather than unresolved structure.

## Architecture

In `plan_tool/convergence_diagnosis.py`, make absence from the newest run and current-run application break recurrence. Refine remedy selection to distinguish unresolved structural recurrence from claim/premise recurrence, preserving re-decompose recommendations only for genuine unresolved structural cases and legacy persisted structural source labels.

Maintain compatibility with persisted history and preserve the existing diagnose/render interfaces so consumers continue to use the same surfaces.

## Input

This work consumes persisted history plus the existing diagnose/render interfaces in `plan_tool/convergence_diagnosis.py`. Compatibility with that persisted history and those interfaces must be preserved.

## References

- [dataclasses — Data Classes](https://docs.python.org/3/library/dataclasses.html) — Defines dataclass field defaults and initialization behavior relevant to preserving the diagnosis model’s public interfaces.
- [difflib — Helpers for computing deltas](https://docs.python.org/3/library/difflib.html) — Documents SequenceMatcher similarity semantics used to retain correct cross-run finding-region matching.
- [json — JSON encoder and decoder](https://docs.python.org/3/library/json.html) — Covers Python JSON decoding and error behavior relevant to maintaining compatibility with persisted review history.
- [pytest tmp_path fixture API](https://docs.pytest.org/en/stable/reference/reference.html#tmp-path) — Documents isolated pathlib-backed temporary directories for regression tests that write and reload saved audit runs.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

- Changing the persisted history format — this work preserves compatibility with existing saved audit runs.
- Redefining audit finding categories — this work only adjusts recurrence and remedy selection for the existing structural, claim, and premise categories.
- Reworking the decomposition workflow — this work narrows when diagnosis recommends re-decomposition rather than changing the workflow itself.

## Risks

- **Failure shape:** Cross-run matching can mistake a still-present finding for one absent from the newest audit, ending genuine structural recurrence too early. **Severity:** medium. **Mitigation:** Preserve existing matching semantics and cover newest-run absence alongside true recurrence. **Unresolved gap:** Similar but reformulated findings can remain difficult to match reliably.
- **Failure shape:** Remedy selection can treat an incorrectly categorized structural finding as claim- or premise-level and withhold needed re-decompose guidance. **Severity:** high. **Mitigation:** Limit the change to existing categories and verify unresolved structural recurrence retains its recommendation. **Unresolved gap:** Category accuracy remains outside this work's scope.
- **Failure shape:** Persisted history from earlier runs can retain a structural source label folded into the current taxonomy, changing results if the reader excludes it. **Severity:** high. **Mitigation:** Read legacy structural labels as their current structural equivalent without rewriting sidecars, and cover that behavior. **Unresolved gap:** Malformed or incomplete saved history remains subject to existing handling.

## Testing

Add focused regression coverage in `tests/test_convergence_diagnosis.py` and essential consumer tests for newest-run absence, applied current findings, structural recurrence, nonstructural findings, and telemetry's info-severity structural split evidence.

**Per-step test strategy** (derived from each step's `change_type`):

- step 1 (feature) — tests covering the behavior this step changes; green before completion.
- step 2 (feature) — tests covering the behavior this step changes; green before completion.
- step 3 (non-code) — verification appropriate to the artifacts rather than unit tests.

## Acceptance criteria

- A finding absent from its newest series audit, or marked applied there, does not receive a recurrence-based re-decompose recommendation; a later unannotated reappearance can recur.
- A genuine unresolved structural recurrence retains its existing re-decompose behavior.
- Persisted legacy structural source labels remain structural recurrence evidence without changing saved-review JSON.
- Claim-level and premise-level findings do not receive a destructive re-decompose recommendation.
- Persisted history remains compatible and existing diagnose/render interfaces continue to work.
- Focused regression coverage is added in `tests/test_convergence_diagnosis.py` and essential consumer tests, including telemetry's structural info-severity evidence.

## Deferred

- Broader cross-run similarity improvements for reformulated findings — postponed as separate work because this plan preserves existing matching semantics.
