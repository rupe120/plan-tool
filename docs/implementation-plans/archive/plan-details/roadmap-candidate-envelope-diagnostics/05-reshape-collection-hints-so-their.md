> **Auto-archived**: this plan was swept on 2026-11-05 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 5 — Reshape collection hints so their records do not resemble operations

<!-- plan-tool:detail-format-version: 1 -->

## Summary

Reshape the per-row discovery records returned by `plan_tool/roadmap_candidate_context.py:candidate_collection_hints` so they remain useful collection hints without copying a candidate operation’s flat field shape. Keep the existing class-to-collection vocabulary and preserve an unambiguous collection mapping for every issued existing row, including both `PatternRow` collections. Update focused context and batch-prompt tests in `tests/test_roadmap_candidate_context.py` and `tests/test_roadmap_candidate_run.py`. On green, prompt rendering still tells the model which collection an existing row belongs to, but the hint record cannot be mistaken for an editable operation.

## Table of Contents

- [Summary](#summary) — States the completed hint behavior and affected files.
- [Table of Contents](#table-of-contents) — Routes readers through this detail.
- [Why](#why) — Explains the current operation-shaped discovery record.
- [Input](#input) — Names the issued-capsule and prompt contracts this step reads.
- [Files (creates vs edits)](#files-creates-vs-edits) — Lists the scoped code and test edits.
- [Implementation](#implementation) — Defines the discovery-only hint boundary.
- [Tests](#tests) — Covers direct hints and rendered batch prompts.
- [Acceptance criteria](#acceptance-criteria) — Defines observable completion checks.
- [References](#references) — Points to the candidate and roadmap contracts.
- [Applicable guardrails](#applicable-guardrails) — Applies the plan’s identity and parser boundaries.
- [Deferred](#deferred) — Separates parser, prompt, and retry work owned elsewhere.

## Why

`plan_tool/roadmap_candidate_context.py:candidate_collection_hints` currently renders each `existing_rows` entry as flat `artifact_key`, `row_type`, `row_id`, and `collection` fields. That closely matches the fields the strict operation parser uses, and the batch prompt exposes these records beside the writable response contract. The hint must still distinguish `system_patterns` from `component_patterns`, but it must present that discovery information in a shape that does not invite a model to copy it into an operation.

## Input

- **Issued batch evidence:** `plan_tool/roadmap_candidate_context.py:CandidateContextBatchCapsule`, `CandidateContextFullMember`, and `CandidateContextInventoryEntry` provide the existing-row identities this renderer verifies against the immutable `ResolvedRoadmapVersion`. The issued capsule, receipt, and their identities remain unchanged.

- **Source-backed collection lookup:** `plan_tool/roadmap_candidate_context.py:candidate_collection_hints` builds the row-to-collection mapping from `stage_row_collections` and `_STAGE_ROW_TYPE_BY_COLLECTION`. It must retain the source and digest checks before rendering a hint.

- **Batch prompt consumer:** `plan_tool/roadmap_candidate_run.py:render_candidate_delta_prompt` serializes the returned hint into the existing `${collection_hints}` slot in `plan_tool/prompts/roadmap-candidate-delta.md`. Step 4 supplies the exact operation shapes separately; this step must remain compatible with that prompt consumer without editing it.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `plan_tool/roadmap_candidate_context.py` — reshape the per-row discovery data returned by `candidate_collection_hints` while preserving its source-verification behavior and class vocabulary.
  - `tests/test_roadmap_candidate_context.py` — add direct coverage for the discovery-only row mapping and its pattern-collection disambiguation.
  - `tests/test_roadmap_candidate_run.py` — update batch-prompt coverage for the rendered hint shape and its separation from writable operations.

## Implementation

- **Keep collection hints discovery-only.** Make `candidate_collection_hints` return a per-issued-row mapping to the source collection without emitting a record that carries an operation identity field name (`artifact_key`, `row_type`, `row_id`) or `collection` at its top level; the former flat record is exactly that shape. Keep `existing_rows` available to the existing batch prompt unless the landed prompt contract already provides another compatible name.

- **Use a visibly separate identity shape.** One suitable approach is to nest or otherwise label the row identity as discovery metadata, with the collection as the value it identifies. The exact JSON layout is the implementer’s choice, provided no top-level key of a hint record is an operation identity field name or `collection`. Derive the operation names from the parser-owned key constants (step 1) rather than restating them, so a later operation field cannot slip past the check.

- **Retain every existing-row mapping.** Build entries from both `capsule.full_members` and `capsule.inventory`, as `candidate_collection_hints` does today. Each entry must continue to identify the source collection for its issued row.

- **Preserve pattern disambiguation.** `PatternRow` alone does not select one collection because `_STAGE_ROW_TYPE_BY_COLLECTION` maps it to both `system_patterns` and `component_patterns`. The returned per-row mapping must retain the exact source collection for each pattern row, not merely the class-level vocabulary.

- **Keep the class vocabulary unchanged.** `valid_collections_by_class` remains a prompt aid and must continue to show every valid collection for each row class. It does not replace the per-row mapping for existing rows.

- **Do not weaken source verification.** Retain the predecessor, receipt-source, capsule-source, row identity, ambiguity, and digest checks in `candidate_collection_hints`. A reshaped hint is derived prompt text only; it must not alter capsule payload bytes, receipts, digests, replay keys, or row authority.

- **Keep writable contracts elsewhere.** Do not modify `plan_tool/roadmap_candidate.py:parse_candidate_delta` or its operation envelopes in this step. Step 4’s parser-derived prompt shapes remain the writable contract; this step only makes the hint clearly unlike that contract.

## Tests

### Tests for this step

- `test_candidate_collection_hints_preserve_each_issued_row_collection` — asserts full-member and inventory entries still map each issued row identity to its source collection.

- `test_candidate_collection_hints_disambiguate_pattern_collections` — asserts pattern rows in `system_patterns` and `component_patterns` retain distinct per-row collection values.

- `test_candidate_collection_hint_records_do_not_match_operation_envelopes` — asserts the top-level keys of every rendered per-row hint record are disjoint from the union of the parser's operation key sets and `collection`. Verify by mutation: restoring the former flat `artifact_key`/`row_type`/`row_id`/`collection` record makes this test fail.

- `test_batch_prompt_identifies_both_existing_pattern_collections` — updates the existing prompt test to read the reshaped hints and assert both pattern collections remain visible in the serialized batch prompt.

- `test_batch_prompt_renders_discovery_hints_separately_from_operation_shapes` — asserts the prompt contains the reshaped discovery mapping while step 4’s operation examples remain the only writable envelope shapes.

Every listed test must be green before this step is complete.

## Acceptance criteria

- `candidate_collection_hints` returns an exact collection mapping for every issued existing row from both full members and inventory entries.

- The mapping distinguishes `system_patterns` from `component_patterns` for issued `PatternRow` records.

- No `existing_rows` hint record has an operation identity field name or `collection` as a top-level key, and the former flat record shape fails that check.

- `valid_collections_by_class` retains its existing class-to-collection vocabulary.

- The batch prompt renders the reshaped hints and still exposes each existing pattern row’s exact collection.

- The source-validation failures in `candidate_collection_hints` remain enforced.

- `tests/test_roadmap_candidate_context.py` and `tests/test_roadmap_candidate_run.py` pass.

## References

- [BUG_BACKLOG.md — Read the candidate-envelope source entry for the hint-shape property and stored-response evidence.](../../../../../BUG_BACKLOG.md)

- [ROADMAP_FEEDBACK_FORMAT.md — Read the ledger-to-candidate lifecycle that keeps hints separate from proposal authority.](../../../../../ROADMAP_FEEDBACK_FORMAT.md)

- [ROADMAP_FORMAT.md — Read the immutable artifact and structural-route contract.](../../../../../ROADMAP_FORMAT.md)

- [plan_tool/roadmap_candidate_context.py — Read `candidate_collection_hints` and the immutable capsule records that supply source-backed identities.](../../../../../plan_tool/roadmap_candidate_context.py)

- [plan_tool/roadmap_candidate_run.py — Read `render_candidate_delta_prompt` for the batch prompt’s hint consumer.](../../../../../plan_tool/roadmap_candidate_run.py)

## Applicable guardrails

- **The plan’s “## Scope guardrails”, strict-parser boundary** — this step must not broaden accepted candidate-delta fields or repair malformed operations.

- **The plan’s “## Scope guardrails”, immutable-evidence boundary** — this step may change derived prompt hints only; issued capsule bytes, receipts, digests, and replay identity must remain unchanged.

- **The plan’s “## Out of scope”, persisted identity and row-rendering boundary** — retain capsule identity records and full decision-row rendering as they are.

- **The plan’s “## Out of scope”, selector and retry boundary** — do not change the selector prompt, retry count, parse-failure receipt behavior, or candidate publication flow.

## Deferred

- Parser diagnostics and operation-envelope validation — steps 1 through 3 own the strict parser and closed correction reasons.

- Batch operation examples and template wording — step 4 owns the parser-derived writable prompt shapes; this step only supplies compatible discovery data.

- End-to-end malformed-reply retry fixtures — step 6 owns the combined retry, receipt, and inert-candidate coverage.
