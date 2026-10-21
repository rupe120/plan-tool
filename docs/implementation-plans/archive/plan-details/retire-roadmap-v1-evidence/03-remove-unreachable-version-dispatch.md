> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 3 — Remove unreachable version dispatch from receipt admission and inspection while keeping immutable receipt publication unchanged

## Summary

Remove the receipt-only version-1 freshness and serialization branches from `plan_tool/roadmap_source_identity.py`, `plan_tool/roadmap_escalation.py`, `plan_tool/roadmap_escalation_selection.py`, and `plan_tool/roadmap_escalation_run.py`. Receipt admission and inspection will use the single baseline-identity rule established by step 2, while receipt records continue to persist `schema_version: 2`, raw source provenance, and canonical source identity. Keep the existing reader guard, admission recheck, and immutable evidence publication flow unchanged. On green, a valid version-2 receipt remains fresh across presentation-only source changes, and an unarchived version-1 receipt is invalid with no handoff.

## Table of Contents

- [Summary](#summary) — Reviewer overview of the receipt-only cleanup and preserved writer behavior.
- [Table of Contents](#table-of-contents) — Links to each section in this detail.
- [Why](#why) — Why receipt code must stop carrying a second freshness rule.
- [Input](#input) — Upstream schema and shared-caller boundaries that constrain the refactor.
- [Files (creates vs edits)](#files-creates-vs-edits) — Production and test files changed in this step.
- [Implementation](#implementation) — Single-rule admission, inspection, and publication requirements.
- [Tests](#tests) — Focused regression and refusal coverage.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Validation, serialization, and test-matrix references.
- [Applicable guardrails](#applicable-guardrails) — Scope limits that preserve the surviving contract.
- [Deferred](#deferred) — Adjacent reader cleanup owned by later steps.

## Why

Step 2 makes version 2 the only legal receipt schema, but receipt code still contains branches that select version 1’s raw-digest rule and omit version-2 identity fields. Those unreachable branches can drift from the baseline-backed rule that creation and inspection must share. Remove them now so receipt admission, receipt currentness, and receipt identity all describe the same surviving contract without changing how immutable finals are published or reused.

## Input

- **Step 2’s schema outcome:** Step 2 establishes version 2 as the only legal roadmap-evidence schema. Treat a version-1 receipt as invalid at the reader boundary rather than attempting admission, conversion, or route selection.

- **Receipt contract:** `plan_tool/roadmap_escalation.py:EscalationReceipt`, `build_receipt`, `parse_receipt`, `receipt_semantic_preimage`, and `render_receipt` retain the persisted discriminator, `source.sha256`, canonical source identity, semantic ID, and canonical JSON representation.

- **Shared currentness boundary:** `plan_tool/roadmap_source_identity.py:admitted_source_is_current` is also called by `plan_tool/roadmap_impact_analysis.py:_receipt_matches_captured_artifact`. Step 4 owns that impact lifecycle, so keep this helper callable by the existing impact path while removing its version-1 decision.

- **Immutable store boundary:** `plan_tool/roadmap_evidence_store.py:publish_evidence` publishes a new final once or returns the exact existing bytes. This step relies on that behavior but does not change the evidence-store module.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `plan_tool/roadmap_source_identity.py` — Remove the raw-digest currentness branch from `admitted_source_is_current` while preserving the shared helper and baseline/journal protocol.
  - `plan_tool/roadmap_escalation.py` — Remove conditional version-1 receipt shape and hash handling so valid receipts always require and serialize canonical source identity.
  - `plan_tool/roadmap_escalation_selection.py` — Make `admit_versioned_artifact_source` admit only baseline-backed canonical or presentation-only noncanonical sources.
  - `plan_tool/roadmap_escalation_run.py` — Remove receipt preflight and inspection dispatch that exists only to select a schema-specific admission or currentness rule.
  - `tests/test_roadmap_source_identity.py` — Replace the version-dispatch test with the one surviving canonical-identity currentness rule.
  - `tests/test_roadmap_escalation.py` — Remove version-1 receipt-shape expectations and preserve version-2 semantic-ID, raw-provenance, and canonical-rendering checks.
  - `tests/test_roadmap_escalation_selection.py` — Replace raw-digest admission coverage with baseline-backed admission and presentation-drift coverage.
  - `tests/test_roadmap_escalation_run.py` — Cover version-2 publication, inspection, cache behavior, and legacy-reader refusal.
  - `tests/cli/test_roadmap_cmd.py` — Rebase receipt-view fixtures on version 2 and prove the view renders an unarchived legacy receipt as invalid without a handoff.

## Implementation

- **Foundational logic: baseline-identity receipt currentness.** Make `plan_tool/roadmap_source_identity.py:admitted_source_is_current` compare canonical source identities only. A matching identity remains current even when `source.sha256` changes due to presentation-only drift; a changed identity remains resolved. Remove the raw-digest version-1 decision without merging this helper with admission, rendering, or full-byte comparison.

- **Keep the shared helper compatible with step 4.** `plan_tool/roadmap_impact_analysis.py:_receipt_matches_captured_artifact` remains outside this step’s file set. Retain a call shape that lets that version-2-only caller stay green until step 4 removes its lifecycle-specific remnants; do not widen this step into the impact-analysis refactor.

- **Require one receipt shape.** In `plan_tool/roadmap_escalation.py:EscalationReceipt`, `_ReceiptSemanticFields`, `_receipt_semantic_fields`, `_canonical_source_identity_fields`, and `_receipt_hash_fields`, treat canonical source identity as present for every valid receipt. Keep `schema_version` and `source.sha256` in the persisted receipt, but keep the existing version-2 semantic-ID rule that excludes the raw digest from the hash input.

- **Preserve immutable version-2 publication.** Keep `plan_tool/roadmap_escalation_run.py:NEW_RECEIPT_SCHEMA_VERSION`, `run_roadmap_escalation_receipt`, `_same_receipt_admission`, and the call to `publish_evidence` on the established version-2 path. Preserve the reader guard, the second preflight before publication, canonical receipt bytes, created-versus-reused outcomes, and the rule that source roadmap artifacts are never rewritten.

- **Use baseline-backed admission everywhere receipt code reads a source.** In `plan_tool/roadmap_escalation_selection.py:admit_versioned_artifact_source`, retain admission for both `CanonicalArtifactSnapshot` and `NoncanonicalArtifactSnapshot` only when `admit_baseline_backed_source` confirms the selected stage. Keep missing, pending, invalid, or semantically changed baselines rejected, and retain presentation-only drift as admissible.

- **Remove receipt-run dispatch, not receipt safeguards.** Simplify `plan_tool/roadmap_escalation_run.py:_resolve_preflight` and `current_escalation_receipt` so they no longer choose behavior by receipt schema version. The inspection cache should represent the one surviving stage admission rather than separate version routes.

- **Fail closed before a legacy receipt reaches source inspection.** `plan_tool/roadmap_escalation_run.py:current_escalation_receipt` must return `("invalid", None)` for an unarchived version-1 receipt. The result must not expose a target or handoff, mark the record fresh or resolved, select feedback, or populate a source-admission cache entry.

- **Keep the view’s safe invalid result.** `plan_tool/cli/roadmap_cmd.py:_render_escalation_receipts` already renders an invalid result as a status and relative location only. Do not add CLI syntax or change that safe rendering; update its fixtures to prove the legacy-reader result reaches it.

## Tests

### Tests for this step

- `tests/test_roadmap_source_identity.py:test_admitted_source_is_current_uses_only_canonical_identity` — asserts matching canonical identities are current despite differing raw digests, while a changed identity is resolved.

- `tests/test_roadmap_escalation.py:test_version2_receipt_requires_and_serializes_canonical_source_identity` — asserts the sole receipt shape retains `schema_version: 2`, `source.sha256`, and canonical source identity.

- `tests/test_roadmap_escalation.py:test_version2_receipt_semantic_id_excludes_raw_source_digest` — asserts presentation-only raw-digest changes keep the same final name while a changed canonical identity changes it.

- `tests/test_roadmap_escalation_selection.py:test_receipt_source_admission_requires_baseline_identity_and_allows_presentation_drift` — asserts canonical and presentation-only noncanonical sources admit only through the matching selected-stage baseline.

- `tests/test_roadmap_escalation_selection.py:test_receipt_source_admission_rejects_missing_pending_invalid_or_changed_baseline` — keeps every rejected baseline state outside receipt selection.

- `tests/test_roadmap_escalation_run.py:test_receipt_creation_rechecks_baseline_admission_before_immutable_publication` — asserts a changed source between preflights produces no final or handoff.

- `tests/test_roadmap_escalation_run.py:test_current_escalation_receipt_keeps_baseline_equal_presentation_drift_fresh` — asserts inspection uses canonical identity rather than raw source bytes.

- `tests/test_roadmap_escalation_run.py:test_current_escalation_receipt_rejects_legacy_record_before_source_admission` — asserts a version-1 record returns `invalid` and no receipt, handoff, or cached admission.

- `tests/test_roadmap_escalation_run.py:test_receipt_publication_reuses_only_the_exact_existing_final` — keeps created and reused outcomes bound to canonical receipt bytes without mutating the source artifact.

- `tests/cli/test_roadmap_cmd.py:test_escalation_view_marks_legacy_receipt_invalid_without_handoff` — asserts the view shows `status: invalid` and a relative location, never receipt details, target, or handoff.

- `tests/cli/test_roadmap_cmd.py:test_escalation_view_snapshots_one_shared_version2_source_once` — keeps the shared-source inspection cache behavior after version-specific cache partitioning is removed.

Every listed test and `uv run pytest tests/ -q -n auto` must be green before this step is complete.

## Acceptance criteria

- `plan_tool/roadmap_source_identity.py:admitted_source_is_current` has one canonical-source-identity currentness rule and no raw-digest version-1 branch.

- `plan_tool/roadmap_escalation_selection.py:admit_versioned_artifact_source` admits only selected-stage baseline-backed sources and still admits baseline-equal presentation-only drift.

- `plan_tool/roadmap_escalation.py:render_receipt` emits `schema_version: 2`, raw `source.sha256`, and canonical source identity for every valid receipt.

- A valid version-2 receipt keeps its existing semantic-ID and immutable final-name behavior across presentation-only source changes.

- `plan_tool/roadmap_escalation_run.py:current_escalation_receipt` returns `("invalid", None)` for an unarchived version-1 record before source admission or feedback selection.

- The escalation view renders that legacy record as invalid without a handoff, target, selector, or fresh receipt fields.

- `plan_tool/roadmap_escalation_run.py:run_roadmap_escalation_receipt` retains its reader guard, second admission check, and create-or-reuse behavior around `publish_evidence`.

- `uv run pytest tests/ -q -n auto` passes.

## References

- [Validators | Pydantic Docshttps: — Review strict field and model validation for the single accepted receipt shape.

- [Serialization | Pydantic Docshttps: — Verify required receipt fields remain present in canonical serialized evidence.

- [How to parametrize fixtures and test functionshttps: — Use a compact fixture matrix for valid baseline-backed sources and rejected legacy or baseline states.

## Applicable guardrails

- **The plan’s “## Out of scope”, version-2 semantics and baseline contract:** Preserve the surviving identity, admission, provenance, and presentation-drift behavior while deleting only the alternate receipt path.

- **The plan’s “## Out of scope”, closed consolidation decision:** Keep `plan_tool/roadmap_source_identity.py:admitted_source_is_current` as the shared currentness boundary; do not merge it with admission, comparison, or rendering logic.

- **The plan’s “## Out of scope”, no in-place converter:** Do not add a receipt-upgrade path that edits an immutable version-1 final or invents a canonical identity.

- **The plan’s “## Out of scope”, unrelated receipt-preflight work:** Do not add a new preflight policy, CLI option, or user-facing receipt-creation mode.

- **The plan’s “## Overview”, no new CLI syntax:** Keep `plan_tool/cli/roadmap_cmd.py` behavior limited to the existing invalid-rendering path; this step changes tests, not the command surface.

- **The plan’s “## Out of scope”, structural operation envelope:** Do not alter the independent structural-operation protocol or its version vocabulary while editing shared source-identity code.

## Deferred

- `plan_tool/roadmap_impact_analysis.py:_receipt_matches_captured_artifact` and `plan_tool/roadmap_impact_run.py:current_impact_analysis` cleanup — Step 4 owns the impact-analysis lifecycle’s remaining use of the shared currentness boundary.

- `plan_tool/roadmap_structural_revision.py` and `plan_tool/roadmap_structural_revision_run.py` legacy-evidence cleanup — Step 5 owns structural preflight removal while preserving its journaled replacement flow.
