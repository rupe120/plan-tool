---
title: Batch Observability Forensics And View
intent: So an operator can diagnose a batch authoring call that died — the provider
  stream leaves a forensic record behind instead of vanishing with the call — and
  can tell whether an unfinished run is working, quiet, or dead without reading the
  run log by hand.
status: planning
priority: medium
enforce_step_tests: true
steps:
- id: 1
  title: Scrub secrets from raw transcript lines before they are written
  intent: Gives the raw provider stream its own scrubbing pass so a forensic transcript
    never becomes the one place unredacted tool inputs survive on disk.
  files:
  - plan_tool/run_log.py
  - tests/test_run_log.py
  complexity: medium
  change_type: feature
  status: current
- id: 2
  title: Replace the always-on verbatim transcript with a redacted, failure-only one
  intent: Leaves a forensic record behind for a call that actually died, without littering
    the run directory with transcripts for healthy calls.
  files:
  - plan_tool/launcher.py
  - tests/test_launcher.py
  complexity: high
  change_type: feature
  depends_on:
  - 1
  depends_on_notes:
    1: Supplies the raw-line redaction pass this step applies to each buffered line
      before writing it.
- id: 3
  title: Make repo_lock's pid-alive check public so runs show can use it
  intent: Gives the liveness view one shared answer to 'is that process still running?'
    instead of a second copy that would trip the duplication guard.
  files:
  - plan_tool/repo_lock.py
  - tests/test_repo_lock.py
  complexity: low
  change_type: refactor
- id: 4
  title: Show whether an unfinished run is working, quiet, or dead in runs show
  intent: Answers 'working, quiet, or dead?' for an unfinished run in one command,
    instead of making an operator read the JSONL by hand.
  files:
  - plan_tool/cli/runs.py
  - tests/test_cli.py
  complexity: medium
  change_type: feature
  depends_on:
  - 3
  depends_on_notes:
    3: Supplies the public pid-alive predicate, so the render calls one shared implementation
      rather than copying repo_lock's.
- id: 5
  title: Document the transcript and liveness fields and file the deferred work
  intent: Points an operator at the two new surfaces and records what this effort
    deliberately left out, so neither is discoverable only by reading the source.
  files:
  - README.md
  - RUNBOOK.md
  - docs/how-to/pipeline/run.md
  - BACKLOG.md
  complexity: medium
  change_type: non-code
  depends_on:
  - 2
  - 4
  depends_on_notes:
    2: Settles the transcript's filename, trigger set, and redaction behavior that
      the docs describe.
    4: Settles the liveness states — working, quiet, never spawned, dead — that the
      operator docs name.
---
# Batch Observability Forensics And View

## Overview

Re-plans the last three steps carved out of Batch Authoring Observability (source steps 10, 11, 12), all of which were left `pending` and never detailed. The work adds a raw NDJSON transcript that is written only when a call reaches a terminal bad outcome, a liveness view for an unfinished run in `runs show`, and the documentation plus backlog bookkeeping that records the new observability surface and what was deliberately left out. The transcript trigger is terminal outcomes only — `rc != 0`, `configured_timeout`, `silence_timeout`, or `spawn_failure` — and never the transient 300-second `claude_call_stall_suspected` marker; the `runs show` liveness signal keys on `run_start`'s plan-tool process pid rather than the most recent `backend_spawn` `child_pid`. These two decisions come from round-2 completeness-audit fixes on the source plan and are settled: do not re-derive them.

## Problem statement

A failed or stalled batch authoring call leaves nothing behind to diagnose it with — the provider stream is gone once the call dies, so there is no forensic record of what the backend was doing when it went. At the same time, an operator looking at a run directory for an unfinished run cannot answer the basic question "working, quiet, or dead?" without inspecting the run log by hand, and a call that emitted `claude_call_start` but never `backend_spawn` (the backend binary was not found) has the same start-with-no-progress signature as a genuine hang, so the two are indistinguishable. Writing a transcript for every call would fix the first problem by leaving forensic artifacts behind for healthy calls too, which is why the capture has to be conditioned on the outcome rather than switched on unconditionally. Neither surface is documented today, and the deferred work from this effort has no home in `BACKLOG.md`.

## Architecture

