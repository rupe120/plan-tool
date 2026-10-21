> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

---
title: Roadmap Stage Lifecycle Output
intent: A `roadmap` stage run emits bounded status lines on **stderr** at accepted-range,
  stage-start, retry/failure, stage-write, and normal-terminal transitions, so an
  operator can see the last transition the command reached without inspecting a process
  or opening the run log. It does not emit a heartbeat or model-derived text. Stdout,
  exit codes, artifact writes, retry policy, and the run-log JSONL are unchanged.
status: completed
priority: medium
risk_profile: standard
risk_profile_rationale: Risk declaration uses standard because --yes does not accept
  model risk proposals.
test_command: uv run pytest tests/ -q -n auto
enforce_step_tests: true
source_seed: plan-seeds/roadmap-stage-lifecycle-output.md
steps:
- id: 1
  title: Give the roadmap-progress backlog entry a unique identifier, narrow its promise,
    and repoint every live queue reference
  intent: Make progress independently identifiable from view reconciliation and keep
    both backlog arcs pointing at the deliberately smaller operator contract.
  files:
  - BACKLOG.md
  - docs/implementation-plans/backlog-arcs/backlog-arc-roadmap.md
  - docs/implementation-plans/backlog-arcs/backlog-arc-seed-ingestion.md
  complexity: low
  change_type: non-code
  detail: docs/implementation-plans/plan-details/roadmap-stage-lifecycle-output/01-give-roadmap-progress-backlog-entry.md
  status: done
- id: 2
  title: Emit bounded stage start, retry or stop, write, and re-gate facts from the
    roadmap runner without a heartbeat or model-derived text
  intent: Let an operator see each confirmed stage transition without changing the
    model invoker, shared progress reporter, retry policy, or artifact lifecycle.
  files:
  - plan_tool/roadmap.py
  - tests/test_roadmap.py
  complexity: medium
  change_type: feature
  detail: docs/implementation-plans/plan-details/roadmap-stage-lifecycle-output/02-emit-bounded-stage-start-retry-stop.md
  status: done
- id: 3
  title: Connect roadmap's direct status sink to stderr and add accepted-range plus
    normal terminal facts without changing stdout or interrupt handling
  intent: Bracket the runner's stage facts with the run's selected range and completed
    result while preserving the existing command interface.
  files:
  - plan_tool/roadmap.py
  - plan_tool/cli/roadmap_cmd.py
  - tests/test_roadmap.py
  - tests/cli/test_roadmap_cmd.py
  complexity: medium
  change_type: feature
  depends_on:
  - 2
  depends_on_notes:
    2: Supplies the runner transitions that the CLI brackets with accepted-range and
      normal terminal status.
  detail: docs/implementation-plans/plan-details/roadmap-stage-lifecycle-output/03-connect-roadmap-direct-status-sink.md
  status: done
- id: 4
  title: Document roadmap's transition-only stderr status without adding it to the
    shared heartbeat reporter contract
  intent: Keep command documentation accurate while preserving the distinction between
    roadmap's direct status lines and the shared reporter's heartbeat behavior.
  files:
  - README.md
  - RUNBOOK.md
  - docs/ARCHITECTURE.md
  complexity: low
  change_type: non-code
  depends_on:
  - 3
  depends_on_notes:
    3: Delivers the exact stderr behavior the command and architecture documentation
      describe.
  detail: docs/implementation-plans/plan-details/roadmap-stage-lifecycle-output/04-document-roadmap-transition-only-stderr.md
  status: done
- id: 5
  title: Update the roadmap demo and walkthrough, close the narrowed backlog entry,
    and advance the seed-ingestion queue
  intent: Tell operators what the terminal now confirms, retain the JSONL as the durable
    diagnostic record, close only the bounded transition-status work, and select the
    already ordered next seed-ingestion item after its prerequisite ships.
  files:
  - docs/how-to/roadmap-demo.md
  - docs/how-to/roadmap.md
  - BACKLOG.md
  - docs/implementation-plans/backlog-arcs/backlog-arc-roadmap.md
  - docs/implementation-plans/backlog-arcs/backlog-arc-seed-ingestion.md
  complexity: medium
  change_type: non-code
  depends_on:
  - 1
  - 3
  depends_on_notes:
    1: Supplies the unambiguous, narrowed backlog entry that this step closes.
    3: Supplies the delivered terminal behavior and its intentionally limited liveness
      claim.
  detail: docs/implementation-plans/plan-details/roadmap-stage-lifecycle-output/05-update-roadmap-demo-walkthrough-then.md
  status: done
