# Step 1 — Move operation key sets into shared parser constants

<!-- plan-tool:detail-format-version: 1 -->

## Summary

Move the three candidate-operation envelope key sets into immutable module-level constants in `plan_tool/roadmap_candidate.py`. Make `_parse_operation` use those constants without changing which `add-row`, `replace-row`, and `remove-row` payloads the strict parser accepts or rejects. Update `tests/test_roadmap_candidate.py` to prove each constant describes the parser’s actual envelope. On green, later prompt work can use the same constants instead of copying operation field lists.

## Table of Contents

- [Summary](#summary) — Quick description of the refactor and its result.
- [Table of Contents](#table-of-contents) — Links to the detail sections.
- [Why](#why) — Explains the current duplicated contract risk.
- [Input](#input) — Names the existing parser contract this step preserves.
- [Files creates vs edits](#files-creates-vs-edits) — Lists the two in-scope edits.
- [Implementation](#implementation) — Describes the shared operation-envelope contract.
- [Tests](#tests) — Covers parser and constant agreement.
- [Acceptance criteria](#acceptance-criteria) — Defines observable completion checks.
- [References](#references) — Points to the roadmap candidate contracts.
- [Applicable guardrails](#applicable-guardrails) — Records the plan boundaries for this refactor.
- [Deferred](#deferred) — Separates later prompt and diagnostic work.

## Why

`plan_tool/roadmap_candidate.py:_parse_operation` currently owns the accepted fields as inline literals, while the batch prompt needs to show that same closed envelope to the model. Leaving the lists embedded in parser branches makes the two surfaces easy to drift apart and contributed to replies that mix collection-hint fields with operation fields. This step establishes one parser-owned source before any model-facing rendering consumes it.

## Input

- **Closed parser contract:** `plan_tool/roadmap_candidate.py:parse_candidate_delta` and `_parse_operation` define the current accepted operation envelopes. Preserve their accepted keys, optional `ordering` behavior, operation selection, and rejection behavior.
- **Current strict-key helper:** `plan_tool/roadmap_candidate.py:_require_keys` receives required and optional key sets. The constants must fit this helper without widening its input contract or changing its current generic diagnostic in this step.
- **Existing consumers:** `plan_tool/roadmap_candidate_run.py` and `plan_tool/roadmap_candidate_review.py` replay normalized operations through `parse_candidate_delta`. This refactor must leave those replay inputs valid without edits outside this step’s declared files.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `plan_tool/roadmap_candidate.py` — add immutable operation-envelope key-set constants near `parse_candidate_delta` and make `_parse_operation` use them.
  - `tests/test_roadmap_candidate.py` — add focused coverage that the constants and strict parser describe the same accepted envelope shapes.

## Implementation

- **Make the parser the owner of operation fields.** Define immutable required and optional key sets for each of `_parse_operation`’s three supported operations: `add-row`, `replace-row`, and `remove-row`. Keep the constants in `plan_tool/roadmap_candidate.py` close to `parse_candidate_delta`, `_ROW_TYPE_NAMES`, and `_parse_operation` so the closed wire contract is easy to find.

- **Preserve the exact current operation vocabulary.** `_parse_operation` must continue to accept only its existing fields for each operation. In particular, `ordering` remains optional only for `add-row` and `remove-row`; `row_id` remains required for `replace-row` and `remove-row`, not `add-row`; and `collection` remains outside every accepted operation envelope.

- **Reuse constants directly in parser validation.** Route each `_require_keys` call in `_parse_operation` through the matching shared constants. One way is to keep each operation’s required and optional fields as paired immutable values. Do not introduce a general schema engine or a second interpretation path: the constants exist to describe the parser’s current fixed contract.

- **Keep parser behavior unchanged.** This is a behavior-preserving refactor. Preserve operation dispatch, `_RELATIONLESS_ADD_ROW_TYPES` handling, row parsing through `_parse_stage_row`, replacement `row_id` matching, and the existing unknown-operation error.

- **Keep the constants safe to share.** Use immutable collection types, matching `_require_keys`’ existing immutable default pattern. The later batch-prompt work can import or render these parser-owned values, but this step must not edit `plan_tool/roadmap_candidate_context.py`, `plan_tool/roadmap_candidate_run.py`, or `plan_tool/prompts/roadmap-candidate-delta.md`.

- **Treat replay callers as unchanged consumers.** `plan_tool/roadmap_candidate_run.py:_normalize_operations` and `plan_tool/roadmap_candidate_review.py` replay operations through `parse_candidate_delta`; they already rely on the parser contract and need no local copy or edit for this refactor.

## Tests

### Tests for this step

- `test_candidate_operation_key_sets_match_the_strict_parser_envelopes` — build one valid minimal envelope for each supported operation from the shared key sets and assert `parse_candidate_delta` accepts all three shapes.
- `test_candidate_operation_key_sets_keep_add_row_without_row_id_or_collection` — assert the add-row constants exclude `row_id` and `collection`, and that either field still makes the strict parser reject the envelope.
- `test_candidate_operation_key_sets_keep_ordering_optional_only_where_supported` — assert `ordering` remains optional for add and remove operations and remains unavailable to replace operations.
- `test_candidate_key_validator_default_optional_keys_are_immutable` — retain the existing `_require_keys` default-immutability coverage.

Every listed test must be green before this step is complete.

## Acceptance criteria

- `plan_tool/roadmap_candidate.py:_parse_operation` uses module-level immutable key-set constants for all three supported operation types.
- The constants describe the same required and optional fields that `_parse_operation` accepted before this step.
- `add-row` still rejects `row_id` and `collection`.
- `replace-row` still requires `row_id` and does not accept `ordering`.
- `remove-row` still accepts optional `ordering`.
- `tests/test_roadmap_candidate.py` passes with focused tests proving the constants and parser agree.

## References

- [BUG_BACKLOG.md § “Candidate proposal retries still emit incompatible row-operation envelopes after the collection-vocabulary repair”](BUG_BACKLOG.md) — Read the fixed operation-field contract and the reason the parser must become the shared source.
- [ROADMAP_FEEDBACK_FORMAT.md](ROADMAP_FEEDBACK_FORMAT.md) — Read the ledger-to-candidate lifecycle that consumes candidate deltas.
- [ROADMAP_FORMAT.md](ROADMAP_FORMAT.md) — Read the immutable roadmap artifact and structural-route contract.
- [plan_tool/roadmap_candidate.py:parse_candidate_delta, _parse_operation, _require_keys](plan_tool/roadmap_candidate.py) — Read the strict candidate-delta wire contract this step preserves.
- [plan_tool/roadmap_candidate_context.py:candidate_collection_hints](plan_tool/roadmap_candidate_context.py) — Read the collection vocabulary surface that must remain separate from the operation envelope.
- [plan_tool/roadmap_candidate_run.py:render_candidate_delta_prompt, _run_batch_candidate_proposal](plan_tool/roadmap_candidate_run.py) — Read the later prompt and bounded-retry consumers of parser failures.

## Applicable guardrails

- **The plan’s “## Step intent”, parser and batch prompt share one source:** this step establishes parser-owned constants only; it must not create a second field vocabulary.
- **The plan’s “## Scope guardrails”, strict parser vocabulary:** the accepted key sets must remain exactly as they are today. The refactor must not coerce or discard unexpected fields.
- **The plan’s “## Out of scope”, model and persisted-state boundaries:** do not change capsule bytes, receipts, digests, replay keys, run-log records, retry bounds, selector behavior, or accepted-head publication.
- **The plan’s “## Out of scope”, decision `source`:** do not add `source` to the parser’s accepted decision-row fields in this step.

## Deferred

- Batch prompt rendering from the parser-owned operation constants — later plan work changes `plan_tool/roadmap_candidate_run.py` and `plan_tool/prompts/roadmap-candidate-delta.md`; those files are outside this step’s declared scope.
- Detailed missing-field, unknown-field, and invalid-row-type diagnostics — later plan work changes `_require_keys` and related parser error behavior; this refactor preserves the current diagnostic text.
- Collection-hint reshaping and stored-reply retry fixtures — later plan work owns `plan_tool/roadmap_candidate_context.py` and candidate-run coverage.
