> **Auto-archived**: this plan was swept on 2026-11-05 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 7 — Close the resolved bug entry and record the Integration re-run outcome

<!-- plan-tool:detail-format-version: 1 -->

## Summary

Remove the resolved plan-authored entry from `BUG_BACKLOG.md` after step 6’s focused retry coverage passes and the implementation is present. Re-run the original Integration candidate-proposal command and use its observed result to choose between closing the entry or filing a narrow residual entry. Keep the backlog as a list of unresolved work: completed work leaves the file, while a still-observed model failure becomes separate follow-up work with fresh evidence. On green, the backlog no longer carries the resolved diagnostic-contract bug and any remaining Integration behavior is clearly scoped.

## Table of Contents

- [Summary](#summary) — States the backlog closure and Integration outcome.
- [Table of Contents](#table-of-contents) — Links to every detail section.
- [Why](#why) — Explains why closure needs both deterministic proof and a live re-run.
- [Input](#input) — Names the completed implementation and source backlog contract.
- [Files (creates vs edits)](#files-creates-vs-edits) — Lists the single backlog edit.
- [Implementation](#implementation) — Defines the closure and residual-reporting decision.
- [Tests](#tests) — States the non-code test-gate status.
- [Acceptance criteria](#acceptance-criteria) — Lists observable completion conditions.
- [References](#references) — Points to the relevant backlog and roadmap contracts.
- [Applicable guardrails](#applicable-guardrails) — Applies the plan’s strict-parser and residual-work limits.
- [Deferred](#deferred) — Separates any further model-behavior remedy from this closure step.

## Why

`BUG_BACKLOG.md` currently keeps the plan-authored candidate-envelope entry open while the parser, prompt, hint, and retry proof work is pending. Once step 6 confirms the deterministic route, the originating Integration command provides the limited live evidence that the changed prompt reaches the model; the backlog must then either remove the fulfilled bug or describe a newly observed residual without preserving a completed entry as if it were still open.

## Input

- **Completed retry proof:** Step 6 proves that the existing `plan_tool/roadmap_candidate_run.py:_run_batch_candidate_proposal` path stores an inert structural candidate after a compliant retry and preserves its rejection-receipt boundaries. Read the landed tests and their result before closing the entry.
- **Source entry:** `BUG_BACKLOG.md` § “Candidate proposal retries still emit incompatible row-operation envelopes after the collection-vocabulary repair” is the only entry this step may remove or replace with a newly observed residual.
- **Backlog lifecycle:** `BUG_BACKLOG.md` § “Triage”, especially “Resolving a bug”, requires regression coverage and verification before removing a fulfilled entry. Completed entries remain in Git history rather than in the live backlog.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `BUG_BACKLOG.md` — remove the fulfilled plan-authored candidate-envelope entry, or replace it with a newly grounded residual entry only when the Integration re-run reproduces incompatible model output.

## Implementation

- **Use the backlog entry as the closure target.** Confirm that steps 1 through 6 landed, that their focused tests pass, and that the original entry’s deterministic claims are covered before changing `BUG_BACKLOG.md`. Do not close the item merely because the planned code exists.

- **Re-run the recorded Integration route.** Run the command named in the entry against the Integration checkout after the implementation is available. Record the command outcome and inspect the resulting candidate state and any rejection evidence; the re-run checks prompt-to-model behavior, while step 6 remains the deterministic proof.

- **Close a successful result by removal.** When the re-run reaches the intended inert structural-candidate path without the reported incompatible envelope behavior, remove the entire `### Candidate proposal retries still emit incompatible row-operation envelopes after the collection-vocabulary repair — PLAN-AUTHORED (...)` entry. Do not replace it with a completed-status note, because `BUG_BACKLOG.md` reserves its live entries for unresolved issues.

- **File only a fresh residual.** When the re-run still produces incompatible `collection` or class-name `row_type` operation fields, remove the fulfilled original entry and add one new BUG entry that names the residual behavior, command outcome, and fresh stored-response evidence. Keep it limited to what the new evidence demonstrates; do not add parse-time repair, widen the retry budget, or reopen the completed diagnostic work without a separate decision.

- **Preserve the backlog’s established shape.** Keep a residual entry under `## BUG` with the fields required by `BUG_BACKLOG.md` § “Triage”. Do not alter `plan_tool/roadmap_candidate.py:parse_candidate_delta`, `plan_tool/roadmap_candidate_run.py:_run_batch_candidate_proposal`, receipt handling, or any test file in this documentation-only step.

## Tests

The test-authoring gate does not apply because step 7 is `change_type: non-code`. Step 6 owns the focused retry tests that support this closure.

### Verification (non-code step)

1. Confirm `tests/test_roadmap_candidate_run.py` covers the malformed-first-response and compliant-retry route required by step 6, and run its focused cases successfully.
2. Re-run the original Integration `--propose-candidate` command and inspect whether it stores an inert structural candidate or produces a fresh rejected-response receipt.
3. Verify `BUG_BACKLOG.md` no longer contains the resolved plan-authored heading.
4. If a residual is observed, verify its new entry contains Files, Symptom, Fix, and Approach and cites fresh Integration evidence.
5. Review the `BUG_BACKLOG.md` diff to confirm no unrelated entry, severity section, or triage rule changed.

## Acceptance criteria

- `BUG_BACKLOG.md` does not retain the fulfilled plan-authored candidate-envelope entry after steps 1 through 6 and their focused verification complete.
- The Integration re-run outcome is reflected by either removal of the resolved entry or one new, evidence-backed residual BUG entry.
- A successful re-run records no new backlog work for the completed diagnostic-contract fix.
- A residual entry, if needed, describes only newly observed model behavior and does not prescribe parse-time repair or changes outside `BUG_BACKLOG.md`.
- The focused step-6 retry coverage passes before the original entry is removed.
- `BUG_BACKLOG.md` retains its existing section structure and live-entry requirements.

## References

- [BUG_BACKLOG.md — read the Triage closure rules and the plan-authored candidate-envelope entry being resolved.](BUG_BACKLOG.md)
- [ROADMAP_FEEDBACK_FORMAT.md — confirm the ledger-to-candidate lifecycle that the re-run must preserve.](ROADMAP_FEEDBACK_FORMAT.md)
- [ROADMAP_FORMAT.md — confirm that a successful proposal remains an inert structural candidate rather than an accepted-head change.](ROADMAP_FORMAT.md)

## Applicable guardrails

- **The plan’s “## Plan intent”, bounded correction route:** This step may close the entry only after the implemented route reaches the candidate-storage result that the plan defines.
- **The plan’s “## Scope guardrails”, strict parser and identity boundaries:** Do not describe a backlog closure as authority to change parsing, receipt identity, replay identity, or accepted-head behavior.
- **The plan’s “## Out of scope”, no repair or retry expansion:** A residual result must become separate backlog work rather than a reason to add coercion, change receipts, or extend the retry loop in this step.

## Deferred

- Further prompt or parser changes for a reproduced residual — file a separate BUG entry with the new Integration evidence; this closure step does not choose or implement its remedy.
