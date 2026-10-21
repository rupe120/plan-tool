# Step 1 — Replace scattered step-number deferral metadata with shared accounting helpers

## Summary

This step moves the current concept ownership and detail-deferral bookkeeping into shared, write-free helpers in `plan_tool/concept_tree.py`. `plan_tool/detail.py`, `plan_tool/review.py`, and `plan_tool/scope_out.py` will delegate to those helpers while keeping their existing persistence, rollback, and command behavior. The key design choice is to centralize copying, parsing, transformation, and validation without centralizing publication. On green, the same metadata is produced and accepted in the same order, but each accounting rule has one implementation.

## Table of Contents

- [Summary](#summary) — Overview of the shared accounting refactor and its result.
- [Why](#why) — Why the duplicated ownership and deferral rules need one home.
- [Input](#input) — Existing metadata and plan fields whose behavior must remain unchanged.
- [Files (creates vs edits)](#files-creates-vs-edits) — Production and test files changed by this step.
- [Implementation](#implementation) — Required helper boundaries, caller updates, and preserved invariants.
- [Tests](#tests) — Characterization and delegation coverage for every affected flow.
- [Acceptance criteria](#acceptance-criteria) — Observable checks for a behavior-preserving result.
- [References](#references) — Test guidance directly relevant to the refactor.
- [Deferred](#deferred) — Later schema and publication work excluded from this step.

## Why

Concept-to-step accounting is currently re-derived in several forms: `plan_tool/detail.py:_concept_deferral_step_ids` parses `detail_deferral_step_ids`, `plan_tool/detail.py:_replace_detail_deferrals` rewrites it, `plan_tool/review.py:_structured_concept_deferral_is_valid` parses and validates it again, and `plan_tool/scope_out.py:ownerless_carved_concept_ids` separately determines whether ownership survives a carve. These copies agree today only because their tests cover overlapping cases. Centralizing the pure rules now gives the durable accounting work in later steps one replacement point while protecting the different publication rules already owned by detail generation, concept synchronization, and scope-out.

## Input

- **Persisted metadata:** `plan_tool/concept_tree.py:ConceptNode.source_metadata` may contain `detail_deferral_step_ids`, encoded as a compact JSON list of positive integer step IDs. Missing, empty, malformed, boolean, non-list, and non-positive values currently act as no usable links.
- **Delivery ownership:** `plan_tool/schema.py:Step.concept_ids` carries exact stable concept IDs. Only owners whose `Step.scope` is `StepScope.COMMITTED` count as surviving delivery ownership in the affected checks.
- **Detail replacements:** `plan_tool/detail.py:DetailDeferral` supplies a concept ID and step ID only after a detail response has passed validation and its detail file has been written successfully.
- **Scope-out snapshots:** `plan_tool/scope_out.py:NarrowPreview.new_steps` is the prepared survivor set used by `plan_tool/scope_out.py:ownerless_carved_concept_ids`; parked survivors do not count as committed owners.
- **Compatibility limit:** This refactor must continue reading and writing the existing `source_metadata` key. It does not add a persisted field, change `CONCEPTS_SCHEMA_VERSION`, or migrate existing sidecars.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `plan_tool/concept_tree.py` — add shared, pure helpers for parsing deferral step IDs, replacing whole-step deferral links, checking whether a structured link points to a valid owner or plan step, and finding concept IDs that lose their final committed owner.
  - `plan_tool/detail.py` — replace local metadata parsing and replacement logic with calls to the shared helpers while retaining detail-write ordering and the sole `save_concepts` call.
  - `plan_tool/review.py` — make `_structured_concept_deferral_is_valid` delegate its metadata parsing and link checks to the shared accounting helpers without changing finding behavior.
  - `plan_tool/scope_out.py` — make `ownerless_carved_concept_ids` delegate ownership accounting to the shared helper while retaining `_prepare_concept_narrow_update`, `apply_narrow`, stale checks, journaling, and rollback.
  - `tests/test_concept_tree.py` — add direct unit coverage for the shared pure accounting rules.
  - `tests/test_detail.py` — preserve and strengthen characterization of ordered whole-step replacement and save-after-detail behavior.
  - `tests/test_review.py` — preserve coverage decisions for valid, malformed, dangling, and owner-mismatched links.
  - `tests/test_scope_out.py` — preserve sole-owner, shared-owner, parked-owner, ordering, no-write, stale-state, and rollback behavior.

## Implementation

The foundational logic is: **parse and transform exact concept ownership and deferral links without writing, while preserving deterministic whole-step accounting.**

- **Put the pure rules in `plan_tool/concept_tree.py`.** This module owns `ConceptNode`, `ConceptTree`, and validation of their persisted shape, so it is the natural shared boundary for the current metadata-backed accounting. Use clear public names such as `concept_deferral_step_ids`, `replace_detail_deferrals`, and `concept_ids_without_committed_owner`; the exact names may vary, but callers should no longer decode or rewrite `detail_deferral_step_ids` themselves.

- **Keep the helper inputs independent of orchestrator types.** In particular, do not make `plan_tool/concept_tree.py` import `plan_tool/detail.py:DetailDeferral`, `plan_tool/scope_out.py:NarrowPreview`, or review recommendation types. One workable shape is to pass normalized `(step_id, concept_ids)` replacements and sets or sequences of committed owner IDs. This keeps the shared layer usable by all three callers without a reverse import.

- **Make candidate preparation write-free.** Shared helpers may copy, normalize, validate, and return a candidate `ConceptTree`; they must not call `save_concepts`, `write_plan`, or any publisher. Return a deep copy when applying replacements so an invalid or abandoned candidate cannot mutate the caller’s original snapshot.

- **Preserve tolerant metadata reads.** The shared parser must keep the behavior of `plan_tool/detail.py:_concept_deferral_step_ids`: return no links for absent or malformed metadata; accept only a JSON list of positive, non-boolean integers; remove duplicate IDs while preserving first occurrence order.

- **Preserve whole-step replacement order.** The shared replacement helper must:
  - process affected steps in deterministic step order;
  - remove each affected step’s old links from every concept before adding that step’s replacements;
  - keep only the successfully supplied replacements;
  - retain unrelated `ConceptNode.source_metadata`;
  - retain the order of existing unrelated step IDs;
  - encode non-empty lists with compact JSON separators; and
  - delete `detail_deferral_step_ids` instead of storing an empty list.

- **Adapt `plan_tool/detail.py:_replace_detail_deferrals` at the boundary.** It may remain as a compatibility wrapper if tests or nearby code benefit from that symbol, but the accounting work should live in `plan_tool/concept_tree.py`. Convert `DetailDeferral` results to the shared helper’s neutral input only after `generate_detail` has established which detail writes succeeded.

- **Keep detail publication where it is.** The consolidated candidate must still be built in the serial tail of `plan_tool/detail.py:generate_detail`, after serial or `_generate_detail_concurrent` authoring finishes. Preserve the rule that failed or skipped detail writes do not replace links, successful results are processed in step order, and `save_concepts` is called once with the complete candidate.

- **Share structured-link validation with `plan_tool/review.py`.** Replace the JSON parsing inside `_structured_concept_deferral_is_valid` with the shared parser and validity predicate. Preserve the current rule: the node must represent a `defer` decision, at least one parsed step ID must exist in the plan, and if the concept has explicit owners, at least one valid link must name one of those owners.

- **Do not change completeness policy.** `plan_tool/review.py:check_concept_coverage` must continue treating an exact committed owner or a currently valid structured detail deferral as coverage. Its handling of approved `wont_do`, unsigned decisions, finding IDs, severity, and collector membership remains unchanged in this refactor; later plan steps change those semantics.

- **Share final-owner accounting with `plan_tool/scope_out.py`.** Move the set-based rule behind `ownerless_carved_concept_ids` into `plan_tool/concept_tree.py`, while keeping the existing `plan_tool/scope_out.py` symbol as a thin compatibility wrapper if useful. Preserve first-authored concept order, deterministic deduplication, many-owner support, and the rule that only committed surviving steps prevent ownerless treatment.

- **Keep scope-out publication local.** `plan_tool/scope_out.py:_prepare_concept_narrow_update` must still load and snapshot the original sidecar, call `plan_tool/concept_review.py:review_concept_scope` for ownerless concepts, and return both original and reviewed state. `plan_tool/scope_out.py:apply_narrow` must retain its compare-and-swap checks, plan-last write order, concept fingerprint refresh, journal rollback, and original sidecar restoration.

- **Reject a shared publisher in this step.** `plan_tool/detail.py:generate_detail`, `plan_tool/concept_sync.py:synchronize_concepts`, and `plan_tool/scope_out.py:apply_narrow` use different publication protocols. Sharing their write operations would change failure behavior and turn this refactor into a feature change.

## Tests

- `test_concept_deferral_step_ids_normalizes_valid_metadata` in `tests/test_concept_tree.py` — accepts positive integer IDs, removes duplicates, and preserves first occurrence order.
- `test_concept_deferral_step_ids_rejects_malformed_metadata` in `tests/test_concept_tree.py` — returns no links for missing, invalid JSON, non-list, boolean, zero, negative, or mixed-type values.
- `test_replace_detail_deferrals_is_copy_only_and_preserves_unrelated_metadata` in `tests/test_concept_tree.py` — returns a changed candidate without mutating the source tree or unrelated metadata.
- `test_replace_detail_deferrals_replaces_whole_steps_in_order` in `tests/test_concept_tree.py` — removes old affected links before adding replacements and emits compact deterministic lists.
- `test_replace_detail_deferrals_removes_empty_metadata_key` in `tests/test_concept_tree.py` — deletes the key when no links remain.
- `test_structured_deferral_requires_known_or_owned_step` in `tests/test_concept_tree.py` — distinguishes unknown links, valid ownerless links, owner-matched links, and owner-mismatched links.
- `test_valid_deferral_persists_after_detail_write` in `tests/test_detail.py` — keeps the existing successful detail-write then accounting-save sequence.
- `test_failed_regeneration_retains_link_and_old_body` in `tests/test_detail.py` — proves an unsuccessful detail write changes neither the artifact nor accounting.
- `test_concurrent_deferrals_save_once_in_step_order` in `tests/test_detail.py` — proves concurrent completion order does not change the single saved candidate.
- `test_detail_accounting_helper_receives_only_written_results` in `tests/test_detail.py` — mixed successful and failed authoring replaces links only for successful steps.
- `test_accepts_valid_structured_deferral` in `tests/test_review.py` — keeps a valid exact structured link as coverage.
- `test_rejects_invalid_structured_deferral` in `tests/test_review.py` — keeps malformed, dangling, and owner-mismatched links from satisfying coverage.
- `test_any_surviving_committed_owner_is_sufficient` in `tests/test_review.py` — preserves many-owner delivery semantics.
- `test_ownerless_carved_concept_is_selected_for_deferral` in `tests/test_scope_out.py` — keeps a sole carved owner eligible for deferral.
- `test_shared_surviving_owner_prevents_deferral` in `tests/test_scope_out.py` — keeps any surviving committed owner sufficient.
- `test_parked_surviving_owner_does_not_prevent_deferral` in `tests/test_scope_out.py` — confirms a deferred survivor is not delivery ownership.
- `test_region_carve_deduplicates_ownerless_concept_ids` in `tests/test_scope_out.py` — preserves first-authored order and emits each ownerless concept once.
- `test_recommend_only_does_not_save_concept_record` in `tests/test_scope_out.py` — confirms preparation remains write-free on the no-apply path.
- `test_concept_save_failure_rolls_back_narrow` in `tests/test_scope_out.py` — confirms shared preparation does not weaken plan and sidecar restoration.

### Test-creation order (refactor step)

Write or strengthen these characterization tests before changing production code:

1. `tests/test_concept_tree.py:test_concept_deferral_step_ids_normalizes_valid_metadata` and `tests/test_concept_tree.py:test_concept_deferral_step_ids_rejects_malformed_metadata` — pin the exact current parser boundary.
2. `tests/test_detail.py:test_detail_accounting_helper_receives_only_written_results` — pin successful-only replacement before extracting the transformation.
3. `tests/test_detail.py:test_concurrent_deferrals_save_once_in_step_order` — pin deterministic ordering and one-save publication.
4. `tests/test_review.py:test_rejects_invalid_structured_deferral` — cover malformed, dangling, and owner-mismatched links as separate cases.
5. `tests/test_scope_out.py:test_shared_surviving_owner_prevents_deferral` and `tests/test_scope_out.py:test_parked_surviving_owner_does_not_prevent_deferral` — pin committed-owner semantics.
6. `tests/test_scope_out.py:test_recommend_only_does_not_save_concept_record` and `tests/test_scope_out.py:test_concept_save_failure_rolls_back_narrow` — pin no-write and rollback behavior.

These characterization tests must remain green and unmodified after the restructuring. If extraction requires changing an expected result, the change is behavioral and does not belong in this step.

## Acceptance criteria

- `plan_tool/concept_tree.py` exposes shared, write-free accounting helpers used by detail, review, and scope-out.
- `plan_tool/detail.py` no longer contains an independent JSON parser or full replacement implementation for `detail_deferral_step_ids`.
- `plan_tool/review.py:_structured_concept_deferral_is_valid` delegates metadata parsing and link validity to the shared accounting rules.
- `plan_tool/scope_out.py:ownerless_carved_concept_ids` delegates final committed-owner accounting while preserving its existing result order.
- Malformed metadata still produces no usable deferral links and does not raise.
- Whole-step replacement still removes obsolete affected-step links, preserves unrelated metadata, writes compact ordered lists, and removes empty keys.
- Concurrent detail authoring still saves one complete concept candidate in deterministic step order and excludes unsuccessful detail results.
- Scope-out recommend-only, stale-state refusal, successful apply, and publication-failure rollback behavior remain unchanged.
- `CONCEPTS_SCHEMA_VERSION` and the serialized `ConceptTree` and `ConceptNode` field sets remain unchanged.
- Focused tests in `tests/test_concept_tree.py`, `tests/test_detail.py`, `tests/test_review.py`, and `tests/test_scope_out.py` pass.

## References

- [pytest: How to Parametrize Fixtures and Test Functions](https://docs.pytest.org/en/stable/how-to/parametrize.html) — Use parametrization for the malformed metadata and ownership-state characterization matrices.

## Deferred

- Durable non-delivery records — step 2 replaces `source_metadata.detail_deferral_step_ids` with the plan’s persisted accounting contract and migration/default behavior.
- Non-delivery decision transitions — step 3 defines review and approval changes for `include`, `defer`, and `wont_do`.
- Publication unification — detail generation, concept synchronization, and scope-out retain their separate writers, compare-and-swap checks, ordering, and rollback protocols.
- Changed completeness semantics — later steps decide how `wont_do`, dangling records, contradictions, and unsigned proposals affect blocking findings.
- Split, merge, seed, and create-restoration behavior — later lifecycle steps consume the shared accounting boundary after the durable record exists.
