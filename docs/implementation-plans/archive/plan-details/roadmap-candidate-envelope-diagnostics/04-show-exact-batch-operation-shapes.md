> **Auto-archived**: this plan was swept on 2026-11-05 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 4 — Show exact batch operation shapes in the candidate prompt

<!-- plan-tool:detail-format-version: 1 -->

## Summary

Update `plan_tool/prompts/roadmap-candidate-delta.md` so the ledger-batch prompt shows the exact accepted JSON envelopes for `add-row`, `replace-row`, and `remove-row`. Have `plan_tool/roadmap_candidate_run.py:render_candidate_delta_prompt` render those shapes from the parser-owned operation key sets landed by step 1. Add prompt-rendering and bounded-retry coverage in `tests/test_roadmap_candidate_run.py`. On green, the batch prompt clearly separates writable operations from discovery-only identity records, and a compliant retry can store an inert structural candidate.

## Table of Contents

- [Summary](#summary) — States the prompt and rendering result.
- [Table of Contents](#table-of-contents) — Routes readers through this detail.
- [Why](#why) — Explains the current envelope ambiguity.
- [Input](#input) — Names the parser and batch-prompt contracts this step reads.
- [Files (creates vs edits)](#files-creates-vs-edits) — Lists the scoped prompt, renderer, and test edits.
- [Implementation](#implementation) — Defines the parser-derived prompt shapes and retry boundary.
- [Tests](#tests) — Lists focused prompt and retry coverage.
- [Acceptance criteria](#acceptance-criteria) — Defines observable completion checks.
- [References](#references) — Points to the relevant roadmap candidate contracts.
- [Applicable guardrails](#applicable-guardrails) — Applies the plan boundaries to this prompt change.
- [Deferred](#deferred) — Separates later hint and selector work.

## Why

`plan_tool/prompts/roadmap-candidate-delta.md` names the allowed operation verbs but does not show their closed field shapes. Meanwhile, `plan_tool/roadmap_candidate_context.py:candidate_collection_hints` renders `existing_rows` records with fields that resemble an operation envelope. The batch model can copy that discovery record into an operation, receive one bounded correction, and repeat the same malformed shape. Showing parser-owned operation shapes gives the correction a prompt that directly distinguishes editable records from capsule identity data.

## Input

- **Step 1 parser constants:** Step 1 supplies the parser-owned required and optional operation key sets from `plan_tool/roadmap_candidate.py:_parse_operation`. Read the landed constants rather than repeating field lists in `plan_tool/roadmap_candidate_run.py`.

- **Batch response contract:** `plan_tool/roadmap_candidate.py:parse_candidate_delta` accepts the unwrapped batch root containing `operations`, `responses`, and `derived_feedback`. This step must preserve that root shape and its strict operation parsing.

- **Prompt assembly:** `plan_tool/roadmap_candidate_run.py:render_candidate_delta_prompt` selects `roadmap-candidate-delta.md` for `CandidateContextBatchCapsule`, supplies `collection_hints`, and appends the existing correction reason for attempt two.

- **Bounded proposal loop:** `plan_tool/roadmap_candidate_run.py:_run_batch_candidate_proposal` has two attempts and records rejected bytes through `record_candidate_failure_diagnostics`. This step changes prompt guidance only; it does not change retry, receipt, or storage behavior.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `plan_tool/prompts/roadmap-candidate-delta.md` — add exact, parser-derived operation examples and clarify the writable decision-row shape.
  - `plan_tool/roadmap_candidate_run.py` — prepare and substitute the operation-shape prompt variable in `render_candidate_delta_prompt`.
  - `tests/test_roadmap_candidate_run.py` — cover rendered shapes, omitted fields, and a malformed-first-attempt retry that stores after a compliant replacement.

## Implementation

- **Render parser-owned operation shapes.** Use the operation key-set constants landed by step 1 to build prompt content for `add-row`, `replace-row`, and `remove-row`. `plan_tool/roadmap_candidate_run.py:render_candidate_delta_prompt` must pass the rendered content only to the batch template; the selector template already owns its separate response contract.

- **Show complete envelopes, not a field inventory.** `plan_tool/prompts/roadmap-candidate-delta.md` must show one exact JSON object shape for each operation. The examples must make the required and optional fields clear enough that a model does not infer that capsule identity fields belong in an operation.

- **Make the add-row boundary visible.** Include a complete entity add-row example with `row_type` set to the collection name `entities`. It must omit `collection` and `row_id`, even though `existing_rows` records contain those discovery fields.

- **Keep examples safe and narrow.** Use placeholder values and a minimal valid entity row. Do not add worked row bodies for every row type, and do not alter the issued capsule, receipt, collection hints, or their persisted shapes.

- **Name the decision-row restriction.** State in the batch prompt that `source` is not writable in a `decisions` row. This aligns the model-facing contract with `plan_tool/roadmap_candidate.py:_parse_stage_row` without accepting, dropping, or rewriting that field.

- **Preserve the existing correction channel.** Keep `_run_batch_candidate_proposal` passing the parser or materialization rejection unchanged into the second prompt through `render_candidate_delta_prompt`. The prompt examples must help the model replace the whole response under the same issued batch, not repair input in the tool.

- **Keep batch and selector surfaces separate.** Do not modify `plan_tool/prompts/roadmap-candidate-delta-selector.md`. Its explicit envelope guidance remains its own contract, while both routes continue to share `parse_candidate_delta`.

## Tests

- `test_batch_prompt_renders_parser_owned_operation_shapes` — renders a batch prompt and verifies each displayed operation object has exactly the required and optional fields defined by the parser-owned constants.

- `test_batch_prompt_add_row_example_omits_discovery_only_fields` — verifies the entity add-row example uses `row_type: "entities"` and omits `collection` and `row_id`.

- `test_batch_prompt_states_decision_source_is_not_writable` — verifies the batch prompt tells the model not to emit `source` for a `decisions` row.

- `test_batch_prompt_keeps_collection_hints_discovery_only` — verifies the rendered `existing_rows` hint remains present as context while the explicit operation examples remain distinct from its identity shape.

- `test_batch_proposal_retries_malformed_operation_envelopes_with_one_complete_correction` — supplies a synthetic first reply using `collection`, class-name `row_type`, and add-row `row_id`, then a compliant replacement; asserts the second prompt carries the correction and the candidate stores.

- `test_batch_proposal_retries_decision_source_with_a_compliant_replacement` — supplies a synthetic malformed decision add-row containing `source`, then a compliant replacement; asserts the candidate stores without changing parser strictness.

Every listed test must be green before this step is complete.

## Acceptance criteria

- `render_candidate_delta_prompt` renders exact batch operation shapes derived from the parser-owned key sets for all three allowed operation names.

- The batch prompt’s entity add-row example omits `collection` and `row_id` and uses the collection vocabulary for `row_type`.

- The batch prompt states that `source` is not a writable `decisions` row field.

- `plan_tool/prompts/roadmap-candidate-delta.md` continues to request the unwrapped batch response root and does not introduce selector expansion behavior.

- A synthetic malformed batch reply receives one existing correction attempt, and a compliant replacement stores an inert structural candidate.

- `tests/test_roadmap_candidate_run.py` passes with the new prompt and retry coverage.

## References

- [BUG_BACKLOG.md — Candidate proposal retry entry](BUG_BACKLOG.md) — Read the scoped failure evidence and required prompt-shape outcome.

- [ROADMAP_FEEDBACK_FORMAT.md — Ledger-backed candidate lifecycle](ROADMAP_FEEDBACK_FORMAT.md) — Read the batch authority and inert-candidate rules.

- [ROADMAP_FORMAT.md — Immutable roadmap artifact contract](ROADMAP_FORMAT.md) — Read the typed row and structural route boundaries.

- [plan_tool/roadmap_candidate.py — Candidate delta parser](plan_tool/roadmap_candidate.py) — Read `parse_candidate_delta` and `_parse_operation` for the accepted wire shapes.

- [plan_tool/roadmap_candidate_run.py — Batch prompt and retry loop](plan_tool/roadmap_candidate_run.py) — Read `render_candidate_delta_prompt` and `_run_batch_candidate_proposal`.

## Applicable guardrails

- **The plan’s “## Scope guardrails”, strict parser contract:** This step must improve prompt guidance without widening accepted operation or row schemas.

- **The plan’s “## Scope guardrails”, identity preservation:** This step must not change issued capsule bytes, receipt or digest identity, replay keys, or accepted-head behavior.

- **The plan’s “## Out of scope”, no parse-time repair:** The prompt must direct a compliant replacement; it must not add coercion, silent dropping, or class-name acceptance.

- **The plan’s “## Out of scope”, bounded retry and receipts:** Retain the existing two-attempt loop and parse-failure receipt behavior.

- **The plan’s “## Out of scope”, selector separation:** Limit prompt edits to `plan_tool/prompts/roadmap-candidate-delta.md`.

## Deferred

- Reshaping `plan_tool/roadmap_candidate_context.py:candidate_collection_hints` — The discovery-record shape remains unchanged in this focused prompt step; any shared context-contract change needs separate work.

- First-attempt model hit-rate measurement — Hermetic tests prove that the prompt contract is satisfiable and the retry path works, but measuring production adherence needs real roadmap inputs and durable operational evidence.
