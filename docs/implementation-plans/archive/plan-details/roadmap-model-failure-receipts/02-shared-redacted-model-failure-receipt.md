> **Auto-archived**: this plan was swept on 2026-11-05 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 2 — Add the shared redacted model-failure receipt

<!-- plan-tool:detail-format-version: 1 -->

## Summary

Add one run-log event and `RunLogWriter` helper that record a rejected model response without storing its contents in JSONL. Update `plan_tool/data_contract.py` and `DATA_CONTRACT.md` so the new event is drift-checked and documented. The receipt records producer-owned phase, attempt, reason, response identity, and the sidecar result supplied by step 1. On green, later roadmap producers can emit a consistent terminal-failure receipt without changing snapshot replacement or cleanup behavior.

## Table of Contents

- [Summary](#summary) — Reviewer overview of the shared receipt contract.
- [Table of Contents](#table-of-contents) — Links to each section in this detail.
- [Why](#why) — Explains the missing durable failure evidence.
- [Input](#input) — Defines the sidecar result from step 1 and existing run-log rules.
- [Files (creates vs edits)](#files-creates-vs-edits) — Lists the focused receipt and documentation changes.
- [Implementation](#implementation) — Defines the safe event envelope and writer boundary.
- [Tests](#tests) — Covers receipt serialization and unchanged snapshot lifecycle behavior.
- [Acceptance criteria](#acceptance-criteria) — Lists observable completion conditions.
- [References](#references) — Points to the relevant existing contracts and future producers.
- [Applicable guardrails](#applicable-guardrails) — States the plan boundaries that bind this step.
- [Deferred](#deferred) — Records producer wiring and unrelated lifecycle work outside this step.

## Why

`plan_tool/run_log.py:AttemptFailed` records that an attempt failed, while `ParseFailure` only points to detail’s parse-failure sidecar and `GateViolations` only covers stage gates. None gives all selected roadmap producers one safe way to record a rejected response, its byte identity, and whether a raw sidecar is available. A shared receipt closes that evidence gap before steps 3–5 attach it to their existing retry and terminal paths.

## Input

- **Step 1 sidecar result:** Step 1 provides `plan_tool/model_response_sidecar.py` with a structured result that distinguishes `written`, `no-response`, `not-retained`, and `write-failed`. This step serializes that result; it does not re-open or re-check sidecar files.
- **Existing event model:** `plan_tool/run_log.py:Event`, `RunLogWriter._emit`, and `RunLogWriter.attempt_failed` define append-only JSONL event registration and producer-owned safe fields.
- **Snapshot lifecycle:** `plan_tool/run_log.py`'s in-flight snapshot refresh and `RunLogWriter.run_end` own in-flight replacement and guarded cleanup. The receipt is an append-only event and must not alter either path.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `plan_tool/run_log.py` — Add the receipt event dataclass, register it in `Event`, and add a `RunLogWriter` emission helper.
  - `plan_tool/data_contract.py` — Register the receipt as a persisted dataclass contract.
  - `tests/test_run_log.py` — Add focused receipt and lifecycle-regression coverage.
  - `DATA_CONTRACT.md` — Document the receipt’s event discriminator, fields, redaction boundary, and sidecar-disposition meanings.

## Implementation

- **Add one shared receipt event.** Define a self-describing event such as `ModelFailureReceipt` beside `AttemptFailed` and `ParseFailure` in `plan_tool/run_log.py`. Register it in `Event` and expose one matching `RunLogWriter` helper so future producers do not hand-build payloads.

- **Keep the receipt producer-owned but structurally consistent.** The helper must accept the existing safe reason or terminal outcome unchanged, plus `phase`, `attempt`, response byte count, a SHA-256 digest of the response bytes when bytes exist, sidecar disposition, and a sidecar path only when step 1 reports one. Do not create a new shared failure-reason vocabulary.

- **Use the closed sidecar-disposition contract from step 1.** `written`, `no-response`, `not-retained`, and `write-failed` must remain distinguishable. `no-response` takes precedence when no bytes exist. A receipt with no raw response or no retained sidecar must omit the path rather than serializing an invented path or placeholder.

- **Resolve the sidecar result before emitting.** The receipt must describe the final sidecar disposition, including a write failure, so later producer steps cannot emit a receipt that claims a sidecar exists before the best-effort write finishes.

- **Keep JSONL redacted.** Do not add raw response text, prompt text, validation messages, provider transcripts, tool-input summaries, or sidecar-write error prose to the event. Existing `RunLogWriter.gate_violations` remains the structured diagnostic source for fresh and bounded stage gate failures.

- **Preserve the run-log lifecycle.** Do not route receipt emission through the in-flight snapshot refresh or `RunLogWriter.run_end`. The existing merge-on-refresh snapshot replacement and guarded same-slug cleanup must remain unchanged.

- **Register and document the persisted shape together.** Add the event to `plan_tool/data_contract.py:persisted_dataclass_contracts` and create a dedicated `DATA_CONTRACT.md` section naming every persisted field. Follow the existing `AttemptFailed` and `ParseFailure` documentation style, with code as the source of truth.

## Tests

### Tests for this step

- `tests/test_run_log.py:test_model_failure_receipt_records_safe_identity_and_sidecar_pointer` — asserts the writer records phase, attempt, producer-owned reason, byte count, SHA-256 digest, disposition, and written-sidecar path.
- `tests/test_run_log.py:test_model_failure_receipt_omits_path_when_no_response_or_sidecar_is_not_retained` — asserts non-written dispositions do not invent a sidecar path.
- `tests/test_run_log.py:test_model_failure_receipt_never_serializes_raw_response_or_diagnostic_prose` — asserts receipt JSONL contains no raw reply, prompt, validation, transcript, or tool-input content.
- `tests/test_run_log.py:test_model_failure_receipt_keeps_write_failed_response_identity_without_path` — asserts a failed best-effort sidecar write retains byte count and digest while omitting the path.
- `tests/test_run_log.py:test_model_failure_receipt_does_not_refresh_or_replace_in_flight_snapshot` — asserts receipt emission leaves the current snapshot ownership and lifecycle fields unchanged.
- `tests/test_run_log.py:test_run_end_skips_unlink_when_a_newer_run_owns_the_snapshot` — keeps guarded cleanup behavior green after the new event is added.

Every listed test must be green before this step is complete. Run the existing `tests/test_data_contract.py` drift checks as part of the focused verification.

## Acceptance criteria

- `plan_tool/run_log.py` exposes one registered terminal model-failure receipt event and one `RunLogWriter` helper for it.
- A receipt records phase, attempt, producer-owned reason, response byte count, response digest, sidecar disposition, and a path only for a written sidecar.
- The four sidecar dispositions remain distinguishable, and no-response does not report a digest or path.
- Receipt JSONL contains no raw response, prompt, validation message, provider transcript, or tool-input summary.
- `plan_tool/data_contract.py:persisted_dataclass_contracts` registers the new event, and its `DATA_CONTRACT.md` section documents every persisted field.
- Receipt emission does not change in-flight snapshot refresh or `RunLogWriter.run_end` replacement and cleanup behavior.
- `tests/test_run_log.py` and the existing data-contract drift tests pass.

## References

- [BUG_BACKLOG.md — “Model-backed commands do not share one complete terminal failure receipt”](BUG_BACKLOG.md) — Read the selected producer scope and later migration boundary.
- [BACKLOG.md #217 — roadmap rejected-response evidence and Integration provenance](BACKLOG.md) — Read the evidence motivating durable rejected-response diagnostics.
- [DATA_CONTRACT.md — `AttemptFailed`, `GateViolations`, and `ParseFailure`](DATA_CONTRACT.md) — Follow the current redacted run-log event contract.
- [plan_tool/roadmap.py:_run_stage and plan_tool/roadmap.py:_run_bounded_stage_feedback](plan_tool/roadmap.py) — Read the fresh and bounded future receipt producers.
- [plan_tool/roadmap_revision_run.py:run_local_feedback_revision](plan_tool/roadmap_revision_run.py) — Read the future local revision producer boundary.

## Applicable guardrails

- **The plan’s “## Scope guardrails”, redacted terminal receipts:** This step must keep receipt JSONL to safe identifiers and metadata, leaving raw response content only to the step 1 sidecar owner.
- **The plan’s “## Scope guardrails”, no lifecycle expansion:** This step must not add cleanup, a reader command, successful-response persistence, or retry behavior.
- **The plan’s “## Scope guardrails”, later migrations:** This step defines the shared receipt only; it must not wire create, detail, seed, candidate, or roadmap producer paths.
- **The plan’s “## Scope guardrails”, stable command behavior:** This step must not change exception classification, return codes, terminal status vocabulary, template-read behavior, or interrupt handling.
- **The plan’s “## Out of scope”, publication and recovery:** This event must not alter roadmap publication, checkpoints, writer journals, or lifecycle recovery.

## Deferred

- `plan_tool/roadmap.py:_run_stage` and `plan_tool/roadmap.py:_run_bounded_stage_feedback` wiring — steps 3 and 4 emit the shared receipt around their established failure paths.
- `plan_tool/roadmap_revision_run.py:run_local_feedback_revision` wiring — step 5 applies the receipt and sidecar policy to local revision outcomes.
- `plan_tool/create.py:_dump_failed_response` and `plan_tool/roadmap_candidate_run.py:record_candidate_failure_diagnostics` migration — later source-BUG work retains their separate behavior.
- In-flight snapshot redesign, cleanup policy, and recovery behavior — outside this receipt-only step.
