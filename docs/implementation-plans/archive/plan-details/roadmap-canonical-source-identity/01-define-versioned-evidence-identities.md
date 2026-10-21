> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 1 — Define versioned evidence identities, issuance, and compatibility from the published baseline

## Summary

Add one redacted canonical-source identity and version-aware receipt and impact-analysis contracts. Update `plan_tool/roadmap_source_identity.py`, `plan_tool/roadmap_escalation.py`, `plan_tool/roadmap_impact_analysis.py`, and `plan_tool/roadmap_structural_revision.py` while keeping version-1 evidence readable. The key decision is that version 2 records canonical freshness separately from immutable raw provenance; version 1 never receives an inferred identity. On green, both versions retain immutable final names, and structural evidence accepts only a matching-version pair.

## Table of Contents

- [Summary](#summary) — Reviewer-level outcome and contract boundary.
- [Table of Contents](#table-of-contents) — Links to the detail sections.
- [Why](#why) — The missing distinction between provenance and freshness.
- [Input](#input) — Existing baseline, evidence, and pair-binding contracts.
- [Files (creates vs edits)](#files-creates-vs-edits) — Scoped production and test changes.
- [Implementation](#implementation) — Versioned identities, compatibility, and pair rules.
- [Tests](#tests) — Focused contract and compatibility coverage.
- [Acceptance criteria](#acceptance-criteria) — Observable completion conditions.
- [References](#references) — Canonical-value and digest references.
- [Applicable guardrails](#applicable-guardrails) — Reader-only and compatibility limits.
- [Deferred](#deferred) — Capture, issuance, and reader work owned by later steps.

## Why

`plan_tool/roadmap_source_identity.py:BaselineRecord` already binds writer-published stage semantics, while `plan_tool/roadmap_escalation.py:ReceiptSource` and `plan_tool/roadmap_impact_analysis.py:ImpactSnapshotEvidence` retain raw byte digests only. The version-1 contracts therefore cannot represent unchanged parsed semantics after a presentation-only source change. Define the missing identity once, then let persisted evidence retain both facts without changing the source or granting baseline authority to a reader.

## Input

- **Published baseline:** Use `plan_tool/roadmap_source_identity.py:BaselineRecord`, `render_baseline_record`, `load_baseline_record`, and `compare_baseline` as the source of canonical identity facts. An identity is valid only when the baseline is bound to its roadmap slug, stage key, and format version.

- **Receipt contract:** Preserve the public receipt boundary in `plan_tool/roadmap_escalation.py:EscalationReceipt`, `build_receipt`, `parse_receipt`, `render_receipt`, `receipt_semantic_id`, and `receipt_semantic_id_from_facts`.

- **Analysis contract:** Preserve canonical rendering, final-name binding, and collision handling in `plan_tool/roadmap_impact_analysis.py:ImpactAnalysis`, `ImpactReceiptEvidence`, `ImpactSnapshotEvidence`, `build_impact_analysis`, and `classify_existing_impact_analysis`.

- **Structural pair binding:** Extend only `plan_tool/roadmap_structural_revision.py:_require_pair_binding` in this step. Step 3 owns live source admission in `plan_tool/roadmap_structural_revision.py:load_structural_revision_preflight`.

## Files (creates vs edits)

- **New files:** None.

- **Existing files (edits only):**
  - `plan_tool/roadmap_source_identity.py` — Define and validate the closed redacted identity derived from a published baseline.
  - `plan_tool/roadmap_escalation.py` — Support closed version-1 and version-2 receipt forms, semantic IDs, and canonical parsing and rendering.
  - `plan_tool/roadmap_impact_analysis.py` — Support version-matched receipt and snapshot evidence in closed analysis forms and semantic IDs.
  - `plan_tool/roadmap_structural_revision.py` — Reject incompatible evidence versions and conflicting retained version-2 identity facts in an exact pair.
  - `tests/test_roadmap_source_identity.py` — Cover identity content, validation, redaction, and module boundaries.
  - `tests/test_roadmap_escalation.py` — Cover both receipt versions, semantic IDs, and invalid hybrid payloads.
  - `tests/test_roadmap_impact_analysis.py` — Cover version-matched analysis evidence and unchanged version-1 behavior.
  - `tests/test_roadmap_structural_revision.py` — Cover exact-pair version compatibility without widening structural authority.

## Implementation

- **Define one complete canonical identity.** Add a frozen redacted value in `plan_tool/roadmap_source_identity.py` with exactly `source_identity_version`, `roadmap_slug`, `stage_key`, `format_version`, and the baseline semantic `digest`. Do not retain the projection, feedback, source text, or raw source digest.

- **Validate at the baseline boundary.** Derive the value only from a `BaselineRecord` that passes the same checks used by `render_baseline_record` and `load_baseline_record`. Compare the five fields as one value; do not offer a smaller matching rule for a caller to select.

- **Keep source identity a leaf contract.** Preserve the boundary asserted by `tests/test_roadmap_source_identity.py:test_source_identity_module_does_not_import_orchestrators`. This module defines values and validation only; it does not inspect artifacts, publish evidence, or repair a pending generation.

- **Keep raw provenance independent.** Retain `ReceiptSource.sha256` and the raw stage digests in `ImpactSnapshotEvidence` unchanged. A canonical identity proves baseline-equal semantics; it neither replaces nor recalculates immutable raw provenance.

- **Make receipt versions closed and explicit.** Extend `plan_tool/roadmap_escalation.py:EscalationReceipt` and its semantic-field validation so version 1 keeps its current field set and version-1 semantic preimage, while version 2 requires the complete selected-stage canonical identity. Do not encode the absent version-1 identity as `null`; reject unknown fields, missing version-2 identity fields, and mixed-version payloads.

- **Preserve the public receipt boundary.** Keep `EscalationReceipt`, `parse_receipt`, `render_receipt`, `validate_receipt_final_name`, and `validate_receipt_source_path` usable by current callers. One approach is internal version-specific validation behind the existing public type boundary, rather than forcing unrelated callers to branch on a new concrete type.

- **Make construction version-aware without hidden fallback.** Keep `build_receipt` able to form legacy version-1 values for existing exact-raw workflows, but require an explicit, validated canonical identity for version 2. Do not derive version 2 from raw bytes, filesystem reads, or a missing identity. Step 3 changes live receipt issuance to select the version-2 path and refuse when that path cannot be admitted.

- **Bind every retained version-2 fact into receipt identity.** Update `receipt_semantic_preimage`, `receipt_semantic_id`, and `receipt_semantic_id_from_facts` so version 2 includes the full canonical identity in its semantic preimage. Keep `created_at` outside both versions’ semantic IDs and retain the current version-1 final names.

- **Make analysis evidence version-matched.** Update `plan_tool/roadmap_impact_analysis.py:ImpactReceiptEvidence`, `ImpactSnapshotEvidence`, `_ImpactAnalysisSemanticFields`, and their validators so:
  - Version 1 retains raw snapshot evidence only.
  - Version 2 retains the selected receipt identity and one canonical identity per configured stage in stage order.
  - The analysis version, retained receipt version, and snapshot variant agree.
  - The version-2 identity for the selected stage equals the receipt identity.

- **Keep analysis construction and reuse strict.** Preserve `build_impact_analysis` for a version-1 receipt and current raw snapshot shape. Version 2 requires version-2 snapshot evidence supplied by step 2; do not upgrade a legacy receipt or infer canonical facts from its raw digest. Keep `parse_impact_analysis`, `render_impact_analysis`, `impact_analysis_semantic_id`, `validate_impact_analysis_final_name`, and `classify_existing_impact_analysis` as exact canonical-byte checks.

- **Fail closed at the structural pair boundary.** Extend `plan_tool/roadmap_structural_revision.py:_require_pair_binding` to require matching receipt and analysis versions. For version 2, also require the analysis’s retained selected-stage identity to equal the receipt identity. Preserve the existing final-name, selector, target, reason, raw source-digest, route, and selected-artifact checks; do not read a baseline or mutate source state here.

- **Keep later readers staged.** Step 2 supplies version-2 capture through `plan_tool/roadmap_impact_snapshot.py:capture_roadmap_impact_snapshot` and consumes it through `plan_tool/roadmap_impact_run.py:current_impact_analysis`. Step 3 updates `plan_tool/roadmap_escalation_run.py:run_roadmap_escalation_receipt` and `plan_tool/roadmap_escalation_run.py:current_escalation_receipt` to choose and judge the version-specific receipt path.

## Tests

### Tests for this step

- `test_canonical_source_identity_copies_all_five_validated_binding_fields` — asserts the identity contains exactly the source-identity version, slug, stage key, format version, and semantic digest.

- `test_canonical_source_identity_rejects_invalid_baseline_facts` — asserts construction cannot bless malformed or incorrectly bound baseline data.

- `test_canonical_source_identity_excludes_projection_feedback_and_raw_provenance` — asserts canonical freshness retains no source content or raw-digest substitute.

- `test_source_identity_module_does_not_import_orchestrators` — keeps the identity contract independent of issuance and reader orchestration.

- `test_receipt_v1_round_trips_with_its_existing_closed_schema` — preserves the version-1 payload, semantic ID, and final name with no canonical identity field.

- `test_receipt_v2_requires_complete_canonical_source_identity` — asserts every retained canonical field is required and strictly typed.

- `test_receipt_v2_semantic_id_includes_canonical_source_identity` — asserts identity changes affect the version-2 final name while `created_at` does not.

- `test_receipt_semantic_id_from_facts_reconstructs_version2_identity` — proves retained redacted facts are sufficient to verify a version-2 receipt without reading a baseline projection.

- `test_receipt_rejects_version_identity_hybrids` — rejects version-1 payloads with version-2 fields and version-2 payloads missing required identity facts.

- `test_analysis_v1_round_trips_without_inferred_canonical_identity` — preserves the current version-1 rendering and semantic final name.

- `test_analysis_v2_binds_receipt_and_ordered_snapshot_identities` — asserts version-2 analysis evidence retains all stage identities in order and matches the selected receipt identity.

- `test_analysis_rejects_mixed_receipt_snapshot_and_analysis_versions` — rejects every analysis combination that crosses the version boundary.

- `test_analysis_semantic_id_includes_version2_identity_facts` — asserts a retained canonical identity change produces a different analysis final name.

- `test_preflight_pair_allows_matching_version1_evidence` — proves the exact-pair check preserves legacy compatibility.

- `test_preflight_pair_rejects_mixed_evidence_versions` — proves a version-1 receipt cannot authorize a version-2 analysis, or the reverse.

- `test_preflight_pair_rejects_conflicting_version2_canonical_identity` — proves matching version numbers alone do not authorize mismatched selected-stage identities.

Every listed test must be green before this step is complete.

## Acceptance criteria

- A canonical source identity contains exactly source-identity version, roadmap slug, stage key, format version, and semantic digest, with no projection, feedback, source text, or raw digest.

- The identity can be created only from a validated `plan_tool/roadmap_source_identity.py:BaselineRecord`.

- `plan_tool/roadmap_escalation.py:parse_receipt` accepts existing version-1 finals unchanged and rejects malformed or mixed-version receipt payloads.

- A version-2 receipt requires a complete canonical identity, retains its raw source digest, and includes the canonical identity in its semantic final name.

- `plan_tool/roadmap_impact_analysis.py:parse_impact_analysis` preserves version-1 canonical bytes and rejects version-mismatched or identity-mismatched version-2 evidence.

- `plan_tool/roadmap_structural_revision.py:_require_pair_binding` refuses a mixed-version receipt-analysis pair before it can authorize structural work.

- The focused roadmap source-identity, escalation, impact-analysis, and structural-revision tests pass, followed by `uv run pytest tests/ -q -n auto`.

## References

- [YAML Ain’t Markup Language (YAML™) Revision 1.2.2https: — Use representation-level semantics to distinguish parsed values from presentation details.

- [hashlib — Secure Hashes and Message Digestshttps: — Use SHA-256 for immutable raw provenance and versioned semantic identities.

## Applicable guardrails

- **The plan’s “## Plan intent”, reader-owned freshness** — Keep canonical freshness separate from raw provenance so later readers can refuse unsafe state without changing it.

- **The plan’s “## Step intent”, version-matched evidence** — Define compatible evidence construction and reuse without changing ordinary or local revision admission.

- **The plan’s “## Out of scope”, baseline ownership** — Do not add enrollment, publication, recovery, repair, migration, or source-normalization behavior to this step.

- **The plan’s “## Out of scope”, strict generated evidence** — Preserve immutable receipt and analysis finals and their strict malformed-input rejection.

## Deferred

- Version-2 snapshot capture and recheck — Step 2 updates `plan_tool/roadmap_impact_snapshot.py:capture_roadmap_impact_snapshot` and `plan_tool/roadmap_impact_run.py:current_impact_analysis` to supply and consume version-2 snapshot identities.

- Version-2 receipt issuance and inspection — Step 3 updates `plan_tool/roadmap_escalation_run.py:run_roadmap_escalation_receipt` and `plan_tool/roadmap_escalation_run.py:current_escalation_receipt` to use reader admission before creating or exposing version-2 receipts.

- Baseline-aware structural currentness — Step 3 extends `plan_tool/roadmap_structural_revision.py:load_structural_revision_preflight` beyond this step’s exact-pair compatibility check.

- Public evidence documentation — Step 4 publishes the landed versioned reader contract after capture and admission behavior is complete.
