# Step 2 — Remove the resolved candidate relation bug from the backlog

<!-- plan-tool:detail-format-version: 1 -->

## Summary

Remove the resolved same-batch relation-authority entry from `BUG_BACKLOG.md` after step 1 lands its focused regressions and the plan’s suite passes. Keep the change limited to the one resolved backlog record. Preserve adjacent active entries and the backlog’s existing section structure. On green, the backlog no longer presents shipped behavior as an open bug.

## Table of Contents

- [Summary](#summary) — Reviewer-level outcome and affected file.
- [Table of Contents](#table-of-contents) — Routes to each section.
- [Why](#why) — Why the resolved issue must leave the active backlog.
- [Input](#input) — Step 1 completion evidence required before removal.
- [Files (creates vs edits)](#files-creates-vs-edits) — The limited documentation footprint.
- [Implementation](#implementation) — Required bounded backlog removal.
- [Tests](#tests) — Non-code verification for the removal.
- [Acceptance criteria](#acceptance-criteria) — Observable closure conditions.
- [References](#references) — Source record and unchanged lifecycle context.
- [Applicable guardrails](#applicable-guardrails) — Boundaries that keep closure narrow.
- [Deferred](#deferred) — Work this closeout does not perform.

## Why

`BUG_BACKLOG.md` lists the predecessor-only relation-authority failure as active work. Once step 1 proves that exact admitted same-batch additions support relation endpoints while preserving fail-closed authority, selector-era behavior, and noncanonical publication behavior, retaining the entry would misstate the current roadmap-candidate contract and invite duplicate work.

## Input

- **Step 1 completion:** Step 1 supplies the focused materialization and candidate-run regressions proving exact same-batch endpoint authority, preserved refusal cases, and inert structural-candidate behavior.
- **Backlog record:** `BUG_BACKLOG.md` contains the exact heading `Candidate relation authority rejects endpoints added by the same admitted batch`; remove that complete record only after the step 1 evidence and the plan-level test command are green.

## Files (creates vs edits)

- **New files:** None.

- **Existing files (edits only):**
  - `BUG_BACKLOG.md` — remove the complete resolved candidate-relation bug record headed `Candidate relation authority rejects endpoints added by the same admitted batch`.

## Implementation

- **Remove only the resolved record.** Delete the target heading and all of its associated fields in `BUG_BACKLOG.md`, from its heading through its origin entry.

- **Keep neighboring backlog items intact.** Retain the preceding structural-approval entry and the following `The single candidate correction still names only the first of several defects that the closed diagnostics do not cover` entry without changing their content or placement.

- **Require implementation evidence first.** Perform this documentation closeout only after step 1 has landed its relation-authority behavior and regressions. Do not replace the active entry with a new closure note, summary, or duplicate tracking record.

- **Avoid a broader backlog sweep.** This step records the resolved candidate-relation behavior only. Other roadmap-candidate risks, diagnostics work, and relation-authority redesigns remain independently tracked or deferred.

## Tests

### Verification (non-code step)

1. `BUG_BACKLOG.md` target-heading search — confirms `Candidate relation authority rejects endpoints added by the same admitted batch` has no remaining match in the active backlog.
2. `BUG_BACKLOG.md` adjacent-entry review — confirms the surrounding active entries remain present and readable after the deletion.
3. `tests/test_roadmap_candidate.py` focused regressions from step 1 — confirms same-batch endpoint authority and preserved refusal boundaries remain green.
4. `tests/test_roadmap_candidate_run.py` focused regression from step 1 — confirms the batch reaches the existing structural review surface, retains its selected-item ledger transition, and publishes no canonical artifact, accepted head, or seed.
5. `uv run pytest tests/ -q -n auto` — confirms the plan-level suite passes after the backlog closeout.
6. `git diff --name-only` — confirms this non-code step changes only `BUG_BACKLOG.md`.

## Acceptance criteria

- `BUG_BACKLOG.md` no longer contains the resolved candidate-relation bug heading or its record body.
- The adjacent active backlog entries remain present and unchanged.
- Step 1’s focused candidate and candidate-run regressions pass.
- `uv run pytest tests/ -q -n auto` passes.
- The step’s diff modifies only `BUG_BACKLOG.md`.

## References

- [BUG_BACKLOG.md — Read the resolved candidate-relation record and preserve the surrounding active entries.](../../../BUG_BACKLOG.md)
- [docs/implementation-plans/2-roadmap-candidate-same-batch-relations.md — Confirm step 1’s acceptance evidence before closing the backlog record.](../2-roadmap-candidate-same-batch-relations.md)
- [plan_tool/roadmap_candidate.py:_validate_operation_authority and _validate_relation_authority — Verify the authority boundary that step 1 changes.](../../../plan_tool/roadmap_candidate.py)

## Applicable guardrails

- **The plan’s “## Plan intent”, fail-closed publication boundary:** Remove the record only after step 1 proves the intended narrow authority change without changing candidate publication behavior.
- **The plan’s “## Step intent”, shipped-behavior closeout:** Limit this step to making the backlog reflect verified behavior.
- **The plan’s “## Out of scope”, broader candidate lifecycle work:** Do not use this documentation change to alter authority, gates, review, promotion, accepted-head selection, or seed lifecycle.

## Deferred

- Broader relation-authority redesigns — remain outside this closeout step under the plan’s “## Out of scope”.
