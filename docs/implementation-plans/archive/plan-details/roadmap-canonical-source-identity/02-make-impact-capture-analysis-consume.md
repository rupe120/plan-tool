> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 2 — Make impact capture and analysis consume canonical freshness without source mutation

## Summary

Make impact snapshot capture, analysis construction, publication, and inspection apply the versioned freshness contract from step 1. Update `plan_tool/roadmap_impact_snapshot.py`, `plan_tool/roadmap_impact_analysis.py`, and `plan_tool/roadmap_impact_run.py` while preserving version-1 exact-raw behavior and immutable provenance. The key decision is that version 2 compares staged artifact semantics through the published baseline identity, but still retains and rechecks the raw source record, brief, and publication-window artifact bytes. On green, presentation-only stage changes can remain current for version-2 evidence without rewriting source, while missing, pending, malformed, or semantically changed source state refuses.

## Table of Contents

- [Summary](#summary) — Reviewer-level outcome and version boundary.
- [Table of Contents](#table-of-contents) — Links to each detail section.
- [Why](#why) — The raw-byte-only impact freshness gap.
- [Input](#input) — Versioned contracts and existing source-admission boundaries.
- [Files (creates vs edits)](#files-creates-vs-edits) — Scoped production and test changes.
- [Implementation](#implementation) — Capture, analysis, recheck, and inspection rules.
- [Tests](#tests) — Focused version, freshness, and no-mutation coverage.
- [Acceptance criteria](#acceptance-criteria) — Observable completion conditions.
- [References](#references) — Representation and digest references.
- [Applicable guardrails](#applicable-guardrails) — Reader-only and source-mutation limits.
- [Deferred](#deferred) — Adjacent reader work owned by step 3.

## Why

`plan_tool/roadmap_impact_snapshot.py:_capture_artifact` currently requires rendered bytes to equal source bytes, and `plan_tool/roadmap_impact_run.py:current_impact_analysis` requires a fully rebuilt analysis to match stored bytes. That treats a harmless presentation change as semantic drift even when the writer-published baseline still matches. The existing `tests/test_roadmap_impact_run.py:test_runner_holds_writer_guard_across_capture_recheck_and_publication` covers capture ordering, but it does not supply version-aware baseline freshness or protect version-2 inspection from raw-stage-digest churn.

## Input

- **Step 1 versioned evidence:** Consume the landed version-specific contracts in `plan_tool/roadmap_source_identity.py:BaselineRecord`, `plan_tool/roadmap_escalation.py:EscalationReceipt`, and `plan_tool/roadmap_impact_analysis.py:ImpactSnapshotEvidence`. The landed field names and validators from step 1 win over this detail.

- **Baseline admission:** Read `plan_tool/roadmap_source_identity.py:baseline_path`, `load_baseline_record`, and `compare_baseline` as side-effect-free inputs. Build version-2 identities through step 1’s validated identity constructor; do not rebuild the five identity fields in impact code.

- **Direct non-stage inputs:** Preserve the source-record and decoded-brief checks in `plan_tool/roadmap_impact_snapshot.py:_capture_recorded_brief_digests`. Baseline identity does not cover either input.

- **Existing ordinary-roadmap admission:** `plan_tool/roadmap.py:_admit_loaded_stage_artifact` and `recheck_admitted_artifact` already compare parsed artifacts with a baseline, but they replace the working text with rendered text. Use their baseline rule as orientation only; impact capture must retain observed raw text and bytes.

- **Publication and inspection boundaries:** `plan_tool/roadmap_impact_run.py:run_roadmap_impact_analysis` already holds `plan_tool/roadmap_revision_publish.py:roadmap_writer_guard` across capture, recheck, and evidence publication. `plan_tool/cli/roadmap_cmd.py:_cmd_roadmap_impact_analyses_view` already owns the reader guard for `current_impact_analysis`; keep the helper guard-neutral.

## Files (creates vs edits)

- **New files:** None.

- **Existing files (edits only):**
  - `plan_tool/roadmap_impact_snapshot.py` — Add version-aware baseline-backed capture and recheck while preserving raw snapshot facts and gate validation.
  - `plan_tool/roadmap_impact_analysis.py` — Bind version-2 analyses through ordered canonical identities and version-specific receipt matching.
  - `plan_tool/roadmap_impact_run.py` — Select the correct capture rule for receipt or analysis evidence, retain the guarded raw recheck, and inspect version-2 analyses without rewriting or re-identifying them.
  - `tests/test_roadmap_impact_snapshot.py` — Cover versioned capture, recheck, refusal, and source immutability.
  - `tests/test_roadmap_impact_analysis.py` — Cover version-matched construction and version-2 receipt binding.
  - `tests/test_roadmap_impact_run.py` — Cover guarded publication and read-only currentness for both evidence versions.

## Implementation

- **Choose the rule before reading stages.** Thread an explicit evidence-version choice through `plan_tool/roadmap_impact_snapshot.py:capture_roadmap_impact_snapshot` and `recheck_roadmap_impact_snapshot`. Keep existing callers usable on the version-1 rule until step 3 updates structural callers.

- **Keep version 1 exact-raw.** Preserve the current version-1 requirement that captured artifact text renders exactly and that recheck reproduces the source record digest, brief digest, stage order, and raw artifact digests. Do not read a baseline or infer a canonical identity on this path.

- **Admit version 2 from the published baseline.** In `plan_tool/roadmap_impact_snapshot.py:_capture_artifact`, require strict UTF-8 and successful parsing, then load the matching stage baseline and require `compare_baseline` to find no semantic difference. Record one complete step-1 canonical identity for every configured stage in stage order. Reject a missing, malformed, wrongly bound, pending, or semantically changed baseline state. `capture_roadmap_impact_snapshot` and `recheck_roadmap_impact_snapshot` receive no pending allowance by default; step 3 alone passes its authenticated active-writer exact-generation allowance, and both functions re-read and member-for-member compare the on-disk journal before this replacement-bound capture succeeds.

- **Retain observed provenance unchanged.** Keep `RoadmapImpactSnapshot.artifact_texts`, `artifact_digests`, `source_record_digest`, and `brief_digest` as facts from the read. A version-2 presentation change may differ from `stage.render(artifact)`, but capture must not normalize the text, rewrite an artifact, create a baseline, clear a pending generation, or alter raw digests.

- **Validate snapshots by their selected version.** Update `snapshot_artifacts_match_captured_text` and the snapshot checks used by `plan_tool/roadmap_impact_analysis.py:_snapshot_evidence` so version 1 keeps its renderer-byte check, while version 2 proves that retained parsed artifacts match their captured text and recorded baseline identities. Do not represent absent version-1 identities as blank or null version-2 values.

- **Keep gates on the observed parsed state.** Continue running `check_full_roadmap_gates` and `_require_current_gates` over the captured artifacts. A baseline match does not bypass malformed artifacts or current deterministic gate failures.

- **Recheck raw input before publication.** `recheck_roadmap_impact_snapshot` must repeat the same version-specific admission and also require the original raw source record, brief, and stage artifact digests to remain unchanged. This stricter publication-window check applies to version 2 as well, so an analysis never publishes against a mixed raw observation.

- **Bind analysis construction by version.** Update `plan_tool/roadmap_impact_analysis.py:build_impact_analysis`, `_snapshot_evidence`, and `_receipt_matches_captured_artifact` to require matching receipt and snapshot versions. For version 2, match the selected receipt identity to the selected captured stage identity, then keep `select_receipt_feedback` as the independent live-feedback check. Do not require a version-2 receipt’s historical raw stage digest to equal the snapshot’s current raw stage digest.

- **Keep immutable analysis rules intact.** Preserve `parse_impact_analysis`, `render_impact_analysis`, `impact_analysis_semantic_id`, `validate_impact_analysis_final_name`, and `classify_existing_impact_analysis` as strict stored-evidence checks. A new version-2 analysis records the raw provenance observed at its own capture time; later presentation drift must not rewrite its final or stored bytes.

- **Make inspection version-aware.** In `plan_tool/roadmap_impact_run.py:current_impact_analysis`, parse the stored analysis before choosing a capture rule. Keep the existing exact rebuilt-candidate comparison for version 1. For version 2, require current source-record and brief digests, ordered canonical identities, receipt validity, live feedback eligibility, closure validity, and route consistency, but do not use a raw stage-digest difference alone to mark the stored analysis stale.

- **Preserve the guarded publication sequence.** In `plan_tool/roadmap_impact_run.py:_resolve_preflight` and `_run_while_guarded`, select capture from the requested receipt’s version, keep `roadmap_writer_guard` over capture, raw recheck, and `publish_evidence`, and publish nothing after a refusal. `current_impact_analysis` remains a read-only helper that neither logs nor publishes evidence.

## Tests

- `tests/test_roadmap_impact_snapshot.py:test_v1_capture_and_recheck_remain_raw_only_without_baseline` — version 1 neither reads nor infers baseline identity and refuses raw input changes.

- `tests/test_roadmap_impact_snapshot.py:test_v2_capture_records_ordered_identities_and_original_raw_provenance` — version 2 retains all stage identities in order alongside the observed source record, brief, text, and digests.

- `tests/test_roadmap_impact_snapshot.py:test_v2_capture_accepts_baseline_equal_presentation_change_without_source_rewrite` — a strict-UTF-8, parsable formatting-only stage change captures successfully and leaves source bytes unchanged.

- `tests/test_roadmap_impact_snapshot.py:test_v2_capture_refuses_missing_invalid_pending_or_semantically_drifted_baseline_without_mutation` — each unsafe baseline state raises without creating, repairing, or clearing source state.

- `tests/test_roadmap_impact_snapshot.py:test_v2_snapshot_validation_does_not_require_renderer_bytes_to_equal_captured_text` — version-2 snapshot validation accepts baseline-equal captured presentation while version-1 strictness remains covered separately.

- `tests/test_roadmap_impact_snapshot.py:test_v2_recheck_refuses_changed_raw_stage_source_before_publication` — a raw stage change after capture, including presentation-only drift, invalidates the publication window.

- `tests/test_roadmap_impact_snapshot.py:test_v2_recheck_refuses_changed_source_record_or_brief` — either direct non-stage input change invalidates the captured snapshot.

- `tests/test_roadmap_impact_analysis.py:test_build_v1_analysis_keeps_exact_raw_receipt_binding_without_identity` — legacy receipt-to-analysis construction retains its exact-raw contract.

- `tests/test_roadmap_impact_analysis.py:test_build_v2_analysis_requires_matching_version_and_selected_canonical_identity` — version mismatch or a selected-stage identity mismatch returns `InvalidImpactAnalysis`.

- `tests/test_roadmap_impact_analysis.py:test_build_v2_analysis_rechecks_live_feedback_without_requiring_receipt_raw_digest_match` — a baseline-equal presentation change does not block construction, but ineligible selected feedback does.

- `tests/test_roadmap_impact_run.py:test_v2_run_rechecks_the_same_raw_snapshot_before_evidence_publication` — guarded publication refuses when the raw capture changes before the final recheck.

- `tests/test_roadmap_impact_run.py:test_v2_run_publishes_analysis_without_mutating_roadmap_source_or_baseline` — publication writes only allowed evidence and lifecycle output.

- `tests/test_roadmap_impact_run.py:test_current_v2_analysis_accepts_baseline_equal_stage_presentation_change` — stored version-2 analysis remains current without changing its final or raw provenance.

- `tests/test_roadmap_impact_run.py:test_current_v2_analysis_refuses_semantic_stage_source_record_or_brief_drift` — each independently changed currentness input returns no current analysis.

- `tests/test_roadmap_impact_run.py:test_current_impact_analysis_remains_read_only_for_versioned_evidence` — inspection neither logs nor publishes and returns the stored typed record only after version-specific admission.

### Tests for this step

Every listed test must be green before this step is complete. Run `uv run pytest tests/test_roadmap_impact_snapshot.py tests/test_roadmap_impact_analysis.py tests/test_roadmap_impact_run.py -q`, then run `uv run pytest tests/ -q -n auto`.

## Acceptance criteria

- Version-1 impact capture and analysis remain exact-raw, baseline-free, and compatible with existing immutable evidence.

- Version-2 snapshots retain raw source record, brief, stage text, and stage digest facts plus one complete canonical identity per configured stage in order.

- A version-2 stage presentation change is admitted only after strict decoding, parsing, and full baseline-identity equality; capture does not rewrite source or provenance.

- Missing, malformed, pending, wrongly bound, or semantically changed source state refuses without baseline enrollment, recovery, repair, or evidence publication.

- The final guarded recheck refuses any raw source-record, brief, or stage-artifact change after capture.

- Version-2 analysis construction requires matching evidence versions and a matching selected-stage canonical identity while rechecking selected live feedback separately.

- `current_impact_analysis` keeps version-1 exact candidate comparison and allows version-2 raw stage presentation drift only when all canonical and direct currentness checks pass.

- The focused impact tests and `uv run pytest tests/ -q -n auto` pass.

## References

- [YAML Ain’t Markup Language (YAML™) Revision 1.2.2https: — Use representation-level equality to separate parsed stage content from presentation.

- [hashlib — Secure Hashes and Message Digestshttps: — Use SHA-256 for immutable raw provenance and identity binding.

## Applicable guardrails

- **The plan’s “## Plan intent”, writer-owned freshness** — Read canonical freshness from the published baseline while retaining raw provenance as a separate fact.

- **The plan’s “## Step intent”, complete impact admission** — Bind every stage through the baseline and keep source-record and brief checks independent.

- **The plan’s “## Out of scope”, baseline lifecycle boundary** — These files may read baseline and pending state but must not initialize, publish, recover, or advance it.

- **The plan’s “## Out of scope”, source-mutation boundary** — Refuse unsafe state without canonicalizing, rewriting, or otherwise changing source bytes or raw provenance.

- **The plan’s “## Out of scope”, generated-candidate boundary** — Do not relax generated structural patch or proof canonicality, or malformed-scalar protection.

## Deferred

- Escalation receipt issuance and receipt inspection — Step 3 applies the same version-specific admission rule in `plan_tool/roadmap_escalation_run.py:run_roadmap_escalation_receipt` and `current_escalation_receipt`.

- Structural preflight version selection — Step 3 updates `plan_tool/roadmap_structural_revision.py:load_structural_revision_preflight` to choose the receipt-analysis pair’s snapshot rule.

- Shared source-admission consolidation — Keep `plan_tool/roadmap.py:_admit_loaded_stage_artifact` and `plan_tool/roadmap_escalation_selection.py:canonical_artifact_snapshot` outside this footprint; any later unification needs a separate reconciliation decision because their working-value and feedback roles differ.
