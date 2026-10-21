> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 2 — Make impact capture and analysis consume canonical freshness without source mutation

## Summary

Extend `plan_tool/roadmap_impact_snapshot.py` to capture a valid writer-published baseline identity for every staged artifact while retaining the raw artifact, source-record, and brief evidence it already records. Update `plan_tool/roadmap_impact_analysis.py` and `plan_tool/roadmap_impact_run.py` to use the version-2 canonical-freshness contract from step 1 without weakening version-1 exact-raw behavior. Keep baseline reads side-effect free and preserve the existing guarded capture, recheck, and immutable evidence-publication order. On green, version-2 impact evidence admits only baseline-backed stage semantics, retains independent source-record and brief checks, and never repairs source state.

## Table of Contents

- [Summary](#summary) — Reviewer-level result and main design choice.
- [Table of Contents](#table-of-contents) — Links to each section in this detail.
- [Why](#why) — The missing baseline-backed impact freshness check.
- [Input](#input) — Contracts from step 1 and the existing writer-owned baseline.
- [Files (creates vs edits)](#files-creates-vs-edits) — The six scoped code and test files.
- [Implementation](#implementation) — Capture, analysis, currentness, and publication rules.
- [Tests](#tests) — Focused refusal and compatibility coverage.
- [Acceptance criteria](#acceptance-criteria) — Observable completion conditions.
- [References](#references) — Semantic equality and hashing references.
- [Applicable guardrails](#applicable-guardrails) — Reader-only scope limits.
- [Deferred](#deferred) — Later reader and structural-admission work.

## Why

`plan_tool/roadmap_impact_snapshot.py:capture_roadmap_impact_snapshot` currently binds impact work to raw artifact digests only, while `plan_tool/roadmap_source_identity.py:BaselineRecord` already carries the writer-owned semantic source identity. The test-local `capture` wrapper in `tests/test_roadmap_impact_run.py:test_runner_holds_writer_guard_across_capture_recheck_and_publication` checks ordering only; it does not make capture baseline-aware. Without this step, a version-2 analysis cannot distinguish immutable raw provenance from current stage semantics or safely refuse a missing, incomplete, or semantically changed baseline state.

## Input

- **Step 1 versioned evidence contract:** Consume the version-2 canonical-freshness identity defined by step 1 in `plan_tool/roadmap_escalation.py:EscalationReceipt` and `plan_tool/roadmap_impact_analysis.py:ImpactSnapshotEvidence`. Do not infer that identity from raw digests.
- **Writer-owned source identity:** Read `plan_tool/roadmap_source_identity.py:baseline_path`, `load_baseline_record`, `compare_baseline`, and pending-generation readers as the sole baseline admission surface. A baseline identifies stage semantics and excludes feedback.
- **Existing raw currentness:** Preserve `plan_tool/roadmap_impact_snapshot.py:_capture_recorded_brief_digests` and the source-record and decoded-brief digests it returns. These inputs have no baseline substitute.
- **Live feedback selection:** Preserve the current validation in `plan_tool/roadmap_impact_analysis.py:_receipt_matches_captured_artifact` and `plan_tool/roadmap_escalation_selection.py:select_receipt_feedback`. Step 3 owns the broader receipt-currentness admission path.

## Files (creates vs edits)

- **New files:** None.

- **Existing files (edits only):**
  - `plan_tool/roadmap_impact_snapshot.py` — Capture and recheck stage-ordered baseline identities with raw snapshot evidence, and refuse incomplete or semantically drifted source state without writing.
  - `plan_tool/roadmap_impact_analysis.py` — Bind version-2 receipt and snapshot freshness identities while retaining version-1 exact-raw construction and immutable rendering.
  - `plan_tool/roadmap_impact_run.py` — Apply version-aware currentness when publishing or inspecting an impact analysis, without changing the guarded publication order.
  - `tests/test_roadmap_impact_snapshot.py` — Add baseline-backed capture, recheck, refusal, and no-mutation coverage.
  - `tests/test_roadmap_impact_analysis.py` — Add version-2 snapshot and receipt binding coverage beside version-1 compatibility cases.
  - `tests/test_roadmap_impact_run.py` — Cover guarded refusal and version-aware current-analysis inspection.

## Implementation

- **Foundational rule:** Select the evidence version before capture. Version 1 retains its existing exact-raw snapshot and recheck path without loading a baseline. Every artifact entering a version-2 impact snapshot must match its valid writer-published baseline semantically. A raw digest remains immutable provenance for the bytes observed; it is not the version-2 freshness authority.

- **Capture every baseline as part of one version-2 snapshot.** Extend `plan_tool/roadmap_impact_snapshot.py:RoadmapImpactSnapshot`, `capture_roadmap_impact_snapshot`, and `_capture_artifact` with an explicit version branch. The version-2 branch retains the same closed `CanonicalBaselineIdentity` for every configured stage beside the existing artifact key, parsed value, captured text, and raw digest; the version-1 branch retains no baseline identities. Keep stage order aligned with `plan_tool/roadmap.py:STAGES`.

- **Fail closed before returning a version-2 snapshot.** For each stage, use the existing `plan_tool/roadmap_source_identity.py:load_baseline_record` and `compare_baseline` contract, then construct the one closed identity, to reject a missing, malformed, wrongly bound, incomplete, or semantically different baseline state. Read any pending publication state only to refuse it; do not call writer recovery or create a baseline. A version-1 capture makes none of these baseline reads.

- **Split source validity from generated-candidate canonicality.** Version 1 retains the existing strict parser-and-renderer source snapshot. Version 2 requires strict UTF-8 and a successful parser, retains its original bytes and raw digest unchanged, and permits a renderer-byte difference only after every stage's full baseline comparison succeeds. It must never normalize or overwrite source bytes. Keep parser/gate evaluation over the parsed values, and preserve renderer-byte checks for generated structural patches and proofs; those candidates are not version-2 current-source inputs.

- **Recheck the complete binding before publication.** Update `plan_tool/roadmap_impact_snapshot.py:_binding` and `recheck_roadmap_impact_snapshot` so the second read confirms the source record, brief, stage raw capture, and canonical identities still describe the same snapshot. This is an issuance-window check for both versions; do not weaken it merely because the semantic baseline identity matches. It is distinct from later version-2 currentness, which compares canonical identities plus independent live inputs and deliberately permits a different retained raw stage digest.

- **Keep analysis pure.** Let `plan_tool/roadmap_impact_analysis.py:_snapshot_evidence` copy already-captured, fieldwise-validated closed baseline identities into the version-2 `ImpactSnapshotEvidence`; do not make `build_impact_analysis` read files or import writer behavior. Persist only the redacted identity facts required by step 1, never a baseline projection or feedback content.

- **Bind receipt, snapshot, and selected stage by version.** Update `plan_tool/roadmap_impact_analysis.py:build_impact_analysis`, `_validated_receipt`, and `_receipt_matches_captured_artifact` so a version-2 receipt must match the captured canonical identity for its selected stage. Keep raw-digest consistency checks for retained provenance, but do not let an otherwise valid version-2 baseline match fail solely because an earlier receipt observed different raw stage bytes.

- **Keep legacy behavior exact.** An exact-raw-current version-1 receipt must still use the existing raw selected-artifact binding and may create or reuse only a version-1 analysis. Do not let the version-2 branch supply an inferred upgrade to stored legacy evidence, and refuse a stale version-1 receipt before analysis publication.

- **Keep feedback, source-record, and brief checks independent.** Continue checking the selected feedback row through `select_receipt_feedback`, and retain the direct source-record and brief comparisons. A matching artifact baseline must not hide resolved feedback, a changed recorded source, or a changed brief.

- **Make inspection version-aware.** Adapt `plan_tool/roadmap_impact_run.py:current_impact_analysis` so version 1 captures and rebuilds only its exact raw candidate without baseline input. For version 2, capture through the version-2 branch and judge freshness through the stored and newly captured closed canonical identities plus the independent source-record, brief, feedback, and closure checks. Do not rebuild a version-2 final or mark it stale solely because its retained raw stage provenance differs.

- **Preserve guarded evidence publication.** Keep `plan_tool/roadmap_impact_run.py:_resolve_preflight`, `run_roadmap_impact_analysis`, and `recheck_roadmap_impact_snapshot` ordered under `plan_tool/roadmap_revision_publish.py:roadmap_writer_guard`. A refused snapshot publishes no impact analysis and changes neither artifacts nor baselines.

## Tests

### Tests for this step

Every test below, plus the existing strict decoding, canonical-rendering, gate, and exact-reuse cases in these three files, must be green before this step is complete.

- `tests/test_roadmap_impact_snapshot.py:test_capture_records_stage_ordered_baseline_identity_beside_raw_provenance` — Capture retains each stage’s raw digest and the matching redacted canonical identity in configured order.
- `tests/test_roadmap_impact_snapshot.py:test_v1_capture_requires_no_baseline_and_keeps_exact_raw_binding` — A retained version-1 receipt selects the raw-only capture path even when no baseline exists.
- `tests/test_roadmap_impact_snapshot.py:test_v2_capture_admits_parseable_nonrendercanonical_bytes_only_when_baseline_equal` — CRLF or equivalent renderer-byte drift retains its raw bytes and admits only when the complete baseline identity matches; unparsable or semantically different input refuses.
- `tests/test_roadmap_impact_snapshot.py:test_capture_refuses_missing_malformed_pending_or_semantically_drifted_baseline_without_writes` — Missing, invalid, incomplete, and mismatched baseline states raise the snapshot error and leave every source file unchanged.
- `tests/test_roadmap_impact_snapshot.py:test_recheck_requires_the_same_raw_source_brief_and_baseline_binding` — A change after capture prevents publication even when the replacement stage remains semantically baseline-valid.
- `tests/test_roadmap_impact_snapshot.py:test_snapshot_capture_never_initializes_repairs_or_recovers_baseline_state` — Capture and recheck only read baseline state and never acquire writer authority or alter a pending generation.
- `tests/test_roadmap_impact_analysis.py:test_v2_analysis_binds_raw_provenance_and_stage_canonical_freshness` — A version-2 analysis retains both identity kinds, includes them in its semantic identity, and omits artifact, feedback, and baseline-projection content.
- `tests/test_roadmap_impact_analysis.py:test_v2_analysis_requires_matching_selected_receipt_and_snapshot_canonical_identity` — Missing, misordered, malformed, or selected-stage-mismatched canonical identity produces `InvalidImpactAnalysis`.
- `tests/test_roadmap_impact_analysis.py:test_v2_analysis_accepts_baseline_equal_selected_artifact_with_different_raw_digest` — Version-2 admission accepts a valid current feedback selection when raw stage provenance differs but canonical freshness matches.
- `tests/test_roadmap_impact_analysis.py:test_v1_analysis_keeps_exact_raw_selected_artifact_binding` — Legacy receipt construction remains exact-raw and does not gain a version-2 fallback.
- `tests/test_roadmap_impact_run.py:test_impact_runner_refuses_a_baseline_rejected_snapshot_before_evidence_publication` — Snapshot refusal returns an invalid result and creates no analysis evidence or source mutation.
- `tests/test_roadmap_impact_run.py:test_current_v2_analysis_uses_canonical_stage_freshness_and_direct_source_checks` — A baseline-equal, parseable presentation change stays current without rebuilding a new raw-evidence final, while changed feedback eligibility, source record, brief, or stage semantics refuses current status.
- `tests/test_roadmap_impact_run.py:test_runner_holds_writer_guard_across_baseline_capture_recheck_and_publication` — The existing guard-order test continues to prove capture, recheck, and evidence publication share one guarded window.

## Acceptance criteria

- `capture_roadmap_impact_snapshot` selects version 1 raw-only capture or version 2 raw provenance plus a valid, stage-ordered closed canonical identity for every configured stage.
- Missing, malformed, pending, wrongly bound, or semantically drifted baseline state prevents only version-2 snapshot capture without modifying roadmap artifacts, baselines, or publication journals.
- `recheck_roadmap_impact_snapshot` rejects any source-record, brief, raw-stage, or baseline-identity change between capture and evidence publication.
- A version-2 `build_impact_analysis` result binds its receipt and snapshot to the same selected-stage canonical identity while retaining raw provenance separately.
- Version-1 impact analysis construction, including analysis creation or reuse from a stored exact-raw-current receipt, and currentness stay exact-raw with no baseline read or inferred canonical identity.
- `current_impact_analysis` keeps version-2 evidence current across an allowed strict-UTF-8, parseable, baseline-equal raw stage change without rebuilding a new final, but refuses changed feedback eligibility, source-record input, brief input, or stage semantics.
- `run_roadmap_impact_analysis` publishes no impact evidence when snapshot admission or recheck fails, and it never repairs source state.
- `uv run pytest tests/test_roadmap_impact_snapshot.py tests/test_roadmap_impact_analysis.py tests/test_roadmap_impact_run.py -q` passes.

## References

- [YAML Ain’t Markup Language (YAML™) Revision 1.2.2](https://yaml.org/spec/1.2.2/) — Use representation equality when separating stage semantics from formatting and raw provenance.
- [hashlib — Secure Hashes and Message Digests](https://docs.python.org/3.13/library/hashlib.html) — Use SHA-256 for immutable raw provenance and canonical identity binding.

## Applicable guardrails

- **The plan’s “## Plan intent”, writer-owned baseline authority** — Read canonical freshness only through the existing baseline contract; these files must not become another source of authority.
- **The plan’s “## Step intent”, independent currentness checks** — Retain raw captured provenance and direct source-record and brief checks while adding baseline-backed stage semantics.
- **The plan’s “## Out of scope”, baseline lifecycle boundary** — Do not initialize, publish, recover, repair, or advance baseline state from impact capture, analysis, or inspection.
- **The plan’s “## Out of scope”, source-mutation boundary** — Do not canonicalize a hand edit in place or alter raw provenance to make it match freshness evidence.
- **The plan’s “## Out of scope”, generated-candidate boundary** — Leave structural patch and proof validation rules unchanged.
- **The plan’s “## Out of scope”, follow-up workflow boundary** — Do not add retention or hand-edit feedback workflows.

## Deferred

- `plan_tool/roadmap_escalation_selection.py` and `plan_tool/roadmap_escalation_run.py` receipt issuance and reader admission — Step 3 owns the complete versioned receipt-currentness path.
- `plan_tool/roadmap_structural_revision.py` structural evidence admission — Step 3 consumes this step’s baseline-backed impact evidence.
- `plan_tool/roadmap_revision_publish.py` baseline lifecycle changes — Writer publication and recovery remain outside this reader-only step.
