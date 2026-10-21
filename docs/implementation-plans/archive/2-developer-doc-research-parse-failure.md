> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

---
title: Developer Doc Research Parse Failure
intent: Keep create trustworthy and resumable by preventing malformed developer-document
  research from silently passing as a valid absence.
status: completed
priority: medium
risk_profile: standard
risk_profile_rationale: Risk declaration uses standard because --yes does not accept
  model risk proposals.
test_command: uv run pytest tests/ -q -n auto
enforce_step_tests: true
source_seed: plan-seeds/developer-doc-research-parse-failure.md
steps:
- id: 1
  title: Use typed generic reference-research results without changing checkpoint,
    plan, or References replacements
  intent: The research phase carries deliberate emptiness separately from a response
    it could not understand.
  files:
  - plan_tool/create.py
  - tests/test_create.py
  complexity: medium
  change_type: refactor
  detail: docs/implementation-plans/plan-details/developer-doc-research-parse-failure/01-use-typed-generic-reference-research.md
  status: done
- id: 2
  title: Retry malformed reference research once with attempt provenance and preserve
    parseable-only checkpoint replacement and existing discard behavior
  intent: A transient formatting mistake gets one bounded chance to recover, recorded
    as attempts one and two with parse-rejection evidence, without hiding a malformed
    reply when repair succeeds or fails.
  files:
  - plan_tool/create.py
  - tests/test_create.py
  complexity: medium
  change_type: feature
  depends_on:
  - 1
  depends_on_notes:
    1: The typed handoff distinguishes a repaired populated or empty result from a
      twice-malformed result.
  detail: docs/implementation-plans/plan-details/developer-doc-research-parse-failure/02-retry-malformed-reference-research-once.md
  status: done
- id: 3
  title: Fail initial malformed research through complete create before plan replacement
    or manifest mutation, while keeping valid empty non-failing
  intent: An initial create never turns failed developer-doc research into an apparently
    valid plan.
  files:
  - plan_tool/create.py
  - tests/test_create.py
  - tests/test_bench.py
  complexity: medium
  change_type: feature
  depends_on:
  - 2
  depends_on_notes:
    2: The bounded research phase supplies a final unparseable outcome only after
      its single repair attempt.
  detail: docs/implementation-plans/plan-details/developer-doc-research-parse-failure/03-fail-initial-malformed-research-through.md
  status: done
- id: 4
  title: Stage malformed iteration research before step or References writes and record
    its outcome, while keeping valid empty non-failing
  intent: A failed reference refresh stays visible in the run log without making a
    new proposal-side step or References write after the iteration's existing applies.
  files:
  - plan_tool/create.py
  - tests/test_create.py
  - tests/cli/test_authoring_cmds.py
  complexity: medium
  change_type: feature
  depends_on:
  - 2
  depends_on_notes:
    2: The bounded research phase supplies the terminal unparseable result that the
      convergence loop must surface.
  detail: docs/implementation-plans/plan-details/developer-doc-research-parse-failure/04-stage-malformed-iteration-research.md
  status: done
---
# Developer Doc Research Parse Failure

## Overview

Generic developer-document research will return a typed outcome that distinguishes populated references, a valid empty list, and an unparseable model reply. Every malformed reply will remain durably visible as a `parse` attempt failure, even when the single bounded repair succeeds. `create` will visibly fail the affected authoring phase if the repair is also unparseable. Valid-empty behavior, `Reference` validation, parseable-response checkpointing, and resumable recovery remain unchanged.

## Problem statement

`plan_tool/create.py:propose_references_from_claude` currently returns `None` for an unparseable reply and `[]` for a valid empty reply. The initial and iterative callers treat both values as false, so failed research can be recorded as `skipped` and processed as an intentional absence of references. This hides a failed authoring phase from the run log and can allow initial creation to continue into dependent work or make an iteration appear to have completed without a reference update.

## Architecture

Introduce one small typed result in `plan_tool/create.py` for generic developer-document research. Its closed outcome vocabulary distinguishes populated references, a valid empty list, and an unparseable response while preserving the payload and validation owned by `plan_tool/create.py:Reference`. `plan_tool/create.py:propose_references_from_claude` returns this result without introducing a flag, a reusable retry framework, or a generalized phase-result abstraction.

