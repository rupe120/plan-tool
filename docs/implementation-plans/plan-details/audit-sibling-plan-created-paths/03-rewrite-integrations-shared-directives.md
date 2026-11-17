# Step 3 — Rewrite DIRECTIVES.md § T and close the sibling-path BUG_BACKLOG entry

<!-- plan-tool:detail-format-version: 1 -->

## Summary

- Rewrite the **T — tool artifacts** bullet in `integrations/shared/DIRECTIVES.md` so it says the audit now receives same-roadmap sibling `creates:` paths. The sibling-path case is no longer a known false positive.
- The bullet keeps the stale roadmap or seed path case as a T false positive.
- Sweep both files for prose that still calls the sibling case unhandled.
- Remove the `BUG_BACKLOG.md` entry "The audit reports a path a sibling plan in the same roadmap creates as missing" last, only after steps 1 and 2 are green.
- On green, § T names one T false-positive class, the entry heading is gone, and the unbuilt-sibling entry is untouched.

## Table of Contents

- [Why](#why) — what the directive says today and why it goes stale
- [Files (creates vs edits)](#files-creates-vs-edits) — the two edited files
- [Implementation](#implementation) — § T rewrite, vocabulary sweep, ordered entry removal
- [Tests](#tests) — non-code verification checks
- [Acceptance criteria](#acceptance-criteria) — observable checks
- [Applicable guardrails](#applicable-guardrails) — plan fences that bind this step
- [Deferred](#deferred) — what this step leaves out

## Why

- The **T — tool artifacts** bullet in `integrations/shared/DIRECTIVES.md` tells triagers that a finding citing a path another plan in the same roadmap creates is a known false positive to verify once and ignore.
- Steps 1 and 2 give the audit those paths, so the instruction tells triagers to ignore something the audit no longer produces. Stale rationale argues for the wrong action.
- The `BUG_BACKLOG.md` entry describing the symptom becomes false on shipment and must be removed so the backlog does not carry a fixed defect.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `integrations/shared/DIRECTIVES.md`: rewrite the T bullet under the bare-finding triage list. Edit only that bullet and any sweep hit.
  - `BUG_BACKLOG.md`: delete the one entry headed "The audit reports a path a sibling plan in the same roadmap creates as missing", from its `###` heading to the line before the next `###` heading.

## Implementation

- **Rewrite the T bullet, keep its place and bold lead-in.** Recommended content:
  - T is the stale roadmap or seed path case: a finding that cites such a path is a known false positive. Verify it once, file or cite the bug entry, and leave the plan alone.
  - The sibling case moves to one clause: the audit receives the `creates:` paths of other plans in the same roadmap, so a finding that reports one as missing is a real signal to check, not a T finding. Write it in present tense with no "previously" or "used to".
  - State the limit: the audit receives sibling paths only for same-roadmap plans. Paths created by plans outside the roadmap are not covered. The unbuilt-sibling case is a separate bug entry. Both statements prevent a reader from reading the clause as broader than it is.
- **Keep the edit small.** This file ships to every consuming repo through `install-skill`. Do not change the R/B/P/D/I labels, the label list sentence above the bullets, or any other bullet.
- **Sweep by vocabulary before editing, and write down the result.** Run `rg -n -i "another plan in the same roadmap|sibling|footprint"` over `integrations/shared/DIRECTIVES.md` and `BUG_BACKLOG.md`.
  - At HEAD, `DIRECTIVES.md` hits only the T bullet. The other matches are unrelated: the "literal sibling" file note, "sibling step's established pattern", "siblings" in the class-sweep rule, and "sibling" in the review-loop rules.
  - `BUG_BACKLOG.md` hits two sibling-plan entries. One is the entry to remove. The other is the unbuilt-sibling entry (`create` writes a single "record unbuilt upstreams and stop" step), which stays.
  - Check any other `BUG_BACKLOG.md` entry that cross-references the removed heading, and update or drop that pointer. At HEAD, expect none outside the removed entry itself.
  - Also run `rg -n "creates as missing|sibling plan in the same roadmap"` over the repo outside `docs/implementation-plans/` and report each remaining hit. The superseded seed under `plan-seeds/archive/` is history and stays.
- **Order the destructive edit last.** Confirm steps 1 and 2 are green and committed (their tests pass), then delete the BUG entry.
  - Remove the whole entry including its Origin line. It has no Jira ticket, so there is no promotion stub to leave.
  - Do not touch the neighboring unbuilt-sibling entry above it.
- **Entry removal only after full shipment** is the rule here: if step 1 or 2 is not green, leave the entry and mark nothing else.

## Tests

### Verification (non-code step)

The test-authoring gate does not apply: it fires only for `feature` and `refactor` steps, and this step is `non-code`. Use these checks instead.

1. `rg -n -i "another plan in the same roadmap" integrations/shared/DIRECTIVES.md` shows § T states the sibling-path case as handled by the audit. It must not list it as a known false positive.
2. `rg -n "stale roadmap or seed path" integrations/shared/DIRECTIVES.md` still finds the T false-positive class.
3. `rg -n "^### The audit reports a path a sibling plan in the same roadmap creates as missing" BUG_BACKLOG.md` returns nothing.
4. `rg -n "^### .create. writes a single .record unbuilt upstreams and stop." BUG_BACKLOG.md` still finds the unbuilt-sibling entry.
5. `rg -n "creates as missing|sibling plan in the same roadmap" BUG_BACKLOG.md integrations/shared/DIRECTIVES.md` shows no prose that calls the sibling case unhandled.
6. `git diff --stat` touches only the two files named above.
7. `uv run pytest tests/ -q -n auto` is green. This includes any test that reads `integrations/shared/DIRECTIVES.md` (for example install-skill content checks).

## Acceptance criteria

- § "T — tool artifacts" names the stale roadmap or seed path as the T false-positive class.
- § T describes a finding that reports a same-roadmap sibling `creates:` path as missing as something to verify, because the audit now receives those paths.
- § T states the same-roadmap limit and does not claim coverage for plans outside the roadmap.
- The `BUG_BACKLOG.md` entry "The audit reports a path a sibling plan in the same roadmap creates as missing" is gone, with no promotion stub.
- The unbuilt-sibling entry is still present and unedited.
- No other edit lands in `integrations/shared/DIRECTIVES.md`.
- `uv run pytest tests/ -q -n auto` passes.

## Applicable guardrails

- **The plan's "## Scope guardrails"** (no filtering of model findings, no new sibling selection rule, no change to the deterministic check): this step edits prose only and touches no `plan_tool/` file.
- **The plan's "## Audit guardrails"** (other T classes and plans outside the roadmap are out of scope): the T rewrite keeps the stale roadmap or seed path class as a false positive and claims nothing for outside-roadmap plans.
- **The plan's "## Out of scope"** (the unbuilt-sibling bug entry, other T classes): leave that entry and any other T-class prose as they are.

## Deferred

- How a plan may depend on an unbuilt sibling plan — the separate `BUG_BACKLOG.md` unbuilt-sibling entry stays open and is not edited here.
- Paths created by plans outside the audited plan's roadmap — not covered by this fix; no new backlog entry is needed beyond the existing deterministic-check behavior.
- Any wording change to the stale roadmap or seed path T class — it stays a known false positive as written.
