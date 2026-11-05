> **Auto-archived**: this plan was swept on 2026-11-05 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 6 — Reconcile the shipped terminal-error backlog records

<!-- plan-tool:detail-format-version: 1 -->

## Summary

Remove the backlog records that steps 2 through 5 fully deliver from `BACKLOG.md` and `BUG_BACKLOG.md`. Confirm each record’s full stated behavior and regression coverage exists before removing it. Keep unrelated terminal-error work tracked where it is. On green, the active backlogs contain no record that claims a shipped roadmap terminal-error defect remains open.

## Table of Contents

- [Summary](#summary) — Gives the completed documentation outcome.
- [Table of Contents](#table-of-contents) — Links to each detail section.
- [Why](#why) — Explains why the backlog must match shipped behavior.
- [Input](#input) — Names the completed step outcomes used to judge closure.
- [Files (creates vs edits)](#files-creates-vs-edits) — Lists the documentation-only footprint.
- [Implementation](#implementation) — Defines the record-by-record closure check.
- [Tests](#tests) — Lists non-code verification.
- [Acceptance criteria](#acceptance-criteria) — States observable completion checks.
- [References](#references) — Points to the records this step reconciles.
- [Applicable guardrails](#applicable-guardrails) — Keeps the backlog edit within plan scope.
- [Deferred](#deferred) — Identifies terminal-error work that remains open.

## Why

`BACKLOG.md` #344, #347, and #348 plus `BUG_BACKLOG.md`’s prompt-template renderer entry describe the writer-guard, text-read, terminal-status, and renderer failure gaps that steps 2 through 5 address. Leaving a fulfilled record active makes planning and review treat shipped behavior as unfinished. Removing a record before all of its stated behavior ships hides a real gap, so closure must follow a direct check against the landed contract and coverage.

## Input

- **Step 2 outcome:** Confirm the read-or-raise consolidation tracked by `BACKLOG.md` #347 is present and preserves each caller’s required exception family and message.

- **Step 3 outcome:** Confirm the origin distinction tracked by `BACKLOG.md` #344 reaches the CLI boundary and selects the documented preflight or post-start disposition.

- **Step 4 outcome:** Confirm the named prompt-template routes covered by `BUG_BACKLOG.md` now classify expected read and decode failures as roadmap failures rather than unexpected crashes.

- **Step 5 outcome:** Confirm the terminal-disposition contract tracked by `BACKLOG.md` #348 is applied at the primary, materialization, and local-revision exits with the required status, run-log, exit-code, and crash behavior.

- **Closure rule:** Use `BACKLOG.md`’s backlog-reconciliation guidance and each record’s full scope, not only its title, to decide whether it is fulfilled.

## Files (creates vs edits)

- **New files:** None.

- **Existing files (edits only):**
  - `BACKLOG.md` — Remove #344, #347, and #348 only after verifying their complete delivered behavior.
  - `BUG_BACKLOG.md` — Remove “Two prompt-template renderers have no read-failure handling in their caller chain” only after verifying all routes it names are covered.

## Implementation

- **Use record-by-record closure.** Treat each backlog record as fulfilled only when the completed work satisfies its stated symptom, fix, and scope. Do not remove a record because a related file changed or because one route now passes.

- **Close `BACKLOG.md` #344 after the origin contract is proven.** Confirm step 3 preserves the difference between preflight and mid-run `RoadmapWriterGuardError` at `plan_tool/roadmap.py:run_roadmap` and `plan_tool/cli/roadmap_cmd.py:cmd_roadmap`, including their distinct terminal handling. Remove the complete record rather than leaving a stale “not started” status.

- **Close `BACKLOG.md` #347 after the shared read boundary is proven.** Confirm step 2’s work covers the duplicated read-and-wrap behavior named at `plan_tool/roadmap.py:_render_stage_prompt`, `_render_stage_feedback_prompt`, and `_load_stage_artifact` without flattening their caller-owned exception meaning. Do not remove unrelated reader concerns that the record does not own.

- **Close `BACKLOG.md` #348 after exception exits have the selected terminal fact.** Confirm step 5 applies the matrix-defined behavior at `plan_tool/cli/roadmap_cmd.py:cmd_roadmap`, includes the materialization pre-lifecycle refusal boundary, and makes one best-effort status attempt before an unexpected exception reaches `plan_tool/cli/app.py`. Retain any part of the entry that is not delivered rather than rewording it into a weaker claim.

- **Close the prompt-template BUG entry after all named routes are covered.** Verify the behavior at `plan_tool/roadmap.py:_render_seed_materialize_prompt` and `plan_tool/roadmap_revision_run.py:render_local_revision_prompt`, including the caller paths the record identifies. The record is one shared defect class, so remove it only when every named route has the expected terminal disposition; keep the structural-rewrite consumer outside this closure check.

- **Preserve independent tracking.** Keep `BACKLOG.md` #339 and #346, model-failure receipts, recovery work, and broader exception-framework proposals untouched. They are related to terminal behavior but are not delivered by this plan.

## Tests

### Verification (non-code step)

1. **Record-to-step check** — Read `BACKLOG.md` #344, #347, and #348 and the named `BUG_BACKLOG.md` entry against the completed behavior and focused regression coverage from steps 2 through 5.

2. **Residual-record search** — Search `BACKLOG.md` and `BUG_BACKLOG.md` for `#344`, `#347`, `#348`, and `Two prompt-template renderers have no read-failure handling in their caller chain`; each fulfilled record must have no active entry remaining.

3. **Unrelated-work check** — Confirm references to `BACKLOG.md` #339 and #346 remain, so this documentation edit does not imply interrupt or stage-loop structural work shipped.

4. **Repository test check** — Run the focused regression tests added or updated by steps 2 through 5 before removing their records; this step adds no test code.

## Acceptance criteria

- `BACKLOG.md` no longer contains active entries #344, #347, or #348 after their full record scopes and focused regression coverage are verified.

- `BUG_BACKLOG.md` no longer contains the prompt-template renderer entry after every route it names has the expected shipped disposition.

- `BACKLOG.md` and `BUG_BACKLOG.md` retain unrelated terminal-error records, including #339 and #346.

- Neither backlog claims a terminal-error gap remains open when its corresponding behavior and regression coverage ship.

## References

- [BACKLOG.md #344](BACKLOG.md) — Read the writer-guard origin and exit-code closure conditions.

- [BACKLOG.md #347](BACKLOG.md) — Read the shared text-read boundary and preserved exception-family conditions.

- [BACKLOG.md #348](BACKLOG.md) — Read the exception terminal-status and crash-boundary conditions.

- [BUG_BACKLOG.md prompt-template renderer entry](BUG_BACKLOG.md) — Read the named renderer routes and caller-chain closure conditions.

## Applicable guardrails

- **The plan’s “## Scope guardrails”, roadmap-result and lifecycle boundaries** — This step must not change implementation behavior while reconciling documentation.

- **The plan’s “## Scope guardrails”, unexpected-error boundary** — This step must not describe unexpected defects as fulfilled expected failures unless steps 2 through 5 preserve the application crash path.

- **The plan’s “## Out of scope”, related terminal work** — This step must not close entries for interrupts, recovery, locking, retries, or success-output behavior.

## Deferred

- `BACKLOG.md` #339 and #346 — Keep their independent interrupt and stage-loop structural work open because this step does not implement either one.

- Model-response receipts and broader exception-framework work — Retain their existing tracking because this documentation-only step closes only the records delivered by steps 2 through 5.
