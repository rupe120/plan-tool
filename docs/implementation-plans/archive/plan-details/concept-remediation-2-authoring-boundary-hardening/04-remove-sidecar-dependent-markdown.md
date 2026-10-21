# Step 4 — Remove the sidecar-dependent Markdown fallback for detail responses

## Summary

Require every newly invoked or resumed detail response to pass the structured response parser before it can become a detail file. Update `plan_tool/detail.py` so `_author_step_detail()` applies the same rule with or without a concept record and in both serial and concurrent runs. Treat matching opaque Markdown-only checkpoints as cache misses because their generic checkpoint metadata cannot prove that they came from the current protocol. Update `tests/test_detail.py` so successful authoring fixtures use structured envelopes and green tests show that malformed or Markdown-only responses never replace an artifact.

## Table of Contents

- [Summary](#summary) — reviewer overview of the required response boundary
- [Table of Contents](#table-of-contents) — links to every section in this detail
- [Why](#why) — the sidecar-dependent behavior that must be removed
- [Input](#input) — upstream parser and checkpoint contracts this step consumes
- [Files (creates vs edits)](#files-creates-vs-edits) — production and test edits
- [Implementation](#implementation) — required parsing behavior across fresh and resumed authoring
- [Tests](#tests) — focused cases for sidecar, checkpoint, retry, and concurrency paths
- [Acceptance criteria](#acceptance-criteria) — observable completion checks
- [References](#references) — authoritative structured-output guidance
- [Deferred](#deferred) — compatibility work intentionally left out

## Why

`plan_tool/detail.py:_author_step_detail()` currently chooses its acceptance rule from `concept_tree`: when the sidecar is absent, both the fresh-response and cached-response branches can fall back from `parse_structured_detail_response()` to `parse_detail_response()`. The pre-scan in `plan_tool/detail.py:generate_detail()` also validates a checkpoint’s structured payload only when a concept record exists. That makes the same model output valid for one plan and invalid for another, and it lets a malformed fresh response or an opaque Markdown-only checkpoint bypass the deferral envelope required by the prompt. The authoring boundary must depend on the response itself, not on whether `load_concepts()` returned a sidecar.

## Input

- **Step 3 response contract:** Step 3 tightens `plan_tool/detail.py:parse_structured_detail_response()` and its deferral validation. This step uses that parser as the required acceptance boundary rather than restating or adding another envelope schema.
- **Detail checkpoint payload:** `plan_tool/checkpoint.py:Checkpoint` stores an opaque payload string. Its generic schema version identifies the checkpoint storage shape, not the detail-response protocol, so it cannot identify a Markdown-only payload as trusted legacy output.
- **Concept record availability:** `plan_tool/detail.py:generate_detail()` may receive `None` from `load_concepts()` for a plan with no concept record. That absence remains supported, but it no longer permits a different response format.
- **Retry limit:** `plan_tool/detail.py:_MAX_INVOKE_ATTEMPTS` remains the bounded retry policy. A missing or invalid envelope follows the existing parse-failure and reprompt path.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `plan_tool/detail.py` — require structured parsing in `_author_step_detail()` for cached and fresh responses regardless of `concept_tree`, and reject opaque Markdown-only checkpoints during `generate_detail()` pre-scan.
  - `tests/test_detail.py` — move authoring success fixtures to structured responses and add focused coverage for no-sidecar authoring, current-format resume, opaque checkpoint invalidation, retries, and concurrent execution.

## Implementation

The foundational logic is: **a detail response is publishable only when `parse_structured_detail_response()` accepts it under the validation context available for that plan.**

- **Use one protocol in `_author_step_detail()`.** Apply structured parsing in both the `cached is not None` branch and the fresh invocation retry loop. Do not call `parse_detail_response()` as an alternative after structured parsing fails.
- **Keep `parse_detail_response()` as the body parser.** `plan_tool/detail.py:parse_structured_detail_response()` still uses it to validate and extract the Markdown portion before the transport envelope. This step removes the authoring fallback to bare Markdown; it does not remove the Markdown-body helper or its focused parser tests.
- **Preserve concept-aware validation.** When `_author_step_detail()` receives `step`, `plan`, and `concept_tree`, continue passing them to `parse_structured_detail_response()` so Step 3’s ownership, review-state, and prose/candidate checks run.
- **Require an empty candidate list without a concept record.** A plan with no concept sidecar may still author details, but only a structured response with no deferral candidates can succeed because there is no signed record against which to validate a candidate. Sidecar absence must never turn a non-empty or malformed envelope into accepted Markdown.
- **Reject old opaque payloads during checkpoint pre-scan.** In `plan_tool/detail.py:generate_detail()`, validate every matching detail checkpoint with `parse_structured_detail_response()`, not only checkpoints loaded alongside a concept tree. A Markdown-only payload becomes a cache miss and the normal invocation path produces a current-format response.
- **Keep a second check in `_author_step_detail()`.** The worker is directly testable and accepts a `cached` argument, so it must enforce the protocol itself even if `generate_detail()` already filtered the checkpoint. The pre-scan prevents invalid cache-hit reporting; the worker check protects the authoring boundary.
- **Recognize current format by payload content.** A checkpoint whose payload contains a valid structured response can resume. Do not infer detail-protocol provenance from `plan_tool/checkpoint.py:CHECKPOINT_SCHEMA_VERSION`; that version is shared by opaque checkpoint users and cannot distinguish legacy detail Markdown.
- **Preserve failure behavior.** Invalid fresh output must still be logged by `plan_tool/detail.py:_log_parse_failure`, receive at most the existing reprompt count, and return an unsuccessful `_StepAuthoringOutcome` without writing a detail file or update record.
- **Cover both dispatch paths.** `plan_tool/detail.py:generate_detail()` has a serial authoring loop and `plan_tool/detail.py:_generate_detail_concurrent`. Both reach `_author_step_detail()`, while both also consume the shared checkpoint pre-scan. Tests must prove that `jobs=1` and `jobs>1` enforce the same envelope rule.
- **Update shared success fixtures carefully.** In `tests/test_detail.py`, use the existing `_structured_detail()` helper or an equivalent structured success fixture for tests that exercise authoring. Keep bare `_GOOD_BODY`-style Markdown where a test directly exercises `parse_detail_response()` or intentionally represents an invalid or pre-feature checkpoint.
- **Do not add checkpoint schema or persistence changes.** The rejected alternative is provenance-gated legacy parsing: `plan_tool/checkpoint.py:Checkpoint` has no detail-protocol discriminator, and that file is outside this step. Re-invocation is the safe compatibility behavior.

## Tests

- `test_author_step_requires_envelope_without_concept_record` — `tests/test_detail.py` proves bare Markdown is rejected even when no concept sidecar exists.
- `test_author_step_accepts_empty_envelope_without_concept_record` — `tests/test_detail.py` proves a valid structured response with no deferrals still authors a legacy plan.
- `test_author_step_requires_envelope_with_concept_record` — `tests/test_detail.py` proves sidecar presence does not change the base response protocol.
- `test_resume_accepts_current_structured_checkpoint` — `tests/test_detail.py` proves a valid structured checkpoint resumes without invoking the backend.
- `test_resume_reinvokes_for_opaque_markdown_checkpoint` — `tests/test_detail.py` proves a matching Markdown-only checkpoint is not reported or used as a cache hit and the backend is invoked.
- `test_direct_worker_rejects_cached_markdown` — `tests/test_detail.py` proves `_author_step_detail()` enforces the rule when called directly with a cached payload.
- `test_missing_envelope_exhausts_bounded_reprompt` — `tests/test_detail.py` proves two Markdown-only fresh responses consume `_MAX_INVOKE_ATTEMPTS`, write nothing, and return an unparseable-response failure.
- `test_retry_recovers_with_structured_second_response` — `tests/test_detail.py` proves a missing envelope on the first attempt can recover when the reprompt returns the required format.
- `test_concurrent_authoring_requires_structured_responses_without_sidecar` — `tests/test_detail.py` proves `jobs>1` follows the same rule and does not publish a bare-Markdown sibling.
- `test_parse_detail_response_accepts_markdown_body` — `tests/test_detail.py` remains green to show that the inner Markdown-body parser still serves `parse_structured_detail_response()`.

### Test-creation order (feature step)

1. Add the direct `_author_step_detail()` no-sidecar rejection and structured-success tests with the worker change.
2. Add current-format checkpoint resume and opaque Markdown checkpoint re-invocation tests with the pre-scan change.
3. Add bounded reprompt and second-attempt recovery tests with structured authoring fixtures.
4. Add the concurrent no-sidecar case after the shared serial boundary is green.
5. Update existing authoring fixtures and checkpoint expectations to use structured envelopes, while leaving direct `parse_detail_response()` coverage focused on Markdown bodies.

Every new test and the existing focused `tests/test_detail.py` suite must be green before this step is considered finished.

## Acceptance criteria

- `_author_step_detail()` returns an unsuccessful `_StepAuthoringOutcome` for a bare Markdown fresh response whether `concept_tree` is present or absent.
- `_author_step_detail()` accepts a valid structured response with an empty deferral list when no concept record exists.
- A valid structured checkpoint resumes without invoking the backend.
- A matching opaque Markdown-only checkpoint is treated as a cache miss, does not emit a checkpoint-hit event, and causes a fresh invocation.
- A direct `_author_step_detail()` call cannot bypass structured validation by supplying bare Markdown through `cached`.
- Missing or malformed envelopes use the existing parse-failure logging and stop after `_MAX_INVOKE_ATTEMPTS`.
- Serial and `jobs>1` authoring apply the same structured-response requirement.
- No rejected response writes or replaces a detail file, returns a plan-update record, or persists deferral links.
- `tests/test_detail.py` passes with authoring success fixtures using structured envelopes.

## References

- [Claude API Structured Outputs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs) — Read the refusal, truncation, and client-side validation guidance that explains why every returned response still needs local validation.

## Deferred

- **Legacy Markdown-only checkpoint compatibility** — generic checkpoint metadata cannot prove that a payload predates the structured protocol, so this step re-invokes instead of adding an unsafe compatibility path.
- **Rewriting existing detail files to add transport envelopes** — persisted detail files contain only the publishable Markdown body; the envelope is an authoring transport contract, not an on-disk detail format.
- **Checkpoint schema changes** — adding a detail-specific protocol discriminator would require plan-level scope beyond `plan_tool/detail.py` and `tests/test_detail.py`.
