# Step 1 — Centralize concept change preparation

## Summary

This step moves the existing concept-change preparation rules into `plan_tool/concept_sync.py` without changing observable behavior. `plan_tool/detail.py` and `plan_tool/scope_out.py` will delegate their concept-tree transformations to that shared preparation layer, while retaining their current orchestration and publication order. The key design decision is to centralize pure copying, mutation, and validation now, without introducing the typed publication intents owned by step 2. On green, synchronization, detail deferrals, and scope-out produce the same plans, concept records, statuses, and failure behavior as before the refactor.

## Table of Contents

- [Summary](#summary) — The result and boundaries of the refactor.
- [Why](#why) — Why concept preparation needs one shared home.
- [Input](#input) — Existing plan and concept contracts that must remain unchanged.
- [Files (creates vs edits)](#files-creates-vs-edits) — The source and test files changed by this step.
- [Implementation](#implementation) — The preparation boundary, caller changes, and invariants.
- [Tests](#tests) — Characterization coverage and the required test-first order.
- [Acceptance criteria](#acceptance-criteria) — Observable proof that the refactor preserves behavior.
- [References](#references) — Primary documentation relevant to fingerprints and test seams.
- [Deferred](#deferred) — Publication features intentionally left to later steps.

## Why

Concept changes are currently prepared in three different shapes: `plan_tool/concept_sync.py:synchronize_concepts` validates and derives a synchronized plan and tree, `plan_tool/detail.py:_replace_detail_deferrals` copies and rewrites deferral metadata, and `plan_tool/scope_out.py:_prepare_concept_narrow_update` loads, validates, copies, and changes ownerless concepts before `apply_narrow`. Keeping these transformations in separate callers makes it easy for their copying, validation, and source-snapshot rules to drift before the publication authority is expanded. This step creates one preparation boundary while preserving every current result and failure path, giving steps 2 and 3 a stable base for typed intents and recoverable publication.

## Input

- `plan_tool/concept_tree.py:ConceptTree` and `plan_tool/concept_tree.py:ConceptNode` define the mutable record being copied and prepared. Preserve stable IDs, authored concept order, metadata strings, schema version, plan slug, and the source `plan_fingerprint`.
- `plan_tool/concept_tree.py:_validate_tree` remains the integrity check for prepared trees. This refactor must not weaken its validation or change `plan_tool/concept_tree.py:load_concepts` and `plan_tool/concept_tree.py:save_concepts` serialization behavior.
- `plan_tool/schema.py:Plan`, `plan_tool/schema.py:StepScope`, and each step’s `concept_ids` are existing inputs to scope mapping and owner checks. No schema field changes belong in this step.
- `plan_tool/concept_review.py:review_concept_scope` remains the authority for applying scoped review decisions and approval metadata. Preparation may call it, but must not duplicate its decision-validation rules.
- `plan_tool/detail.py:DetailDeferral` and the `detail_deferral_step_ids` metadata value are the existing detail-deferral contract. Preserve the compact JSON list encoding, replacement order, and removal behavior.
- The exact plan Markdown and current concept sidecar are compare-and-swap inputs to `plan_tool/concept_sync.py:synchronize_concepts`. Preserve the distinction between the original tree and reviewed tree.

## Files (creates vs edits)

- **New files:** None.

- **Existing files (edits only):**
  - `plan_tool/concept_sync.py` — add the shared, write-free preparation boundary and have `synchronize_concepts` use it.
  - `plan_tool/detail.py` — replace the local `_replace_detail_deferrals` implementation with delegation to the shared preparation logic.
  - `plan_tool/scope_out.py` — keep scope-out loading and orchestration local, but delegate concept copying, ownerless deferral changes, and prepared-state validation to the shared logic.
  - `tests/test_concept_sync.py` — add direct characterization coverage for preparation and retain synchronization equivalence tests.
  - `tests/test_concept_tree.py` — pin the concept-tree validation and serialization behavior on which preparation relies.
  - `tests/test_detail.py` — pin deferral replacement, removal, ordering, and failure behavior before changing the caller.
  - `tests/test_scope_out.py` — pin ownerless-concept preparation, non-mutating exits, and rollback behavior before changing the caller.

## Implementation

The foundational logic is: **prepare a validated concept change from an immutable source snapshot without writing any artifact**.

- **Create one write-free preparation boundary in `plan_tool/concept_sync.py`.** It should accept the existing source state needed by a caller, deep-copy mutable records, apply the requested existing transformation, validate the candidate, and return prepared data for the caller to publish. A small internal prepared-state object is reasonable if it carries the original and candidate values clearly, but do not introduce the discriminated intent model assigned to step 2.

- **Separate preparation from publication in `plan_tool/concept_sync.py:synchronize_concepts`.** Move candidate plan construction, `_mapped_scopes` application, `render_scope_decisions`, final tree construction, and validation behind the preparation boundary where practical. Keep filesystem reads, compare-and-swap checks, `_atomic_publish`, rollback, provenance refresh, and `ConceptSyncResult` status mapping in `synchronize_concepts`.

- **Preserve the original-versus-reviewed comparison.** `original_tree` remains the expected current sidecar snapshot, while `reviewed_tree` is the candidate source for decisions. Never compare the current sidecar against the reviewed candidate; doing so would reject valid edits or accept stale source state.

- **Keep final fingerprint framing unchanged.** `plan_tool/concept_sync.py:_fingerprint` must still hash the fully rendered candidate plan bytes plus the existing ordered detail files. Preparation must set the candidate tree’s `plan_fingerprint` from those exact bytes before validation and serialization.

- **Move detail transformation ownership out of `plan_tool/detail.py`.** The behavior now implemented by `plan_tool/detail.py:_replace_detail_deferrals` belongs in the shared preparation layer. Preserve these rules:
  - Only successfully written detail results participate.
  - Each affected step’s old links are removed before its new links are added.
  - Unrelated concept metadata stays unchanged.
  - Concept and step processing order stays deterministic.
  - The input `ConceptTree` is never mutated.
  - An empty retained list removes `detail_deferral_step_ids` instead of storing an empty JSON list.

- **Keep detail orchestration local.** `plan_tool/detail.py:generate_detail` should still decide which detail results succeeded, collect replacements after both serial and concurrent authoring paths, compute the current fingerprint, and perform the existing save and error-to-result conversion. This step changes where the candidate tree is prepared, not when or how detail files and the sidecar are published.

- **Split scope-out preparation by responsibility.** `plan_tool/scope_out.py:_prepare_concept_narrow_update` should continue resolving the current fingerprint, loading the sidecar, checking missing or unknown ownership, and capturing the original sidecar text needed by `apply_narrow`. Delegate the copy-and-change portion to `plan_tool/concept_sync.py`, using the existing result of `ownerless_carved_concept_ids` and `plan_tool/concept_review.py:review_concept_scope`.

- **Preserve scope-out decision semantics.** Only concepts that lose their final committed owner change to `defer`; concepts still owned by a committed survivor and unrelated concepts remain unchanged. The existing signed `review_concept_scope(..., sign_off=True)` behavior stays intact in this refactor.

- **Keep scope-out publication and rollback unchanged.** `plan_tool/scope_out.py:apply_narrow` must retain its stale-plan and stale-sidecar checks, detail archive/rename journal, plan write, final fingerprint refresh, concept save, and restoration behavior. The prepared update may change shape internally, but it must still carry enough original state for these checks.

- **Do not broaden the public behavior.** Invalid mappings in `plan_tool/concept_sync.py:_mapped_scopes`, malformed concept records, missing sidecars for concept-owned scope-out work, unknown concept IDs, stale source state, and persistence failures must produce the same current statuses, exceptions, messages where asserted, and non-mutation guarantees.

- **Leave existing external callers stable.** `plan_tool/create.py` calls `render_scope_decisions` and `synchronize_concepts`; those public surfaces should remain compatible because `plan_tool/create.py` is outside this step’s file set.

## Tests

- `tests/test_concept_sync.py:test_prepare_concept_change_does_not_mutate_inputs` — the shared preparation boundary returns copied candidates and leaves the source plan and trees unchanged.
- `tests/test_concept_sync.py:test_prepare_concept_change_preserves_rendered_scope_and_mapping` — preparation produces the same deferred prose, out-of-scope prose, and mapped `StepScope` values as `synchronize_concepts`.
- `tests/test_concept_sync.py:test_sync_renders_decisions_preserves_markdown_and_maps_steps` — successful synchronization still preserves unowned Markdown and publishes the expected scopes and fingerprint.
- `tests/test_concept_sync.py:test_sync_detects_changed_owned_section_without_writes` — plan compare-and-swap failure still writes nothing.
- `tests/test_concept_sync.py:test_sync_rejects_conflicting_mappings_without_writes` — conflicting concept mappings still fail before publication.
- `tests/test_concept_sync.py:test_second_publication_failure_rolls_back_new_sidecar` — a later publication failure still restores artifact existence and contents.
- `tests/test_concept_tree.py:test_save_and_load_round_trip_exact_record` — prepared trees remain compatible with the existing serializer.
- `tests/test_concept_tree.py:test_tampering_duplicates_and_invalid_parent_are_rejected` — central preparation does not bypass tree integrity checks.
- `tests/test_detail.py:TestStructuredDetailDeferrals.test_valid_deferral_persists_after_detail_write` — a successful detail result still adds the correct structured deferral link.
- `tests/test_detail.py:TestStructuredDetailDeferrals.test_include_transition_regenerates_and_clears_link` — successful regeneration still removes an obsolete deferral link.
- `tests/test_detail.py:TestStructuredDetailDeferrals.test_failed_regeneration_retains_link_and_old_body` — a failed regeneration still changes neither the old detail nor its concept link.
- `tests/test_detail.py:TestStructuredDetailDeferrals.test_concurrent_deferrals_save_once_in_step_order` — concurrent authoring still prepares one ordered concept update and saves once.
- `tests/test_scope_out.py:test_successful_apply_persists_narrow_and_deferrals` — successful scope-out still narrows the plan and defers the ownerless concept.
- `tests/test_scope_out.py:test_scope_out_changes_only_ownerless_carved_concepts` — shared and unrelated concepts remain unchanged.
- `tests/test_scope_out.py:test_recommend_only_does_not_save_concept_record` — recommend-only scope-out remains non-mutating.
- `tests/test_scope_out.py:test_owned_concept_without_usable_record_refuses_before_writes` — missing required concept state still stops before seed or plan writes.
- `tests/test_scope_out.py:test_concept_save_failure_rolls_back_narrow` — sidecar failure still restores the original plan and concept record.

### Test-creation order (refactor step)

Write or strengthen the characterization tests before changing production code, in this order:

1. Pin `synchronize_concepts` success, source-divergence, mapping-conflict, fingerprint, and rollback results in `tests/test_concept_sync.py`.
2. Pin deep-copy and validation expectations using `tests/test_concept_sync.py` and the existing round-trip and rejection cases in `tests/test_concept_tree.py`.
3. Pin detail deferral add, replace, remove, failed-regeneration, and concurrent ordering behavior in `tests/test_detail.py`.
4. Pin scope-out’s ownerless-only change rule, missing-record refusal, recommend-only no-write path, and save-failure rollback in `tests/test_scope_out.py`.
5. Refactor the production modules only after those tests pass.

The same characterization tests must remain green and unmodified after the restructuring. Any expectation change indicates behavior-changing work and belongs in a later feature step.

## Acceptance criteria

- The shared preparation entry point in `plan_tool/concept_sync.py` performs no filesystem writes and does not mutate its input `Plan` or `ConceptTree` objects.
- `plan_tool/concept_sync.py:synchronize_concepts` retains its existing signature and returns the same `SyncStatus`, plan contents, concept contents, and rollback results for the characterized cases.
- Prepared synchronized trees carry the fingerprint of the exact rendered candidate plan bytes under the existing `plan_tool/concept_sync.py:_fingerprint` framing.
- `plan_tool/detail.py` no longer owns a separate implementation of concept deferral replacement.
- Detail deferral addition, replacement, removal, failed regeneration, and concurrent step ordering produce the same persisted records as before the refactor.
- `plan_tool/scope_out.py` delegates concept mutation preparation while preserving missing-record, unknown-ID, ownerless-only, stale-state, and rollback behavior.
- `plan_tool/create.py` requires no change and remains compatible with `render_scope_decisions` and `synchronize_concepts`.
- The focused tests in `tests/test_concept_sync.py`, `tests/test_concept_tree.py`, `tests/test_detail.py`, and `tests/test_scope_out.py` pass.
- The characterization tests written before the refactor pass unchanged after it.

## References

- [Python hashlib — Secure hashes and message digests](https://docs.python.org/3/library/hashlib.html) — Use this to preserve the existing SHA-256 framing for candidate plan fingerprints.
- [pytest — Monkeypatching functions and environments](https://docs.pytest.org/en/stable/how-to/monkeypatch.html) — Use failure seams to characterize publication and rollback behavior before restructuring.

## Deferred

- Typed, discriminated publication intents — step 2 adds the request shapes and rejects incompatible combinations.
- All-or-recoverable multi-artifact publication and durable recovery — step 3 owns staging, journaling, commit, restoration verification, and uncertain-path results.
- Scope-review, create, detail, and scope-out migration to the publication authority — later plan steps own those behavior-changing integrations.
- Changes to `plan_tool/concept_review.py:review_concept_scope` decision and approval policy — this step reuses that policy without redesigning it.
- Concept-tree schema or serializer changes — no frontmatter decision authorizes a persisted-schema change in this refactor.
