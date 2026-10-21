> **Replaced**: this file has been superseded by `docs/implementation-plans/2-batch-observability-forensics-and-view.md`.
> Preserved here for history; do not edit.

## Overview

Re-plans the last three steps carved out of Batch Authoring Observability (source steps 10, 11, 12), all of which were left `pending` and never detailed. The work adds a raw NDJSON transcript that is written only when a call reaches a terminal bad outcome, a liveness view for an unfinished run in `runs show`, and the documentation plus backlog bookkeeping that records the new observability surface and what was deliberately left out. The transcript trigger is terminal outcomes only — `rc != 0`, `configured_timeout`, `silence_timeout`, or `spawn_failure` — and never the transient 300-second `claude_call_stall_suspected` marker; the `runs show` liveness signal keys on `run_start`'s plan-tool process pid rather than the most recent `backend_spawn` `child_pid`. These two decisions come from round-2 completeness-audit fixes on the source plan and are settled: do not re-derive them.

## Problem statement

A failed or stalled batch authoring call leaves nothing behind to diagnose it with — the provider stream is gone once the call dies, so there is no forensic record of what the backend was doing when it went. At the same time, an operator looking at a run directory for an unfinished run cannot answer the basic question "working, quiet, or dead?" without inspecting the run log by hand, and a call that emitted `claude_call_start` but never `backend_spawn` (the backend binary was not found) has the same start-with-no-progress signature as a genuine hang, so the two are indistinguishable. Writing a transcript for every call would fix the first problem by leaving forensic artifacts behind for healthy calls too, which is why the capture has to be conditioned on the outcome rather than switched on unconditionally. Neither surface is documented today, and the deferred work from this effort has no home in `BACKLOG.md`.

## Architecture

Three pieces, matching the three carved steps.

**Conditional raw transcript.** `plan_tool/backend_runner.py`, `plan_tool/launcher.py`, and `plan_tool/run_log.py` gain the ability to save the raw NDJSON provider stream for a single call, written only once the call reaches a terminal outcome: `rc != 0`, `configured_timeout`, `silence_timeout`, or `spawn_failure`. A call that crossed the 300-second `claude_call_stall_suspected` marker and then recovered and finished normally is *not* a trigger — "stalls" here means the call ultimately died from silence, not that it was briefly suspected. The transcript applies its own redaction pass to each raw line before writing it. This is deliberately separate from step 9's redaction, which covers the summarized stream events and not this raw-line capture; this step scrubs the raw lines itself rather than assuming step 9 already did.

**Liveness in `runs show`.** `plan_tool/cli/runs.py` renders an unfinished run's liveness from the run directory in a single command. The primary signal is `run_start`'s existing plan-tool process pid — "is anything still supervising this run" — because `backend_spawn`'s `child_pid` is only a detail about the *current* call: between phases with no backend call active, the last known `child_pid` has already exited normally even though the run is fine. A call that emitted `claude_call_start` but never `backend_spawn` renders as "never spawned," a distinct state from "stalled."

**Documentation and bookkeeping.** `README.md`, `RUNBOOK.md`, and `docs/RUN_FLOW.md` point an operator at the new fields; `BACKLOG.md` records what this effort deliberately left out.

The transcript work depends on the termination reason (source step 3), the redaction pass (source step 9), the `backend_spawn` / `backend_termination` / `run_interrupted` events (source step 4), and the live `in-flight.json` snapshot (source step 8) — all of which are still `pending` outside this plan.

## Testing

Test files named by the carved scope: `tests/test_backend_runner.py`, `tests/test_launcher.py`, `tests/test_run_log.py` for the conditional transcript, and `tests/test_cli.py` for the `runs show` liveness rendering. The two settled decisions are the ones worth pinning as explicit carve-outs rather than leaving to prose: that a call which crossed the `claude_call_stall_suspected` marker and then finished normally writes *no* transcript, and that liveness keys on `run_start`'s plan-tool process pid rather than the last `backend_spawn` `child_pid`. "Never spawned" (a `claude_call_start` with no `backend_spawn`) needs its own assertion distinguishing it from "stalled."