After the first unparseable response, `plan_tool/create.py:propose_references_from_claude` records an `attempt_failed` event with failure kind `parse` and attempt one, then makes exactly one repair request that restates the JSON-array contract and includes the rejected response. The existing progress and run-log seams record the repair request as attempt two. A parseable repair continues normally while retaining that first rejected-attempt event; a second malformed response records the same `parse` event for attempt two and produces a bounded diagnostic through the existing create failure convention. Only parseable responses qualify for a successful references checkpoint.

At `plan_tool/create.py:_prepare_create_plan`, the unparseable outcome ends `propose_references` with `error` and raises `plan_tool/create.py:CreateError` before reference fetching or body synthesis. That error propagates through `plan_tool/create.py:create_plan`, which returns before its plan-publication and manifest-mutation boundary. Its diagnostic names terminal developer-document reference research and directs the operator to retry the original `plan-tool create …` command; existing earlier checkpoints remain resumable. CLI-facing error presentation continues through the existing `plan_tool/style.py:error` boundary.

At `plan_tool/create.py:_converge_create_plan`, the existing deterministic `apply_finding` phase retains its current behavior before generic-reference refresh. The refresh then starts and ends its own `propose_references` run-log phase and obtains the typed outcome before it proposes or writes the round's steps. A terminal unparseable outcome records `error`, enters the existing explicit iteration-stage failure path, and makes no new proposal-side step or References write, preserving the post-apply plan state. A parseable outcome then permits step re-proposal; a populated reference result can still patch References when that independent step re-proposal fails. A valid `[]` records the normal `skipped` no-output outcome: initial creation may retain the TODO References placeholder, while iteration preserves the published References block. The terminal failure detail propagates through `CreateResult.iteration_stage_failure`.

The CLI authoring seam represented by `tests/cli/test_authoring_cmds.py:create` remains compatible with the resulting `CreateResult`: a published plan with an iteration-stage failure remains a registered, resumable `create` result and exits `0`, while its FAILURE presentation and run-log outcome make the incomplete iteration visible. Focused tests verify that the new research outcome reaches the existing initial and iterative boundaries without changing unrelated CLI creation behavior.

## Input

This plan consumes the existing generic reference-research contract in `plan_tool/create.py`. `plan_tool/create.py:propose_references_from_claude` currently represents an unparseable reply as `None`, a valid empty reply as `[]`, and populated research as `list[Reference]`; `plan_tool/create.py:Reference` owns the existing payload shape. The plan also relies on parseable-only checkpointing, `plan_tool/create.py:_prepare_create_plan` and `plan_tool/create.py:_converge_create_plan` as the two research caller boundaries, `plan_tool/create.py:create_plan` as the initial publication boundary, `plan_tool/create.py:CreateError` for controlled initial failure, and the existing iteration-stage failure path. The full repository confirms that `CreateResult.iteration_stage_failure` preserves the published plan and reports `iteration_incomplete` while `cmd_create` returns `0`; this plan retains that CLI contract.

## References

