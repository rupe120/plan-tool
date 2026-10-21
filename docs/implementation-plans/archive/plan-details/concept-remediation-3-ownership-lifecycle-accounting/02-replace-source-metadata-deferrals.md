# Step 2 — Replace metadata deferrals with durable non-delivery records

## Summary

This step adds a first-class persisted non-delivery record to `plan_tool/concept_tree.py` and removes detail deferral links from `ConceptNode.source_metadata`. `plan_tool/detail.py` converts successful detail deferrals into these records through the shared preparation contract from step 1, while `plan_tool/concept_sync.py` validates and renders the new source of truth. The record has a stable identity based on the concept, disposition, and artifact reference; mutable review state and step-routing data do not affect that identity. On green, `concepts.json` round-trips structured non-delivery records, legacy detail metadata upgrades deterministically, and no detail workflow writes `detail_deferral_step_ids`.

## Table of Contents

- [Summary](#summary) — The persisted contract and observable result.
- [Why](#why) — Why string metadata cannot support lifecycle accounting.
- [Input](#input) — Existing sidecar, detail envelope, and step-1 contracts this work consumes.
- [Files (creates vs edits)](#files-creates-vs-edits) — The source, documentation, and test changes.
- [Implementation](#implementation) — The record shape, identity, migration, and integration rules.
- [Tests](#tests) — Unit coverage for persistence, detail replacement, synchronization, and drift checks.
- [Acceptance criteria](#acceptance-criteria) — Observable requirements for completion.
- [References](#references) — Primary documentation relevant to deterministic identity and testing.
- [Deferred](#deferred) — Lifecycle behavior owned by later plan steps.

## Why

`plan_tool/detail.py:_concept_deferral_step_ids()` currently decodes `detail_deferral_step_ids` from an open string bag, and `plan_tool/detail.py:_replace_detail_deferrals()` writes compact JSON back into that bag. The representation has no independent record identity, approval state, rationale, or stable artifact link, so later split, merge, scope-out, and restoration work cannot tell one non-delivery occurrence from another or review it directly. A dedicated persisted record makes deliberate non-delivery part of the sidecar contract while leaving `Step.concept_ids` as the authority for delivery.

## Input

- **Step 1 preparation contract:** Build on step 1’s write-free concept-accounting preparation result. This step changes the prepared value from embedded step-number metadata to structured records; it does not move publication, compare-and-swap, or rollback behavior.
- **Concept sidecar:** `plan_tool/concept_tree.py:ConceptTree`, `ConceptNode`, `_decode_tree()`, `_validate_tree()`, `load_concepts()`, and `save_concepts()` define the strict `concepts.json` boundary. Preserve rejection of duplicate keys, unknown fields, invalid types, stale fingerprints, and invalid positional concept IDs.
- **Detail transport envelope:** `plan_tool/detail.py:DetailDeferral` and `parse_structured_detail_response()` continue to accept exactly `concept_id` and `step_id` from the transport-only envelope. The envelope is not the durable accounting record and must not be written into detail Markdown.
- **Successful authoring results:** `plan_tool/detail.py:DetailResult`, `_StepAuthoringOutcome`, and the post-authoring tail of `generate_detail()` identify which detail artifacts were actually written. Failed or skipped results must not replace prior accounting.
- **Legacy sidecars:** Schema-version-1 nodes may contain `source_metadata["detail_deferral_step_ids"]` as a compact JSON list. Migration must use the stored value and durable plan/detail references available at the reader boundary; it must not infer links from titles or prose.
- **Legacy ownership hint:** `source_metadata["step_id"]`, consumed by `plan_tool/concept_sync.py:_mapped_scopes()`, is a separate single-owner compatibility hint. Do not remove or reinterpret it as a detail deferral.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `plan_tool/concept_tree.py` — Add the persisted non-delivery dataclass, stable identity helper, schema-version migration, strict validation, and the `ConceptTree` collection that owns the records.
  - `plan_tool/detail.py` — Read and format deferrals from structured records, prepare replacements for successfully written details, and stop reading or writing `detail_deferral_step_ids`.
  - `plan_tool/concept_sync.py` — Validate non-delivery records against reviewed concepts and use approved matching records when rendering parked decisions.
  - `plan_tool/data_contract.py` — Register the new nested persisted dataclass and its schema owner.
  - `DATA_CONTRACT.md` — Document the new `ConceptTree` field, non-delivery record fields, identity framing, review semantics, and legacy upgrade behavior.
  - `tests/test_concept_tree.py` — Cover identity, strict decoding, migration, validation, and round trips.
  - `tests/test_detail.py` — Replace metadata assertions with structured-record assertions and cover whole-step replacement behavior.
  - `tests/test_concept_sync.py` — Cover matching, missing, unsigned, duplicate-source, and contradictory records during synchronization.
  - `tests/test_data_contract.py` — Extend field and section drift guards to the new persisted dataclass.

## Implementation

The foundational logic is: **a non-delivery entry is a distinct persisted record whose concept, disposition, and artifact reference determine its identity, while review state and routing data remain mutable and separately validated.**

- **Add a dedicated record to `plan_tool/concept_tree.py`.** A suitable name is `NonDeliveryRecord`. Store these records as an ordered list on `ConceptTree`, rather than inside `ConceptNode.source_metadata`, so they can be validated, replaced, reviewed, and transformed independently.

- **Use an explicit bounded field set.** The record must carry:
  - a stable record `id`;
  - the exact `concept_id`;
  - a `disposition` limited to `defer` or `wont_do`;
  - non-delivery `rationale`;
  - a non-empty immutable `origin_ref` naming the producing occurrence;
  - a non-empty repo-relative or namespaced current `artifact_ref` that may be atomically remapped when an artifact moves;
  - an ordered, duplicate-free `linked_step_ids` tuple of zero or more positive step IDs used for lifecycle routing and split fan-out;
  - a `review_state` using the concept review vocabulary.

  Keep the concept ID and record ID separate. `linked_step_ids` and the current `artifact_ref` are routing fields, not record identity, because step numbers and detail paths change during structural edits.

- **Define deterministic identity in `plan_tool/concept_tree.py`.** Use a domain-tagged, length-prefixed SHA-256 encoding like `concept_id()`, over `concept_id`, `disposition`, and immutable `origin_ref` in that fixed order. Exclude rationale, review state, `artifact_ref`, and `linked_step_ids` so review, rename, split fan-out, merge, or renumbering does not silently mint a different occurrence. Document the exact bytes and add a golden input-to-digest vector; property tests alone do not pin a persisted identity format.

- **Bump `CONCEPTS_SCHEMA_VERSION` and make migration explicit.** `plan_tool/concept_tree.py:_decode_tree()` should accept the current strict shape and the one supported legacy shape. At the `load_concepts()` boundary, convert each valid legacy `detail_deferral_step_ids` entry into one structured record, preserve unrelated metadata, remove only that retired key from the in-memory candidate, and produce deterministic record order.
  - Derive `origin_ref` from the producing occurrence and use the referenced step’s persisted detail path as the initial current `artifact_ref`.
  - If the legacy row names a step whose artifact cannot be recovered, preserve an explicit namespaced legacy reference rather than guessing by title. Later dangling-link validation must still be able to report the bad link.
  - Mark migrated records unreviewed because the old string did not prove that the record fields themselves were reviewed.
  - Reject malformed legacy JSON and duplicate legacy links instead of silently converting them to no records.
  - A subsequent `save_concepts()` writes only the new schema.

- **Separate structural decoding from semantic publication checks.** `_decode_tree()` and the persisted-shape portion of `_validate_tree()` require record IDs to match identity inputs, known dispositions and review states, unique positive `linked_step_ids`, non-empty references, and no duplicate record IDs. They deliberately allow an unknown `concept_id`, missing artifact, or temporarily dangling step link so `check_concept_coverage()` can load and report stable diagnostics. A stricter candidate-publication validator rejects those semantic dangling references before any new or modified tree is published.

- **Replace detail-side metadata helpers.** Retire `plan_tool/detail.py:_DETAIL_DEFERRAL_STEPS_KEY` and `_concept_deferral_step_ids()`. Update `_format_concept_scope_block()` and `_included_deferral_step_ids()` to read structured records while preserving deterministic concept and step ordering.

- **Preserve whole-step replacement semantics in `plan_tool/detail.py`.** Extend the step-1 preparation seam rather than rebuilding the algorithm in `generate_detail()`:
  - include only `DetailResult` values whose detail write succeeded;
  - remove all prior detail-produced records associated with each affected step before adding its replacements;
  - leave records from unrelated steps and other producers unchanged;
  - add at most one equivalent record per concept and artifact;
  - derive an immutable `origin_ref` from the producing plan, step, and detail occurrence;
  - use the written detail’s repo-relative path as the current `artifact_ref`;
  - carry the envelope’s step ID as the initial one-element `linked_step_ids` tuple;
  - derive the disposition from the validated detail contract (`defer`);
  - carry the concept rationale without inventing prose;
  - create the record as unreviewed pending step 3’s explicit review workflow;
  - return records in deterministic step/result order.

  The existing transport envelope remains unchanged. Do not add persisted fields to `DetailDeferral`.

- **Keep persistence single-writer behavior.** The post-authoring tail of `plan_tool/detail.py:generate_detail()` should prepare one candidate after serial or concurrent work has finished, refresh its `plan_fingerprint`, and call `save_concepts()` once. Failed regeneration retains the old records. Dry-run changes neither the sidecar nor the detail file. Step 4 owns stronger publication ordering after regeneration, so this step should preserve the current writer boundary rather than introduce another publisher.

- **Make synchronization use the new accounting source.** In `plan_tool/concept_sync.py`, add a write-free validation/preparation helper near `_accepted_decisions()`, `render_scope_decisions()`, and `_mapped_scopes()`:
  - an approved `defer` or `wont_do` decision is publishable only when at least one approved record names the same concept and disposition;
  - an approved record whose disposition conflicts with its concept decision is invalid;
  - an `include` decision cannot be treated as deliberately undelivered;
  - multiple records for one concept may be valid when their artifact references differ;
  - `render_scope_decisions()` renders each concept once in concept-tree order, not once per record;
  - `_mapped_scopes()` may continue reading the separate legacy owner hint `source_metadata["step_id"]`.

  Return the existing `SyncStatus.INVALID_STATE` or `SyncStatus.MAPPING_CONFLICT` result as appropriate and preserve `synchronize_concepts()` compare-and-swap, fingerprint, publication order, and rollback behavior.

- **Register the nested persisted type.** Add a separate `PersistedDataclassContract` entry in `plan_tool/data_contract.py:persisted_dataclass_contracts()` for the new record, following the existing separate entries for `ConceptTree` and `ConceptNode`.

- **Document the exact contract.** Update `DATA_CONTRACT.md` under `Concept sidecar`, `ConceptTree`, and a new non-delivery-record subsection. State which fields form identity, which routing fields may change without changing identity, the allowed dispositions and review states, the meanings of `origin_ref`, current `artifact_ref`, and `linked_step_ids`, and the schema-1 migration rule. Keep `ConceptNode.source_metadata` documented as an open string bag, but state that `detail_deferral_step_ids` is no longer a valid persisted key.

## Tests

- `test_non_delivery_id_has_golden_vector` — pins the exact domain tag, field order, framing, and SHA-256 result.
- `test_non_delivery_id_excludes_mutable_review_and_routing_fields` — review, rationale, and step renumbering do not change identity.
- `test_non_delivery_id_changes_for_concept_disposition_or_artifact` — distinct accounting occurrences cannot collide by construction.
- `test_concept_tree_round_trips_non_delivery_records` — the new nested records survive `save_concepts()` and `load_concepts()` exactly.
- `test_non_delivery_record_rejects_unknown_concept_and_invalid_fields` — strict validation rejects dangling concept IDs, bad enums, empty artifact references, booleans as step IDs, and invalid review states.
- `test_non_delivery_record_rejects_duplicate_identity` — duplicate IDs and equivalent duplicate records are invalid.
- `test_schema_one_detail_metadata_migrates_deterministically` — legacy links become ordered unreviewed records and unrelated metadata remains unchanged.
- `test_schema_one_malformed_detail_metadata_is_invalid` — corrupt legacy accounting is not treated as an empty deferral set.
- `test_saved_schema_two_omits_detail_deferral_metadata` — a migrated save contains the new records and no retired metadata key.
- `test_valid_detail_deferral_persists_non_delivery_record` — a successful detail write creates the expected artifact-linked record without writing the transport envelope.
- `test_failed_regeneration_retains_prior_non_delivery_record` — failed authoring preserves both the old detail and its accounting.
- `test_include_regeneration_removes_only_affected_detail_records` — successful replacement removes the affected step’s old records and preserves unrelated records.
- `test_concurrent_deferrals_prepare_once_in_step_order` — concurrent authoring produces one sidecar save with deterministic record order.
- `test_dry_run_does_not_change_non_delivery_records` — dry-run reports intended work without mutating the sidecar.
- `test_sync_requires_approved_matching_non_delivery_record` — a parked approved concept without approved matching accounting is rejected.
- `test_sync_rejects_disposition_conflict` — a record cannot approve `defer` for a concept currently decided as `wont_do`, or the reverse.
- `test_sync_renders_concept_once_with_multiple_artifact_records` — multiple valid sources do not duplicate plan-section prose.
- `test_sync_preserves_owner_step_metadata_mapping` — the unrelated `source_metadata["step_id"]` compatibility mapping remains functional.
- `test_non_delivery_contract_is_registered_and_documented` — runtime fields and the `DATA_CONTRACT.md` subsection remain in sync.
- `test_retired_detail_deferral_key_is_documented_as_invalid` — the contract clearly excludes the old metadata representation.

### Test-creation order (feature step)

Add the identity, strict-validation, and schema-migration tests with the `plan_tool/concept_tree.py` implementation first. Add detail replacement tests with the `plan_tool/detail.py` integration, then synchronization tests with `plan_tool/concept_sync.py`, and finish with the registry/documentation drift tests. Every new test listed for this step must be green before the step is considered finished.

## Acceptance criteria

- `ConceptTree` persists an ordered collection of structured non-delivery records in `concepts.json`.
- Every record contains a distinct record ID, exact concept ID, `defer` or `wont_do` disposition, rationale, artifact reference, optional positive source step ID, and review state.
- The stable record ID is reproducible from the documented concept/disposition/artifact framing and matches a checked-in golden vector.
- Changing rationale, review state, or source step ID does not change the record ID.
- Loading schema-version-1 `detail_deferral_step_ids` produces deterministic unreviewed records without dropping unrelated source metadata.
- Saving a migrated tree writes the new schema and no `detail_deferral_step_ids` key.
- Malformed legacy metadata, duplicate records, invalid dispositions, and invalid record IDs raise `InvalidConceptTreeError`; structurally valid dangling concept, step, or artifact references load for coverage diagnostics but cannot be newly published.
- A successful detail write replaces all old detail-produced records for that step and adds only the envelope’s validated concept links.
- A failed or skipped detail write retains its prior records.
- Concurrent detail authoring saves the concept sidecar once and orders replacements by step result order.
- Dry-run leaves the detail file and concept sidecar unchanged.
- `parse_structured_detail_response()` continues to accept transport objects containing exactly `concept_id` and `step_id`.
- `synchronize_concepts()` rejects approved parked decisions without approved matching records and rejects record/decision conflicts without writing either artifact.
- `render_scope_decisions()` renders each valid parked concept once even when it has multiple source records.
- `plan_tool/data_contract.py:persisted_dataclass_contracts()` and `DATA_CONTRACT.md` describe every persisted field of the new record.
- Focused tests in `tests/test_concept_tree.py`, `tests/test_detail.py`, `tests/test_concept_sync.py`, and `tests/test_data_contract.py` pass.

## References

- [hashlib — Secure Hashes and Message Digests](https://docs.python.org/3/library/hashlib.html) — Use this for the stable, explicitly framed non-delivery record identity.
- [pytest: How to Parametrize Fixtures and Test Functions](https://docs.pytest.org/en/stable/how-to/parametrize.html) — Use parametrization for invalid field, disposition, review-state, and migration cases.

## Deferred

- `plan_tool/concept_review.py:review_concept_scope()` non-delivery approval and decision-transition rules — step 3 adds explicit authoring, approval, replacement, and removal transitions.
- `plan_tool/detail.py:generate_detail()` publication only after regenerated artifacts are durable — step 4 strengthens this ordering.
- `plan_tool/review.py:_structured_concept_deferral_is_valid()` and `check_concept_coverage()` — step 5 replaces the legacy metadata consumer and enables blocking structured-accounting checks.
- Split and merge remapping of `linked_step_ids` and current `artifact_ref` — steps 7 and 8 own lifecycle transformation behavior while preserving `record_id` and `origin_ref`.
- Scope-out, seed, and create-restoration producers — steps 8 through 11 add records through their own workflows.
- `plan_tool/create.py:_review_concept_scope()` use of `source_metadata["step_id"]` — this is an ownership compatibility hint, not the retired detail-deferral key, and remains unchanged.
