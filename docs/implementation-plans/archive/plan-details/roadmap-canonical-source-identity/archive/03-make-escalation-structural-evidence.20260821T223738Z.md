> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 3 — Make escalation and structural-evidence readers admit only current versioned evidence

## Summary

Make receipt creation, receipt inspection, and structural preflight use the version-specific source-freshness rules from steps 1 and 2. Update `plan_tool/roadmap_escalation_selection.py`, `plan_tool/roadmap_escalation_run.py`, `plan_tool/cli/roadmap_cmd.py`, `plan_tool/roadmap_revision_publish.py`, and `plan_tool/roadmap_structural_revision.py` while preserving the existing redacted result and refusal surfaces. The key decision is that version 1 remains exact-raw, while version 2 accepts only a strict, parsed, baseline-equal source with independently eligible live feedback. On green, ordinary readers never expose or authorize evidence from a pending, changed, mismatched-version, or semantically stale source state; the structural publisher’s second preflight alone recognizes its exact active generation.

## Table of Contents

- [Summary](#summary) — Reviewer-level result and version boundary.
- [Table of Contents](#table-of-contents) — Links to every section in this detail.
- [Why](#why) — The current raw-digest-only reader gap.
- [Input](#input) — Contracts supplied by steps 1 and 2.
- [Files (creates vs edits)](#files-creates-vs-edits) — Scoped production and test changes.
- [Implementation](#implementation) — Reader admission, stable observation, and structural preflight rules.
- [Tests](#tests) — Focused version, concurrency, and refusal coverage.
- [Acceptance criteria](#acceptance-criteria) — Observable completion conditions.
- [References](#references) — Canonical-value and digest references.
- [Applicable guardrails](#applicable-guardrails) — Reader-only and strict-canonicality limits.
- [Deferred](#deferred) — Work outside this step.

## Why

`plan_tool/roadmap_escalation_run.py:current_escalation_receipt` currently judges receipts through raw source digests, while `plan_tool/roadmap_structural_revision.py:load_structural_revision_preflight` rebuilds evidence from the current snapshot. Those paths need the same version-aware distinction as impact analysis: raw bytes remain immutable provenance, but only version 2 may accept a presentation-only change after a fully validated published baseline confirms unchanged stage semantics. Without a stable reader observation and version-specific cache key, a receipt can be exposed during recoverable publication or evaluated through the wrong version’s rule.

## Input

- **Step 1 evidence contracts:** Consume the landed version-specific shapes from `plan_tool/roadmap_escalation.py:EscalationReceipt` and `plan_tool/roadmap_impact_analysis.py:ImpactAnalysis`. Parsed evidence version selects the freshness rule; the landed field names and validators win over this detail.

- **Step 1 baseline identity:** Use the closed identity derived from `plan_tool/roadmap_source_identity.py:BaselineRecord`. Read `baseline_path`, `load_baseline_record`, `compare_baseline`, `pending_generation_path`, and `load_pending_generation` only as reader admission inputs.

- **Step 2 snapshot contract:** Use the version-aware result of `plan_tool/roadmap_impact_snapshot.py:capture_roadmap_impact_snapshot` and `RoadmapImpactSnapshot` when structural preflight rebuilds an analysis. Step 2 owns impact-analysis inspection in `plan_tool/roadmap_impact_run.py:current_impact_analysis`.

- **Existing structural boundary:** Preserve the public behavior of `plan_tool/roadmap_structural_revision.py:load_structural_revision_preflight`, `StructuralRevisionPreflightError`, and `StructuralRevisionFeedbackIneligibleError`. `plan_tool/roadmap_revision_publish.py:publish_structural_revision_proof` calls this preflight before and immediately before publication.
- **Publisher-owned pending boundary:** `plan_tool/roadmap_revision_publish.py:publish_structural_revision_proof` has an active `RoadmapWriterToken` and constructs one exact `PendingGeneration(kind="structural-feedback-publication", ...)` before its second preflight. Only that callback may present the active token and that exact generation; receipt creation, views, first structural preflight, and every unrelated recovery state remain ordinary pending-state refusals.

## Files (creates vs edits)

- **New files:** None.

- **Existing files (edits only):**
  - `plan_tool/cli/roadmap_cmd.py` — Make `--view escalations` inspect a stable, reader-guarded evidence set and render only currently admitted versioned receipts.
  - `plan_tool/roadmap_escalation_selection.py` — Add version-aware source admission while keeping live feedback selection separate from baseline semantics.
  - `plan_tool/roadmap_escalation_run.py` — Use stable versioned admission for receipt creation and `current_escalation_receipt`, including version-aware source caching and final rechecks.
  - `plan_tool/roadmap_revision_publish.py` — Bind the structural publisher’s second preflight to its own active token and exact pending generation without changing recovery or generation replacement.
  - `plan_tool/roadmap_structural_revision.py` — Bind the exact versioned receipt-analysis pair to the current snapshot and preserve feedback-specific refusal.
  - `tests/cli/test_roadmap_cmd.py` — Cover guarded receipt inspection, redacted refusal, and mixed-version order independence.
  - `tests/test_roadmap_escalation_selection.py` — Cover pure version-specific stage admission and independent feedback eligibility.
  - `tests/test_roadmap_escalation_run.py` — Cover receipt issuance’s stable observation, recheck, and no-publication failures.
  - `tests/test_roadmap_revision_publish.py` — Cover the publisher’s exact active-generation allowance and rejection of every other journal state.
  - `tests/test_roadmap_structural_revision.py` — Cover current versioned structural binding and refusal classification.
  - `tests/test_roadmap_structural_revision_run.py` — Cover runner behavior when the strengthened preflight rejects evidence.

## Implementation

- **Choose the freshness rule from evidence version first.** Keep version 1 on its exact-raw source path without reading or inferring a baseline identity. For version 2, require strict UTF-8, successful parsing, a fully valid matching baseline identity, and no pending publication state. A version-2 renderer-text difference is admissible only when the full baseline comparison succeeds. Structural preflight also refuses every pending state unless its publisher-only allowance below validates.

- **Keep raw provenance separate from freshness.** Evolve `plan_tool/roadmap_escalation_selection.py:canonical_artifact_snapshot` and its snapshot result types, or add an equally narrow version-aware admission path, so receipt creation and inspection retain observed raw bytes and digest without treating that digest as the version-2 freshness test. Do not normalize, re-render, or rewrite source text.

- **Keep selection pure and feedback-specific.** `plan_tool/roadmap_escalation_selection.py:select_receipt_feedback` must continue to decide whether the selected feedback row is unique, open, unanswered, and points to one live target. Baseline comparison excludes feedback, so version-2 admission must always recheck those live facts rather than treating a matching stage identity as approval for stale feedback.

- **Use one stable receipt observation.** In `plan_tool/roadmap_escalation_run.py:run_roadmap_escalation_receipt` and its preflight path, use `plan_tool/roadmap_revision_publish.py:roadmap_reader_guard` to cover baseline and artifact admission, pending-publication inspection, final source recheck, and evidence publication. Refuse if the selected source, baseline identity, raw provenance, or live feedback changes before publication; do not issue a version-1 fallback receipt.

- **Preserve closed receipt behavior.** Keep `EscalationRunResult`, redacted lifecycle logging, immutable final-name validation, collision handling, and existing receipt reuse rules. A rejected versioned admission must publish no receipt and must not add source prose, reviewer requests, baseline projections, or repair instructions to a log or result.

- **Make escalation views stable and order-independent.** Update `plan_tool/cli/roadmap_cmd.py:_cmd_roadmap_escalations_view` to follow the reader-guarded rescan pattern used by `_cmd_roadmap_impact_analyses_view`. Update `plan_tool/roadmap_escalation_run.py:current_escalation_receipt` so a shared source cache distinguishes both stage and evidence version; a version-1 receipt and version-2 receipt for the same stage must receive their own rule without depending on evidence scan order.

- **Withhold fresh output on every refusal.** Keep the established distinction between invalid stored evidence, source-unavailable evidence, and resolved evidence where it remains meaningful. A versioned currentness failure must not render a fresh receipt, target, or handoff. Keep the view log-free, including reader-guard failures.

- **Rebuild structural evidence through the selected version.** In `plan_tool/roadmap_structural_revision.py:load_structural_revision_preflight`, use the exact receipt-analysis pair’s compatible version to capture and validate the current snapshot. Preserve `_require_pair_binding`, `_require_snapshot_binding`, `_current_selected_slice`, closure reconstruction, and exact final-name checks; extend their comparison rules to use raw binding for version 1 and retained canonical identities for version 2.

- **Allow only the publisher's own exact pending generation.** Extend `load_structural_revision_preflight` with an internal-only optional allowance carrying both a `RoadmapWriterToken` and the expected `PendingGeneration`. Before source capture, load any journal and refuse it unless no journal exists or all of the following hold: the caller presents an active token bound to this roadmap, the loaded generation equals the expected generation member-for-member, and its kind is exactly `structural-feedback-publication`. The allowance never calls recovery or writes a journal. In `publish_structural_revision_proof`, keep the first preflight unexceptional; construct the generation once, then have only its `before_replace` second preflight pass that exact generation and its active writer token. Do not change `_publish_generation` ordering or its cleanup-on-refusal behavior.

- **Keep refusal ownership precise.** Continue raising `StructuralRevisionFeedbackIneligibleError` only when the selected live feedback no longer qualifies, because `plan_tool/roadmap_structural_revision_run.py:run_structural_revision` maps it to `feedback-rejected`. Treat baseline, pending-publication, version-pair, snapshot, closure, and other evidence-currentness failures as `StructuralRevisionPreflightError`, which the runner maps to `evidence-rejected` before backend work.

- **Do not widen structural authority.** A current same-artifact or cross-artifact analysis still authorizes only the selected artifact and selected feedback row. Do not alter generated patch/proof canonicality, evaluator isolation, recovery behavior, or general generation replacement. The publisher-only allowance changes neither preflight’s public CLI inputs nor its selection, relation, repair, or journal authority.

## Tests

- `tests/test_roadmap_escalation_selection.py:test_v1_source_admission_keeps_exact_raw_behavior_without_baseline_inference` — version 1 accepts only its exact raw source rule and never gains a canonical identity.

- `tests/test_roadmap_escalation_selection.py:test_v2_source_admission_accepts_only_parseable_baseline_equal_presentation_drift` — version 2 admits a presentation-only change only with strict decoding, successful parsing, and a matching complete baseline identity.

- `tests/test_roadmap_escalation_selection.py:test_v2_source_admission_refuses_missing_invalid_pending_or_semantically_drifted_baseline` — every unsafe baseline state refuses without modifying the source or baseline.

- `tests/test_roadmap_escalation_selection.py:test_live_feedback_eligibility_remains_independent_of_v2_baseline_match` — an open, unique, live selected target remains required even when stage semantics match the baseline.

- `tests/test_roadmap_escalation_run.py:test_v2_receipt_creation_holds_one_reader_guard_across_admission_recheck_and_publication` — receipt issuance observes one stable writer-published state.

- `tests/test_roadmap_escalation_run.py:test_v2_receipt_creation_refuses_changed_or_pending_source_before_publication` — a changed or recoverable source state creates no receipt and exposes no handoff.

- `tests/test_roadmap_escalation_run.py:test_receipt_lifecycle_remains_redacted_for_versioned_admission_failures` — versioned refusal does not log source prose, reviewer text, baseline contents, or raw command input.

- `tests/cli/test_roadmap_cmd.py:test_escalation_view_rescans_and_inspects_receipts_under_reader_guard` — the view re-enumerates evidence inside the reader guard and stays log-free.

- `tests/cli/test_roadmap_cmd.py:test_escalation_view_mixed_versions_are_independent_of_evidence_order` — version-1 and version-2 receipts for one stage receive the same results in either scan order.

- `tests/cli/test_roadmap_cmd.py:test_escalation_view_withholds_fresh_fields_when_versioned_source_admission_fails` — no fresh status, target, or handoff is rendered after pending or stale versioned admission.

- `tests/test_roadmap_structural_revision.py:test_preflight_binds_current_version_matched_pair_to_the_selected_snapshot` — matching versioned evidence binds only when its current source rule, closure, and live feedback all hold.

- `tests/test_roadmap_structural_revision.py:test_preflight_rejects_mixed_versions_or_stale_v2_identity_without_widening_selection` — invalid version pairing or canonical freshness fails before candidate construction.

- `tests/test_roadmap_structural_revision.py:test_preflight_retains_feedback_rejected_for_ineligible_live_feedback` — feedback eligibility remains distinguishable from all other evidence rejection.

- `tests/test_roadmap_structural_revision.py:test_preflight_refuses_every_pending_generation_without_exact_active_writer_allowance` — a normal reader, expired token, wrong roadmap token, wrong kind, or member-mismatched generation remains `evidence-rejected` before structural context returns.

- `tests/test_roadmap_revision_publish.py:test_structural_publication_second_preflight_accepts_only_its_exact_active_pending_generation` — the first preflight sees no journal; the second succeeds only with the publisher’s matching active token and generation, while an injected unrelated journal or allowance mismatch refuses and retains current cleanup behavior.

- `tests/test_roadmap_structural_revision_run.py:test_structural_runner_rejects_versioned_evidence_before_seed_or_backend` — preflight rejection creates no evaluator prompt, backend call, or seed-side effect.

### Tests for this step

Every listed test must pass before this step is complete. Run `uv run pytest tests/test_roadmap_escalation_selection.py tests/test_roadmap_escalation_run.py tests/test_roadmap_structural_revision.py tests/test_roadmap_structural_revision_run.py tests/cli/test_roadmap_cmd.py -q`, then run `uv run pytest tests/ -q -n auto`.

## Acceptance criteria

- Version-1 receipts remain readable and current only through exact-raw source admission, with no inferred canonical identity or baseline read.

- Version-2 receipt creation and inspection require strict parsing, a matching published baseline identity, no pending publication, and currently eligible feedback.

- A version-2 presentation-only source change can remain current without changing the retained raw provenance or source bytes.

- Receipt creation performs stable observation and final recheck before publication; any changed or unsafe state publishes no receipt.

- `--view escalations` rescans under a reader guard, remains log-free, and evaluates mixed version-1/version-2 evidence independently of scan order.

- Structural preflight accepts only an exact compatible-version pair that rebuilds against the appropriate current snapshot rule.

- Structural preflight refuses every pending generation except the publisher’s exact `structural-feedback-publication` journal during its own second preflight, authenticated by an active matching writer token; it never recovers, mutates, or accepts an unrelated pending journal.

- Only an ineligible selected feedback row reaches `feedback-rejected`; every other versioned-evidence failure reaches `evidence-rejected` before evaluator or backend work.

- The focused test command and `uv run pytest tests/ -q -n auto` pass.

## References

- [YAML Ain’t Markup Language (YAML™) Revision 1.2.2](https://yaml.org/spec/1.2.2/) — Use representation equality to distinguish stage semantics from source formatting.

- [hashlib — Secure Hashes and Message Digests](https://docs.python.org/3.13/library/hashlib.html) — Use SHA-256 for immutable raw provenance and identity binding.

## Applicable guardrails

- **The plan’s “## Plan intent”, writer-owned baseline authority** — Read canonical freshness through the published baseline only; these files must not create a second authority.

- **The plan’s “## Step intent”, live feedback and version matching** — Recheck live feedback separately from stage semantics and reject incompatible receipt-analysis evidence.

- **The plan’s “## Out of scope”, baseline lifecycle boundary** — Do not enroll, publish, recover, advance, or repair a baseline from any reader path.

- **The plan’s “## Out of scope”, source-mutation boundary** — Refuse unsafe source state without canonicalizing or rewriting source bytes or raw provenance.

- **The plan’s “## Out of scope”, generated-candidate boundary** — Leave structural patch/proof canonicality and malformed-input protection unchanged.

## Deferred

- Impact-analysis inspection in `plan_tool/roadmap_impact_run.py:current_impact_analysis` — Step 2 owns its version-aware capture and currentness behavior.

- Baseline enrollment, publication, recovery, and reader-side repair — remain outside this step under the plan’s lifecycle boundary.

- Retention and hand-edit follow-up workflows — remain with the plan’s named backlog work.
