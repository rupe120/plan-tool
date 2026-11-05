> **Auto-archived**: this plan was swept on 2026-11-05 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 6 — Prove malformed batch retries reach an inert structural candidate

<!-- plan-tool:detail-format-version: 1 -->

## Summary

Add focused batch-route integration coverage in `tests/test_roadmap_candidate_run.py` for malformed replies followed by a compliant retry. The tests exercise the existing `plan_tool/roadmap_candidate_run.py:_run_batch_candidate_proposal` loop with synthetic replies shaped like the stored malformed attempts. The key decision is to prove the already-owned parser, correction, receipt, and storage paths work together without changing production behavior. On green, each malformed first reply yields one complete correction and a valid second reply stores a structural candidate without moving the accepted head.

## Table of Contents

- [Summary](#summary) — States the test-only outcome and storage boundary.
- [Table of Contents](#table-of-contents) — Routes readers through this detail.
- [Why](#why) — Explains the missing end-to-end proof for corrected batch replies.
- [Input](#input) — Names the parser, retry, and storage contracts under test.
- [Files (creates vs edits)](#files-creates-vs-edits) — Lists the single scoped test edit.
- [Implementation](#implementation) — Defines the retry scenarios and invariants to prove.
- [Tests](#tests) — Names the focused cases and their assertions.
- [Verification (non-code step)](#verification-non-code-step) — Lists checks for this test-only step.
- [Acceptance criteria](#acceptance-criteria) — Gives reviewer-visible completion conditions.
- [References](#references) — Points to the candidate and roadmap contracts.
- [Applicable guardrails](#applicable-guardrails) — Applies the plan’s retry and identity boundaries.
- [Deferred](#deferred) — Separates parser and prompt ownership from this proof step.

## Why

`plan_tool/roadmap_candidate_run.py:_run_batch_candidate_proposal` already retries a rejected batch reply once, but the current coverage does not prove that both recorded malformed envelope shapes receive the complete diagnostic set from steps 3 and 5 and can then reach the existing inert structural-storage path. This proof matters because a parser diagnostic is only useful when it survives prompt correction, preserves the rejected-response receipt, and allows a compliant replacement to store without publishing a new accepted head.

## Input

- **Step 3 diagnostic contract:** Step 3 makes `plan_tool/roadmap_candidate.py:parse_candidate_delta` return complete closed-vocabulary diagnostics for malformed operations and eligible row bodies. This step treats those diagnostics as retry text and does not redefine parser behavior.

- **Step 5 hint contract:** Step 5 changes `plan_tool/roadmap_candidate_context.py:candidate_collection_hints` so discovery records do not look like writable operations. Exercise the batch route after that shape lands; do not re-test the context renderer directly here.

- **Existing batch retry and storage path:** `plan_tool/roadmap_candidate_run.py:_run_batch_candidate_proposal`, `record_candidate_failure_diagnostics`, and `_store_batch_candidate` own the two-attempt loop, failure receipt, and immutable candidate publication. Keep their interfaces and lifecycle rules unchanged.

- **Existing fixtures and assertions:** Reuse the batch fixtures and candidate-stack helpers already in `tests/test_roadmap_candidate_run.py`, including `_seed_batch_ledger`, `_FIRST_BATCH_DELTA`, `_only_run_log`, and `roadmap_candidate_review.build_candidate_stack_view`, where they fit the new cases.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `tests/test_roadmap_candidate_run.py` — add batch-route cases for each malformed stored-reply shape, its complete correction, and successful inert structural-candidate storage after the compliant retry.

## Implementation

- **Prove both malformed reply shapes through the real batch loop.** Add focused cases near the existing ledger-batch retry coverage in `tests/test_roadmap_candidate_run.py`. Feed a malformed first response and a compliant second response through `plan_tool/roadmap_candidate_run.py:run_initial_candidate_proposal`, rather than calling `parse_candidate_delta` directly.

- **Cover the complete correction surface.** One malformed reply must include operation-envelope defects that steps 1 and 3 can safely name. The other must include the known class-name `row_type` diagnosis path and the unsupported `decisions` `source` field. Assert the second prompt contains every expected closed-vocabulary diagnostic from the first reply, not only the first error.

- **Keep the response boundary strict.** The malformed first reply must remain rejected exactly as received. Do not make the test accept, repair, or normalize it before the retry; the compliant replacement is the only input that may reach `materialize_candidate`.

- **Use the existing bounded retry behavior.** Assert exactly two model calls occur: one rejected attempt and one successful replacement. Do not add a third-attempt scenario or alter the shared loop’s retry budget.

- **Prove the result is inert and structural.** The stored result must contain a candidate whose operation classification is structural, while `plan_tool/roadmap_versions.py:accepted_head_path` and `load_accepted_version` still identify the original accepted roadmap. Use the existing candidate-stack view only to confirm the stored candidate remains reviewable rather than promoted.

- **Preserve failure evidence.** Inspect the run-log `parse_failure` event and its referenced receipt through `tests/test_roadmap_candidate_run.py:_only_run_log`. Assert it records attempt 1 and retains the exact malformed response bytes; the successful retry must not erase or replace that receipt.

- **Reuse shared production owners unchanged.** `plan_tool/roadmap_candidate.py:parse_candidate_delta`, `plan_tool/roadmap_candidate_run.py:_run_batch_candidate_proposal`, and `plan_tool/roadmap_candidate_run.py:record_candidate_failure_diagnostics` already provide the needed semantics. This step adds no local test helper that copies their parser, correction, or receipt logic.

## Tests

- `test_malformed_batch_operation_envelope_correction_reaches_inert_structural_candidate` — asserts a malformed operation envelope produces one complete correction, then a compliant second reply stores a structural candidate after two calls without moving the accepted head.

- `test_malformed_batch_decision_source_correction_reaches_inert_structural_candidate` — asserts a malformed `decisions` row that includes the unsupported `source` field receives the closed diagnostic with its other eligible defects, then a compliant retry stores the inert structural candidate.

- `test_malformed_batch_retry_preserves_first_response_receipt_after_storage` — asserts the attempt-one `parse_failure` event points to bytes equal to the rejected reply after the second attempt succeeds.

- `test_malformed_batch_retry_does_not_publish_accepted_head` — asserts the accepted-head bytes and loaded accepted version remain unchanged while the retried candidate is available through the existing review-stack surface.

## Verification (non-code step)

1. Run the focused cases in `tests/test_roadmap_candidate_run.py`.
2. Run the candidate-run test module to confirm existing selector and exhausted-retry coverage still passes.
3. Confirm the new assertions use real batch invocation, run-log receipt reading, and accepted-head loading rather than private parser copies.

## Acceptance criteria

- A malformed batch operation-envelope reply receives one correction that names every eligible closed-vocabulary defect asserted by the test.

- A malformed batch reply containing the unsupported `decisions` `source` field receives a correction that names that field without accepting it.

- Each compliant second reply produces `outcome == "stored"` with `call_count == 2`.

- Each stored retried candidate has structural operation classification and is available to the existing candidate-review stack.

- The accepted-head bytes and accepted roadmap version remain unchanged after each successful retried proposal.

- The run log retains an attempt-one `parse_failure` receipt whose file contains the exact rejected response bytes.

- `tests/test_roadmap_candidate_run.py` passes.

## References

- [BUG_BACKLOG.md — Candidate proposal retries still emit incompatible row-operation envelopes after the collection-vocabulary repair](BUG_BACKLOG.md) — Read the source issue and the intended retry outcome.

- [ROADMAP_FEEDBACK_FORMAT.md — ledger-to-candidate lifecycle](ROADMAP_FEEDBACK_FORMAT.md) — Read the batch feedback and candidate lifecycle boundaries.

- [ROADMAP_FORMAT.md — immutable artifact and structural route contract](ROADMAP_FORMAT.md) — Read the structural candidate and accepted-head rules.

- [plan_tool/roadmap_candidate.py — strict candidate-delta parser](plan_tool/roadmap_candidate.py) — Read `parse_candidate_delta`, `_parse_operation`, and `_parse_stage_row` for the rejection contract exercised here.

- [plan_tool/roadmap_candidate_run.py — batch retry, diagnostics, and storage](plan_tool/roadmap_candidate_run.py) — Read `_run_batch_candidate_proposal`, `record_candidate_failure_diagnostics`, and `_store_batch_candidate` for the lifecycle under test.

## Applicable guardrails

- **The plan’s “## Step intent”, malformed-reply proof boundary:** Limit this step to synthetic replies shaped like the recorded attempts and their correction-to-storage proof.

- **The plan’s “## Scope guardrails”, strict parser boundary:** Do not broaden accepted candidate-delta fields or make class-name schema selection into input acceptance.

- **The plan’s “## Scope guardrails”, identity and storage boundary:** Keep issued capsule, receipt, digest, replay, and accepted-head behavior unchanged; assert those boundaries through the existing run path.

- **The plan’s “## Out of scope”, retry and receipt lifecycle boundary:** Do not change retry count, run-log schema, rejected-byte retention, or candidate publication behavior while adding coverage.

## Deferred

- Parser aggregation and safe diagnostic wording — Steps 1 through 3 own the parser and diagnostic contract; this step only proves the landed behavior reaches the retry prompt.

- Batch prompt and collection-hint design — Steps 4 and 5 own model-facing operation shapes and discovery-record separation; this step exercises their result without editing those surfaces.
