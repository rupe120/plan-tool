# Step 5 — Record local feedback revision failures and reply-bearing gate rejections while preserving recoverable publication replacement

<!-- plan-tool:detail-format-version: 1 -->

## Summary

Record a shared redacted model-failure receipt for rejected local `--revise-feedback` replies in `plan_tool/roadmap_revision_run.py`. Reuse the sidecar result from step 1 and the shared receipt writer from step 2, while retaining the local revision’s one-call flow and terminal attempt matrix. Keep `publish_revision_candidate` and recovery behavior unchanged. On green, every eligible rejected reply has safe diagnostic evidence before the existing `roadmap_local_revision_attempt` terminal record, without retaining accepted replies or changing publication outcomes.

## Table of Contents

- [Summary](#summary) — Gives the completed local-revision evidence behavior.
- [Table of Contents](#table-of-contents) — Links to each section in this detail.
- [Why](#why) — Explains the local revision evidence gap.
- [Input](#input) — Names the shared receipt contracts and local terminal record.
- [Files (creates vs edits)](#files-creates-vs-edits) — Lists the focused implementation and test changes.
- [Implementation](#implementation) — Defines receipt eligibility, ordering, and publication boundaries.
- [Tests](#tests) — Covers rejected replies, gate rejections, and unchanged replacement behavior.
- [Acceptance criteria](#acceptance-criteria) — Lists observable completion conditions.
- [References](#references) — Points to the local revision and run-log contracts.
- [Applicable guardrails](#applicable-guardrails) — Applies the plan’s safety and scope limits.
- [Deferred](#deferred) — Records related work outside this producer.

## Why

`plan_tool/roadmap_revision_run.py:_run_accepted_revision` records only the closed terminal matrix through `RunLogWriter.roadmap_local_revision_attempt`. A rejected local reply can therefore leave no digest, byte count, or sidecar outcome, even when the reply reaches operation parsing, merge, candidate validation, or a local gate rejection. The local flow has no `RunLogWriter.gate_violations` event for its reply-bearing gate rejections, so it needs the shared failure receipt without changing the recoverable publication path.

## Input

- **Step 1 sidecar contract:** Consume the rejected-response sidecar result from step 1. Preserve its disposition and optional path without reopening, transforming, or cleaning up the sidecar.
- **Step 2 receipt contract:** Use step 2’s shared `RunLogWriter` model-failure receipt helper for the local revision phase, attempt, reason, response identity, and sidecar result.
- **Local terminal record:** `plan_tool/run_log.py:RoadmapLocalRevisionAttempt` and `RunLogWriter.roadmap_local_revision_attempt` remain the single closed terminal matrix for the one physical backend call.
- **Publication boundary:** `plan_tool/roadmap_revision_run.py:_run_accepted_revision` delegates replacement and recovery concerns to `publish_revision_candidate` and the outer `recover_roadmap_publication` preflight path.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `plan_tool/roadmap_revision_run.py` — Emit shared model-failure receipts for eligible rejected local replies before recording the existing terminal attempt.
  - `tests/test_roadmap_revision_run.py` — Add focused run-log, redaction, gate-rejection, and publication-lifecycle regression coverage.

## Implementation

- **Make receipt eligibility follow the rejected reply.** Extend `plan_tool/roadmap_revision_run.py:_run_accepted_revision` after `invoker` returns so failures with a reply record one shared receipt when that reply does not become an accepted published revision. Use the original `reply` as the evidence source, not parsed operations, merge errors, gate messages, prompts, or `_reply_head`.

- **Cover local rejection branches that consume the reply.** Record evidence for a nonzero backend result that includes reply text, a zero-byte reply through the shared no-response result, whitespace-only reply bytes with their digest and sidecar disposition, operation parsing rejection, merge rejection, candidate parse failure, and reply-bearing `gate-rejected` exits. A source or admission rejection before the invoker runs has no reply and must not manufacture a receipt.

- **Classify post-reply source admission separately.** When `RoadmapSourceAdmissionError` arises after the invoker returns, emit a sidecar-eligible receipt with safe reason `source-admission-rejected` before the existing terminal result path; a source/admission rejection before invocation has no reply and emits no receipt. Other reply-bearing local gate rejection remains receipt-eligible.

- **Treat local gate rejection as receipt-eligible.** `RoadmapRevisionPublishError` and the local candidate-gate path can return `gate-rejected` after a reply is available. Keep `_gate_rejection_detail` as the user-facing diagnostic, but also retain the reply through the shared receipt because this local flow has no structured `gate_violations` record to replace it.

- **Keep receipt timing deterministic.** Emit the receipt before the matching `_attempt_result` call writes `roadmap_local_revision_attempt`, so the rejected response remains diagnosable even though the terminal event contains only closed phase facts. Preserve the existing single-invoker-call rule and attempt number.

- **Do not retain accepted or publication-only failures.** A reply that passes operation, merge, and validation and then reaches a publication failure is not a rejected model response. Do not add successful-response persistence or receipt emission merely because `publish_revision_candidate` later raises.

- **Leave publication recovery alone.** Keep `replacement_started`, `before_replace`, `publication_outcome`, `recover_roadmap_publication`, and interrupt handling intact. The receipt is diagnostic-only: sidecar write failure must be represented by the shared disposition and must not alter replacement, recovery, result category, terminal vocabulary, stdout, or exit-code behavior.

- **Keep JSONL redacted.** Route all receipt fields through the shared writer from step 2. `plan_tool/roadmap_revision_run.py` must not add raw reply text, prompt text, exception prose, gate messages, or provider output to the receipt payload.

## Tests

- `test_nonzero_reply_records_redacted_local_failure_receipt` — asserts a nonzero backend result with reply text emits one receipt with the local phase, attempt `1`, byte identity, and no raw reply in JSONL.
- `test_blank_local_reply_records_no_response_receipt` — asserts an empty reply records the shared no-response disposition without a digest, sidecar path, or raw content.
- `test_whitespace_local_reply_retains_byte_identity` — asserts a whitespace-only rejected reply retains its byte count, digest, and sidecar disposition while preserving the existing unusable-reply outcome.
- `test_operation_rejection_records_reply_receipt_before_terminal_attempt` — asserts invalid operations produce one receipt before the existing `roadmap_local_revision_attempt` event.
- `test_merge_rejection_records_original_reply_receipt` — asserts merge failure identifies the original backend reply rather than derived operations or exception text.
- `test_candidate_parse_failure_records_original_reply_receipt` — asserts candidate parse failure preserves the rejected reply’s identity and leaves the artifact unchanged.
- `test_reply_bearing_local_gate_rejection_records_receipt_without_gate_violations` — asserts a local gate rejection records a receipt while preserving `_gate_rejection_detail` and does not invent a separate structured gate event.
- `test_local_post_reply_source_admission_records_retained_receipt` — asserts post-invocation `RoadmapSourceAdmissionError` emits one `source-admission-rejected` receipt with sidecar eligibility while pre-invocation admission emits none.
- `test_sidecar_write_failure_does_not_change_local_revision_result` — asserts a failed best-effort sidecar write is represented in the receipt but preserves the existing terminal outcome and artifact state.
- `test_publication_failure_after_accepted_reply_does_not_record_model_failure_receipt` — asserts publication failure keeps its current validation and replacement reporting without treating an accepted reply as rejected.
- `test_recoverable_publication_replacement_behavior_is_unchanged_with_receipts` — asserts accepted local revision publication and its seed invalidation behavior remain unchanged.

### Tests for this step

Every listed test in `tests/test_roadmap_revision_run.py` must be green before this step is complete.

## Acceptance criteria

- Eligible rejected local replies emit exactly one shared redacted model-failure receipt before the terminal `roadmap_local_revision_attempt` event.
- Receipt identity comes from the original backend reply and JSONL contains no raw reply, prompt, gate message, or exception detail.
- Only zero-byte replies use the shared no-response disposition; whitespace-only replies retain their byte identity and sidecar disposition.
- Reply-bearing local `gate-rejected` outcomes emit a receipt while retaining their current result detail and terminal matrix values.
- A `RoadmapSourceAdmissionError` discovered after a reply returns emits a `source-admission-rejected` receipt with the same sidecar eligibility; pre-invocation admission failures emit none.
- Pre-invocation rejections, accepted replies, and publication-only failures emit no model-failure receipt.
- Sidecar persistence failure remains diagnostic-only and does not change the local revision result, artifact state, or publication lifecycle.
- `tests/test_roadmap_revision_run.py` passes.

## References

- [DATA_CONTRACT.md — Read the `RoadmapLocalRevisionAttempt` contract and its redaction boundary.](../../../../DATA_CONTRACT.md)
- [plan_tool/roadmap_revision_run.py — Read `_run_accepted_revision`, `_attempt_result`, and `_gate_rejection_detail` for local failure ordering.](../../../../plan_tool/roadmap_revision_run.py)
- [plan_tool/run_log.py — Read `RunLogWriter.roadmap_local_revision_attempt` and the shared receipt surface from step 2.](../../../../plan_tool/run_log.py)
- [BUG_BACKLOG.md — Read the model-backed terminal-failure receipt source issue.](../../../../BUG_BACKLOG.md)

## Applicable guardrails

- **The plan’s “## Scope guardrails”, redacted receipt boundary:** Keep raw response and prompt content out of JSONL; use only the shared receipt’s safe fields and sidecar reference.
- **The plan’s “## Scope guardrails”, gate diagnostics boundary:** Do not add receipt persistence for fresh or bounded stage gate rejections in this step; local reply-bearing gate rejection is the limited exception this step owns.
- **The plan’s “## Out of scope”, behavior stability:** Do not change retry behavior, correction prompts, result outcomes, terminal status vocabulary, stdout, exit codes, template handling, or interrupts.
- **The plan’s “## Out of scope”, publication lifecycle:** Do not change publication, writer-journal, checkpoint, replacement, or recovery authority while adding diagnostics.

## Deferred

- Fresh-stage and bounded-feedback receipt wiring in `plan_tool/roadmap.py` — steps 3 and 4 own those separate producers.
- Shared sidecar persistence and receipt event definitions — steps 1 and 2 own their contracts.
- Publication recovery or writer-journal changes — the plan’s “## Out of scope” retains this lifecycle work outside the receipt slice.
