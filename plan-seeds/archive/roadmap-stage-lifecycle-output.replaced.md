> **Replaced**: this file has been superseded by `docs/implementation-plans/2-roadmap-stage-lifecycle-output.md`.
> Preserved here for history; do not edit.
> **Identifier correction 2026-09-01:** the `#325` citation below names the
> retired conversational proposal, not the current `BACKLOG.md` #325 entry.

# Lifecycle progress output for long-running `roadmap` stage runs

Seed for `BACKLOG.md` **#323 — "Emit concise progress status for long-running
`roadmap` commands"** (the entry at `BACKLOG.md:8857`, filed 2026-08-31 from the
Integration `project-workspace-membership-proof` run). **Two entries currently carry the
id `#323`**: this one, and an unrelated `--view walk` / `--view html`
reconciliation entry at `BACKLOG.md:5672` that took the number first — cite the
title, not the number, and renumber before the resulting plan reconciles the
backlog. The plan updates that entry when the work ships. Routed by
[`backlog-arc-roadmap.md`](../docs/implementation-plans/backlog-arcs/backlog-arc-roadmap.md)
§ "Ordered route" as the immediate priority. The former conversational route
is retired and is not a successor to this work.

## Outcome

A `roadmap` stage run emits ordered lifecycle lines on **stderr** while it is
still running — the accepted stage range, each stage's start, each retry with
the failure kind that caused it, each successful stage write, and one terminal
outcome — so an operator can tell healthy multi-minute backend work from a
stalled process without inspecting the process or opening the run log. Stdout,
exit codes, artifact writes, retry policy, and the run-log JSONL are unchanged.

## Overview

`plan_tool/progress.py` already is this feature for every other
backend-invoking verb, and its module docstring states this seed's exact
problem: *"Without a separate channel a user sees no output for the duration of
each claude call (often minutes per step)"*, resolved by *"human-readable status
lines on **stderr** while the structured stdout parsers receive byte-identical
input"* plus a daemon heartbeat thread emitting a periodic `Ns elapsed` tick.
`create.py`, `detail.py`, `review.py`, `launcher.py`, `cli/completeness_phases.py`,
and `cli/jira_cmd.py` all consume it. **`roadmap.py` imports it nowhere.**

So this is not a new capability. It is wiring the one backend-invoking verb that
was never connected to the shipped, verb-agnostic seam — and the seed's main job
is to fence that wiring against becoming an observability subsystem.

## Problem statement

`plan_tool/roadmap.py` contains exactly two `print(` calls, both inside
`_confirm_apply_seeds` (`roadmap.py:2563`, `:2574`) on the interactive `--apply`
path. **The stage path prints nothing until `run_roadmap` returns.** Every
operator-facing line is rendered post-return by `cli/roadmap_cmd.py`
(`_print_completed` `:1728`, `_print_completed_no_change` `:1750`,
`_print_invalid` `:1925`, `_print_exhausted` `:1934`, then four summary blocks).

A stage run in between is four sequential backend calls, each retryable up to
`MAX_STAGE_ATTEMPTS = 3` (`roadmap.py:184`).

**Measured, in-repo, dated — `docs/ROADMAP_DEMO_ORCHESTRATION.md:565-596`.** A
2026-08-06 stage-1 run cost ~7.5 minutes and ~$1.45, ran three attempts
(gates, gates, parse), and **wrote nothing**, with no terminal output for the
duration. The same section records the standing workaround this seed removes —
*"Always open `.plan-tool/runs/<slug>/*.jsonl` and read the `attempt_failed`
events before diagnosing"* — and the diagnostic gap that makes it necessary:
*"The terminal error names only the final attempt's failure kind."* It read
`(parse failure)` when two of three attempts failed on an unrelated gate axis.
The 2026-08-31 Integration run named in the backlog entry is the second instance, with
four stages and one validation retry.

**One premise in the backlog entry needs narrowing: the terminal is silent at
default verbosity only.** `cli/app.py:658-665` sets the process console
verbosity — `backend_runner.py:78 set_console_verbosity`, reached through
`launcher.py:44-48`'s re-export — with `_CONSOLE_VERBOSITY_QUIET` as the
unflagged default, and roadmap's batch invoker reaches
`backend_runner.run_streaming_once` without `suppress_content_output`, so
`plan-tool -v roadmap <slug>` already prints one stderr line per backend
`tool_use` (`backend_runner.py:594`) and `--debug` dumps raw NDJSON. A
recoverable rate limit also already prints via `shell._notify_or_tool`
(`shell.py:335`). None of that is *lifecycle* output — it is backend content at
a verbosity an operator should not need — but the gap is a missing channel, not
a missing stream, and this seed adds the channel rather than making `-v` louder.

