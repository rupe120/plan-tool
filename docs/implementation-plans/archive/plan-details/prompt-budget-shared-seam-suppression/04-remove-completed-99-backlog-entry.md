> **Auto-archived**: this plan was swept on 2026-07-08 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 4 — Remove the completed #99 backlog entry and references

## Summary

Remove `BACKLOG.md` entry `#99` now that the shared-seam prompt-budget suppression work is complete. Keep the edit limited to `BACKLOG.md`: delete the `#99` backlog block and repair every live inbound reference that still frames it as pending work. The key design choice is delete-plus-repair, not only deleting the entry body, because `BACKLOG.md` has roll-up and priority references that can outlive the block. Green means `BACKLOG.md` no longer lists or points readers to `#99` as unstarted, while nearby shipped `#95` and live `#97` context remains accurate.

## Table of Contents

- [Summary](#summary) — The short version of the backlog cleanup and expected result.
- [Why](#why) — Why deleting the shipped item must include inbound reference repair.
- [Input](#input) — Existing backlog structure this step reads and must preserve.
- [Files creates vs edits](#files-creates-vs-edits) — The exact file footprint for this non-code step.
- [Implementation](#implementation) — The intended cleanup boundaries and references to sweep.
- [Tests](#tests) — The test impact for this documentation-only change.
- [Verification (non-code step)](#verification-non-code-step) — Manual and grep checks for the backlog artifact.
- [Acceptance criteria](#acceptance-criteria) — Observable checks for reviewers and CI.
- [Deferred](#deferred) — Work that stays outside this shipped-entry cleanup.

## Why

`BACKLOG.md` is the forward-looking list, so a completed entry should not remain as a candidate feature or as a priority target. Entry `#99` also appears outside its own block in the quality roll-up and priority prose, so removing only the block would leave readers with stale signals that the prompt-budget shared-seam suppression still needs planning or execution. This step keeps the backlog truthful after step 3 proves the suppression behavior with regression coverage.

## Input

- **Step 3 outcome:** step 3 adds regression coverage showing named create, detail, and review prompt-budget sends no longer double-record `phase="shell-backstop"` telemetry. Treat that as the completion signal for retiring `#99`.
- **Backlog policy:** `BACKLOG.md:How to use it` says shipped feature entries should be removed rather than kept as history.
- **Quality roll-up:** `BACKLOG.md:Quality/accuracy lens (cross-cutting)` includes `#99` under `heuristic-tuning`; remove that pending-work reference while preserving the live `#72` signal.
- **Priority index:** `BACKLOG.md:Priority (mission-grounded)` mentions `#99` in the T3 grounding tier and in the `Remaining prompt-context quality` note above the backlog. Repair both so they no longer point at completed suppression work.
- **Entry body:** `BACKLOG.md:#99 — Double-warn / double-telemetry suppression for the prompt-budget advisory shared seam` is the block to delete.
- **Limit:** do not remove unrelated `#95` historical context or live `#97` prompt-context quality work unless the sentence only exists to describe `#99` as pending.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `BACKLOG.md` — Delete the `#99` entry block and repair every inbound `#99` reference in the quality roll-up, priority tier prose, and backlog-section summary note.

## Implementation

- **Foundational logic:** shipped backlog item retirement with inbound-reference repair.
- **Delete the entry block.** Remove the whole `BACKLOG.md:#99 — Double-warn / double-telemetry suppression for the prompt-budget advisory shared seam` section, stopping before the next backlog entry heading.
- **Repair the quality roll-up.** In `BACKLOG.md:Quality/accuracy lens (cross-cutting)`, remove the `#99` clause from the `heuristic-tuning` bullet. Keep `#72` if it remains the only live item for that facet; do not delete the facet unless the surrounding wording would become awkward or empty.
- **Repair the priority prose.** In `BACKLOG.md:Priority (mission-grounded)`, remove the statement that `#95` left only shared-seam suppression as `#99`. Keep the `#97` prompt-context quality tiering intact.
- **Repair the backlog-section note.** In `BACKLOG.md:Backlog`, update the `Remaining prompt-context quality` note so it no longer says the remaining quality work is `#97 plus #99`. The forward-looking remainder should be `#97` only unless HEAD has another live entry that belongs in that sentence.
- **Sweep exact id references.** Run a whole-file search for `#99` after editing `BACKLOG.md`. Any remaining match must be either removed or rewritten so it does not describe `#99` as open, pending, tiered, or a dependency.
- **Preserve related live context.** Leave `#95` references that describe the shipped prompt-budget advisory or historical origin in place when they still make sense without `#99`. Leave `#97` wording about symbol-aware excerpts and optional run-detail embed follow-up in place; that is separate live work.

## Tests

No unit tests are expected for this non-code step. Do not add test files for a pure `BACKLOG.md` cleanup.

### Verification (non-code step)

- `rg "#99" BACKLOG.md` — returns no matches, or only a deliberately retained historical mention that does not frame the item as pending.
- `rg "shared-seam double|suppression remainder|Double-warn|double-telemetry" BACKLOG.md` — returns no stale pending-work wording for the completed `#99` item.
- Read `BACKLOG.md:Quality/accuracy lens (cross-cutting)` — the `heuristic-tuning` bullet remains grammatical and does not double-count completed suppression work.
- Read `BACKLOG.md:Priority (mission-grounded)` — T3 and the backlog-section prompt-context note still point to live work only.

## Acceptance criteria

- `BACKLOG.md` no longer contains the `#99 — Double-warn / double-telemetry suppression for the prompt-budget advisory shared seam` entry.
- `BACKLOG.md` no longer lists `#99` in the quality roll-up, priority tiers, or backlog-section summary note.
- `BACKLOG.md` keeps live `#97` prompt-context quality work and shipped `#95` context accurate.
- No files other than `BACKLOG.md` are edited.

## Deferred

- Code or test changes — step 3 owns the regression coverage, and this step only retires the completed backlog entry.
- Telemetry schema or `DATA_CONTRACT.md` updates — suppression shipped without this cleanup changing persisted data contracts.
- Removing unrelated `#95` or `#97` references — those entries describe separate shipped context or live backlog work, not the completed `#99` item.
