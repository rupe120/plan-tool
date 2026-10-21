> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 4 — Remove unreachable version dispatch from the impact-analysis lifecycle while keeping immutable analysis publication unchanged

## Summary

Make impact analysis use the version-2 baseline-identity rule from snapshot capture through inspection. Update `plan_tool/roadmap_impact_analysis.py`, `plan_tool/roadmap_impact_snapshot.py`, and `plan_tool/roadmap_impact_run.py` to remove version-1 shapes, defaults, and currentness branches. Preserve canonical analysis rendering, semantic identity, writer-guard ordering, snapshot recheck, and immutable evidence reuse. On green, a fresh version-2 analysis remains current across presentation-only source changes, while a source change during capture-to-publication still prevents publication.

## Table of Contents

- [Summary](#summary) — Reviewer overview of the version-2-only impact lifecycle.
- [Table of Contents](#table-of-contents) — Links to each section in this detail.
- [Why](#why) — Why the remaining legacy branches must be removed.
- [Input](#input) — Upstream schema and snapshot contracts this step relies on.
- [Files (creates vs edits)](#files-creates-vs-edits) — Production and test files changed in this step.
- [Implementation](#implementation) — Required version-2-only analysis, snapshot, and publication behavior.
- [Tests](#tests) — Focused regression coverage for the surviving lifecycle.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Validation, serialization, and parametrized-test references.
- [Applicable guardrails](#applicable-guardrails) — Plan boundaries that constrain this cleanup.
- [Deferred](#deferred) — Related work outside this step’s declared scope.

## Why

Version 2 already provides the baseline-backed identity and presentation-drift behavior that impact analysis needs, but the lifecycle still carries optional nested evidence, version-1 raw-digest checks, and version-selected snapshot capture. After step 2 rejects version 1 at the evidence boundary and step 3 removes receipt-side dispatch, those branches can no longer describe a valid route. Removing them gives capture, analysis construction, occupied-final reuse, and inspection one currentness rule without changing how immutable analysis finals are published.

## Input

- **Step 2’s version-2-only schema outcome:** Treat `schema_version: 2` and the required canonical identities as the only valid receipt and analysis evidence shape. Do not add a conversion or fallback path for version-1 bytes.

- **Step 3’s receipt admission outcome:** `plan_tool/roadmap_source_identity.py:admitted_source_is_current` remains the shared baseline-identity currentness check used by `plan_tool/roadmap_impact_analysis.py:_receipt_matches_captured_artifact`.

- **Snapshot binding:** `plan_tool/roadmap_impact_snapshot.py:RoadmapImpactSnapshot` retains captured source text, parsed artifacts, raw digests, and canonical source identities. Raw digests remain observed provenance and recheck inputs; canonical identities decide presentation-tolerant currentness.

- **Immutable publication boundary:** `plan_tool/roadmap_impact_run.py:_run_while_guarded` uses `plan_tool/roadmap_evidence_store.py:publish_evidence` after a successful snapshot recheck. Existing finals remain immutable and can only be reused or reported as collisions.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `plan_tool/roadmap_impact_analysis.py` — Require the version-2 nested receipt and snapshot evidence shape, remove version-1 serialization and validation branches, and keep the version-2 semantic-currentness comparison.
  - `plan_tool/roadmap_impact_run.py` — Capture the single supported snapshot shape during preflight and inspection, then use one comparison path for current analyses.
  - `plan_tool/roadmap_impact_snapshot.py` — Remove selectable evidence-version capture behavior while preserving baseline admission, captured raw provenance, gate checks, and recheck binding.
  - `tests/test_roadmap_impact_analysis.py` — Replace legacy-shape coverage with version-2-required evidence, semantic identity, and immutable-reuse coverage.
  - `tests/test_roadmap_impact_run.py` — Use version-2 receipt fixtures throughout the run and inspection lifecycle tests.
  - `tests/test_roadmap_impact_snapshot.py` — Make version-2 baseline-backed capture the normal fixture path and retain presentation-change recheck coverage.
  - `tests/cli/test_roadmap_cmd.py` — Keep impact-analysis command and view behavior covered without legacy-version fixtures or names.

## Implementation

- **Require one persisted analysis shape.** In `plan_tool/roadmap_impact_analysis.py:ImpactReceiptEvidence` and `ImpactSnapshotEvidence`, require explicit version-2 discriminators and their canonical identities. Remove optional identity fields, omitted-version interpretation, and `_FrozenModel.version`; `ImpactAnalysis` must still serialize its `schema_version` and all required version-2 evidence.

- **Keep raw provenance but do not make it the freshness rule.** `build_impact_analysis`, `_impact_receipt_evidence_fields`, `_impact_snapshot_evidence_fields`, and `_impact_snapshot_hash_fields` must retain the recorded raw receipt and artifact digests where the analysis contract already records them. Continue excluding presentation-only raw digest changes from the semantic identity while retaining source-record and brief digests as direct inputs.

- **Use canonical identities for every valid analysis binding.** Keep `_requires_bound_evidence_and_route_precedence`, `_snapshot_evidence`, and `_receipt_matches_captured_artifact` enforcing selected-stage identity agreement, configured artifact order, selected feedback binding, and route precedence. Remove the alternate raw-digest binding rule rather than weakening these checks.

- **Keep one occupied-final comparison.** `classify_existing_impact_analysis` and `plan_tool/roadmap_impact_run.py:current_impact_analysis` must compare rebuilt analyses with the existing presentation-tolerant logic in `version2_analysis_matches`. Do not replace it with full rendered-byte equality: a fresh analysis after a presentation-only source change can render different provenance bytes but must reuse the same immutable final.

- **Capture only baseline-backed snapshots.** Make `plan_tool/roadmap_impact_snapshot.py:capture_roadmap_impact_snapshot`, `_capture_artifact`, `snapshot_artifacts_match_captured_text`, and `recheck_roadmap_impact_snapshot` operate on the single version-2 shape. Every captured stage must pass baseline admission and supply a stage-ordered canonical identity. Keep the original source text and digest so recheck still detects any change made after capture.

- **Preserve the two timing rules for presentation changes.** A new capture may accept source text whose presentation differs from its baseline when the canonical identity matches. A recheck of an already-captured snapshot must still reject any raw source change before publication. This prevents a run from publishing against inputs that changed in its capture-to-write window.

- **Keep publication ordering unchanged.** In `plan_tool/roadmap_impact_run.py:run_roadmap_impact_analysis`, `_resolve_preflight`, and `_run_while_guarded`, retain recovery under `roadmap_writer_guard`, then capture, closure resolution, analysis construction, snapshot recheck, and `publish_evidence`. The runner must not rewrite roadmap artifacts, baselines, receipts, or an occupied analysis final.

- **Do not widen the comparator cleanup.** Keep `plan_tool/roadmap_impact_analysis.py:version2_analysis_matches` available under its existing name because `plan_tool/roadmap_structural_revision.py:_matches_rebuilt_analysis` imports it outside this step’s file list. Remove dispatch from this impact lifecycle without changing structural-revision code.

- **Keep CLI behavior stable.** `plan_tool/cli/roadmap_cmd.py:_cmd_roadmap_impact_analysis` and `_cmd_roadmap_impact_analyses_view` remain thin callers. Update only their declared test coverage as needed; do not add version selection, fallback output, or a new command mode.

## Tests

### Tests for this step

- `test_analysis_round_trips_with_required_version2_identities` — verifies rendered and parsed analysis evidence always includes version 2 and both required canonical-identity projections.

- `test_analysis_rejects_missing_or_mismatched_version2_identity_evidence` — verifies omitted nested versions, omitted identities, and inconsistent selected-stage identities cannot form an analysis.

- `test_analysis_semantic_id_dedups_presentation_only_source_drift` — verifies raw receipt and artifact digest changes do not alter a version-2 analysis semantic ID when canonical identities remain the same.

- `test_existing_analysis_reuses_presentation_only_drift` — verifies `classify_existing_impact_analysis` reuses the immutable final for a semantically matching rebuilt analysis and rejects direct-input drift.

- `test_capture_records_baseline_identities_and_observed_raw_provenance` — verifies a captured snapshot contains all stage-ordered canonical identities and its observed raw digests.

- `test_capture_accepts_baseline_equal_presentation_without_rewriting_source` — verifies capture accepts presentation-only source differences without changing source files or baselines.

- `test_recheck_refuses_raw_presentation_change_before_publication` — verifies a source presentation change after capture makes the snapshot stale before evidence publication.

- `test_run_publishes_without_mutating_roadmap_source_or_baseline` — verifies the guarded runner publishes an analysis while leaving roadmap artifacts and baseline files unchanged.

- `test_existing_analysis_reuses_after_presentation_only_source_drift` — verifies a later run reuses, rather than overwrites or duplicates, the same immutable analysis final.

- `test_current_analysis_accepts_presentation_change_without_side_effects` — verifies inspection reports a fresh version-2 analysis as current after presentation-only drift and performs no publication.

- `test_current_analysis_refuses_semantic_and_direct_input_drift` — verifies inspection does not report current when canonical stage content, recorded source, or brief content changes.

- `test_impact_analysis_view_bootstraps_reader_lock` — verifies the CLI view keeps its guarded, redacted output behavior with version-2 analysis fixtures and no legacy-only claim.

- `test_run_refuses_a_version1_receipt_with_no_route_or_publication` — verifies `run_roadmap_impact_analysis` returns `invalid` for a version-1 receipt with no route resolution and no evidence write, proving the reader-refusal matrix's impact-publication boundary survives dispatch removal rather than raising an unhandled error.

- `test_current_analysis_refuses_a_version1_record_with_no_route` — verifies `current_impact_analysis` returns `invalid` with no route for a version-1 analysis or receipt input, matching the plan's reader-refusal matrix for impact inspection.

- `test_impact_analysis_view_refuses_a_version1_record_without_crashing` — verifies `_cmd_roadmap_impact_analyses_view` renders the documented refusal output for a version-1 record: no crash, no silent upgrade, no claim that it is current.

Every listed test must be green before this step is considered finished.

## Acceptance criteria

- Valid impact analyses always contain `schema_version: 2`, nested receipt and snapshot version fields, and the required canonical identities.

- Version-1 or identity-omitting analysis evidence is rejected at the schema boundary and never reaches snapshot capture, route selection, or publication.

- `capture_roadmap_impact_snapshot` has one baseline-backed capture path; it preserves raw captured text and digests while retaining stage-ordered canonical identities.

- A raw presentation change after capture causes `recheck_roadmap_impact_snapshot` to reject publication.

- A new run or inspection after presentation-only drift reports the analysis current or reuses its existing final without overwriting that final.

- Semantic stage changes, recorded-brief source changes, and brief-content changes do not report an existing analysis as current.

- `run_roadmap_impact_analysis` still recovers publication state under the writer guard, rechecks before calling `publish_evidence`, and leaves roadmap artifacts and baselines unchanged.

- The declared impact production files contain no version-1 dispatch branch.

- `run_roadmap_impact_analysis`, `current_impact_analysis`, and the impact-analyses CLI view each return the documented `invalid`/no-route/no-publication result for a version-1 record, with no crash and no silent upgrade — the reader-refusal matrix's impact-lifecycle boundaries stay proven by a direct test, not only by dispatch removal.

- The focused impact-analysis, snapshot, runner, and CLI tests pass.

## References

- [Validators | Pydantic Docshttps: — Use model and field validation to require version-2 nested evidence and cross-field identity binding.

- [Fields | Pydantic Docshttps: — Check required-field and strict-type behavior when removing legacy defaults.

- [Serialization | Pydantic Docshttps: — Preserve explicit schema discriminators and canonical JSON model output.

- [How to parametrize fixtures and test functionshttps: — Cover presentation-only and semantic-drift cases across the surviving reader paths.

## Applicable guardrails

- **Single-schema reader goal:** The plan’s `## Plan intent` requires this lifecycle to use the one surviving evidence schema. Remove the alternate path without changing the surviving version-2 behavior.

- **Impact-only lifecycle:** The plan’s `## Step intent` limits this work to impact snapshot capture, analysis construction, publication, and inspection. Do not expand into receipt or structural-revision behavior.

- **Surviving version-2 contract:** The plan’s `## Out of scope`, version-2 semantics boundary, keeps baseline admission and canonical-identity behavior fixed while this step removes dead branches.

- **No legacy conversion:** The plan’s `## Out of scope`, evidence-upgrade boundary, prevents this step from inferring identities or converting old immutable finals.

- **Structural-operation boundary:** The plan’s `## Out of scope`, structural protocol boundary, keeps structural operation modules and their separate protocol unchanged.

## Deferred

- Structural-revision dispatch cleanup — `plan_tool/roadmap_structural_revision.py:_require_snapshot_binding` and `_matches_rebuilt_analysis`, plus their structural-revision tests, remain outside this impact-lifecycle step.

- Generic version-1 evidence conversion — remains outside this step because conversion would require facts that legacy evidence does not provide.
