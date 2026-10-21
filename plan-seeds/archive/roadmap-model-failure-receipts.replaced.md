> **Replaced**: this file has been superseded by `docs/implementation-plans/2-roadmap-model-failure-receipts.md`.
> Preserved here for history; do not edit.

# Seed: roadmap model-failure receipts

Source: `BUG_BACKLOG.md` — "Model-backed commands do not share one complete
terminal failure receipt" — first implementation slice, plus `BACKLOG.md`
#217. The resulting plan updates both source entries when this slice ships;
it does not remove the BUG entry while later producer migrations remain.

## Outcome

Every rejected model response in fresh roadmap stage authoring, bounded stage
feedback, and local feedback revision leaves one dependable, redacted terminal
receipt, including recovered attempts, and records whether its raw response is
available in a best-effort sidecar.

## In scope

- Define the shared redacted receipt and raw-response sidecar contract before
  migrating the selected producers.
- Cover fresh stage authoring, bounded stage feedback, and local
  `--revise-feedback` as one complete producer class.
- Retain raw responses for every reply-bearing rejection before gates,
  including `authored-review-rows`; retain structured gate diagnostics instead
  of duplicating gate-rejected raw artifacts.
- Reconcile the existing detail parse-failure helper and roadmap #217 work into
  one shared sidecar owner without requiring a producer to invent a plan path.
- Update the run-log data contract, operator documentation, and the two source
  backlog records when the slice ships.

## Overview

Roadmap model calls expose call duration, byte counts, and failure kinds, but
their diagnostic evidence depends on which loop rejected the response. A
recovered parse failure can be counted without preserving the malformed bytes;
an exhausted local revision can report `operation-rejected` without the parser
reason; and sidecar capture is currently a detail-specific convention. This
slice establishes one receipt contract and applies it across the selected
roadmap stage and revision routes.

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
it never stores response text. A shared sidecar leaf owns path construction and
best-effort raw-byte persistence using producer-owned identifiers. Sidecar I/O
failure is diagnostic metadata only and cannot replace the command's outcome.

The sidecar disposition is a closed four-value contract:

| Value | Producer and precedence | Consumer and operator path |
| --- | --- | --- |
| `written` | The shared sidecar owner receives raw response bytes and writes them before receipt emission. | The receipt carries the safe path, byte count, and digest; the operator reads the sidecar. |
| `no-response` | No response bytes exist; this takes precedence over every write state. | The receipt carries zero bytes and no path; the operator uses invocation metadata. |
| `not-retained` | The failure has an owning structured diagnostic, currently a gate rejection, so policy does not request a raw sidecar. | The receipt points the operator to the structured diagnostic and carries no sidecar path. |
| `write-failed` | Raw bytes exist and policy requests retention, but the best-effort write fails. | The receipt keeps byte count and digest without a path; the original retry or terminal outcome proceeds unchanged. |

`invoke`, `parse`, and `authored-review-rows` are sidecar-eligible whenever raw
bytes exist. Gate rejection remains `not-retained` because `gate_violations`
and the parsed candidate supply its diagnosis. Successful responses emit no
terminal-failure receipt.

## Scope guardrails

- Do not put raw response text, prompt text, validation prose, provider
  transcripts, or tool-input summaries in JSONL.
- Do not add retention cleanup, a sidecar reader command, successful-response
  persistence, or new retry behavior.
- Do not migrate create, detail, seed materialization, candidate proposal, or
  candidate review in this slice; they remain later migrations under the
  source BUG entry.
- Do not change exception classification, CLI return codes, terminal status
  vocabulary, template-read handling, or interrupt semantics; #339, #344,
  #347, and #348 own those contracts.

## Out of scope

- The later cross-command producer migrations named by the source BUG entry.
- Persisting gate-rejected or successful raw responses.
- Changing retry budgets, correction prompts, result outcomes, stdout, or exit
  codes.
- A generic artifact store, retention policy, cleanup command, or diagnostic
  viewer.
- Roadmap publication, checkpoint, writer-journal, or lifecycle recovery.

## Allowed behavior changes

Rejected reply bytes may appear under the existing gitignored diagnostic state
area, and run logs gain the shared redacted receipt fields or event required by
the contract. No command outcome, retry decision, stdout, or exit code changes.

## Allowed reorganization

Move the detail-specific parse-failure writer into a cycle-free shared leaf and
adapt its existing caller only as required to establish one sidecar owner. Do
not reorganize the model-call loops or merge their distinct retry policies.

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
that `authored-review-rows` follows the settled sidecar policy; that gate
rejections use structured diagnostics without a raw sidecar; and that success
emits no failure receipt. Prove all four sidecar dispositions and show that a
write failure leaves retries, results, stdout, and exit codes unchanged.

At the bare-plan gate, retain the shared receipt property, complete producer
set, disposition table, and ordering fence without prescribing fixture-level
mechanics. At the detail-grounded gate, require focused coverage for every
producer/disposition pairing and the no-raw-JSONL invariant.

## Acceptance criteria

- Fresh stage authoring, bounded stage feedback, and local feedback revision
  all emit the same redacted terminal-failure receipt contract.
- A recovered failed attempt remains diagnosable even though the command later
  succeeds.
- Reply-bearing `invoke`, `parse`, `authored-review-rows`, and local revision
  rejection outcomes follow the explicit sidecar policy; gates retain their
  structured evidence without raw-response duplication.
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