---
# Roadmap Stage Lifecycle Output

## Overview

`roadmap` currently stays quiet between the command starting and its final summary. This
plan adds a few direct stderr status lines that say what transition the command most recently
completed: the selected stages, a stage beginning, a retry, a write, a stopped stage, and a
normal result.

This is intentionally not a heartbeat. After a `started` line, a long quiet interval can
still mean either a slow backend call or a stalled process. The line tells an operator where
to look; it does not prove the call remains alive. The run log remains the durable diagnostic
record, including detailed failure information.

The plan implements the `BACKLOG.md` entry titled **“Emit concise progress status for
long-running `roadmap` commands.”** That entry currently duplicates #323, which belongs to
unrelated view-reconciliation work. Step 1 assigns the progress entry a unique identifier,
then inventories and repoints its title-based references plus the active-queue references in
the roadmap and seed-ingestion arcs. View-reconciliation references retain #323.

## Steps

The machine-readable ordered step list lives in the `steps:` frontmatter block.

## Problem statement

The stage path in `plan_tool/roadmap.py` invokes the backend and publishes artifacts before
`cmd_roadmap` in `plan_tool/cli/roadmap_cmd.py` prints its existing final summary. A normal
multi-stage run therefore gives an operator no indication of the stage it has reached. A Integration
run recorded in `docs/how-to/roadmap-demo.md` took several minutes and retried a stage
before the terminal emitted anything.

The existing `plan_tool.progress` reporter solves a different problem for other commands: it
owns a per-call heartbeat. Reusing it here would add thread ownership, transport-diagnostic,
and interrupt-boundary work that this small operator aid does not need. Roadmap will instead
use one local callable that writes a complete bounded status line. It creates no background
work and has no cross-command API.

## Architecture

`cmd_roadmap` sits at the command boundary and supplies the existing stderr presentation
helper to an optional callback seam in `plan_tool/roadmap.py`. The runner owns the accepted
range and confirmed stage-transition facts after preflight; the command owns the terminal fact
around its returned result. This keeps stage behavior available to direct callers without
coupling the runner to CLI presentation.

The seam remains local to the roadmap command and runner instead of extending
`plan_tool.progress` or another shared interface. The trade-off is deliberately transition-only
visibility: it preserves existing retry, interrupt, run-log, and cross-command ownership while
leaving a quiet backend call without a liveness signal.

## Design

### One local status sink

`cmd_roadmap` supplies `style.note` (or the equivalent existing stderr helper) to the
roadmap runner as an optional status callback. The runner is silent when no callback is
provided, which keeps direct unit-level callers and non-CLI uses unchanged. One private
status-emission wrapper constructs and delivers every lifecycle line, including the CLI
terminal line. It treats a callback `Exception` as a lost status line and returns, so a broken
or closed stderr sink cannot change invocation, publication, retry, result, or exit behavior.
It does not catch `BaseException`, so `KeyboardInterrupt` retains its existing path. The
callback has no lifecycle state, thread, timer, run-log sink, or recovery output.

Only `plan_tool/roadmap.py` and `plan_tool/cli/roadmap_cmd.py` own this seam. Do not modify
`plan_tool.progress`, `plan_tool.shell`, `backend_runner.py`, or a shared caller interface.
Do not introduce a reporter class, event type, enum, CLI flag, configuration setting, or new
persisted event.

Before a slug, configured stage name, stage number, or selected-stage list reaches the callback,
a private roadmap formatter makes it safe for a terminal line. It renders each dynamic value as
escaped ASCII, limits an individual rendered field to 80 characters, and, when it clips a
field, appends a short stable digest of the complete value. The formatter limits its callback
body to 250 printable characters with the same digest rule. `style.note` adds the fixed six
printable characters `note: `, so the final textual stderr line, excluding its newline and any
terminal styling, is at most 256 characters. This keeps control characters such as newlines
from creating a second line and keeps injected sparse tables or huge stage numbers from making
a status line unbounded. No exception or model-derived value reaches this formatter.

### Status contract

All new lines go to stderr and use a fixed roadmap/stage prefix. They contain only the slug,
stage number and configured name, an existing retry failure kind, or an existing roadmap
outcome. They never include prompt text, reply text, exception detail, transport output, or a
run-log path.

