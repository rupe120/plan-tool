> **Auto-archived**: this plan was swept on 2026-07-08 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 6 — Remove the Resolved Rate-Limit Switch Risk

## Summary

This step removes the stale backlog risk after steps 1-5 have scoped, tested, and documented rate-limit backend switching. The primary edits are `BUG_BACKLOG.md` and `BACKLOG.md`. The most important design decision is to delete the resolved risk entry and repair only forward-looking references that still frame the issue as pending, while leaving accurate historical context alone. On green, the bug backlog no longer tells readers that auto-`SWITCH` still flips the process-wide backend for parallel workers, and the plan gate's negative grep passes.

## Table of Contents

- [Summary](#summary) — The short version of the cleanup and expected result.
- [Why](#why) — Why the backlog entry is now stale.
- [Input](#input) — The upstream completion signals this cleanup depends on.
- [Files (creates vs edits)](#files-creates-vs-edits) — The backlog files this step edits.
- [Implementation](#implementation) — The cleanup rule, target anchors, and reference sweep.
- [Tests](#tests) — The deterministic check that covers this non-code cleanup.
- [Verification (non-code step)](#verification-non-code-step) — Manual checks for backlog accuracy.
- [Acceptance criteria](#acceptance-criteria) — Observable conditions for completion.
- [Deferred](#deferred) — Related backlog items intentionally left alone.

## Why

`BUG_BACKLOG.md:Auto-\`SWITCH\` flips the process-wide backend for all parallel workers` describes the exact risk this plan resolves: rate-limit fallback switching could affect sibling workers in one process. Once steps 1-4 make the backend switch scoped and covered, and step 5 documents the scoped behavior, keeping that RISK entry in the active bug backlog gives future readers the wrong status. The cleanup matters because `BUG_BACKLOG.md` is for current outstanding bugs, while shipped or historical context belongs in git history or in live backlog entries only when it still affects pending work.

## Input

- **Step 5 dependency outcome:** scoped `--on-rate-limit switch` behavior must be documented in the operator and maintainer docs before this cleanup runs.
- **Bug-backlog contract:** `BUG_BACKLOG.md:When an item is fixed, remove it` says fixed issues should be deleted from the active bug backlog rather than marked complete in place.
- **Risk entry to retire:** `BUG_BACKLOG.md:Auto-\`SWITCH\` flips the process-wide backend for all parallel workers` is the active item being removed.
- **Backlog cross-link rule:** `BACKLOG.md` is cross-linked, so this step must search for stale references to the retired risk outside the entry block before declaring the cleanup done.
- **Plan gate:** `docs/implementation-plans/2-parallel-rate-limit-switch-scope.md:Remove the resolved rate-limit switch risk` checks for the stale phrases `process-wide backend for all parallel workers`, `cross-worker backend leakage`, and `Auto-\`SWITCH\` flips` across `BUG_BACKLOG.md` and `BACKLOG.md`.

## Files (creates vs edits)

- **New files:** none.

- **Existing files (edits only):**
  - `BUG_BACKLOG.md` — Delete the resolved `Auto-\`SWITCH\` flips the process-wide backend for all parallel workers` RISK entry. If the RISK section becomes empty, follow the existing empty-section style used by `BUG_BACKLOG.md:## BUG`.
  - `BACKLOG.md` — Sweep for forward-looking references that still describe the rate-limit switch risk as unresolved, pending, or blocking. Remove or reword only those stale references.

## Implementation

- **Foundational logic:** resolved-risk backlog cleanup.

- **Delete the active bug entry.** Remove the whole `BUG_BACKLOG.md:Auto-\`SWITCH\` flips the process-wide backend for all parallel workers` block, including its Files, Symptom, Fix, Approach, and Origin bullets. Do not leave a "fixed" note in `BUG_BACKLOG.md`; the file's own rule says fixed items are removed.

- **Preserve section shape.** If deleting the block leaves `BUG_BACKLOG.md:## RISK` with no entries, add the same `_(none outstanding)_` marker used under `BUG_BACKLOG.md:## BUG`. Keep `BUG_BACKLOG.md:## MINOR` and the argparse golden entry unchanged.

- **Sweep inbound references.** Search both declared files for the retired risk's unique phrases, not only the title:
  - `Auto-\`SWITCH\` flips`
  - `process-wide backend for all parallel workers`
  - `cross-worker backend leakage`
  - `whole-process switch`
  - `completeness-apply --jobs N` near rate-limit backend switching language

- **Edit `BACKLOG.md` only when it still frames the risk as live.** If a `BACKLOG.md` reference says the scoped switch work is still pending, still blocking another item, or still a current bug, remove or update that wording. If a reference accurately points to shipped history or to a separate live item, keep it.

- **Keep `BACKLOG.md:#98 — Rate-limit handling under parallel workers: non-interactive policy + de-dup the invoker helpers` in scope only for stale cross-references.** That entry still tracks different follow-up work: repeated prompts under `--jobs N` and duplicated helper logic. Do not delete or rewrite it as part of this step unless it directly names the retired process-wide switch risk as unresolved.

- **Do not edit code or tests.** The backend behavior belongs to steps 1-4, and documentation belongs to step 5. If the sweep shows the scoped behavior is not actually implemented or documented, stop and send the finding back to the owning step rather than fixing code or docs here.

## Tests

- Run the inline step 6 gate from `docs/implementation-plans/2-parallel-rate-limit-switch-scope.md:Remove the resolved rate-limit switch risk` and assert none of the stale phrases remain in `BUG_BACKLOG.md` or `BACKLOG.md`.

### Verification (non-code step)

- Read `BUG_BACKLOG.md:## RISK` and confirm the retired auto-`SWITCH` risk entry is gone.
- Read `BUG_BACKLOG.md:## BUG`, `BUG_BACKLOG.md:## RISK`, and `BUG_BACKLOG.md:## MINOR` and confirm the section markers still make sense after deletion.
- Run `rg "Auto-\`SWITCH\` flips|process-wide backend for all parallel workers|cross-worker backend leakage" BUG_BACKLOG.md BACKLOG.md` and confirm it returns no stale live-risk references.
- Run `rg "whole-process switch|completeness-apply --jobs N|rate-limit" BACKLOG.md BUG_BACKLOG.md` and manually check any remaining hits describe current work or accurate history, not the retired switch leak.
- Confirm `BACKLOG.md:#98 — Rate-limit handling under parallel workers: non-interactive policy + de-dup the invoker helpers` still tracks only its separate prompt-policy and helper-dedup follow-ups.

## Acceptance criteria

- `BUG_BACKLOG.md` no longer contains `BUG_BACKLOG.md:Auto-\`SWITCH\` flips the process-wide backend for all parallel workers`.
- `BUG_BACKLOG.md:## RISK` remains valid markdown and uses `_(none outstanding)_` if no RISK entries remain.
- `BACKLOG.md` has no forward-looking reference that says cross-worker backend leakage from rate-limit `SWITCH` is still unresolved.
- The step 6 gate in `docs/implementation-plans/2-parallel-rate-limit-switch-scope.md:Remove the resolved rate-limit switch risk` passes.
- `BACKLOG.md:#98 — Rate-limit handling under parallel workers: non-interactive policy + de-dup the invoker helpers` remains present unless a separate plan explicitly retires it.

## Deferred

- `BACKLOG.md:#98 — Rate-limit handling under parallel workers: non-interactive policy + de-dup the invoker helpers` — Leave it live because it tracks repeated prompting and helper duplication, not the scoped backend leak resolved by this plan.
- Code or test fixes for scoped backend behavior — Owned by steps 1-4; this step only reconciles backlog state after those changes are complete.
- Operator and maintainer wording about scoped switch behavior — Owned by step 5; this step only removes stale backlog risk language.
