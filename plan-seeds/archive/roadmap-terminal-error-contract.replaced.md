> **Replaced**: this file has been superseded by `docs/implementation-plans/2-roadmap-terminal-error-contract.md`.
> Preserved here for history; do not edit.

# Seed: roadmap terminal error contract

Sources: `BACKLOG.md` #344, #347, and #348, plus `BUG_BACKLOG.md` — "Two
prompt-template renderers have no read-failure handling in their caller
chain." The resulting plan updates or removes each source entry only after its
corresponding terminal-disposition behavior ships.

## Outcome

Every ordinary exception exit in the primary roadmap stage run and the named
prompt-renderer routes has one origin-aware terminal disposition whose human
error, status-channel fact, run-log outcome, exit code, and crash-report
behavior agree.

## In scope

- Derive and publish the complete disposition matrix for preflight refusals,
  expected failures after work starts, and unexpected exceptions.
- Distinguish preflight from mid-run writer-guard failures by origin rather
  than mapping one exception type uniformly.
- Give every exception exit in the primary `run_roadmap` dispatch one
  roadmap-level terminal status fact without changing per-stage status
  ordering.
- Normalize prompt-template read failures across stage authoring, bounded
  feedback, local revision, and seed materialization so equivalent failures
  reach the same disposition.
- Preserve the application-level unexpected-crash path for defects that do not
  belong to a roadmap-domain or environmental exception family.
- Reconcile all named source backlog entries when their behavior ships.

## Overview

Roadmap already reports returned failure results coherently, but raised
exceptions cross several independently evolved boundaries. The same writer
guard type can mean invalid preflight usage or a failure after stages have
published; some template reads become clean roadmap errors while siblings
reach the generic crash handler; and exception exits can end the status stream
without a roadmap-level terminal fact. This effort makes those surfaces one
terminal contract without absorbing model-response evidence or interrupt
safety.

## Problem statement

An operator or automation consumer currently has to infer failure origin from
which message, status fact, run-log ending, exit code, or crash file happened
to appear. Uniformly catching broad exception classes loses whether work had
started, while letting expected environment failures escape produces crash
artifacts for conditions the command can explain. The contract needs to be
defined by execution origin and expectedness, then applied consistently at the
CLI boundary and the renderer seams that feed it.

## Architecture

`create` derives one exhaustive disposition table before step decomposition.
For each disposition it records: definition; producer and precedence; whether
work may already have occurred; human rendering; terminal status fact;
run-log ending; exit code; crash-report behavior; and operator next action.
The minimum semantic rows are preflight refusal, expected failure after start,
and unexpected exception. Existing public exit-code meanings remain the
authority: input-shaped refusal stays distinct from a verb that ran but did
not finish, and an unexpected defect continues through the application crash
boundary.

Exception origin is preserved before the common CLI catch erases it, using the
smallest typed or wrapped distinction that makes the matrix enforceable.
Template readers translate expected path/read/decode failures into the
appropriate roadmap exception family at their owning seam. The roadmap CLI
emits the terminal status selected by the matrix exactly once, after the last
stage fact and before returning or re-raising. Status reporting remains
best-effort and cannot replace the original exception.

## Scope guardrails

- Do not capture or persist model replies; the roadmap model-failure-receipt
  seed owns that evidence.
- Do not catch `KeyboardInterrupt`, `SystemExit`, or arbitrary
  `BaseException`; BACKLOG #339 owns interrupt and second-interrupt semantics.
- Do not redesign roadmap result outcomes, retry loops, publication recovery,
  checkpoints, or writer locking.
- Do not convert unexpected programming defects into clean domain errors to
  avoid a crash report.
- Do not introduce a generic application-wide exception framework.

## Out of scope

- Model-response receipts and raw-response sidecars.
- Interrupt handling, second-interrupt safety, and the post-success `stopped`
  vocabulary in #339.
- Structural enforcement of every normal `break` path's stage-level stopped
  emission in #346.
- Publication rollback, checkpoint recovery, journal recovery, or lock-policy
  changes.
