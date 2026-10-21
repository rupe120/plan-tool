> **Auto-archived**: this plan was swept on 2026-08-03 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 4 — Record #157 evidence and keep #152 blocked

## Summary

Update `BACKLOG.md` to record the completed #157 contract trace and remove its stale open-work framing. Preserve #152 as blocked and unshipped: its revised plan is evidence-based, but no impact-aware predicate or loop wiring has landed. The key decision is to record the real advisory `impact="high"` candidates and their reachable continuation paths without claiming that the planned augment exists. On completion, the backlog points implementers to the revised #152 plan while #153 and #154 remain blocked on #152’s unshipped augment.

## Table of Contents

- [Summary](#summary) — Reviewer overview of the backlog-only outcome.
- [Table of Contents](#table-of-contents) — Section map for this detail.
- [Why](#why) — Why the backlog must distinguish completed evidence from unshipped code.
- [Input](#input) — Evidence and revised plan artifacts produced by steps 1–3.
- [Files (creates vs edits)](#files-creates-vs-edits) — The single backlog edit.
- [Implementation](#implementation) — Required evidence, status, and dependency wording.
- [Tests](#tests) — Non-code verification for the backlog update.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [Deferred](#deferred) — Implementation and related arc work left open.

## Why

`BACKLOG.md:#157 — Resolve the impact-bearing non-blocking severity contract before #152’s augment gate` is a decision-trace item, while `BACKLOG.md:#152 — Key convergence blocking on the impact axis` tracks unshipped behavior. Steps 1–3 establish that high impact can accompany normalized `nit` or `info` severity and that only selected reconcile and audit paths can observe those findings. The backlog must retain that evidence without treating the planned #152 predicate, its loop wiring, or its downstream dependencies as complete.

## Input

- **Step 1 evidence:** Use the characterization coverage for `plan_tool/review.py:Recommendation`, `plan_tool/review.py:extract_reconcile_recommendations`, and `plan_tool/convergence.py:is_blocking`. It establishes that high-impact findings can normalize to advisory `nit` or `info`, while `LOW` is a blocking `medium` control case.

- **Step 2 evidence:** Use the live-path trace that distinguishes `plan_tool/cli/reconcile.py:_iterate_reconcile_loop` and `plan_tool/review.py:audit_plan_until_stable` from `plan_tool/cli/completeness_cmd.py:_run_iterate_convergence_loop`.

- **Step 3 outcome:** Read `docs/implementation-plans/2-gate-convergence-by-impact.md` and its detail files under `docs/implementation-plans/plan-details/gate-convergence-by-impact/`. Treat the revised plan as proposed implementation scope, not evidence that its code is present.

## Files (creates vs edits)

- **New files:** None.

- **Existing files (edits only):**
  - `BACKLOG.md` — Record the completed #157 evidence, remove #157 as open forward-looking work, and update #152 plus its inbound #153/#154 references without changing their unshipped status.

## Implementation

- **Foundational logic:** Evidence-based backlog status for the impact-convergence arc.

- **Close the completed investigation:** Fold #157’s durable result into `BACKLOG.md:#152 — Key convergence blocking on the impact axis`. State that parser-supported `impact="high"` findings can normalize to `nit` or `info`, and that `LOW` is not a valid advisory example because it normalizes to `medium`. Remove the completed #157 entry rather than retaining a historical shipped-status stub.

- **Record reachability, not new plumbing:** State that the traced advisory candidates reach `plan_tool/cli/reconcile.py:_iterate_reconcile_loop` and `plan_tool/review.py:audit_plan_until_stable`; they do not become completeness-loop inputs through `plan_tool/cli/completeness_cmd.py:_run_iterate_convergence_loop`. Point #152 readers to the revised implementation plan for the exact planned call-site scope.

- **Keep #152 blocked and unshipped:** Replace the obsolete “blocked on #157” wording with a status that accurately says the evidence is complete but the #152 augment has not been implemented. Do not mark its augment shipped, remove its remaining work, or describe `plan_tool/convergence.py:is_blocking_impact` as present.

- **Preserve the later demote boundary:** Keep #152’s impact-only demote explicitly pending on #154. The completed #157 trace does not calibrate impact and must not weaken the severity floor.

- **Preserve inbound dependency truth:** Update `BACKLOG.md:#153` and `BACKLOG.md:#154` only as needed to remove a stale dependency on #157 or stale example wording. Both remain blocked on #152’s unshipped augment; neither becomes ready or shipped from this documentation change.

- **Keep the backlog focused on current work:** Do not edit production code, tests, prompts, schemas, `docs/AUDIT_FLOW.md`, `CLAUDE.md`, or the revised #152 plan in this step.

## Tests

- No automated test changes — this non-code step updates only `BACKLOG.md`.

### Verification (non-code step)

- `#157 closure records the traced contract` — confirm #157 no longer appears as open work and #152 names the advisory high-impact `nit`/`info` evidence plus the blocking `LOW` control.

- `#152 remains unshipped` — confirm no #152 status or acceptance wording says the augment predicate or loop wiring has landed.

- `reachability wording matches steps 1–3` — confirm the backlog names reconcile and audit as reachable paths and excludes completeness-loop finding plumbing.

- `arc dependencies remain accurate` — search `BACKLOG.md` for `#152`, `#153`, `#154`, and `#157`; confirm #153 and #154 remain blocked on the unshipped #152 augment, while #152’s demote remains pending on #154.

- `backlog structure remains intact` — inspect the surrounding entries for their existing heading, bullet, and blank-line spacing.

## Acceptance criteria

- `BACKLOG.md` no longer lists #157 as an open backlog item.

- `BACKLOG.md:#152 — Key convergence blocking on the impact axis` records that `impact="high"` can accompany normalized `nit` or `info` severity, and that `LOW` normalizes to blocking `medium`.

- #152 identifies `plan_tool/cli/reconcile.py:_iterate_reconcile_loop` and `plan_tool/review.py:audit_plan_until_stable` as the traced implementation paths and excludes `plan_tool/cli/completeness_cmd.py:_run_iterate_convergence_loop` from advisory-finding adoption.

- #152 remains explicitly blocked or planning and is not described as shipped.

- #152’s impact-only demote remains pending on #154.

- #153 and #154 remain open and blocked on the unshipped #152 augment.

## Deferred

- **#152 augment implementation** — The predicate and reachable loop wiring remain future work in `docs/implementation-plans/2-gate-convergence-by-impact.md`.

- **#152 impact-only demote** — Remains pending on #154’s calibration work.

- **#153 recurrence routing and #154 drift calibration** — Remain separate backlog work and do not advance from this evidence-recording step.
