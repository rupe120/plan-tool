> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 4 — Mark BACKLOG #244 resolved only after the description, research, and refusal changes ship

## Summary

Retire the active BACKLOG #244 work item after steps 1–3 have shipped and their regression coverage is green. Edit only `BACKLOG.md`, removing #244 from both the next-pick board and its full catalog card. The key decision is that backlog closure records completed delivery, not a planned or partially tested design. On green, `BACKLOG.md` no longer recommends or lists #244 as open work.

## Table of Contents

- [Summary](#summary) — The completed backlog-cleanup result.
- [Table of Contents](#table-of-contents) — Quick links to this detail.
- [Why](#why) — Why accurate backlog status depends on shipped behavior.
- [Input](#input) — Upstream delivery evidence required before closure.
- [Files (creates vs edits)](#files-creates-vs-edits) — The sole documentation edit.
- [Implementation](#implementation) — Closure rule and both #244 references to retire.
- [Tests](#tests) — Upstream regression evidence and non-code verification.
- [Acceptance criteria](#acceptance-criteria) — Observable closure conditions.
- [Applicable guardrails](#applicable-guardrails) — Scope boundaries for this final step.
- [Deferred](#deferred) — Work this close-out does not expand.

## Why

`BACKLOG.md` still presents #244 as ready work in `### Now / Next / Blocked / Parked (working set)` and as an open catalog card under `**#244 — Research whatever technology a plan actually chose, and refuse to guess when research comes back empty**`. Leaving either reference after delivery sends the next session toward finished work; removing it before the description, research, and refusal contracts are proven would hide an unfinished feature.

## Input

- **Step 1 outcome:** Consume the shipped operator-description contract and its preservation coverage. Do not close #244 while that outcome is incomplete.

- **Step 2 outcome:** Consume the shipped roadmap-selected research behavior and per-product evidence coverage. Do not treat an authored detail or a proposed approach as delivery evidence.

- **Step 3 outcome:** Consume the shipped pre-publication refusal and its recovery coverage. The refusal’s test results are required before this documentation-only close-out.

- **Backlog convention:** `BACKLOG.md:## Purpose` defines the backlog as forward-looking and directs shipped feature entries out of the active catalog. `BACKLOG.md:### Now / Next / Blocked / Parked (working set)` is the separate active-selection surface that must agree with the catalog.

## Files (creates vs edits)

- **New files:** None.

- **Existing files (edits only):**
  - `BACKLOG.md` — Remove the active #244 next-pick row and the full #244 catalog card after the dependent implementation and tests ship.

## Implementation

- **Foundational logic — retire a delivered backlog item only after its complete feature contract is proven.** Treat steps 1, 2, and 3 as a single delivery gate for #244. If any required behavior or its regression coverage remains incomplete, leave both `BACKLOG.md` #244 references unchanged.

- **Remove both active references together.** Delete the #244 row from `BACKLOG.md:### Now / Next / Blocked / Parked (working set)` and remove the matching `**#244 — Research whatever technology a plan actually chose, and refuse to guess when research comes back empty**` card from the full catalog. The board and catalog must not disagree about whether this work remains selectable.

- **Use removal as the close-out form.** Follow `BACKLOG.md:## Purpose` rather than adding a new in-place “resolved” status, delivery summary, or partial-completion note. The implementation plan and git history retain delivery evidence; this forward-looking backlog must not retain #244 as an open or selectable item.

- **Keep the edit narrow.** Do not revise the technology-research behavior, rewrite the completed rationale, or change unrelated backlog ordering while retiring #244. A new concern discovered during verification belongs in a separate backlog item.

## Tests

Step 4 adds no test files; the upstream tests are the evidence required before the backlog edit.

- `tests/test_roadmap_artifacts.py` and `tests/test_roadmap_revision.py` — Step 1’s landed description-preservation coverage remains green.

- `tests/test_create.py:TestProposeReferencesFromClaude`, `tests/test_create.py:TestCreatePlanResume`, and `tests/test_create.py:TestCreatePlanIterationLoop` — Step 2 and step 3 coverage proves selected research, refusal recovery, and iteration behavior before close-out.

### Verification (non-code step)

The test-authoring gate does not apply because step 4 has `change_type: non-code`.

1. Run the plan’s test command after steps 1–3 land and confirm it passes before editing `BACKLOG.md`.

2. Confirm the delivered step 1–3 changes and their tests are committed; do not infer completion from the presence of their detail files.

3. Search `BACKLOG.md` for `#244` and the #244 title after the edit. Both searches must return no active or catalog reference.

4. Review `BACKLOG.md:### Now / Next / Blocked / Parked (working set)` and confirm no remaining row recommends #244.

5. Run `git diff --check` and confirm this step changes only `BACKLOG.md`.

## Acceptance criteria

- Steps 1, 2, and 3 have shipped their description, research, and refusal outcomes, and the plan’s test command passes before #244 is retired.

- `BACKLOG.md` contains no #244 ready-to-author row or other active-selection guidance.

- `BACKLOG.md` contains no full #244 feature card or unresolved-status text.

- The step changes no production code or test file.

- A new follow-up concern is recorded separately rather than extending #244 during close-out.

## Applicable guardrails

- **The plan’s “## Plan intent”, grounded technology research:** Close #244 only when the delivered feature satisfies the plan’s stated grounding and refusal intent; this step does not redefine that behavior.

- **The plan’s step 4 intent, accurate close-out:** Keep the backlog accurate without claiming completion before the dependent work and its tests are complete.

- **The plan’s “## Out of scope”, non-expansion boundary:** Do not use this backlog edit to alter the hosting/store contract, expand research to other surfaces, or add unrelated research policy.

## Deferred

- Additional research behavior or test fixes — complete them in steps 1–3 or track them as new work before retiring #244.

- Research quality, freshness, and scope expansion — remain outside this backlog close-out and require separate planning.
