> **Auto-archived**: this plan was swept on 2026-08-05 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 3 — Record validation and close the source risk

## Summary

Remove the completed reused-coverage RISK from `BUG_BACKLOG.md` and create a session handoff with the shipped validation evidence. Verify the dependency outcomes through their focused persistence, report, CLI, and contract tests before retiring the tracking record. Treat the handoff as the durable completion record: it must distinguish executed results from planned checks and preserve the separate checkpoint-identity risk. On green, the backlog no longer advertises the resolved defect and the next session can see exactly what was verified.

## Table of Contents

- [Summary](#summary) — Reviewer overview of the closeout work.
- [Table of Contents](#table-of-contents) — Links to each section in this detail.
- [Why](#why) — Why the source RISK must be retired with evidence.
- [Input](#input) — Dependency outcomes and tracking policy this step reads.
- [Files (creates vs edits)](#files-creates-vs-edits) — The handoff and backlog changes.
- [Implementation](#implementation) — Validation, risk retirement, and handoff rules.
- [Tests](#tests) — Dependency regressions that support the closeout.
- [Acceptance criteria](#acceptance-criteria) — Observable closure conditions.
- [References](#references) — CLI execution reference for the no-call boundary.
- [Applicable guardrails](#applicable-guardrails) — Scope limits for this documentation-only step.
- [Deferred](#deferred) — Separate risk that remains open.

## Why

`BUG_BACKLOG.md` still lists `completeness-audit --reuse-audit loses its original coverage verdict` even after steps 1 and 2 are intended to preserve and replay that provenance. Because `BUG_BACKLOG.md` removes completed items rather than keeping shipped-history notes, deleting the entry without a durable validation record would make the result hard to audit later. This step closes that gap by recording the evidence that a fresh and fingerprint-fresh reused audit now agree without another conceptual Claude call.

## Input

- **Step 1 outcome:** Confirm `plan_tool/review_persistence.py:SavedReview`, `save_review`, `load_review`, and `update_annotation` preserve the normalized known-or-unknown coverage result through the completeness sidecar.

- **Step 2 outcome:** Confirm `plan_tool/completeness_report.py:ReusableAudit` and `resolve_reusable_audit` expose saved coverage, while `plan_tool/cli/completeness_cmd.py:_resolve_audit_reuse`, `finalize_completeness_run`, and `_run_iterate_convergence_loop` deliver it to both report paths.

- **Report boundary:** Confirm `plan_tool/cli/completeness_phases.py:_render_completeness_json`, `_render_grouped_report`, and `write_pre_apply_audit_checkpoint` receive the selected result without changing coverage semantics.

- **Tracking policy:** Follow the opening policy in `BUG_BACKLOG.md`: completed entries are removed and Git history plus the session handoff retain the record.

## Files (creates vs edits)

- **New files:**
  - `handoffs/2026-08-04-reuse-audit-coverage-verdict-session.md` — Record the shipped behavior, executed validation, audit status, and remaining separate risk.

- **Existing files (edits only):**
  - `BUG_BACKLOG.md` — Remove the complete RISK entry headed `completeness-audit --reuse-audit loses its original coverage verdict`.

## Implementation

- **Foundational logic: evidence-based risk closure.** Retire the source RISK only after the dependency regressions prove that saved coverage survives persistence and is replayed on accepted reuse without invoking `plan_tool/review.py:audit_plan_until_stable`.

- **Validate the landed code, not the sibling detail proposals.** Check the step 1 persistence seam and the step 2 reuse seam in the code and tests before editing `BUG_BACKLOG.md`. A missing known-or-unknown distinction, a missing iterate handoff, or a test that permits a conceptual audit call leaves the RISK open.

- **Use focused proof for each behavior.** Capture persistence of known coverage, conservative handling of a coverage-less legacy sidecar, audit-only reuse, and `--iterate` reuse. The no-call cases must make the conceptual-audit seam unreachable; a report that merely looks correct is not proof that reuse skipped the call.

- **Keep Markdown and JSON together.** Record evidence that the same selected coverage result reaches `plan_tool/cli/completeness_phases.py:_render_completeness_json` and `_render_grouped_report`. For iterate reuse, include the existing `write_pre_apply_audit_checkpoint` path so the checkpoint and final report do not disagree.

- **Delete the source entry as a whole.** Remove its heading and all of its fields from `BUG_BACKLOG.md`. Do not leave a completed marker or replace it with a new backlog item; retain the surrounding `## RISK` section and unrelated entries unchanged.

- **Make the handoff the completion record.** In `handoffs/2026-08-04-reuse-audit-coverage-verdict-session.md`, record the dependency revisions or checkout identifier, each command actually run, its exit status and result summary, and the coverage scenarios it proved. State the final audit outcome separately, including an explicit blocked or not-run status when applicable; never record an expected result as if it ran.

- **Name the boundary that remains open.** State that the `BUG_BACKLOG.md` RISK headed `Pre-apply audit checkpoints are indistinguishable from final reports downstream` was not changed. It concerns checkpoint identity and history selection, not restoration of saved coverage.

## Tests

This non-code step adds no test file. Use the dependency-step regressions as the evidence required before retiring the source RISK.

### Verification (non-code step)

1. `tests/test_review_persistence.py:test_save_load_normalized_audit_coverage` — Confirms a valid coverage result round-trips through the saved-review sidecar.

2. `tests/test_review_persistence.py:test_missing_or_malformed_audit_coverage_is_unknown_but_loadable` and `test_update_annotation_preserves_audit_coverage` — Confirm legacy tolerance does not imply clean coverage and a walk rewrite retains known provenance.

3. `tests/test_completeness_report.py:test_write_completeness_report_persists_normalized_audit_coverage` and `test_resolve_reusable_audit_exposes_saved_audit_coverage` — Confirm the completeness writer and reuse read seam carry the saved value.

4. `tests/test_completeness_report.py:test_resolve_reusable_audit_coverage_less_sidecar_is_fresh_and_unknown` — Confirms a fingerprint-fresh legacy sidecar remains reusable while reporting unknown coverage.

5. `tests/cli/test_completeness_cmd.py:test_audit_only_reuse_replays_budget_limited_coverage_without_audit` — Confirms reused Markdown and JSON retain budget-limited coverage while the conceptual audit cannot run.

6. `tests/cli/test_completeness_cmd.py:test_iterate_reuse_replays_confirmed_low_yield_coverage_without_audit` — Confirms reused iterate reporting and its checkpoint path retain the low-yield verdict without an up-front audit.

7. `tests/cli/test_completeness_cmd.py:test_coverage_less_reuse_renders_unknown_without_audit` — Confirms legacy reuse stays call-free and does not render a clean default.

8. `tests/test_data_contract.py:test_saved_review_coverage_is_conditionally_persisted` — Confirms the documented saved-review contract still identifies coverage as optional provenance.

## Acceptance criteria

- The focused persistence, completeness-report, CLI, and data-contract test command completes successfully, and `handoffs/2026-08-04-reuse-audit-coverage-verdict-session.md` records the actual command and result.

- The handoff identifies evidence for known budget-limited reuse, known low-yield reuse, and coverage-less legacy reuse, including the no-conceptual-audit boundary.

- The handoff records the actual final audit status without presenting an unrun or blocked audit as successful.

- `BUG_BACKLOG.md` has no remaining heading or fields for `completeness-audit --reuse-audit loses its original coverage verdict`.

- `BUG_BACKLOG.md` retains the separate checkpoint-identity RISK.

- This step’s documentation diff changes only `BUG_BACKLOG.md` and `handoffs/2026-08-04-reuse-audit-coverage-verdict-session.md`.

## References

- [Claude Code CLI Reference](https://code.claude.com/docs/en/cli-usage) — Use when recording any CLI audit invocation and the no-call reuse boundary.

## Applicable guardrails

- **The plan’s “## Plan intent”, report-equivalence boundary:** Close the RISK only with evidence that fresh and fingerprint-fresh reused reports preserve the same coverage verdict without another conceptual audit call.

- **The plan’s “## Step intent”, closeout boundary:** Limit this step to validation evidence and tracking updates; it does not change the shipped implementation.

- **The plan’s “## Out of scope”, audit-policy boundary:** Record observed coverage behavior without changing the policy that produces it.

- **The plan’s “## Out of scope”, legacy-reuse boundary:** Do not treat a coverage-less legacy sidecar as grounds to require a replacement audit.

- **The plan’s “## Out of scope”, unrelated-persistence boundary:** Leave general saved-review behavior and the separate checkpoint-identity work outside this closeout.

## Deferred

- **Checkpoint identity and historical checkpoint handling** — Remain in the separate `BUG_BACKLOG.md` RISK; this step closes only the saved-coverage source risk.
