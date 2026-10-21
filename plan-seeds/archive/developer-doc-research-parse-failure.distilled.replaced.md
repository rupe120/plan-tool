> **Replaced**: this file has been superseded by `docs/implementation-plans/2-developer-doc-research-parse-failure.md`.
> Preserved here for history; do not edit.

## Overview

Generic developer-document research will return a typed outcome that distinguishes populated references, a valid empty list, and an unparseable model reply. `create` will make one bounded repair request after malformed output, then fail the affected authoring phase visibly if the repair is also unparseable. Valid-empty behavior, `Reference` validation, parseable-response checkpointing, and the existing resumable recovery path remain unchanged.

## Problem statement

`propose_references_from_claude` returns `None` for an unparseable reply and an empty list for a valid `[]` reply. `_prepare_create_plan` currently treats both as false, records `propose_references` as `skipped`, converts the value to `[]`, and may continue through reference fetching and body synthesis, so the run log cannot distinguish deliberate absence from failed research. `_converge_create_plan` has the same ambiguity and can present a failed reference refresh as an ordinary absent update instead of a failed authoring stage.

## Architecture

Introduce one small typed result in `plan_tool/create.py` for generic developer-doc research. Its closed outcome vocabulary distinguishes populated references, a valid empty list, and an unparseable response while preserving the existing `Reference` payload and the rule that only parseable responses are checkpointed.

After the first unparseable response, `propose_references_from_claude` makes exactly one repair request that states the JSON-array contract and includes the rejected response. The retry is recorded as attempt two through the current progress and run-log seams. A parseable repair continues normally; a second malformed response produces a bounded diagnostic through the existing create failure-artifact convention and returns the typed unparseable outcome. This adds neither a flag, an unbounded loop, nor a general retry framework.

At `_prepare_create_plan`, an unparseable outcome ends `propose_references` with an error and raises a controlled `CreateError` before reference fetching, body-section synthesis, plan publication, or manifest mutation. The error identifies the failed research phase and directs the operator to retry `create`; existing initial-step checkpoints remain available, but the malformed reference payload is not stored as a successful checkpoint.

At `_converge_create_plan`, an unparseable outcome enters the existing explicit iteration-stage failure path. The round leaves the published plan’s steps and References body unchanged, records `error` rather than `skipped`, and propagates the failed-stage detail through `CreateResult.iteration_stage_failure` while the published, resumable plan retains the CLI’s existing zero exit.

A valid `[]` remains a normal skipped/no-output result. An initial plan may render its TODO References placeholder, while an iteration preserves the already-published References block.

## Out of scope

- Roadmap-specific reference research, because it has a separate validated result contract.
- Changes to reference retrieval, reference-document fetching, body-synthesis content, or valid-empty behavior; those existing behaviors remain unchanged.
- More than one repair retry, new CLI flags, or generalized phase-result machinery; recovery stays bounded and local to this research phase.

## Risks

- A valid empty array could be treated as a failure. Severity: not specified in the seed. Mitigation: pin the valid-empty path with tests.
- An iteration error after publication could destructively replace the round’s prior body. Severity: not specified in the seed. Mitigation: prove that the original References block and steps survive.
- The run-log outcome could collapse back to `skipped`, hiding the failure from `runs show`. Severity: not specified in the seed. Mitigation: assert `error` for malformed research and the existing normal outcome for valid-empty research.
- Malformed output could be retried indefinitely, increasing model cost without increasing trust. Severity: not specified in the seed. Mitigation: assert exactly two calls on the repair path.

## Testing

Add hermetic coverage in `tests/test_create.py` for all three typed outcomes and both caller boundaries. Extend `TestProposeReferencesFromClaude` to cover populated, valid-empty, repaired, and twice-malformed replies; verify that the repair request includes the rejected response and JSON-array correction, the repair path makes exactly two calls, and a second parse failure leaves a bounded diagnostic without a successful references checkpoint.

Use `TestReferencesRenderedIntoBody` to preserve the valid-empty initial behavior and the existing References block during iteration. Cover `_prepare_create_plan` to prove a final unparseable outcome raises `CreateError` before dependent fetch, body synthesis, plan publication, or manifest mutation. Cover `_converge_create_plan` to prove the existing iteration-stage failure is surfaced through `CreateResult.iteration_stage_failure` while the published steps and References section remain unchanged. Extend the create run-log fixtures to assert `error` for malformed research and the existing normal outcome for valid-empty research. The existing `TestProposeReferencesFromClaude`, `TestReferencesRenderedIntoBody`, and create run-log fixture coverage must continue to pass.

## Acceptance criteria

- Generic developer-doc research exposes distinct populated, valid-empty, and unparseable outcomes without changing `Reference` validation.
- A first malformed reply receives exactly one repair request containing the rejected response and the JSON-array correction; a second malformed reply leaves a bounded parse-failure diagnostic and no successful references checkpoint.
- An initial research phase that remains unparseable exits through `CreateError`, logs `propose_references` as an error, does not run dependent reference fetching or body synthesis, and writes neither plan nor manifest.
- An iteration research phase that remains unparseable surfaces the existing iteration-stage failure through `CreateResult.iteration_stage_failure` and leaves the published plan’s steps and References section unchanged.
- A valid `[]` reply remains non-failing and preserves its documented initial and iteration behavior.
- Focused tests in `tests/test_create.py` cover the result contract, initial no-write error boundary, iteration preservation boundary, and run-log outcomes.

## Input

This plan consumes the existing generic reference-research contracts in `plan_tool/create.py`: `propose_references_from_claude` currently distinguishes an unparseable reply as `None` from a valid empty reply as `[]`; `_prepare_create_plan` and `_converge_create_plan` are its two caller boundaries; and the existing `Reference` payload validation, parseable-only checkpoint rule, create failure-artifact convention, `propose_references` run-log phase, controlled `CreateError`, and `CreateResult.iteration_stage_failure` path remain authoritative. The cited verification surface is `tests/test_create.py`, specifically `TestProposeReferencesFromClaude`, `TestReferencesRenderedIntoBody`, and the create run-log fixtures; this distillation does not independently verify those contracts against the codebase.
