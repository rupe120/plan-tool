> **Auto-archived**: this plan was swept on 2026-08-18 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 1 — Extract behavior-preserving shared feedback selector primitives

## Summary

Move the current artifact-qualified selector parsing and feedback-row lookup into `plan_tool/roadmap_feedback.py`, then have `plan_tool/roadmap_revision.py` use that shared boundary. The shared parser exposes typed internal outcomes for malformed syntax and an unknown configured artifact, while the local-revision adapter preserves its current `RevisionContractError` surface. Add focused selector and lookup tests in `tests/test_roadmap_feedback.py` while retaining local-revision preflight regression coverage in `tests/test_roadmap_revision.py`. The key decision is that the shared lookup returns the complete ordered candidate set without deciding whether a row is eligible. When green, local revision accepts, rejects, logs, and writes exactly as it does now.

## Table of Contents

- [Summary](#summary) — Reviewer-level outcome and boundary.
- [Table of Contents](#table-of-contents) — Links to each section.
- [Why](#why) — Why the shared boundary is needed now.
- [Input](#input) — Existing selector and feedback-row contracts.
- [Files (creates vs edits)](#files-creates-vs-edits) — New and modified files.
- [Implementation](#implementation) — Required extraction and compatibility rules.
- [Tests](#tests) — Focused regression coverage.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [Applicable guardrails](#applicable-guardrails) — Scope limits that bind this refactor.
- [Deferred](#deferred) — Similar-looking code intentionally left unchanged.

## Why

`plan_tool/roadmap_revision.py:parse_feedback_selector` and the selected-feedback lookup inside `plan_tool/roadmap_revision.py:preflight_feedback_revision` currently sit inside local-revision policy, while the receipt path needs the same low-level facts without inheriting local revision eligibility. Extracting only those facts creates one reusable boundary and lets the next step define receipt selection separately, without changing the existing local writer’s behavior.

## Input

- **Selector contract:** `plan_tool/roadmap_revision.py:FeedbackSelector` and `plan_tool/roadmap_revision.py:parse_feedback_selector` accept one configured `RoadmapStage.artifact_key` from `plan_tool/roadmap.py:STAGES` plus one feedback identifier. Its existing public failure surface groups malformed syntax and unknown stage as `RevisionContractError`; the shared boundary must retain their distinct internal facts without changing that surface.
- **Feedback contract:** `plan_tool/roadmap_artifacts.py:RoadmapArtifact` is the current union of concrete stage artifacts, each of which exposes an ordered `feedback` tuple of `plan_tool/roadmap_artifacts.py:FeedbackRow` records; `FeedbackRow.id` is the lookup key.
- **Compatibility limit:** `plan_tool/roadmap_revision_run.py:_parse_selector` catches `RevisionContractError`, so extraction must preserve the local revision caller’s successful and rejected selector behavior.
- **Purity limit:** This step consumes parsed artifacts only. It does not parse artifact text, render artifacts, read paths, or persist data.

## Files (creates vs edits)

- **New files:**
  - `plan_tool/roadmap_feedback.py` — Canonical artifact-qualified selector parsing and duplicate-preserving feedback lookup primitives.
  - `tests/test_roadmap_feedback.py` — Direct contract tests for the new shared boundary.

- **Existing files (edits only):**
  - `plan_tool/roadmap_revision.py` — Delegate selector parsing and selected-feedback candidate lookup while preserving the existing local-revision public interface and preflight policy.
  - `tests/test_roadmap_revision.py` — Keep local preflight tests as regression coverage and move selector-only cases to the shared-module suite.

## Implementation

- **Foundational logic:** Parse one `<artifact-key>:<feedback-id>` selector into either a typed malformed-syntax or unknown-stage outcome, or one selector value, then return every feedback row in the selected artifact whose `FeedbackRow.id` matches that identifier.

- **Make `plan_tool/roadmap_feedback.py` the shared owner.** Move the existing `FeedbackSelector` record and `parse_feedback_selector(value, artifact_keys)` grammar from `plan_tool/roadmap_revision.py` behind this module. Expose typed internal errors or an equivalent closed result that distinguishes malformed selector syntax from an unknown configured artifact without retaining raw input. Expose a pure lookup primitive that accepts a selected artifact and selector and returns every matching feedback row.

- **Preserve the selector grammar exactly.** Accept only a known artifact key, one separator, and a feedback id that is nonblank after trimming and contains no colon. Return the typed syntax outcome for a non-string, missing separator, empty/blank part, or second colon, and the typed stage outcome only after syntax succeeds but the artifact key is not configured. Preserve the feedback-id text after the separator instead of normalizing or trimming it, because the current parser validates whitespace but returns the original identifier.

- **Preserve candidate cardinality and order.** Return zero, one, or many matching rows in the selected concrete artifact's `feedback` order. Do not silently choose the first result, deduplicate rows, validate state, inspect the target, or turn cardinality into a receipt or local-revision verdict.

- **Keep local revision compatibility intact.** Update `plan_tool/roadmap_revision.py:preflight_feedback_revision` to use the shared primitives while retaining its current render-canonical check, retained-feedback validation, target checks, text-field allowlist, and `RevisionPreflight` result. Keep `plan_tool/roadmap_revision.py:FeedbackSelector`, `plan_tool/roadmap_revision.py:parse_feedback_selector`, and selector failure messages/types compatible for callers such as `plan_tool/roadmap_revision_run.py:_parse_selector`; an adapter maps either typed shared outcome back to the existing `RevisionContractError` surface. Receipt code consumes the typed outcome directly and never inspects exception text.

- **Do not move eligibility policy into the shared module.** The rejected alternative is a shared helper that declares feedback eligible or ineligible. `plan_tool/roadmap_revision.py:preflight_feedback_revision` remains the owner of local-revision eligibility, and step 2 owns receipt-specific selection rules.

- **Keep the extraction side-effect free.** Do not change `TEXT_FIELDS_BY_ROW_TYPE`, revision operations, merge behavior, seed invalidation, local run-log verdicts, artifact writes, or CLI behavior.

## Tests

### Tests for this step

- `tests/test_roadmap_feedback.py::test_parse_feedback_selector_accepts_configured_stage_keys_and_preserves_feedback_id` — Accepts every configured artifact key and proves a nonblank feedback id is returned unchanged.
- `tests/test_roadmap_feedback.py::test_parse_feedback_selector_distinguishes_malformed_syntax_from_unknown_configured_artifact` — Verifies non-string, missing/invalid parts, and another colon use the syntax outcome, while a syntactically valid unknown key uses the stage outcome without retaining raw input.
- `tests/test_roadmap_feedback.py::test_matching_feedback_rows_preserves_zero_one_and_many_candidates_in_artifact_order` — Proves lookup neither chooses a row nor collapses duplicate feedback ids.
- `tests/test_roadmap_revision.py::test_revision_selector_compatibility_preserves_revision_contract_errors_and_messages` — Proves callers using the existing revision-module selector surface still receive the current local revision contract failures for both typed shared outcomes.
- `tests/test_roadmap_revision.py::test_preflight_selects_one_open_response_less_live_row` — Confirms extraction leaves accepted local preflight data unchanged.
- `tests/test_roadmap_revision.py::test_preflight_rejects_duplicate_feedback_and_duplicate_live_target_ids` — Confirms duplicate feedback candidates still reject through local preflight rather than being silently selected.

Every listed test must be green before this step is complete.

## Acceptance criteria

- `plan_tool/roadmap_feedback.py` provides the shared selector parser, selector value, typed malformed-syntax/unknown-stage outcomes, and artifact-local feedback lookup without importing local-revision policy.
- Known artifact keys and nonblank colon-free feedback ids retain the current parser behavior, including preservation of the returned feedback-id text; malformed syntax and an unknown configured artifact remain distinct internal outcomes.
- The shared lookup returns all matching feedback rows in source order and preserves zero-match and duplicate-match evidence for its caller.
- `plan_tool/roadmap_revision.py:preflight_feedback_revision` retains its current accepted and rejected local-revision behavior, including duplicate-feedback rejection.
- Existing selector callers still receive compatible `RevisionContractError` behavior and messages, so `plan_tool/roadmap_revision_run.py:_parse_selector` continues to produce its existing selector-rejected path while receipt callers use typed outcomes rather than error text.
- `tests/test_roadmap_feedback.py` and the affected cases in `tests/test_roadmap_revision.py` pass.

## Applicable guardrails

- **The plan’s “## Step intent”, behavior preservation:** Limit this work to existing selector parsing and lookup facts plus non-public typed error discrimination; do not add receipt eligibility, reasons, or a local-revision verdict.
- **The plan’s “## Out of scope”, local-revision compatibility:** Do not alter the local revision allowlist, write behavior, invalidation behavior, or failure handling while changing ownership of the helper code.
- **The plan’s “## Plan intent”, receipt-only boundary:** Do not invoke a backend, write a receipt, rewrite a roadmap artifact, or infer broader impact in this extraction.
- **The plan’s “## Out of scope”, broad analysis:** Keep lookup scoped to the selected artifact and do not inspect other roadmap artifacts.

## Deferred

- `plan_tool/roadmap_revision_run.py:_selected_target_id` and `plan_tool/roadmap_revision_patch.py:_selected_feedback` — Leave their matching-id code unchanged because they serve log recovery and merge-time snapshot validation with different fallback and error contracts; consolidate them only in a separately scoped refactor.
- `plan_tool/roadmap_view.py:build_feedback_index` and `plan_tool/roadmap_gates.py:VIOLATION_DUPLICATE_FEEDBACK_ID` — Leave multi-artifact view indexing and roadmap validation unchanged; neither is the selected-artifact lookup this step extracts.
