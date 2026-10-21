> **Replaced**: this file has been superseded by `docs/implementation-plans/2-roadmap-candidate-vocabulary-retry.md`.
> Preserved here for history; do not edit.

## Outcome

Ledger-backed roadmap feedback that adds a Domain entity can produce an inert structural candidate and reach its approval gate; a malformed model reply receives bounded correction and leaves no candidate published when attempts are exhausted.

## Overview

Source: BUG_BACKLOG "Structural candidate generation can emit internal row-class names that its validator rejects"; Jira IPPT-10. The candidate batch exposes internal row class names such as `EntityRow` in its immutable context while the typed delta accepts artifact collection names such as `entities`. The prompt says to use collection names but does not give the mapping. The batch path makes one model call and rejects a malformed reply immediately.

## Problem statement

The 2026-09-25 Integration proposal returned `candidate proposal: response-rejected` for `candidate row type 'EntityRow' is not allowed`. Existing fixtures already emit `entities`; they miss the model-facing mismatch. A valid correction must preserve receipt, digest, authority, and replay identity for previously persisted candidate context.

## Architecture

Present the closed internal-class-to-collection vocabulary in the model-facing prompt or rendered view, without changing the issued capsule, receipt, stored `row_type`, or strict delta parser. Add a bounded correction attempt sequence to the ledger-batch proposal path for parse and candidate-materialization rejections. Failed transport and storage remain their existing failure classes. Each attempt keeps redacted telemetry and the existing response receipt semantics, with an exact terminal result and call count. Reuse the same immutable batch and receipt across attempts; a valid reply stores through the existing publication boundary.

## In scope

The candidate prompt/context rendering, ledger-batch attempt lifecycle, its run-log diagnostics, and focused tests for proposal, receipt identity, and replay.

## Out of scope

Persisted evidence-contract migration, wholesale replacement of stored `row_type` values, permissive parsing or silent normalization of class names, selector-era proposal behavior, and changes to accepted-head publication or structural approval decisions.

## Scope guardrails

The binary observable is that an ordinary ledger request to add a Domain entity reaches a stored structural candidate when the model uses `entities`, while malformed `EntityRow` replies exhaust a finite correction budget without candidate publication. The model-facing mapping cannot change capsule payload bytes, receipt/digest identities, authority, or replay keys. Correction cannot turn a transport or storage failure into a rejected model response.

## Risks

A mapping that rewrites issued context would invalidate stored evidence. A retry around storage could repeat a write. A correction prompt that echoes response content into ordinary telemetry could leak model output. Keep each boundary explicit.

## Testing

Exercise an ordinary ledger batch that adds a Domain entity through the real prompt and storage path; prove the response reaches the structural decision gate. Exercise an `EntityRow` response followed by correction and exhaustion, checking prompt, bounded attempt count, redacted telemetry, exact response receipts, and no candidate publication. Replay stored context before and after the rendering change to prove byte and identity stability.

## Acceptance criteria

- The model sees the valid collection token for every class name exposed by the batch context, including `EntityRow` to `entities`.
- A valid Domain entity operation stores an inert structural candidate and can enter the structural approve/edit/reject decision route.
- A malformed class-name operation triggers a named, bounded correction attempt; exhaustion reports the exact failure and publishes no candidate.
- Existing persisted capsule, receipt, digest, and replay identity remain unchanged; strict parsing still rejects class names.
- The originating `BUG_BACKLOG.md` promotion stub is removed only after the implementation and tests ship; Jira IPPT-10 remains the work record during execution.

## Deferred

Any migration of stored row-type vocabulary is separate versioned work.

## Stop / defer

Stop for an explicit design decision if the observable outcome cannot be delivered without changing stored evidence identity or the accepted-head publication boundary. File unrelated discoveries in the appropriate backlog.

## References

- `ROADMAP_FEEDBACK_FORMAT.md` — ledger-to-candidate and approval lifecycle.
- `ROADMAP_FORMAT.md` — immutable artifact and structural route contract.
- `plan_tool/roadmap_candidate_context.py:_row_identity`, `_render_batch_payload`, `_row_digest` — current persisted vocabulary and payload identity.
- `plan_tool/roadmap_candidate.py:parse_candidate_delta`, `_ROW_TYPE_NAMES` — accepted operation vocabulary.
- `plan_tool/roadmap_candidate_run.py:render_candidate_delta_prompt`, `_run_batch_candidate_proposal` — model-facing prompt and current batch invocation.
- `plan_tool/prompts/roadmap-candidate-delta.md` — closed model response contract.
- `tests/test_roadmap_candidate_run.py` — focused batch proposal and telemetry coverage.
