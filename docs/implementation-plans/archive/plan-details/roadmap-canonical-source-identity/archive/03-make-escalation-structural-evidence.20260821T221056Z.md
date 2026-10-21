> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 3 — Make escalation and structural-evidence readers admit only current versioned evidence

## Summary

Make receipt creation, receipt inspection, and structural preflight apply the versioned freshness boundary established by steps 1 and 2. Update `plan_tool/roadmap_escalation_selection.py`, `plan_tool/roadmap_escalation_run.py`, and `plan_tool/roadmap_structural_revision.py` so version 2 uses an admitted baseline identity for stage semantics while version 1 remains exact-raw. Recheck live feedback separately from stage semantics, and keep source-record and brief checks active for structural evidence. On green, readers accept only current, matching-version evidence without writing or repairing baseline state.

## Table of Contents

- [Summary](#summary) — Reviewer-level result and main design choice.
- [Table of Contents](#table-of-contents) — Links to each section in this detail.
- [Why](#why) — The current raw-digest-only reader boundary.
- [Input](#input) — Versioned evidence and snapshot contracts from earlier steps.
- [Files (creates vs edits)](#files-creates-vs-edits) — Scoped code and test updates.
- [Implementation](#implementation) — Version-aware reader admission and refusal rules.
- [Tests](#tests) — Focused coverage for each admission boundary.
- [Acceptance criteria](#acceptance-criteria) — Observable completion conditions.
- [References](#references) — Canonical-value and hashing references.
- [Applicable guardrails](#applicable-guardrails) — Reader-only scope limits.
- [Deferred](#deferred) — Work owned by later documentation and separate writer surfaces.

## Why

`plan_tool/roadmap_escalation_run.py:current_escalation_receipt` and `plan_tool/roadmap_structural_revision.py:load_structural_revision_preflight` currently use raw stage digests as freshness checks. That rejects a valid version-2 baseline-backed stage state when its observed bytes differ, while a baseline match alone would be unsafe if feedback, the recorded source, or the brief changed. This step makes each reader apply the same versioned boundary without widening any reader into a baseline writer.

## Input

- **Step 1 evidence contract:** Consume the version-specific `plan_tool/roadmap_escalation.py:EscalationReceipt` and `plan_tool/roadmap_impact_analysis.py:ImpactAnalysis` shapes. Version 1 retains exact-raw behavior; version 2 carries an explicit canonical-freshness identity and never derives one from legacy evidence.

- **Step 2 snapshot contract:** Consume the baseline-backed stage identities and independent source-record and brief facts supplied by `plan_tool/roadmap_impact_snapshot.py:RoadmapImpactSnapshot` and `capture_roadmap_impact_snapshot`. Do not recreate snapshot capture in these readers.

- **Baseline admission contract:** Read only through `plan_tool/roadmap_source_identity.py:baseline_path`, `load_baseline_record`, `compare_baseline`, and `load_pending_generation`. A pending, missing, malformed, wrongly bound, or semantically different baseline state is not current evidence.

- **Existing selection boundary:** Preserve `plan_tool/roadmap_escalation_selection.py:canonical_artifact_snapshot` for version-1 and generated-candidate renderer-byte validation, and preserve `select_receipt_feedback` as the live feedback and target eligibility check. Add a version-2 source-reader snapshot that requires strict UTF-8 and parsing but lets a full baseline comparison, rather than a renderer-byte match, decide semantic freshness.

## Files (creates vs edits)

- **New files:** None.

- **Existing files (edits only):**
  - `plan_tool/roadmap_escalation_selection.py` — Keep raw snapshot validation separate from baseline-backed version-2 admission, and carry only the redacted identity facts needed by receipt issuance.
  - `plan_tool/roadmap_escalation_run.py` — Make receipt creation and `current_escalation_receipt` version-aware and hold the reader-side source observation stable without changing source or baseline state.
  - `plan_tool/cli/roadmap_cmd.py` — Rescan and inspect escalation receipts inside the existing reader guard, with no scan-order-dependent cache reuse.
  - `plan_tool/roadmap_structural_revision.py` — Make exact-pair structural preflight compare current evidence by its matching version while retaining independent feedback, source-record, brief, closure, and route checks.
  - `tests/test_roadmap_escalation_selection.py` — Cover separation of raw source provenance, canonical freshness, and live feedback selection.
  - `tests/test_roadmap_escalation_run.py` — Cover version-2 issuance and receipt-currentness refusal paths without source mutation.
  - `tests/cli/test_roadmap_cmd.py` — Cover guarded receipt views and order-independent mixed-version source evaluation.
  - `tests/test_roadmap_structural_revision.py` — Cover version-aware structural preflight admission and refusal before returning context.
  - `tests/test_roadmap_structural_revision_run.py` — Keep structural reader refusals mapped to preflight rejection before seed invalidation or backend work.

## Implementation

- **Foundational rule:** Use the published baseline only to judge version-2 stage semantics. Keep raw bytes and their digest as immutable provenance, and continue to recheck live feedback eligibility independently.

- **Separate the two source-reader contracts.** Preserve `plan_tool/roadmap_escalation_selection.py:canonical_artifact_snapshot` rejection of unreadable, non-UTF-8, unparsable, and non-render-canonical source for version 1. Add a version-2 source-reader snapshot that still rejects unreadable, non-UTF-8, and unparsable source but retains a parsed renderer-different input and its raw digest for full baseline comparison. Do not normalize source bytes or let a baseline match excuse malformed current input; renderer-byte checks remain mandatory for generated patches, proofs, and immutable evidence finals.

- **Add a reader-only baseline admission path.** Near `canonical_artifact_snapshot` and `select_receipt_feedback`, provide the complete closed `CanonicalBaselineIdentity` needed to admit a version-2 selected stage against its writer-published baseline. Refuse incomplete publication and every baseline state the existing source-identity readers reject; compare all five identity fields, and do not initialize, recover, repair, or advance anything.

- **Issue only admitted version-2 receipts.** Update `plan_tool/roadmap_escalation_run.py:_resolve_preflight` and `run_roadmap_escalation_receipt` so a new receipt receives the canonical-freshness identity required by `plan_tool/roadmap_escalation.py:build_receipt`. A failed version-2 admission must reject preflight rather than issuing a new version-1 receipt.

- **Hold one stable reader observation for receipt creation.** In `run_roadmap_escalation_receipt`, acquire `plan_tool/roadmap_revision_publish.py:roadmap_reader_guard` before version-2 preflight. Keep it through artifact and baseline admission, the pending-generation refusal, final raw-snapshot recheck, and evidence publication. A missing or unusable reader guard, a pending generation, or a changed observation refuses before a receipt identity or handoff is exposed. The reader guard serializes with writers but gives this reader no writer token or mutation authority.

- **Keep receipt inspection version-specific.** In `current_escalation_receipt`, retain the current exact raw-digest and target checks for version 1 without a baseline read. For version 2, require the stored full canonical identity to fieldwise match the current admitted identity and re-run `select_receipt_feedback`; do not reject a version-2 receipt solely because its retained raw stage digest differs. Keep source-unavailable distinct from a readable source or baseline state that is no longer current.

- **Keep mixed-version inspection order-independent.** Update `plan_tool/cli/roadmap_cmd.py:_cmd_roadmap_escalations_view` to acquire `roadmap_reader_guard`, rescan receipts after the guard is held, and evaluate every record before releasing it. Change `current_escalation_receipt`’s cache key from stage alone to `(stage_key, receipt.schema_version)` (or an equivalent version-tagged observation) so version-1 exact-raw and version-2 baseline-equal evaluation never reuse each other’s verdict. A guard failure reports `guard-unavailable`; evidence scan order changes neither receipt’s status.

- **Keep structural pairing exact before current-state work.** In `plan_tool/roadmap_structural_revision.py:load_structural_revision_preflight`, retain the named-final reads, canonical evidence parsing, and `_require_pair_binding` ordering. A receipt and analysis must have matching versions and matching version-specific receipt identity before snapshot capture, closure resolution, or selected-feedback return.

- **Compare structural currentness by evidence version.** Keep version 1 on the existing exact raw selected-stage and full snapshot binding without a baseline read. For version 2, use the fieldwise-equal closed canonical identities captured by step 2 for stage semantics, while still requiring the stored and current source-record and brief digests, live feedback selection, target identity, closure, and route to agree. Do not rebuild a version-2 analysis final or turn its raw stage provenance into a freshness gate.

- **Keep structural authority unchanged.** Preserve `plan_tool/roadmap_structural_revision.py:_current_selected_slice`, `_resolve_current_closure`, and the `requires-scope-review` refusal boundary. A versioned admission result must not widen the selected artifact, relation closure, or structural writer’s publication scope.

- **Preserve redaction and preflight ordering.** Keep `plan_tool/roadmap_escalation_run.py:_emit_preflight` and the structural runner’s existing rejection path free of source prose, reviewer request text, and baseline contents. Reader refusal must happen before structural candidate work, seed invalidation, or backend invocation.

## Tests

### Tests for this step

Every test below, plus the existing strict decoding, canonical-rendering, redaction, and structural-proof cases in these files, must be green before this step is complete.

- `tests/test_roadmap_escalation_selection.py:test_versioned_selection_keeps_raw_provenance_separate_from_baseline_freshness` — A selected version-2 artifact retains its raw digest while exposing only the admitted redacted baseline identity for semantic freshness.

- `tests/test_roadmap_escalation_selection.py:test_v2_selection_admits_parseable_renderer_drift_only_with_full_baseline_identity` — A strict-UTF-8, parseable source with renderer-byte drift admits only through the full baseline identity; malformed or semantically different input refuses without normalization.

- `tests/test_roadmap_escalation_selection.py:test_versioned_selection_refuses_unadmitted_baseline_without_changing_feedback_rules` — Missing, pending, malformed, wrongly bound, or semantically different baseline state refuses version-2 admission while ordinary feedback and target checks retain their current order.

- `tests/test_roadmap_escalation_run.py:test_receipt_creation_requires_admitted_baseline_and_never_falls_back_to_v1` — Receipt creation rejects when version-2 baseline admission fails, publishes no receipt, and never emits a new version-1 record.

- `tests/test_roadmap_escalation_run.py:test_v2_receipt_creation_holds_reader_guard_across_admission_recheck_and_publish` — A pending or concurrently changed artifact/baseline pair rejects before receipt publication or handoff; a writer cannot interleave its generation through the guarded observation.

- `tests/test_roadmap_escalation_run.py:test_current_v1_receipt_requires_exact_raw_source_and_does_not_infer_v2_identity` — A legacy receipt remains fresh only for its exact current raw source and never gains canonical-freshness data.

- `tests/test_roadmap_escalation_run.py:test_current_v2_receipt_accepts_baseline_equal_stage_change_and_rechecks_feedback` — A version-2 receipt stays fresh across an allowed strict-UTF-8, parseable baseline-equal raw change only while the selected feedback row and target remain eligible.

- `tests/test_roadmap_escalation_run.py:test_current_v2_receipt_refuses_baseline_failure_without_mutating_source_or_baseline` — Readable but unadmitted baseline state renders the receipt non-fresh and leaves artifacts, baselines, and pending-generation state unchanged.

- `tests/cli/test_roadmap_cmd.py:test_escalations_view_rescans_and_evaluates_under_reader_guard` — The view holds the reader guard across its rescan and every receipt evaluation, and returns `guard-unavailable` without a usable guard.

- `tests/cli/test_roadmap_cmd.py:test_escalations_view_mixed_versions_is_order_independent` — The same selected stage with a raw-exact version-1 receipt and a baseline-equal renderer-different version-2 receipt produces the same separate statuses in either evidence order.

- `tests/test_roadmap_structural_revision.py:test_preflight_keeps_v1_exact_raw_currentness` — A version-1 receipt-analysis pair rejects when its current selected stage or snapshot raw binding differs.

- `tests/test_roadmap_structural_revision.py:test_preflight_accepts_current_v2_pair_with_baseline_equal_stage_bytes` — A matching version-2 pair admits an allowed parseable raw-stage difference without rebuilding a new final when canonical identity, source-record, brief, feedback, target, closure, and route remain current.

- `tests/test_roadmap_structural_revision.py:test_preflight_v2_refuses_each_independent_currentness_change` — Changed baseline semantics, feedback eligibility, source record, brief, target, closure, or mixed evidence version rejects preflight before structural context is returned.

- `tests/test_roadmap_structural_revision_run.py:test_structural_runner_refusal_matrix_stops_before_seed_or_backend` — Extend the existing refusal matrix to prove a versioned-evidence rejection remains `evidence-rejected` and reaches neither seed invalidation nor the backend.

## Acceptance criteria

- A new receipt is version 2 only when its selected stage has an admitted current baseline identity; no failed version-2 path emits version 1 evidence.

- Version-2 receipt creation holds one reader guard across artifact/baseline admission, pending-generation refusal, final recheck, and evidence publication; no receipt identity or handoff is exposed from an unstable source pair.

- `current_escalation_receipt` keeps version-1 receipts exact-raw with no baseline read and lets a version-2 receipt remain fresh across an allowed strict-UTF-8, parseable baseline-equal raw-stage change.

- Escalation views rescan and evaluate inside the reader guard, and a cache key includes the evidence version as well as the stage so mixed-version evidence is scan-order independent.

- A version-2 receipt becomes non-fresh when its baseline admission, selected feedback eligibility, or target binding changes, without modifying source, evidence, baselines, or pending publication state.

- `load_structural_revision_preflight` rejects mixed-version finals before snapshot capture and rejects every non-current version-2 input before returning selected structural context.

- Version-2 structural preflight retains direct source-record and brief checks, fieldwise compares the full closed baseline identity, and neither rebuilds a new evidence final nor uses a raw stage-digest mismatch alone to reject baseline-equal current semantics.

- Structural evidence rejection preserves the existing no-backend and no-seed-invalidation boundary.

- `uv run pytest tests/test_roadmap_escalation_selection.py tests/test_roadmap_escalation_run.py tests/test_roadmap_structural_revision.py tests/test_roadmap_structural_revision_run.py -q` passes, followed by `uv run pytest tests/ -q -n auto`.

## References

- [YAML Ain’t Markup Language (YAML™) Revision 1.2.2](https://yaml.org/spec/1.2.2/) — Use representation equality to distinguish stage semantics from source formatting and immutable raw provenance.
- [hashlib — Secure Hashes and Message Digests](https://docs.python.org/3.13/library/hashlib.html) — Use SHA-256 only for the immutable and versioned identities defined by the evidence contracts.

## Applicable guardrails

- **The plan’s “## Plan intent”, canonical-source boundary** — Treat the existing writer-published baseline as the only semantic freshness authority in these reader paths.

- **The plan’s “## Step intent”, live-feedback boundary** — Recheck live feedback and target eligibility separately from baseline-backed stage semantics.

- **The plan’s “## Out of scope”, baseline lifecycle boundary** — Do not add initialization, enrollment, publication, recovery, or revision-admission behavior to these files.

- **The plan’s “## Out of scope”, reader-mutation boundary** — Do not repair, canonicalize, migrate, or accept a hand-edited source through a reader path.

- **The plan’s “## Out of scope”, provenance and candidate boundary** — Preserve immutable raw provenance and leave generated structural patch and proof validation unchanged.

- **The plan’s “## Out of scope”, follow-up workflow boundary** — Do not add retention or hand-edit-to-feedback workflow behavior.

## Deferred

- Published descriptions of versioned receipt, analysis, and structural-reader behavior — Step 4 owns `ROADMAP_FORMAT.md`, `DATA_CONTRACT.md`, and `docs/ARCHITECTURE.md`.

- Baseline lifecycle changes in `plan_tool/roadmap_revision_publish.py` — Writer-owned publication and recovery remain outside this reader-only step.
