# Step 2 — Retry rejected ledger replies once; preserve one candidate publication, guarded pointer and ledger replacements, and exact response receipts

<!-- plan-tool:detail-format-version: 1 -->

## Summary

Retry one rejected ledger-batch reply with correction feedback before returning `response-rejected`. Update `plan_tool/roadmap_candidate_run.py` and its focused tests in `tests/test_roadmap_candidate_run.py`. Keep the issued batch capsule, receipt, pointer guard, and ledger snapshot fixed across both attempts; only a validated second reply can reach the existing storage path. Green behavior makes at most two model calls, publishes at most one candidate, and retains exact rejected response bytes as attempt-specific receipts.

## Table of Contents

- [Summary](#summary) — Reviewer overview of the retry boundary and stored-result rules.
- [Table of Contents](#table-of-contents) — Links to each section in this detail file.
- [Why](#why) — The current one-reply rejection behavior and its missing correction path.
- [Input](#input) — Immutable batch and mutable storage contracts this step reads.
- [Files (creates vs edits)](#files-creates-vs-edits) — Declared file changes.
- [Implementation](#implementation) — Bounded retry, publication, guard, and receipt requirements.
- [Tests](#tests) — Focused behavior and failure-boundary coverage.
- [Acceptance criteria](#acceptance-criteria) — Observable completion conditions.
- [References](#references) — Ledger and immutable-roadmap contracts to consult.
- [Applicable guardrails](#applicable-guardrails) — Plan boundaries that constrain this change.

## Why

`plan_tool/roadmap_candidate_run.py:_run_batch_candidate_proposal` rejects the first malformed or unmaterializable ledger reply immediately, even when the model can correct the reported issue using the vocabulary supplied by step 1. The batch must allow one bounded correction without widening reviewer authority, rebuilding the batch from changed mutable input, or making a rejected reply look like a storage failure.

## Input

- **Step 1 output:** Step 1 makes valid collection vocabulary visible in every batch prompt, including stored-candidate review. This step alone owns the ledger proposal's correction loop and uses that prompt contract on both attempts.
- **Fixed batch authority:** Read `plan_tool/roadmap_candidate_context.py:CandidateContextBatchCapsule`, its receipt, and `plan_tool/roadmap_candidate_run.py:render_candidate_delta_prompt`. The same issued capsule and receipt must ground both calls.
- **Reply acceptance boundary:** Use `plan_tool/roadmap_candidate.py:parse_candidate_delta` and `plan_tool/roadmap_candidate.py:materialize_candidate` as the distinction between a retryable rejected reply and an accepted reply ready for storage.
- **Publication boundary:** Retain `plan_tool/roadmap_candidate_run.py:_store_batch_candidate` and `require_batch_state_unchanged` as the sole path that replaces the active-candidate pointer and ledger bytes.

## Files (creates vs edits)

- **New files:** None.

- **Existing files (edits only):**
  - `plan_tool/roadmap_candidate_run.py` — Add the ledger-only two-attempt correction flow, preserve exact rejected-response diagnostics per attempt, and retain the current guarded single-publication path.
  - `tests/test_roadmap_candidate_run.py` — Cover corrected success, exhausted rejection, receipt fidelity, and non-retry failure boundaries.

## Implementation

- **Retry only rejected ledger content.** Extend `plan_tool/roadmap_candidate_run.py:_run_batch_candidate_proposal` so an error from `parse_candidate_delta` or a refusal from `materialize_candidate` receives one correction attempt. Keep the selector-era route in `run_initial_candidate_proposal` unchanged.

- **Use one shared budget of two calls.** A first rejected reply consumes attempt 1; its correction call is attempt 2. A rejected second reply returns `response-rejected` with `call_count == 2`. Do not add a configurable retry policy or additional attempt classes.

- **Keep authority fixed between attempts.** Reuse the original `CandidateContextBatchCapsule`, `capsule.receipt`, root, source, admission, and admitted ledger snapshot. The correction prompt may include the self-contained rejection reason, but it must not rebuild context, re-read eligibility, or grant authority beyond the first prompt.

- **Keep rejection feedback narrow and actionable.** Extend `render_candidate_delta_prompt` or add a nearby prompt-rendering helper so the second prompt clearly identifies the failed response contract and asks for one replacement JSON response. Do not include a mutable ledger view, repository content, or a new prompt template.

- **Preserve exact rejected responses.** Record attempt 1's rejection and best-effort exact response receipt before calling the model again. Record attempt 2's rejection and receipt on exhaustion; the terminal summary names attempt 2 and call count 2 without recording its receipt twice. Update diagnostic state around `CandidateModelInvocation`, `_ProposalAttempt`, and `record_candidate_failure_diagnostics` so each attempt has its own number, original response bytes, digest, and redacted reason. A successful corrected second reply must not erase the first rejection record. If attempt 2 fails during transport, the first rejection remains visible while the terminal outcome stays `failed`.

- **Publish at most once.** Run `_store_batch_candidate` only after one reply has parsed and materialized successfully. A corrected reply may produce one inert candidate through the existing `publish_roadmap_generation` path; a twice-rejected run must not create candidate members, supersession records, pointer changes, or ledger lifecycle updates.

- **Retain storage classification and guards.** Once a reply is accepted, preserve `diagnostics.response_accepted` and the existing distinction between `CandidateStorageRefusal` (`refused`) and storage errors (`failed`). Do not retry transport failures, writer-guard failures, ledger-read failures, pointer changes, admitted-item changes, or failures from `_store_batch_candidate`.

- **Keep pointer and ledger replacement checks in place.** `_store_batch_candidate`, `_apply_batch_ledger_patch`, and `require_batch_state_unchanged` must continue to compare the recorded active-candidate admission and ledger bytes before publication. The retry loop must not weaken those checks or replace unrelated reviewer edits.

## Tests

### Tests for this step

- `test_rejected_batch_reply_is_corrected_once_and_stores_one_candidate` — A malformed first ledger reply and valid second reply make two calls, include the rejection reason in the second prompt, and store exactly one candidate.
- `test_rejected_batch_reply_reuses_the_issued_capsule_and_receipt_for_correction` — Both prompts retain the same issued batch authority and receipt rather than rebuilding context between attempts.
- `test_two_rejected_batch_replies_exhaust_the_shared_budget_without_publication` — Two malformed replies return `response-rejected`, report two calls, and leave candidate storage, the active pointer, and ledger bytes unchanged.
- `test_each_rejected_batch_reply_has_an_exact_attempt_numbered_receipt` — Exhaustion writes one receipt per rejected response before any next call, with original bytes, digest, reason, and attempt number, without duplicate final receipt or raw response text in the run log.
- `test_corrected_batch_reply_keeps_the_first_rejection_receipt` — A successful second reply still leaves the first rejected reply’s exact receipt available for diagnosis.
- `test_batch_transport_failure_is_not_retried_or_recorded_as_response_rejection` — A nonzero invoker result remains `failed` after one call and does not enter the correction path.
- `test_transport_failure_after_a_rejected_reply_preserves_first_receipt` — A failed correction transport keeps the first rejection record and ends as `failed` after two calls.
- `test_batch_storage_failure_after_a_corrected_reply_is_not_retried_or_recorded_as_a_parse_failure` — A valid corrected reply followed by storage failure remains `failed`, makes no third call, and does not misclassify accepted content as rejected.
- `test_corrected_batch_publication_still_refuses_changed_pointer_or_ledger` — A mutable-state change before storage retains the existing refusal behavior and does not overwrite the newer pointer or ledger state.

Every listed test must be green before this step is complete.

## Acceptance criteria

- A ledger-batch reply rejected by parsing or materialization receives exactly one correction call using the original issued batch authority.
- A valid corrected reply stores one inert candidate and reports `call_count == 2`.
- Two rejected ledger replies return `response-rejected`, report `call_count == 2`, and publish no candidate or mutable lifecycle update.
- Each rejected ledger reply has one attempt-specific, best-effort receipt whose bytes and SHA-256 digest match the original model response; attempt 1 is recorded before correction, and exhaustion does not duplicate attempt 2's receipt.
- Run logs contain receipt metadata and rejection reasons but not raw model response content.
- A transport failure, writer or storage failure, or storage refusal does not consume the correction retry or become `response-rejected`.
- `plan_tool/roadmap_candidate_run.py:_store_batch_candidate` remains the only publication path and retains its pointer and ledger byte checks.
- `tests/test_roadmap_candidate_run.py` passes.

## References

- [ROADMAP_FEEDBACK_FORMAT.md — ledger ownership, candidate lifecycle, and non-publication outcomes](../../../../ROADMAP_FEEDBACK_FORMAT.md)
- [ROADMAP_FORMAT.md — immutable candidate authority and accepted-head boundary](../../../../ROADMAP_FORMAT.md)
- [plan_tool/roadmap_candidate_run.py — batch invocation, candidate storage, and response diagnostics](../../../../plan_tool/roadmap_candidate_run.py)
- [tests/test_roadmap_candidate_run.py — existing batch, storage-guard, and receipt coverage](../../../../tests/test_roadmap_candidate_run.py)

## Applicable guardrails

- **The plan’s “## Plan intent”, candidate publication boundary:** This step may correct a rejected ordinary ledger reply, but it must retain inert candidate publication and must not alter approval behavior.
- **The plan’s “## Step intent”, bounded correction:** This step must stop after one correction opportunity and leave exhausted replies unpublished.
- **The plan’s “## Scope guardrails”, response classification:** This step must preserve the difference between rejected model content and transport or storage failures.
- **The plan’s “## Scope guardrails”, immutable evidence and authority:** This step must not change capsule payload bytes, receipt or digest identities, replay keys, or reviewer authority.
- **The plan’s “## Out of scope”, lifecycle and parser boundaries:** This step must not migrate persisted evidence, make parsing permissive, alter selector-era proposal behavior, or change accepted-head publication and structural decisions.
