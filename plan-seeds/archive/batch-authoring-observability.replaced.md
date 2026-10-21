> **Replaced**: this file has been superseded by `docs/implementation-plans/2-batch-authoring-observability.md`.
> Preserved here for history; do not edit.

# Seed: batch-authoring call observability

## Outcome

Batch authoring calls that share `plan_tool.shell.claude_invoke` — starting
with `roadmap`, the initial rollout target — expose the same in-progress
liveness signal `run` already gets from `launcher._run_streaming_once`:
heartbeat, stall suspicion, a safety-net silence kill, and a normalized
termination reason, all durable in the JSONL run log and `in-flight.json`.
`claude_invoke`'s `(rc, stdout)` contract and all existing roadmap/detail/audit
parsing and gate logic are unchanged.

## In scope

- A shared Popen-based streaming runner usable by both `claude_invoke`'s
  `_run_once` and `launcher._run_streaming_once`, replacing `_run_once`'s
  buffered `subprocess.run`.
- New run-log event types (`backend_spawn`, `backend_termination`,
  `run_interrupted`) and wiring the existing `claude_call_progress` /
  `claude_call_stall_suspected` events into the batch path.
- A closed termination-reason enum recorded on `run_end`.
- Keeping `in-flight.json` current through a call's life, not just at start.
- `runs show` rendering current liveness from JSONL + the in-flight snapshot.
- Raw-NDJSON transcript capture, triggered automatically by a failed or
  stalled call (no pre-invocation opt-in flag) and redacted by a shared pass.
- Net-new `KeyboardInterrupt` handling around `roadmap`'s stage-invocation
  loop — `cli/roadmap_cmd.py` has none today (contrast `cli/run_cmd.py`,
  which already catches it, though only to stamp rc=130 into a generic
  `run_end`, not to emit `run_interrupted` or explicitly reap the child).

## Out of scope

- Percent-complete estimation for a model call — liveness only.
- Any change to roadmap semantics, gates, retry budgets, feedback, or seed
  invalidation behavior.
- Changing the default (unbounded) total-duration timeout for any command.
  The new silence-based kill is a distinct mechanism (see Allowed behavior
  changes) — it must not be described or implemented as a global timeout.
- Raw provider transcripts as a default durable artifact.
- A browser or network consumer of the event stream.
- Wiring `create`, `annotate`, `jira`, and `lessons` with their own
  phase/attempt event labels — they inherit the shared-runner mechanics
  automatically the moment `claude_invoke` switches (see Architecture), but
  giving each of them roadmap-quality operator rendering is deferred.
- `runs watch` (a tailing/follow mode) — `runs show`'s one-shot render is the
  deliverable here.
- Making per-command silence/stall thresholds configurable.

## Overview

`roadmap`'s stage-generation calls, like every other batch-authoring call
routed through `plan_tool.shell.claude_invoke`, run the backend under
buffered `subprocess.run` and parse its `stream-json` output only after the
child exits. The JSONL run log records `claude_call_start`, then nothing,
then a terminal `claude_call_end`. `launcher._run_streaming_once` already
solves this for `run`/`apply_finding`: it pumps `stream-json` incrementally,
emits a 20-second heartbeat, flags a 300-second stall suspicion, and kills a
child silent for 900 seconds — but that capability isn't reachable from the
batch path.

## Problem statement

An operator watching a long `roadmap` stage call cannot tell, from the run
directory alone, whether the backend is working, has gone quiet, or is
already dead. `claude_invoke` is shared by seven call sites (`annotate.py`,
`create.py`, `detail.py`, `jira.py`, `lessons.py`, `review.py`,
`roadmap.py`); none of them get incremental visibility today.

## Architecture

- **The runner extraction is global, not staged per command.** `claude_invoke`
  is one function; there is no per-caller gate proposed or needed. The moment
  the "wire batch calls" step lands, every one of the seven callers above gets
  the new Popen-based runner, its heartbeat, and its silence kill —
  simultaneously. "Roll out by command class" (roadmap, then detail, then
  reconciliation/audit) describes staging **richer event wiring and operator
  rendering** per call site, not staged activation of the runner itself —
  these are different axes and must not be conflated in the step graph.
- **The 900-second silence kill applies unconditionally, to every batch
  caller, from the moment the runner switches over.** This is a deliberate,
  allowed behavior change (see below), not an accidental side effect —
  `_run_streaming_once` already applies its kill ladder unconditionally even
  with no run-log attached (the safety net is intentionally outside the
  `run_logger is not None` branch), and this effort adopts the same stance for
  batch calls rather than gating it behind per-caller opt-in.
- **Configured-timeout enforcement (`PLAN_TOOL_CLAUDE_TIMEOUT` /
  `scoped_claude_timeout`) does not exist on the streaming side today** — only
  the buffered `_run_once` path enforces it, via `subprocess.run(timeout=...)`.
  The shared runner adds this as new functionality (an elapsed-time check
  alongside the existing silence check in the same monitor thread), not a
  reused capability.
- **Observer wiring**: `_run_streaming_once`'s callers already pass a
  `run_logger` directly; `claude_invoke`'s callers cannot — its invoker
  protocols (`StageInvoker`, `DetailInvoker`, …) are fixed at
  `Callable[[str], tuple[int, str]]` across many call sites and must not
  change. The shared runner takes an explicit observer (a narrow protocol:
  spawn / stream-event / progress / stall / termination callbacks).
  `_run_streaming_once`'s existing callers adapt their `run_logger` into one
  directly; `claude_invoke` builds one from the ContextVar-based active sink
  (`shell.get_active_sink()` / `RunLogWriter.bind_shell_sink`), widened to
  carry more than the current `ClaudeCallEnd`-only contract.