> **Seed/code ambiguity:** the seed names `claude_call_stall_suspected` and `claude_call_start` as bare symbols, and each resolves to several repository declarations (`plan_tool/run_log.py:claude_call_stall_suspected` vs `tests/test_launcher.py:claude_call_stall_suspected`; `plan_tool/progress.py:claude_call_start`, `plan_tool/run_log.py:claude_call_start`, and five test-module declarations). Both anchors are almost certainly the `plan_tool/run_log.py` event, but the seed must say so explicitly — please pin one `path:symbol` per anchor rather than leaving the choice to a reader.

> **Seed/code conflict:** the seed names `plan_tool/backend_runner.py` and the live snapshot file `in-flight.json` as existing paths this plan edits; neither is on disk. `in-flight.json` is nonetheless a real contract in the making — `plan_tool/run_log.py` already exports `IN_FLIGHT_FILENAME` and an atomic snapshot writer/reader, and `plan_tool/cli/runs.py` already imports `IN_FLIGHT_FILENAME` — so the missing file is the *snapshot instance*, not the mechanism. `backend_runner.py` has no counterpart at all; the seed's own dependency list says the backend events it carries are still `pending` outside this plan, so treat it as a module this effort's antecedents create.

Three pieces, matching the three carved steps.

**Conditional raw transcript.** `plan_tool/backend_runner.py`, `plan_tool/launcher.py`, and `plan_tool/run_log.py` gain the ability to save the raw NDJSON provider stream for a single call, written only once the call reaches a terminal outcome: `rc != 0`, `configured_timeout`, `silence_timeout`, or `spawn_failure`. A call that crossed the 300-second `claude_call_stall_suspected` marker and then recovered and finished normally is *not* a trigger — "stalls" here means the call ultimately died from silence, not that it was briefly suspected. The transcript applies its own redaction pass to each raw line before writing it. This is deliberately separate from step 9's redaction, which covers the summarized stream events and not this raw-line capture; this step scrubs the raw lines itself rather than assuming step 9 already did. `plan_tool/run_log.py` is the natural home for the write primitive: it already owns the run directory layout (`RUNS_REL`, `run_dir`) and the atomic write patterns, and it holds no first-party `plan_tool.*` imports, so keeping the transcript writer there preserves that leaf position. Note that its existing `append_event` path caps a single JSONL line at `_MAX_LINE_BYTES` (4096) and raises `RunLogLineTooLarge` rather than risk a torn write — a raw provider line can exceed that comfortably, so the transcript is a separate artifact with its own write path rather than more events on the run log.

**Liveness in `runs show`.** `plan_tool/cli/runs.py` renders an unfinished run's liveness from the run directory in a single command. The primary signal is `run_start`'s existing plan-tool process pid — "is anything still supervising this run" — because `backend_spawn`'s `child_pid` is only a detail about the *current* call: between phases with no backend call active, the last known `child_pid` has already exited normally even though the run is fine. A call that emitted `claude_call_start` but never `backend_spawn` renders as "never spawned," a distinct state from "stalled." This lands on the existing `runs show` sub-action, which already reads the run directory through `_iter_events` / `_load_events_with_skips` and already imports `IN_FLIGHT_FILENAME`, so liveness is another read-only summary over the same JSONL rather than a new command.

**Documentation and bookkeeping.** `README.md`, `RUNBOOK.md`, and `docs/how-to/pipeline/run.md` point an operator at the new fields; `BACKLOG.md` records what this effort deliberately left out.

The transcript work depends on the termination reason (source step 3), the redaction pass (source step 9), the `backend_spawn` / `backend_termination` / `run_interrupted` events (source step 4), and the live `in-flight.json` snapshot (source step 8) — all of which are still `pending` outside this plan.

Two `depends_on` edges in this plan's frontmatter connect steps that declare no production file in common, and the seed does not explain either one: step 2 (`plan_tool/launcher.py`) on step 1 (`plan_tool/run_log.py`), and step 4 (`plan_tool/cli/runs.py`) on step 3 (`plan_tool/repo_lock.py`). The first is consistent with the layering described above — `launcher.py` already imports from `run_log` (`ClaudeCallEnd`, `RunLogLineTooLarge`, `utc_now_iso`), so a launcher-side trigger would consume a `run_log`-side write primitive — but the seed never states it, and the step 4 → step 3 edge has no explanation in the seed at all: `repo_lock.py` appears nowhere in the seed's Architecture. Both edges are left as-is for a human reviewer rather than given a justification this seed did not supply.