- [json — JSON encoder and decoderhttps: — Documents JSON parsing, top-level value handling, and JSONDecodeError diagnostics needed to distinguish valid empty arrays from malformed replies.
- [dataclasses — Data Classeshttps: — Covers frozen data classes and typed fields suitable for the closed reference-research result.
- [typing — Support for type hintshttps: — Defines Literal, unions, aliases, and other annotations useful for expressing distinct populated, empty, and unparseable outcomes.
- [Increase output consistencyhttps: — Explains how to specify exact JSON response formats when constructing the initial and corrective Claude prompts.
- [pytest API Referencehttps: — Documents raises, MonkeyPatch, temporary-path fixtures, and capture helpers needed for hermetic failure-boundary and side-effect tests.
- [RFC 8259: The JavaScript Object Notation (JSON) Data Interchange Formathttps: — Defines the authoritative JSON grammar and array semantics underlying the model-response contract.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

- Roadmap-specific reference research, because it has a separate validated result contract.
- Reference retrieval, reference-document fetching, body-synthesis content, and valid-empty behavior, which retain their existing contracts.
- More than one repair retry, new CLI flags, or generalized phase-result machinery; recovery remains bounded and local to generic developer-document research.

## Risks

- A valid empty array could be treated as a failure. Severity: not specified in the seed. Mitigation: pin the valid-empty initial and iteration paths with tests. Unresolved gap: severity requires review.
- An iteration error after publication could destructively replace a plan state reached by the existing apply phase. Severity: not specified in the seed. Mitigation: stage terminal reference research before proposal-side step or References writes, snapshot the post-apply state, and prove that both sections remain unchanged from that boundary. Unresolved gap: severity requires review.
- The run-log outcome could collapse back to `skipped`, hiding a terminal parse failure from `runs show`. Severity: not specified in the seed. Mitigation: assert iteration `error` for malformed research, `skipped` for valid-empty research, and `ok` for populated research. Unresolved gap: severity requires review.
- Malformed output could be retried indefinitely or lose its provenance, increasing model cost without increasing trust. Severity: not specified in the seed. Mitigation: assert exactly two calls, `attempt_failed(parse)` for every rejected attempt, and call provenance one and two on the repair path. Unresolved gap: severity requires review.

## Testing

Add hermetic unit coverage in `tests/test_create.py` for the three typed outcomes and both caller boundaries. Extend `TestProposeReferencesFromClaude` with populated, valid-empty, repaired, and twice-malformed replies. Verify that the repair prompt includes the rejected response and the JSON-array correction, the repair path makes exactly two calls, every malformed reply emits `attempt_failed(parse)` with its own attempt number, its run-log calls are attempts one and two, and a second parse failure leaves a bounded diagnostic without a successful references checkpoint.

Use `TestReferencesRenderedIntoBody` to preserve valid-empty initial rendering and the existing References block during iteration. Cover `_prepare_create_plan` to prove that a final unparseable outcome raises `CreateError` with terminal-reference-research retry guidance before dependent fetching and body synthesis; separately cover `create_plan` end to end to prove that the error reaches the initial publication boundary without a plan or manifest write. Cover `_converge_create_plan` to snapshot the post-apply plan state, then prove that terminal malformed reference research occurs before any proposal-side step or References write, surfaces through `CreateResult.iteration_stage_failure`, and retains both sections from that boundary. Assert the failure banner at that emitter names reference research and the established exit-0, resumable-plan contract; keep the mocked CLI test focused on `0` and completed-create handling. Retain the existing valid-reference update when step re-proposal fails. Extend the create run-log fixtures in `tests/test_create.py` to assert iteration `error` for malformed research and `skipped` for valid-empty research. Preserve the CLI's `0` exit for a published-but-incomplete iteration in `tests/cli/test_authoring_cmds.py`, and remove any stale test wording that describes this path as non-zero.

The existing `tests/test_create.py::TestProposeReferencesFromClaude`, `tests/test_create.py::TestReferencesRenderedIntoBody`, and create run-log fixture coverage must continue to pass.

**Per-step test strategy** (derived from each step's `change_type`):

- step 1 (refactor) — tests covering the behavior this step changes; green before completion.
- step 2 (feature) — tests covering the behavior this step changes; green before completion.
- step 3 (feature) — tests covering the behavior this step changes; green before completion.
- step 4 (feature) — tests covering the behavior this step changes; green before completion.

## Acceptance criteria

- Generic developer-document research exposes distinct populated, valid-empty, and unparseable outcomes without changing `Reference` validation.
- A first malformed reply emits `attempt_failed(parse)` for attempt one and receives exactly one repair request containing the rejected response and the JSON-array correction; the run log records attempts one and two, while a second malformed reply emits the same event for attempt two, leaves a bounded parse-failure diagnostic, and creates no successful references checkpoint.
- An initial research phase that remains unparseable exits through `CreateError` that names terminal developer-document reference research and directs retry of the original `plan-tool create …` command, logs `propose_references` as `error`, does not run dependent reference fetching or body synthesis, and causes complete `create_plan` to write neither the plan nor the manifest.
- An iteration research phase that remains unparseable records `propose_references` as `error`, surfaces the existing failure through `CreateResult.iteration_stage_failure`, keeps the CLI exit at `0` for the published resumable plan, and leaves the post-apply plan's steps and References section unchanged without making a new proposal-side write.
- A valid `[]` reply remains non-failing and preserves its documented initial and iteration behavior.
- A valid iteration reference result remains publishable when independent step re-proposal fails, while a valid-empty iteration records `propose_references` as `skipped` and preserves the References section.
- Focused tests in `tests/test_create.py` cover the result contract, initial complete-operation no-write boundary, iteration preservation boundary, repair-attempt provenance, and run-log outcomes.

## Deferred

- None. This plan postpones no implementation work; permanent exclusions remain in
  Out of scope.
