# Step 1 — Show valid collection names and disambiguate existing batch rows

<!-- plan-tool:detail-format-version: 1 -->

## Summary

Make every batch candidate prompt show the collection vocabulary the delta parser accepts and identify the collection for each referenced existing row. Cover fresh proposals, stored-candidate review replacements, and structural edits without changing immutable capsule or receipt bytes. The retry lifecycle belongs to step 2.

## Table of Contents

- [Summary](#summary) — Reviewer overview of the prompt change.
- [Table of Contents](#table-of-contents) — Links to this detail file’s sections.
- [Why](#why) — The current class-name versus collection-name mismatch.
- [Input](#input) — Immutable batch and delta contracts this step reads.
- [Files (creates vs edits)](#files-creates-vs-edits) — Declared file changes.
- [Implementation](#implementation) — Required prompt hints across batch callers.
- [Tests](#tests) — Focused regression and failure-boundary coverage.
- [Acceptance criteria](#acceptance-criteria) — Observable completion conditions.
- [References](#references) — Format and code contracts to consult.
- [Applicable guardrails](#applicable-guardrails) — Plan boundaries for this work.

## Why

`plan_tool/roadmap_candidate_context.py:_row_identity` records Python row-type names such as `EntityRow`, while `plan_tool/roadmap_candidate.py:parse_candidate_delta` accepts collection names such as `entities`. That leaves a model with enough context to identify a row but not enough vocabulary to emit a valid operation, and `PatternRow` has two possible collections. Fresh and stored-candidate batch prompts share this mismatch.

## Input

- **Immutable batch evidence:** Read `CandidateContextBatchCapsule`, `CandidateContextBatchReceipt`, and the payload rendered by `plan_tool/roadmap_candidate_context.py:_render_batch_payload`. Prompt-only guidance must not alter this persisted evidence or its identities.
- **Operation vocabulary:** Read `plan_tool/roadmap_candidate.py:_ROW_TYPE_NAMES`, `_parse_stage_row`, and `_find_existing_row` as the closed vocabulary and lookup behavior the prompt must help the model satisfy.
- **Actual collection ownership:** Use `plan_tool/roadmap_artifacts.py:stage_row_collections` to distinguish a row’s real collection, especially `ComponentsArtifact.system_patterns` from `ComponentsArtifact.component_patterns`.
- **Batch authority:** Preserve the reviewer-item snapshot contract carried by `CandidateContextBatchCapsule.reviewer_items`; hints describe valid operation syntax only and must not add edit authority.

## Files (creates vs edits)

- **New files:** None.

- **Existing files (edits only):**
  - `plan_tool/roadmap_candidate_context.py` — Add or expose prompt-only collection information derived from the current source artifacts while retaining existing serialized row identities and payload rendering.
  - `plan_tool/roadmap_candidate_run.py` — Render source-checked collection guidance into batch prompts.
  - `plan_tool/roadmap_candidate_review.py` — Supply the immutable source at review replacement and structural edit model calls.
  - `plan_tool/prompts/roadmap-candidate-delta.md` — Tell the model where to find valid collection names and how existing rows are disambiguated.
  - `tests/test_roadmap_candidate_run.py` — Cover prompt guidance, source binding, and byte identity.
  - `tests/test_roadmap_candidate_review.py` — Cover stored-batch review and structural edit prompts.

## Implementation

- **Keep persisted identities unchanged.** `plan_tool/roadmap_candidate_context.py:_row_identity` and `_row_digest` must retain their current persisted representation. The collection hint is a prompt-view fact, not a new capsule field, receipt field, digest input, replay key, or authority source.

- **Derive collection names from the actual artifact shape.** Use the stage collection ownership exposed by `plan_tool/roadmap_artifacts.py:stage_row_collections` when preparing model-facing guidance. A referenced `EntityRow` must be shown as belonging to `entities`; a referenced `PatternRow` must name the specific collection that contains it. Do not infer a pattern collection from the Python class alone.

- **Show the parser’s accepted vocabulary.** The batch prompt rendered by `plan_tool/roadmap_candidate_run.py:render_candidate_delta_prompt` must present valid collection names in the form accepted by `plan_tool/roadmap_candidate.py:parse_candidate_delta`. Keep class names invalid rather than normalizing or accepting them.

- **Keep new-pattern choices available.** Show both pattern collection names as valid choices for a new pattern. Existing-row guidance must identify one actual collection; it must not imply that the same `PatternRow` class maps to only one collection globally.

- **Keep prompt guidance outside issued evidence.** Derive a transient supplement from the resolved immutable source version named by the receipt, checking every hinted row against the issued capsule. Pass it through `render_candidate_delta_prompt` on fresh proposals and through the two stored-batch call sites in `plan_tool/roadmap_candidate_review.py`. Resolve the source before either review invocation; refuse before a model call when the source or row binding cannot be proved. Selector-era prompts retain their existing route.

## Tests

### Tests for this step

- `test_batch_prompt_lists_valid_domain_collection_names` — Asserts a rendered batch prompt names `entities` and other valid operation collections, not only Python row class names.
- `test_batch_prompt_disambiguates_existing_pattern_rows_by_collection` — Asserts existing `PatternRow` references identify `system_patterns` or `component_patterns` according to their source collection, while both remain available for additions.
- `test_batch_prompt_refuses_unproved_source_row_binding_before_invocation` — A changed or mismatched source cannot produce a hint or reach the model.
- `test_batch_prompt_guidance_keeps_capsule_and_receipt_identities_unchanged` — Prompt guidance does not alter issued payload bytes, receipt, or capsule identity.
- `test_stored_batch_replacement_prompt_includes_source_bound_collection_hints` — Review replacement uses the same source-bound hints as a fresh proposal.
- `test_structural_batch_edit_prompt_includes_source_bound_collection_hints` — Structural edit uses the same source-bound hints as a fresh proposal.

Every listed test must be green before this step is complete.

## Acceptance criteria

- A batch prompt for a Domain entity names `entities` as a valid collection name.
- A batch prompt identifies the actual collection for every existing row reference it presents.
- Existing system and component patterns are distinguishable in prompt guidance, and both pattern collections are offered for a new pattern.
- Prompt-only collection guidance leaves capsule payload bytes, receipt contents, and identity digests unchanged.
- Fresh proposal, stored-batch review replacement, and structural edit model calls all receive the same verified hints; an unprovable source binding refuses before invocation.
- Focused candidate-run and candidate-review tests pass.

## References

- [ROADMAP_FEEDBACK_FORMAT.md — Read the ledger-to-candidate workflow and non-publication rules for rejected output.](../../../../ROADMAP_FEEDBACK_FORMAT.md)
- [ROADMAP_FORMAT.md — Read the immutable candidate lifecycle and stage collection schema.](../../../../ROADMAP_FORMAT.md)
- [plan_tool/roadmap_candidate_context.py:_row_identity, _render_batch_payload, _row_digest — Verify persisted identity and payload boundaries.](../../../../plan_tool/roadmap_candidate_context.py)
- [plan_tool/roadmap_candidate.py:parse_candidate_delta, _ROW_TYPE_NAMES — Verify the closed operation collection vocabulary.](../../../../plan_tool/roadmap_candidate.py)
- [plan_tool/roadmap_candidate_run.py:render_candidate_delta_prompt — Implement prompt rendering.](../../../../plan_tool/roadmap_candidate_run.py)
- [plan_tool/roadmap_candidate_review.py — Supply source-bound hints to stored-batch model calls.](../../../../plan_tool/roadmap_candidate_review.py)
- [plan_tool/prompts/roadmap-candidate-delta.md — Keep the model response contract closed while adding guidance.](../../../../plan_tool/prompts/roadmap-candidate-delta.md)

## Applicable guardrails

- **The plan’s “## Plan intent”, candidate publication boundary:** Prompt guidance must not weaken validation or publication rules.
- **The plan’s “## Step intent”, collection vocabulary:** Limit the feature to helping the model choose collection names and distinguish existing pattern collections.
- **The plan’s “## Scope guardrails”, immutable evidence boundary:** Keep collection guidance transient and preserve the issued batch’s authority and identity.
- **The plan’s “## Out of scope”, persisted-contract changes:** Do not migrate stored row types, broaden parser acceptance, or alter accepted-head and structural approval behavior.
