> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 3 — Define exact immutable root and candidate records plus accepted-head resolution and enrollment preparation

## Summary

Create `plan_tool/roadmap_versions.py` as the read-only contract for immutable root and candidate records, their fixed storage inventory, accepted-head resolution, and preparation of the fixed root-enrollment generation. Extend `plan_tool/roadmap_impact_snapshot.py` so a captured snapshot retains the recorded brief’s raw UTF-8 bytes and raw-byte digest alongside its existing decoded-text digest. Keep one closed stored-version shape for roots and candidates, with the accepted-head selector as the only way to choose stored content. On green, step 4 can publish that exact prepared generation; this step neither acquires a writer token nor writes a version or selector.

## Table of Contents

- [Summary](#summary) — The step outcome and scoped files.
- [Table of Contents](#table-of-contents) — Links to each detail section.
- [Why](#why) — Why current snapshot evidence cannot yet provide immutable version authority.
- [Input](#input) — The snapshot, stage order, and source-byte contracts this step consumes.
- [Files (creates vs edits)](#files-creates-vs-edits) — The new version contract and snapshot updates.
- [Implementation](#implementation) — Record rules, raw-byte bindings, and selector-only resolution.
- [Tests](#tests) — Focused compatibility, record, and fail-closed coverage.
- [Acceptance criteria](#acceptance-criteria) — Observable completion conditions.
- [References](#references) — Strict record and deterministic identity guidance.
- [Applicable guardrails](#applicable-guardrails) — Plan boundaries that constrain this contract.
- [Deferred](#deferred) — Publication and lifecycle work owned by later steps.

## Why

`plan_tool/roadmap_impact_snapshot.py:RoadmapImpactSnapshot` binds the current live roadmap, while `plan_tool/roadmap_source_identity.py:baseline_record()` binds a semantic baseline that leaves feedback out. Neither provides one immutable, complete root-or-candidate record or a selector that can return exact stored bytes. The snapshot route retained by step 1 supplies the complete gate-valid bundle; this step defines the byte-bound contract that later enrollment, candidate storage, promotion, and readers share without making any of them visible yet.

## Input

- **Complete snapshot:** Step 1 preserves `plan_tool/roadmap_impact_snapshot.py:RoadmapImpactSnapshot` and its existing gate behavior, including its stage-ordered artifact texts, parsed artifacts, artifact digests, and gate-valid evidence. The version contract must require a complete captured bundle; it must not read current artifact paths to fill a missing member.

- **Recorded brief:** `plan_tool/roadmap_source.py:read_recorded_brief_source()` identifies the recorded brief path, while `read_brief_text()` preserves the existing decoded-text digest behavior. Capture raw bytes separately from that compatibility path and require strict UTF-8 decoding before accepting them as version content.

- **Stage inventory:** The filename constants in `plan_tool/roadmap_artifacts.py` are leaf-safe. `plan_tool/roadmap.py:STAGES` and `RoadmapStage.artifact_path` remain the orchestrator table, but production version reading must not import that module because `plan_tool/roadmap_view.py` must remain a reader-layer leaf rather than gain a transitive orchestrator dependency.

- **Existing strict-record precedent:** `plan_tool/roadmap_source_identity.py:CanonicalSourceIdentity`, `load_pending_generation()`, and `render_pending_generation()` show the current closed-field, strict-JSON, and SHA-256 validation style. Reuse the contract shape without changing that module’s baseline or journal schema.

## Files (creates vs edits)

- **New files:**
  - `plan_tool/roadmap_versions.py` — Define immutable root and candidate records, deterministic identity and storage-inventory validation, accepted-head parsing, enrolled-state detection, and selector-based resolution.
  - `tests/test_roadmap_versions.py` — Cover record shape, exact byte bindings, selected-version lookup, absent-head handling, and fail-closed malformed storage.

- **Existing files (edits only):**
  - `plan_tool/roadmap_impact_snapshot.py` — Capture and bind raw recorded-brief bytes and their raw digest while preserving the current decoded-text digest contract.
  - `tests/test_roadmap_impact_snapshot.py` — Characterize raw-brief capture, raw-presentation stale detection, artifact-digest validation, and compatibility for existing direct snapshot construction.

## Implementation

- **Foundational logic:** Resolve immutable version content only from one validated accepted-head selector and its exact stored root-or-candidate record.

- **Retain raw brief evidence in snapshots.** Add intuitive raw-byte fields such as `brief_bytes` and `brief_raw_digest` to `plan_tool/roadmap_impact_snapshot.py:RoadmapImpactSnapshot`. `capture_roadmap_impact_snapshot()` must read the referenced brief through `Path.read_bytes()`, decode it strictly as UTF-8, and bind the SHA-256 of those unchanged bytes.

- **Preserve the existing brief digest.** Keep `RoadmapImpactSnapshot.brief_digest` on its current decoded-text path through `plan_tool/roadmap_source.py:read_brief_text()` and `digest_decoded_text()`. The raw digest is version evidence; it must not redefine existing source-evidence semantics.

- **Keep snapshot compatibility deliberate.** New raw-brief fields may remain optional at the dataclass boundary so current direct constructions outside this step continue to work. Captured snapshots and `recheck_roadmap_impact_snapshot()` must always carry a complete raw binding, and the version contract must reject a snapshot that lacks it.

- **Bind all captured raw inputs.** Update `plan_tool/roadmap_impact_snapshot.py:snapshot_artifacts_match_captured_text()` to validate each artifact text against its recorded SHA-256 digest. Validate the raw brief digest when the raw fields are present. Update the private `_binding()` used by `recheck_roadmap_impact_snapshot()` so a raw-byte-only brief change, including CRLF-to-LF replacement, makes the snapshot stale.

- **Own one leaf-safe version inventory.** In `plan_tool/roadmap_versions.py`, define one fixed tuple pairing the four literal artifact keys with member names taken from `plan_tool/roadmap_artifacts.py`'s filename constants. Version parsing, identity, resolution, and later readers use that tuple; they must not import `plan_tool/roadmap.py`, accept a caller inventory, or scan a directory. A test may import `STAGES` to prove exact key, order, and `artifact_path(...).name` parity.

- **Define one closed stored-version shape.** In `plan_tool/roadmap_versions.py`, define strict immutable records for a stored version and an accepted-head selector. The version record must bind its schema version, roadmap slug, version kind, explicit predecessor and candidate-lineage positions, fixed brief member name and digest, and the complete leaf-inventory-ordered artifact members with each exact digest.

- **Keep root and candidate records in one namespace.** A root must carry explicit null values for candidate-only bindings. A candidate must carry non-null predecessor, content, and lineage identities, including a fixed identity for an initial empty review lineage. Later candidate steps own how those identities are constructed; this step owns their closed shape, grammar, and inclusion in the version identity.

- **Make identities reproducible.** Compute the version id from deterministic JSON over the version-owned record fields, excluding the id being checked. Recompute it when parsing or resolving a record. A changed slug, kind, predecessor, lineage binding, member name, order, or digest must invalidate the record rather than resolve a different version.

- **Keep storage paths fixed and module-owned.** Give `plan_tool/roadmap_versions.py` one fixed version namespace, record filename, accepted-head filename, brief filename, and staged-member naming rule. Validate version ids before using them as path components. Do not accept arbitrary member paths, scan directories, or select a newest version.

- **Separate byte storage from publication.** Provide pure rendering, parsing, path, member-inventory, and root-enrollment-generation preparation helpers that step 4’s writer can use. This step must not import `plan_tool/roadmap_revision_publish.py`, acquire a writer token, write files, or expose an enrollment command.

- **Resolve only the selected target.** Define `load_accepted_version()` as the read boundary for later consumers. It must read one fixed accepted-head selector, validate its slug and version id, load that exact root or candidate record, and verify every named stored artifact and brief byte stream against its recorded digest before returning immutable stage-ordered bytes.

- **Fail closed without hiding enrollment state.** A missing accepted-head selector is the only unversioned result. A present selector that is malformed, points to missing storage, names a mismatched record, or has a digest-mismatched member must raise a version-contract error; it must not fall back to live artifacts, a normalized brief, a sibling version, or a false “not enrolled” result. `is_roadmap_enrolled()` must preserve that distinction for step 4’s writer fence.

- **Keep validation mechanical.** The version module may validate shape, membership, ordering, strict decoding, identities, and digests. It must not rerun roadmap gates, assess roadmap prose, inspect review quality, or infer promotion authority.

## Tests

### Tests for this step

- `tests/test_roadmap_impact_snapshot.py:test_capture_retains_raw_recorded_brief_bytes_and_digest_without_changing_decoded_digest` — CRLF brief bytes remain exact in the snapshot while the established decoded-text digest keeps its current value.

- `tests/test_roadmap_impact_snapshot.py:test_recheck_refuses_a_raw_brief_presentation_change_with_the_same_decoded_text` — Replacing only raw line endings makes a captured snapshot stale.

- `tests/test_roadmap_impact_snapshot.py:test_snapshot_artifacts_match_captured_text_rejects_a_mismatched_artifact_digest` — A forged artifact digest cannot pass captured-evidence validation.

- `tests/test_roadmap_impact_snapshot.py:test_legacy_direct_snapshot_without_raw_brief_fields_keeps_compatibility_contract` — Existing explicit snapshot construction remains usable outside immutable-version storage.

- `tests/test_roadmap_versions.py:test_root_and_candidate_records_round_trip_through_one_closed_schema` — Both record kinds parse and render through one shared stored-version contract.

- `tests/test_roadmap_versions.py:test_root_requires_explicit_null_candidate_bindings_and_candidate_requires_non_null_bindings` — Root and candidate records cannot omit or substitute their distinct predecessor, content, or lineage positions.

- `tests/test_roadmap_versions.py:test_version_identity_changes_or_refuses_when_any_bound_record_field_changes` — Every identity-preimage field, including member order and the raw brief digest, is protected.

- `tests/test_roadmap_versions.py:test_version_record_requires_the_configured_stage_order_and_fixed_member_names` — Duplicate, missing, reordered, or caller-shaped artifact inventories are rejected.
- `tests/test_roadmap_versions.py:test_leaf_version_inventory_matches_the_orchestrator_stage_table` — The fixed version keys and member names equal `STAGES` and each `RoadmapStage.artifact_path(...).name`, while `plan_tool.roadmap_versions` has no production import of `plan_tool.roadmap`.

- `tests/test_roadmap_versions.py:test_load_version_refuses_digest_mismatched_or_missing_exact_members` — A stored record cannot return altered, absent, or substituted brief or artifact bytes.

- `tests/test_roadmap_versions.py:test_load_accepted_version_reads_only_the_head_named_root_or_candidate` — Resolution reads the one selector target and does not inspect sibling versions, directory order, or live roadmap artifacts.

- `tests/test_roadmap_versions.py:test_missing_head_is_unversioned_but_invalid_present_head_fails_closed` — Absence remains distinct from malformed or dangling accepted-head state.

- `tests/test_roadmap_versions.py:test_version_contract_validation_and_resolution_do_not_create_or_repair_storage` — Parsing and lookup leave version files, selector state, and source artifacts unchanged.

Every listed test must be green before this step is complete.

## Acceptance criteria

- `RoadmapImpactSnapshot` captures exact raw recorded-brief bytes and a matching raw SHA-256 digest while preserving its existing decoded-text digest behavior.

- A raw-only recorded-brief change causes `recheck_roadmap_impact_snapshot()` to refuse the stale snapshot.

- `plan_tool/roadmap_versions.py` accepts only closed root or candidate records whose identities, stage order, fixed member names, and byte digests all validate.
- The version reader owns one leaf-safe fixed four-member inventory that matches the orchestrator stage table by test without importing `plan_tool.roadmap` in production.

- Root and candidate records use one namespace and resolver, while retaining explicit distinct predecessor, content, and lineage bindings.

- `load_accepted_version()` returns only the exact bytes named by a valid selector and never searches, repairs, or falls back to live roadmap content.

- A missing selector reports an unversioned roadmap; any invalid present selector or invalid selected storage fails closed.

- This step creates no immutable version files, accepted-head selector, persisted journal, enrollment command, or legacy-writer behavior change. It only prepares the fixed root-enrollment generation that step 4 publishes.

- All tests listed in `## Tests` pass.

## References

- [Configuration | Pydantic Docshttps: — Review strict, frozen, extra-field-forbidden record validation.

- [json — JSON encoder and decoderhttps: — Use deterministic serialization and strict duplicate-free decoding for persisted records.

- [hashlib — Secure hashes and message digestshttps: — Bind raw brief and artifact bytes to version identities.

- [RFC 8785: JSON Canonicalization Scheme (JCS)https: — Review stable JSON rules before fixing the version-identity preimage.

## Applicable guardrails

- **The plan’s “## Plan intent” and step intent** — Limit this step to inert version records, validation, resolution, and enrollment preparation; publication and visibility remain outside it.

- **The plan’s “## Scope guardrails”, binary observables** — Use exact bytes, identities, and deterministic member order as the contract’s observable facts.

- **The plan’s “## Scope guardrails”, allowed behavior changes and allowed reorganization** — Add only the shared version-aware read boundary; leave existing unversioned readers and roadmap flows unchanged.

- **The plan’s “## Scope guardrails”, model and promotion authority** — Do not add model input, candidate mutation, review authority, or accepted-head movement.

- **The plan’s “## Scope guardrails”, validation boundary** — Validate record mechanics only; do not add semantic, quality, or gate judgments to storage resolution.

- **The plan’s “## Out of scope”, version management and operational hardening** — Do not add retention, history, bulk migration, concurrent workflow handling, or a general version framework.

## Deferred

- Root enrollment, journal publication, accepted-head creation, and the atomic legacy-writer fence — Step 4 owns the first observable accepted head.

- Candidate materialization, candidate storage inputs, and review-lineage construction — Steps 6 through 8 own those lifecycle facts while reusing this step’s shared record shape.

- Exact promotion of a review-sealed candidate — Step 9 owns accepted-head replacement.

- Accepted-head reader routing and CLI actions — Steps 10 and 11 own those integrations.

- Generalizing `plan_tool/roadmap_evidence_store.py:publish_evidence()` into version storage — That cross-module refactor exceeds this focused contract step.