- New event types on `run_log.py` — `backend_spawn` (backend, transport,
  child_pid, effective_timeout_ms, prompt_bytes), `backend_termination`
  (reason, signal_or_timeout, elapsed_ms, silent_ms), `run_interrupted`
  (source, signal, active_phase, active_attempt). Closed termination-reason
  enum: `completed`, `configured_timeout`, `silence_timeout`,
  `operator_interrupt`, `spawn_failure`, `backend_nonzero`, `unknown`.
  `run_end` carries a normalized `termination_reason` alongside its existing
  compatibility fields.
- `in-flight.json` updates atomically at phase start, backend spawn, each
  heartbeat, and termination, staying a small current-status projection; the
  JSONL stays append-only and authoritative for history.
- Structured `claude_stream_event` payloads stay summarized: tool type and a
  redacted path/pattern/command summary only, never stdin prompt content,
  environment values, credentials, or complete provider messages. A
  suppressed field logs a `redacted`/`omitted` marker, never a silent drop.
  Raw NDJSON transcript capture fires automatically when a call fails or
  stalls — not gated behind an operator flag set before invocation — and is
  stored beside the run log. A call that completes normally never gets one,
  which is what keeps it from becoming a default durable artifact.
- Ordering constraint on the work itself: characterize today's start/end-only
  behavior in tests before touching anything; extract the shared runner
  byte-compatible with `run`'s existing behavior before wiring `claude_invoke`
  to it; add termination classification (including `roadmap`'s net-new
  `KeyboardInterrupt` handling) after the runner is live; refresh
  `in-flight.json` after termination classification exists to report against;
  land redaction before any transcript-capture flag ships.

## Allowed behavior changes

- Every `claude_invoke` caller (not just `roadmap`) gains a 900-second
  silence-based child termination it does not have today. No caller currently
  relies on silent-but-alive behavior past that window; if one is found during
  characterization testing, that caller's scoped timeout wins and this seed's
  owner is notified before the runner switch lands, not after.
- `run`'s existing bare `KeyboardInterrupt` → generic `run_end(outcome=
  "error")` handling gains a distinct `run_interrupted` event and explicit
  child terminate/reap; this changes what `run_end` records for an
  interrupted run without changing its exit code (130).

## Allowed reorganization

`launcher._run_streaming_once`'s Popen/pump/heartbeat logic moves to a
neutral, leaf-level module shared with `shell.claude_invoke`. No other module
boundary changes.

## Risks

- The universal silence kill (see Allowed behavior changes) could terminate a
  legitimate batch call outside `roadmap`/`detail`/`review` whose usage
  pattern includes a long single tool-use burst with no incremental stream
  event. Mitigate by keeping the threshold centrally defined and
  test-injectable (already required), and treat any such caller surfaced
  during characterization as a signal to raise its scoped threshold, not to
  abandon the global kill.
- Two genuinely different retry layers exist per roadmap call: the
  roadmap-level attempt loop (`_run_stage`, parse/gate failures) and
  `claude_invoke`'s own internal rate-limit/transient retry loop, which can
  spawn more than one subprocess per single `claude_call_start`/
  `claude_call_end` bracket. The event model must account for multiple
  `backend_spawn`/progress sequences nesting inside one bracket — this is
  compatible with the sink's existing phase/attempt-override behavior, but is
  not automatic and needs its own test.
- Migrating `_run_streaming_once` risks a behavior regression in `run` — no
  caller of the shared runner may observe stdout/stderr/timing changes versus
  today.

## Testing

Prove: full event ordering on a roadmap call (start, spawn, stream activity,
periodic progress, end, phase end, run end); growing `silent_ms` with reset on
stream activity; exactly one stall marker per call; a 900-second-silent call
is reaped and records `silence_timeout` with no extra-budget retry;
`PLAN_TOOL_CLAUDE_TIMEOUT` records `configured_timeout` distinctly from
`silence_timeout`; Ctrl-C records `run_interrupted` and leaves no in-flight
snapshot or orphan child, for both `roadmap` and `run`; gate-failure/retry
logs still pair the right phase/attempt with each terminal call event,
including when `claude_invoke`'s internal retry loop fires more than once per
bracket; usage/cache/request-id/cost fields stay populated; a known secret
fixture never reaches JSONL, verbose terminal output, or an opt-in transcript;
concurrent runs don't clobber each other's snapshot/log state; `runs show`
renders an incomplete/stalled run without a live PID.

## Acceptance criteria

The next time a roadmap backend call goes quiet, an operator can tell from the
run directory alone: whether the child started and which phase/attempt it
belongs to; elapsed and silent duration and the last safe observable
activity; whether the call crossed the stall-investigation threshold; and
whether it ended normally, timed out, was silence-terminated, or was
interrupted. No change weakens existing prompt, credential, artifact, or
run-log size/atomicity protections.

## Deferred

Configurable per-command silence/stall thresholds; a repository policy
restricting which tool summaries are safe across Claude/Codex/future backends
beyond the shared redaction pass; a `runs watch` polling/tailing mode; giving
`create`/`annotate`/`jira`/`lessons` their own phase/attempt event labels and
`runs show` rendering.
