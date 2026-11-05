> **Auto-archived**: this plan was swept on 2026-11-05 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

---
format_version: 1
title: Roadmap Terminal Error Contract
intent: Every ordinary exception exit in the primary roadmap stage run and the named
  prompt-renderer routes has one origin-aware terminal disposition whose human error,
  status-channel fact, run-log outcome, exit code, and crash-report behavior agree.
status: completed
priority: medium
risk_profile: standard
risk_profile_rationale: Risk declaration uses standard because --yes does not accept
  model risk proposals.
test_command: uv run pytest tests/ -q -n auto
enforce_step_tests: true
source_seed: plan-seeds/roadmap-terminal-error-contract.md
steps:
- id: 1
  title: Publish the roadmap terminal disposition matrix
  intent: Give every implementation and test one authoritative mapping from failure
    origin to shared human message, terminal status, run-log ending, exit code, crash
    behavior, and operator action.
  files:
  - ROADMAP_FORMAT.md
  complexity: medium
  change_type: non-code
  detail: docs/implementation-plans/plan-details/roadmap-terminal-error-contract/01-publish-roadmap-terminal-disposition.md
  status: done
- id: 2
  title: Centralize roadmap text reads without changing their exception meanings
  intent: Make prompt and artifact reads share one bounded mechanism before their
    terminal behavior is extended.
  files:
  - plan_tool/roadmap.py
  - plan_tool/roadmap_revision_run.py
  - tests/test_roadmap.py
  - tests/test_roadmap_revision_run.py
  complexity: medium
  change_type: refactor
  depends_on:
  - 1
  depends_on_notes:
    1: Defines the origin-specific exception meanings the shared reader must preserve.
  detail: docs/implementation-plans/plan-details/roadmap-terminal-error-contract/02-centralize-roadmap-text-reads-without.md
  status: done
- id: 3
  title: Preserve writer-guard origins and terminal records before or during a roadmap
    run
  intent: Let the CLI distinguish invalid preflight use from a roadmap run that started
    but could not finish, while giving both dispositions a complete terminal record.
  files:
  - plan_tool/roadmap.py
  - plan_tool/cli/roadmap_cmd.py
  - tests/test_roadmap.py
  - tests/cli/test_roadmap_cmd.py
  complexity: medium
  change_type: feature
  depends_on:
  - 1
  depends_on_notes:
    1: Specifies the separate preflight-refusal and after-start failure dispositions,
      including their terminal status, run-log ending, exit code, and crash behavior.
  detail: docs/implementation-plans/plan-details/roadmap-terminal-error-contract/03-preserve-writer-guard-origins-terminal.md
  status: done
- id: 4
  title: Normalize template read failures across stage authoring, feedback, local
    revision, and seed materialization
  intent: Make equivalent template failures receive the matrix-owned human error and
    roadmap-domain treatment regardless of which named rendering route encounters
    them.
  files:
  - plan_tool/roadmap.py
  - plan_tool/roadmap_revision_run.py
  - tests/test_roadmap.py
  - tests/test_roadmap_revision_run.py
  complexity: medium
  change_type: feature
  depends_on:
  - 1
  - 2
  depends_on_notes:
    1: Defines the expected template-failure disposition and its operator-facing contract.
    2: Provides the shared read boundary while preserving route-specific messages
      and exception families.
  detail: docs/implementation-plans/plan-details/roadmap-terminal-error-contract/04-normalize-template-read-failures-across.md
  status: done
- id: 5
  title: Apply each terminal disposition across the primary, materialization, and
    local revision exits
  intent: Keep human output, status facts, run-log completion, exit codes, and crash
    persistence consistent for every ordinary primary-stage and named template-route
    exit.
  files:
  - plan_tool/roadmap.py
  - plan_tool/roadmap_revision_run.py
  - plan_tool/cli/roadmap_cmd.py
  - tests/test_roadmap.py
  - tests/test_roadmap_revision_run.py
  - tests/cli/test_roadmap_cmd.py
  - tests/cli/test_app.py
  complexity: high
  change_type: feature
  depends_on:
  - 1
  - 3
  - 4
  depends_on_notes:
    1: Supplies the exhaustive terminal mapping and exactly-once ordering contract.
    3: Supplies the origin distinction needed to choose usage versus runtime-failure
      handling.
    4: Makes all four named template routes enter the expected roadmap exception family
      before this step applies their common terminal disposition.
  detail: docs/implementation-plans/plan-details/roadmap-terminal-error-contract/05-apply-each-terminal-disposition-across.md
  status: done