The emitted order is:

1. After the runner accepts the selected sources and before its selected-stage loop, emit the
   accepted selected stage numbers. A `RoadmapError` or `RoadmapArtifactError` refusal before
   that point emits no lifecycle line. The two source-admission paths that instead return
   `OUTCOME_STAGE_INVALID` before that loop (`_load_and_regate_below` and
   `_load_predecessors`) emit neither accepted-range nor `stopped`, because no selected stage
   started; the CLI still emits their one terminal `stage-invalid` result.
2. Immediately before choosing a selected stage route, emit that stage's `started` line.
   This covers fresh authoring, ordinary `run_roadmap` re-entry with active feedback, and
   feedback-free re-gating. It does not cover the separate `--revise-feedback` command.
3. In each of the two retry loops (`_run_stage` and `_run_bounded_stage_feedback`), run the
   next attempt's source/admission check before emitting `retrying after <existing failure
   kind>`, then emit it immediately before that next invoker call. If that check stops the
   stage, emit no retry line or extra invocation. A final failed attempt is not labelled as a
   retry.
4. After an artifact is published and re-admitted for downstream use, emit its `wrote` line.
   No write line is emitted for a failed publication or read-back.
5. A feedback-free route emits `re-gated without write` only after its gates pass. A
   non-retrying source, re-gate, publication, or read-back failure that becomes a result emits
   a bounded `stopped` line; it never pretends that another attempt will run.
6. If `RoadmapError` or `RoadmapArtifactError` escapes after a selected stage emits `started`,
   emit one bounded `stopped` line and re-raise the same error. The CLI keeps its existing
   usage-error output and exit code; it emits no lifecycle terminal because no
   `RoadmapResult` exists.
7. For every `RoadmapResult`, including a pre-loop `stage-invalid`, `cmd_roadmap` emits one
   terminal line with the existing outcome after it has rendered the existing result and
   summaries. `KeyboardInterrupt` keeps the existing `interrupted`/130 path and has no
   terminal-status guarantee.

For a stage whose retry budget is exhausted, the runner emits a bounded stopped/failure line
with its existing failure kind before the CLI emits the existing `stage-exhausted` terminal
outcome. The retry kinds remain `invoke`, `parse`, `gates`, and `authored-review-rows`; the
outcomes remain `completed`, `completed-no-change`, `stage-exhausted`, and `stage-invalid`.
This plan adds no vocabulary to either set.

The callback has no relationship to the run-log event sequence. Existing `phase_start`,
`claude_call_start`, `attempt_failed`, `roadmap_stage_written`, and `run_end` records retain
their current fields and timing. The existing stdout summaries, exit codes, artifact writes,
retry decisions, and `--view` routes stay unchanged.

### Boundary and selection rules

The stage loop has three routes. `_run_stage` and `_run_bounded_stage_feedback` make backend
calls and each own a retry loop. `_run_feedback_free_stage` makes no backend call. It still
gets a `started` line so selected stage numbers do not appear to be skipped, but it reports
only the verified re-gate result and never claims a model invocation or a write.

Status is a confirmed transition, not a prediction. A `wrote` line follows successful
publication and read-back; a retry line follows the next attempt's admission check and
precedes its invoker call; a normal terminal follows the already-rendered command result. Once
a stage has emitted `started`, every non-success ending — exhausted retry budget, source
admission, feedback-free re-gate, publication, read-back, or escaping roadmap exception —
emits exactly one safe `stopped` fact. A returned result then gets its terminal line; an
escaping error retains the existing CLI error path without one. A post-call admission or
publication failure is not a retry, because the stage loop will not make another attempt.

## Scope guardrails

- Add direct transition status only to the normal `roadmap` stage-run path.
- Keep output on stderr. stdout must remain byte-identical for completed, no-change,
  exhausted, invalid, and all view routes.
- Do not add a heartbeat, thread, timer, dashboard, status file, scheduler, cancellation,
  transport streaming, or durable progress state.
- Do not change `MAX_STAGE_ATTEMPTS`, correction prompts, stage gates, artifact publication,
  source admission, `OUTCOMES`, `FAILURE_*`, exit codes, or run-log records.
- Do not show backend prompts, replies, exception details, failure tails, or model content.
- Escape and cap every dynamic slug, stage-name, stage-number, and selected-stage field before
  it reaches stderr. Cap the callback body at 250 printable characters so the final textual
  `note: ` stderr line is at most 256 characters; never rely on slug path validation as
  terminal-output validation.
- Treat status delivery as fail-open: swallow callback `Exception` without adding a fallback
  line or changing roadmap execution; never swallow `BaseException`.
- Do not add this behavior to `--apply`, `--refresh-seeds`, `--materialize`,
  `--revise-feedback`, structural rewrite, or another command. Evidence for a separate
  long-running route needs a separate backlog decision.

## Risks

- **Unbounded or sensitive status output (medium):** A transition line could expose model,
  exception, or transport content. Fixed message inputs and tests with distinctive injected
  content mitigate this risk; unanticipated future failure kinds need the same bounded format.
- **Status that misstates a transition (medium):** A line could claim a retry, write, or
  liveness state the runner has not confirmed. Emission after the named transition and coverage
  for retry exhaustion, admission, publication, and read-back failures mitigate this risk; a
  quiet backend call remains intentionally indistinguishable from a stalled one.
- **Command-interface regression (medium):** Direct status could alter existing output or
  non-stage routes. Stderr capture tests preserve stdout and verify that view routes remain
  silent; consumers that parse stderr must tolerate this documented human-facing output.

## Out of scope

- A heartbeat or liveness signal for a quiet backend call — it requires separate lifecycle
  and interrupt design beyond this transition-only status.
- Changes to stdout, exit codes, retry policy, artifact writes, or run-log JSONL — this plan
  preserves those existing interfaces and records.
- Progress status for other roadmap routes or commands — each needs separate evidence and a
  backlog decision.

## Testing

Use the existing deterministic stage invokers and temporary plan roots. No test starts a real
backend or waits for time to pass.

- A fresh multi-stage success records selected-range, `started`, and `wrote` status in stage
  order, followed by the normal terminal outcome. Assert each message appears only after the
  transition it names.
- A runner call without the optional callback produces no lifecycle output; the same call with
  an injected collector receives the bounded transition sequence. This protects direct callers
  from a fallback stderr write.
- A callback that raises `Exception` drops only that status line. Runner and CLI coverage prove
  the same invocation/result/exit behavior still occurs; an injected `KeyboardInterrupt` is
  not swallowed.
- Use a newline/control-character slug and configured stage name, then overlong values with a
  shared prefix. Assert every emitted record remains one ASCII line, each rendered dynamic
  field and callback body is capped, and clipped values retain distinct stable suffixes. At the
  CLI boundary, capture a `style.note` status with styling disabled and assert its final text,
  including `note: ` but excluding its newline, is at most 256 characters. Repeat this with
  sparse injected tables containing huge stage numbers and enough selected rows to exceed the
  accepted-selection display budget.
- Cover a retry followed by success in both `_run_stage` and
  `_run_bounded_stage_feedback`. The line names the real existing failure kind and is emitted
  only when another attempt occurs.
- In both retry loops, force source admission to fail between a failed attempt and its next
  invoker call. Assert there is no retry line or extra invocation, then one stopped fact and
  the terminal invalid result.
- Cover budget exhaustion in both loops. The final failed attempt is a bounded stopped/failure
  fact, never `retrying`, and the CLI then emits `stage-exhausted`.
- Cover non-retrying failures from source admission, feedback-free re-gating, publication,
  and re-admission. After `started`, each produces exactly one stopped fact, no retry line, and
  no write line. A feedback-free success produces `re-gated without write` and makes no
  backend call. Separately cover a pre-loop `_load_and_regate_below` or `_load_predecessors`
  invalid result: no accepted-range or stopped fact, and one terminal `stage-invalid` line.
- Force prompt rendering and post-write read-back to raise `RoadmapError` or
  `RoadmapArtifactError` after `started`. Each route emits exactly one stopped line, then
  preserves today's CLI usage-error output and exit code without a lifecycle terminal line.
- CLI tests capture stdout and stderr. They prove stage-run status reaches stderr, existing
  stdout summaries are unchanged, `--view` routes add no status, and exactly one terminal line
  follows each returned outcome: `completed`, `completed-no-change`, `stage-exhausted`, and
  `stage-invalid`. The feedback-free CLI re-entry case specifically preserves its unchanged
  stdout summary before `completed-no-change`. An injected interrupt keeps rc 130 and emits no
  required terminal line.
- Inject distinctive prompt, reply, exception-detail, and transport-tail text into retry and
  failure cases. Assert none reaches a status line.
- Replay existing run-log assertions with status enabled to prove its event order and payloads
  are unchanged.

## Documentation and backlog work

Step 1 changes the duplicated progress entry by title and updates every live queue reference:
the roadmap arc and the seed-ingestion arc move to its new identifier, while the unrelated
view-reconciliation entry retains #323. It makes the approved reduction explicit: roadmap
reports its last confirmed transition, not a live liveness signal.

Step 4 keeps the shared reporter documentation accurate: `roadmap` emits direct bounded
transition status but does not join `ProgressReporter`'s heartbeat contract. README and the
runbook explain that stderr redirection suppresses these human lines while stdout remains the
machine-readable surface.

Step 5 keeps the demo's existing instruction to inspect JSONL before diagnosing an exhausted
stage: live status shows only the current transition and never replaces the per-attempt record.
It adds that distinction to the walkthrough, which currently explains the command but says
nothing about live terminal status. When it closes #337, it also advances the seed-ingestion
arc from its completed prerequisite to #333, without selecting #327 or #331. `BACKLOG #217`
remains the separate retained-reply gap.

