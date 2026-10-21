> **Auto-archived**: this plan was swept on 2026-08-03 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

---
title: Gate Convergence By Impact
status: completed
priority: medium
enforce_step_tests: true
steps:
- id: 1
  title: Add the impact-aware blocking rule
  files:
  - plan_tool/convergence.py
  - tests/test_convergence.py
  complexity: low
  change_type: feature
  detail: docs/implementation-plans/plan-details/gate-convergence-by-impact/01-impact-aware-blocking-rule.md
  status: done
- id: 2
  title: Use the impact-aware rule in reachable convergence paths
  files:
  - plan_tool/cli/reconcile.py
  - plan_tool/review.py
  - tests/test_cli.py
  - tests/test_review.py
  complexity: medium
  change_type: feature
  depends_on:
  - 1
  detail: docs/implementation-plans/plan-details/gate-convergence-by-impact/02-use-impact-aware-rule-convergence-loops.md
  status: done
- id: 3
  title: Document verified impact-aware augment behavior
  files:
  - docs/AUDIT_FLOW.md
  - CLAUDE.md
  - BACKLOG.md
  allowed_mentions:
  - CLAUDE.md
  - BACKLOG.md
  complexity: low
  change_type: non-code
  depends_on:
  - 2
  detail: docs/implementation-plans/plan-details/gate-convergence-by-impact/03-document-shipped-impact-aware-augment.md
  status: done
---
# Gate Convergence By Impact

## Overview

Add an augment-only impact-aware convergence rule: a recommendation blocks when `rec.impact == "high"` or its severity already blocks. The observable promotions are parser-supported `nit` and `info` recommendations with high impact; `LOW` normalizes to `medium` and already blocks by severity. Adopt the rule only where those advisory recommendations can reach a continuation decision: reconcile refreshes and audit materiality. This plan does not implement impact-only demotion.

## Problem statement

Severity-only continuation can stop despite a high-impact advisory recommendation. The completed trace establishes that conceptual advisory recommendations reach `plan_tool/cli/reconcile.py:_iterate_reconcile_loop` and `plan_tool/review.py:audit_plan_until_stable`, but not `plan_tool/cli/completeness_cmd.py:_run_iterate_convergence_loop`. The plan must therefore add a monotonic predicate and wire only the paths that can observe its promotion, without inventing new completeness finding flow.

## Architecture

Add `is_blocking_impact(rec: Recommendation) -> bool` beside `is_blocking` in `plan_tool/convergence.py`. The predicate returns `rec.impact == "high" or is_blocking(rec.severity)`. It preserves `is_blocking` as the severity floor: absent, low, and medium impact cannot demote medium, high, or critical severity.

Use the predicate at every `ConvergenceState.has_blocking_findings` refresh in `plan_tool/cli/reconcile.py:_iterate_reconcile_loop`, including resume paths, and when `plan_tool/review.py:audit_plan_until_stable` builds `material_new`. Preserve `partition_findings_for_triage` behavior: a triage-deferred finding alone does not promise another reconcile iteration. Leave completeness continuation, deterministic/reporting gates, `Recommendation`, parsing, prompts, and `convergence_diagnosis.py` unchanged.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

- Impact-only demotion: retain severity-based blocking until a separate #152 implementation consumes the shipped #154 calibration evidence.
- New impact emission, parser/schema changes, or conceptual-finding plumbing into completeness.
- Recurrence routing (#153/#158), prompt changes, and `plan_tool/convergence_diagnosis.py` changes.
- Severity-only deterministic and reporting gates, including `plan_tool/cli/completeness_cmd.py:_completeness_has_blocking_findings`.

## Risks

- High-impact `nit` and `info` findings can add iterations. The monotonic predicate bounds this change because it cannot make an existing block advisory.
- Missing an reconcile refresh could let a resumed loop revert to severity-only behavior. Update and test every refresh, including resume paths.
- Treating completeness as a compatible adoption site would claim behavior its collection cannot observe. Keep it severity-based unless separate scope adds the missing data flow.

## Testing

- Add predicate coverage in `tests/test_convergence.py` for high-impact `nit` and `info`, the medium-or-higher severity floor, missing impact, and the `LOW`/`medium` control case.
- Add reconcile tests in `tests/test_cli.py` for the initial and later refreshes, including resume paths, with a high-impact advisory recommendation that reaches the existing decision.
- Add audit-loop tests in `tests/test_review.py` showing a high-impact advisory recommendation makes `material_new` productive while untagged advisory findings remain low-yield.
- Do not add completeness continuation tests as impact-aware behavior; retain its severity-based coverage.

**Per-step test strategy** (derived from each step's `change_type`):

- step 1 (feature) — unit tests added with the implementation; green before completion.
- step 2 (feature) — focused reconcile and review tests added with the implementation; green before completion.
- step 3 (non-code) — verify the implemented predicate and selected callers before changing documentation or backlog status.

## Acceptance criteria

- `plan_tool/convergence.py:is_blocking_impact` promotes high-impact `nit` or `info` recommendations while retaining `is_blocking(rec.severity)` as the severity floor.
- Every relevant refresh in `plan_tool/cli/reconcile.py:_iterate_reconcile_loop`, including resume paths, uses the shared predicate.
- `plan_tool/review.py:audit_plan_until_stable` uses the predicate when building `material_new`.
- `plan_tool/cli/completeness_cmd.py:_run_iterate_convergence_loop` receives no impact-aware behavior change.
- The documentation step verifies implemented code before describing the augment or backlog item as shipped.
- The implementation leaves impact-only demotion, recurrence routing, prompts, schemas, and new plumbing out of scope; calibration is shipped separately as advisory evidence.

## Deferred

- #152 impact-only demotion remains a separate implementation slice that can consume #154's shipped calibration evidence.
- #153 recurrence routing is superseded by #158; #154 calibration is complete.
- Any completeness impact plumbing requires separate scope and evidence.