- id: 6
  title: Reconcile the shipped terminal-error backlog records
  intent: Keep the project backlog truthful by closing only the roadmap terminal-error
    entries whose behavior now ships.
  files:
  - BACKLOG.md
  - BUG_BACKLOG.md
  complexity: low
  change_type: non-code
  depends_on:
  - 2
  - 3
  - 4
  - 5
  depends_on_notes:
    2: 'Completes the read-or-raise consolidation tracked by BACKLOG #347.'
    3: 'Completes the writer-guard origin distinction tracked by BACKLOG #344.'
    4: Completes the named prompt-template read-failure bug.
    5: 'Completes the exception terminal-status contract tracked by BACKLOG #348.'
  detail: docs/implementation-plans/plan-details/roadmap-terminal-error-contract/06-reconcile-shipped-terminal-error.md
  status: done
---
# Roadmap Terminal Error Contract

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
work may already have occurred; human rendering; terminal-status emission attempt;
run-log ending; exit code; crash-report behavior; and operator next action.
The minimum semantic rows are preflight refusal, expected failure after start,
and unexpected exception. Existing public exit-code meanings remain the
authority: input-shaped refusal stays distinct from a verb that ran but did
not finish, and an unexpected defect continues through the application crash
boundary. For equivalent expected template path/read/decode failures, the
matrix owns one shared human error; routes retain their origin only for
classification and structured terminal facts, not alternate user-facing text.

Exception origin is preserved before the common CLI catch erases it, using the
smallest typed or wrapped distinction that makes the matrix enforceable.
Template readers translate expected path/read/decode failures into the
appropriate roadmap exception family at their owning seam. The disposition
application owns the primary run lifecycle, its CLI exception result, the
materialization lifecycle/CLI pair, and the local-revision run/CLI pair. It
selects the same terminal status, run-log ending, exit code, and crash behavior
for equivalent template failures, attempts status emission exactly once after
the last stage fact, and preserves the primary lifecycle's selected exit code
rather than a default error code. A pre-lifecycle terminal-record boundary covers
writer-guard refusal before a primary or materialization lifecycle starts; it
records the matrix-selected disposition without pretending stages ran. Status
reporting remains best-effort and cannot replace the original exception.

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

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

- Model-response receipts and raw-response sidecars.
- Interrupt handling, second-interrupt safety, and the post-success `stopped`
  vocabulary in #339.
- Structural enforcement of every normal `break` path's stage-level stopped
  emission in #346.
- Publication rollback, checkpoint recovery, journal recovery, or lock-policy
  changes.
- Changing success output or adding retry behavior.

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
  differences. Its caller selects the exception family, while the disposition
  matrix selects the human error for equivalent template failures.

## Testing

Use a disposition matrix across the primary run lifecycle/CLI pair, the
materialization lifecycle/CLI pair, the local-revision run/CLI pair, and the
renderer entry routes. Prove the same expected template failure yields the same
human error, terminal status, run-log ending, exit code, and no crash file
whether reached through fresh stage authoring, bounded feedback, local revision,
or seed materialization. Prove the selected primary and materialization exit
code matches the run-log ending; preflight and mid-run writer-guard failures
select their different dispositions and each receives exactly one terminal
record; and an unexpected exception still reaches the application crash path
after exactly one best-effort roadmap terminal-status emission attempt.

At the bare-plan gate, retain the disposition fields, origin boundary, and
stage-versus-roadmap ordering property without selecting helper mechanics. At
the detail-grounded gate, require focused coverage for every disposition and
each named producer route.

## Acceptance criteria

- The plan carries one exhaustive terminal-disposition table with definition,
  producer, precedence, consumers, exit code, crash behavior, and operator path
  for every value.
- Every ordinary exception exit in the primary `run_roadmap` and materialization
  lifecycle makes exactly one best-effort roadmap terminal-status emission
  attempt and records a run-log ending consistent with its human message,
  selected return code, and crash behavior; a pre-lifecycle writer-guard refusal
  receives the same terminal record without claiming a stage began.
- Preflight and mid-run writer-guard failures remain distinguishable after they
  reach the CLI boundary.
- Equivalent prompt-template read/decode failures across all four named routes
  receive the same matrix-owned human error and expected-failure terminal
  disposition, including status, run-log ending, exit code, and crash behavior.
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