## Acceptance criteria

- A normal selected-stage run emits bounded stderr lines for its accepted range, every
  selected stage start, actual retry, successful write or verified feedback-free re-gate,
  stopped stage when applicable, and one normal terminal outcome.
- The output identifies the roadmap slug and stage number/name, never backend or exception
  content. A line shows the last confirmed transition only; it does not claim a quiet call is
  alive.
- Every dynamic slug, stage-name, stage-number, and selected-stage field is escaped to one
  ASCII line and capped at 80 characters; the callback body is capped at 250 printable
  characters so the final textual `note: ` line is capped at 256 characters, excluding its
  newline and terminal styling. An overlong field or body carries a stable suffix so it remains
  distinguishable without exposing an unbounded raw value.
- Both backend retry loops obey the same retry/final-failure rule, and the feedback-free path
  reports no backend call or write.
- A source/admission invalid result before the selected-stage loop emits only the terminal
  `stage-invalid` line. After a `started` line, every invalid or exhausted stage emits exactly
  one stopped fact before its terminal result; a failed admission between attempts emits no
  false retry line.
- A status-sink `Exception` cannot alter invocation, artifacts, retries, outcomes, or exit
  codes. An escaping `RoadmapError` or `RoadmapArtifactError` after `started` emits one stopped
  fact, then preserves the existing usage-error path with no lifecycle terminal.
