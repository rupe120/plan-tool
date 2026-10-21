> **Replaced**: this file has been superseded by `docs/implementation-plans/2-developer-doc-research-parse-failure.md`.
> Preserved here for history; do not edit.

# Plan seed: fail closed when developer-doc research is unparseable

This file is a `plan-tool create` input. Use it via:

```
plan-tool create developer-doc-research-parse-failure --from-existing plan-seeds/developer-doc-research-parse-failure.md --iterate
```

It is not itself a plan. `plan-tool create` consumes the scope below to
produce the implementation plan and detail bundle.

## Overview

Make developer-document reference research return a discriminating outcome so
`create` distinguishes a valid empty reference list from an unparseable model
reply. A malformed reply will stop the affected create phase visibly instead
of continuing as though research found no references.

## Problem statement

`propose_references_from_claude` returns `None` for an unparseable reply and
an empty list for a valid `[]` reply. `_prepare_create_plan` currently treats
both values as false, records `propose_references` as `skipped`, converts the
value to `[]`, and can run reference fetching and body synthesis. The run log
therefore loses the difference between a deliberate “no suitable reference”
result and a failed research phase.

The iteration caller has the same ambiguous return path. It can present an
unparseable reference refresh as an ordinary absent update instead of a
failed authoring stage.

## Design

Introduce one small, typed result owned by `create.py` for generic
developer-doc research. It will carry a closed outcome vocabulary that
distinguishes populated references, a valid empty list, and an unparseable
response. Preserve the existing `Reference` payload and checkpoint rules:
only a parseable response is checkpointed.

On the first unparseable response, make one bounded repair request that names
the JSON-array contract and includes the rejected response. Record the retry
as attempt two through the current progress and run-log seams. If that reply
parses, continue normally; if it does not, preserve a bounded parse-failure
diagnostic using the existing create failure-artifact convention and return
the typed unparseable outcome. Do not add a flag, an unbounded retry loop, or
a new general retry framework.

At the initial `_prepare_create_plan` call site, an unparseable outcome will
end `propose_references` with an error outcome and raise a controlled
`CreateError` before reference fetching, body-section synthesis, plan
publication, or manifest mutation. The error will name the failed research
phase and tell the operator that retrying `create` is the supported recovery.
Existing initial-step checkpoints may remain available for that retry; the
malformed reference payload must not be saved as a successful checkpoint.

At the `_converge_create_plan` re-proposal call site, an unparseable outcome
will become the existing explicit iteration-stage failure path. It will leave
the published plan’s steps and References body unchanged for that round,
record an error rather than `skipped`, and propagate the failed-stage detail
through `CreateResult.iteration_stage_failure` while the published, resumable
plan retains the CLI's existing zero exit. The one repair retry is
the only automatic recovery; after it fails, the operator decides whether to
rerun the resumable create command.

A valid `[]` response remains distinct and preserves its current behavior:
the initial plan may render its TODO References placeholder, while an
iteration leaves the already-published References block intact. It remains a
normal skipped/no-output phase rather than an error.

## Scope

In scope:

- `plan_tool/create.py`'s generic reference-research result and both generic
  call sites.
- The one-time repair prompt, bounded parse-failure diagnostic,
  `propose_references` run-log outcome, and CLI-visible controlled error.
- Hermetic `tests/test_create.py` coverage for all three outcomes and the
  initial and iteration failure boundaries.

Out of scope:

- Roadmap-specific reference research and its separate validated result
  contract.
- Changing reference retrieval, reference-document fetching, body-synthesis
  content, or the valid-empty behavior.
- More than one repair retry, new CLI flags, or generalized phase-result
  machinery.

## Risks

- Treating a valid empty array as a failure would reject legitimate plans with
  no relevant external documentation. Tests will pin the valid-empty path.
- Reporting an error after publication without preserving the round’s prior
  body would make a failed refresh destructive. The iteration test will prove
  both the original References block and steps survive.
- Collapsing the run-log outcome again would hide the failure from `runs show`.
  Tests will assert `error` for malformed research and the existing normal
  outcome for valid empty research.
- Retrying malformed output indefinitely would raise model cost without
  increasing trust. Tests will assert exactly two calls on the repair path.

## Acceptance criteria

- Generic developer-doc research exposes distinct populated, valid-empty, and
  unparseable outcomes without changing `Reference` validation.
- A first malformed reply receives exactly one repair request with the rejected
  response and JSON-array correction; a second malformed reply leaves a
  bounded parse-failure diagnostic and no successful references checkpoint.
- An unparseable initial reply exits through `CreateError`, logs the research
  phase as an error, does not run dependent fetch or body synthesis, and
  writes neither plan nor manifest.
- An unparseable iteration reply surfaces the existing iteration-stage failure
  and leaves the published plan’s steps and References section unchanged.
- A valid empty reply remains non-failing and preserves its documented initial
  and iteration behaviors.
- Focused create tests cover the result contract, the initial no-write error
  boundary, the iteration preservation boundary, and run-log outcomes.

## References

- Source evidence: `plan_tool/create.py` —
  `propose_references_from_claude`, `_prepare_create_plan`, and
  `_converge_create_plan` own the generic research outcome and its two caller
  boundaries.
- Test evidence: `tests/test_create.py` — `TestProposeReferencesFromClaude`,
  `TestReferencesRenderedIntoBody`, and the create run-log fixtures cover the
  current parse, publication, iteration, and phase-outcome behavior.
