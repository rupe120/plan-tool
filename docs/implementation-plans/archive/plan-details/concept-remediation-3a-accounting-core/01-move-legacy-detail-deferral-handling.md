# Step 1 — Move legacy detail deferral handling into shared concept helpers

## Summary

This step moves the legacy `detail_deferral_step_ids` decode and candidate-update rules from `plan_tool/detail.py` and `plan_tool/review.py` into shared, write-free helpers in `plan_tool/concept_tree.py`. Detail authoring and concept coverage then use the same interpretation of legacy metadata while keeping their current orchestration and publication behavior. The key design decision is to share only copying, decoding, and validation; `plan_tool/detail.py:generate_detail()` remains responsible for fingerprinting and the single `save_concepts()` call. On green, serial and concurrent detail authoring, failed regeneration, and coverage checks behave exactly as they do before the refactor.

## Table of Contents

- [Summary](#summary) — Overview of the helper extraction and unchanged behavior.
- [Why](#why) — Why the legacy metadata rules need one owner.
- [Input](#input) — The legacy metadata contract this refactor must preserve.
- [Files (creates vs edits)](#files-creates-vs-edits) — Exact production and test files affected.
- [Implementation](#implementation) — Recommended helper boundary and invariants.
- [Tests](#tests) — Characterization and focused helper coverage.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Relevant JSON and pytest documentation.
- [Deferred](#deferred) — Later accounting and publication work excluded from this refactor.

## Why

Legacy detail deferrals are interpreted independently by `plan_tool/detail.py:_concept_deferral_step_ids()` and `plan_tool/review.py:_structured_concept_deferral_is_valid()`, while candidate mutation lives in `plan_tool/detail.py:_replace_detail_deferrals()`. These copies can drift on malformed JSON, duplicate IDs, owner checks, or replacement ordering. Moving the common rules to the concept artifact’s owning module gives later accounting steps one stable boundary without changing detail publication, coverage findings, or the persisted schema.

## Input

- **Legacy metadata field:** `plan_tool/concept_tree.py:ConceptNode.source_metadata` may contain `"detail_deferral_step_ids"` as a string holding a JSON array of positive integer step IDs.
- **Decode behavior:** Missing, empty, malformed, non-list, boolean, non-integer, or non-positive values provide no usable links. Duplicate valid IDs collapse to their first occurrence while preserving order.
- **Coverage context:** `plan_tool/review.py:check_concept_coverage()` combines decoded links with the node's persisted decision, the plan’s known step IDs, and exact `steps[].concept_ids` ownership.
- **Authoring context:** `plan_tool/detail.py:generate_detail()` replaces links only for successfully written detail results and publishes one updated `ConceptTree` after all serial or concurrent authoring finishes.
- **Schema limit:** This step does not add fields or change `CONCEPTS_SCHEMA_VERSION`; the legacy value remains a string in `source_metadata`.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `plan_tool/concept_tree.py` — Add shared, pure helpers for decoding legacy detail links, checking usable links against caller-supplied plan context, and preparing a copied tree with whole-step replacements.
  - `plan_tool/detail.py` — Replace `_concept_deferral_step_ids()` and `_replace_detail_deferrals()` with the shared helpers; keep detail selection, result ordering, fingerprint refresh, error mapping, and `save_concepts()` ownership here.
  - `plan_tool/review.py` — Make `_structured_concept_deferral_is_valid()` use the shared decoder or validity helper while preserving the current coverage rule.
  - `tests/test_concept_tree.py` — Add direct tests for the shared decode and copy-on-write replacement contract.
  - `tests/test_detail.py` — Preserve and strengthen orchestration characterization for successful, failed, serial, and concurrent deferral replacement.
  - `tests/test_review.py` — Preserve and strengthen characterization of which legacy links count as concept coverage.

## Implementation

The foundational logic is the **canonical decode-and-replace rule for legacy detail deferral step links**.

- **Put the common rule with the persisted model.** Add public, write-free helpers near `plan_tool/concept_tree.py:ConceptNode` and `plan_tool/concept_tree.py:ConceptTree`. One helper should decode the `"detail_deferral_step_ids"` value; another should prepare a copied tree from ordered whole-step replacements. A small validity helper may also accept known and owner step-ID sets so callers do not repeat link filtering.

- **Single-source the metadata key.** Move the `"detail_deferral_step_ids"` identifier out of `plan_tool/detail.py:_DETAIL_DEFERRAL_STEPS_KEY` and stop spelling it independently in `plan_tool/review.py:_structured_concept_deferral_is_valid()`. Keep the legacy key unchanged because changing persisted shape belongs to later steps.

- **Keep decoding fail-soft.** The shared decoder must return no usable IDs for absent or malformed legacy metadata. It must accept only positive integers, reject booleans, and deduplicate valid IDs in their stored order. Do not make reading legacy metadata raise from prompt rendering, regeneration selection, or completeness review.

- **Preserve whole-step replacement.** The candidate helper must:
  - Deep-copy the supplied `ConceptTree` and never mutate the caller’s snapshot.
  - Process replacements in caller order.
  - Remove the affected step’s old link from every concept before adding that step’s replacement links.
  - Preserve unrelated `source_metadata` entries and links for unaffected steps.
  - Store retained IDs as compact JSON such as `[1,3]`.
  - Remove the metadata key when no IDs remain instead of storing `[]`.
  - Avoid filesystem writes and avoid calling `save_concepts()`.

- **Adapt detail authoring at the existing read sites.** Use the shared decoder from `plan_tool/detail.py:_format_concept_scope_block()` and `_included_deferral_step_ids()`. Approved `include` concepts with a usable link to a current plan step must still add that step to regeneration, with selected steps sorted by ID.

- **Adapt the publication tail without moving it.** In `plan_tool/detail.py:generate_detail()`, build replacements only from `DetailResult` values where `written` is true, preserving deterministic result order from both authoring paths. Convert `DetailDeferral` records into the shared helper’s neutral concept-ID input rather than making `plan_tool/concept_tree.py` import the detail-layer dataclass.

- **Retain single-writer behavior.** After candidate preparation, `plan_tool/detail.py:generate_detail()` must still update `ConceptTree.plan_fingerprint` from the final durable plan and call `save_concepts()` once. A save failure must continue to mark written results as unsuccessful with the existing recovery message while leaving the prior concept sidecar in place.

- **Keep coverage read-only and semantically unchanged.** `plan_tool/review.py:_structured_concept_deferral_is_valid()` may retain the review-specific checks or delegate them to a shared predicate. A link counts only when the concept decision is `defer`, at least one decoded ID names a current step, and that ID is an exact owner when explicit owners exist. Any valid owner-compatible link remains sufficient; invalid links do not become coverage.

- **Do not import detail authoring into review.** Reusing `plan_tool/detail.py:_concept_deferral_step_ids()` from `plan_tool/review.py` would couple a read-only audit to the authoring orchestrator and leave the persisted contract in the wrong module. Keep dependencies directed toward `plan_tool/concept_tree.py`.

## Tests

- `tests/test_concept_tree.py:test_legacy_detail_deferral_ids_decode_in_stored_order` — Valid positive IDs are returned in order and duplicates collapse to their first occurrence.
- `tests/test_concept_tree.py:test_malformed_legacy_detail_deferral_ids_decode_as_empty` — Missing, malformed, non-list, boolean, non-integer, and non-positive values provide no usable links.
- `tests/test_concept_tree.py:test_detail_deferral_replacement_is_copy_on_write` — Candidate preparation leaves the input tree unchanged.
- `tests/test_concept_tree.py:test_detail_deferral_replacement_preserves_unrelated_metadata` — Whole-step replacement retains unrelated metadata and unaffected step links.
- `tests/test_concept_tree.py:test_detail_deferral_replacement_removes_empty_key` — Removing a step’s final link deletes the metadata key rather than storing an empty array.
- `tests/test_concept_tree.py:test_detail_deferral_replacements_follow_supplied_step_order` — Multiple replacements produce deterministic compact JSON in the supplied order.
- `tests/test_detail.py:TestStructuredDetailDeferrals.test_valid_deferral_persists_after_detail_write` — A successful detail write records its validated link.
- `tests/test_detail.py:TestStructuredDetailDeferrals.test_include_transition_regenerates_and_clears_link` — Successful include regeneration removes the old link.
- `tests/test_detail.py:TestStructuredDetailDeferrals.test_failed_regeneration_retains_link_and_old_body` — Failed regeneration changes neither the old detail nor its recovery link.
- `tests/test_detail.py:TestStructuredDetailDeferrals.test_concurrent_deferrals_save_once_in_step_order` — Concurrent results prepare one ordered candidate and publish the sidecar once.
- `tests/test_review.py:TestConceptCoverage.test_accepts_valid_structured_deferral` — A known owner-compatible legacy link counts as coverage.
- `tests/test_review.py:TestConceptCoverage.test_rejects_invalid_structured_deferral` — A link to an unknown step does not count as coverage.
- `tests/test_review.py:TestConceptCoverage.test_valid_link_among_positive_legacy_links_counts` — When several well-formed IDs are stored, one valid owner-compatible link remains sufficient.
- `tests/test_review.py:TestConceptCoverage.test_malformed_legacy_link_does_not_count` — Malformed metadata produces the existing `concept-coverage` finding rather than raising.

### Test-creation order (refactor step)

Before changing production code, run and, where an edge is missing, extend these characterization tests:

1. `tests/test_detail.py:TestStructuredDetailDeferrals.test_valid_deferral_persists_after_detail_write` — Pin successful write-then-link behavior.
2. `tests/test_detail.py:TestStructuredDetailDeferrals.test_include_transition_regenerates_and_clears_link` — Pin successful removal of an obsolete link.
3. `tests/test_detail.py:TestStructuredDetailDeferrals.test_failed_regeneration_retains_link_and_old_body` — Pin the no-write failure path.
4. `tests/test_detail.py:TestStructuredDetailDeferrals.test_concurrent_deferrals_save_once_in_step_order` — Pin deterministic ordering and one sidecar save.
5. `tests/test_review.py:TestConceptCoverage.test_accepts_valid_structured_deferral` — Pin accepted legacy coverage.
6. `tests/test_review.py:TestConceptCoverage.test_rejects_invalid_structured_deferral` — Pin rejected legacy coverage.
7. Add the mixed-validity and malformed-metadata coverage cases in `tests/test_review.py` before extraction — pin the current “any usable owner-compatible link” and fail-soft rules.

These characterization tests must stay green and unmodified after the restructuring. Add direct shared-helper tests in `tests/test_concept_tree.py` once the boundary exists; they supplement rather than replace the caller-level gate.

## Acceptance criteria

- `plan_tool/concept_tree.py` is the single owner of the `"detail_deferral_step_ids"` decode and candidate-replacement rules.
- Legacy metadata decoding preserves ordered positive IDs, removes duplicates, and returns no usable IDs for malformed values without raising.
- Candidate preparation does not mutate its input tree, does not write files, and preserves unrelated metadata.
- Replacing one step removes all of that step’s old links before adding its new links, deletes empty metadata keys, and emits compact JSON.
- `plan_tool/detail.py:generate_detail()` still saves the concept sidecar once after successful serial or concurrent authoring and never saves from a worker.
- Failed detail regeneration retains the previous detail body and legacy link.
- `plan_tool/review.py:check_concept_coverage()` remains read-only and keeps the same valid-link, owner, and finding behavior.
- `CONCEPTS_SCHEMA_VERSION` and the persisted `ConceptTree` field set remain unchanged.
- The focused tests in `tests/test_concept_tree.py`, `tests/test_detail.py`, and `tests/test_review.py` pass.

## References

- [Python json — JSON encoder and decoder](https://docs.python.org/3.13/library/json.html) — Use this for the legacy JSON-array decode behavior and compact `separators` encoding.
- [pytest API and Built-in Fixtures](https://docs.pytest.org/en/stable/builtin.html) — Use this for characterization matrices, temporary sidecars, and save-call spies.

## Deferred

- First-class durable non-delivery records — Step 2 defines the persisted record and stable identity; step 3 migrates valid legacy deferrals.
- Legacy metadata removal and schema migration — Step 3 owns deterministic migration and removal of `"detail_deferral_step_ids"` from newly persisted sidecars.
- Stronger publication-time accounting validation — Step 4 rejects unknown concepts, dangling routes, and contradictory candidate state.
- Broader synchronization and scope-out publication changes — `plan_tool/concept_sync.py:synchronize_concepts()` and `plan_tool/scope_out.py:apply_narrow()` retain their current compare-and-swap, rollback, and publication protocols until their owning remediation steps.
