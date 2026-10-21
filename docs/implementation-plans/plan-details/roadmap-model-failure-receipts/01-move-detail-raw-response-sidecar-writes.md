# Step 1 — Move detail raw-response sidecar writes to a shared owner

<!-- plan-tool:detail-format-version: 1 -->

## Summary

Extract detail’s rejected-response sidecar write into `plan_tool/model_response_sidecar.py` and route `plan_tool/detail.py:_log_parse_failure` through it. The shared leaf must accept producer-owned identifiers instead of requiring a plan path, while detail keeps its existing parse-retry flow, path convention, and run-log pointer behavior. Use whole-file replacement for the raw UTF-8 payload, but treat any sidecar I/O failure as diagnostic-only. On green, detail produces the same best-effort parse-failure evidence through a reusable owner that later roadmap producers can call.

## Table of Contents

- [Summary](#summary) — Reviewer overview of the extraction and unchanged detail behavior.
- [Table of Contents](#table-of-contents) — Links to each section in this detail.
- [Why](#why) — Explains why the sidecar owner must stop depending on detail.
- [Input](#input) — Defines the existing detail caller and sidecar-path contract.
- [Files (creates vs edits)](#files-creates-vs-edits) — Separates the new leaf and focused test coverage from detail edits.
- [Implementation](#implementation) — Describes the reusable, best-effort sidecar contract.
- [Tests](#tests) — Names the focused regression and leaf-boundary cases.
- [Acceptance criteria](#acceptance-criteria) — Lists observable completion conditions.
- [References](#references) — Points to the failure-receipt contract and current producers.
- [Applicable guardrails](#applicable-guardrails) — States the plan boundaries that bind this extraction.
- [Deferred](#deferred) — Records related producer work outside this step.

## Why

`plan_tool/detail.py:_log_parse_failure` currently owns both detail-specific plan-slug derivation and the reusable operation of storing a rejected model reply beneath `.plan-tool/parse-failures/`. That prevents the selected roadmap producers from using one owner without inventing a detail plan path, even though `plan_tool/create.py:_dump_failed_response` and `plan_tool/roadmap_candidate_run.py:record_candidate_failure_diagnostics` already show the same sidecar concern in other command lanes. This step extracts only the shared persistence boundary so later receipt work can use it without changing detail’s result, retry, or JSONL behavior.

## Input

- **Detail caller:** `plan_tool/detail.py:_author_step_detail` calls `plan_tool/detail.py:_log_parse_failure` after parsing rejects a raw model response and before retrying.
- **Detail identity:** `plan_tool/detail.py:_log_parse_failure` derives the plan slug with `plan_tool/detail_artifacts.py:_plan_slug` and supplies the step and attempt identity used in the current filename convention.
- **Run-log pointer:** `plan_tool/detail.py:_author_step_detail` converts a successful sidecar path to a repo-relative POSIX path for `RunLogWriter.parse_failure`; a failed sidecar write remains an empty `failure_path` while `raw_bytes` stays recorded.
- **Raw payload:** the leaf must preserve the rejected response as UTF-8 bytes without parsing, trimming, redacting, or placing those bytes in JSONL.

## Files (creates vs edits)

- **New files:**
  - `plan_tool/model_response_sidecar.py` — Add the narrow shared owner for path construction, raw-response persistence, and a result that distinguishes the sidecar outcomes needed by later receipt work.
  - `tests/test_model_response_sidecar.py` — Add focused persistence, failure, and leaf-import-boundary coverage.

- **Existing files (edits only):**
  - `plan_tool/detail.py` — Replace the local `_log_parse_failure` write mechanics with the shared owner while retaining `_author_step_detail`’s existing retry and run-log behavior.
  - `tests/test_detail.py` — Keep the detail integration tests proving parse failures retain the same sidecar and run-log behavior after the extraction.

## Implementation

- **Make `plan_tool/model_response_sidecar.py` the single owner of rejected-response sidecar persistence.** Give it a small public entry point that receives `repo_root`, a producer-owned slug or equivalent identifier, a collision-free receipt identity, and the raw response or an explicit decision not to retain one. Every selected producer supplies an identity unique to its run, phase, and attempt; the resulting written path must never be reused for a different reply. It must not require a `Path` to a plan merely to derive identity.

- **Return a structured sidecar result rather than making callers infer state from exceptions.** The result must let step 2 distinguish a written sidecar, no response, intentionally unretained response, and write failure without reading the filesystem again. Keep this result local to the sidecar leaf; this step must not add or change the run-log receipt schema.

- **Keep the stored payload exact and replace files as whole files.** Encode the supplied response once as UTF-8 bytes and use the repository’s whole-file atomic replacement behavior from `plan_tool/fileio.py:atomic_write_bytes` or an equivalent leaf-safe mechanism. A failed write must leave an existing target intact and report failure to the caller rather than exposing a partial response.

- **Preserve detail’s externally visible behavior.** Retain `plan_tool/detail.py:_log_parse_failure` as a compatibility wrapper if that keeps its callers and focused tests stable, or adapt its single call from `plan_tool/detail.py:_author_step_detail` directly. The detail path must remain under `.plan-tool/parse-failures/<plan-slug>/`, use the existing step/attempt-oriented naming shape, return `None` on best-effort write failure, and avoid changing retry notices, `_MAX_INVOKE_ATTEMPTS`, `RunLogWriter.parse_failure`, or the `raw_bytes` calculation.

- **Keep the new module a leaf.** It may depend on low-level write support such as `plan_tool/fileio.py`, but it must not import `plan_tool/detail.py`, `plan_tool/roadmap.py`, `plan_tool/run_log.py`, or producer orchestration modules. Producers own failure reasons, retries, and receipt emission; the leaf owns only sidecar persistence and its result.

- **Do not fold in adjacent implementations.** `plan_tool/create.py:_dump_failed_response` and `plan_tool/roadmap_candidate_run.py:record_candidate_failure_diagnostics` exercise the same persistence concern, but their migration is separate work. Do not change their paths, filename shapes, durability choices, or result handling in this step.

## Tests

### Tests for this step

- `tests/test_model_response_sidecar.py:test_written_response_is_stored_under_the_producer_slug` — asserts a retained raw response is written below `.plan-tool/parse-failures/<slug>/`, returns a usable path, and preserves its exact UTF-8 bytes.
- `tests/test_model_response_sidecar.py:test_existing_target_is_replaced_as_one_complete_response` — asserts replacement leaves the final target containing only the new complete payload.
- `tests/test_model_response_sidecar.py:test_distinct_receipt_identities_never_overwrite_each_other` — asserts two producer attempts produce distinct paths and each receipt path resolves to bytes matching its digest.
- `tests/test_model_response_sidecar.py:test_write_failure_reports_write_failed_and_preserves_existing_target` — injects a write failure and asserts no exception escapes, no successful path is reported, and a prior file remains unchanged.
- `tests/test_model_response_sidecar.py:test_no_response_and_not_retained_are_distinct_non_write_results` — asserts the shared result keeps absence and policy-based non-retention separate without creating a sidecar directory.
- `tests/test_model_response_sidecar.py:test_leaf_does_not_import_producer_orchestrators` — asserts the new leaf has no import edge to detail, roadmap, run-log, or other producer modules.
- `tests/test_detail.py:TestGenerateDetailParseFailureLogging.test_first_attempt_failure_logs_raw_response` — keeps the existing detail path and exact rejected-response content regression green through the shared owner.
- `tests/test_detail.py:TestGenerateDetailParseFailureLogging.test_clean_first_attempt_writes_no_failure_log` — keeps successful first attempts from creating a sidecar directory.
- `tests/test_detail.py:TestGenerateDetailRunLogParseFailure.test_parse_failure_event_path_empty_when_logging_failed` — keeps best-effort failure from changing detail’s parse-failure event or retry outcome.
- `tests/test_detail.py:TestGenerateDetailRunLogParseFailure.test_parse_failure_event_does_not_duplicate_payload` — keeps rejected response content out of JSONL.

Every listed test must be green before this step is complete.

## Acceptance criteria

- `plan_tool/model_response_sidecar.py` owns reusable raw-response sidecar writes without importing producer orchestration modules.
- A caller can provide its own slug and attempt identity without supplying a plan path.
- Every written result has a collision-free receipt identity, so its path remains bound to the receipt's digest even after later rejected replies.
- A retained response is stored as its exact UTF-8 payload under `.plan-tool/parse-failures/<slug>/`.
- A sidecar write replaces a target as one complete file; a failed replacement does not expose partial new content.
- The shared result distinguishes written, no-response, not-retained, and write-failed outcomes without changing the run-log schema.
- `plan_tool/detail.py:_author_step_detail` keeps writing existing detail parse-failure sidecars before retry and keeps `RunLogWriter.parse_failure` free of raw response content.
- `tests/test_model_response_sidecar.py` and the affected cases in `tests/test_detail.py` pass.

## References

- [`BUG_BACKLOG.md` — “Model-backed commands do not share one complete terminal failure receipt”](BUG_BACKLOG.md) — Read the shared-owner and later-migration boundaries.
- [`BACKLOG.md` #217 — roadmap rejected-response evidence and Integration provenance](BACKLOG.md) — Read the selected roadmap evidence context.
- [`DATA_CONTRACT.md` — `AttemptFailed`, `GateViolations`, and `ParseFailure`](DATA_CONTRACT.md) — Preserve the existing redacted JSONL boundary.
- [`plan_tool/detail.py:_log_parse_failure`](plan_tool/detail.py) — Read the current detail path, best-effort behavior, and caller contract.
- [`plan_tool/roadmap.py:_run_stage` and `plan_tool/roadmap.py:_run_bounded_stage_feedback`](plan_tool/roadmap.py) — Read the future producer identities that need a plan-path-free helper.
- [`plan_tool/roadmap_revision_run.py:run_local_feedback_revision`](plan_tool/roadmap_revision_run.py) — Read the future local revision producer boundary.

## Applicable guardrails

- **The plan’s “## Scope guardrails”, redacted terminal receipts:** This step may retain raw replies only in the local sidecar and must not add raw response, prompt, validation, provider, or tool-input data to JSONL.
- **The plan’s “## Scope guardrails”, no lifecycle expansion:** This step must not add cleanup, a reader command, successful-response persistence, or retry behavior.
- **The plan’s “## Scope guardrails”, later migrations:** This extraction may preserve detail’s existing behavior, but it must not migrate create, candidate, seed-materialization, or candidate-review producers.
- **The plan’s “## Scope guardrails”, stable command behavior:** This step must not change exception classification, return codes, terminal statuses, template reads, or interrupt handling.
- **The plan’s “## Out of scope”, publication and recovery:** The sidecar leaf must not take ownership of roadmap publication, checkpoints, journals, or recovery.

## Deferred

- `plan_tool/roadmap.py:_run_stage` and `plan_tool/roadmap.py:_run_bounded_stage_feedback` migration — later steps use the shared sidecar owner while adding their receipt behavior.
- `plan_tool/roadmap_revision_run.py:run_local_feedback_revision` migration — step 5 applies the settled reply-retention policy for local revisions.
- `plan_tool/create.py:_dump_failed_response` and `plan_tool/roadmap_candidate_run.py:record_candidate_failure_diagnostics` consolidation — later producer migrations retain their current behavior until the source BUG entry assigns them.
- Terminal-failure receipt fields and `plan_tool/run_log.py` changes — step 2 owns the redacted receipt schema and sidecar disposition serialization.
