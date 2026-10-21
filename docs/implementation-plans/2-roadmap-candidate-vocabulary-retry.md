---
format_version: 1
title: Roadmap Candidate Vocabulary Retry
intent: Ledger-backed roadmap feedback that adds a Domain entity can produce an inert
  structural candidate and reach its approval gate; a malformed model reply receives
  bounded correction and leaves no candidate published when attempts are exhausted.
status: planning
priority: medium
risk_profile: standard
risk_profile_rationale: Risk declaration uses standard because --yes does not accept
  model risk proposals.
test_command: uv run pytest tests/ -q -n auto
enforce_step_tests: true
source_seed: plan-seeds/roadmap-candidate-vocabulary-retry.md
steps:
- id: 1
  title: Show valid collection names and disambiguate existing batch rows
  intent: A model adding a Domain entity can choose `entities` when the issued context
    names `EntityRow`, and can distinguish the two collections containing `PatternRow`.
  files:
  - plan_tool/roadmap_candidate_context.py
  - plan_tool/roadmap_candidate_run.py
  - plan_tool/roadmap_candidate_review.py
  - plan_tool/prompts/roadmap-candidate-delta.md
  - tests/test_roadmap_candidate_run.py
  - tests/test_roadmap_candidate_review.py
  complexity: low
  change_type: feature
  detail: docs/implementation-plans/plan-details/roadmap-candidate-vocabulary-retry/01-show-valid-collection-names.md
  status: current
- id: 2
  title: Retry rejected ledger replies once; preserve one candidate publication, guarded
    pointer and ledger replacements, and exact response receipts
  intent: Malformed replies get a chance to correct themselves, and exhaustion leaves
    no candidate published.
  files:
  - plan_tool/roadmap_candidate_run.py
  - tests/test_roadmap_candidate_run.py
  complexity: high
  change_type: feature
  depends_on:
  - 1
  depends_on_notes:
    1: The first prompt gives both attempts valid row vocabulary and exact existing-row
      collection hints.
  detail: docs/implementation-plans/plan-details/roadmap-candidate-vocabulary-retry/02-retry-rejected-ledger-replies-once.md
- id: 3
  title: Remove the IPPT-10 promotion stub after the behavior and tests ship
  intent: The backlog stops advertising work completed under IPPT-10.
  files:
  - BUG_BACKLOG.md
  complexity: low
  change_type: non-code
  depends_on:
  - 2
  detail: docs/implementation-plans/plan-details/roadmap-candidate-vocabulary-retry/03-remove-ippt-10-promotion-stub-after.md
---
# Roadmap Candidate Vocabulary Retry

## Overview

Source: BUG_BACKLOG "Structural candidate generation can emit internal row-class names that its validator rejects"; Jira IPPT-10. The candidate batch exposes internal row class names such as `EntityRow` in its immutable context while the typed delta accepts artifact collection names such as `entities`. The prompt says to use collection names but does not give the mapping. The batch path makes one model call and rejects a malformed reply immediately.

## Problem statement

The 2026-09-25 Integration proposal returned `candidate proposal: response-rejected` for `candidate row type 'EntityRow' is not allowed`. Existing fixtures already emit `entities`; they miss the model-facing mismatch. A valid correction must preserve receipt, digest, authority, and replay identity for previously persisted candidate context.

## Architecture

Present the closed internal-class-to-collection vocabulary in the model-facing prompt or rendered view, without changing the issued capsule, receipt, stored `row_type`, or strict delta parser. `PatternRow` has two valid collections, `system_patterns` and `component_patterns`. Before each batch model call, including stored-candidate review and structural edit calls, resolve the immutable source version named by the issued receipt, inspect its typed collection membership, and check each hinted row against the capsule's artifact, class, row id, and row digest. Render a separate syntax hint for each existing row; refuse before invocation if the source binding or membership cannot be proved. Hints do not enter the capsule or grant edit authority. Add one correction opportunity after a parse or candidate-materialization rejection: at most two total model calls for a ledger batch. Failed transport and storage remain their existing failure classes. Record the rejected reply's exact response receipt and redacted attempt event before invoking correction; record the second rejection the same way on exhaustion. The terminal summary names the last rejection and call count 2, while both attempt records remain inspectable, without a duplicate final receipt. Receipt capture stays best-effort under the existing contract. Reuse the same immutable batch and receipt across attempts; a valid reply stores through the existing publication boundary.

## Scope guardrails

The binary observable is that an ordinary ledger request to add a Domain entity reaches a stored structural candidate when the model uses `entities`, while malformed `EntityRow` replies exhaust two total model calls without candidate publication. For every existing row reference, the model-facing hint identifies the actual collection, including either `system_patterns` or `component_patterns` for `PatternRow`; both collection names remain available for a new pattern. The hint cannot change capsule payload bytes, receipt/digest identities, authority, or replay keys. Correction cannot turn a transport or storage failure into a rejected model response.

## References

- `ROADMAP_FEEDBACK_FORMAT.md` — ledger-to-candidate and approval lifecycle.
- `ROADMAP_FORMAT.md` — immutable artifact and structural route contract.
- `plan_tool/roadmap_candidate_context.py:_row_identity`, `_render_batch_payload`, `_row_digest` — current persisted vocabulary and payload identity.
- `plan_tool/roadmap_candidate.py:parse_candidate_delta`, `_ROW_TYPE_NAMES` — accepted operation vocabulary.
- `plan_tool/roadmap_candidate_run.py:render_candidate_delta_prompt`, `_run_batch_candidate_proposal` — model-facing prompt and current batch invocation.
- `plan_tool/prompts/roadmap-candidate-delta.md` — closed model response contract.
- `tests/test_roadmap_candidate_run.py` — focused batch proposal and telemetry coverage.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

Persisted evidence-contract migration, wholesale replacement of stored `row_type` values, permissive parsing or silent normalization of class names, selector-era proposal behavior, and changes to accepted-head publication or structural approval decisions.

## Risks

A mapping that rewrites issued context would invalidate stored evidence. A hint computed from the wrong source could misidentify a pattern collection. A retry around storage could repeat a write. A correction prompt that echoes response content into ordinary telemetry could leak model output. Keep each boundary explicit.

## Testing

Exercise an ordinary ledger batch that adds a Domain entity through the real prompt and storage path; prove the response reaches the structural decision gate. Include both kinds of `PatternRow` in source context and verify each exact existing-row hint, including a replayed batch and a source-binding mismatch that refuses before invocation. Exercise an `EntityRow` response followed by correction and exhaustion, checking the second prompt, two-call limit, redacted telemetry, one response receipt per rejected attempt, terminal summary, and no candidate publication. Replay stored context before and after the rendering change to prove byte and identity stability.

## Acceptance criteria

- The model sees the valid collection token for every class name exposed by the batch context, including `EntityRow` to `entities`; each existing `PatternRow` is identified as either `system_patterns` or `component_patterns` according to its source collection.
- A valid Domain entity operation stores an inert structural candidate and can enter the structural approve/edit/reject decision route.
- A malformed class-name operation triggers one named correction attempt; each rejected reply has one exact response receipt and redacted attempt record before another call, and exhaustion after two total calls reports `response-rejected` with call count 2 and publishes no candidate.
- Existing persisted capsule, receipt, digest, and replay identity remain unchanged; strict parsing still rejects class names.
- The originating `BUG_BACKLOG.md` promotion stub is removed only after the implementation and tests ship; Jira IPPT-10 remains the work record during execution.

## Deferred

Any migration of stored row-type vocabulary is separate versioned work.
