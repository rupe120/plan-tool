> **Auto-archived**: this plan was swept on 2026-07-07 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 9 — Reconcile BACKLOG #63 After The Subsystem Ships

## Summary

This step removes the shipped `#63` data-contract backlog entry from `BACKLOG.md` and repairs every in-file reference that still describes it as future work. The only file in scope is `BACKLOG.md`. The key decision is to treat this as a full backlog reconciliation, not a block deletion: update the quality roll-up, priority tier, section summary, former-`#62` wording, and any dependency-style references that point at `#63`. On green, `BACKLOG.md` no longer tells readers that the data-contract subsystem or its per-plan `Input` contract work is still open.

## Table of Contents

- [Summary](#summary) — The shipped-work cleanup this step performs.
- [Why](#why) — Why backlog reconciliation matters after step 8 ships.
- [Files (creates vs edits)](#files-creates-vs-edits) — The single backlog file this step edits.
- [Implementation](#implementation) — The cleanup rule and the references to repair.
- [Tests](#tests) — The verification checks for this non-code step.
- [Acceptance criteria](#acceptance-criteria) — The observable state of `BACKLOG.md` when done.
- [References](#references) — Markdown reference material useful for this edit.
- [Deferred](#deferred) — Work intentionally left outside this backlog cleanup.

## Why

Steps 1-8 ship the data-contract subsystem that `BACKLOG.md:#63 — Data-contract subsystem (app-level definition + audit check + bespoke apply + create/detail integration + per-plan HEAD-verified ## Input section)` currently describes as future work. Leaving that entry or its inbound references in place makes the backlog lie about project state, especially because `BACKLOG.md:Quality/accuracy lens (cross-cutting)`, `BACKLOG.md:Priority (mission-grounded)`, and `BACKLOG.md:Backlog` all use `#63` to guide execution order.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `BACKLOG.md` — Remove the `#63` entry and repair every surrounding index, tier, roll-up, and cross-reference that frames the shipped data-contract subsystem or former `#62` `## Input` contract work as pending.

## Implementation

- **Foundational logic: shipped-backlog entry retirement.** Treat `#63` as completed by the data-contract subsystem plan after step 8. Remove its backlog entry rather than preserving a shipped-work summary in `BACKLOG.md`; this file is for forward-looking work, and the implementation plan plus git history own the record of what shipped.

- **Delete the entry block.** Remove `BACKLOG.md:#63 — Data-contract subsystem (app-level definition + audit check + bespoke apply + create/detail integration + per-plan HEAD-verified ## Input section)` in full, including the consolidation note for former `#62`, the touchpoint list, bootstrap note, effort, risks, dependencies, approach, quality marker, and origin.

- **Repair inbound references.** Grep the full file for `#63`, `#62`, `## Input`, `Input-contract`, and the exact `data-contract subsystem` wording. Update or remove each live reference that says the feature is still future work:
  - `BACKLOG.md:Quality/accuracy lens (cross-cutting)` — Remove `#63` from the `grounding` roll-up, keeping the remaining entries readable and correctly ordered.
  - `BACKLOG.md:Priority (mission-grounded)` — Remove `#63` from the `T3 — deterministic verifiability & grounding (P2), larger` tier and adjust the prose so the tier still reads naturally.
  - `BACKLOG.md:Backlog` under `### A. New capability, well-scoped` — Remove `#63` from the priority note about the plan-creation-quality, granularity, and grounding cluster.
  - Any remaining former-`#62` wording — Delete it if it only explains the now-shipped consolidation into `#63`.

- **Preserve unrelated references.** Do not remove legitimate mentions of `DATA_CONTRACT.md` or data-contract obligations in other live entries when those entries still describe future work of their own. For example, another backlog entry may still say it must update `DATA_CONTRACT.md` if it adds a new persisted schema; that is not an inbound reference to `#63`.

- **Do not create a shipped-work archive.** Do not add a new completed-items section to `BACKLOG.md`. The file already says shipped historical content belongs in git log, implementation plans under `docs/implementation-plans/`, and `LESSONS_LEARNED.md` only when there is a reusable design lesson.

## Tests

No repository test file changes are needed; this is a non-code backlog reconciliation.

### Verification (non-code step)

- `rg "#63|#62" BACKLOG.md` — Returns no lines that frame the data-contract subsystem or former `## Input` contract item as open backlog work.
- `rg "data-contract subsystem|Input-contract|## Input" BACKLOG.md` — Returns no stale future-work references to the shipped subsystem.
- `rg "DATA_CONTRACT.md|data-contract" BACKLOG.md` — Any remaining hits belong to other live backlog entries and do not depend on `#63`.
- Manual Markdown pass — `BACKLOG.md:Quality/accuracy lens (cross-cutting)`, `BACKLOG.md:Priority (mission-grounded)`, and `BACKLOG.md:Backlog` still read cleanly after list edits.

## Acceptance criteria

- `BACKLOG.md` no longer contains the `#63` backlog entry block.
- `BACKLOG.md` no longer contains former-`#62` consolidation text tied to `#63`.
- `BACKLOG.md:Quality/accuracy lens (cross-cutting)` does not list `#63`.
- `BACKLOG.md:Priority (mission-grounded)` does not list `#63` in `T3`.
- `BACKLOG.md:Backlog` does not describe `#63` as part of the remaining plan-creation-quality, granularity, and grounding cluster.
- Any remaining `DATA_CONTRACT.md` or `data-contract` mentions in `BACKLOG.md` refer to live, separate backlog work, not the shipped subsystem.

## References

- [CommonMark Specification](https://spec.commonmark.org/) — Use for keeping Markdown lists, headings, and block quotes valid while editing `BACKLOG.md`.

## Deferred

- New data-contract follow-up entries — Add only if a real unshipped scope remains after step 8; do not invent one as part of retiring `#63`.
- Lessons-learned updates — Leave reusable design lessons to `LESSONS_LEARNED.md` only if the implementer finds one worth preserving during the actual cleanup.
