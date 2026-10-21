> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 3 — Fold the reopen nonce into escalation receipt identity and currentness

## Summary

Extend the receipt, selection, runner, and impact-analysis contracts to carry an optional feedback reopen nonce from the selected feedback row. Make `plan_tool/roadmap_escalation.py` include that nonce in a reopened receipt’s semantic identity while preserving the semantic preimage, final name, and exact canonical wire form of no-nonce receipts and analyses. Require currentness readers to match the selected row’s nonce, not only its target and baseline-backed identity. On green, a reopened row produces a distinct receipt and impact-analysis identity, while ordinary version-2 evidence keeps its existing behavior.

## Table of Contents

- [Summary](#summary) — The completed behavior at a glance.
- [Table of Contents](#table-of-contents) — Links to each section in this detail.
- [Why](#why) — The identity gap this step closes.
- [Input](#input) — Upstream row data and existing receipt contracts.
- [Files (creates vs edits)](#files-creates-vs-edits) — The exact files this step changes.
- [Implementation](#implementation) — Nonce propagation, identity, and currentness rules.
- [Tests](#tests) — Focused coverage for legacy and reopened evidence.
- [Acceptance criteria](#acceptance-criteria) — Observable completion conditions.
- [References](#references) — Relevant primary documentation.
- [Applicable guardrails](#applicable-guardrails) — Scope limits for this work.
- [Deferred](#deferred) — Work intentionally left to other steps.

## Why

`plan_tool/roadmap_source_identity.py:canonical_projection` deliberately removes feedback from baseline identity, while `plan_tool/roadmap_escalation.py:_receipt_hash_fields` also leaves raw source bytes out of the receipt dedup key. That is correct for presentation-only source drift, but it means an ordinary receipt and the first receipt after a confirmed feedback reopen can otherwise share an identity. `plan_tool/roadmap_escalation_run.py:current_escalation_receipt` and `plan_tool/roadmap_impact_analysis.py:_receipt_matches_captured_artifact` currently reselect the feedback row but have no reopen-instance fact to compare.

## Input

- **Step 1 row contract:** Step 1 adds the optional feedback reopen record to `plan_tool/roadmap_artifacts.py:FeedbackRow`. Read the landed nonce field and its validation rules from that module; its code wins if its final names differ from this detail.

- **Receipt selection:** `plan_tool/roadmap_escalation_selection.py:ReceiptSelection` is the receipt-safe channel from `select_receipt_feedback` to receipt construction. Keep it limited to safe identity facts.

- **Receipt identity:** `plan_tool/roadmap_escalation.py:_ReceiptSemanticFields`, `build_receipt`, and `receipt_semantic_id_from_facts` define the value that names an immutable receipt. Preserve their existing exclusion of raw source digest and creation time.

- **Impact identity:** `plan_tool/roadmap_impact_analysis.py:ImpactReceiptEvidence` rebuilds the nested receipt identity through `receipt_semantic_id_from_facts`; `build_impact_analysis` and `_receipt_matches_captured_artifact` consume the same receipt facts during creation and currentness checks.

## Files (creates vs edits)

- **New files:** None.

- **Existing files (edits only):**
  - `plan_tool/roadmap_escalation.py` — Add the optional receipt nonce, validate it as the step-1 nonce form, and include it in semantic construction and fact-based identity reconstruction when present.
  - `plan_tool/roadmap_escalation_selection.py` — Carry the selected row’s optional nonce in `ReceiptSelection` without widening receipt eligibility.
  - `plan_tool/roadmap_escalation_run.py` — Preserve the nonce through the guarded preflight/recheck path and require it during `current_escalation_receipt` freshness checks without adding it to run-log facts.
  - `plan_tool/roadmap_impact_analysis.py` — Retain the nonce in `ImpactReceiptEvidence`, reconstruct receipt identity with it, and require it when rechecking a receipt against a captured artifact.
  - `ROADMAP_FORMAT.md` — Document the optional receipt and nested impact-evidence field, the absent-nonce compatibility rule, and the reader currentness rule.
  - `tests/test_roadmap_escalation.py` — Cover receipt schema, semantic preimage, reconstruction, and redaction behavior.
  - `tests/test_roadmap_escalation_run.py` — Cover guarded recheck and receipt-view currentness when the nonce changes.
  - `tests/test_roadmap_escalation_selection.py` — Cover selecting the nonce from one eligible feedback row.
  - `tests/test_roadmap_impact_analysis.py` — Cover nested analysis evidence, reconstruction, and stale reopened-row checks.

## Implementation

- **Foundational logic: nonce-bound receipt currentness.** Carry one optional `reopen_nonce` from the selected feedback row into the receipt identity, then require the live selected row to carry the same value whenever receipt or analysis currentness is recomputed.

- **Keep the nonce receipt-safe and narrow.** Extend `plan_tool/roadmap_escalation_selection.py:ReceiptSelection` only with the optional nonce required for identity. `select_receipt_feedback` should copy it from the one selected eligible row and must not retain the reopen record’s surrounding data, reviewer request, response, or artifact prose.

- **Keep eligibility unchanged.** `plan_tool/roadmap_escalation_selection.py:select_receipt_feedback` must still accept only one `open`, response-less row and preserve its existing verdict ordering. The nonce distinguishes a qualifying reopen from its earlier receipt; it must not become an alternate way to select a row.

- **Make identity and wire encoding conditional.** Add the optional nonce to `plan_tool/roadmap_escalation.py:_ReceiptSemanticFields`, `build_receipt`, `_receipt_semantic_fields`, and `receipt_semantic_id_from_facts`. A present nonce must change the canonical semantic preimage, persisted receipt bytes, and therefore the receipt final name. An absent nonce must be left out of both that semantic preimage and the rendered receipt object, so existing version-2 bytes remain canonical, parseable, and keep their names. Omit only this absent field; do not globally omit existing `null` fields that are already part of the version-2 analysis wire contract.

- **Validate at the persisted boundary.** Receipt parsing must reject a malformed present nonce even when the source artifact parser would have rejected it earlier. Reuse the landed step-1 nonce contract rather than inventing a second normalization or broader token grammar.

- **Preserve presentation tolerance.** Continue excluding `created_at` and raw `source.sha256` from receipt identity. A matching nonce must not make harmless source presentation drift into a collision or stale result.

- **Bind both guarded reads.** `plan_tool/roadmap_escalation_run.py:_resolve_preflight` already retains the accepted `ReceiptSelection` in `_Preflight`, so its equality recheck should include the nonce through that value. Keep the nonce out of `_emit_preflight` and the lifecycle telemetry payload.

- **Require the live nonce on receipt view.** In `plan_tool/roadmap_escalation_run.py:current_escalation_receipt`, after the existing source admission and target checks, require the reselected nonce to equal the receipt nonce. A removed, replaced, or newly added nonce must resolve the receipt and withhold the trusted handoff.

- **Carry the same fact into analysis evidence.** Extend `plan_tool/roadmap_impact_analysis.py:ImpactReceiptEvidence`, its validator, `build_impact_analysis`, and `_impact_receipt_evidence_fields` so the nested receipt evidence states the optional nonce and the analysis semantic identity includes it. `ImpactReceiptEvidence` must call `receipt_semantic_id_from_facts` with the same nonce it stores. Its absent nonce must likewise be omitted from the nested persisted evidence, while existing fields such as a `null` `next_workflow` retain their current wire form.

- **Recheck nonce currentness for impact analysis.** Update `plan_tool/roadmap_impact_analysis.py:_receipt_matches_captured_artifact` to require the captured selected row’s nonce to match the receipt. Keep `version2_analysis_matches` aligned with that identity fact while preserving its raw-digest presentation tolerance. `plan_tool/roadmap_impact_run.py:current_impact_analysis` should remain an unchanged consumer of the updated pure analysis contract.

- **Keep the reference doc exact.** Update `ROADMAP_FORMAT.md:### Versioned receipt reference` and `ROADMAP_FORMAT.md:### Versioned analysis reference` to name the optional nonce, explain that an absent nonce has no wire key, and describe nonce matching as part of currentness. Keep the no-nonce examples valid, byte-canonical legacy version-2 examples with their existing identities and existing `null` fields.

## Tests

### Tests for this step

- `tests/test_roadmap_escalation_selection.py:test_selection_copies_reopen_nonce_from_the_selected_row` — An accepted selected row carries its feedback reopen nonce into `ReceiptSelection` without exposing response or request text.

- `tests/test_roadmap_escalation.py:test_receipt_reopen_nonce_changes_the_semantic_id_and_round_trips` — Two otherwise identical receipts with different present nonces have different semantic IDs and final names.

- `tests/test_roadmap_escalation.py:test_absent_reopen_nonce_preserves_the_legacy_v2_semantic_preimage` — A no-nonce receipt keeps the existing version-2 preimage and final name behavior.

- `tests/test_roadmap_escalation.py:test_legacy_no_nonce_receipt_bytes_parse_and_render_unchanged` — Existing canonical version-2 receipt bytes with no nonce key remain exact after parse and render.

- `tests/test_roadmap_escalation.py:test_receipt_identity_from_facts_requires_the_matching_reopen_nonce` — `receipt_semantic_id_from_facts` reproduces a receipt only with its exact optional nonce.

- `tests/test_roadmap_escalation.py:test_receipt_rejects_an_invalid_present_reopen_nonce` — Persisted receipt parsing rejects a malformed nonce rather than accepting an unchecked value.

- `tests/test_roadmap_escalation.py:test_rendered_receipt_retains_only_the_optional_nonce_and_existing_safe_facts` — The new field does not permit reviewer request, response, or source prose into receipt JSON.

- `tests/test_roadmap_escalation_run.py:test_receipt_admission_recheck_rejects_a_changed_reopen_nonce` — The second guarded preflight blocks publication when the selected nonce changes.

- `tests/test_roadmap_escalation_run.py:test_current_receipt_requires_the_matching_reopen_nonce` — A receipt resolves rather than remains fresh when the current selected row no longer has its nonce.

- `tests/test_roadmap_escalation_run.py:test_current_receipt_requires_the_matching_target` — A receipt resolves rather than remains fresh when the live selected row points at another valid target.

- `tests/test_roadmap_impact_analysis.py:test_analysis_receipt_evidence_retains_and_reconstructs_reopen_nonce` — Built analysis evidence carries the nonce and rejects a nested receipt identity rebuilt with a different value.

- `tests/test_roadmap_impact_analysis.py:test_legacy_no_nonce_analysis_bytes_parse_and_render_unchanged` — Existing canonical version-2 analysis bytes with no nested nonce key, including existing `null` fields, remain exact after parse and render.

- `tests/test_roadmap_impact_analysis.py:test_build_analysis_requires_the_captured_reopen_nonce` — A changed selected-row nonce makes `build_impact_analysis` return `InvalidImpactAnalysis` even when canonical source identity is unchanged.

- `tests/test_roadmap_impact_analysis.py:test_build_analysis_requires_the_captured_target` — A changed selected-row target makes `build_impact_analysis` return `InvalidImpactAnalysis` even when canonical source identity is unchanged.

- `tests/test_roadmap_impact_analysis.py:test_version2_analysis_nonce_change_is_not_reused` — Analyses tied to different receipt nonces do not match or reuse each other.

- `tests/test_roadmap_impact_analysis.py:test_nonce_bound_analysis_still_tolerates_raw_source_digest_drift` — Matching nonce and canonical identity retain the existing presentation-only raw-digest tolerance.

- **Green-before-done:** Every listed case must pass before this step is complete.

## Acceptance criteria

- A receipt built from an eligible row with a present reopen nonce includes that nonce in its semantic identity and has a different final name from an otherwise identical no-nonce receipt.

- A receipt without a reopen nonce retains the existing version-2 semantic preimage and final-name behavior.

- A receipt and nested impact evidence without a reopen nonce omit that key and preserve existing canonical version-2 bytes, including unrelated `null` fields.

- Receipt parsing accepts only an absent nonce or a value valid under the landed step-1 nonce contract.

- `current_escalation_receipt` returns `resolved` rather than `fresh` when the selected row’s nonce differs from the receipt’s nonce.

- `build_impact_analysis` refuses a captured artifact whose selected row has a different nonce from the receipt, even when the baseline-backed canonical identity still matches.

- Nested `ImpactReceiptEvidence` reconstructs the receipt semantic ID using the same optional nonce it stores.

- Matching nonce values preserve existing raw-source presentation-drift reuse behavior for receipts and impact analyses.

- `ROADMAP_FORMAT.md` documents the optional nonce and currentness rule, and its no-nonce receipt and impact examples remain valid version-2 evidence.

- `uv run pytest tests/test_roadmap_escalation.py tests/test_roadmap_escalation_run.py tests/test_roadmap_escalation_selection.py tests/test_roadmap_impact_analysis.py -q` passes.

## References

- [secrets — Generate secure random numbers for managing secretshttps: — Use this to understand the opaque, high-entropy nonce property produced by the upstream record writer.

- [pytest fixtures: explicit, modular, scalablehttps: — Use this for focused fixtures that isolate legacy, reopened, and stale evidence cases.

## Applicable guardrails

- **The plan’s “## Plan intent”, bounded recovery proof:** Make the first post-reopen receipt distinct without adding a general evidence-recovery capability.

- **The plan’s “## Step intent”, receipt and impact identity:** Update both identity and currentness readers; changing only final-name construction is incomplete.

- **The plan’s “## Out of scope”, restricted mutation and command surface:** Do not add writer behavior, new command options, lifecycle editing, or structural-rewrite behavior in these files.

- **The plan’s “## Out of scope”, narrow impact work:** Limit `plan_tool/roadmap_impact_analysis.py` changes to receipt identity and currentness facts; do not expand routing, closure, or transaction behavior.

## Deferred

- Feedback reopen candidate safety and mutation — Later plan work owns deciding safety and atomically changing the selected feedback row; this step only consumes its landed nonce.

- Broader feedback provenance or recovery support — Remains outside this receipt-identity change and must follow the plan’s existing scope process.
