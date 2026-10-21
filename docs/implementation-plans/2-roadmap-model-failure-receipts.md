---
format_version: 1
title: Roadmap Model Failure Receipts
intent: Every rejected model response in fresh roadmap stage authoring, bounded stage
  feedback, and local feedback revision leaves one dependable, redacted terminal receipt,
  including recovered attempts, and records whether its raw response is available
  in a best-effort sidecar.
status: completed
priority: medium
risk_profile: standard
risk_profile_rationale: Risk declaration uses standard because --yes does not accept
  model risk proposals.
test_command: uv run pytest tests/ -q -n auto
enforce_step_tests: true
source_seed: plan-seeds/roadmap-model-failure-receipts.md
steps:
- id: 1
  title: Move detail raw-response sidecar writes to a shared owner while preserving
    best-effort whole-file replacement
  intent: Give roadmap and detail one reusable owner for rejected-response sidecars
    without changing detail behavior or subsuming create's separate later migration.
  files:
  - plan_tool/detail.py
  - tests/test_detail.py
  creates:
  - plan_tool/model_response_sidecar.py
  - tests/test_model_response_sidecar.py
  complexity: medium
  change_type: refactor
  detail: docs/implementation-plans/plan-details/roadmap-model-failure-receipts/01-move-detail-raw-response-sidecar-writes.md
  status: done
- id: 2
  title: Add the shared redacted model-failure receipt without changing run-log snapshot
    replacement or cleanup
  intent: Make every migrated producer describe a failed model response with the same
    safe, machine-readable evidence envelope.
  files:
  - plan_tool/run_log.py
  - plan_tool/data_contract.py
  - tests/test_run_log.py
  - DATA_CONTRACT.md
  complexity: medium
  change_type: feature
  depends_on:
  - 1
  depends_on_notes:
    1: Provides the shared sidecar result needed to record written, no-response, not-retained,
      and write-failed dispositions.
  detail: docs/implementation-plans/plan-details/roadmap-model-failure-receipts/02-shared-redacted-model-failure-receipt.md
  status: done
- id: 3
  title: Record fresh roadmap stage failures before retry while preserving accepted
    artifact writes
  intent: Keep invoke, parse, and authored-review-row failures diagnosable even when
    a later fresh-stage attempt succeeds.
  files:
  - plan_tool/roadmap.py
  - tests/test_roadmap.py
  complexity: medium
  change_type: feature
  depends_on:
  - 1
  - 2
  depends_on_notes:
    1: Provides best-effort raw-response persistence using the roadmap-owned slug,
      stage, and attempt identifiers.
    2: Provides the redacted receipt shape and its closed sidecar dispositions.
  detail: docs/implementation-plans/plan-details/roadmap-model-failure-receipts/03-record-fresh-roadmap-stage-failures.md
  status: done
- id: 4
  title: Record bounded roadmap feedback failures before retry while preserving accepted
    revision writes
  intent: Preserve durable evidence for rejected bounded-feedback replies, including
    failures followed by a successful retry.
  files:
  - plan_tool/roadmap.py
  - tests/test_roadmap.py
  complexity: medium
  change_type: feature
  depends_on:
  - 1
  - 2
  depends_on_notes:
    1: Provides the shared sidecar writer for reply-bearing pre-gate failures.
    2: Provides the common receipt contract used for retained replies, absent replies,
      gate diagnostics, and sidecar write failures.
  detail: docs/implementation-plans/plan-details/roadmap-model-failure-receipts/04-record-bounded-roadmap-feedback.md
  status: done
- id: 5
  title: Record local feedback revision failures and reply-bearing gate rejections
    while preserving recoverable publication replacement
  intent: Give local --revise-feedback failures the same diagnostic evidence as roadmap
    stage failures, retaining a rejected reply only when no structured gate diagnostic
    exists.
  files:
  - plan_tool/roadmap_revision_run.py
  - tests/test_roadmap_revision_run.py
  complexity: high
  change_type: feature
  depends_on:
  - 1
  - 2
  depends_on_notes:
    1: Provides best-effort raw-response persistence for reply-bearing failures, including
      a local gate rejection that has no structured diagnostic event.
    2: Provides the shared receipt emitted after the sidecar disposition is resolved.
  detail: docs/implementation-plans/plan-details/roadmap-model-failure-receipts/05-record-local-feedback-revision-failures.md
  status: done
