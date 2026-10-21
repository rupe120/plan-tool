> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 1 — Define versioned evidence identities, issuance, and compatibility from the published baseline

## Summary

Add a redacted canonical-baseline identity and version-aware receipt and impact-analysis contracts. Update `plan_tool/roadmap_source_identity.py`, `plan_tool/roadmap_escalation.py`, `plan_tool/roadmap_impact_analysis.py`, and `plan_tool/roadmap_structural_revision.py` while preserving readable version-1 evidence. The key decision is that version 2 carries canonical freshness separately from the existing raw source digest; version 1 never gains an inferred identity. On green, both versions parse and retain immutable final names, while a structural pair must use one matching evidence version.

## Table of Contents

- [Summary](#summary) — Reviewer-level outcome and contract boundary.
- [Table of Contents](#table-of-contents) — Links to the detail sections.
- [Why](#why) — The missing versioned distinction between provenance and freshness.
- [Input](#input) — Existing baseline, receipt, analysis, and pair-binding contracts.
- [Files (creates vs edits)](#files-creates-vs-edits) — Scoped production and test changes.
- [Implementation](#implementation) — Versioned identity, compatibility, and exact-pair rules.
- [Tests](#tests) — Focused contract and compatibility coverage.
- [Acceptance criteria](#acceptance-criteria) — Observable completion conditions.
- [References](#references) — Canonical-value and digest references.
- [Applicable guardrails](#applicable-guardrails) — Reader-only and compatibility limits.
- [Deferred](#deferred) — Capture, issuance, and reader work owned by later steps.

## Why

`plan_tool/roadmap_source_identity.py:BaselineRecord` already proves writer-published stage semantics, while `plan_tool/roadmap_escalation.py:ReceiptSource` and `plan_tool/roadmap_impact_analysis.py:ImpactSnapshotEvidence` retain only raw digests. The current version-1-only models cannot say that a stage’s parsed semantics still equal its published baseline when presentation bytes change. Define that missing identity once, then make the persisted receipt, analysis, and structural-pair contracts distinguish it from raw provenance without changing any source state.

## Input

- **Published baseline:** Use `plan_tool/roadmap_source_identity.py:BaselineRecord`, `load_baseline_record`, and `compare_baseline` as the source of the canonical identity. A valid identity comes only from a fully validated record bound to its roadmap slug, stage key, and format version.
- **Receipt contract:** Preserve the closed, immutable receipt shape implemented by `plan_tool/roadmap_escalation.py:EscalationReceipt`, `build_receipt`, `parse_receipt`, `render_receipt`, and `receipt_semantic_id_from_facts`.
- **Analysis contract:** Preserve exact canonical rendering and final-name binding in `plan_tool/roadmap_impact_analysis.py:ImpactAnalysis`, `ImpactReceiptEvidence`, `ImpactSnapshotEvidence`, `build_impact_analysis`, and `classify_existing_impact_analysis`.
- **Structural pair binding:** Extend only the evidence-version rule in `plan_tool/roadmap_structural_revision.py:_require_pair_binding`. Step 3 owns live source admission and reader-side currentness.

## Files (creates vs edits)

- **New files:** None.

- **Existing files (edits only):**
  - `plan_tool/roadmap_source_identity.py` — Define the closed, redacted canonical-baseline identity and validate construction from `BaselineRecord`.
  - `plan_tool/roadmap_escalation.py` — Support immutable version-1 and version-2 receipt shapes, semantic identities, parsing, and canonical rendering.
  - `plan_tool/roadmap_impact_analysis.py` — Support version-matched receipt and snapshot evidence in closed analysis shapes and semantic preimages.
  - `plan_tool/roadmap_structural_revision.py` — Require the parsed receipt and analysis in an exact pair to use compatible evidence versions and matching retained identity facts.
  - `tests/test_roadmap_source_identity.py` — Cover identity contents, validation, redaction, and leaf-module discipline.
  - `tests/test_roadmap_escalation.py` — Cover both receipt versions, version-specific semantic IDs, and invalid hybrid shapes.
  - `tests/test_roadmap_impact_analysis.py` — Cover version-matched analysis evidence and preserved version-1 behavior.
  - `tests/test_roadmap_structural_revision.py` — Cover exact-pair version compatibility without widening structural selection.

## Implementation

- **Define one complete canonical identity.** Add a frozen, redacted value in `plan_tool/roadmap_source_identity.py` that copies exactly the published baseline’s source-identity version, roadmap slug, stage key, format version, and semantic digest. Do not retain the baseline projection, feedback, raw artifact text, or raw digest in this value.

- **Validate at the baseline boundary.** Derive the identity only from a `BaselineRecord` that passes the same validation used by `render_baseline_record` and `load_baseline_record`. Treat all five fields as one equality unit; do not let a caller compare or select a smaller subset.

- **Keep source identity a leaf contract.** Preserve the import boundary checked by `tests/test_roadmap_source_identity.py:test_source_identity_module_does_not_import_orchestrators`. This module defines values and validation only; it does not load roadmap artifacts, issue evidence, publish baselines, or repair pending publication state.

- **Make receipt versions closed and explicit.** Evolve `plan_tool/roadmap_escalation.py:EscalationReceipt` and its semantic-field validation so version 1 keeps its current field set and semantic preimage, while version 2 requires the canonical identity for the selected stage. Do not represent the missing version-1 identity as `null`, and reject unknown fields, missing version-2 identity fields, or a version-1/2 hybrid payload.

- **Keep version-1 storage stable.** Preserve `parse_receipt`, `render_receipt`, `receipt_semantic_preimage`, `receipt_semantic_id`, `validate_receipt_final_name`, and the exclusion of `created_at` from the receipt semantic ID for version 1. Existing version-1 final names must remain readable and reusable through their raw-evidence path.

- **Bind version-2 receipt identity into the final name.** Make a version-2 receipt’s canonical identity part of the receipt semantic preimage so a changed baseline identity produces a distinct immutable final name. Keep `ReceiptSource.sha256` as raw provenance; it is not replaced or recalculated from the canonical identity.

- **Prepare analysis for matching evidence versions.** Update `plan_tool/roadmap_impact_analysis.py:ImpactReceiptEvidence`, `ImpactSnapshotEvidence`, `_ImpactAnalysisSemanticFields`, and the semantic-ID helpers so a version-2 analysis retains the selected receipt identity and the stage-ordered snapshot identities needed to verify it. Require the analysis, receipt evidence, and snapshot evidence to agree on one version, and require the selected snapshot identity to equal the receipt identity.

- **Preserve the version-1 analysis path.** Keep `build_impact_analysis` able to construct the current version-1 analysis from a version-1 receipt and raw snapshot evidence. Step 2 supplies version-2 snapshot capture and candidate construction; do not infer version 2 from a version-1 receipt or raw artifact digests.

- **Keep final reuse exact.** Preserve `parse_impact_analysis`, `render_impact_analysis`, `impact_analysis_semantic_id`, `validate_impact_analysis_final_name`, and `classify_existing_impact_analysis` as canonical-byte checks. A matching semantic identity does not relax persisted receipt or analysis byte validation.

- **Fail closed on structural version mismatch.** Extend `plan_tool/roadmap_structural_revision.py:_require_pair_binding` to reject a receipt-analysis pair that mixes evidence versions or carries conflicting version-2 identity facts. Preserve the existing selector, target, reason, raw source-digest, exact-final-name, route, and selected-artifact boundaries; do not add baseline reads or source mutation here.

- **Keep issuance and reader behavior staged.** `plan_tool/roadmap_escalation_run.py:run_roadmap_escalation_receipt`, `plan_tool/roadmap_impact_snapshot.py:capture_roadmap_impact_snapshot`, and `plan_tool/roadmap_impact_run.py:current_impact_analysis` consume these contracts in later steps. Keep compatibility helpers explicit enough that those callers can choose a version without a hidden fallback.

## Tests

### Tests for this step

- `test_baseline_identity_copies_all_five_validated_binding_fields` — asserts the redacted identity contains exactly the source-identity version, slug, stage key, format version, and semantic digest.
- `test_baseline_identity_rejects_an_invalid_or_unbound_baseline_record` — asserts identity construction cannot bless malformed or wrongly bound baseline data.
- `test_baseline_identity_excludes_projection_feedback_and_raw_source_data` — asserts canonical freshness retains no source content or raw-provenance substitute.
- `test_source_identity_module_does_not_import_orchestrators` — keeps the identity contract independent of issuance and reader orchestration.
- `test_receipt_v1_round_trips_as_a_frozen_closed_value` — keeps the existing version-1 payload, semantic ID, and final name readable without a canonical identity field.
- `test_receipt_v2_requires_a_complete_canonical_source_identity` — asserts every canonical identity field is required and strictly typed for version 2.
- `test_receipt_semantic_id_changes_with_version2_canonical_identity` — asserts version-2 identity participates in the semantic preimage while `created_at` remains outside it.
- `test_receipt_rejects_version_identity_hybrids` — rejects version-1 payloads with version-2 fields and version-2 payloads missing required identity facts.
- `test_analysis_v1_round_trips_without_inferred_canonical_identity` — preserves the current version-1 analysis rendering and semantic final name.
- `test_analysis_v2_binds_selected_receipt_and_snapshot_identities` — asserts the selected stage identity matches across version-2 receipt and snapshot evidence.
- `test_analysis_rejects_mixed_receipt_snapshot_and_analysis_versions` — rejects every analysis combination that crosses the version boundary.
- `test_analysis_semantic_id_includes_versioned_identity_facts` — asserts changes to retained version-2 identity facts change the analysis final name.
- `test_preflight_pair_allows_matching_version1_evidence` — proves the exact-pair check preserves legacy compatibility.
- `test_preflight_pair_rejects_mixed_evidence_versions` — proves a version-1 receipt cannot authorize a version-2 analysis, or the reverse.
- `test_preflight_pair_rejects_conflicting_version2_canonical_identity` — proves matching version numbers alone do not authorize a pair with different selected-stage identities.

Every listed test must be green before this step is complete.

## Acceptance criteria

- A canonical baseline identity contains exactly source-identity version, roadmap slug, stage key, format version, and semantic digest, with no projection, feedback, source text, or raw digest.
- The identity can be created only from a validated `plan_tool/roadmap_source_identity.py:BaselineRecord`.
- `plan_tool/roadmap_escalation.py:parse_receipt` accepts existing version-1 finals unchanged and rejects malformed or mixed-version receipt payloads.
- A version-2 receipt requires a complete canonical identity and includes it in its semantic final name while retaining its raw source digest.
- `plan_tool/roadmap_impact_analysis.py:parse_impact_analysis` preserves version-1 canonical bytes and rejects version-mismatched or identity-mismatched version-2 analysis evidence.
- `plan_tool/roadmap_structural_revision.py:_require_pair_binding` refuses mixed-version receipt-analysis pairs before they can authorize structural work.
- The focused roadmap source-identity, escalation, impact-analysis, and structural-revision test files pass, followed by `uv run pytest tests/ -q -n auto`.

## References

- [YAML Ain’t Markup Language (YAML™) Revision 1.2.2](https://yaml.org/spec/1.2.2/) — Use representation equality to keep presentation-only changes outside canonical stage semantics.
- [hashlib — Secure Hashes and Message Digests](https://docs.python.org/3.13/library/hashlib.html) — Use SHA-256 consistently for immutable provenance and versioned semantic identities.

## Applicable guardrails

- **The plan’s “## Plan intent”, reader-owned freshness** — Keep canonical freshness separate from raw provenance so later readers can refuse unsafe source state without changing it.
- **The plan’s “## Step intent”, compatibility boundary** — Define version-matched evidence creation and reuse without changing ordinary or local revision admission.
- **The plan’s “## Out of scope”, writer ownership** — Do not add baseline enrollment, publication, recovery, repair, migration, or source-normalization behavior to this step’s files.
- **The plan’s “## Out of scope”, strict generated evidence** — Keep immutable receipt and analysis finals, malformed-scalar rejection, and generated structural candidate validation strict.

## Deferred

- Version-2 snapshot capture and recheck — Step 2 updates `plan_tool/roadmap_impact_snapshot.py:capture_roadmap_impact_snapshot` and `plan_tool/roadmap_impact_run.py:current_impact_analysis` to supply and consume the new snapshot identity.
- Version-2 receipt issuance and live reader admission — Step 3 updates `plan_tool/roadmap_escalation_run.py:run_roadmap_escalation_receipt` and the escalation selection boundary.
- Baseline-aware structural currentness — Step 3 extends `plan_tool/roadmap_structural_revision.py:load_structural_revision_preflight` beyond this step’s exact-pair version check.
- Public contract documentation — Step 4 updates the roadmap format, data contract, and architecture references after the reader behavior lands.
