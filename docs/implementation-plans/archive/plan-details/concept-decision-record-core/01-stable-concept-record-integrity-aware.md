> **Auto-archived**: this plan was swept on 2026-07-16 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 1 — Add the stable concept record and integrity-aware persistence

## Summary

This step creates `plan_tool/concept_tree.py` as the owner of the persisted concept-tree model, stable node identity, sidecar path, strict loading, and atomic saving. It registers the parent and nested records in `plan_tool/data_contract.py` and documents their JSON fields in `DATA_CONTRACT.md`. The key design decision is to derive each node identifier only from its title and parent path, while treating order, decision content, and review state as mutable data. On green, `tests/test_concept_tree.py` proves exact round trips, stable identifiers, rejection of stale or malformed records, and safe replacement of `plan-details/<slug>/concepts.json`; `tests/test_data_contract.py` proves the documented schema matches the runtime dataclasses.

## Table of Contents

- [Summary](#summary) — Overview of the new model, persistence boundary, and observable result.
- [Why](#why) — Why stable identity and strict integrity checks are needed.
- [Input](#input) — Values required to locate and validate a concept record.
- [Files (creates vs edits)](#files-creates-vs-edits) — New and modified files in this step.
- [Implementation](#implementation) — Required model, identity, validation, and persistence rules.
- [Tests](#tests) — Unit and contract cases that define the behavior.
- [Acceptance criteria](#acceptance-criteria) — Observable conditions for completion.
- [References](#references) — Primary references for hashing, JSON, and atomic publication.
- [Deferred](#deferred) — Related work owned by later steps or reconciliation.

## Why

Plan prose has no durable concept identity or integrity boundary, so later review and synchronization code cannot safely tell an unchanged concept from a reordered one, or a current record from one derived against older plan content. This step establishes that boundary before bootstrap, review, and synchronization depend on it: mutable concept attributes must survive round trips under one stable identifier, and corrupt or stale records must be rejected before their decisions can affect Markdown.

## Input

- **Plan location:** `plan_tool/concept_tree.py:concepts_path` takes the plan Markdown path and derives `plan-details/<slug>/concepts.json`. Mirror `plan_tool/grounding.py:grounding_path`; use `plan_tool/locator.py:slug_from_filename` only for slug extraction, not for resolving the detail-bundle directory.
- **Expected plan state:** the load boundary receives the current expected plan fingerprint and compares it with the stored fingerprint. An absent sidecar is different from a present record with malformed integrity metadata or a mismatched fingerprint.
- **Concept position:** stable identity consumes the normalized node title and its ordered parent-title path. It does not consume order, review state, decision text, rationale, source metadata, or other mutable attributes.
- **Persisted JSON:** loading accepts only the schema owned by `plan_tool/concept_tree.py:CONCEPTS_SCHEMA_VERSION`. The loader validates the top-level record, every nested node, the identifier derivation, parent relationships, and the expected plan fingerprint before returning a usable tree.

## Files (creates vs edits)

- **New files:**
  - `plan_tool/concept_tree.py` — define the concept records, stable identifier derivation, sidecar path, validation errors, strict loader, and atomic single-file saver.
  - `tests/test_concept_tree.py` — cover identity, round trips, integrity rejection, path derivation, and atomic replacement.

- **Existing files (edits only):**
  - `plan_tool/data_contract.py` — import the new leaf and add separate `PersistedDataclassContract` entries for the parent concept record and its nested node record.
  - `DATA_CONTRACT.md` — add the `concepts.json` path, integrity rules, schema constant, and one field table for each registered dataclass.
  - `tests/test_data_contract.py` — assert both concept records are registered and their fields, schema constant, path, identity rule, and fingerprint rule are documented.

## Implementation

The foundational logic is: **accept a persisted concept tree only when its schema, structure, stable identifiers, and stored plan fingerprint all match the current expected state**.

- **Own the full record in one leaf.** Add `plan_tool/concept_tree.py` as a stdlib-focused domain and persistence module. Follow the shape of `plan_tool/grounding.py:Grounding`, `grounding_path`, `write_grounding`, and `read_grounding` for a tracked JSON sidecar beside the detail bundle, while keeping this loader strict because callers must distinguish stale or invalid state from absence.

- **Define separate parent and child records.** Use clear dataclasses such as `ConceptTree` and `ConceptNode`, with `CONCEPTS_FILENAME = "concepts.json"` and an initial `CONCEPTS_SCHEMA_VERSION`. The parent record must carry the schema version, plan slug, plan fingerprint, and the concept collection. Each node must carry its stable id, title, parent/source linkage needed by later derivation, decision content, and the plan’s three-state review value. Keep collection defaults safe for programmatic construction, but do not let defaults make malformed persisted JSON valid.

- **Keep stable identity narrower than the mutable record.** Provide one public identity helper, such as `concept_id(title, parent_path)`, that hashes an unambiguous encoding of the parent-title path and title with SHA-256. A NUL-delimited UTF-8 encoding is a suitable approach because it prevents boundary collisions. Exclude node order, review state, decision text, rationale, source metadata, and all other mutable fields so reordering or editing a decision does not break durable joins.

- **Validate identity on load.** Do not trust the stored id merely because it is syntactically a digest. Recompute the expected id from the stored title and parent path and reject any mismatch. Also reject duplicate ids, impossible parent paths, malformed child records, unknown review-state values, wrong field types, and unsupported schema versions.

- **Preserve stored values on valid reads.** Once validation succeeds, reconstruct the exact persisted values rather than re-deriving mutable fields. In particular, loading must not replace decision content, review state, source linkage, or the stored plan fingerprint with newly computed values.

- **Make stale state explicit.** The read API should return the normal absence result only when `concepts.json` does not exist. A present but malformed record and a plan-fingerprint mismatch should produce distinct typed invalid/stale failures so later CLI code can map them to different outcomes without parsing error strings. Do not silently return `None` for those cases as `plan_tool/grounding.py:read_grounding` does; the concept record can carry reviewed decisions and therefore needs a stricter boundary.

- **Resolve the sidecar path directly.** `plan_tool/concept_tree.py:concepts_path` should compute `plan_path.parent / "plan-details" / slug / CONCEPTS_FILENAME`, matching `plan_tool/grounding.py:grounding_path`. Keep `plan_tool/locator.py:slug_from_filename` as a function-local dependency if the new leaf follows the import-light grounding pattern.

- **Publish one complete JSON document atomically.** A save function such as `save_concepts(plan_path, tree)` should validate the tree before writing, create the bundle directory, stage UTF-8 JSON in the target directory, flush and `fsync` it, then use `os.replace` to publish it. A failed stage or replace must leave the previous valid `concepts.json` usable and remove the temporary file when possible.

- **Keep the stored slug tied to the path.** Saving must reject a tree whose `plan_slug` disagrees with the slug derived by `concepts_path`, or derive the slug inside the save boundary so disagreement cannot be persisted. Loading must apply the same check; a valid record copied under another plan must not be accepted.

- **Use strict JSON types.** Python’s `bool` is an `int` subclass, so schema-version and numeric validation must reject booleans where integers are required. Reject non-object top-level JSON, non-list node collections, non-object node entries, duplicate JSON keys if the chosen parsing approach exposes them, and non-finite numeric values if any numeric field is introduced.

- **Register both dataclasses.** Add separate entries for `ConceptTree` and `ConceptNode` in `plan_tool/data_contract.py:persisted_dataclass_contracts`, mirroring the separate `SavedReview` and `Recommendation` entries. Point `source_symbol` at `plan_tool/concept_tree.py:ConceptTree` and `plan_tool/concept_tree.py:ConceptNode`, and register `CONCEPTS_SCHEMA_VERSION` on the parent contract.

- **Document the runtime contract.** Add a `DATA_CONTRACT.md` section for the `plan-details/<slug>/concepts.json` sidecar and separate nested headings for `ConceptTree` and `ConceptNode`. State which fields are persisted, the allowed three-state value set, how the stable id is derived, which attributes are excluded from identity, how the plan fingerprint is checked, and how absence differs from stale or malformed state.

- **Keep other producers out of this step.** `plan_tool/concept_tree.py` owns storage and validation only. Deterministic construction belongs to step 3, scoped review belongs to step 4, and concept-to-Markdown propagation belongs to step 5. This step should not parse plan body sections or invent merge behavior.

- **Prefer the established sidecar shape over locator-based resolution.** Routing `concepts.json` through `plan_tool/locator.py:resolve_plan` is the rejected alternative because locator resolves plan Markdown files, not files inside `plan-details/<slug>/`.

## Tests

- `tests/test_concept_tree.py:test_concepts_path_is_inside_plan_detail_bundle` — derives `plan-details/<slug>/concepts.json`, including a priority-prefixed plan filename.
- `tests/test_concept_tree.py:test_concept_id_is_deterministic` — repeated calls with the same title and parent path return the same SHA-256 identifier.
- `tests/test_concept_tree.py:test_concept_id_ignores_mutable_fields` — nodes differing only in order, review state, decision content, rationale, or source metadata retain the same id.
- `tests/test_concept_tree.py:test_concept_id_changes_with_title_or_parent_path` — different titles or different parent paths produce different ids.
- `tests/test_concept_tree.py:test_save_and_load_round_trip_exact_record` — stable ids, source linkage, decision content, three-state values, ordering, and integrity metadata survive a full JSON round trip.
- `tests/test_concept_tree.py:test_save_creates_missing_bundle_directory` — saving creates the required `plan-details/<slug>` directory.
- `tests/test_concept_tree.py:test_second_save_replaces_single_sidecar` — a later save replaces the record without accumulating JSON or temporary files.
- `tests/test_concept_tree.py:test_missing_sidecar_returns_absent` — a missing `concepts.json` yields the documented absence result.
- `tests/test_concept_tree.py:test_malformed_json_is_invalid` — malformed or non-object JSON raises the typed invalid-record failure.
- `tests/test_concept_tree.py:test_wrong_schema_version_is_invalid` — an unsupported `CONCEPTS_SCHEMA_VERSION` is rejected.
- `tests/test_concept_tree.py:test_missing_or_wrong_typed_integrity_field_is_invalid` — absent or wrongly typed slug, fingerprint, schema, or node fields are rejected.
- `tests/test_concept_tree.py:test_plan_fingerprint_mismatch_is_stale` — a stored fingerprint different from the expected current fingerprint raises the typed stale-record failure.
- `tests/test_concept_tree.py:test_stored_slug_must_match_plan_path` — a record copied under another plan path is rejected.
- `tests/test_concept_tree.py:test_tampered_concept_id_is_invalid` — a stored id that does not match its title and parent path is rejected.
- `tests/test_concept_tree.py:test_duplicate_concept_ids_are_invalid` — two nodes with the same positional identity cannot load as distinct records.
- `tests/test_concept_tree.py:test_invalid_parent_path_is_rejected` — a node whose declared parent chain is not represented by the tree is rejected.
- `tests/test_concept_tree.py:test_unknown_review_state_is_invalid` — values outside the plan’s three-state vocabulary are rejected.
- `tests/test_concept_tree.py:test_failed_atomic_publish_preserves_previous_record` — a simulated publication failure leaves the last valid sidecar readable.
- `tests/test_concept_tree.py:test_save_rejects_invalid_tree_before_replacement` — invalid in-memory data never replaces a valid persisted record.
- `tests/test_data_contract.py:test_contract_registry_names_concept_records` — both parent and nested dataclasses appear in `persisted_dataclass_contracts`.
- `tests/test_data_contract.py:test_concept_contract_discovers_runtime_fields` — registered fields match the runtime dataclasses.
- `tests/test_data_contract.py:test_concept_contract_is_documented` — both field tables, `CONCEPTS_SCHEMA_VERSION`, `concepts.json`, identity exclusions, and fingerprint rejection are present in `DATA_CONTRACT.md`.

### Test-creation order (feature step)

1. Add path and identity tests with `plan_tool/concept_tree.py:concepts_path` and the stable-id helper.
2. Add exact round-trip and atomic replacement tests with the record dataclasses and persistence functions.
3. Add malformed-schema, stale-fingerprint, slug, parent, duplicate-id, and tampered-id rejection tests with the strict loader.
4. Add the runtime-registry and documentation drift tests after registering `ConceptTree` and `ConceptNode`.

Every new test in `tests/test_concept_tree.py` and `tests/test_data_contract.py` must be green before this step is considered finished.

## Acceptance criteria

- `plan_tool/concept_tree.py` exposes persisted parent and node records, `CONCEPTS_FILENAME`, `CONCEPTS_SCHEMA_VERSION`, a stable-id helper, `concepts_path`, and strict load/save operations.
- The same title under the same parent path always has the same id, including after changes to order, review state, decision content, rationale, or source metadata.
- Changing the title or parent path changes the node id.
- Saving then loading preserves every persisted value exactly.
- A missing `concepts.json` is reported as absent, while malformed data and a plan-fingerprint mismatch produce distinct typed failures.
- Loading rejects a tampered id, duplicate id, invalid parent path, unsupported schema version, invalid three-state value, or slug that disagrees with the plan path.
- Saving publishes one complete `plan-details/<slug>/concepts.json` atomically, and a failed publication does not destroy the previous valid record.
- `plan_tool/data_contract.py:persisted_dataclass_contracts` contains separate entries for `ConceptTree` and `ConceptNode`.
- `DATA_CONTRACT.md` contains separate field tables for both records and documents the path, schema constant, identity inputs and exclusions, three-state vocabulary, and fingerprint validation.
- All new tests in `tests/test_concept_tree.py` and `tests/test_data_contract.py` pass.

## References

- [Python hashlib — Secure hashes and message digests](https://docs.python.org/3/library/hashlib.html) — Use the SHA-256 API for deterministic node identifiers.
- [Python json — JSON encoder and decoder](https://docs.python.org/3/library/json.html) — Use the decoder and encoder rules when enforcing strict persisted-record types and exact round trips.
- [Python os — Miscellaneous operating system interfaces](https://docs.python.org/3/library/os.html) — Read the `os.replace` and `fsync` behavior used to publish a staged sidecar safely.
- [Python tempfile — Generate temporary files and directories](https://docs.python.org/3/library/tempfile.html) — Use sibling temporary files so final replacement stays on the same filesystem.

## Deferred

- Deterministic bootstrap from plan sections — step 3 owns source parsing, initial node construction, and re-derivation conflicts.
- Scoped three-state review and sign-off — step 4 owns review transitions and scope completeness.
- Concept-record and Markdown synchronization — step 5 owns propagation and divergent-edit conflict handling.
- Coordinated transaction recovery across `concepts.json` and plan Markdown — the plan explicitly leaves recovery across the two independently published artifacts for later work.
- Shared atomic JSON helper extraction — `plan_tool/grounding.py:_atomic_write_text` and `plan_tool/review_persistence.py:_atomic_write_text` already duplicate this behavior; consolidating all call sites would change files outside this step and should be planned by reconciliation.