- id: 6
  title: Document roadmap failure receipts and record the shipped backlog slice
  intent: Tell operators how to locate rejected replies and mark the roadmap producer
    class complete while retaining later producer migrations.
  files:
  - README.md
  - docs/OPERATIONS.md
  - docs/ARCHITECTURE.md
  - BUG_BACKLOG.md
  - BACKLOG.md
  complexity: medium
  change_type: non-code
  depends_on:
  - 3
  - 4
  - 5
  depends_on_notes:
    3: Delivers the fresh-stage receipt behavior the documentation describes.
    4: Delivers the bounded-feedback receipt behavior the documentation describes.
    5: Delivers the local revision receipt behavior and completes the selected roadmap
      producer class.
  detail: docs/implementation-plans/plan-details/roadmap-model-failure-receipts/06-document-roadmap-failure-receipts.md
  status: done
---
# Roadmap Model Failure Receipts

## Overview

Roadmap model calls expose call duration, byte counts, and failure kinds, but
their diagnostic evidence depends on which loop rejected the response. A
recovered parse failure can be counted without preserving the malformed bytes;
an exhausted local revision can report `operation-rejected` without the parser
reason; and roadmap has no shared sidecar owner with detail. Create separately
mirrors detail's existing helper and remains a later migration. This slice
establishes one receipt contract and applies it across the selected roadmap
stage and revision routes.

## Problem statement

The operator can often identify that a roadmap attempt failed but cannot
determine why from durable state. The Integration evidence recorded in #217 came from
`_run_bounded_stage_feedback`, while #217's former one-call-site proposal named
only `_run_stage`. The same class also includes local feedback revision and the
`authored-review-rows` rejection, neither of which is covered by a parse-only
sink. Patching one branch would leave sibling routes green and still lose the
evidence needed to reproduce the next malformed response.

## Architecture

The shared run-log layer owns one redacted terminal-failure receipt shape. A
producer classifies the failure, attempts any eligible sidecar write, and then
emits the receipt before retrying or returning. The JSONL receipt stores phase,
attempt, safe reason, response byte count and digest, and sidecar disposition;
it never stores response text or copies validation messages. A shared sidecar
leaf owns path construction and best-effort raw-byte persistence using
producer-owned identifiers. Sidecar I/O failure is diagnostic metadata only and
cannot replace the command's outcome.

The sidecar disposition is a closed four-value contract:

| Value | Producer and precedence | Consumer and operator path |
| --- | --- | --- |
| `written` | The shared sidecar owner receives raw response bytes and writes them before receipt emission. | The receipt carries the safe path, byte count, and digest; the operator reads the sidecar. |
| `no-response` | No response bytes exist; this takes precedence over every write state. | The receipt carries zero bytes and no path; the operator uses invocation metadata. |
| `not-retained` | The failure has an owning structured diagnostic, currently a fresh or bounded stage gate rejection, so policy does not request a raw sidecar. | The receipt's phase and attempt correlate it with the existing bounded `gate_violations` event; it carries no sidecar path or copied messages. |
| `write-failed` | Raw bytes exist and policy requests retention, but the best-effort write fails. | The receipt keeps byte count and digest without a path; the original retry or terminal outcome proceeds unchanged. |

For every selected producer, the receipt reason is the producer's existing safe
failure kind or terminal outcome at the point its returned reply is rejected.
Every reply-bearing rejection is sidecar-eligible, including bounded feedback
`invalid_detail` when reply validation or limits reject it and local revision
`operation-rejected`, `merge-rejected`, `candidate-parse-failed`, and
`gate-rejected`. Fresh and bounded stage gate rejection remains `not-retained`
because `gate_violations` supplies its diagnosis. A reply-bearing local revision
gate rejection is sidecar-eligible because its terminal event has only the
closed verdict, not a structured diagnostic. A source-admission failure found
after a reply is returned uses the safe receipt reason
`source-admission-rejected` and is sidecar-eligible across fresh authoring,
bounded feedback, and local revision. Genuinely pre-invocation admission and
publication failures do not reject a returned reply and emit no receipt.
Successful responses emit no terminal-failure receipt.

## Scope guardrails

- Do not put raw response text, prompt text, validation prose, provider
  transcripts, or tool-input summaries in the new terminal-failure receipt.
  Existing bounded `gate_violations` messages remain the structured diagnostic
  for fresh and bounded stage gates; the receipt references them by phase and
  attempt without duplicating them.
- Do not add retention cleanup, a sidecar reader command, successful-response
  persistence, or new retry behavior.