## References

- [Claude Code CLI referencehttps: — Authoritative list of CLI flags and exit behavior, including --output-format stream-json and its --verbose requirement, which defines the raw stream the transcript captures.
- [Run Claude Code programmatically (headless mode)https: — Documents the newline-delimited JSON event stream emitted in headless runs, the shape an implementer must persist verbatim and redact line by line.
- [Anthropic Messages API — Streaminghttps: — Primary reference for the message_start / content_block_delta / message_stop event sequence carried inside the provider stream, needed to reason about what a truncated or silent transcript looks like.
- [Python subprocess — Popen, TimeoutExpired, and spawn errorshttps: — Defines returncode semantics, communicate(timeout=...) / TimeoutExpired, and the FileNotFoundError raised when the backend binary is absent — the exact distinction between rc != 0, configured_timeout, and spawn_failure.
- [Python os module — os.kill and ProcessLookupErrorhttps: — Specifies that signal 0 performs error checking without sending a signal, the standard primitive for probing whether run_start's plan-tool pid is still alive.
- [psutil documentation — pid_exists vs Process.is_runninghttps: — Explains the PID-reuse hazard and why is_running() is preferred over a bare pid check, directly relevant to trusting a recorded pid as a liveness signal in runs show.
- [JSON Lines (NDJSON) format specificationhttps: — The format contract for the transcript file — one valid JSON value per line, \n separators, trailing newline guidance — so partial writes from a killed call stay parseable.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

- Writing a transcript for calls that complete successfully — the capture is conditioned on a terminal bad outcome precisely so healthy calls leave no forensic artifacts behind.
- Treating the transient 300-second `claude_call_stall_suspected` marker as a transcript trigger; a call that crossed it and then finished normally writes nothing.
- Using the most recent `backend_spawn` `child_pid` as the liveness signal in `runs show`; the primary signal is `run_start`'s plan-tool process pid.
- Re-deriving either of those two decisions — they come from round-2 completeness-audit fixes on the source plan and are settled.
- Redacting the summarized stream events; that is step 9's job outside this plan. This work scrubs only the raw lines it writes itself.
- The source-plan work this effort depends on and does not deliver: the termination reason (source step 3), the redaction pass (source step 9), the `backend_spawn` / `backend_termination` / `run_interrupted` events (source step 4), and the live `in-flight.json` snapshot (source step 8) — all still `pending` outside this plan.

## Risks

- **Dependency shortfall.** Four antecedents — source steps 3, 4, 8, and 9 — are still `pending` outside this plan, and the transcript work consumes all of them. Severity: high; the transcript step is unimplementable until they land. No mitigation inside this plan; the ordering constraint is a precondition, not something this work can resolve.
- **Redaction gap on raw lines.** The transcript writes raw provider output, so anything the step's own redaction pass misses reaches disk verbatim. Severity: high. Mitigated by making redaction this step's own responsibility rather than assuming step 9's summarized-event pass already covered it — but the two passes then have to be kept honest independently, and nothing here checks that they agree.
- **`backend_runner.py` does not exist yet.** The seed names it as a file this plan edits, but there is no such module on disk. Severity: medium; unresolved — the plan needs the antecedent that creates it, or a decision about where the transcript hook actually lives.
- **Liveness is a heuristic, not a fact.** A live plan-tool pid says something is supervising the run, not that the run is making progress; a pid can also be recycled by the operating system. Severity: medium. Mitigated by rendering "never spawned" as a distinct state from "stalled" so the one genuinely diagnosable case is not folded into the ambiguous one.
- **Raw lines can exceed the run log's line cap.** `plan_tool/run_log.py` caps a single event line at `_MAX_LINE_BYTES` (4096) and raises `RunLogLineTooLarge` rather than write a torn record; a raw provider line can be larger. Severity: medium. Mitigated by writing the transcript as its own artifact with its own write path rather than as run-log events.

## Testing

Test files named by the carved scope: `tests/test_backend_runner.py`, `tests/test_launcher.py`, `tests/test_run_log.py` for the conditional transcript, and `tests/test_cli.py` for the `runs show` liveness rendering. The two settled decisions are the ones worth pinning as explicit carve-outs rather than leaving to prose: that a call which crossed the `claude_call_stall_suspected` marker and then finished normally writes *no* transcript, and that liveness keys on `run_start`'s plan-tool process pid rather than the last `backend_spawn` `child_pid`. "Never spawned" (a `claude_call_start` with no `backend_spawn`) needs its own assertion distinguishing it from "stalled."

Both carve-outs are negative claims — no transcript, not the `child_pid` — which are exactly the assertions a suite tends to leave to prose and which stay green when the rule is later widened to swallow them. Verify each by mutation rather than by reading: fold the recovered-stall case into the triggering arm, and fold `child_pid` into the liveness signal, and confirm a test goes red each time.

Default to unit tests per the project convention; reserve `@pytest.mark.integration` for the `runs show` rendering if it has to be driven through the CLI entry point rather than through the summarizer directly.

**Per-step test strategy** (derived from each step's `change_type`):

- step 1 (feature) — tests covering the behavior this step changes; green before completion.
- step 2 (feature) — tests covering the behavior this step changes; green before completion.
- step 3 (refactor) — tests covering the behavior this step changes; green before completion.
- step 4 (feature) — tests covering the behavior this step changes; green before completion.
- step 5 (non-code) — verification appropriate to the artifacts rather than unit tests.

## Acceptance criteria

- A call that ends with `rc != 0`, `configured_timeout`, `silence_timeout`, or `spawn_failure` leaves a raw NDJSON transcript in the run directory.
- A call that completes normally leaves no transcript, including one that crossed the 300-second `claude_call_stall_suspected` marker and then recovered.
- Every line written to the transcript has passed this step's own redaction pass, independent of step 9's summarized-event redaction.
- `plan-tool runs show` on an unfinished run reports its liveness from `run_start`'s plan-tool process pid, not from the most recent `backend_spawn` `child_pid`.
- `plan-tool runs show` renders a call with a `claude_call_start` and no `backend_spawn` as "never spawned," distinct from "stalled."
- `README.md`, `RUNBOOK.md`, and `docs/how-to/pipeline/run.md` each describe the new transcript artifact and the `runs show` liveness fields.
- `BACKLOG.md` carries an entry for the work this effort deliberately left out.

## Deferred

Work postponed rather than permanently excluded — unlike `## Out of scope`, each item here can come back, and step 5 records them in `BACKLOG.md`.

- **The `backend_runner.py`-side transcript hook.** The seed names the module as a file this effort edits and no such module is on disk, so no step claims it. Blocked on the antecedent that creates it, and on the decision about where the capture hook belongs — the matching risk carries the same unresolved question.
- **A cross-check that the transcript's raw-line redaction and source step 9's summarized-event redaction agree.** Each pass stays independently responsible for its own output here; proving the two stay honest against one shared secret corpus is separate work, and it cannot be written until step 9 lands.
- **Distinguishing a recycled pid from a live one in `runs show`.** Liveness ships as an acknowledged heuristic over `run_start`'s pid; recording a process start time (or an equivalent identity check) alongside that pid to close the PID-reuse hole changes what `run_start` writes and is its own change.
- **Pinning one `path:symbol` anchor each for `claude_call_stall_suspected` and `claude_call_start`.** Both almost certainly mean the `plan_tool/run_log.py` event, but the plan does not assert it; resolving the ambiguity belongs to the seed rather than to an implementer guessing mid-step.
- **A rationale for the two cross-module `depends_on` edges** — step 2 (`plan_tool/launcher.py`) on step 1 (`plan_tool/run_log.py`), and step 4 (`plan_tool/cli/runs.py`) on step 3 (`plan_tool/repo_lock.py`). Left for a human reviewer rather than given a justification the seed never supplied.
- **The source plan's remaining deferrals that touch this surface:** configurable per-command silence/stall thresholds, a repository policy for which tool summaries are safe across backends beyond the shared redaction pass, a `runs watch` polling/tailing mode, and per-verb phase/attempt event labels for `create`/`annotate`/`detail`/`jira`/`lessons`/`review`. Each is its own effort and none is needed for the two surfaces this plan delivers.
