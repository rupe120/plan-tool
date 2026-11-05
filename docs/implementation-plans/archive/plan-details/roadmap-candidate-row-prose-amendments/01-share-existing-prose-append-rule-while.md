> **Auto-archived**: this plan was swept on 2026-11-05 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 1 — Share the existing prose append rule while preserving stage replacements and deletions

<!-- plan-tool:detail-format-version: 1 -->

## Summary

Extract the existing stage body-fragment spacing rule into a reusable helper in `plan_tool/roadmap_revision_patch.py`. Keep `merge_stage_revision()` and `_apply_stage_prose_amendments()` responsible for stage-specific replacement and deletion behavior. Update `tests/test_roadmap_revision_patch.py` to pin the shared append behavior and the unchanged stage merge behavior. On green, later candidate assembly can reuse the exact append rule without changing how stage revisions replace or remove issued prose spans.

## Table of Contents

- [Summary](#summary) — Reviewer overview of the small shared-helper refactor.
- [Table of Contents](#table-of-contents) — Quick links to each section.
- [Why](#why) — Why candidate additions need the existing append rule.
- [Input](#input) — Existing stage operations and artifact-body contract this step preserves.
- [Files (creates vs edits)](#files-creates-vs-edits) — The two scoped file edits.
- [Implementation](#implementation) — Shared append behavior and stage-specific boundaries.
- [Tests](#tests) — Focused regression coverage for the helper and stage merge.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Source contract and current implementation anchors.
- [Applicable guardrails](#applicable-guardrails) — Scope limits that bind this refactor.

## Why

Candidate additions need the same body spacing behavior that stage revisions already use, but copying that behavior into the candidate path would create two rules that can drift. The append-only rule is already proven by `_apply_stage_prose_amendments()` in `plan_tool/roadmap_revision_patch.py`; make that narrow rule reusable while keeping source-span replacement and deletion owned by the stage merge path.

## Input

- **Stage operations:** `merge_stage_revision()` receives `StageRevisionOperations`, whose additions carry `AppendRowProseAmendment` fragments while edits and removals carry issued-span amendments.
- **Artifact body:** `_apply_stage_prose_amendments()` starts from `RoadmapArtifact.body`, applies issued replacements or deletions, then appends admitted fragments in material-operation order.
- **Later consumer:** step 2 consumes the extracted append rule for candidate assembly; this step must not add candidate schema, authority, validation, or materialization behavior.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `plan_tool/roadmap_revision_patch.py` — extract the body-fragment append rule from `_apply_stage_prose_amendments()` into a reusable helper and retain stage-specific span processing.
  - `tests/test_roadmap_revision_patch.py` — add focused helper coverage and preserve regression coverage for stage additions, replacements, and deletions.

## Implementation

- **Extract only the append rule.** Move the final body-and-fragment joining behavior from `plan_tool/roadmap_revision_patch.py:_apply_stage_prose_amendments()` into a module-level helper that accepts an existing body and ordered admitted fragments, then returns the completed body.

- **Preserve fragment order.** The helper must append fragments in the order supplied. `_apply_stage_prose_amendments()` must continue to collect additions in `StageRevisionOperations.material_operations` order so later candidate assembly can use the same deterministic rule.

- **Preserve spacing exactly.** The helper must retain the current outcomes for an empty body, a body ending in one newline, a body ending in a blank-line separator, and a body with no trailing newline. It must not trim, rewrite, synthesize, or reorder fragment text.

- **Keep stage replacements and deletions local.** `_apply_stage_prose_amendments()` must still validate issued `StageProseSpan` ownership, reject overlapping replacements, apply replacements from the end of the body backward, and only then pass the resulting body plus admitted addition fragments to the shared helper.

- **Keep stage operation rules unchanged.** `AppendRowProseAmendment`, `ReplaceRowProseAmendment`, and `DeleteRowProseAmendment` retain their current distinct handling. This helper shares formatting behavior only; it must not turn candidate additions into stage operations or introduce source-span behavior for candidate work.

- **Use the helper as the future seam.** Expose the helper from `plan_tool/roadmap_revision_patch.py` in a form step 2 can import directly. One approach is a clearly named module-level function; its exact name is flexible if it describes appending row-owned prose fragments and keeps the call site readable.

## Tests

### Tests for this step

- `test_append_row_prose_fragments_preserves_existing_spacing_rules` — asserts the shared helper produces the current separator behavior for empty bodies and bodies ending with zero, one, or two trailing newlines.
- `test_append_row_prose_fragments_keeps_fragment_order_and_text` — asserts multiple fragments remain unchanged and appear in supplied order.
- `test_stage_merge_separates_each_appended_row_prose_block` — retain or adapt this regression so `merge_stage_revision()` still gives each added row its own correctly separated prose block through the shared helper.
- `test_stage_merge_applies_only_issued_row_owned_prose_spans` — retain coverage that edits and removals still require issued row-owned spans rather than using the append path.
- `test_stage_merge_applies_material_operations_before_feedback_responses` — retain coverage that the refactor does not change merge ordering or feedback response handling.

Every listed test must be green before this step is complete.

## Acceptance criteria

- The append-spacing rule exists once in `plan_tool/roadmap_revision_patch.py` and is callable by later candidate assembly.
- `_apply_stage_prose_amendments()` still applies valid replacement and deletion spans before it appends addition fragments.
- Appending to empty, newline-terminated, blank-line-terminated, and non-newline-terminated bodies matches the current stage output.
- Multiple fragments preserve their supplied order and exact text.
- `tests/test_roadmap_revision_patch.py` passes with coverage for the shared rule and preserved stage merge behavior.

## References

- [BUG_BACKLOG.md — Read “Structural candidates cannot satisfy described-row gates for newly added rows” for the required reuse of the established append-only rule.](BUG_BACKLOG.md)
- [plan_tool/roadmap_revision_patch.py — Read `_apply_stage_prose_amendments()` and `merge_stage_revision()` for the current append, replacement, and deletion boundaries.](plan_tool/roadmap_revision_patch.py)
- [plan_tool/roadmap_revision.py — Read `AppendRowProseAmendment`, `ReplaceRowProseAmendment`, and `DeleteRowProseAmendment` for the distinct typed amendment contracts.](plan_tool/roadmap_revision.py)

## Applicable guardrails

- **The plan’s “## Out of scope”, prose amendment boundary:** Limit this step to sharing append formatting. Do not add replacement-row or removal-row prose capability outside the existing stage behavior.
- **The plan’s “## Out of scope”, candidate authority and lifecycle:** Do not change candidate authority, ledger transitions, accepted-head selection, seed effects, or correction diagnostics.
- **The plan’s “## Out of scope”, prose-gate enforcement:** Do not alter `undescribed-row` behavior or create a bypass around it.
- **The plan’s “## Architecture”, batch cardinality boundary:** Do not import the stage route’s per-feedback material-operation limit into the shared append helper.