- Every returned outcome — `completed`, `completed-no-change`, `stage-exhausted`, and
  `stage-invalid` — has exactly one terminal line after its existing CLI result rendering.
- Stdout, exit codes, retry policy, artifacts, run-log JSONL, and non-stage roadmap modes are
  unchanged.
- No shared reporter, shell, subprocess, heartbeat, timer, or persistent-progress code is
  added or modified.
- The uniquely identified, narrowed backlog entry, roadmap arc, README, runbook,
  architecture document, demo, walkthrough, and seed-ingestion arc describe the delivered
  limitation consistently. The demo retains JSONL guidance for detailed diagnosis, and the
  seed-ingestion arc selects #333 after #337 is complete.

## Deferred

- A real liveness signal for a quiet backend call. That needs its own lifecycle and interrupt
  design, and this plan deliberately does not supply one.
- Retaining an unusable backend reply (`BACKLOG #217`), which remains a diagnosis/storage
  concern rather than a transition-status concern.
- Progress output for other roadmap routes or commands, a quiet flag, backend streaming,
  cancellation, or a dashboard.

## References

- `plan_tool/roadmap.py` — Defines the runner's stage routes, retry loops, and result outcomes.
- `plan_tool/cli/roadmap_cmd.py` — Defines the command boundary, stderr presentation, and normal summaries.
- `BACKLOG.md`, `docs/implementation-plans/backlog-arcs/backlog-arc-roadmap.md`, and
  `docs/implementation-plans/backlog-arcs/backlog-arc-seed-ingestion.md` — Define the
  progress entry and its live queue references that step 1 repoints.
- `docs/how-to/roadmap-demo.md` — Records the roadmap run that motivates transition status.
