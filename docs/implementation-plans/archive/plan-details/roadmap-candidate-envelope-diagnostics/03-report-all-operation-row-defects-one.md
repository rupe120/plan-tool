> **Auto-archived**: this plan was swept on 2026-11-05 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 3 — Report all operation and row defects in one correction

<!-- plan-tool:detail-format-version: 1 -->

## Summary

Make `plan_tool/roadmap_candidate.py` collect candidate-delta defects across a rejected response instead of stopping at the first operation. The parser must report operation-envelope and eligible row-body defects together through the existing `CandidateDeltaError` channel, while `tests/test_roadmap_candidate.py` pins the complete, closed diagnostic result and one existing assertion in `tests/test_roadmap_candidate_run.py` that pinned the retired class-name wording is updated to the new reason. The key design decision is that a known internal class-name `row_type` can select a row schema for diagnosis only; it never becomes accepted input. On green, the existing bounded retry receives one deterministic correction with every actionable defect it can safely name.

## Table of Contents

- [Summary](#summary) — Gives the completed behavior and main design choice.
- [Table of Contents](#table-of-contents) — Routes readers through this detail.
- [Why](#why) — Explains why the current first-error behavior cannot support the retry.
- [Input](#input) — Names the parser and diagnostic contracts this step consumes.
- [Files (creates vs edits)](#files-creates-vs-edits) — Lists the two scoped edits.
- [Implementation](#implementation) — Defines complete, safe parser diagnostics.
- [Tests](#tests) — Lists focused parser coverage.
- [Acceptance criteria](#acceptance-criteria) — States observable completion checks.
- [References](#references) — Points to the candidate and roadmap contracts.
- [Applicable guardrails](#applicable-guardrails) — Applies the plan’s scope limits.
- [Deferred](#deferred) — Separates prompt and retry integration work.

## Why

`plan_tool/roadmap_candidate.py:parse_candidate_delta` currently builds its operations with a fail-fast parse, so `_parse_operation` and `_parse_stage_row` expose only the first malformed record. `plan_tool/roadmap_candidate_run.py:_run_batch_candidate_proposal` already forwards that one error into its only correction attempt, making a response with several copied envelope fields and a `DecisionRow.source` field impossible to correct in one retry. The parser must produce one safe, complete reason before the unchanged retry path consumes it.

## Input

- **Step 2 closed field diagnostics:** Build on step 2’s `missing-field` and `unknown-field` behavior around `plan_tool/roadmap_candidate.py:_require_keys`. Retain its closed-name and stable-order guarantees when this step combines findings.

- **Candidate parser contract:** `plan_tool/roadmap_candidate.py:parse_candidate_delta`, `_parse_operation`, and `_parse_stage_row` define the accepted operation and row shapes. Invalid input must still raise `CandidateDeltaError` and must not produce a `CandidateDelta`.

- **Row schemas:** `plan_tool/roadmap_candidate.py:_ROW_TYPE_NAMES` and `_parse_stage_row` define collection-name row types. `plan_tool/roadmap_artifacts.py:DecisionRow` supplies the known `source` field that remains outside the writable `decisions` schema.

- **Existing correction channel:** `plan_tool/roadmap_candidate_run.py:render_candidate_delta_prompt` and `_run_batch_candidate_proposal` already pass the parser reason to the second attempt. They remain unchanged; this step changes only the reason they receive.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `plan_tool/roadmap_candidate.py` — aggregate safe operation and row diagnostics during candidate-delta parsing, including diagnosis-only schema selection for known class names.
  - `tests/test_roadmap_candidate.py` — add parser-level coverage for complete, deterministic aggregate diagnostics and rejected inputs.
  - `tests/test_roadmap_candidate_run.py` — update only the one existing assertion this step's change invalidates: `test_ledger_entity_addition_corrects_class_name_and_reaches_structural_review` expects the retired `candidate row type 'EntityRow' is not allowed` wording in the correction prompt. New integration fixtures stay with step 6.

## Implementation

- **Collect every eligible operation defect.** Change `plan_tool/roadmap_candidate.py:parse_candidate_delta` and its operation parsing path so one malformed operation does not prevent inspection of later operations. Return no partially parsed delta when any diagnostic exists; raise one `CandidateDeltaError` carrying the complete result after the response has been checked.

- **Keep diagnostics deterministic.** Preserve response operation order, and preserve the stable field ordering established by step 2 within each operation and row. The same rejected JSON must produce the same ordered reason every time.

- **Check both envelope and row body.** For each recognized operation shape, report its closed-envelope defects and, where a row schema can be selected, its row-body defects in the same correction. Do not let an invalid envelope suppress a diagnosable row-body defect.

- **Diagnose known class names without accepting them.** A valid collection-name `row_type` continues to select its normal schema. A known internal row class name may map to its collection schema only for diagnosis, so a class-name `row_type` can report `invalid-row-type` alongside safe row findings such as the non-writable `source` field on a decision row. The operation remains rejected.

- **Handle ambiguous and unknown row types safely.** Treat the two pattern collections as one shared `PatternRow` schema for diagnosis. For an unrecognized row type, emit the closed fallback required by step 2 and do not inspect its row body because no safe schema exists.

- **Keep parsing strict and bounded.** Do not add coercion, drop fields, accept class names, or accept `DecisionRow.source`. Preserve the existing accepted key sets, unknown-`op` and duplicate-key messages, root validation, and non-operation parsing behavior.

- **Reuse the existing retry boundary unchanged.** `plan_tool/roadmap_candidate_run.py:_run_batch_candidate_proposal` must continue receiving one parser reason through `CandidateDeltaError`; do not edit that module, its retry count, receipt handling, or candidate storage in this step.

## Tests

### Tests for this step

- `test_candidate_delta_reports_every_operation_envelope_defect` — parse several malformed recognized operations and assert one rejection names each safe envelope defect rather than only the first operation’s defect.

- `test_candidate_delta_reports_envelope_and_row_defects_together` — use a class-name decision `row_type` with operation-envelope defects and `source`, then assert one ordered rejection includes the invalid row type and the closed `unknown-field` diagnostic for `source`.

- `test_candidate_delta_known_class_name_selects_schema_for_diagnosis_only` — assert a known internal class name identifies its valid collection schema for diagnostics but still cannot parse into a candidate operation.

- `test_candidate_delta_unknown_row_type_does_not_inspect_untyped_row_body` — assert an unrecognized row type receives the closed invalid-row-type result without echoing or attempting to diagnose arbitrary row-body keys.

- `test_candidate_delta_aggregate_diagnostic_order_is_stable` — parse the same multi-operation malformed response repeatedly and assert the complete reason has one stable ordering.

- `test_candidate_delta_aggregate_rejection_returns_no_partial_delta` — assert any aggregate diagnostic raises `CandidateDeltaError` rather than returning accepted operations from the same response.

- `test_ledger_entity_addition_corrects_class_name_and_reaches_structural_review` (existing, updated) — assert the second prompt carries the closed `invalid-row-type` reason naming the valid `entities` collection, checking those keys rather than the full prose. The first-attempt prompt assertions stay as they are.

Every listed test must be green before this step is complete. The full suite runs at the step gate, so any other existing test that pins the retired wording is found there, not assumed absent.

## Acceptance criteria

- `plan_tool/roadmap_candidate.py:parse_candidate_delta` reports all safe envelope defects across a malformed operations array in one `CandidateDeltaError`.

- A known class-name `row_type` reports `invalid-row-type` and can expose the matching row schema’s closed field diagnostics without becoming accepted input.

- A `decisions` row with `source` remains rejected and reports that known non-writable field in the aggregate reason.

- An unrecognized row type uses the closed fallback and does not cause arbitrary row-body names or values to appear in diagnostics.

- A malformed response never returns a partially accepted `CandidateDelta`.

- `tests/test_roadmap_candidate.py` passes with the focused aggregate-diagnostic cases.

## References

- [BUG_BACKLOG.md — Candidate proposal retry entry](BUG_BACKLOG.md) — Read the failure shape and intended bounded correction.
- [ROADMAP_FEEDBACK_FORMAT.md](ROADMAP_FEEDBACK_FORMAT.md) — Read the ledger-to-candidate lifecycle.
- [ROADMAP_FORMAT.md](ROADMAP_FORMAT.md) — Read the immutable artifact and structural-route contract.
- [plan_tool/roadmap_candidate.py](plan_tool/roadmap_candidate.py) — Read `parse_candidate_delta`, `_parse_operation`, `_parse_stage_row`, and `_require_keys`.
- [plan_tool/roadmap_artifacts.py](plan_tool/roadmap_artifacts.py) — Read `DecisionRow` and its persisted `source` field.
- [plan_tool/roadmap_candidate_run.py](plan_tool/roadmap_candidate_run.py) — Read the unchanged correction, retry, and receipt path.

## Applicable guardrails

- **The plan’s “## Scope guardrails”, complete closed diagnostics:** this step must report every eligible defect in one correction while naming only tool-defined fields and row types.

- **The plan’s “## Scope guardrails”, unchanged strict parser:** this step must retain current accepted key sets and reject malformed responses instead of repairing them.

- **The plan’s “## Out of scope”, non-writable decision fields:** this step may use `DecisionRow.source` to select a diagnostic schema but must not accept, remove, or coerce it.

- **The plan’s “## Out of scope”, retry and persistence boundaries:** this step must not change capsule bytes, receipt or digest identity, replay keys, parse-failure record shape, retry count, or candidate publication.

- **The plan’s “## Out of scope”, existing value-echoing diagnostics:** this step must not reword unknown-operation or duplicate-JSON-key errors.

## Deferred

- Batch-prompt operation examples — step 4 owns `plan_tool/prompts/roadmap-candidate-delta.md` and its prompt-rendering coverage.

- Collection-hint reshaping — step 5 owns `plan_tool/roadmap_candidate_context.py` and the model-facing hint record shape.

- New retry, receipt, and inert-candidate integration coverage — step 6 owns those fixtures in `tests/test_roadmap_candidate_run.py` and proves the parser’s complete reason reaches a successful bounded retry. Step 3 edits only the one pre-existing assertion its own change invalidates.
