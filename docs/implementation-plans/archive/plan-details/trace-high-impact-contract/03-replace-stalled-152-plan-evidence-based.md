> **Auto-archived**: this plan was swept on 2026-08-03 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 3 — Replace the stalled #152 plan with the evidence-based scope

## Summary

Rewrite the stalled #152 implementation plan and its three detail files from the completed evidence in steps 1–2. The revised scope must use the real advisory, high-impact recommendation shapes and only the continuation paths that can receive them. Keep the augment rule monotonic and remove the unsupported completeness-loop claim rather than adding new finding plumbing. On green, the #152 plan is implementable, testable, and still clearly separate from the later demote work.

## Table of Contents

- [Summary](#summary) — The revised #152 plan outcome.
- [Table of Contents](#table-of-contents) — Links to each section in this detail.
- [Why](#why) — Why the stalled scope needs correction.
- [Input](#input) — Evidence from the two trace steps that controls the rewrite.
- [Files (creates vs edits)](#files-creates-vs-edits) — Plan and detail files to revise.
- [Implementation](#implementation) — The evidence-based future implementation scope.
- [Tests](#tests) — Verification cases for the rewritten plan artifacts.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [Deferred](#deferred) — Work not authorized by the evidence-based scope.

## Why

The current #152 plan uses a medium-severity example that already blocks and assigns the change to completeness continuation checks that do not receive conceptual audit recommendations. Steps 1–2 establish the parser-supported advisory candidates and which live paths can observe them. The plan must now describe only the predicate and call sites where `impact="high"` can change a continuation result, so implementation does not add compatibility-only edits or invent new data flow.

## Input

- **Step 1 evidence:** Use the implemented tests that establish the normalized `nit` and `info` high-impact recommendation shapes, including the `LOW` control case that normalizes to `medium`.
- **Step 2 evidence:** Use the implemented reachability tests to distinguish `plan_tool/cli/reconcile.py:_iterate_reconcile_loop` and `plan_tool/review.py:audit_plan_until_stable` from `plan_tool/cli/completeness_cmd.py:_run_iterate_convergence_loop`.
- **Existing contract:** Keep `plan_tool/convergence.py:is_blocking`, `plan_tool/review.py:Recommendation`, and `plan_tool/review.py:partition_findings_for_triage` unchanged until the revised #152 implementation steps explicitly own a change.

## Files (creates vs edits)

- **New files:** None.

- **Existing files (edits only):**
  - `docs/implementation-plans/2-gate-convergence-by-impact.md` — Replace the unsupported architecture, file lists, test strategy, acceptance criteria, and deferred wording with the traced scope.
  - `docs/implementation-plans/plan-details/gate-convergence-by-impact/01-impact-aware-blocking-rule.md` — Ground the predicate detail and its tests in the advisory high-impact shapes established by step 1.
  - `docs/implementation-plans/plan-details/gate-convergence-by-impact/02-use-impact-aware-rule-convergence-loops.md` — Limit adoption to the reachable reconcile refreshes and audit materiality check established by step 2.
  - `docs/implementation-plans/plan-details/gate-convergence-by-impact/03-document-shipped-impact-aware-augment.md` — Make documentation and backlog updates conditional on verified implementation, with no claim that the augment already shipped.

## Implementation

- **Foundational logic:** Evidence-based impact-aware continuation scope.

- **Make the plan follow the trace:** Revise `docs/implementation-plans/2-gate-convergence-by-impact.md` so the augment predicate remains `impact == "high"` or the existing severity result. State the observable promotion using the parsed `nit` and `info` candidates from step 1, not a medium-severity example that already blocks.

- **Limit live adoption to reachable paths:** Keep the future loop-wiring step focused on every `plan_tool/cli/reconcile.py:_iterate_reconcile_loop` refresh that sets `ConvergenceState.has_blocking_findings`, plus `plan_tool/review.py:audit_plan_until_stable` when it builds `material_new`. These are the paths where step 2 establishes that a high-impact advisory recommendation can reach the decision.

- **Remove completeness from the future behavior claim:** Do not retain `plan_tool/cli/completeness_cmd.py:_run_iterate_convergence_loop` as an impact-aware adoption site merely because it has a similar severity check. Its `_open_findings_now` collection does not provide the conceptual candidates, so changing it would not implement the evidenced behavior. Keep `plan_tool/cli/completeness_cmd.py:_completeness_has_blocking_findings` and other deterministic/reporting gates severity-based.

- **Rewrite the predicate detail around real inputs:** In `docs/implementation-plans/plan-details/gate-convergence-by-impact/01-impact-aware-blocking-rule.md`, retain the type-only boundary around `plan_tool/review.py:Recommendation` and the `plan_tool/convergence.py:is_blocking_impact` seam. Require coverage for high-impact `nit` and `info`, the medium-or-higher severity floor, and missing impact tags.

- **Rewrite the wiring detail around actual refreshes:** In `docs/implementation-plans/plan-details/gate-convergence-by-impact/02-use-impact-aware-rule-convergence-loops.md`, enumerate the initial and later recommendation refreshes inside `plan_tool/cli/reconcile.py:_iterate_reconcile_loop`, including resume paths. Retain the `plan_tool/review.py:audit_plan_until_stable` productivity rule, while preserving triage behavior: a finding deferred by `partition_findings_for_triage` does not by itself prove another reconcile iteration.

- **Keep shipped-status wording honest:** In `docs/implementation-plans/plan-details/gate-convergence-by-impact/03-document-shipped-impact-aware-augment.md`, require the future documentation step to verify the implemented predicate and selected callers before changing workflow or backlog status. Do not describe #152 as shipped during this plan-maintenance step.

- **Preserve the policy boundary:** Do not turn impact into an impact-only stop rule, alter parser or prompt contracts, change `Recommendation`, or update `plan_tool/convergence_diagnosis.py`. The #152 demote form remains dependent on #154 calibration.

## Tests

- `test_revised_152_plan_names_advisory_high_impact_candidates` — The plan uses normalized `nit` or `info` high-impact findings as its observable augment cases and keeps `LOW`/`medium` out of that claim.
- `test_revised_152_plan_limits_loop_wiring_to_reachable_paths` — The plan and step-2 detail include reconcile refreshes and audit materiality, and do not list completeness continuation as an impact-aware behavior change.
- `test_revised_152_predicate_detail_preserves_severity_floor` — The step-1 detail keeps medium, high, and critical findings blocking regardless of impact.
- `test_revised_152_docs_detail_requires_shipped-code_verification` — The step-3 detail does not mark the augment or backlog item shipped before its implementation is verified.

### Verification (non-code step)

- `plan frontmatter and prose agree` — Check that the revised `steps:` file lists and the body name the same future implementation and test files.
- `evidence matches scope` — Compare each claimed candidate and continuation site with the completed step 1–2 test assertions.
- `no unsupported completeness claim remains` — Search the revised #152 plan and its details for impact-aware completeness-loop adoption.
- `no premature shipped claim remains` — Check that the documentation detail treats shipped status as a future post-implementation verification.

## Acceptance criteria

- `docs/implementation-plans/2-gate-convergence-by-impact.md` describes a high-impact `nit` or `info` finding as the augment’s observable promotion case.
- The revised #152 plan assigns impact-aware continuation wiring only to `plan_tool/cli/reconcile.py:_iterate_reconcile_loop` and `plan_tool/review.py:audit_plan_until_stable`.
- The revised #152 plan does not require an impact-aware edit to `plan_tool/cli/completeness_cmd.py:_run_iterate_convergence_loop`.
- The predicate detail preserves `is_blocking(rec.severity)` as the severity floor for absent, low, and medium impact.
- The documentation detail requires verification of implemented code before describing the augment as shipped.
- The plan and all three revised detail files keep impact-only demotion, recurrence routing, calibration, prompts, schemas, and new plumbing out of scope.

## Deferred

- **#152 impact-only demotion** — Remains blocked on #154 calibration; this rewrite preserves the augment-only rule.
- **New impact emission or completeness plumbing** — Requires separate scope because the traced completeness collection does not carry the conceptual advisory candidates.
- **#153 recurrence routing and #154 calibration** — Remain separate backlog work and must not be folded into the revised #152 plan.
