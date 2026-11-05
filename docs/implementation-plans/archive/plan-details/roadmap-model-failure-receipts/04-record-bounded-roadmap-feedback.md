> **Auto-archived**: this plan was swept on 2026-11-05 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 4 — Record bounded roadmap feedback failures before retry while preserving accepted revision writes

<!-- plan-tool:detail-format-version: 1 -->

## Summary

Record a shared redacted model-failure receipt for rejected replies in the bounded stage-feedback retry loop in `plan_tool/roadmap.py`. Reuse the sidecar outcome from step 1 and the receipt event from step 2 without changing bounded feedback’s retry budget, correction prompts, gate diagnostics, or accepted artifact publication. Extend `tests/test_roadmap.py` around `TestAttemptFailedEvent` and `TestBoundedReentryRoutes`. On green, a failed bounded-feedback attempt remains diagnosable even when a later retry writes the accepted revision.

## Table of Contents

- [Summary](#summary) — States the completed bounded-feedback evidence behavior.
- [Table of Contents](#table-of-contents) — Links to each section in this detail.
- [Why](#why) — Explains the recovered-attempt evidence gap.
- [Input](#input) — Names the upstream sidecar and receipt contracts this step consumes.
- [Files (creates vs edits)](#files-creates-vs-edits) — Lists the focused code and test changes.
- [Implementation](#implementation) — Defines receipt timing, boundaries, and preserved publication behavior.
- [Tests](#tests) — Covers recovered retries, receipt contents, and exclusions.
- [Acceptance criteria](#acceptance-criteria) — Lists observable completion conditions.
- [References](#references) — Points to the roadmap and receipt contracts.
- [Applicable guardrails](#applicable-guardrails) — Applies the plan’s scope boundaries to this producer.
- [Deferred](#deferred) — Records nearby producer work outside this step.

## Why

`plan_tool/roadmap.py:_run_bounded_stage_feedback` records an `attempt_failed` event when a bounded feedback reply is unusable or off contract, but a later accepted revision leaves no redacted identity or sidecar outcome for that rejected reply. That gap matters most when the retry recovers, because the accepted replacement is the only artifact left on disk. This step adds the missing durable evidence without changing the reviewer-owned feedback workflow or the accepted revision path.

## Input

- **Step 1 sidecar contract:** Consume the shared rejected-response sidecar result from step 1. Preserve its disposition and optional path exactly; do not reopen, transform, or clean up the sidecar.
- **Step 2 receipt contract:** Use the shared `RunLogWriter` model-failure receipt helper from step 2. Supply the bounded-feedback phase, attempt, failure reason, response identity, and sidecar result without adding a producer-specific event shape.
- **Bounded retry contract:** `plan_tool/roadmap.py:_run_bounded_stage_feedback`, `_StageOutcome`, and `_note_stage_attempt_failure` define the retry-spending bounded-feedback outcomes. `FAILURE_INVOKE` and `FAILURE_PARSE` are receipt candidates; `FAILURE_GATES` remains represented by `RunLogWriter.gate_violations`.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `plan_tool/roadmap.py` — Record sidecar-backed shared failure receipts for bounded-feedback invoke and parse failures before retrying.
  - `tests/test_roadmap.py` — Add focused receipt coverage for bounded-feedback retries, accepted revision writes, and excluded gate failures.

## Implementation

- **Record rejected bounded-feedback replies before the next attempt.** Extend `plan_tool/roadmap.py:_run_bounded_stage_feedback` so every reply-bearing `FAILURE_INVOKE`, `FAILURE_PARSE`, and post-invocation `invalid_detail` path records one shared failure receipt before it returns or retries. Keep existing retry classifications and terminal outcomes unchanged; pre-invocation limit/source failures have no reply and emit no receipt.

- **Keep the reply as the evidence source.** Derive the receipt’s byte count, digest, and best-effort sidecar input from the original `reply` returned by `invoker`. Do not derive them from parsed operations, merged candidates, correction prompts, `_reply_head`, or exception text.

- **Handle missing replies through the shared result.** Only a zero-byte reply uses the step 1 no-response result. A whitespace-only returned reply has bytes and must retain its digest and sidecar disposition even though the retry loop rejects it as unusable.

- **Keep sidecar failure non-blocking.** If the shared sidecar owner reports a write failure, emit that disposition in the receipt and continue through the existing retry path. A diagnostic write failure must not consume an extra attempt, alter the existing failure kind, or prevent a later accepted revision.

- **Preserve gate diagnostics as their current owner.** Emit one redacted `not-retained` receipt for `FAILURE_GATES` in `_run_bounded_stage_feedback` after `RunLogWriter.gate_violations`; keep that event as the bounded structured diagnostic and persist neither raw response nor copied messages.

- **Record post-reply source admission.** If the post-parse `guard()` rejects sources after a reply returns, emit a sidecar-eligible receipt with safe reason `source-admission-rejected`; an admission failure before invocation has no reply and emits no receipt.

- **Preserve accepted revision publication.** A successful candidate returned by `_run_bounded_stage_feedback` must still travel through `plan_tool/roadmap.py:_run_roadmap`’s existing accepted bounded-feedback write path. The receipt is append-only evidence for the failed attempt; it must not change artifact rendering, feedback state changes, overwrite tracking, or replacement ordering.

- **Keep the producer boundary local.** `plan_tool/roadmap_revision_run.py:run_local_feedback_revision` has a reply-bearing local revision flow, but it is a separate producer with a one-shot result contract and is not part of this step’s declared files.

## Tests

- `test_bounded_feedback_parse_failure_receipt_survives_a_recovered_retry` — A malformed bounded-feedback reply emits one parse receipt with rejected-reply identity and then allows the next reply to publish the accepted revision.
- `test_bounded_feedback_invoke_failure_with_reply_records_that_reply` — A nonzero bounded-feedback invocation with a reply emits an invoke receipt tied to that reply before retrying.
- `test_bounded_feedback_empty_reply_receipt_uses_no_response_disposition` — An empty bounded-feedback reply records no response bytes, digest, or sidecar path.
- `test_bounded_feedback_whitespace_reply_retains_byte_identity` — A whitespace-only bounded-feedback reply retains its byte count, digest, and sidecar disposition while preserving the existing unusable-reply retry classification.
- `test_bounded_feedback_sidecar_write_failure_does_not_block_accepted_revision` — A failed best-effort sidecar write is recorded as such while the retry can still accept and publish a revision.
- `test_bounded_feedback_gate_rejection_emits_not_retained_receipt` — A gate-rejected bounded-feedback candidate keeps its existing `attempt_failed` and `gate_violations` events and adds one redacted `not-retained` receipt without a raw-response sidecar or copied messages.
- `test_bounded_feedback_post_reply_source_admission_records_retained_receipt` — A `guard()` rejection after a returned reply emits one `source-admission-rejected` receipt with sidecar eligibility, while pre-invocation admission emits none.
- `test_bounded_feedback_post_reply_invalid_detail_records_retained_receipt` — A returned reply rejected by `StageRevisionLimitError` or `StageRevisionSourceError` emits one sidecar-eligible `invalid_detail` receipt, while an equivalent pre-invocation failure emits none.
- `test_bounded_feedback_receipt_never_serializes_reply_or_correction_text` — JSONL receipt fields contain only the shared redacted envelope, not model text, prompt text, validation prose, or retry corrections.

### Tests for this step

Add or update the focused cases in `tests/test_roadmap.py` beside `TestAttemptFailedEvent` and `TestBoundedReentryRoutes`. Every listed test must be green before this step is finished.

## Acceptance criteria

- A reply-bearing bounded-feedback `FAILURE_INVOKE`, `FAILURE_PARSE`, or post-invocation `invalid_detail` outcome emits one shared model-failure receipt before its retry or return.
- A receipt for a non-empty rejected reply uses that reply’s byte identity and reports the sidecar outcome from step 1.
- An empty rejected reply produces the shared no-response receipt outcome without a raw-response identity or path.
- A whitespace-only rejected reply remains byte-bearing evidence and records its digest and sidecar disposition.
- A sidecar write failure remains diagnostic-only and does not change retry behavior or prevent a later accepted bounded-feedback write.
- A recovered bounded-feedback retry still writes the accepted revision through `plan_tool/roadmap.py:_run_roadmap`.
- `FAILURE_GATES` retains `RunLogWriter.gate_violations` as its structured reply diagnostic and emits one redacted `not-retained` receipt without a raw-response sidecar or copied messages.
- The focused `tests/test_roadmap.py` coverage passes.

## References

- [BUG_BACKLOG.md — Read the model-failure receipt problem statement and roadmap evidence scope.](../../../../BUG_BACKLOG.md)
- [BACKLOG.md #217 — Read the roadmap rejected-response evidence and provenance context.](../../../../BACKLOG.md)
- [DATA_CONTRACT.md — Read the `AttemptFailed`, `GateViolations`, and shared failure-receipt event contracts.](../../../../DATA_CONTRACT.md)
- [plan_tool/roadmap.py:_run_bounded_stage_feedback — Read the bounded feedback retry loop and accepted candidate path.](../../../../plan_tool/roadmap.py)
- [plan_tool/roadmap.py:_run_roadmap — Read the bounded-feedback publication path that remains unchanged.](../../../../plan_tool/roadmap.py)
- [plan_tool/roadmap_revision_run.py:run_local_feedback_revision — Read the separate local revision producer that stays outside this step.](../../../../plan_tool/roadmap_revision_run.py)

## Applicable guardrails

- **The plan’s “## Scope guardrails”, redaction boundary:** Keep the new receipt limited to the shared safe envelope. Do not place reply text, prompt text, validation text, or tool input in JSONL.
- **The plan’s “## Scope guardrails”, unchanged execution behavior:** Preserve bounded-feedback failure classification, retry budget, correction prompts, result outcomes, stdout, and exit-code behavior.
- **The plan’s “## Out of scope”, gate-rejected responses:** Do not persist raw bounded-feedback gate-rejected responses or duplicate their existing structured gate diagnostics; emit only the required redacted `not-retained` receipt.
- **The plan’s “## Out of scope”, lifecycle work:** Do not change roadmap publication, checkpoints, writer journals, cleanup, or recovery.
- **The plan’s “## Out of scope”, other producers:** Leave local feedback revision and unrelated model-backed producer migrations outside this step.

## Deferred

- Local feedback revision receipt wiring in `plan_tool/roadmap_revision_run.py:run_local_feedback_revision` — It uses a separate one-shot producer contract and is outside this step’s declared files.
- Shared retry-loop consolidation — Fresh stages, bounded stage feedback, and local revision have different result and publication contracts; any consolidation needs separate refactor scope.
