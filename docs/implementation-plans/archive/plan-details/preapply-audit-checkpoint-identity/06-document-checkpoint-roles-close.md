> **Auto-archived**: this plan was swept on 2026-08-05 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 6 — Document checkpoint roles and close the checkpoint identity handoff

## Summary

Document the completed checkpoint-role contract in `docs/AUDIT_FLOW.md`, `docs/AUDIT_RESUME_FLOW.md`, and `docs/cli/completeness-audit.md`. Update `BUG_BACKLOG.md` and `handoffs/2026-08-05-checkpoint-identity-session.md` to close the resolved risk with the actual verification record. The key decision is that a pre-apply checkpoint remains durable recovery evidence but is not a completed audit for reuse or convergence history. On green, operators can tell which saved reports are safe to reuse, which count as completed runs, and how crash recovery preserves evidence without double-counting it.

## Table of Contents

- [Summary](#summary) — Scope and expected completed state.
- [Table of Contents](#table-of-contents) — Section guide.
- [Why](#why) — The documentation gap this closeout removes.
- [Input](#input) — Completed persistence and reader behavior this step documents.
- [Files (creates vs edits)](#files-creates-vs-edits) — Documentation and closure records to update.
- [Implementation](#implementation) — Checkpoint-role policy and documentation approach.
- [Tests](#tests) — Existing implementation coverage and non-code verification.
- [Acceptance criteria](#acceptance-criteria) — Observable documentation and closure results.
- [References](#references) — Persisted-JSON and test references.
- [Applicable guardrails](#applicable-guardrails) — Plan boundaries this closeout must preserve.
- [Deferred](#deferred) — Work outside this documentation and closure step.

## Why

`docs/AUDIT_FLOW.md` still describes audit recovery as having no checkpoints, while `plan_tool/cli/completeness_phases.py:write_pre_apply_audit_checkpoint` deliberately saves one before applies begin. Without a clear role policy, the documentation can lead operators to treat recovery evidence as a completed audit, repeating the ambiguity that steps 1–5 remove from `plan_tool/completeness_report.py:resolve_reusable_audit`, `plan_tool/convergence_diagnosis.py:load_report_history`, and `plan_tool/cli/completeness_phases.py:_completeness_convergence_diagnosis`.

## Input

- **Persisted role from steps 1–2:** Read the landed `is_pre_apply_checkpoint` contract from `plan_tool/review_persistence.py:SavedReview` and `DATA_CONTRACT.md:### SavedReview`. Step 2 marks only the sidecar produced by `plan_tool/cli/completeness_phases.py:write_pre_apply_audit_checkpoint` and emits version 3; ordinary final saves remain unmarked at their current versions.

- **Reuse and history rules from steps 3–4:** Document the final-only eligibility enforced by `plan_tool/completeness_report.py:resolve_reusable_audit` and `plan_tool/convergence_diagnosis.py:load_report_history`.

- **Rendering rule from step 5:** Document that `plan_tool/cli/completeness_phases.py:_completeness_convergence_diagnosis` receives final-only history and adds the current in-memory run once. It must not identify a checkpoint by position or timestamp.

- **Landed code wins:** Confirm field spelling, accepted role states, and reader behavior from the completed code and focused tests before editing prose. If implementation diverges from this plan, record the discrepancy in `handoffs/2026-08-05-checkpoint-identity-session.md` rather than documenting an unlanded contract.

## Files (creates vs edits)

- **New files:** None.

- **Existing files (edits only):**
  - `docs/AUDIT_FLOW.md` — describe the pre-apply checkpoint in the iterative completeness sequence and update the `## Source map` with the role-aware writer, readers, and final-run diagnosis.
  - `docs/AUDIT_RESUME_FLOW.md` — distinguish durable checkpoint recovery evidence from an eligible final reusable audit in `## TL;DR`, `## What's reused vs re-derived`, `## Crash / interrupt recovery`, and `## Source map`.
  - `docs/cli/completeness-audit.md` — clarify the `--iterate`, `--reuse-audit`, and `--reuse-audit-id` behavior for marked checkpoints and eligible final sidecars.
  - `BUG_BACKLOG.md` — remove the resolved `### Pre-apply audit checkpoints are indistinguishable from final reports downstream` RISK after verification succeeds.
  - `handoffs/2026-08-05-checkpoint-identity-session.md` — append the completion evidence, retain the audit ledger and legacy-policy decision, and replace the open next action with the closed outcome.

## Implementation

- **Foundational logic: final-only eligibility for persisted completeness reports.** Document that version-3 `is_pre_apply_checkpoint: true` identifies a durable pre-apply checkpoint; raw version-3 `false` or an unmarked version-1/2 completeness sidecar identifies an ordinary final; malformed, misplaced, or role/version-mismatched metadata remains inspectable but is unsafe for reuse and convergence history. State that reusable-audit selection requires both `SavedReview.kind="completeness"` and the ordinary-final role, and that role-unaware version-1/2 readers reject version-3 checkpoints instead of silently treating them as final.

- **Document role, not filename or recency.** In `docs/AUDIT_FLOW.md:## High-level flow`, show that an iterative audit writes the checkpoint before `apply_finding`, then writes the final report after the loop. Explain that both artifacts retain the existing completeness filename and kind conventions, use distinct collision-safe canonical stems when they land in one second, and rely on persisted role for downstream eligibility.

- **Describe the complete reader boundary.** In the flow source map, name `plan_tool/review_persistence.py:SavedReview`, `plan_tool/cli/completeness_phases.py:write_pre_apply_audit_checkpoint`, `plan_tool/completeness_report.py:resolve_reusable_audit`, and `plan_tool/convergence_diagnosis.py:load_report_history`. State that reuse selects the newest eligible `kind="completeness"` ordinary final and rejects a filename/payload kind mismatch, while history creates snapshots only from eligible ordinary finals.

- **Make pinned reuse safe and understandable.** In `docs/cli/completeness-audit.md:## Options`, explain that `--reuse-audit-id` remains an exact selection request, but a marked checkpoint or unknown-role sidecar is not reusable and leads to a fresh audit. Do not add a new flag or imply that operators must rename sidecars.

- **Keep recovery durable.** In `docs/AUDIT_RESUME_FLOW.md:## Crash / interrupt recovery`, state that the checkpoint survives a crash during apply and remains available as recovery evidence even when a rapid final report is written in the same wall-clock second. A rerun still derives deterministic findings from disk, and the checkpoint does not become a reusable conceptual audit or a completed convergence snapshot.

- **Describe final rendering without the old workaround.** Update the relevant flow prose and source map to explain that `plan_tool/cli/completeness_phases.py:_completeness_convergence_diagnosis` trusts role-filtered history and appends one current `RunSnapshot`. Do not retain language that says the newest saved report is removed as a checkpoint.

- **Keep consumer scope precise.** `plan_tool/telemetry_analysis.py` and `plan_tool/split_criteria.py` consume `load_report_history`, so they inherit final-only history without their own role rules. Do not describe checkpoints as unusable everywhere: `plan_tool/cli/completeness_cmd.py:cmd_completeness_apply` and `plan_tool/cli/data_contract_cmd.py:_newest_saved_completeness_with_contract_payload` have separate saved-artifact recovery behavior.

- **Close records only on evidence.** Remove the matching RISK from `BUG_BACKLOG.md` only after focused tests and the required iterative completeness audit pass. In `handoffs/2026-08-05-checkpoint-identity-session.md`, record the exact commands, report paths, outcomes, material findings, and the user-approved version-3 scope decision; preserve the settled legacy policy and mark the next action complete.

- **Keep the documentation narrow.** Preserve the existing headings where possible and update each flow document’s source map when adding symbols. Do not document a migration, pruning policy, filename change, or broader report-schema cleanup.

## Tests

The test-authoring gate does not apply because this is a non-code step. Use the landed implementation coverage as evidence for the documentation claims; do not add or modify test files here.

- Checkpoint-role persistence matrix (`tests/test_review_persistence.py`) — confirms version-3 checkpoints, ordinary finals, version-1/2 legacy absence, malformed-role handling, and role-unaware-reader rejection.
- Reusable-audit selection matrix (`tests/test_completeness_report.py`) — confirms default and pinned lookup skip marked or unknown checkpoint roles.
- Convergence-history matrix (`tests/test_convergence_diagnosis.py`) — confirms marked and unknown roles never become `RunSnapshot` entries.
- `test_current_run_counted_once_iterate_after_checkpoint` (`tests/cli/test_completeness_cmd.py`) — confirms role-filtered history retains prior finals and counts the current iterative run once.

### Verification (non-code step)

1. **Documentation-to-code check** — compare every cited symbol and role rule against the landed implementations in `plan_tool/review_persistence.py`, `plan_tool/completeness_report.py`, `plan_tool/convergence_diagnosis.py`, and `plan_tool/cli/completeness_phases.py`.

2. **Focused regression run** — run `uv run pytest -q tests/test_review_persistence.py tests/test_completeness_report.py tests/test_convergence_diagnosis.py tests/cli/test_completeness_cmd.py` and record the result in `handoffs/2026-08-05-checkpoint-identity-session.md`.

3. **Required completion audit** — run `uv run plan-tool --backend codex completeness-audit preapply-audit-checkpoint-identity --iterate`, read the saved report, and add its exact path and outcome to the handoff ledger before clearing the backlog record.

4. **Documentation sweep** — confirm `docs/AUDIT_FLOW.md` no longer says the audit path has no checkpoints, and confirm the flow source maps name the writer, role-aware reuse reader, and role-aware history reader.

5. **Diff check** — run `git diff --check` for the five in-scope files and confirm the handoff’s final status matches the backlog state.

## Acceptance criteria

- `docs/AUDIT_FLOW.md` describes the checkpoint-before-apply ordering and the final-report-after-loop ordering, with the checkpoint identified by persisted role rather than filename position.

- `docs/AUDIT_RESUME_FLOW.md` states that version-3 checkpoints remain durable recovery evidence while only ordinary finals, including unmarked version-1/2 legacy sidecars, are eligible for reuse and convergence history; it explains the older-reader rejection fence.

- `docs/cli/completeness-audit.md` explains that default reuse skips newer marked checkpoints and filename/payload kind mismatches, and that a pinned marked, unknown-role, or non-completeness sidecar does not supply reusable findings.

- The flow documentation states that malformed, misplaced, or role/version-mismatched metadata fails closed for reuse and convergence without claiming it is deleted, migrated, or silently reclassified.

- The flow documentation states that same-second checkpoint and final publication allocates distinct canonical report stems without a new suffix or directory, so recovery evidence is not overwritten.

- `BUG_BACKLOG.md` no longer contains the resolved checkpoint-identity RISK, and unrelated backlog entries remain unchanged.

- `handoffs/2026-08-05-checkpoint-identity-session.md` contains the final audit command, report path, focused test result, outcome, and closure decision, with no remaining implementation next action.

- The focused implementation regression suite and required iterative completeness audit have completed successfully before the backlog and handoff are closed.

## References

- [json — JSON encoder and decoder](https://docs.python.org/3/library/json.html) — Review the parsing and serialization behavior behind the persisted role field.

- [RFC 8259: The JavaScript Object Notation (JSON) Data Interchange Format](https://www.rfc-editor.org/rfc/rfc8259.html) — Use the JSON object and value rules when describing malformed marker handling.

- [How to parametrize fixtures and test functions](https://docs.pytest.org/en/stable/how-to/parametrize.html) — Reference for the upstream role-selection regression matrices.

## Applicable guardrails

- **The plan’s “Plan intent”** — keep checkpoint persistence as crash-recovery evidence while documenting its exclusion from final-report reuse and convergence only.

- **The plan’s “Step intent”** — leave operators and the next session with the settled role policy, recovery behavior, and closure record; do not turn this into a new implementation change.

- **The plan’s “## Out of scope”** — do not use documentation closeout to authorize filename changes, legacy-sidecar migration, pruning, changed crash recovery, or broader convergence and persistence redesign.

## Deferred

- Legacy report migration or cleanup — historical unmarked sidecars remain in place under the plan’s legacy policy; migration, pruning, and heuristic classification are outside this step.

- Saved-artifact apply eligibility — any role-policy change for `plan_tool/cli/completeness_cmd.py:cmd_completeness_apply` or `plan_tool/cli/data_contract_cmd.py:_newest_saved_completeness_with_contract_payload` needs a separate recovery-flow decision.