- Do not migrate create, detail, seed materialization, candidate proposal, or
  candidate review in this slice; they remain later migrations under the
  source BUG entry.
- Do not change exception classification, CLI return codes, terminal status
  vocabulary, template-read handling, or interrupt semantics; #339, #344,
  #347, and #348 own those contracts.

## References

- `BUG_BACKLOG.md` — "Model-backed commands do not share one complete terminal
  failure receipt."
- `BACKLOG.md` #217 — roadmap rejected-response evidence and Integration provenance.
- `DATA_CONTRACT.md` — `AttemptFailed`, `GateViolations`, `ParseFailure`, and
  `RoadmapLocalRevisionAttempt` contracts.
- `plan_tool/roadmap.py:_run_stage` and
  `plan_tool/roadmap.py:_run_bounded_stage_feedback` — stage attempt producers.
- `plan_tool/roadmap_revision_run.py:run_local_feedback_revision` — local
  feedback revision producer.
- `plan_tool/detail.py:_log_parse_failure` — existing best-effort sidecar
  behavior to consolidate.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

- The later cross-command producer migrations named by the source BUG entry.
- Persisting fresh or bounded stage gate-rejected responses, or any successful
  raw response. A reply-bearing local revision gate rejection is in scope because
  it has no structured gate diagnostic.
- Changing retry budgets, correction prompts, result outcomes, stdout, or exit
  codes.
- A generic artifact store, retention policy, cleanup command, or diagnostic
  viewer.
- Roadmap publication, checkpoint, writer-journal, or lifecycle recovery.

## Risks

- Raw rejected replies are unbounded diagnostic files and may contain project
  context. Keep them gitignored and preserve the existing best-effort local
  storage posture; retention policy remains separate.
- A receipt emitted before sidecar completion can claim a file that does not
  exist. The ordering fence requires sidecar disposition to be resolved first.
- A shared helper can accidentally normalize producer-specific failure reasons.
  Preserve each producer's reason and result vocabulary; standardize the
  evidence envelope, not the command outcome.
- Retrofitting only the originally cited parse branch would recreate the defect
  class. The producer inventory is an explicit pre-edit deliverable.

## Testing

Use a producer/rejection matrix over fresh authoring, bounded feedback, and
local revision. Prove that every reply-bearing pre-gate rejection emits one
redacted receipt per attempt, including a failed attempt followed by success;
  that `authored-review-rows` and reply-bearing bounded `invalid_detail` follow
  the settled sidecar policy; that fresh and bounded stage gate rejections use
  the existing bounded `gate_violations` event without a raw sidecar or copied
  messages; that local `operation-rejected`,
  `merge-rejected`, `candidate-parse-failed`, and reply-bearing `gate-rejected`
  are retained; that post-reply source admission uses
  `source-admission-rejected` and is retained across all three producers; and
  that pre-invocation admission, publication, and success outcomes emit no
  receipt. Prove all four sidecar dispositions and show that a write failure
  leaves retries, results, stdout, and exit codes unchanged.

At the bare-plan gate, retain the shared receipt property, complete producer
set, disposition table, and ordering fence without prescribing fixture-level
mechanics. At the detail-grounded gate, require focused coverage for every
producer/disposition pairing and the no-raw-JSONL invariant.

## Acceptance criteria

- Fresh stage authoring, bounded stage feedback, and local feedback revision
  all emit the same redacted terminal-failure receipt contract.
- A recovered failed attempt remains diagnosable even though the command later
  succeeds.
- Every reply-bearing selected-producer rejection uses its existing safe outcome
  as the receipt reason and follows the explicit sidecar policy; fresh and bounded
  stage gates correlate to existing structured evidence without raw-response or
  validation-message duplication; and post-reply source admission uses
  `source-admission-rejected` with a receipt and sidecar, while local rejection
  outcomes remain diagnosable through their receipt and sidecar.
- Receipt emission follows sidecar disposition resolution, and sidecar failure
  cannot change the real command outcome.
- No raw response or prompt content enters JSONL.
- `DATA_CONTRACT.md` and operator documentation describe the receipt and
  sidecar lookup contract.
- `BACKLOG.md` #217 records the shipped consolidation, while the source BUG
  entry records this slice complete and retains the later migrations.

## Deferred

The source BUG entry retains migrations for create, detail, roadmap seed
materialization, candidate proposal, and candidate review. BACKLOG #339, #344,
#347, and #348 retain interrupt, exception-classification, template-read,
return-code, and terminal-status work.
