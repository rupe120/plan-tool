> **Auto-archived**: this plan was swept on 2026-08-03 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 3 — Document verified impact-aware augment behavior

## Summary

After steps 1–2 are implemented and verified, document the shipped augment-only rule and update backlog status. This documentation step must confirm the predicate and its selected callers before claiming shipment; maintaining this plan does not mark #152 or its augment as shipped.

## Table of Contents

- [Summary](#summary) — Documentation outcome.
- [Why](#why) — Why verification precedes status updates.
- [Input](#input) — Code that must exist first.
- [Files (creates vs edits)](#files-creates-vs-edits) — Future documentation files.
- [Implementation](#implementation) — Conditional documentation work.
- [Tests](#tests) — Non-code verification.
- [Acceptance criteria](#acceptance-criteria) — Observable checks.
- [Deferred](#deferred) — Related work kept separate.

## Why

Workflow and backlog wording must describe implemented behavior, not this planning rewrite. The eventual documentation must accurately state that high impact augments severity-based continuation only at the traced reconcile and audit paths, while the later #152 demote work remains pending on #154 calibration.

## Input

- Verify `plan_tool/convergence.py:is_blocking_impact` implements `impact == "high" or is_blocking(severity)`.
- Verify every selected `plan_tool/cli/reconcile.py:_iterate_reconcile_loop` refresh uses the predicate and `plan_tool/review.py:audit_plan_until_stable` uses it for `material_new`.
- Verify completeness continuation, deterministic/reporting gates, `Recommendation`, prompts, schemas, and `plan_tool/convergence_diagnosis.py` remain outside the implementation.
- If this code and its focused tests are not verified, stop without describing the augment or backlog item as shipped.

## Files (creates vs edits)

- **New files:** None.

- **Existing files (edits only, after verification):**
  - `docs/AUDIT_FLOW.md` — Document the implemented convergence augment and its limits.
  - `CLAUDE.md` — Update contributor guidance at the convergence-policy boundary.
  - `BACKLOG.md` — Record the verified augment status while retaining the demote work behind #154.

## Implementation

- Verify the predicate and selected callers before editing workflow documentation or backlog status.
- Describe the augment rule: high-impact advisory recommendations can keep the selected convergence paths open; medium, high, and critical severity remain blocking regardless of impact.
- Name the actual adoption boundary: reconcile refreshes and audit materiality. Do not claim that completeness continuation gained impact-aware behavior.
- Keep triage separate: `partition_findings_for_triage` still controls apply/defer behavior, and deferral alone does not guarantee another reconcile iteration.
- Mark only the verified augment slice as shipped. Keep #152 open if its impact-only demote slice remains pending on #154 calibration.
- Do not edit code, tests, prompts, schemas, or generated documentation in this non-code step.

## Tests

- No automated test changes — this step updates documentation and backlog tracking only after implementation verification.

### Verification (non-code step)

- `implemented predicate matches documentation` — Compare the documented rule with `is_blocking_impact` and its focused tests.
- `selected callers match documentation` — Confirm every reconcile refresh and audit `material_new` use is implemented; confirm completeness is not described as impact-aware.
- `shipped status follows verification` — Update workflow and backlog wording only after the predicate and callers are verified in code.
- `deferred scope remains separate` — Confirm impact-only demotion, recurrence routing, calibration, prompts, schemas, and new plumbing remain unclaimed.

## Acceptance criteria

- Documentation and backlog wording change only after implementation verification.
- The published rule preserves `is_blocking(rec.severity)` as the severity floor and identifies high-impact `nit` or `info` as the promotion case.
- Documentation names only reconcile refreshes and audit materiality as impact-aware continuation behavior.
- Backlog status distinguishes the verified augment from #152’s demote slice, which remains dependent on #154.
- This planning-maintenance step does not itself claim the augment is shipped.

## Deferred

- #152 impact-only demotion remains blocked on #154 calibration.
- #153 recurrence routing and #154 calibration remain separate backlog work.
- New impact emission or completeness plumbing requires separate scope.
