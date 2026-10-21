> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 2 — Make version 2 the only legal roadmap evidence schema, keep schema_version, and preserve structural journal recovery and replacement

## Summary

Make version 2 the only accepted roadmap-evidence schema in the shared identity, receipt, analysis, and snapshot contracts. Update `plan_tool/roadmap_source_identity.py`, `plan_tool/roadmap_escalation.py`, `plan_tool/roadmap_impact_analysis.py`, `plan_tool/roadmap_impact_snapshot.py`, and `plan_tool/roadmap_structural_revision_run.py` so supported evidence always carries `schema_version: 2` and its required canonical identities. Keep version 2’s existing hashes, raw-digest provenance, baseline admission, journal recovery, and structural replacement behavior unchanged. On green, new and retained version-2 evidence parses as before, while version 1 is rejected at the schema boundary before later steps remove the now-unreachable dispatch code.

## Table of Contents

- [Summary](#summary) — Reviewer overview of the schema gate and preserved publication safeguards.
- [Table of Contents](#table-of-contents) — Links to the detail sections.
- [Why](#why) — Why one legal schema must precede dispatch cleanup.
- [Input](#input) — The retirement record and persisted contracts this step relies on.
- [Files (creates vs edits)](#files-creates-vs-edits) — Production, documentation, and test changes in scope.
- [Implementation](#implementation) — Required version-2-only contract and safety boundaries.
- [Tests](#tests) — Focused regression coverage and the green-before-done gate.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Primary references for strict validation and serialization.
- [Applicable guardrails](#applicable-guardrails) — Plan boundaries that limit this step.
- [Deferred](#deferred) — Later steps that remove unreachable reader dispatch.

## Why

The roadmap evidence contracts currently permit two schemas with different freshness rules, while all new evidence already uses version 2. Keeping version 1 legal lets omitted fields, defaults, and implicit branches select an obsolete rule. This step closes the persisted-contract boundary first, so the later receipt, impact, and structural cleanup steps can delete unreachable code without risking a live version-1 route.

## Input

- **Retirement decision:** Step 1’s `docs/history/roadmap-evidence-v1-retirement.md` supplies the completed inventory and disposition evidence that permits rejecting active version-1 finals. Do not infer a baseline identity or replace an immutable final in this step.

- **Re-confirm the gate before touching the schema boundary.** `plan_tool.schema.Plan.next_runnable_step` advances this step once step 1 is marked done; it does not itself read `docs/history/roadmap-evidence-v1-retirement.md`. Before making any edit in this step, re-read that record and confirm it states an explicit, dated project/roadmap roster, a separate dated consumer roster, a dated named approval of the roster set and disposition table, and zero blocking rows against those rosters. If any of the rosters or the approval is unstated, or any blocking row remains — including a reissued final with an unconfirmed consumer-roster cutover — stop and report back rather than proceeding; a "zero blocking rows" claim with no stated rosters and approval behind it is not a clean record.
- **Receipt contract:** `plan_tool/roadmap_escalation.py:EscalationReceipt`, `_ReceiptSemanticFields`, `build_receipt`, and `parse_receipt` retain `schema_version`, the raw `source.sha256` provenance, and the required `canonical_source_identity`.
- **Analysis contract:** `plan_tool/roadmap_impact_analysis.py:ImpactAnalysis`, `ImpactReceiptEvidence`, `ImpactSnapshotEvidence`, `build_impact_analysis`, and `parse_impact_analysis` retain explicit version-2 nested evidence and the existing semantic-id rules.
- **Snapshot and publication state:** `plan_tool/roadmap_impact_snapshot.py:capture_roadmap_impact_snapshot`, `recheck_roadmap_impact_snapshot`, and `_require_admitted_pending_generation` must keep baseline and pending-generation admission separate from evidence parsing.
- **Structural writer boundary:** `plan_tool/roadmap_structural_revision_run.py:run_structural_revision` must continue to recover a recorded publication generation under `roadmap_writer_guard` before structural preflight and before any replacement path.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `plan_tool/roadmap_source_identity.py` — Restrict `EVIDENCE_SCHEMA_VERSIONS` and `is_supported_evidence_schema_version` to version 2 while preserving `admitted_source_is_current` as the shared currentness entry point for the later cleanup.
  - `plan_tool/roadmap_escalation.py` — Make version 2 the default and sole valid receipt schema while keeping `schema_version`, raw source provenance, canonical identity, semantic-id, and canonical-rendering rules.
  - `plan_tool/roadmap_impact_analysis.py` — Require explicit version-2 receipt and snapshot evidence fields, remove missing-version compatibility defaults, and keep the version-2 semantic and reuse inputs unchanged.
  - `plan_tool/roadmap_impact_snapshot.py` — Default snapshot capture to version 2 and reject every other evidence version before source capture or baseline admission.
  - `plan_tool/roadmap_structural_revision_run.py` — Make `_preflight_is_canonical` reject a non-version-2 snapshot explicitly while preserving recovery and publication ordering.
  - `ROADMAP_FORMAT.md` — Replace the dual receipt and analysis evidence references, inventories, and examples with the single version-2 contract; retain the independent structural-operation `version: 1` reference.
  - `DATA_CONTRACT.md` — Update `## Version-evolution policy` to point roadmap-evidence retirement at the completed step-1 record and its fail-closed outcome.
  - `docs/ARCHITECTURE.md` — Describe one baseline-identity evidence rule while retaining the journaled structural-publication boundary.
  - `tests/test_roadmap_source_identity.py` — Update supported-version and currentness fixtures so version 2 is the sole legal evidence schema without changing pending-generation protocol coverage.
  - `tests/test_roadmap_escalation.py` — Make normal receipt fixtures version 2 and prove version 1, omitted identity, and unsupported values fail validation.
  - `tests/test_roadmap_escalation_run.py` — Move normal lifecycle fixtures to version 2 and keep receipt publication and reuse assertions on the unchanged writer path.
  - `tests/test_roadmap_escalation_selection.py` — Prove version-1 source admission is rejected by the shared schema gate and retain version-2 baseline admission coverage.
  - `tests/test_roadmap_impact_analysis.py` — Build normal analyses from explicit version-2 nested evidence and reject version-1 or omitted nested discriminators.
  - `tests/test_roadmap_impact_run.py` — Rebase normal receipt and analysis fixtures on version 2 without changing immutable-analysis publication behavior.
  - `tests/test_roadmap_impact_snapshot.py` — Make capture fixtures version 2 by default and retain baseline, pending-generation, presentation-drift, and recheck coverage.
  - `tests/test_roadmap_revision_publish.py` — Keep journal recovery and recorded artifact-and-seed replacement coverage valid with version-2 structural fixtures.
  - `tests/test_roadmap_structural_revision.py` — Rebase exact-pair fixtures on version-2 receipt, analysis, and snapshot evidence.
  - `tests/test_roadmap_structural_revision_proof.py` — Rebase proof fixtures on version-2 snapshot bindings without weakening preservation checks.
  - `tests/test_roadmap_structural_revision_run.py` — Build a complete version-2 snapshot for runner fixtures and prove non-version-2 snapshots fail canonical preflight.
  - `tests/test_roadmap_format.py` — Parse and identity-check one version-2 receipt and analysis example, while guarding the separate structural-operation envelope.
  - `tests/cli/test_roadmap_cmd.py` — Update normal evidence fixtures used by roadmap command tests to version 2 without adding CLI syntax.

## Implementation

- **Foundational logic: version-2-only evidence admission.** Make `plan_tool/roadmap_source_identity.py:EVIDENCE_SCHEMA_VERSIONS` and `is_supported_evidence_schema_version` recognize exactly the JSON integer `2`. Keep the shared helper rather than copying `== 2` checks into callers; later steps will remove the unreachable version dispatch behind those callers.

- **Keep the evidence discriminator.** Every receipt and analysis record must still serialize `schema_version: 2`. Do not replace the field with an inferred default, omit it from nested analysis evidence, or use a separate boolean that would weaken the persisted contract.

- **Require the complete version-2 receipt shape.** In `plan_tool/roadmap_escalation.py:EscalationReceipt`, `_ReceiptSemanticFields`, `build_receipt`, `receipt_semantic_id_from_facts`, and `_canonical_source_identity_fields`, require the selected-stage `CanonicalSourceIdentity` for every valid record. Keep `source.sha256` as immutable raw provenance and keep the existing version-2 semantic-id rule that permits presentation-only source drift without changing the identity.

- **Require the complete version-2 analysis shape.** In `plan_tool/roadmap_impact_analysis.py:ImpactReceiptEvidence`, `ImpactSnapshotEvidence`, `_ImpactAnalysisSemanticFields`, `build_impact_analysis`, and `_snapshot_evidence`, remove the missing-field path that treats an omitted nested `schema_version` as version 1. Version-2 receipt and snapshot identities must remain explicit, ordered, and bound to the selected stage; raw artifact digests, source-record digest, and brief digest remain persisted for their existing purposes.

- **Make snapshots version 2 before reading roadmap state.** Update `plan_tool/roadmap_impact_snapshot.py:RoadmapImpactSnapshot`, `capture_roadmap_impact_snapshot`, `snapshot_artifacts_match_captured_text`, and `_capture_artifact` so normal capture uses version 2 and unsupported values fail closed. Keep the current baseline-backed admission, raw captured text and digest retention, gate walk, and recheck binding intact. Presentation-only source changes remain admissible only through the existing baseline identity rule.

- **Reject implicit structural fallback.** In `plan_tool/roadmap_structural_revision_run.py:_preflight_is_canonical`, test the evidence version explicitly before selecting the version-2 canonical snapshot check. A non-version-2 snapshot must return a preflight rejection rather than taking the old renderer-based path. Leave the broader structural preflight branch removal to step 5.

- **Preserve journal recovery and replacement exactly.** Do not change `SOURCE_IDENTITY_VERSION`, `PendingGeneration`, `render_pending_generation`, or `load_pending_generation` in `plan_tool/roadmap_source_identity.py`; these describe the baseline and publication-journal protocol, not the retired evidence schema. Keep `run_structural_revision` calling `recover_roadmap_publication` inside `roadmap_writer_guard` before `load_structural_revision_preflight`, and do not alter its use of `publish_structural_revision_proof`, the selected artifact, or the seed-state callback.

- **Update documentation by contract section, not by blind token removal.** In `ROADMAP_FORMAT.md:Versioned receipt reference`, `Versioned analysis reference`, and `Reader-only freshness and refusal boundary`, state one version-2 evidence contract and retain one executable example per evidence type. In `docs/ARCHITECTURE.md:Immutable roadmap evidence`, describe the one canonical-identity freshness rule and preserve the writer-guard and journal rules. Keep the structural-operation `version: 1` material under `ROADMAP_FORMAT.md:Version-1 operation and source-span reference`; it is a separate evaluator protocol.

- **Keep this step focused on legal input.** Do not remove the now-unreachable raw-digest admission, analysis lifecycle, or structural-preflight dispatch in this batch. Steps 3 through 5 own that behavior-preserving cleanup after this strict gate lands.

## Tests

### Tests for this step

- `tests/test_roadmap_source_identity.py:test_supported_evidence_schema_version_accepts_only_json_integer_two` — asserts `2` is accepted and `1`, booleans, missing values, and other integers are rejected.
- `tests/test_roadmap_source_identity.py:test_pending_generation_version_remains_a_journal_protocol` — asserts the journal still round-trips with explicit absent member states and is not treated as roadmap evidence.
- `tests/test_roadmap_escalation.py:test_receipt_v2_round_trips_as_the_only_closed_schema` — asserts a valid receipt persists `schema_version: 2`, raw source digest, and canonical source identity.
- `tests/test_roadmap_escalation.py:test_receipt_rejects_version1_and_missing_version2_identity` — asserts version 1 and a version-2-shaped receipt without the identity fail parsing and construction.
- `tests/test_roadmap_escalation_selection.py:test_version1_source_admission_is_rejected_by_the_shared_schema_gate` — asserts direct source admission cannot select the old raw-source route.
- `tests/test_roadmap_escalation_run.py:test_default_receipt_creation_publishes_version2_evidence` — asserts the normal creation path still creates or reuses only a valid version-2 final.
- `tests/test_roadmap_impact_analysis.py:test_analysis_requires_explicit_version2_receipt_and_snapshot_evidence` — asserts top-level and nested evidence retain version 2 and the required canonical identities.
- `tests/test_roadmap_impact_analysis.py:test_analysis_rejects_version1_or_omitted_nested_schema_version` — asserts no parser default turns legacy or incomplete input into a valid analysis.
- `tests/test_roadmap_impact_snapshot.py:test_default_capture_is_version2_and_retains_raw_provenance` — asserts capture records baseline identities and raw text digests without rewriting the source.
- `tests/test_roadmap_impact_snapshot.py:test_capture_rejects_every_nonversion2_evidence_value_before_snapshot_use` — asserts unsupported values cannot select the legacy capture behavior.
- `tests/test_roadmap_impact_run.py:test_version2_analysis_reuse_survives_presentation_only_source_drift` — keeps immutable publication reuse bound to the existing version-2 identity rule.
- `tests/test_roadmap_structural_revision.py:test_exact_pair_fixtures_bind_version2_receipt_analysis_and_snapshot` — asserts normal structural evidence remains an exact version-2 pair.
- `tests/test_roadmap_structural_revision_proof.py:test_proof_preserves_a_version2_snapshot_binding` — keeps row, relation, ordering, feedback, and gate preservation checks independent of retired evidence.
- `tests/test_roadmap_structural_revision_run.py:test_structural_preflight_rejects_nonversion2_snapshot_without_legacy_fallback` — asserts `_preflight_is_canonical` fails closed on a non-version-2 fixture.
- `tests/test_roadmap_revision_publish.py:test_publication_recovery_restores_mixed_members_and_refuses_unknown_bytes` — keeps recorded journal recovery and unknown-byte refusal unchanged.
- `tests/test_roadmap_format.py:test_version2_only_receipt_and_analysis_examples_match_the_landed_contract` — parses, renders, and identity-checks the sole examples in `ROADMAP_FORMAT.md`.
- `tests/test_roadmap_format.py:test_structural_operation_version1_reference_remains_independent` — asserts the evaluator-envelope documentation remains present and separate from retired evidence wording.
- `tests/cli/test_roadmap_cmd.py:test_roadmap_evidence_fixtures_use_version2_without_new_cli_flags` — keeps command wiring on the existing interface and version-2 evidence fixtures.

Every listed test and `uv run pytest tests/ -q -n auto` must be green before this step is complete.

## Acceptance criteria

- `docs/history/roadmap-evidence-v1-retirement.md` was re-read immediately before this step's schema-boundary edits and, at that time, stated an explicit, dated project/roadmap roster, a dated consumer roster, a dated named approval, and zero blocking rows against those rosters; this step was not started against a record with an unstated roster or approval, or one naming an unresolved blocker.
- `plan_tool/roadmap_source_identity.py:is_supported_evidence_schema_version` accepts only the integer `2`.
- Receipt parsing and construction retain `schema_version: 2`, `source.sha256`, and a selected-stage canonical source identity; version 1 and missing identity are invalid.
- Analysis parsing and construction retain a top-level and nested version-2 discriminator plus ordered canonical identities; missing nested schema fields are invalid.
- `plan_tool/roadmap_impact_snapshot.py:capture_roadmap_impact_snapshot` defaults to version 2 and rejects every other evidence version before returning a snapshot.
- Existing valid version-2 receipt and analysis bytes still parse, render canonically, and retain their current semantic-id and presentation-drift behavior.
- `plan_tool/roadmap_structural_revision_run.py:_preflight_is_canonical` rejects non-version-2 snapshots instead of selecting the old fallback.
- `plan_tool/roadmap_structural_revision_run.py:run_structural_revision` still recovers the recorded journal under the writer guard before structural preflight, and `tests/test_roadmap_revision_publish.py:test_publication_recovery_restores_mixed_members_and_refuses_unknown_bytes` stays green.
- The evidence sections of `ROADMAP_FORMAT.md`, `DATA_CONTRACT.md`, and `docs/ARCHITECTURE.md` describe only version-2 roadmap evidence; the independent structural-operation `version: 1` reference remains intact.
- `uv run pytest tests/ -q -n auto` passes with no skipped or expected-failure version-1 evidence path.

## References

- [Validators | Pydantic Docshttps: — Use field and model validation to reject unsupported versions and incomplete identity bindings.
- [Fields | Pydantic Docshttps: — Review required fields and defaults before removing missing-version compatibility behavior.
- [Serialization | Pydantic Docshttps: — Verify that required `schema_version` and canonical identity fields remain in rendered evidence.
- [How to parametrize fixtures and test functionshttps: — Cover the accepted version and rejected values with one clear test matrix.

## Applicable guardrails

- **The plan’s “## Out of scope”, version-2 semantics and baseline contract:** Keep the surviving identity, admission, provenance, and presentation-drift behavior unchanged; this step removes legal legacy input, not redesigns version 2.
- **The plan’s “## Out of scope”, no in-place converter:** Do not add a path that edits a version-1 final or invents its missing writer-owned identity.
- **The plan’s “## Out of scope”, closed consolidation decision:** Keep `admitted_source_is_current` as the shared boundary and do not merge its distinct callers or checks.
- **The plan’s “## Out of scope”, unrelated receipt-preflight work:** Do not add a new preflight gate or CLI option while tightening the evidence contract.
- **The plan’s “## Out of scope”, structural operation envelope:** Preserve `plan_tool/roadmap_structural_operations.py` and its live `version: 1` documentation and tests.

## Deferred

- `plan_tool/roadmap_escalation_selection.py:admit_versioned_artifact_source` and `plan_tool/roadmap_escalation_run.py:current_escalation_receipt` dispatch cleanup — Step 3 removes the unreachable receipt-admission and inspection branches after this schema gate rejects their version-1 input.
- `plan_tool/roadmap_impact_analysis.py` lifecycle-only dispatch and `plan_tool/roadmap_impact_run.py` cleanup — Step 4 removes the unreachable impact-analysis branches while keeping immutable publication unchanged.
- `plan_tool/roadmap_structural_revision.py` and the remaining structural runner dispatch — Step 5 removes the unreachable structural-preflight branches while retaining journaled replacement safeguards.
