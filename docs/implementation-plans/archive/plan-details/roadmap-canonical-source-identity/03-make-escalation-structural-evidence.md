> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 3 — Make escalation and structural-evidence readers admit only current versioned evidence

## Summary

Make receipt creation, receipt inspection, and structural preflight apply the version-specific freshness rules from steps 1 and 2. Update `plan_tool/roadmap_escalation_selection.py`, `plan_tool/roadmap_escalation_run.py`, `plan_tool/cli/roadmap_cmd.py`, `plan_tool/roadmap_revision_publish.py`, and `plan_tool/roadmap_structural_revision.py` while preserving redacted outputs and refusal categories. Version 1 remains exact-raw; version 2 requires a strict, parsed source that matches its published baseline plus independently eligible live feedback. On green, ordinary readers reject pending, changed, mismatched-version, or semantically stale evidence, while the structural publisher can recognize only its own exact pending generation during its final guarded recheck.

## Table of Contents

- [Summary](#summary) — Reviewer-level outcome and version boundary.
- [Table of Contents](#table-of-contents) — Links to every section in this detail.
- [Why](#why) — The reader-currentness gap this step closes.
- [Input](#input) — Contracts supplied by steps 1 and 2.
- [Files (creates vs edits)](#files-creates-vs-edits) — Scoped production and test changes.
- [Implementation](#implementation) — Versioned admission, stable receipt reads, and structural preflight rules.
- [Tests](#tests) — Focused freshness, pending-state, and refusal coverage.
- [Acceptance criteria](#acceptance-criteria) — Observable completion conditions.
- [References](#references) — Canonical-value and digest references.
- [Applicable guardrails](#applicable-guardrails) — Reader-only and strict-candidate limits.
- [Deferred](#deferred) — Work outside this step.

## Why

`plan_tool/roadmap_escalation_run.py:current_escalation_receipt` currently judges receipt freshness through a raw source digest, while `plan_tool/roadmap_structural_revision.py:load_structural_revision_preflight` rebuilds evidence from the current snapshot. Those paths need the same distinction that step 2 introduces for impact evidence: raw bytes remain immutable provenance, but version 2 may accept a presentation-only source change only when the published baseline confirms unchanged stage semantics. The reader must also observe source and baseline state consistently so it cannot expose evidence during a recoverable publication or apply one version’s rule to another version’s evidence.

## Input

- **Step 1 evidence contracts:** Use the landed version-specific forms of `plan_tool/roadmap_escalation.py:EscalationReceipt` and `plan_tool/roadmap_impact_analysis.py:ImpactAnalysis`. The parsed evidence version selects the currentness rule; landed field names and validators win over this detail.

- **Step 1 source identity:** Read `plan_tool/roadmap_source_identity.py:BaselineRecord`, `baseline_path`, `load_baseline_record`, `compare_baseline`, `pending_generation_path`, and `load_pending_generation` only as side-effect-free reader inputs.

- **Step 2 impact snapshot:** Use `plan_tool/roadmap_impact_snapshot.py:capture_roadmap_impact_snapshot` and `RoadmapImpactSnapshot` when structural preflight rebuilds the selected analysis. Step 2 owns version-aware impact-analysis inspection in `plan_tool/roadmap_impact_run.py:current_impact_analysis`.

- **Existing structural boundary:** Preserve `plan_tool/roadmap_structural_revision.py:load_structural_revision_preflight`, `StructuralRevisionPreflightError`, and `StructuralRevisionFeedbackIneligibleError`. `plan_tool/roadmap_revision_publish.py:publish_structural_revision_proof` calls this preflight before proving and again immediately before replacement.

## Files (creates vs edits)

- **New files:** None.

- **Existing files (edits only):**
  - `plan_tool/cli/roadmap_cmd.py` — Make `--view escalations` inspect a reader-guarded evidence set and render only currently admitted versioned receipts.
  - `plan_tool/roadmap_escalation_selection.py` — Add version-aware source admission while leaving live feedback selection separate from baseline semantics.
  - `plan_tool/roadmap_escalation_run.py` — Apply stable versioned admission to receipt issuance and `current_escalation_receipt`, including version-aware source caching and final rechecks.
  - `plan_tool/roadmap_revision_publish.py` — Bind the structural publisher’s final preflight to its own active token and exact pending generation without changing recovery or replacement behavior.
  - `plan_tool/roadmap_structural_revision.py` — Bind the exact versioned receipt-analysis pair to the current snapshot and preserve feedback-specific refusal.
  - `tests/cli/test_roadmap_cmd.py` — Cover guarded receipt inspection, redacted refusal, and mixed-version order independence.
  - `tests/test_roadmap_escalation_selection.py` — Cover pure version-specific source admission and independent feedback eligibility.
  - `tests/test_roadmap_escalation_run.py` — Cover stable receipt issuance, final recheck, and no-publication failures.
  - `tests/test_roadmap_revision_publish.py` — Cover the publisher’s exact active-generation allowance and refusal of every other journal state.
  - `tests/test_roadmap_structural_revision.py` — Cover current versioned structural binding and refusal classification.
  - `tests/test_roadmap_structural_revision_run.py` — Cover runner behavior when strengthened preflight rejects evidence.

## Implementation

- **Apply one versioned admission rule.** Treat a selected receipt source as current only when its version-specific source condition and its live feedback condition both pass. Version 1 keeps exact-raw behavior and must not read or infer a baseline identity. Version 2 requires strict UTF-8, successful parsing, a matching published baseline identity, and no pending publication.

- **Keep provenance separate from freshness.** Extend `plan_tool/roadmap_escalation_selection.py:canonical_artifact_snapshot` and its narrow result model, or add an adjacent helper, so receipt paths retain observed raw bytes and their digest without treating raw equality as version-2 freshness. A version-2 presentation-only change is admissible only after the complete baseline comparison succeeds; do not normalize, re-render, or rewrite source bytes.

- **Keep feedback selection independent.** Preserve `plan_tool/roadmap_escalation_selection.py:select_receipt_feedback` as the authority for unique, open, unanswered feedback that points to one live target. The baseline excludes feedback, so matching stage semantics never makes a stale or ineligible feedback row current.

- **Use a stable receipt observation.** In `plan_tool/roadmap_escalation_run.py:run_roadmap_escalation_receipt` and its preflight path, use `plan_tool/roadmap_revision_publish.py:roadmap_reader_guard` across baseline and artifact admission, pending-generation inspection, final raw-source recheck, and evidence publication. Refuse if the observed source, baseline identity, raw provenance, or live feedback changes before publication; do not fall back to issuing version 1.

- **Preserve receipt safety surfaces.** Keep `EscalationRunResult`, redacted lifecycle logging, immutable final-name validation, collision handling, and existing receipt reuse behavior. A failed versioned admission publishes no receipt and must not put source prose, reviewer requests, baseline projections, or repair guidance into a result or log.

- **Make escalation views stable and order-independent.** Update `plan_tool/cli/roadmap_cmd.py:_cmd_roadmap_escalations_view` to rescan under a reader guard, following the coordination pattern in `_cmd_roadmap_impact_analyses_view`. Update `plan_tool/roadmap_escalation_run.py:current_escalation_receipt` so its shared source cache distinguishes stage and evidence version; receipts for the same stage must not receive a different result because scan order chose the other version’s cached rule.

- **Withhold fresh fields on refusal.** Preserve the useful distinction between invalid evidence, unavailable source, and resolved evidence. A versioned currentness failure must not render a fresh receipt, target, or handoff, and the view remains log-free even when the reader guard cannot be acquired.

- **Rebuild structural evidence through the selected version.** In `plan_tool/roadmap_structural_revision.py:load_structural_revision_preflight`, validate a matching-version exact pair, then rebuild current snapshot and closure under that version’s rule. Keep `_require_pair_binding`, `_require_snapshot_binding`, `_current_selected_slice`, exact final-name validation, and source-record and brief checks. Version 1 keeps raw binding; version 2 compares retained canonical identities without treating a raw presentation change as freshness drift.

- **Allow only the publisher’s own pending generation.** Give `load_structural_revision_preflight` a private opt-in allowance for an active `RoadmapWriterToken` and one expected `PendingGeneration`. Ordinary preflight refuses a journal. The allowance succeeds only when the active token is bound to this roadmap, the on-disk journal is exactly the supplied generation, and its kind is `structural-feedback-publication`; it must not recover, edit, or otherwise accept a different journal. Pass the same authenticated allowance through `capture_roadmap_impact_snapshot` and `recheck_roadmap_impact_snapshot`; both shared reads independently re-check the journal, and callers without the allowance keep their default pending refusal.

- **Keep the publisher exception narrow.** In `plan_tool/roadmap_revision_publish.py:publish_structural_revision_proof`, keep the first preflight ordinary. Construct the exact generation once after that preflight, then let only `_publish_generation`’s `before_replace` callback pass that generation and the active token to the final preflight. Preserve `_publish_generation` ordering and its cleanup when the callback refuses.

- **Keep refusal ownership precise.** Raise `StructuralRevisionFeedbackIneligibleError` only when the selected live feedback no longer qualifies, so `plan_tool/roadmap_structural_revision_run.py:run_structural_revision` reports `feedback-rejected`. Treat baseline, pending-generation, version-pair, snapshot, closure, and other evidence-currentness failures as `StructuralRevisionPreflightError`, reported as `evidence-rejected` before evaluator or backend work.

- **Do not widen structural authority.** A current same-artifact or cross-artifact analysis still authorizes only the selected artifact and feedback row. Leave evaluator isolation, generated patch and proof validation, recovery, and general generation replacement unchanged.

## Tests

- `tests/test_roadmap_escalation_selection.py:test_v1_source_admission_keeps_exact_raw_behavior_without_baseline_inference` — version 1 uses exact raw source behavior and never gains a canonical identity.

- `tests/test_roadmap_escalation_selection.py:test_v2_source_admission_accepts_only_parseable_baseline_equal_presentation_drift` — version 2 accepts presentation-only change only with strict decoding, parsing, and matching baseline identity.

- `tests/test_roadmap_escalation_selection.py:test_v2_source_admission_refuses_missing_invalid_pending_or_semantically_drifted_baseline` — unsafe baseline and journal states refuse without changing source or baseline.

- `tests/test_roadmap_escalation_selection.py:test_live_feedback_eligibility_remains_independent_of_v2_baseline_match` — a baseline match does not bypass unique, open, unanswered, live-target feedback checks.

- `tests/test_roadmap_escalation_run.py:test_v2_receipt_creation_holds_one_reader_guard_across_admission_recheck_and_publication` — issuance observes one stable writer-published state.

- `tests/test_roadmap_escalation_run.py:test_v2_receipt_creation_refuses_changed_or_pending_source_before_publication` — changed or recoverable state creates no receipt and exposes no handoff.

- `tests/test_roadmap_escalation_run.py:test_receipt_lifecycle_remains_redacted_for_versioned_admission_failures` — versioned refusal does not log source prose, reviewer text, or baseline contents.

- `tests/cli/test_roadmap_cmd.py:test_escalation_view_rescans_and_inspects_receipts_under_reader_guard` — the view rescans inside the guard and remains log-free.

- `tests/cli/test_roadmap_cmd.py:test_escalation_view_mixed_versions_are_independent_of_evidence_order` — version-1 and version-2 receipts for one stage have the same results in either scan order.

- `tests/cli/test_roadmap_cmd.py:test_escalation_view_withholds_fresh_fields_when_versioned_source_admission_fails` — pending or stale versioned evidence renders no fresh target or handoff.

- `tests/test_roadmap_structural_revision.py:test_preflight_binds_current_version_matched_pair_to_the_selected_snapshot` — matching evidence binds only when its source rule, closure, and live feedback all hold.

- `tests/test_roadmap_structural_revision.py:test_preflight_rejects_mixed_versions_or_stale_v2_identity_without_widening_selection` — mixed versions and stale version-2 identity refuse before candidate construction.

- `tests/test_roadmap_structural_revision.py:test_preflight_retains_feedback_rejected_for_ineligible_live_feedback` — live feedback remains distinguishable from other evidence failures.

- `tests/test_roadmap_structural_revision.py:test_preflight_refuses_every_pending_generation_without_exact_active_writer_allowance` — ordinary readers, expired or wrong tokens, wrong generation kind, and member mismatches all refuse.

- `tests/test_roadmap_revision_publish.py:test_structural_publication_second_preflight_accepts_only_its_exact_active_pending_generation` — the final publisher recheck accepts only its matching token and generation, while unrelated journals and allowance mismatches refuse.

- `tests/test_roadmap_structural_revision_run.py:test_structural_runner_rejects_versioned_evidence_before_seed_or_backend` — evidence rejection reaches neither evaluator prompt, backend call, nor seed-side effect.

### Tests for this step

Every listed test must pass before this step is complete. Run `uv run pytest tests/test_roadmap_escalation_selection.py tests/test_roadmap_escalation_run.py tests/test_roadmap_structural_revision.py tests/test_roadmap_structural_revision_run.py tests/cli/test_roadmap_cmd.py -q`, then run `uv run pytest tests/ -q -n auto`.

## Acceptance criteria

- Version-1 receipts remain readable and current only through exact-raw admission, without baseline reads or inferred canonical identity.

- Version-2 receipt creation and inspection require strict parsing, a matching published baseline identity, no pending generation, and currently eligible feedback.

- A version-2 presentation-only stage change can remain current without changing retained raw provenance or source bytes.

- Receipt creation performs stable observation and a final recheck before publication; an unsafe or changed state publishes no receipt.

- `--view escalations` rescans under a reader guard, remains log-free, and evaluates mixed version-1 and version-2 evidence independently of scan order.

- Structural preflight accepts only a matching-version exact pair that rebuilds against the appropriate current snapshot rule.

- Structural preflight refuses every pending generation except the publisher’s exact `structural-feedback-publication` journal during its own final preflight, authenticated by an active matching writer token.

- Only ineligible selected feedback reaches `feedback-rejected`; every other versioned-evidence failure reaches `evidence-rejected` before evaluator or backend work.

- The focused test command and `uv run pytest tests/ -q -n auto` pass.

## References

- [YAML Ain’t Markup Language (YAML™) Revision 1.2.2https: — Use representation equality to separate stage semantics from source formatting.

- [hashlib — Secure Hashes and Message Digestshttps: — Use SHA-256 for immutable raw provenance and identity binding.

## Applicable guardrails

- **The plan’s “## Plan intent”, writer-owned baseline authority** — Read canonical freshness from the published baseline only; do not create another authority in a receipt or structural reader.

- **The plan’s “## Step intent”, live feedback and version matching** — Recheck live feedback separately from stage semantics and reject incompatible receipt-analysis evidence.

- **The plan’s “## Out of scope”, baseline lifecycle boundary** — Do not enroll, publish, recover, advance, or repair baseline state from reader paths.

- **The plan’s “## Out of scope”, source-mutation boundary** — Refuse unsafe source state without rewriting source bytes or mutable provenance.

- **The plan’s “## Out of scope”, generated-candidate boundary** — Leave structural patch and proof canonicality plus malformed-input protection unchanged.

## Deferred

- Version-aware impact-analysis inspection in `plan_tool/roadmap_impact_run.py:current_impact_analysis` — Step 2 owns its capture and currentness behavior.

- Baseline enrollment, publication, recovery, and reader-side repair — remain outside this step’s reader-only boundary.

- Retention and hand-edit follow-up workflows — remain outside this step’s scope.
