> **Replaced**: this file has been superseded by `docs/implementation-plans/2-batch-observability-forensics-and-view.md`.
> Preserved here for history; do not edit.

<!-- plan-tool scope-out carved-seed
source: docs/implementation-plans/2-batch-authoring-observability.md
carved_steps: 10, 11, 12
-->

# Plan seed: carved steps 10..12 from Batch Authoring Observability

This is a `plan-tool create --from-existing` input. It re-plans **only the carved region** in the **Scope to re-plan** sections below (one per carved step). The **Done-context**, **Upstream prerequisites**, and **External prerequisites** sections are already-implemented context, not work to re-plan.

Source plan intent: Batch authoring calls that share `plan_tool.shell.claude_invoke` — starting with `roadmap`, the initial rollout target — expose the same in-progress liveness signal `run` already gets from `launcher._run_streaming_once`: heartbeat, stall suspicion, a safety-net silence kill, and a normalized termination reason, all durable in the JSONL run log and `in-flight.json`. `claude_invoke`'s `(rc, stdout)` contract and all existing roadmap/detail/audit parsing and gate logic are unchanged.. State the re-plan's own Outcome; do not inherit this as the new plan's purpose.

## Scope to re-plan (source step 10)

**Save a raw NDJSON transcript only when a call fails or stalls**

Intent: Gives a failed or stalled call the full provider stream for forensics without leaving transcripts behind for healthy calls. The trigger is a terminal outcome only — `rc != 0`, `configured_timeout`, `silence_timeout`, or `spawn_failure` — never a call that merely crossed the 300-second `claude_call_stall_suspected` marker and then recovered and finished normally; "stalls" in the title means the call ultimately died from silence, not that it was ever briefly suspected. Applies the same redaction pass to each raw line before it is written to the transcript file — step 9's pass covers the summarized stream events, not this separate raw-line capture, so this step scrubs the raw lines itself rather than assuming step 9 already did.

Files:
- plan_tool/backend_runner.py
- plan_tool/launcher.py
- plan_tool/run_log.py
- tests/test_backend_runner.py
- tests/test_launcher.py
- tests/test_run_log.py

Change type: feature

_The carved step was never detailed; re-plan scope comes from the carved frontmatter only._

## Done-context (already done — do not re-plan; source step 10)

Everything in this section is **already implemented** done-context. Do **not** re-plan or re-implement it.

The carved step was left **attempted/partial** (status `pending`) — account for this in the re-plan, but treat its work (in **Scope to re-plan** above) as not yet complete.

## Scope to re-plan (source step 11)

**Show liveness for an unfinished run in runs show**

Intent: Answers 'working, quiet, or dead?' from the run directory in a single command. Liveness keys on `run_start`'s existing plan-tool process pid — "is anything still supervising this run" — as the primary signal; `backend_spawn`'s `child_pid` is a secondary detail about the current call, since between phases with no backend call active the last known child_pid has already exited normally even though the run is fine. A call that emitted `claude_call_start` but never `backend_spawn` (the backend binary wasn't found) renders as "never spawned," distinct from "stalled" — the same start-with-no-progress signature would otherwise be indistinguishable from a genuine hang.

Files:
- plan_tool/cli/runs.py
- tests/test_cli.py

Change type: feature

_The carved step was never detailed; re-plan scope comes from the carved frontmatter only._

## Done-context (already done — do not re-plan; source step 11)

Everything in this section is **already implemented** done-context. Do **not** re-plan or re-implement it.

The carved step was left **attempted/partial** (status `pending`) — account for this in the re-plan, but treat its work (in **Scope to re-plan** above) as not yet complete.

## Scope to re-plan (source step 12)

**Document the new observability surface and file the deferred work**

Intent: Points an operator at the new fields and records what this effort deliberately left out.

Files:
- README.md
- RUNBOOK.md
- docs/RUN_FLOW.md
- BACKLOG.md

Change type: non-code

_The carved step was never detailed; re-plan scope comes from the carved frontmatter only._

## Done-context (already done — do not re-plan; source step 12)

Everything in this section is **already implemented** done-context. Do **not** re-plan or re-implement it.

The carved step was left **attempted/partial** (status `pending`) — account for this in the re-plan, but treat its work (in **Scope to re-plan** above) as not yet complete.

## External prerequisites (not done yet)

- step 3 [pending]: Add a configured-timeout kill and a termination reason to the shared runner — consumes: Supplies the termination reason that decides whether a transcript is written at all.
- step 9 [pending]: Redact tool-input summaries in all three backend parsers — consumes: Redaction must land before any raw provider text becomes a durable artifact.
- step 4 [pending]: Add the backend_spawn, backend_termination and run_interrupted run-log events
- step 8 [pending]: Keep in-flight.json current for the whole life of a call — consumes: Supplies the live snapshot fields; run_log.read_in_flight has no production consumer before this step.

## Provenance

- Source plan: docs/implementation-plans/2-batch-authoring-observability.md
- Carved steps: 10, 11, 12
- **Prior design work on these steps already happened — read it before
  re-planning, don't re-derive it.** The `intent:` text carried into each
  "Scope to re-plan" section above already reflects two rounds of hand-applied
  completeness-audit fixes, not the original `create`-authored draft:
  - Commit `d48d8a1b` — initial 12-step decomposition from
    `plan-tool create --model opus --from-existing`.
  - Commit `6e674648` — round-1 audit fixes. Step 10 gained its own raw-line
    redaction requirement (distinct from step 9's summary-level redaction).
  - Commit `050aea18` — round-2 audit fixes, the more load-bearing round for
    this carved region: step 10's transcript trigger was pinned to terminal
    outcomes only (`rc != 0`, `configured_timeout`, `silence_timeout`,
    `spawn_failure`), explicitly excluding the transient 300-second
    `claude_call_stall_suspected` marker — a real ambiguity the audit caught
    (a call that stalls then recovers is not a transcript trigger). Step 11
    gained the liveness-pid decision (key on `run_start`'s plan-tool process
    pid, not the last `backend_spawn` `child_pid`) and the "never spawned" vs.
    "stalled" distinction for an exec-not-found backend.
  - Completeness reports grounding those fixes:
    `docs/implementation-plans/plan-details/batch-authoring-observability/reports/20260812-165729-completeness.md`
    (findings `transcript-capture-trigger`, `runs-show-liveness-pid`,
    `exec-not-found-liveness-gap`) and
    `docs/implementation-plans/plan-details/batch-authoring-observability/reports/20260812-162406-completeness.md`
    (finding `transcript-redaction-gap`).
  - Re-auditing this re-plan from scratch without reading the above risks
    re-discovering the same three findings at the cost of another audit round.
