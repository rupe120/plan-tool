> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 5 — Remove the resolved quota bug and refresh its queue entries

## Summary

Retire the resolved monthly plan-quota BUG from `BUG_BACKLOG.md` and remove its obsolete delivery phase from `docs/implementation-plans/backlog-arcs/bug-backlog-draining-arc.md`. Refresh `BACKLOG.md` so its queue facts and current pick reflect the remaining live work. Treat `BUG_BACKLOG.md` as the source for severity counts and preserve the status of unresolved items rather than re-triaging them. On green, no active queue presents quota recovery or another shipped delivery as pending work.

## Table of Contents

- [Summary](#summary) — Reviewer overview of the queue cleanup.
- [Table of Contents](#table-of-contents) — Navigation for this detail file.
- [Why](#why) — Why stale queue records need removal.
- [Input](#input) — Completion evidence and queue records this step reads.
- [Files (creates vs edits)](#files-creates-vs-edits) — The three tracking documents updated here.
- [Implementation](#implementation) — Required retirement and queue-refresh rules.
- [Tests](#tests) — Non-code verification for the tracking records.
- [Acceptance criteria](#acceptance-criteria) — Observable completed queue state.
- [Applicable guardrails](#applicable-guardrails) — Scope limits for this documentation-only closure.
- [Deferred](#deferred) — Work this queue cleanup does not take on.

## Why

`BUG_BACKLOG.md`, `BACKLOG.md`, and `docs/implementation-plans/backlog-arcs/bug-backlog-draining-arc.md` still present the monthly quota failure as active work. Once steps 1–4 have delivered, tested, and documented the fix, those records would send a later session toward duplicate work and hide the actual current priority.

## Input

- **Step 4 outcome:** close the source records only after step 4 confirms that the documentation agrees with the delivered behavior from steps 1–3. A completed detail file alone is not closure evidence.

- **Bug-record contract:** use `BUG_BACKLOG.md: ## Triage` and `## BUG` as the source of truth for which BUG entries remain. Keep the `Files`, `Symptom`, `Fix`, and `Approach` contract for every surviving entry.

- **Queue contract:** update `BACKLOG.md: ## Priority (mission-grounded)`, `### Now / Next / Blocked / Parked (working set)`, and `Next concrete pick` from the remaining live records. Select no replacement pick in advance; the live BUG inventory determines it when this step runs.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `BUG_BACKLOG.md` — remove the complete `### A monthly plan-quota exhaustion is classified and retried exactly like a short rate limit` record while preserving the remaining severity sections and entries.
  - `BACKLOG.md` — refresh `Current queue facts`, the working-set board, and `Next concrete pick` so they no longer name quota recovery or another shipped delivery.
  - `docs/implementation-plans/backlog-arcs/bug-backlog-draining-arc.md` — remove `### Phase 3 — Stop expensive quota churn`, update `## Purpose and boundary` for the remaining entry count, and keep the remaining phase numbering continuous.

## Implementation

- **Retire the whole resolved record.** Delete the monthly plan-quota heading in `BUG_BACKLOG.md: ## BUG` together with every field belonging to it. Do not leave an orphaned `Fix`, `Approach`, or origin paragraph behind.

- **Keep the remaining BUG queue intact.** Preserve the ordering and text of the escalation-evidence and YAML-scalar entries. Keep the `## BUG`, `## RISK`, and `## MINOR` headings so the triage structure remains usable even when a section has no entries.

- **Derive queue counts from the live headings.** After the removal, `BACKLOG.md: Current queue facts` must report the two remaining BUG entries, three RISK entries, and no MINOR entries. Update its checked-on date to the completion date rather than carrying forward a stale snapshot.

- **Promote only documented live work.** Replace the quota-specific `Now (confirmed BUG)` and `Next concrete pick` text in `BACKLOG.md: ### Now / Next / Blocked / Parked (working set)` with a then-current remaining BUG or explicit triage state. Do not name a shipped delivery or change the status of dependent or blocked work.

- **Avoid duplicate board ownership.** Keep the selected remaining item in one working-set lane after the refresh. If a `Now` row becomes its queue entry, remove any duplicate while preserving the item’s current-state wording.

- **Remove the obsolete arc phase as a unit.** Delete the full quota-focused `Phase 3` section from `docs/implementation-plans/backlog-arcs/bug-backlog-draining-arc.md`, including its old deferral, implementation outline, and exit condition. Update the later phase labels so the live sequence has no gap, without changing the remaining phase content.

- **Sweep the retired vocabulary in scope.** Search the three declared files for the exact monthly-quota bug title, `plan-quota-recovery`, and the retired quota-exhaustion wording. Remove each stale queue reference, but do not use a broad `quota` search as a removal rule.

## Tests

**Test-authoring gate:** does not apply because step 5 has `change_type: non-code`, and no test file is in scope.

### Verification (non-code step)

1. **Bug-record count check** — confirm `BUG_BACKLOG.md: ## BUG` contains exactly three `###` entries and none is the monthly plan-quota title.

2. **Severity-facts check** — compare `BACKLOG.md: Current queue facts` with the live `BUG_BACKLOG.md` headings; it reports two BUG entries, three RISK entries, and no MINOR entries.

3. **Current-pick check** — confirm `BACKLOG.md: ### Now / Next / Blocked / Parked (working set)` and `Next concrete pick` contain no quota-recovery wording, name no shipped delivery, and list any selected remaining item once.

4. **Arc-continuity check** — confirm `docs/implementation-plans/backlog-arcs/bug-backlog-draining-arc.md: ## Purpose and boundary` names the remaining live entries, has no quota phase, and retains continuous live phase labels.

5. **Vocabulary-sweep check** — run a scoped search across `BACKLOG.md`, `BUG_BACKLOG.md`, and `docs/implementation-plans/backlog-arcs/bug-backlog-draining-arc.md`; the retired monthly-quota title, `plan-quota-recovery`, and retired quota-exhaustion wording return no matches.

6. **Regression check** — run `uv run pytest tests/ -q -n auto`.

## Acceptance criteria

- `BUG_BACKLOG.md` no longer contains the monthly plan-quota BUG record or any of its field text.

- The surviving `BUG_BACKLOG.md` headings support the counts stated in `BACKLOG.md: Current queue facts`.

- `BACKLOG.md` has no working-set or next-pick reference to quota recovery or another shipped delivery.

- `docs/implementation-plans/backlog-arcs/bug-backlog-draining-arc.md` no longer presents quota recovery as a pending phase and has no gap in its remaining live phase labels.

- A scoped retired-vocabulary search across the three declared files returns no matches.

- The diff changes only `BACKLOG.md`, `BUG_BACKLOG.md`, and `docs/implementation-plans/backlog-arcs/bug-backlog-draining-arc.md`, and the full test command passes.

## Applicable guardrails

- **The plan’s “## Step intent”, queue transition:** retire only the resolved quota record and point the queue at existing live work; do not use this step to redesign remaining backlog priorities.

- **The plan’s “## Out of scope”, recovery behavior:** make no production-code, recovery-policy, provider, or external-backend-test change while closing the tracking records.

## Deferred

- Changes to the remaining BUG records — retain their current status and route any fix through their own scoped work.
