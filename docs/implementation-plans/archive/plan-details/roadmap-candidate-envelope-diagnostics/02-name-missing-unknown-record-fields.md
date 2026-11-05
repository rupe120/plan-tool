> **Auto-archived**: this plan was swept on 2026-11-05 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 2 — Name missing and unknown record fields with closed diagnostic names

<!-- plan-tool:detail-format-version: 1 -->

## Summary

Replace the generic strict-key failure in `plan_tool/roadmap_candidate.py` with diagnostics that identify missing and unknown record fields using only names the tool defines. Keep `parse_candidate_delta` strict: invalid records remain rejected, and no field is added, dropped, or coerced. Update `tests/test_roadmap_candidate.py` to cover both named known fields and the safe fallback for arbitrary model-supplied names. On green, a retry reason can tell the model what to fix without echoing untrusted record text.

## Table of Contents

- [Summary](#summary) — States the parser diagnostic change and observable result.
- [Table of Contents](#table-of-contents) — Links to each detail section.
- [Why](#why) — Explains why the generic strict-key error cannot guide a retry.
- [Input](#input) — Names the parser contracts and step 1 constants this work reads.
- [Files (creates vs edits)](#files-creates-vs-edits) — Lists the two in-scope edits.
- [Implementation](#implementation) — Defines closed missing- and unknown-field diagnostics.
- [Tests](#tests) — Lists focused parser coverage.
- [Acceptance criteria](#acceptance-criteria) — Defines completion checks.
- [References](#references) — Points to the relevant candidate and roadmap contracts.
- [Applicable guardrails](#applicable-guardrails) — Applies the plan boundaries to this step.
- [Deferred](#deferred) — Separates later aggregation and prompt work.

## Why

`plan_tool/roadmap_candidate.py:_require_keys` currently turns every missing or unexpected key into the same generic error, and `plan_tool/roadmap_candidate_run.py:_run_batch_candidate_proposal` forwards that error unchanged into the only retry. The retry therefore lacks the field-level information needed to correct a rejected envelope or row body. The parser needs a useful reason while keeping model-provided names out of diagnostics.

## Input

- **Strict candidate-delta parser:** `plan_tool/roadmap_candidate.py:parse_candidate_delta`, `_parse_operation`, `_parse_stage_row`, and nested record parsers all use `_require_keys`; its diagnostic behavior must work for envelopes, rows, and nested records without changing accepted shapes.
- **Step 1 operation keys:** Step 1 provides parser-owned immutable operation-envelope key sets. Use those landed values as the source for any operation-field name that may appear in a diagnostic.
- **Decision-row mismatch:** `plan_tool/roadmap_artifacts.py:DecisionRow` has a `source` field that `plan_tool/roadmap_candidate.py:_parse_stage_row` does not accept for `decisions`. This step must preserve that rejection while making its name safe to report when later work selects the decision schema for diagnosis.
- **Retry consumer:** `plan_tool/roadmap_candidate_run.py:render_candidate_delta_prompt` and `_run_batch_candidate_proposal` already carry `CandidateDeltaError` text into the correction. They remain unchanged in this step.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `plan_tool/roadmap_candidate.py` — add closed field-name diagnostic support around `_require_keys` and its parser callers.
  - `tests/test_roadmap_candidate.py` — add focused strict-parser cases for named and redacted field diagnostics.

## Implementation

- **Name the two field-error classes.** Make strict-key failures distinguish `missing-field` from `unknown-field`. A diagnostic must identify the relevant record context and the field name only when that name belongs to a tool-owned closed vocabulary.

- **Keep the parser strict.** `_require_keys` and all callers must continue rejecting missing and unexpected keys. Do not silently drop an unknown key, supply a missing value, accept `DecisionRow.source`, or otherwise change the parsed `CandidateDelta` shape.

- **Use a closed display vocabulary.** Derive reportable names from parser-owned operation key sets, row and nested-record key sets, and the known row dataclass fields that the parser intentionally excludes. The implementation may use a focused helper or context passed from callers, but it must not infer safety from arbitrary response text.

- **Redact arbitrary model names.** When an unexpected key is not in the applicable closed vocabulary, render the fixed fallback `other` rather than the received key. This rule applies even when the original key is readable or resembles a valid field.

- **Preserve useful known mismatches.** A known but non-writable field such as `source` on a `decisions` row must remain reportable as `unknown-field` once a later parser path supplies the row schema. Do not solve that case by making `source` accepted.

- **Keep this step local to field diagnostics.** Preserve `_parse_operation` dispatch, `_parse_stage_row` row-type rejection, duplicate-key diagnostics, and unknown-operation diagnostics. Step 3 owns collecting every defect and diagnostic handling for invalid class-name `row_type` values; this step establishes the closed field-name rule that work uses.

- **Retain deterministic output.** For records with multiple missing or unknown keys, use a stable ordering for emitted names so the same payload produces the same reason. The exact aggregation across operations remains step 3 work.

## Tests

### Tests for this step

- `test_candidate_missing_required_field_names_the_closed_field` — omit a required operation or row field and assert the parser raises a `missing-field` diagnostic naming that parser-defined field.
- `test_candidate_unknown_known_field_names_the_closed_field` — add a known but disallowed field to a strict record and assert the parser raises an `unknown-field` diagnostic naming that field.
- `test_candidate_unknown_arbitrary_field_is_named_other` — add an arbitrary model-supplied key and assert the error uses `other` without including the supplied key.
- `test_candidate_decision_source_remains_rejected_with_a_closed_name` — assert a `decisions` row carrying `source` remains invalid and can be described as a known non-writable field by the diagnostic path this step establishes.
- `test_candidate_field_diagnostic_order_is_stable` — use more than one missing or unknown field and assert repeated parsing produces the same ordered diagnostic names.
- `test_candidate_key_validator_default_optional_keys_are_immutable` — retain the existing immutability coverage for `_require_keys`.

Every listed test must be green before this step is complete.

## Acceptance criteria

- `plan_tool/roadmap_candidate.py:_require_keys` or its direct diagnostic boundary distinguishes `missing-field` from `unknown-field`.
- A missing parser-defined field is named in the failure reason.
- A known but disallowed field is named in the failure reason without becoming accepted input.
- An arbitrary unknown key is rendered as `other` and does not appear in the error text.
- The diagnostic output is stable for the same rejected record.
- `source` remains outside the accepted `decisions` row schema.
- `tests/test_roadmap_candidate.py` passes with the focused diagnostic cases.

## References

- [BUG_BACKLOG.md § “Candidate proposal retries still emit incompatible row-operation envelopes after the collection-vocabulary repair”](BUG_BACKLOG.md) — Read the retry failure this diagnostic closes.
- [ROADMAP_FEEDBACK_FORMAT.md](ROADMAP_FEEDBACK_FORMAT.md) — Read the ledger-to-candidate lifecycle.
- [ROADMAP_FORMAT.md](ROADMAP_FORMAT.md) — Read the immutable artifact and structural-route contract.
- [plan_tool/roadmap_candidate.py:parse_candidate_delta, _parse_operation, _parse_stage_row, _require_keys](plan_tool/roadmap_candidate.py) — Read the strict wire contract and parser-owned field vocabularies.
- [plan_tool/roadmap_artifacts.py:DecisionRow](plan_tool/roadmap_artifacts.py) — Read the persisted `source` field that remains non-writable in candidate rows.
- [plan_tool/roadmap_candidate_run.py:render_candidate_delta_prompt, _run_batch_candidate_proposal, record_candidate_failure_diagnostics](plan_tool/roadmap_candidate_run.py) — Read the unchanged correction and receipt path that consumes parser reasons.

## Applicable guardrails

- **The plan’s “## Scope guardrails”, closed diagnostics:** this step must render only tool-defined field names and must use the plan’s safe fallback for every other model-supplied name.
- **The plan’s “## Scope guardrails”, unchanged strict parser:** preserve every accepted key set and reject invalid input rather than repairing it.
- **The plan’s “## Out of scope”, decision `source`:** keep `source` outside the writable `decisions` row contract.
- **The plan’s “## Out of scope”, retry and persistence boundaries:** do not change capsule bytes, receipts, digests, replay keys, run-log schema, retry count, or candidate publication.
- **The plan’s “## Out of scope”, existing value-echoing diagnostics:** do not reword unknown-operation or duplicate-JSON-key errors.

## Deferred

- Full multi-operation and row-body defect collection — step 3 owns one complete correction across a rejected response.
- Invalid class-name `row_type` diagnostics and class-to-collection schema selection — step 3 owns this diagnostic route.
- Batch prompt operation examples and collection-hint reshaping — later steps own `plan_tool/roadmap_candidate_run.py`, `plan_tool/prompts/roadmap-candidate-delta.md`, and `plan_tool/roadmap_candidate_context.py`.
