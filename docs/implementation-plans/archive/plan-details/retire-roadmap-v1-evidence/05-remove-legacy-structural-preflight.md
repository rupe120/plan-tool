> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 5 — Remove legacy structural preflight branches while preserving journal recovery and journaled artifact-and-seed replacement

## Summary

Make structural revision preflight accept and compare only the version-2 evidence shape supplied by step 4. Update `plan_tool/roadmap_structural_revision.py` and `plan_tool/roadmap_structural_revision_run.py` to remove version-1 currentness and render-canonical fallbacks while retaining the existing exact-pair, feedback, route, and publication checks. Keep journal recovery, the guarded recheck, and journaled artifact, baseline, and seed-state replacement unchanged. On green, unsupported evidence fails closed at the structural reader, while valid version-2 evidence continues through one bounded structural publication path.

## Table of Contents

- [Summary](#summary) — Reviewer overview of the structural preflight cleanup.
- [Table of Contents](#table-of-contents) — Links to each section in this detail.
- [Why](#why) — Why structural revision must stop carrying a second evidence rule.
- [Input](#input) — Upstream version-2 and publication contracts this step consumes.
- [Files (creates vs edits)](#files-creates-vs-edits) — Production and test files changed in this step.
- [Implementation](#implementation) — Required single-schema preflight and preserved publication ordering.
- [Tests](#tests) — Focused refusal, currentness, recovery, and replacement coverage.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Validation and parametrized-test references.
- [Applicable guardrails](#applicable-guardrails) — Plan boundaries that limit this cleanup.
- [Deferred](#deferred) — Nearby work that remains outside this step.

## Why

Structural revision still selects behavior from evidence and snapshot versions even though step 4 supplies one version-2 analysis and snapshot contract. Those branches can let unsupported input reach a structural route or make presentation-only drift follow the wrong comparison rule. Removing them gives the structural reader one baseline-identity rule without weakening the publication journal that protects destructive artifact and seed updates.

## Input

- **Step 2’s schema boundary:** Treat `plan_tool/roadmap_escalation.py:parse_receipt` and `plan_tool/roadmap_impact_analysis.py:parse_impact_analysis` as the rejection point for unsupported persisted evidence. `plan_tool/roadmap_structural_revision.py:load_structural_revision_preflight` must translate that failure to `StructuralRevisionPreflightError` without attempting snapshot capture.

- **Step 4’s single snapshot contract:** Use the landed version-2-only behavior of `plan_tool/roadmap_impact_snapshot.py:capture_roadmap_impact_snapshot`, `recheck_roadmap_impact_snapshot`, and `snapshot_artifacts_match_captured_text`. Keep raw digests as recorded provenance, while canonical source identities decide presentation-tolerant currentness.

- **Analysis comparison:** `plan_tool/roadmap_impact_analysis.py:version2_analysis_matches` remains the surviving comparison for a rebuilt analysis. Structural preflight must not add another raw-digest currentness rule.

- **Publication journal:** `plan_tool/roadmap_revision_publish.py:publish_structural_revision_proof` calls `load_structural_revision_preflight` both before and during its journaled replacement boundary. Preserve `writer_token` and `allowed_pending_generation` on the preflight API so the second call can admit only its exact active structural generation.

- **Publication regression coverage:** `tests/test_roadmap_revision_publish.py:test_structural_publication_rechecks_exact_evidence_and_complete_snapshot_under_one_lease` and `tests/test_roadmap_revision_publish.py:test_structural_publication_writes_exact_proved_bytes_to_only_the_matched_artifact` remain no-diff checks for the publisher contract.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `plan_tool/roadmap_structural_revision.py` — Collapse preflight binding, snapshot binding, rebuilt-analysis comparison, and snapshot capture onto the version-2 contract while retaining pending-generation admission.
  - `plan_tool/roadmap_structural_revision_run.py` — Remove the version-1 render-canonical fallback from `_preflight_is_canonical` and keep the runner’s recovery, refusal, and publication ordering.
  - `tests/test_roadmap_structural_revision.py` — Replace version-1 success fixtures with version-2 fixtures, retain one explicit legacy fixture for refusal, and cover journal admission under the surviving contract.
  - `tests/test_roadmap_structural_revision_run.py` — Update runner fixtures to complete version-2 snapshots and cover unsupported snapshot rejection, recovery ordering, and unchanged replacement outcomes.

## Implementation

- **Foundational logic: version-2-only structural preflight binding.** Make `plan_tool/roadmap_structural_revision.py:load_structural_revision_preflight` build and recheck one baseline-backed snapshot shape. Do not retain an evidence-version argument or conditional solely for this caller after step 4 removes that selection.

- **Bind canonical identities on every accepted pair.** Simplify `plan_tool/roadmap_structural_revision.py:_require_pair_binding` so receipt identity, analysis receipt identity, and the selected snapshot identity always agree. Keep the exact final name, semantic ID, selector, target, reason, and raw-source provenance checks; remove only the version-specific branch around the required canonical identity.

- **Keep presentation drift valid.** Simplify `plan_tool/roadmap_structural_revision.py:_require_snapshot_binding` and `_matches_rebuilt_analysis` to use the version-2 identity comparison. Do not replace this with full raw artifact-digest or rendered-byte equality, because valid presentation-only source changes must remain current.

- **Fail closed instead of falling back.** Make `plan_tool/roadmap_structural_revision_run.py:_preflight_is_canonical` use the version-2 snapshot self-consistency check and return `False` for an unsupported snapshot version. Do not leave an `else` path that treats an unknown value as version 1.

- **Retain exact selected-artifact checks.** `_preflight_is_canonical` must continue to confirm that the selected stage, artifact, and captured text match the admitted snapshot before the evaluator reply can be processed. Keep `plan_tool/roadmap_impact_snapshot.py:snapshot_artifacts_match_captured_text` as the full-snapshot check rather than validating only the selected artifact.

- **Keep route and feedback limits unchanged.** Preserve `plan_tool/roadmap_structural_revision.py:_current_selected_slice`, `_resolve_current_closure`, and the `requires-scope-review` refusal in `load_structural_revision_preflight`. Same-artifact and cross-artifact evidence remain admissible preflight routes, but the writer stays limited to the selected artifact.

- **Preserve recovery before ordinary preflight.** In `plan_tool/roadmap_structural_revision_run.py:run_structural_revision`, retain `roadmap_writer_guard` followed by `recover_roadmap_publication` before the ordinary call to `load_structural_revision_preflight`. A recovered or absent journal is required before a new attempt can read evidence.

- **Preserve the journaled recheck path.** Keep `plan_tool/roadmap_structural_revision.py:_require_structural_pending_generation` and the `writer_token` / `allowed_pending_generation` parameters. `plan_tool/roadmap_revision_publish.py:publish_structural_revision_proof` must still be able to re-enter preflight after it records the exact `structural-feedback-publication` generation and before it replaces artifact, baseline, and seed-state members.

- **Keep runner results redacted and ordered.** `run_structural_revision` must continue to map a structural preflight rejection to `preflight-rejected` / `evidence-rejected` without invoking the model transport or publisher. This is the boundary the legacy-refusal test proves, given an available evaluator — `verified_structural_evaluator` wraps `load_structural_revision_preflight`, so an unavailable evaluator is classified `evaluator-rejected` before evidence is ever examined, a pre-existing ordering this step does not change. Keep the fact-free final-name and evaluator-availability checks ahead of evidence-derived logging.

- **Do not widen the cleanup.** Leave `plan_tool/roadmap_revision_publish.py` unchanged. Its journal write, replacement, verification, recovery, and seed-state behavior is the contract this step preserves, not code to consolidate.

## Tests

Update the focused structural fixtures to use complete version-2 snapshots and canonical identities. Keep one deliberately legacy wire fixture only for the reader-refusal case.

### Tests for this step

- `tests/test_roadmap_structural_revision.py:test_preflight_binds_exact_current_version2_evidence_and_selected_slice` — verifies a valid version-2 pair binds the selected artifact, feedback, raw provenance, and canonical identity.

- `tests/test_roadmap_structural_revision.py:test_preflight_rejects_legacy_evidence_before_snapshot_capture` — verifies an explicit unarchived version-1 receipt or analysis fails as `StructuralRevisionPreflightError` and never starts snapshot capture.

- `tests/test_roadmap_structural_revision.py:test_preflight_pair_rejects_conflicting_version2_canonical_identity` — verifies a receipt and analysis with mismatched selected-stage identities cannot bind.

- `tests/test_roadmap_structural_revision.py:test_rebuilt_v2_analysis_ignores_raw_snapshot_presentation_digests` — verifies presentation-only raw digest changes do not make a rebuilt valid analysis stale.

- `tests/test_roadmap_structural_revision.py:test_preflight_allows_only_the_active_structural_publication_generation` — verifies ordinary preflight refuses a journal and the guarded recheck admits only the exact active structural generation.

- `tests/test_roadmap_structural_revision.py:test_preflight_allows_same_and_cross_routes_without_widening_selected_artifact` — verifies both accepted route classes preserve the one-artifact writer boundary.

- `tests/test_roadmap_structural_revision.py:test_preflight_rejects_scope_review_and_redacts_reviewer_request` — verifies the scope-review refusal remains after the version cleanup and does not expose request text.

- `tests/test_roadmap_structural_revision_run.py:test_structural_preflight_accepts_v2_presentation_drift_on_an_unselected_stage` — verifies full-snapshot self-consistency accepts valid presentation-only drift outside the selected artifact.

- `tests/test_roadmap_structural_revision_run.py:test_structural_preflight_accepts_v2_presentation_drift_on_the_selected_stage` — verifies the selected artifact follows the same presentation-tolerant rule.

- `tests/test_roadmap_structural_revision_run.py:test_structural_preflight_rejects_unsupported_snapshot_version_before_backend` — verifies a value other than 2 cannot enter the old fallback and reaches neither the model invoker nor publication.

- `tests/test_roadmap_structural_revision_run.py:test_structural_runner_recovers_publication_before_structural_preflight` — verifies recovery runs under the writer guard before evidence preflight starts.

- `tests/test_roadmap_structural_revision_run.py:test_structural_runner_reports_unrecoverable_publication_state_cleanly` — verifies an unrecoverable journal stops the attempt without a structural invocation.

- `tests/test_roadmap_structural_revision_run.py:test_structural_runner_maps_legacy_preflight_rejection_to_evidence_rejected` — verifies the runner reports the structural reader’s legacy refusal without invoking the model transport or the publisher, using an available evaluator so `evaluator-rejected` is not what the test exercises.

- `tests/test_roadmap_structural_revision_run.py:test_structural_interrupt_after_replacement_boundary_is_unknown` — verifies an interrupt after the journaled replacement boundary retains the unknown-after-interrupt publication result.

Every listed test must be green before this step is considered finished.

## Acceptance criteria

- `plan_tool/roadmap_structural_revision.py:load_structural_revision_preflight` accepts only the version-2 receipt, analysis, and snapshot contract supplied by steps 2 and 4.

- An unarchived version-1 evidence pair raises `StructuralRevisionPreflightError` before snapshot capture, route construction, model invocation, or publication.

- `plan_tool/roadmap_structural_revision.py` and `plan_tool/roadmap_structural_revision_run.py` contain no roadmap-evidence branch that selects version-1 behavior; the independent operation-envelope protocol remains untouched.

- Valid version-2 presentation-only drift passes `_preflight_is_canonical`, while any unsupported snapshot version is rejected before the model invoker and publisher.

- Same-artifact and cross-artifact evidence retain their existing preflight behavior, and `requires-scope-review` remains refused.

- `run_structural_revision` recovers a pending publication under `roadmap_writer_guard` before ordinary structural preflight.

- The publisher can still pass its exact active structural generation through `writer_token` and `allowed_pending_generation` for the final journaled recheck.

- `uv run pytest tests/test_roadmap_structural_revision.py tests/test_roadmap_structural_revision_run.py -q` passes, and `uv run pytest tests/ -q -n auto` remains green.

## References

- [Validators | Pydantic Docshttps: — Use the schema boundary to reject unsupported persisted evidence before structural preflight consumes it.

- [Serialization | Pydantic Docshttps: — Preserve the required version-2 discriminator and identity fields while comparing admitted evidence.

- [How to parametrize fixtures and test functionshttps: — Cover supported version-2 inputs, explicit legacy refusal, and unsupported snapshot values without duplicating fixtures.

## Applicable guardrails

- **Single-schema reader goal:** The plan’s `## Plan intent` requires structural preflight to use the one surviving evidence schema and keep its version-2 behavior unchanged.

- **Structural safety boundary:** The plan’s `## Step intent` requires unsupported input to stop before structural work while preserving the destructive publication safeguards.

- **Stable version-2 contract:** The plan’s `## Out of scope`, version-2 semantics boundary, keeps baseline admission and canonical-identity behavior fixed during this cleanup.

- **No conversion path:** The plan’s `## Out of scope`, evidence-upgrade boundary, prevents preflight from repairing, inferring, or converting legacy evidence.

- **No consolidation work:** The plan’s `## Out of scope`, closed consolidation boundary, keeps the established currentness operations separate.

- **Unrelated gate work:** The plan’s `## Out of scope`, adjacent receipt-preflight boundary, keeps unrelated gate changes out of these files.

- **Operation-envelope boundary:** The plan’s `## Out of scope`, structural protocol boundary, keeps the independent structural operation protocol and its tests unchanged.

## Deferred

- Publication-module refactoring — `plan_tool/roadmap_revision_publish.py` remains outside this step’s footprint; retain its recovery and journaled replacement contract through the focused regression suite.

- Structural operation-envelope changes — `plan_tool/roadmap_structural_operations.py` and its protocol tests remain outside this evidence-reader cleanup.

- Generic legacy-evidence conversion — retain the plan’s upgrade path rather than adding conversion behavior at structural preflight.
