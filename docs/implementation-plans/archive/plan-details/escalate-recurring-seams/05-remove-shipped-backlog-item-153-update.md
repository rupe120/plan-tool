# Step 5 — Remove shipped backlog item #153 and update related convergence notes

## Summary

Remove the shipped `#153` entry from `BACKLOG.md` and update every remaining convergence note that treats it as pending work. Keep open items `#152`, `#154`, and `#156` accurate by describing the structural escalation as shipped without creating a replacement backlog number. This step edits only `BACKLOG.md`; on green, no `#153` reference remains and the quality roll-up lists only open work.

## Table of Contents

- [Summary](#summary) — The documentation cleanup and finished state.
- [Table of Contents](#table-of-contents) — Links to each section.
- [Why](#why) — Why stale backlog status and references must be removed.
- [Input](#input) — The shipped-step outcome and backlog entries this update reads.
- [Files (creates vs edits)](#files-creates-vs-edits) — The single documentation file changed.
- [Implementation](#implementation) — Remove the entry and reconcile inbound references.
- [Tests](#tests) — Non-code verification for the documentation change.
- [Acceptance criteria](#acceptance-criteria) — Checkable finished backlog state.

## Why

`BACKLOG.md` is the forward-looking work list, but its `#153` entry and related convergence notes still describe the recurring high-impact structural stop as future work after steps 3 and 4 have landed it. Leaving that entry and its inbound references in place makes the backlog recommend duplicate work and obscures the remaining `#152` demotion and `#154` calibration work.

## Input

- **Shipped behavior:** Steps 3 and 4 provide the completed live-loop structural stop and recommend-only presentation that fulfill `BACKLOG.md`’s `#153` outcome.
- **Backlog relationships:** Read the `#153` entry and every `#153` reference in `BACKLOG.md`, especially the `Current quality/accuracy-impacting items` roll-up and entries `#152`, `#154`, and `#156`.
- **Open-work boundary:** Preserve `#152`, `#154`, and `#156` as open entries. Their remaining work must not be removed or marked shipped by this cleanup.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `BACKLOG.md` — remove the shipped `#153` entry, delete it from the convergence roll-up, and reword surviving references to describe the landed structural escalation without a dead issue number.

## Implementation

- **Foundational logic — shipped-item removal plus inbound-reference reconciliation.** Treat `BACKLOG.md`’s `#153` entry as fully shipped because steps 3 and 4 completed its live completeness and reconcile loop outcomes.

- **Remove only the shipped entry.** Delete the complete `**#153 — Route a recurring high-impact seam…**` block, including its status, scope contract, and iterate recipe. Preserve the surrounding `#152` and `#154` entries and their spacing.

- **Update the quality roll-up.** In `BACKLOG.md`’s `Current quality/accuracy-impacting items` under the `convergence` facet, remove the `#153` item while retaining the other open entries and their descriptions.

- **Reword surviving dependencies by feature, not number.** Update the `#152`, `#154`, and `#156` notes that name `#153` so they refer to the shipped recurring structural escalation where that context still matters. Do not imply that `#154` depends on it, and do not alter `#152`’s pending impact-only demotion or `#154`’s calibration scope.

- **Sweep all remaining references.** Check every `#153` occurrence in `BACKLOG.md`, including range-style references such as `#152–#154`; replace or rephrase any wording that presents the removed item as open. Do not add a replacement issue number or historical shipped-entry block.

## Tests

No automated test file applies; `BACKLOG.md` is a documentation-only backlog artifact.

### Verification (non-code step)

- **Backlog-reference sweep** — Search `BACKLOG.md` for `#153` and confirm it returns no matches.
- **Open-entry review** — Confirm `#152`, `#154`, and `#156` remain present and accurately describe only their unshipped work.
- **Roll-up review** — Confirm the `Current quality/accuracy-impacting items` convergence list contains no removed item and remains readable after the deletion.
- **Formatting review** — Confirm the entry boundary between `#152` and `#154` retains the existing heading and blank-line convention.

## Acceptance criteria

- `BACKLOG.md` contains no `#153` reference or `#153` entry.
- The `Current quality/accuracy-impacting items` convergence roll-up no longer lists `#153`.
- `BACKLOG.md` entries `#152`, `#154`, and `#156` remain open and do not describe the shipped structural escalation as pending.
- No new backlog entry, production-code change, or automated test is added.
