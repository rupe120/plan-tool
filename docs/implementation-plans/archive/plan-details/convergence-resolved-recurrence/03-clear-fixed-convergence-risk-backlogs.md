> **Auto-archived**: this plan was swept on 2026-08-05 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 3 — Clear the fixed convergence risk from the backlogs

## Summary

Remove the completed convergence RISK from `BUG_BACKLOG.md` and reconcile the remaining related work in `BACKLOG.md`. Keep `BACKLOG.md` #116 open only for its unfinished localized-split work, while removing the completed newest-run and structural-evidence accuracy work from its roadmap and roll-ups. The key decision is to delete completed tracking rather than add a shipped-history note, while retaining entries that still describe distinct future work. On green, neither backlog presents the resolved finding as a reason for a destructive re-decompose recommendation.

## Table of Contents

- [Summary](#summary) — Reviewer overview of the backlog cleanup and result.
- [Table of Contents](#table-of-contents) — Links to each section in this detail.
- [Why](#why) — Why the tracking records are stale after the dependency steps land.
- [Input](#input) — Dependency outcomes and backlog records this step verifies.
- [Files (creates vs edits)](#files-creates-vs-edits) — The two markdown files this step changes.
- [Implementation](#implementation) — The retirement and cross-reference reconciliation rules.
- [Tests](#tests) — Dependency regressions and non-code verification.
- [Acceptance criteria](#acceptance-criteria) — Observable backlog-state outcomes.
- [Applicable guardrails](#applicable-guardrails) — Plan boundaries for this documentation-only step.
- [Deferred](#deferred) — Remaining convergence roadmap work.

## Why

`BUG_BACKLOG.md` currently lists a RISK that steps 1 and 2 close, while `BACKLOG.md` still presents the same newest-run failure as open #116 work and as a dependency for related audit-trajectory proposals. Leaving those statements in place would send future planning toward a defect that no longer exists and blur the remaining localized-fork and telemetry work. This step makes the two backlogs describe only work that remains open.

## Input

- **Step 1 outcome:** Confirm the landed newest-series behavior: a region absent from its latest series run cannot drive recurrence.

- **Step 2 outcome:** Confirm `plan_tool/convergence_diagnosis.py:recurring_regions` now limits recurrence evidence to the existing `plan_tool/review.py:STRUCTURAL_SOURCES` boundary.

- **Legacy outcome:** Confirm persisted `detail-purity` history remains structural recurrence evidence through the read-time compatibility bridge, without a sidecar rewrite or taxonomy change.

- **Tracking policy:** Follow `BUG_BACKLOG.md`’s opening rule that completed bugs are removed, and `BACKLOG.md`’s `## Purpose` and `## Direct implementation vs. plan-tool plan` guidance that shipped work is not kept as open backlog scope.

- **Affected records:** Reconcile the RISK heading in `BUG_BACKLOG.md`; the `### Quality/accuracy lens` roll-up; `BACKLOG.md` #172, #116, #129, #148, and #160; and every remaining `#116` reference that could still imply the completed recurrence rule is pending.

## Files (creates vs edits)

- **New files:** None.

- **Existing files (edits only):**
  - `BUG_BACKLOG.md` — Remove the completed `convergence` RISK entry as one complete record.
  - `BACKLOG.md` — Remove the completed #116 recurrence-accuracy slice and correct the roll-up, dependencies, scope statements, and related-entry references that describe it as open work.

## Implementation

- **Foundational logic:** Retire only the backlog claims disproved by steps 1 and 2, while preserving distinct convergence work that is still open.

- **Verify before changing tracking.** Read the landed code and dependency-step regressions, not their detail proposals, before declaring the RISK closed. If either the newest-run rule or structural-only recurrence boundary is missing, route the gap to its owning step instead of editing either backlog.

- **Remove the completed RISK as a whole.** Delete its complete entry from `BUG_BACKLOG.md`, including symptom, fix, approach, and origin. Do not replace it with a shipped note; the file’s own policy makes removal the completion record.

- **Keep #116, but narrow it to its remaining proposal.** In `BACKLOG.md`’s `**#116 — Turn a localized "spinning" verdict …**` block, remove the completed accuracy sub-change. Update its `Effort`, `Risks`, `Approach`, `Quality`, and `Origin` text so each describes only the still-open localized classification, split-title, and operator-offer work. Do not reuse the former designation for a different proposal; eliminate references that present its completed behavior as open work.

- **Correct every roadmap statement that depends on the closed slice.** Update the `### Quality/accuracy lens` convergence roll-up so #116 names only localized work. In #172, remove the completed rule from `Dependencies` and `Scope contract` while retaining its hand-resolution telemetry and identity-aware trend work. Remove #129’s confirmation bullet that exists only to justify the completed slice, and remove #148’s relation to the closed RISK.

- **Preserve valid #116 ownership.** Sweep `BACKLOG.md` for `#116` after editing. Keep references in entries such as #153, #158, #159, and #160 where they still mean open fork-classifier work; update #160’s `Stop / defer` wording where it assigns finding-matching accuracy to the completed #116 slice.

- **Keep the backlogs forward-looking.** Do not add implementation history, new roadmap items, code changes, or category definitions. The only remaining references to the resolved behavior should be in the plan and repository history, not in open-work tracking.

## Tests

No test file is created or edited in this documentation-only step. Use the dependency-step regressions as the proof required before removing their tracking records.

### Verification (non-code step)

1. `tests/test_convergence_diagnosis.py:test_recurs_in_window_requires_latest_run_presence` — Passes, proving an older-only recurrence does not remain spinning.

2. `tests/test_convergence_diagnosis.py:test_nonstructural_recurrence_converges_without_redecompose_advice` — Passes, proving nonstructural recurrence cannot produce destructive advice.

3. `tests/test_convergence_diagnosis.py:test_legacy_detail_purity_recurrence_remains_structural` — Passes, proving a persisted structural source alias remains eligible after the source fold.

4. `tests/cli/test_convergence_cmd.py:test_missing_latest_finding_converges_without_redecompose_command` and `test_structural_spinning_emits_reseed` — Pass, proving persisted structural sidecars both clear correctly when absent and retain a positive re-seed path when unresolved.

5. `BUG_BACKLOG.md` — Review the `## RISK` section to confirm it remains valid markdown and contains no completed convergence RISK.

6. `BACKLOG.md` — Search for the removed accuracy-slice vocabulary and the completed RISK’s wording; each must have no remaining match.

7. `BACKLOG.md` — Review every remaining `#116` match and confirm it refers only to unfinished fork-classifier work.

## Acceptance criteria

- `BUG_BACKLOG.md` no longer contains the resolved `convergence` re-decomposition RISK entry.

- `BACKLOG.md` #116 no longer lists newest-run absence or resolved-finding decay as pending work.

- The `### Quality/accuracy lens` roll-up describes #116 only as unfinished localized-split work.

- `BACKLOG.md` #172 no longer depends on or scopes the completed newest-run recurrence rule, while retaining its telemetry and identity-trend roadmap.

- `BACKLOG.md` #129, #148, and #160 contain no stale reference that presents the removed RISK or completed accuracy slice as open work.

- Remaining `BACKLOG.md` references to #116 still point to work that remains open.

- The three dependency regressions named in `## Tests` pass before the backlog edits are accepted.

- The documentation diff changes only `BUG_BACKLOG.md` and `BACKLOG.md`.

## Applicable guardrails

- **The plan’s “## Plan intent”, genuine structural recurrence:** Record the resolved false-positive risk without implying that unresolved structural recurrence has been removed.

- **The plan’s “## Step intent”, accurate roadmap:** Keep only the still-open audit-trajectory and localized-remedy work in `BACKLOG.md`.

- **The plan’s “## Out of scope”, persisted-history compatibility:** Do not claim or introduce a sidecar-format change in either backlog.

- **The plan’s “## Out of scope”, finding-category boundaries:** Do not redefine structural, claim, or premise categories while describing the completed source boundary.

- **The plan’s “## Out of scope”, decomposition workflow:** Do not change the remaining split, scope-out, or re-seed proposals; this step only updates their tracking text.

## Deferred

- BACKLOG #116’s localized fork classification, suggested split titles, and operator offer — remain open in `BACKLOG.md`; this step removes only the completed recurrence-accuracy slice.

- BACKLOG #172’s hand-resolution telemetry and identity-aware trends — remain separate future work after its dependency wording is corrected.
