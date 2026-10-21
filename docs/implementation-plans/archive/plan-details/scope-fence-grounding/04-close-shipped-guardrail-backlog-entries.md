# Step 4 — Close the shipped guardrail backlog entries

## Summary

Remove the shipped `#161` and `#162` entries from `BACKLOG.md`. Update the quality roll-up, priority tier, and remaining `#163` wording so the backlog contains no pending-work description or dependency that points at removed entries. Keep `#163` as a separate future option, described against the shipped deterministic preservation behavior rather than as work waiting on `#161`. On green, `BACKLOG.md` presents only work that remains unshipped.

## Table of Contents

- [Summary](#summary) — What the backlog cleanup delivers.
- [Table of Contents](#table-of-contents) — Quick links to this detail.
- [Why](#why) — Why shipped entries and their references must leave the forward-looking backlog.
- [Input](#input) — The completed outcomes from steps 2 and 3 that justify retirement.
- [Files (creates vs edits)](#files-creates-vs-edits) — The single documentation file changed by this step.
- [Implementation](#implementation) — Required entry removal and reference repair.
- [Tests](#tests) — Non-code checks for the backlog edit.
- [Acceptance criteria](#acceptance-criteria) — Observable completed-backlog state.
- [Deferred](#deferred) — Guardrail work that remains intentionally tracked.

## Why

`BACKLOG.md` describes itself as a forward-looking list and directs authors to remove entries when their work ships. Its `#161` and `#162` entries, plus the `Current quality/accuracy-impacting items` and `Backlog tiers` indexes, still describe guardrail preservation and originating-contract grounding as pending. Leaving them there misstates available work and leaves `#163` pointing at a backlog prerequisite that no longer exists.

## Input

- **Step 2 outcome:** step 2 preserves the three recognized guardrail headings and excludes them from deferral buckets.
- **Step 3 outcome:** step 3 grounds completeness audits in recorded originating scope contracts.
- **Completion boundary:** confirm those outcomes in the working tree before retiring their tracker entries; this step records shipped status and does not re-check or change their implementation.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `BACKLOG.md` — remove shipped entries `#161` and `#162`, then repair their roll-up, tier, and remaining-entry references.

## Implementation

- **Foundational logic: retire shipped tracker entries without leaving dangling backlog references.**

- **Remove the completed entries.** Delete the full `BACKLOG.md:#161 — Preserve seed scope/audit guardrail sections through \`create\` instead of silently dropping them` and `BACKLOG.md:#162 — Render the seed / backlog scope contract into the plan-audit prompt` sections. Do not replace them with “shipped” summaries; the file’s `How to use it` guidance assigns historical implementation detail to the plan and git history.

- **Repair both indexes.** Update `BACKLOG.md:Current quality/accuracy-impacting items` and `BACKLOG.md:Backlog tiers` so neither presents `#161` or `#162` as available trust-core work. Remove the obsolete “ship them together” description rather than moving it into another backlog bucket.

- **Keep the fold-detector option coherent.** Retain `BACKLOG.md:#163 — Claude-judged fold detector for dropped guardrail sections` as pending work. Rewrite only the statements that name `#161` or `#162` as an unshipped dependency, priority comparison, or future sequence: describe the deterministic preservation check as an existing prerequisite and keep the entry’s bounded, advisory scope unchanged.

- **Preserve unrelated backlog content.** Do not renumber entries, rewrite neighboring items, or change the tracker’s heading and blank-line conventions. The removal must be limited to the two shipped entries and the references required to keep the remaining backlog accurate.

## Tests

- `BACKLOG.md shipped-entry search` — confirms no `#161` or `#162` tracker entry or pending-work reference remains.
- `BACKLOG.md #163 review` — confirms the fold-detector entry remains and describes its prerequisite without a dangling backlog dependency.

### Verification (non-code step)

- Read `BACKLOG.md:How to use it` and confirm the edit follows its rule that shipped features are removed.
- Review the diff to confirm only `#161`, `#162`, their index references, and the necessary `#163` dependency wording changed.
- Confirm `BACKLOG.md` retains its Markdown heading hierarchy and single blank-line entry spacing.

## Acceptance criteria

- `BACKLOG.md` contains no `#161` or `#162` backlog entry.
- The `Current quality/accuracy-impacting items` and `Backlog tiers` sections no longer list either shipped item as pending work.
- `BACKLOG.md:#163 — Claude-judged fold detector for dropped guardrail sections` remains present without a dependency on a removed backlog entry.
- No files other than `BACKLOG.md` are changed by this step.

## Deferred

- `BACKLOG.md:#163 — Claude-judged fold detector for dropped guardrail sections` — retain as a separate optional follow-up; this step only closes the deterministic preservation and prompt-grounding work that has shipped.
