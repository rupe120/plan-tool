> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 2 — Make impact capture and analysis consume canonical freshness without source mutation

## Summary

Update `plan_tool/roadmap_impact_snapshot.py` to capture version-aware baseline freshness alongside the existing raw impact evidence. Update `plan_tool/roadmap_impact_analysis.py` and `plan_tool/roadmap_impact_run.py` so version-2 analyses use canonical stage identities while version 1 keeps exact-raw behavior. Keep capture read-only and preserve the guarded capture, recheck, and evidence-publication order. On green, presentation-only stage changes can remain current for version 2 only when every required baseline check passes.

## Table of Contents

- [Summary](#summary) — Reviewer-level result and main design choice.
- [Table of Contents](#table-of-contents) — Links to each detail section.
- [Why](#why) — The missing baseline-backed impact freshness boundary.
- [Input](#input) — Contracts from step 1 and existing source readers.
- [Files (creates vs edits)](#files-creates-vs-edits) — Scoped production and test changes.
- [Implementation](#implementation) — Version-aware capture, analysis, inspection, and publication rules.
- [Tests](#tests) — Focused compatibility and refusal coverage.
- [Acceptance criteria](#acceptance-criteria) — Observable completion conditions.
- [References](#references) — Semantic equality and digest references.
- [Applicable guardrails](#applicable-guardrails) — Reader-only scope limits.
- [Deferred](#deferred) — Related reader and consolidation work outside this step.

## Why

`plan_tool/roadmap_impact_snapshot.py:capture_roadmap_impact_snapshot` currently treats renderer-canonical artifact text and raw artifact digests as the only source-freshness proof. `plan_tool/roadmap_source_identity.py:BaselineRecord` already lets the writer-owned baseline distinguish stage semantics from presentation, but impact capture and later inspection do not consume that distinction. This step lets version-2 impact evidence use the published baseline without changing the source it observes, while retaining the independent source-record, brief, feedback, and relation checks that keep canonical freshness from becoming an overbroad approval.

## Input

- **Step 1 versioned evidence contract:** Consume the landed version-specific receipt and analysis shapes from step 1. The parsed evidence version selects the capture and currentness rules; landed field names and validation rules win over this detail.

- **Published baseline:** Read `plan_tool/roadmap_source_identity.py:baseline_path`, `load_baseline_record`, `compare_baseline`, `pending_generation_path`, and `load_pending_generation`. These are read-only admission inputs; a baseline covers stage semantics, not live feedback.

- **Current snapshot contract:** Preserve `plan_tool/roadmap_impact_snapshot.py:RoadmapImpactSnapshot`, `_capture_recorded_brief_digests`, `check_full_roadmap_gates`, and `recheck_roadmap_impact_snapshot`. Source-record and decoded-brief digests remain direct currentness facts.

- **Analysis and publication flow:** Preserve `plan_tool/roadmap_impact_analysis.py:build_impact_analysis` as a pure value builder and `plan_tool/roadmap_impact_run.py:_resolve_preflight`, `current_impact_analysis`, and `run_roadmap_impact_analysis` as their storage and lifecycle owners.

## Files (creates vs edits)

- **New files:** None.

- **Existing files (edits only):**
  - `plan_tool/roadmap_impact_snapshot.py` — Capture and recheck version-appropriate stage freshness while retaining raw snapshot facts and refusing unsafe baseline states.
  - `plan_tool/roadmap_impact_analysis.py` — Build version-2 analysis evidence from captured canonical identities without adding filesystem or writer behavior.
  - `plan_tool/roadmap_impact_run.py` — Select capture and inspection behavior from parsed evidence version while preserving guarded publication.
  - `tests/test_roadmap_impact_snapshot.py` — Cover baseline-backed capture, recheck, presentation drift, refusal, and no-mutation behavior.
  - `tests/test_roadmap_impact_analysis.py` — Cover version-specific receipt-to-snapshot binding and retained redaction.
  - `tests/test_roadmap_impact_run.py` — Cover version-aware publication and current-analysis inspection.

## Implementation

- **Select the rule before capture.** Thread the evidence version from the parsed receipt or stored analysis through `plan_tool/roadmap_impact_run.py:_resolve_preflight`, `current_impact_analysis`, `capture_roadmap_impact_snapshot`, and `recheck_roadmap_impact_snapshot`. Version 1 keeps the current exact-raw path and does not read a baseline. Version 2 requires a current baseline identity for every configured stage.

- **Retain two different facts for version 2.** Extend `plan_tool/roadmap_impact_snapshot.py:RoadmapImpactSnapshot` and `_capture_artifact` so each stage retains the observed text and raw digest as provenance, plus the stage-ordered canonical identity from step 1 as freshness evidence. Keep identity order aligned with the artifact order used by `plan_tool/roadmap.py:STAGES`.

- **Fail closed on baseline state.** In the version-2 capture path, use the existing baseline readers to reject a missing, malformed, wrongly bound, pending, or semantically different source state. Compare parsed artifacts to their matching stage baseline, then retain only the redacted identity defined by step 1. Do not initialize, recover, rewrite, or advance any baseline or pending generation.

- **Keep source and generated-candidate rules separate.** Preserve `stage.render(artifact) == text` as the version-1 source rule. For version 2, require strict UTF-8 and successful parsing, preserve the observed text and digest unchanged, and allow a renderer-text difference only when the complete baseline comparison succeeds. Continue to apply the current full-roadmap gates to parsed artifacts. Do not weaken renderer-byte checks for generated structural patches or proofs.

- **Make snapshot validation version-aware.** Update `snapshot_artifacts_match_captured_text` and `plan_tool/roadmap_impact_analysis.py:_snapshot_evidence` so exact parsed-artifact-to-rendered-text equality remains required for version 1, while version 2 validates its captured raw provenance and complete canonical identities instead. A direct, malformed, incomplete, misordered, or mismatched snapshot remains invalid.

- **Recheck the complete publication binding.** Update `plan_tool/roadmap_impact_snapshot.py:_binding` so a second version-2 read confirms the source record, brief, raw stage capture, canonical identities, and gates still describe the same capture. This recheck protects new evidence publication; a baseline match alone must not allow a changed raw snapshot into the guarded publication window.

- **Keep analysis pure and redacted.** Let `plan_tool/roadmap_impact_analysis.py:build_impact_analysis` and `_snapshot_evidence` copy only already-captured version-2 identity facts into `ImpactSnapshotEvidence`. Do not make this module read paths, load baselines, acquire guards, or retain baseline projections, feedback prose, or artifact prose.

- **Bind receipt and snapshot by their selected-stage rule.** Update `_validated_receipt` and `_receipt_matches_captured_artifact` so version 1 retains its exact selected-artifact raw-digest check. For version 2, require the selected receipt identity to match the selected captured snapshot identity, while still checking live feedback selection, target, and reason through `select_receipt_feedback`. A version-2 receipt must not be rejected only because a baseline-equal presentation change changed its raw stage digest.

- **Keep inspection strict where it matters.** In `plan_tool/roadmap_impact_run.py:current_impact_analysis`, preserve exact candidate reconstruction for version 1. For version 2, determine currentness from matching retained and newly captured canonical identities plus the direct source-record, brief, feedback, target, and impact-closure checks; do not require the stored raw stage digest or final analysis bytes to equal a newly observed presentation-only stage state.

- **Preserve publication ordering.** Keep `run_roadmap_impact_analysis` inside `roadmap_writer_guard`, with capture before analysis construction, a complete snapshot recheck before `publish_evidence`, and no publication after a refusal. `capture_roadmap_impact_snapshot` itself remains a reader and must not acquire a writer guard or write evidence.

- **Do not fold ordinary revision admission into impact capture.** `plan_tool/roadmap.py:admit_stage_artifact` and `recheck_admitted_artifact` serve ordinary and local revision flows and replace their in-memory text with rendered canonical text. Impact capture must retain the observed source representation, so use the baseline leaf contracts directly rather than importing that revision-oriented path.

## Tests

### Tests for this step

Every test below, the existing relevant cases in these three files, and the plan’s configured test command must be green before this step is complete.

- `tests/test_roadmap_impact_snapshot.py:test_v1_capture_requires_no_baseline_and_keeps_exact_raw_binding` — Version-1 capture and recheck succeed without baseline reads and reject non-render-canonical source text.

- `tests/test_roadmap_impact_snapshot.py:test_v2_capture_retains_stage_ordered_canonical_identities_beside_raw_provenance` — Version-2 capture preserves source-record, brief, text, and raw-digest facts while retaining a matching identity for every configured stage.

- `tests/test_roadmap_impact_snapshot.py:test_v2_capture_admits_parseable_baseline_equal_presentation_drift_without_rewriting_source` — A strict-UTF-8 presentation-only change remains observed as written and is admitted only through a matching baseline identity.

- `tests/test_roadmap_impact_snapshot.py:test_v2_capture_refuses_missing_invalid_pending_or_semantically_drifted_baseline_without_writes` — Each unsafe baseline state raises `RoadmapImpactSnapshotError` and leaves roadmap artifacts, baselines, journals, and evidence unchanged.

- `tests/test_roadmap_impact_snapshot.py:test_v2_recheck_requires_same_raw_source_brief_and_canonical_binding_before_publication` — A change after capture rejects publication even when the replacement stage remains baseline-equal.

- `tests/test_roadmap_impact_snapshot.py:test_snapshot_capture_never_acquires_writer_guard_or_mutates_source_state` — Capture and recheck only read their inputs.

- `tests/test_roadmap_impact_analysis.py:test_v2_analysis_binds_selected_receipt_and_snapshot_canonical_identity` — A version-2 analysis accepts only matching selected-stage identities and retains no source or baseline content.

- `tests/test_roadmap_impact_analysis.py:test_v2_analysis_accepts_baseline_equal_selected_artifact_with_different_raw_digest` — Version-2 receipt validation permits an eligible selected artifact whose raw digest changed only through admitted presentation drift.

- `tests/test_roadmap_impact_analysis.py:test_v1_analysis_keeps_exact_raw_selected_artifact_binding_without_identity_inference` — Legacy evidence remains raw-only and cannot enter the version-2 path.

- `tests/test_roadmap_impact_run.py:test_impact_runner_refuses_baseline_rejected_snapshot_before_evidence_publication` — A capture refusal returns an invalid result and publishes no analysis.

- `tests/test_roadmap_impact_run.py:test_current_v2_analysis_accepts_baseline_equal_presentation_drift` — Stored version-2 analysis remains current when stage semantics, source record, brief, feedback, and closure remain valid despite raw presentation drift.

- `tests/test_roadmap_impact_run.py:test_current_v2_analysis_refuses_changed_feedback_source_record_brief_or_stage_semantics` — Each independent currentness change prevents a version-2 analysis from being reported current.

- `tests/test_roadmap_impact_run.py:test_runner_holds_writer_guard_across_versioned_capture_recheck_and_publication` — Capture, recheck, and publication stay in one guarded window.

## Acceptance criteria

- `capture_roadmap_impact_snapshot` selects raw-only capture for version 1 and baseline-backed capture for version 2.

- Version-2 snapshots retain a valid stage-ordered canonical identity for every configured artifact while keeping raw artifact, source-record, and brief provenance separate.

- Missing, malformed, pending, wrongly bound, or semantically drifted baseline state refuses version-2 capture without changing source, baseline, journal, or evidence state.

- A strict-UTF-8, parsable, baseline-equal presentation change is admissible only for version 2 and remains unmodified on disk.

- `recheck_roadmap_impact_snapshot` rejects any source-record, brief, raw-stage, identity, or gate change between capture and new evidence publication.

- `build_impact_analysis` keeps version-1 raw matching and requires selected-stage canonical-identity matching for version 2 without filesystem access.

- `current_impact_analysis` keeps version-1 exact-raw and reports version 2 current only when canonical identities and all independent live checks still match.

- `run_roadmap_impact_analysis` publishes no impact analysis after snapshot admission or recheck fails.

- `uv run pytest tests/test_roadmap_impact_snapshot.py tests/test_roadmap_impact_analysis.py tests/test_roadmap_impact_run.py -q` and `uv run pytest tests/ -q -n auto` pass.

## References

- [YAML Ain’t Markup Language (YAML™) Revision 1.2.2](https://yaml.org/spec/1.2.2/) — Use representation equality to distinguish stage semantics from presentation.

- [hashlib — Secure Hashes and Message Digests](https://docs.python.org/3.13/library/hashlib.html) — Use SHA-256 for immutable raw provenance and identity binding.

## Applicable guardrails

- **The plan’s “## Plan intent”, writer-owned baseline authority** — Read canonical freshness through the established baseline contract only; these impact readers must not become another source of authority.

- **The plan’s “## Step intent”, independent currentness checks** — Keep raw provenance and source-record and brief checks active while adding baseline-backed stage freshness.

- **The plan’s “## Out of scope”, baseline lifecycle boundary** — Do not add enrollment, publication, recovery, repair, migration, or revision-admission behavior to this step’s files.

- **The plan’s “## Out of scope”, source-mutation boundary** — Do not normalize source text or alter retained raw provenance to make it appear fresh.

- **The plan’s “## Out of scope”, generated-candidate boundary** — Leave structural patch, proof, and malformed-scalar validation rules unchanged.

- **The plan’s “## Out of scope”, follow-up workflow boundary** — Do not add retention or hand-edit-to-feedback behavior.

## Deferred

- `plan_tool/roadmap_escalation_selection.py` and `plan_tool/roadmap_escalation_run.py` versioned receipt issuance and inspection — Step 3 owns the complete escalation-reader admission path.

- `plan_tool/roadmap_structural_revision.py` versioned structural-evidence admission — Step 3 consumes the baseline-backed impact evidence from this step.

- Consolidating `plan_tool/roadmap.py:admit_stage_artifact` with impact capture — The ordinary revision reader has different retained-text needs; any shared abstraction requires a scoped refactor or reconcile decision.
