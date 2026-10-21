> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 3 — Enroll an exact immutable root, roll back only incomplete new files, and select it without rewriting source artifacts

## Summary

Add `plan_tool/roadmap_versions.py` and `tests/test_roadmap_versions.py` as the storage and selection boundary for an enrolled roadmap. Enrollment accepts one complete `plan_tool/roadmap_impact_snapshot.py:RoadmapImpactSnapshot`, stores its four captured artifact byte sequences plus its exact recorded-brief bytes under one immutable version id, and writes an accepted-head selector last. The same closed stored-version record admits this root and later candidate versions, so accepted-head resolution can validate either without a second namespace. The captured snapshot, not current top-level paths or a directory scan, supplies root content and identity. On green, a caller resolves the selected stored version exactly, while interrupted enrollment recovery deletes only its recorded new version files.

## Table of Contents

- [Summary](#summary) — The step’s outcome and narrow footprint.
- [Table of Contents](#table-of-contents) — Links to each section.
- [Why](#why) — Why roadmap versions need one exact storage and selection boundary.
- [Input](#input) — The captured snapshot, stage table, and journal contracts this step reads.
- [Files (creates vs edits)](#files-creates-vs-edits) — The two new files and their roles.
- [Implementation](#implementation) — Immutable root enrollment, recovery, and accepted-head selection rules.
- [Tests](#tests) — Direct coverage for exact storage, refusal, recovery, and selection.
- [Acceptance criteria](#acceptance-criteria) — Observable conditions for completing the step.
- [References](#references) — Record validation, deterministic encoding, and digest guidance.
- [Applicable guardrails](#applicable-guardrails) — Plan boundaries that constrain this storage proof.
- [Deferred](#deferred) — Later lifecycle integration that does not belong in enrollment.

## Why

The current roadmap files and `plan_tool/roadmap_source_identity.py` baselines can prove a current semantic source, but they do not retain a complete immutable version or name one canonical reader target. Step 1 supplies one gate-valid captured bundle and step 2 supplies durable recorded-member publication; this step combines them into the first accepted root without turning a source rewrite, a baseline sidecar, or a newest-file convention into version authority.

## Input

- **Complete captured bundle:** Step 1’s `plan_tool/roadmap_impact_snapshot.py:RoadmapImpactSnapshot` supplies stage-ordered `artifact_keys`, `artifact_texts`, parsed `artifacts`, raw `artifact_digests`, source identities, and the recorded brief digest. Extend that capture to retain the exact recorded-brief text whose digest it already validates. Accept only a complete snapshot that still satisfies `snapshot_artifacts_match_captured_text()` and whose UTF-8 encoded artifact and brief text matches each recorded raw digest.

- **Current-state recheck:** `plan_tool/roadmap_impact_snapshot.py:recheck_roadmap_impact_snapshot()` compares the captured binding with a second complete, gate-valid read. Enrollment needs this recheck, including exact brief bytes, after journaling and before any version member becomes visible.

- **Fixed artifact order:** `plan_tool/roadmap.py:STAGES` and each `RoadmapStage.artifact_path` define the accepted four-artifact order and source-relative names. Derive the root inventory from this table; do not accept a caller-provided artifact mapping or reorder it by filename.

- **Publication transaction:** Step 2 exposes the guarded form of `plan_tool/roadmap_revision_publish.py:_publish_generation()`. Build its `plan_tool/roadmap_source_identity.py:PendingGeneration` from `GenerationMember` records and reuse the same `RoadmapWriterToken` checked by `require_roadmap_writer_token()`.

- **Baseline distinction:** `plan_tool/roadmap_source_identity.py:baseline_record()` uses `canonical_projection()`, which deliberately leaves out feedback. It remains source-admission evidence only; root-version identity must bind the full captured artifact bytes, including any retained feedback.

## Files (creates vs edits)

- **New files:**
  - `plan_tool/roadmap_versions.py` — Own the shared immutable root/candidate record, exact version-id/path rules, root enrollment publication, enrolled-state check, and accepted-head resolution.
  - `tests/test_roadmap_versions.py` — Cover exact root storage, selector behavior, stale-input refusal, and recovery of an incomplete first enrollment.

- **Existing files (edits only):**
  - `plan_tool/roadmap_impact_snapshot.py` — Retain the exact recorded-brief text beside its existing digest in the immutable snapshot.
  - `tests/test_roadmap_impact_snapshot.py` — Prove snapshot capture and recheck bind exact brief bytes.

## Implementation

- **Foundational logic:** Store a complete captured roadmap as one immutable root whose accepted-head selector is the only way this module chooses version content.

- **Settle a narrow public boundary.** Expose intuitive helpers such as `enroll_accepted_root()`, `store_version()`, `load_version()`, `load_accepted_version()`, and `is_roadmap_enrolled()` from `plan_tool/roadmap_versions.py`. Step 3 uses `store_version()` only for the root; step 6 uses the same closed record and namespace for candidates. A caller must be able to address a validated version id directly, but the module must not add version listing, retention, comparison, or workflow-state APIs.

- **Use fixed version storage.** Keep the selector and version directories below `plan_tool/roadmap_artifacts.py:roadmap_dir()`, with one fixed versions directory, one fixed stored-version record filename, and one fixed accepted-head filename owned by this module. A version id must use the existing lowercase SHA-256 grammar; validate it before using it as a path component. Do not create a private candidate namespace or a root-only resolver.

- **Bind every stored version to exact raw content.** Define one frozen, closed stored-version record plus the accepted-head selector, following `plan_tool/roadmap_source_identity.py:CanonicalSourceIdentity`'s strict-record approach. The record carries a version kind, schema version, roadmap slug, explicit predecessor (`null` only for a root and non-null for a candidate), explicit lineage binding (`null` only for a root and a deterministic initial-or-answer-bound identity for a candidate), the exact recorded-brief member and digest, and the `STAGES`-ordered artifact key, stored filename, and raw-byte digest inventory. Its identity preimage includes all of those fields, and a reader recomputes the id from that same inventory. Complete candidate review records remain separate metadata rather than a second selected-version shape.

- **Store captured bytes, not regenerated artifacts.** Convert each `RoadmapImpactSnapshot.artifact_texts` entry and its retained recorded-brief text to UTF-8 only after checking their SHA-256 values against the paired digests. Do not call `RoadmapStage.render()` to create a root artifact, and do not reread a top-level artifact or live brief while assembling stored members.

- **Require the complete snapshot shape.** Reject a snapshot with missing, duplicate, reordered, mismatched, or unparseable stage evidence before building a `PendingGeneration`. `snapshot_artifacts_match_captured_text()` proves the parsed snapshot shape; this module must add the raw-digest check that that helper does not own.

- **Publish only new version files.** Build ordered `GenerationMember` records for the root’s four stored artifacts, stored brief, stored-version record, and finally the accepted-head selector. Every enrollment member must record `old_bytes=None`; top-level source artifacts, baselines, seed state, and existing journals must not become generation members.

- **Keep the selector last.** Put the accepted-head file after every root file and root record in the generation order. A selected head must never point at a partially written root.

- **Recheck inside the journal window.** Pass a final-recheck callback to the step 2 publication boundary. That callback must call `recheck_roadmap_impact_snapshot()` for the original capture and admit only the exact in-flight `PendingGeneration`; a general “ignore pending journal” path would allow another transaction’s journal to bypass the check.

- **Fail closed on prior enrollment or collision.** Require an active matching `RoadmapWriterToken`, reject an existing accepted-head selector or target root member before publishing, and preserve all existing bytes on refusal. Do not overwrite a root because its id or source content appears equivalent.

- **Recover only recorded new files.** Reuse `plan_tool/roadmap_revision_publish.py:recover_roadmap_publication()` for an interrupted enrollment. Because every recorded old state is absent, recovery must delete only the recorded partial root and selector files; it must not recurse through directories, rewrite, delete, or restore any source artifact.

- **Resolve only through the selector.** `load_accepted_version()` must read the accepted-head record, validate its version id, load that exact stored-version record regardless of root or candidate kind, and verify the recorded brief plus every stored artifact digest before returning immutable bytes in stage order. It must not inspect current source files, choose the newest version directory, or repair a malformed selector.

- **Keep enrolled detection separate from resolution.** `is_roadmap_enrolled()` must treat an accepted-head selector’s presence as enrollment so later legacy-writer checks can fail closed. A missing selector is the only unversioned result; a malformed selector or missing selected root must fail resolution rather than fall back to source artifacts.

- **Leave current consumers unchanged.** Do not modify `plan_tool/roadmap_view.py:load_roadmap()` in this step. Step 9 routes one reader through `load_accepted_version()`, while this step only provides the deterministic read boundary it needs.

## Tests

### Tests for this step

- `test_enrollment_stores_the_complete_snapshot_and_recorded_brief_as_one_immutable_root` — Enrolling a four-stage fixture stores the captured artifact and exact brief bytes and returns the same bound values through `load_accepted_version()`.

- `test_root_identity_binds_slug_predecessor_brief_stage_order_filenames_and_raw_bytes` — Changing any identity-preimage field, including the recorded brief, changes or invalidates the root identity rather than resolving the original root.

- `test_root_record_requires_explicit_null_predecessor_and_lineage_bindings` — A root record accepts only `predecessor_version_id: null` and `lineage_identity: null`; an omitted or non-null field is rejected.

- `test_stored_version_contract_loads_root_and_candidate_records_from_one_namespace` — The shared resolver validates a null-predecessor/null-lineage root and a non-null-predecessor/lineage-bound candidate through the same record shape without a private candidate lookup rule.

- `test_enrollment_rechecks_the_exact_snapshot_after_journaling_before_writing_members` — The final recheck sees its own pending generation, and a stale capture leaves source files, root files, and the head selector unchanged.

- `test_enrollment_never_rewrites_or_journals_top_level_source_artifacts` — The four source artifact byte sequences stay unchanged and no source path appears in the enrollment generation.

- `test_enrollment_refuses_an_existing_head_or_root_member_without_overwrite` — A repeated or colliding enrollment fails before replacing either stored version content or the accepted-head selector.

- `test_incomplete_root_recovery_deletes_only_recorded_new_version_files` — Recovering a partial first enrollment removes only recorded files with absent old states and leaves every top-level source artifact untouched.

- `test_load_accepted_version_uses_the_selected_stored_root_not_current_sources_or_newest_directory` — Later source edits and another unselected version directory do not affect accepted-head resolution.

- `test_load_accepted_version_returns_the_captured_brief_after_live_brief_changes` — Changing the recorded live brief after enrollment cannot alter the selected version's exact brief bytes or context input.

- `test_malformed_or_tampered_head_and_root_never_fall_back_to_source_artifacts` — A missing selected root, invalid selector id, changed root record, or digest-mismatched stored artifact raises a version error instead of returning current source content.

Every named test in `tests/test_roadmap_versions.py` must be green before this step is complete.

## Acceptance criteria

- `enroll_accepted_root()` accepts only one complete, current, gate-valid `RoadmapImpactSnapshot` and creates one immutable root with all four captured artifact byte sequences plus the exact bound recorded brief.

- A root id binds the roadmap slug, explicit null predecessor and lineage fields, recorded brief, stage-ordered filenames, and raw artifact digests through deterministic record encoding; the same preimage positions carry non-null predecessor and lineage identities for candidates.

- Enrollment writes no top-level roadmap artifact, baseline, seed-state, or other source file.

- The accepted-head selector is written only after the root’s stored artifacts and root record are present.

- Recovery of an interrupted enrollment deletes only recorded new version files and leaves all source artifacts unchanged.

- `load_accepted_version()` returns exact artifact and brief bytes only from the root or candidate named by the accepted-head selector and rejects missing, malformed, or tampered storage without a source, root-only, private-candidate, or newest-version fallback.

- `is_roadmap_enrolled()` distinguishes an absent selector from an invalid present selector so later writer checks can fail closed.

- `tests/test_roadmap_versions.py` passes.

## References

- [Configuration | Pydantic Docs](https://docs.pydantic.dev/latest/api/config/) — Use strict, frozen models for root and selector records with no unrecognized fields.

- [json — JSON encoder and decoder](https://docs.python.org/3.13/library/json.html) — Use deterministic encoding and strict decoding for records that feed version identity.

- [hashlib — Secure hashes and message digests](https://docs.python.org/3.13/library/hashlib.html) — Use SHA-256 to bind each stored artifact and the root identity preimage.

- [RFC 8785: JSON Canonicalization Scheme (JCS)](https://datatracker.ietf.org/doc/html/rfc8785) — Review canonical JSON requirements before settling the root identity encoding.

## Applicable guardrails

- **The plan’s “## Plan intent” and step intent** — Make this module the deterministic authority for an enrolled root only; do not add candidate review or promotion behavior.

- **The plan’s “## Scope guardrails”, binary observables** — Preserve and verify exact stored bytes and identities. Do not use semantic equivalence, timestamps, or directory order as identity or selection inputs.

- **The plan’s “## Scope guardrails”, allowed behavior changes and allowed reorganization** — Add the enrollment and accepted-head boundary without changing unversioned readers or reorganizing unrelated roadmap artifact code.

- **The plan’s “## Scope guardrails”, model and promotion authority** — Keep enrollment fully deterministic. It must not accept model output, move a later accepted head, or create review authority.

- **The plan’s “## Out of scope”, recovery and version management** — Reuse the existing journal recovery primitive only for recorded initial-root files; do not add retention, garbage collection, history UI, concurrency handling, or bulk migration.

## Deferred

- Routing `plan_tool/roadmap_view.py:load_roadmap()` through accepted-head resolution — Step 9 owns the one downstream reader conversion.

- Candidate materialization metadata, immutable review seals, and accepted-head replacement after approval — Steps 5, 7, and 8 own those lifecycle stages; step 6 stores candidate bytes through this step's shared version contract.

- Refusal by current in-place writers — Step 10 owns the legacy-writer fence after this module can identify enrollment.

- CLI arguments and the end-to-end command path — Step 11 owns the operator surface.

- Generalizing `plan_tool/roadmap_evidence_store.py:publish_evidence()` into a shared version store — That is a cross-module storage refactor and exceeds this root-enrollment proof.
