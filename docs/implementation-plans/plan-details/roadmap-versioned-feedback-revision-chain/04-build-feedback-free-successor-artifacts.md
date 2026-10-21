# Step 4 — Build feedback-free successor artifacts, a response patch, and a fresh roadmap-derived feedback set

<!-- plan-tool:detail-format-version: 1 -->

## Summary

Update `plan_tool/roadmap_candidate.py` so one closed model response can produce feedback-free successor artifacts, a bounded patch for the admitted reviewer items, and a newly derived feedback set for the successor revision. Update `plan_tool/prompts/roadmap-candidate-delta.md` to request that complete response contract, and extend `tests/test_roadmap_candidate.py` around its validation and materialization. The key decision is that derived feedback is regenerated for the successor rather than copied from its source, while reviewer-owned state remains outside immutable artifacts. On green, a valid batch produces inert candidate material ready for step 5 to store atomically.

## Table of Contents

- [Summary](#summary) — The completed candidate-materialization outcome.
- [Table of Contents](#table-of-contents) — Links to each section.
- [Why](#why) — Why the current single embedded-feedback delta cannot form a revision-chain successor.
- [Input](#input) — Contracts supplied by step 3 and existing candidate assembly.
- [Files (creates vs edits)](#files-creates-vs-edits) — The production, prompt, and test footprint.
- [Implementation](#implementation) — Closed response validation, feedback-free artifacts, response patches, and derived feedback.
- [Tests](#tests) — Focused contract coverage for successful and refused materialization.
- [Acceptance criteria](#acceptance-criteria) — Observable completion conditions.
- [References](#references) — Immutable-record and canonical-byte references.
- [Applicable guardrails](#applicable-guardrails) — Boundaries on candidate and ledger authority.
- [Deferred](#deferred) — Storage and lifecycle work owned by later steps.

## Why

`plan_tool/roadmap_candidate.py:materialize_candidate` currently authorizes operations against one `CandidateContextFeedback` item and returns artifacts that retain the predecessor’s artifact shape. Step 3 instead supplies an ordered root/source-bound batch, so candidate assembly needs to validate the whole model reply against that immutable batch, keep reviewer state out of successor artifacts, and return the exact material step 5 needs without writing mutable or canonical state.

## Input

- **Step 3 batch contract:** Consume step 3’s exact root/source binding, ordered admitted reviewer-item snapshots, current derived context, and immutable receipt. The landed step 3 names and record shapes win over this detail.
- **Candidate assembly:** Extend `plan_tool/roadmap_candidate.py:CandidateDelta`, `parse_candidate_delta`, `materialize_candidate`, `_verify_bindings`, `_prepare_operations`, `_assemble_candidate_artifacts`, and the candidate result records rather than creating a second materialization path.
- **Artifact contract:** Use `plan_tool/roadmap_artifacts.py:REVIEW_ROW_KEYS` and the stage parser/renderer methods exposed through `plan_tool/roadmap.py:STAGES` to prove successor artifact bytes contain design content only.
- **Gate contract:** Keep `plan_tool/roadmap_impact_snapshot.py:check_complete_roadmap_gates` as the final deterministic artifact check. This step consumes its result; it must not change gate authority or stage operations.

## Files (creates vs edits)

- **New files:**
  - `plan_tool/prompts/roadmap-candidate-delta-selector.md` — The selector-era template, kept byte-for-byte for the ledger-less route.

- **Existing files (edits only):**
  - `plan_tool/roadmap_candidate.py` — Replace the single-feedback delta outcome with a closed batch-aware response contract; materialize feedback-free artifacts, an admitted-item response patch, and a fresh derived set.
  - `plan_tool/prompts/roadmap-candidate-delta.md` — Describe the closed batch response shape and prohibit artifact feedback, unadmitted responses, and carried-forward derived entries.
  - `tests/test_roadmap_candidate.py` — Replace single-feedback fixtures where necessary and add focused batch, artifact, patch, derived-set, and refusal coverage.

## Implementation

- **Accept one complete closed response.** Extend `CandidateDelta` and `parse_candidate_delta` into the closed response boundary for the artifact delta, reviewer-response patch, and fresh derived-feedback set. Reject duplicate keys, trailing content, unknown fields, partial patches, and malformed typed values before assembly.

- **Bind every model-authored response to the issued batch.** Make `materialize_candidate` validate the supplied batch receipt and root/source identities before it accepts operations or responses. Every response patch entry must match exactly one admitted reviewer snapshot, and every admitted reviewer item must receive exactly one response. Reject omitted, duplicated, substituted, or unadmitted items.

- **Keep reviewer state outside successor artifacts.** Continue using `_apply_operation` and `_assemble_candidate_artifacts` for typed roadmap changes, but project every assembled `CandidateArtifact` through the feedback-free artifact contract before rendering. A successor artifact must not render `feedback`, `removals`, a proposed response, or any reviewer lifecycle state.

- **Return a patch, not a ledger mutation.** Return an immutable, bounded response-patch result that identifies each admitted item and its model response. It represents the later `open` to `awaiting-review` transition, but this step must not mutate a ledger or invent the stored candidate revision id; step 5 attaches that provenance during guarded storage.

- **Regenerate derived feedback from the successor.** Validate and return one complete fresh ordinary roadmap-derived set for the candidate revision. Do not copy, match, warn about, or retain prior-source derived entries in the new set; prior derived context remains only batch evidence. Derived entries are context for the model response, not reviewer-item response-patch targets.

- **Preserve existing candidate safety checks.** Keep the normalized-operation authority checks in `_validate_operation_authority`, relation-impact handling in `_validate_relation_authority`, render/reparse verification, stable artifact ordering from `STAGES`, and complete-gate validation. A refusal must expose no partial candidate, response patch, or fresh derived set.

- **Keep identities deterministic.** Update `_content_identity` and any review-required evidence built by `_build_review_requirement` so they bind the complete batch-aware response material that step 5 will persist. Equivalent response ordering must produce the same normalized result and identity; a changed admitted response or derived entry must change it. The identity binds that material only for a candidate that carries a response patch: a selector-era candidate is stored with no patch, and its identity is recomputed from its stored bytes on every later review, replacement, and promotion, so it must equal the value minted before the batch route existed.

- **Make the prompt self-contained.** In `plan_tool/prompts/roadmap-candidate-delta.md`, replace the single `${feedback_id}` instruction with the issued batch as authority. Require the exact response shape inline, preserve the existing “do not inspect the repository” boundary, and ensure every `${...}` placeholder has a supplied caller value. Do not point the prompt at repository documentation.

- **Keep the selector-era prompt beside it.** The ledger-less selector route still parses its response with the selector branch of `parse_candidate_proposal_response`, which accepts exactly one `delta` or `expand` disposition. `render_candidate_delta_prompt` therefore renders `roadmap-candidate-delta.md` for a `CandidateContextBatchCapsule` and `roadmap-candidate-delta-selector.md` for any other capsule. The selector template keeps the selected `${feedback_id}` instruction and the `delta` and `expand` dispositions, and its variables are the same four the renderer supplies. Every caller — the initial proposal, both expansion calls, and the replacement request — reaches the prompt through that one renderer.

## Tests

- `test_candidate_materializes_feedback_free_successor_artifacts` — asserts changed artifacts reparse and render without keys named by `REVIEW_ROW_KEYS`.
- `test_candidate_preserves_unchanged_feedback_free_artifact_bytes` — asserts an unchanged source member retains its verified bytes when those bytes already satisfy the feedback-free contract.
- `test_candidate_response_patch_covers_each_admitted_item_exactly_once` — asserts every ordered admitted reviewer snapshot has one and only one bounded response.
- `test_candidate_response_patch_rejects_omitted_duplicate_or_unadmitted_item` — asserts incomplete, repeated, and substituted responses refuse without candidate material.
- `test_candidate_response_patch_binds_item_snapshot_not_live_ledger_state` — asserts the patch uses the batch snapshot and cannot authorize a changed request, target, or fingerprint.
- `test_candidate_response_patch_does_not_mutate_reviewer_state` — asserts materialization returns a patch only and does not apply an `awaiting-review` transition or candidate provenance.
- `test_candidate_derived_set_is_fresh_not_carried_from_source` — asserts successor derived feedback comes only from the response and does not retain source entries by default.
- `test_candidate_derived_set_accepts_empty_complete_set` — asserts a valid response may produce an empty fresh derived set.
- `test_candidate_derived_set_rejects_malformed_or_duplicate_entries` — asserts invalid derived feedback refuses before candidate material is returned.
- `test_candidate_identity_binds_response_patch_and_fresh_derived_set` — asserts either material change changes candidate identity while equivalent ordering does not.
- `test_candidate_refusal_exposes_no_partial_patch_or_derived_set` — asserts binding, authority, rendering, or gate failure returns only a refusal.
- `test_candidate_prompt_names_the_complete_batch_response_contract` — asserts `plan_tool/prompts/roadmap-candidate-delta.md` contains the closed response vocabulary and no stale single-item instruction.
- `test_selector_era_prompt_requests_the_delta_or_expand_shape_its_parser_accepts`, `test_batch_prompt_requests_the_unwrapped_batch_shape_and_offers_no_expansion`, and the four `..._stores_when_the_model_answers_the_shape_its_prompt_asks_for` tests (selector and batch proposal, selector and batch replacement) — assert each capsule type is prompted for the shape its parser accepts, using a stand-in model that answers whatever shape its prompt requests.
- `test_candidate_prompt_placeholders_are_supplied_by_its_rendering_contract` — asserts the template has no unresolved placeholders when rendered by its existing caller contract.
- `test_roadmap_candidate_contract` — runs every changed case in `tests/test_roadmap_candidate.py` green before this step is complete.

## Acceptance criteria

- A valid model response returns feedback-free successor artifacts, a response patch for every admitted reviewer item, and one fresh revision-bound derived-feedback set.
- No successor artifact renders mutable feedback or reviewer lifecycle collections.
- The response patch covers all and only the admitted batch snapshots exactly once.
- Candidate materialization does not mutate the ledger, active-candidate pointer, accepted head, or reviewer item state.
- The response patch contains no invented candidate revision id; guarded storage supplies that provenance in step 5.
- A successor derived set does not carry forward, match, or warn about source-derived entries.
- Existing typed-operation authority, relation authority, render/reparse, stage ordering, and complete roadmap-gate checks remain required.
- A selector-era candidate is prompted for the `delta` or `expand` shape its parser accepts, and a batch candidate for the unwrapped batch shape; neither route can be answered with the other's shape.
- Invalid batch bindings, invalid response-patch coverage, malformed derived feedback, or failed gates return a refusal with no partial material.
- `tests/test_roadmap_candidate.py` passes.

## References

- [Models — Pydantic Documentation](https://docs.pydantic.dev/latest/concepts/models/) — Read strict, frozen model configuration for closed response and result records.
- [json — JSON Encoder and Decoder](https://docs.python.org/3.13/library/json.html) — Read JSON decoding and stable serialization behavior for the closed response boundary.
- [RFC 8785: JSON Canonicalization Scheme](https://www.rfc-editor.org/rfc/rfc8785.html) — Use as the reference for reproducible candidate identity inputs.
- [hashlib — Secure Hashes and Message Digests](https://docs.python.org/3.13/library/hashlib.html) — Read SHA-256 behavior for immutable candidate evidence.

## Applicable guardrails

- **The plan’s “## Scope guardrails”, mutable ledger authority:** This step must return a ledger patch as inert material and must not make reviewer feedback part of immutable artifacts.
- **The plan’s “## Scope guardrails”, exact candidate evidence:** This step must bind operations, responses, and derived feedback to the issued root/source batch without using later mutable input.
- **The plan’s “## Scope guardrails”, unrelated ledger edits:** This step must limit the response patch to admitted items and must not consume unrelated reviewer items.
- **The plan’s “## Out of scope”, candidate and stage authority:** This step must not add candidate branches, change roadmap gates or stage operations, or create a general review protocol.

## Deferred

- Candidate storage, ledger transition, candidate-revision provenance, and active-pointer publication — step 5 owns the guarded atomic write.
- Reviewer edits, legacy migration, and ledger persistence — step 6 owns mutable-ledger operations.
- Review questions, rejection, discard, and sealed replacement behavior — step 8 owns the focused candidate-review lifecycle.