- Changing success output or adding retry behavior.

## Allowed behavior changes

Exception exits gain the matrix-selected roadmap terminal status. Mid-run
writer-guard failure may change from the preflight usage code to the existing
runtime-failure code. Expected template read/decode failures use clean roadmap
error handling instead of the generic crash path. Unexpected exceptions retain
crash persistence and propagation semantics.

## Allowed reorganization

Add the smallest origin-specific exception subtype or wrapper needed to retain
preflight versus mid-run meaning. Extract one read-or-raise helper only if it
can preserve each caller's exception family and bespoke message. Do not merge
the roadmap command dispatcher, stage guard, or publication layer.

## Risks

- Catching a broad `OSError` too high can misclassify a publication defect as
  an expected template problem and suppress its crash evidence.
- Emitting a terminal status from both a stage guard and the CLI can duplicate
  or reorder lifecycle facts. The disposition matrix must separate stage-level
  and roadmap-level ownership.
- A status callback failure can mask the exception being reported. Existing
  best-effort `Exception` handling remains the fence; `BaseException` behavior
  stays with #339.
- A shared read helper can flatten legitimate preflight and mid-run exception
  differences. Its caller selects the exception family and message.

## Testing

Use a disposition matrix across the CLI exception branches and renderer entry
routes. Prove the same expected template failure yields the same human error,
terminal status, run-log ending, exit code, and no crash file whether reached
through fresh stage authoring, bounded feedback, local revision, or seed
materialization. Prove preflight and mid-run writer-guard failures select their
different dispositions. Prove an unexpected exception still reaches the
application crash path after exactly one roadmap terminal status fact.

At the bare-plan gate, retain the disposition fields, origin boundary, and
stage-versus-roadmap ordering property without selecting helper mechanics. At
the detail-grounded gate, require focused coverage for every disposition and
each named producer route.

## Acceptance criteria

- The plan carries one exhaustive terminal-disposition table with definition,
  producer, precedence, consumers, exit code, crash behavior, and operator path
  for every value.
- Every ordinary exception exit in the primary `run_roadmap` dispatch emits
  exactly one roadmap-level terminal status fact consistent with its human
  message, run log, return code, and crash behavior.
- Preflight and mid-run writer-guard failures remain distinguishable after they
  reach the CLI boundary.
- Equivalent prompt-template read/decode failures across all four named routes
  receive the same expected-failure treatment.
- Unexpected exceptions are not laundered into expected roadmap errors, and a
  reporting failure cannot replace the original exception.
- #344, #347, #348, and the prompt-template BUG entry are updated or removed
  only when their corresponding behavior and regression coverage ship.

## Deferred

BACKLOG #339 retains interrupt and post-success `stopped` semantics; #346
retains structural enforcement for normal stage-loop failure branches. Model
reply evidence remains in the roadmap model-failure-receipt effort. Any
application-wide exception framework or additional command migration is filed
separately.

## References

- `BACKLOG.md` #344 — preflight versus mid-run writer-guard exit codes.
- `BACKLOG.md` #347 — roadmap read-or-raise duplication and exception-family
  boundary.
- `BACKLOG.md` #348 — missing roadmap-level terminal status on exception exits.
- `BUG_BACKLOG.md` — "Two prompt-template renderers have no read-failure
  handling in their caller chain."
- `plan_tool/cli/roadmap_cmd.py:cmd_roadmap` — CLI exception and return-code
  boundary.
- `plan_tool/roadmap.py:_stage_run_guard` — stage-level exception status owner.
- `plan_tool/roadmap.py:_render_stage_prompt`,
  `plan_tool/roadmap.py:_render_stage_feedback_prompt`, and
  `plan_tool/roadmap.py:_render_seed_materialize_prompt` — prompt renderer
  seams.
- `plan_tool/roadmap_revision_run.py:render_local_revision_prompt` — local
  revision renderer seam.
- `plan_tool/cli/app.py` — generic unexpected-error and crash-report boundary.