## Architecture

### Reuse `progress.ProgressReporter`; author no lifecycle vocabulary

**Decision, must not drift:** the reporter is
`plan_tool.progress.ProgressReporter` (`progress.py:124`) with its existing
`start_step(idx, total, label, *, prefix, phase, attempt, prompt_bytes)
-> StepHandle` and `StepHandle.complete` / `.fail` / `.notice(message, kind=)`
(`progress.py:99-121`). No new reporter class, no new event dataclass, no new
enum. `StderrReporter` already ships the `[i/n]` counter, the `⋯` working glyph,
the `↻` notice glyph, `HEARTBEAT_INTERVAL_S = 15.0`, and a `run_log=` tee.

**The seam shape is the one three orchestrators already use**, verbatim:
a `reporter: Optional[ProgressReporter] = None` parameter, defaulted inside the
orchestrator body with `if reporter is None: reporter = StderrReporter()`
(`detail.py:3767-3768` — whose comment reads *"Default to live stderr reporting;
tests inject NullReporter"* — and `launcher.py:1696-1697`). It parallels
roadmap's existing `invoker: StageInvoker = shell_roadmap_invoker`
(`roadmap.py:2002`), `max_stage_attempts`, and `run_logger` defaults exactly.
`NullReporter` (`progress.py:168`) is the test injection.

### Three stage routes, and only two of them make a call

The stage loop (`roadmap.py:2197`) dispatches three ways, and conflating them
would make the output lie:

- `_run_stage` (`roadmap.py:1455`) — fresh authoring; attempt loop at `:1494`.
- `_run_bounded_stage_feedback` (`roadmap.py:1615`) — predecessor with open
  feedback; **its own second attempt loop** at `:1650`.
- `_run_feedback_free_stage` (`roadmap.py:1725`) — **makes no backend call**,
  re-gates the predecessor and returns it.

**Guarantee, must not drift:** the feedback-free route must not open a progress
step. A step handle asserts a call is in flight; opening one for a route that
invokes nothing reports work that is not happening, and its heartbeat would tick
against an instant return. It gets a distinct one-shot line naming the re-gate,
or no line — `create`'s decision, not this seed's, but it may never be reported
as a call.

Both attempt loops must be instrumented. The Integration retry could have come from
either, and instrumenting only `_run_stage` reproduces the class-sweep failure
CLAUDE.md § "Fix the class, not the cited spot" describes.

### The retry notice carries the real failure kind — and there are four

Retries route through `StepHandle.notice(..., kind="retry")`. The kind reported
is the attempt's own, read from the existing closed set — **four
retry-consuming constants, not the three the backlog entry implies**:

- `FAILURE_INVOKE` (`roadmap.py:608`) — rc≠0 or blank reply
- `FAILURE_PARSE` (`roadmap.py:609`) — unliftable reply or `RoadmapArtifactError`
- `FAILURE_GATES` (`roadmap.py:610`) — gate violations
- `FAILURE_AUTHORED_REVIEW_ROWS` (`roadmap.py:620`) — reply minted a
  `feedback`/`removals` row the reviewer never wrote; refused in the attempt
  loop rather than by a gate, and it has its own `_print_exhausted` arm at
  `roadmap_cmd.py:1967`

A fifth, **non-retrying** exit exists: `_StageOutcome(invalid_detail=...)` from
`RoadmapSourceAdmissionError` (`roadmap.py:1490`, `:1499`, `:1585`) returns
immediately without consuming an attempt. It is a stage failure, never a retry —
reporting it as one would tell an operator to expect a second attempt that will
never come. Naming the live kind per attempt is what closes the
*"terminal error names only the final attempt's failure kind"* gap above; it is
a consequence of correct per-attempt reporting, not a separate deliverable.

### Terminal outcome reuses `OUTCOMES`; no third vocabulary

The terminal line reports the existing closed four-member set —
`OUTCOME_COMPLETED`, `OUTCOME_COMPLETED_NO_CHANGE`, `OUTCOME_STAGE_EXHAUSTED`,
`OUTCOME_STAGE_INVALID` (`roadmap.py:584-597`), with
`is_successful_roadmap_outcome` (`:600`) already distinguishing success. A
*second*, narrower lifecycle vocabulary already coexists with it in the run log
(`"error"`, `"interrupted"`, `"preflight-refused"`, `"no-op"`, `"partial"`,
`"exhausted"` — `roadmap.py:1975`, `:1914`, `roadmap_cmd.py:1373-1477`). **This
seed adds no member to either and introduces no third.** Naming a new closed
vocabulary would oblige the full per-value contract `SEED_FORMAT.md` requires
(definition, producer, precedence, consumers, exit path) for a line of text.

### stderr only — stdout is a live piping surface

`--view <mode>` renders to stdout (`roadmap_cmd.py:1618`) and
`--view html --output -` prints the page to stdout (`roadmap_cmd.py:1564`).
`progress.py:14-17` already states the rule for exactly this reason. Note the
existing streams are mixed — `style.success`/`style.detail` go to **stdout**,
`style.error`/`info`/`warn`/`note`/`tool` to **stderr** (`style.py:76-127`) —
and `tests/cli/test_roadmap_cmd.py:2060 TestOverwriteAdviceIsPrintedExactlyOnce`
exists because advice once printed twice on two different streams. Lifecycle
lines land on stderr and nowhere else; none of the existing post-return
rendering moves.

### The layering boundary this does and does not cross

`tests/test_roadmap.py:6766 test_the_orchestrator_renders_no_operator_advice`
pins that `run_roadmap` *"reports overwrites as data and prints nothing.
Rendering belongs to `cli.roadmap_cmd`."* Its assertions are narrow — the
absence of `"--from-stage"` and `"replaced"` — so lifecycle lines do not turn it
red, but the boundary it names is real and stays: **operator advice and result
summaries stay in `cli/roadmap_cmd.py`; in-flight progress lives with the call,
exactly as it does in `create`/`detail`/`review`/`launcher`.** That split is the
existing convention, not an exception carved for this seed. If `create` finds
the boundary genuinely cannot carry the reporter, extracting only the reporter
wiring behind it is the allowed move; nothing else reorganizes.

### The run log already has the events — mirror, never duplicate

`RunLogWriter` already emits `phase_start`, `phase_end`, `claude_call_start`,
`attempt_failed`, `gate_violations`, `roadmap_stage_written`, and `run_end`
(`run_log.py:2050-3158`), from sites throughout the stage loop
(`roadmap.py:2203`, `:2239`, `:2249`, `:2325`, `:2386`, `:2403`). `StderrReporter`
already accepts `run_log=` and tees `claude_call_start` through
`_ClaudeCallStartSink` (`progress.py:69`). The stderr channel presents what the
JSONL already records; **no run-log event is added, removed, renamed, or
re-timed**, and the reporter is never made the producer of a persisted event.

## In scope

`plan_tool/roadmap.py` (the reporter parameter on `run_roadmap`/`_run_roadmap`,
threaded into `_run_stage` and `_run_bounded_stage_feedback`, plus the
feedback-free route's non-call line), `plan_tool/cli/roadmap_cmd.py` only if
`cmd_roadmap` must pass a reporter through, `tests/test_roadmap.py` (whose
`_Env.run` at `:496` already has the `kwargs.setdefault("invoker", ...)` idiom
the reporter default follows), `tests/cli/test_roadmap_cmd.py`, and the operator
docs that currently prescribe reading the JSONL —
`docs/ROADMAP_DEMO_ORCHESTRATION.md:582-590` and `docs/ROADMAP_WALKTHROUGH.md`.
**Not** `plan_tool/progress.py`: the seam ships complete, and a roadmap-shaped
change to it would be this seed reaching into a shared leaf for one consumer.

### Scope contract

- **Not-allowed list, enumerated — a principle stated in prose does not hold
  the line** (CLAUDE.md § "Validating a semantic property you cannot observe"):
  no new CLI flag of any kind (`--progress`, `--quiet`, `--json`, a verbosity
  level); no new member of `OUTCOMES`, of the `FAILURE_*` set, or of the
  run-log lifecycle vocabulary, and no third vocabulary; no backend prompt,
  response, or content text in a lifecycle line (that is `-v`/`--debug`'s
  existing job, and it is not extended here); no dashboard, status file,
  daemon, scheduler, cancellation, or job control; no durable progress
  persistence; no change to stdout on any route; no change to
  `MAX_STAGE_ATTEMPTS`, the corrections blocks, or any retry decision; no
  progress wiring for another verb; no new autouse fixture.
- **Allowed behavior changes:** interactive `roadmap` stage runs gain stderr
  lifecycle lines and a heartbeat tick. Exit codes, artifact writes, the four
  `OUTCOMES`, retry semantics, every post-return summary, stdout on every
  route, and the run-log JSONL are byte-for-byte unchanged.
- **Allowed reorganization:** none, unless the CLI-to-orchestrator boundary
  provably cannot carry the reporter — then extract only the reporter wiring,
  behind the existing boundary, and nothing else.
- **Verification:** § Testing.
- **Stop / defer:** § Deferred; anything the iteration loop surfaces outside
  this fence goes to `BACKLOG.md` / `BUG_BACKLOG.md`, never applied as plan
  expansion.

## Out of scope

- **BACKLOG #217** (a stage that dies on an unusable reply keeps no copy of
  it). Adjacent and tempting — the same 2026-08-06 run proves both gaps, and
  `docs/ROADMAP_DEMO_ORCHESTRATION.md:589` names #217 in the same breath — but
  retaining a reply is storage, not reporting. Lifecycle lines say a parse
  attempt failed; they do not make it diagnosable.
- Progress output for `--revise-feedback`, `--rewrite-structural`,
  `--analyze-escalation`, `--escalate-feedback`, `--refresh-seeds`,
  `--materialize`, or `--apply`. Each is a single bounded request or a
  no-backend route, not a multi-minute multi-stage run; extending there is a
  separate, evidence-gated decision.
- Any change to `backend_runner.py`'s console verbosity, its stdout pump, the
  silence-kill ladder, or `set_console_verbosity`.
- BACKLOG #325's conversational cross-artifact feedback route. It depends on
  this shipping; it is not part of it.
- Rebalancing which existing lines go to stdout vs stderr.

## Risks

- **Scope inflation into an observability subsystem.** The named failure mode
  for this class. Mitigated by the enumerated not-allowed list above, and by
  the design being *wiring an existing seam* — every line of new vocabulary is
  evidence of drift.
- **Instrumenting one attempt loop and not the other.** `_run_stage` is the
  obvious one; `_run_bounded_stage_feedback` has a near-duplicate loop and is
  the route a *revision* retry takes. A green suite proves nothing here — the
  un-swept route's tests pin its current silence (CLAUDE.md § Tests). Mitigated
  by § Testing asserting both loops and the class-sweep check on the third
  route.
- **436 existing `tests/test_roadmap.py` tests gaining a live stderr reporter
  and a daemon heartbeat thread**, against a 30s per-test timeout and `-n auto`.
  Mitigated by defaulting `reporter` in `_Env.run` the way `invoker` already is;
  the risk is the tests that call `roadmap._run_stage` / `run_roadmap` directly
  and bypass `_Env` (`_drive_stage` at `tests/test_roadmap.py:2296`, and the
  `tests/cli/` real-orchestrator classes at `:2060`, `:2135`).
- **Reporting a state before the transition that produces it** — the backlog
  entry's own stated risk. A stage write must be announced after
  `roadmap_stage_written`'s condition holds, never at loop top; a terminal
  success never before an outcome is assigned. Mitigated by § Testing's
  ordering assertions, which are the point of those tests rather than a
  by-product.
- **The heartbeat thread outliving a `KeyboardInterrupt`.** `cmd_roadmap`
  already maps `KeyboardInterrupt` to rc 130 (`roadmap_cmd.py:603`); the handle
  must be closed on that path too, or a daemon thread ticks past the message.

## Testing

Hermetic, with the existing injection idioms — `_StubInvoker`
(`tests/test_roadmap.py:375`), `_GateRecorder` (`:362`), `max_stage_attempts=`,
and `NullReporter` for everything not asserting on output. No test spawns a real
backend; `tests/conftest.py:63`'s autouse gate already refuses one.

- **Ordering, four-stage success:** a recording reporter observes start → write
  per stage, in stage order, with the terminal line last and no line preceding
  the transition it reports.
- **Retry, in both loops:** a `_GateRecorder`-forced gate failure then success
  emits a retry notice naming `gates` — asserted once through `_run_stage` and
  once through `_run_bounded_stage_feedback`, since a single-route assertion is
  the incomplete sweep this plan's own risk names.
- **All four retry kinds, by mutation:** `invoke` (rc≠0), `parse` (unliftable
  reply), `gates`, and `authored-review-rows` (a reply minting a `feedback`
  row — the shape `tests/test_roadmap.py:3317` already drives) each surface
  their own kind, not a generic "retrying".
- **The non-retrying invalid path** (`RoadmapSourceAdmissionError`) reports a
  stage failure and **no** retry notice, proving the two are distinguished.
- **Exhaustion** reports each of the three attempts and one
  `stage-exhausted` terminal line, mirroring
  `tests/test_roadmap.py:6066`'s existing `[1,2,3]` attempt assertion.
- **The feedback-free route opens no step** — assert on the recording reporter
  that no call was reported for a re-gate that invokes nothing.
- **stdout is untouched:** a full run's captured stdout is byte-identical to
  today's for `completed`, `completed-no-change`, `stage-exhausted`, and
  `stage-invalid`; every lifecycle line is in stderr. Assert on the
  real-orchestrator-plus-real-render shape `tests/cli/test_roadmap_cmd.py:2060`
  already establishes.
- **`--view` routes are unaffected** — `--view summary` and
  `--view html --output -` still write only their page to stdout and emit no
  lifecycle line, since neither runs a stage.
- **The run log is unchanged:** replay an existing run-log assertion
  (`_Env.run_log_events`) and prove the event sequence, fields, and ordering are
  identical with the reporter attached.
- **Interrupt:** a `KeyboardInterrupt` mid-stage still exits 130 and leaves no
  live heartbeat thread.
- **Existing `tests/test_roadmap.py` and `tests/cli/test_roadmap_cmd.py` pass
  unmodified** except where a test is deliberately updated to inject a reporter
  — including `test_the_orchestrator_renders_no_operator_advice` (`:6766`),
  green and unedited.

## Acceptance criteria

- A four-stage run emits, on stderr and while still running, the accepted stage
  range, each stage's start, each retry with its own failure kind, each stage
  write, and exactly one terminal line naming one of the existing four
  `OUTCOMES`.
- An operator can distinguish a healthy long-running stage from a stalled
  process without `ps`, without `-v`/`--debug`, and without opening
  `.plan-tool/runs/<slug>/*.jsonl`.
- Every retry-consuming failure kind — `invoke`, `parse`, `gates`,
  `authored-review-rows` — is named live at the attempt that produced it; the
  non-retrying source-admission failure is never reported as a retry.
- Both attempt loops (`_run_stage`, `_run_bounded_stage_feedback`) report; the
  feedback-free re-gate opens no progress step.
- `plan_tool/progress.py` is unchanged, and the implementation adds no reporter
  class, event type, enum, or CLI flag.
- `OUTCOMES`, the `FAILURE_*` constants, `MAX_STAGE_ATTEMPTS`, retry semantics,
  artifact writes, exit codes, and the run-log JSONL are unchanged; stdout is
  byte-identical on every route, including all eight `--view` modes.
- No lifecycle line contains backend prompt or response text.
- `docs/ROADMAP_DEMO_ORCHESTRATION.md`'s *"Always open
  `.plan-tool/runs/<slug>/*.jsonl`"* instruction and its *"terminal error names
  only the final attempt's failure kind"* note are updated to describe what the
  terminal now shows, with the JSONL kept as the durable record rather than the
  live channel.
- `BACKLOG.md`'s "Emit concise progress status for long-running `roadmap`
  commands" entry is updated when the work ships, and its duplicate id is
  resolved so the reconciliation is unambiguous.

## Deferred

- BACKLOG #217's retained unusable reply, which would make a `parse` exhaustion
  diagnosable rather than merely visible.
- Progress output for the single-request roadmap routes, if an operator ever
  reports one of them running long enough to matter.
- A `--quiet` flag, if the new stderr lines prove unwanted in a real scripted
  run. Absent that evidence, redirecting stderr is the answer.
- Whether the two coexisting lifecycle vocabularies (`OUTCOMES` and the
  run-log's) should be reconciled. This seed adds to neither; unifying them is
  its own decision with its own compatibility surface.
