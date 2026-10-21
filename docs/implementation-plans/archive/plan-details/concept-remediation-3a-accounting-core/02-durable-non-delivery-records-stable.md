# Step 2 — Add durable non-delivery records and stable record IDs

## Summary

This step adds a first-class `NonDeliveryRecord` to `plan_tool/concept_tree.py` and stores an ordered collection of those records on `ConceptTree`. It defines a stable SHA-256 `record_id`, extends strict `concepts.json` decoding, bumps the sidecar schema, and registers the nested persisted type in `plan_tool/data_contract.py` and `DATA_CONTRACT.md`. The key design decision is to derive identity only from the exact concept ID, disposition, and immutable origin reference; rationale, review state, artifact location, and step routing remain outside identity. On green, current and supported legacy sidecars load without inventing accounting, valid records round-trip exactly, malformed records fail clearly, and the documented identity matches a golden test vector.

## Table of Contents

- [Summary](#summary) — Overview of the new persisted record and stable identity.
- [Why](#why) — Why open metadata cannot provide durable non-delivery accounting.
- [Input](#input) — The sidecar and step-1 contracts this feature builds on.
- [Files (creates vs edits)](#files-creates-vs-edits) — Exact production, documentation, and test edits.
- [Implementation](#implementation) — Record shape, identity framing, decoding, and validation rules.
- [Tests](#tests) — Focused identity, persistence, compatibility, and drift coverage.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Primary references for JSON decoding, hashing, and tests.
- [Deferred](#deferred) — Migration, publication validation, review, and coverage work assigned to later steps.

## Why

`plan_tool/concept_tree.py:ConceptNode.source_metadata` can carry legacy `detail_deferral_step_ids`, but that string value has no independent occurrence identity, reviewed rationale, approval state, immutable origin, or relocatable artifact link. Step 1 centralizes the legacy interpretation without changing that persisted shape. This step supplies the durable shape that later migration, review, lifecycle, and completeness steps need, while keeping exact delivery ownership in `steps[].concept_ids`.

## Input

- **Step 1 output:** Use step 1’s shared, write-free legacy deferral helpers as the only interpretation of `ConceptNode.source_metadata["detail_deferral_step_ids"]`. This step does not repeat or change those rules.
- **Current concept sidecar:** `plan_tool/concept_tree.py:ConceptTree`, `ConceptNode`, `_decode_tree()`, `_validate_tree()`, `load_concepts()`, and `save_concepts()` define the strict `concepts.json` boundary.
- **Current identity contract:** `plan_tool/concept_tree.py:concept_id()` demonstrates the project’s SHA-256 and length-prefix approach. Non-delivery identity needs its own domain tag and inputs; it must not reuse concept identity.
- **Current schema:** `plan_tool/concept_tree.py:CONCEPTS_SCHEMA_VERSION` is `1`. Adding the top-level record collection requires a schema bump and an explicit version-1 decode path.
- **Ownership boundary:** `DATA_CONTRACT.md:Authored plan concept ownership` defines `steps[].concept_ids` as exact delivery ownership. A non-delivery record does not create or replace an owner.
- **Verification limit:** Structural decoding can validate stored values and identity integrity without reading a plan or checking the filesystem. Unknown concept IDs, absent step IDs, and missing artifacts must remain loadable for later diagnostics.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `plan_tool/concept_tree.py` — Add the persisted non-delivery dataclass, stable ID helper, `ConceptTree` collection, schema-version compatibility, and strict structural validation.
  - `plan_tool/data_contract.py` — Register the new nested persisted dataclass in `persisted_dataclass_contracts()`.
  - `DATA_CONTRACT.md` — Document the new top-level field, every record field, identity bytes, mutable routing fields, validation boundary, and version-1 compatibility behavior.
  - `tests/test_concept_tree.py` — Add identity, golden-vector, validation, decoding, compatibility, and round-trip tests.
  - `tests/test_data_contract.py` — Extend runtime-field and documentation drift checks to the new record.

## Implementation

The foundational logic is: **derive each non-delivery record ID from the exact concept ID, disposition, and immutable origin reference, while validating all other persisted fields without making them part of identity.**

- **Add one persisted nested type.** Add a dataclass such as `plan_tool/concept_tree.py:NonDeliveryRecord` and an ordered `non_delivery_records` collection on `ConceptTree`. Keep records separate from `ConceptNode.source_metadata` so one occurrence can be reviewed, routed, and transformed without changing the concept node.

- **Represent the plan-approved field set.** Each record must contain:
  - `record_id`, a lowercase 64-character SHA-256 value;
  - `concept_id`, an exact lowercase 64-character concept ID;
  - `disposition`, exactly `defer` or `wont_do`;
  - rationale or evidence explaining the non-delivery decision;
  - `review_state`, using the existing `CONCEPT_REVIEW_STATES` vocabulary;
  - `reviewed_semantic_digest`, empty unless approved and otherwise the
    domain-tagged digest of `concept_id`, disposition, rationale/evidence, and
    `origin_ref` that the operator actually reviewed;
  - `origin_ref`, a non-empty immutable reference to the producing occurrence;
  - `artifact_ref`, a non-empty relocatable reference to the current artifact;
  - `linked_step_ids`, an ordered, duplicate-free tuple of zero or more positive integer step IDs.

  Use clear field names that distinguish immutable origin from current routing. If rationale and evidence are separate fields, document and validate both; if one bounded field carries both, name its meaning clearly. Do not add an open-ended provenance bag when the required provenance fits the explicit fields above.

- **Bound persisted text.** Define named finite limits for operator- or producer-supplied rationale/evidence and reference strings. Reject empty required values, control characters, invalid reference syntax, and values beyond those limits. The exact limits may follow existing plan/detail path constraints, but they must be constants documented in `DATA_CONTRACT.md` and tested at the boundary.

- **Pin the identity bytes.** A recommended helper name is `non_delivery_record_id(concept_id, disposition, origin_ref)`. Use this exact framing:
  - start with the ASCII domain tag `plan-tool/non-delivery-record/v1` followed by NUL;
  - process `concept_id`, `disposition`, and `origin_ref` in that order;
  - encode each value as UTF-8;
  - for each value, hash its ASCII decimal byte length, NUL, encoded bytes, then NUL;
  - return the lowercase SHA-256 hex digest.

  Do not normalize `origin_ref` while hashing. Validate its canonical stored form before identity calculation so two textual references are not silently treated as one occurrence.

- **Pin a golden vector.** For `concept_id = "a" * 64`, `disposition = "defer"`, and `origin_ref = "detail:sample:step:2:occurrence:1"`, the framing above produces `2cf58544bc1e289e068b8c32cae84db4643871968944f91b0146e444052b043a`. Keep this vector in `tests/test_concept_tree.py`; property tests alone would allow an incompatible framing change.

- **Keep mutable fields out of identity but bind approval to semantics.** Changes to rationale/evidence, `review_state`, `reviewed_semantic_digest`, `artifact_ref`, or `linked_step_ids` must not change `record_id`. Define `non_delivery_review_digest()` with ASCII domain tag `plan-tool/non-delivery-review/v1` plus NUL, followed in order by `concept_id`, disposition, rationale/evidence, and `origin_ref`; frame each UTF-8 value as ASCII decimal byte length, NUL, bytes, NUL, then return lowercase SHA-256. Routing-only changes remain outside both identity and approval. For concept `"a" * 64`, disposition `defer`, evidence `not now`, and origin `detail:sample:step:2:occurrence:1`, pin `9f4156388f0783efd5e7dcf949a53e84b98fa88b6553c46051df9190a4c68368` as the golden digest. Changing `concept_id`, disposition, or `origin_ref` creates a different record identity.

- **Keep stale approval diagnosable.** Structural decoding validates digest shape and field types but deliberately permits an approved record whose stored semantic digest is missing or mismatched. Step 4's candidate-publication validator rejects that state before any new generation is written; step 8 loads historical state and emits the record-specific stale-approval finding.

- **Bump the sidecar schema.** Update `plan_tool/concept_tree.py:CONCEPTS_SCHEMA_VERSION` because `ConceptTree` gains a persisted field. `save_concepts()` must always emit the current complete shape.

- **Decode by stored schema version.** Extend `plan_tool/concept_tree.py:_decode_tree()` with two strict top-level shapes:
  - current records require the new `non_delivery_records` field and every exact nested field;
  - version-1 records accept only their existing top-level and node fields, then normalize in memory to the current schema with an empty record collection.

  Preserve all version-1 `ConceptNode.source_metadata`, including `detail_deferral_step_ids`. Step 3 owns converting that metadata into records. This step must not guess records, origins, artifacts, dispositions, or rationale during the schema-default upgrade.

- **Retain strict JSON behavior.** Continue using `plan_tool/concept_tree.py:_reject_duplicate_keys()` through `load_concepts()`. Reject duplicate keys at every nesting level, unknown or missing fields, non-finite numbers, booleans used as integers, malformed IDs, unknown dispositions, unknown review states, and a `record_id` that does not match its identity inputs.

- **Validate collection integrity.** Extend `plan_tool/concept_tree.py:_validate_tree()` to reject duplicate `record_id` values and invalid nested record types. Preserve record order exactly through load and save. Treat two rows with the same identity inputs as duplicate records even if mutable fields differ, because they describe one occurrence with conflicting state.

- **Keep structural and semantic validation separate.** Structural loading must allow:
  - a well-formed `concept_id` absent from `ConceptTree.concepts`;
  - a positive `linked_step_ids` entry absent from the current plan;
  - a syntactically valid `artifact_ref` whose target is missing.

  These conditions need durable diagnostic evidence. Do not make `load_concepts()` read the plan, inspect artifact existence, or discard the record. Step 4 adds the stricter candidate-publication check that prevents newly publishing dangling or contradictory accounting.

- **Preserve the existing writer boundary.** `plan_tool/concept_tree.py:save_concepts()` remains the sole sidecar writer in this step and keeps its existing atomic replacement behavior. This feature changes the serialized shape and validation, not filesystem transaction ownership.

- **Register the nested record independently.** Add a `PersistedDataclassContract` entry in `plan_tool/data_contract.py:persisted_dataclass_contracts()` for `NonDeliveryRecord`, following the separate `ConceptTree` and `ConceptNode` entries. The `ConceptTree` registry entry will discover its new collection field automatically.

- **Document the full contract.** Under `DATA_CONTRACT.md:Concept sidecar`, update the `ConceptTree` table and add a `NonDeliveryRecord` subsection with one row per persisted field. State the exact identity framing and golden vector, identity exclusions, allowed dispositions and review states, ordered-unique positive-step rule, reference syntax and bounds, version-1 defaulting behavior, and the distinction between structural loading and later semantic publication checks.
  Document the approval-digest framing and invariant in the same subsection.

- **Reject a metadata-only replacement.** Do not put the new record inside `ConceptNode.source_metadata` or serialize it as a JSON string. That would retain the weak open-bag boundary and prevent nested field drift checks.

## Tests

- `test_non_delivery_record_id_matches_golden_vector` — the documented domain tag, field order, byte lengths, delimiters, UTF-8 encoding, and SHA-256 output remain compatible.
- `test_non_delivery_record_id_is_stable` — repeated calls with identical identity inputs return the same lowercase 64-character value.
- `test_non_delivery_record_id_changes_with_each_identity_input` — changing the concept ID, disposition, or immutable origin changes the ID.
- `test_non_delivery_record_id_excludes_mutable_fields` — rationale, review state, artifact reference, and linked-step routing do not affect identity.
- `test_non_delivery_record_round_trips_exactly` — `save_concepts()` and `load_concepts()` preserve record values, tuple order, and collection order.
- `test_schema_version_one_defaults_non_delivery_records` — a strict version-1 sidecar loads with an empty record collection and current in-memory schema.
- `test_schema_version_one_preserves_legacy_metadata` — compatibility loading does not remove or reinterpret `detail_deferral_step_ids` or unrelated metadata.
- `test_current_schema_requires_non_delivery_records` — a current-schema JSON object missing the collection is invalid.
- `test_non_delivery_record_rejects_unknown_fields` — extra top-level or nested fields raise `InvalidConceptTreeError`.
- `test_non_delivery_record_rejects_duplicate_json_keys` — duplicate nested keys are rejected by the existing strict JSON hook.
- `test_non_delivery_record_rejects_invalid_identity` — malformed IDs and a digest inconsistent with the identity inputs are rejected.
- `test_non_delivery_record_rejects_invalid_disposition_or_review_state` — values outside the documented vocabularies are rejected.
- `test_non_delivery_record_rejects_invalid_linked_step_ids` — booleans, zero, negatives, non-integers, and duplicate IDs are invalid.
- `test_non_delivery_record_accepts_ordered_unique_fan_out` — several distinct positive step IDs retain their authored order.
- `test_non_delivery_record_enforces_text_and_reference_bounds` — empty, unsafe, or oversized required values fail at the structural boundary.
- `test_duplicate_non_delivery_record_identity_is_invalid` — repeated record IDs or equivalent identity inputs cannot coexist.
- `test_structurally_valid_dangling_record_loads` — unknown concepts and dangling step or artifact routes remain available for later diagnostics.
- `test_non_delivery_contract_discovers_runtime_fields` — the registry field list equals the dataclass fields.
- `test_non_delivery_contract_is_documented` — every persisted field, schema constant, disposition, review state, and identity exclusion appears in the correct `DATA_CONTRACT.md` section.

### Test-creation order (feature step)

1. Add the ID framing and golden-vector tests with the identity helper.
2. Add dataclass validation and exact round-trip tests with the new persisted shape.
3. Add version-1 compatibility and strict JSON decoding tests with the schema bump.
4. Add registry and documentation drift tests with the contract updates.

Every new test listed for this step must be green before the step is considered finished.

## Acceptance criteria

- `plan_tool/concept_tree.py:ConceptTree` persists an ordered `non_delivery_records` collection.
- Each record stores a stable record ID, exact concept ID, `defer` or `wont_do` disposition, bounded rationale/evidence, review state, immutable origin, current artifact reference, and ordered unique positive step links.
- `non_delivery_record_id()` uses the documented domain tag and length-prefixed byte framing over `concept_id`, `disposition`, and `origin_ref` in that order.
- The checked-in golden vector produces `2cf58544bc1e289e068b8c32cae84db4643871968944f91b0146e444052b043a`.
- Changing `artifact_ref`, `linked_step_ids`, rationale/evidence, or review state leaves `record_id` unchanged.
- Changing the concept ID, disposition, or origin reference changes `record_id`.
- Current-schema sidecars reject missing fields, unknown fields, duplicate keys, duplicate record identities, invalid enums, invalid linked-step values, and tampered IDs.
- Structurally valid records with unknown concepts or dangling routes load without being dropped.
- Version-1 sidecars load with an empty record collection while preserving legacy metadata for step 3.
- `save_concepts()` writes only the current schema and preserves its existing atomic replacement behavior.
- `plan_tool/data_contract.py:persisted_dataclass_contracts()` registers `NonDeliveryRecord` separately from `ConceptTree`.
- `DATA_CONTRACT.md:Concept sidecar` documents every persisted field and the exact identity contract.
- Focused tests in `tests/test_concept_tree.py` and `tests/test_data_contract.py` pass.

## References

- [RFC 8259: The JavaScript Object Notation (JSON) Data Interchange Format](https://www.rfc-editor.org/rfc/rfc8259.html) — Use its object and interoperability rules for strict sidecar decoding.
- [Python hashlib — Secure hashes and message digests](https://docs.python.org/3.13/library/hashlib.html) — Use the byte-oriented SHA-256 API for stable record identity.
- [Python json — JSON encoder and decoder](https://docs.python.org/3.13/library/json.html) — Use `object_pairs_hook` and strict parsing behavior to reject duplicate keys and malformed nested records.
- [pytest API and Built-in Fixtures](https://docs.pytest.org/en/stable/builtin.html) — Use parametrization and temporary paths for validation and persistence tests.

## Deferred

- Legacy `detail_deferral_step_ids` conversion — step 3 creates deterministic records from valid legacy metadata and removes the retired key from newly persisted sidecars.
- Semantic candidate-publication validation — step 4 rejects unknown concepts, dangling routes, and contradictory accounting before publication.
- Explicit approval and approval invalidation — step 5 owns operator review and the rules for semantic versus routing-only changes.
- Pending include regeneration — steps 6 and 7 persist and complete the transition without removing parked accounting early.
- Coverage and reporting semantics — step 8 replaces the legacy coverage consumer in `plan_tool/review.py:check_concept_coverage()` and reports invalid accounting without treating it as coverage.
- Split, merge, scope-out, and seed lifecycle transforms — the later remediation plans consume `record_id`, `origin_ref`, `artifact_ref`, and `linked_step_ids` without changing this step’s identity contract.
