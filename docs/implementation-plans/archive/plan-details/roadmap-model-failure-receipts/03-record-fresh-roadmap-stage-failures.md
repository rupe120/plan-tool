> **Auto-archived**: this plan was swept on 2026-11-05 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 3 — Record fresh roadmap stage failures before retry while preserving accepted artifact writes

<!-- plan-tool:detail-format-version: 1 -->

## Summary

Add fresh-stage failure receipts to `plan_tool/roadmap.py` before `_run_stage` retries an invoke, parse, or authored-review-row failure. Reuse the shared sidecar and redacted receipt contracts delivered by steps 1 and 2, while keeping the current retry budget, correction prompts, artifact publication path, and gate diagnostics unchanged. Extend `tests/test_roadmap.py` around the existing retry-loop and `TestAttemptFailedEvent` coverage. On green, a failed fresh attempt remains diagnosable even when a later attempt writes the accepted artifact.

## Table of Contents

- [Summary](#summary) — Gives the reviewer the step’s outcome and main boundary.
- [Table of Contents](#table-of-contents) — Links to the detail sections.
- [Why](#why) — Explains the missing evidence for recovered fresh-stage failures.
- [Input](#input) — Names the upstream receipt contracts this producer consumes.
- [Files (creates vs edits)](#files-creates-vs-edits) — Lists the focused code and test edits.
- [Implementation](#implementation) — Defines when fresh-stage receipts are recorded and what remains unchanged.
- [Tests](#tests) — Lists focused regression coverage for recovered failures and accepted writes.
- [Acceptance criteria](#acceptance-criteria) — States observable completion conditions.
- [References](#references) — Points to the relevant receipt and roadmap contracts.
- [Applicable guardrails](#applicable-guardrails) — Applies the plan’s safety and scope limits.
- [Deferred](#deferred) — Identifies related producer paths outside this step.

## Why

`plan_tool/roadmap.py:_run_stage` records spent attempts through `_note_stage_attempt_failure`, but `attempt_failed` does not retain a response identity or best-effort raw-response availability. When a later attempt succeeds, `RoadmapResult` carries only the accepted artifact, so an earlier fresh invoke, parse, or authored-review-row failure lacks the complete redacted evidence this plan requires.

## Input

- **Step 1 sidecar contract:** Use the shared rejected-response sidecar result produced by step 1. Preserve its disposition and path outcome without reopening, transforming, or cleaning up the sidecar.
- **Step 2 receipt contract:** Use the shared run-log receipt helper produced by step 2 for the producer-owned phase, attempt, failure reason, response identity, and sidecar result.
- **Fresh-stage failure classification:** `plan_tool/roadmap.py:_run_stage`, `_StageOutcome`, and `FAILURE_AUTHORED_REVIEW_ROWS` define the fresh attempt paths that spend the stage budget. The established `FAILURE_INVOKE` and `FAILURE_PARSE` outcomes remain their current classifications.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `plan_tool/roadmap.py` — Record a shared failure receipt for reply-bearing fresh-stage invoke, parse, and authored-review-row failures before `_run_stage` retries.
  - `tests/test_roadmap.py` — Add focused recovered-attempt receipt coverage beside `TestRetryLoop` and `TestAttemptFailedEvent`.

## Implementation

- **Record each rejected fresh reply before retrying.** Extend `plan_tool/roadmap.py:_run_stage` so the fresh authoring loop uses the step 1 sidecar owner and step 2 run-log helper for failures that have a model reply. Emit the receipt in the same attempt that `_note_stage_attempt_failure` records the existing attempt classification, before control continues to the next attempt.

- **Keep identity tied to the rejected reply.** Derive the receipt’s byte count and digest from the original reply returned by `invoker`, not from lifted artifact text, parser errors, correction text, or `_reply_head`. Only a zero-byte reply uses the shared no-response disposition; a whitespace-only rejected reply retains its byte identity and sidecar disposition while preserving the existing unusable-reply retry classification.

- **Cover both parse branches.** `_run_stage` can reject a reply because `_lift_artifact_text` cannot find an artifact or because `stage.parse` raises `RoadmapArtifactError`. Both paths must produce the same parse-kind receipt behavior, while retaining their current correction messages and retry behavior.

- **Treat authored review rows as model failure evidence.** The `FAILURE_AUTHORED_REVIEW_ROWS` branch after `_authored_review_rows(artifact, None)` must produce a receipt for the reply it rejects. Preserve the branch’s current rule: fresh model output cannot create reviewer-owned feedback or removal records.

- **Preserve accepted publication.** Do not route receipt persistence through the accepted artifact writer. The success path in `plan_tool/roadmap.py:_run_roadmap` must still publish only the rendered, gated artifact through `publish_stage_artifact`, reload it through `admit_stage_artifact`, and record `roadmap_stage_written` only for accepted output.

- **Keep gate failures on their existing diagnostic path.** Emit one redacted `not-retained` receipt for a fresh `FAILURE_GATES` attempt after `run_logger.gate_violations` records its structured diagnosis. Do not persist a raw sidecar or duplicate gate messages; the receipt correlates by phase and attempt.

- **Record post-reply source admission.** If the source recheck rejects after a reply was parsed, emit a sidecar-eligible receipt with safe reason `source-admission-rejected`; pre-invocation admission rejection has no reply and emits no receipt.

- **Leave adjacent producer loops alone.** `_run_bounded_stage_feedback` and `plan_tool/roadmap_revision_run.py:run_local_feedback_revision` exercise related retry behavior, but they belong to later producer work. Do not consolidate the loops or change their receipt behavior here.

## Tests

### Tests for this step

- `test_recovered_fresh_invoke_failure_emits_a_redacted_receipt_before_the_successful_write` — asserts a reply-bearing failed invocation creates one receipt with the invoke kind and shared sidecar result, while the second attempt completes and writes the artifact.
- `test_recovered_fresh_empty_invoke_failure_records_no_response_without_raw_content` — asserts an empty reply produces the no-response receipt outcome and JSONL contains none of the response or correction text.
- `test_recovered_fresh_whitespace_invoke_failure_retains_byte_identity` — asserts a whitespace-only rejected reply records byte count, digest, and sidecar disposition while preserving the existing retry behavior.
- `test_unliftable_fresh_reply_emits_a_parse_receipt_before_retry` — asserts the `_lift_artifact_text` rejection path records one parse receipt and the later accepted attempt still writes normally.
- `test_parser_rejected_fresh_reply_emits_a_parse_receipt_before_retry` — asserts the `stage.parse` rejection path records one parse receipt, covering the separate parse branch.
- `test_authored_review_rows_on_a_fresh_stage_emit_a_receipt_before_retry` — asserts `FAILURE_AUTHORED_REVIEW_ROWS` records the rejected reply without changing the prohibition or retry correction.
- `test_fresh_gate_rejection_emits_not_retained_receipt` — asserts gate messages remain on the existing structured event and exactly one redacted `not-retained` receipt is added without raw bytes or copied messages.
- `test_fresh_post_reply_source_admission_records_retained_receipt` — asserts a source recheck after a returned reply emits one `source-admission-rejected` receipt with sidecar eligibility, while a pre-invocation rejection emits none.
- `test_fresh_sidecar_write_failure_preserves_retry_and_receipt_identity` — asserts a write-failed receipt retains rejected-reply identity and the next attempt still follows the existing retry path.
- `test_clean_fresh_stage_emits_no_model_failure_receipt` — asserts a first-attempt accepted artifact does not create failure evidence.

Every listed test must be green before this step is complete.

## Acceptance criteria

- Fresh `_run_stage` invoke, parse, and authored-review-row failures record one shared redacted receipt before a retry begins.
- A receipt records response identity and the step 1 sidecar outcome without placing raw response, prompt, validation, or correction text in JSONL.
- Both fresh parse failure branches produce a parse receipt.
- A recovered fresh failure leaves its receipt durable while the later accepted artifact is published through the existing write and readback path.
- Fresh gate-rejected replies emit a `not-retained` receipt that correlates to `gate_violations`, without a raw sidecar or copied messages.
- `tests/test_roadmap.py` passes with the focused receipt and publication regression cases.

## References

- [BUG_BACKLOG.md — Read the model-failure receipt problem statement and roadmap evidence scope.](../../../../../BUG_BACKLOG.md)
- [BACKLOG.md #217 — Read the roadmap rejected-response evidence and provenance context.](../../../../../BACKLOG.md)
- [DATA_CONTRACT.md — Read the `AttemptFailed`, `GateViolations`, and shared failure-receipt event contracts.](../../../../../DATA_CONTRACT.md)
- [plan_tool/roadmap.py:_run_stage — Read the fresh-stage attempt loop and its current retry classifications.](../../../../../plan_tool/roadmap.py)
- [plan_tool/detail.py:_log_parse_failure — Read the existing best-effort rejected-response sidecar precedent.](../../../../../plan_tool/detail.py)

## Applicable guardrails

- **The plan’s “## Scope guardrails”, redaction boundary:** Keep receipt data limited to the shared safe envelope. Do not add reply-derived text or duplicate fresh gate diagnostics.
- **The plan’s “## Scope guardrails”, unchanged execution behavior:** Preserve failure classifications, retry handling, terminal outcomes, prompts, stdout, and exit-code behavior in `plan_tool/roadmap.py`.
- **The plan’s “## Out of scope”, fresh gate-rejected responses:** Do not add sidecar persistence, raw-response data, or copied gate messages for `FAILURE_GATES`; its required receipt remains redacted and `not-retained`.
- **The plan’s “## Out of scope”, lifecycle work:** Do not alter roadmap publication, checkpoints, writer journals, cleanup, or recovery while adding receipts.
- **The plan’s “## Out of scope”, other producers:** Do not migrate bounded feedback, local feedback revision, or unrelated model-backed commands in this step.

## Deferred

- Bounded stage-feedback receipt wiring in `plan_tool/roadmap.py:_run_bounded_stage_feedback` — a later producer migration owns this separate retry route.
- Local feedback revision receipt wiring in `plan_tool/roadmap_revision_run.py:run_local_feedback_revision` — a later producer migration owns this reply-bearing revision route.
- Shared retry-loop consolidation — the fresh, bounded-feedback, and local-revision loops have distinct contracts; any consolidation requires separate refactor scope.
