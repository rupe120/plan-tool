> **Auto-archived**: this plan was swept on 2026-08-18 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 1 — Extract behavior-preserving roadmap command lifecycle setup

## Summary

Extract the shared run-log ownership and terminal cleanup used by roadmap commands into one private lifecycle helper in `plan_tool/roadmap.py`. Adapt `run_roadmap()` and `apply_roadmap_seeds()` to use that helper without changing their public signatures, emitted records, result mapping, or injected-logger behavior. Keep stage-attempt logging in `_run_stage()` and keep apply’s aggregate event where they are. On green, existing stage runs and `--apply` produce the same lifecycle records and clean up their owned `in-flight.json` snapshot on every terminal path.

## Table of Contents

- [Summary](#summary) — The change and its observable result.
- [Table of Contents](#table-of-contents) — Links to each section.
- [Why](#why) — Why lifecycle ownership needs one reusable home.
- [Input](#input) — Existing lifecycle contracts the refactor preserves.
- [Files (creates vs edits)](#files-creates-vs-edits) — The two files this step changes.
- [Implementation](#implementation) — The lifecycle extraction and its invariants.
- [Tests](#tests) — Regression coverage for unchanged command behavior.
- [Acceptance criteria](#acceptance-criteria) — Checkable completion conditions.
- [References](#references) — Primary references for interrupt and snapshot behavior.
- [Applicable guardrails](#applicable-guardrails) — Scope limits that bind this refactor.
- [Deferred](#deferred) — Later observability work intentionally left out.

## Why

`plan_tool/roadmap.py:run_roadmap()` and `plan_tool/roadmap.py:apply_roadmap_seeds()` each own the same essential lifecycle: validate the slug before opening a log, create a `RunLogWriter` only when the caller did not supply one, retain a result or exception, and close only the writer they created from one `finally:` path. Later seed actions need this ownership model, but copying it again would make terminal cleanup and injected-writer rules drift. Extracting the shared shape now gives later steps one safe extension point while preserving the established stage and apply records.

## Input

- **Current ownership contract:** `plan_tool/roadmap.py:run_roadmap()` and `plan_tool/roadmap.py:apply_roadmap_seeds()` each accept `run_logger`, create `plan_tool/run_log.py:RunLogWriter` only when it is absent, and leave a supplied logger open for its caller.
- **Current terminal mapping:** `run_roadmap()` maps `OUTCOME_COMPLETED` to return code `0` and stage exhaustion to `1`; `apply_roadmap_seeds()` maps `APPLY_OUTCOME_REFUSED` to `2` and its other current outcomes to `0`.
- **Current failure contract:** `plan_tool/roadmap.py:_error_run_end_fields()` maps `KeyboardInterrupt` to the existing interrupt return code and safe error text; other exceptions keep their current error mapping and still propagate.
- **Current inner logging boundary:** `plan_tool/roadmap.py:_run_stage()` owns per-attempt `claude_call_start`, shell-sink binding, failure, and gate events. The extracted command lifecycle must not move or wrap those events.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `plan_tool/roadmap.py` — Extract the common owned-writer setup and single terminal `run_end()` path used by `run_roadmap()` and `apply_roadmap_seeds()`.
  - `tests/test_roadmap.py` — Characterize the unchanged stage-run and apply lifecycle behavior, including ownership, error, and interrupt paths.

## Implementation

- **Make the foundational logic one owned roadmap-command lifecycle.** Extract a private helper in `plan_tool/roadmap.py` that centralizes the repeated `RunLogWriter.start()` ownership decision and owned-writer teardown. One approach is a small context or handle that gives the command body its effective logger and accepts its existing terminal outcome and return-code mapping; keep the exact shape flexible if it preserves the rules below.

- **Preserve slug validation before writer startup.** `run_roadmap()` and `apply_roadmap_seeds()` currently call `roadmap_dir()` before opening a slug-scoped log. Keep that ordering, whether the check remains at each public entry point or becomes a documented helper precondition. An invalid slug must still fail without creating a run record or snapshot.

- **Keep terminal-result policy with each command.** The shared helper should own lifecycle mechanics, not decide whether a stage result is completed or exhausted, or whether an apply result is refused. Let `run_roadmap()` and `apply_roadmap_seeds()` retain their current result-specific outcome and return-code choices, then hand those facts to the lifecycle owner for its one `RunLogWriter.run_end()` call.

- **End only a writer this command started.** Preserve `RunLoggerLike` injection: a caller-supplied logger remains available to the caller after `run_roadmap()` or `apply_roadmap_seeds()` returns or raises. The helper must not add a second `run_end()` call around the stage writer, the apply writer, or a supplied test writer.

- **Preserve current start configuration.** Keep `run_roadmap()`’s `RunLogWriter.start()` command, empty argv, and `from_stage` flags unchanged. Keep `apply_roadmap_seeds()`’s apply-mode flags and `roadmap_seed_apply_result` event unchanged. Do not add context fields, materialization phases, or new event kinds in this refactor.

- **Preserve all terminal paths.** Route successful returns, stage exhaustion, apply refusal, ordinary exceptions, and `KeyboardInterrupt` through the existing owned-writer cleanup behavior. Continue to use `_error_run_end_fields()` for exception terminal records, re-raise the original exception, and let `RunLogWriter.run_end()` remove the owned snapshot.

- **Leave inner and future command work separate.** Keep `_run_stage()` as the owner of backend-attempt lifecycle events, and do not change `materialize_plan_seed()`, `materialize_and_diff_one_plan()`, or `refresh_roadmap_seeds()` yet. The extracted helper should be small enough for steps 4 and 5 to adopt later without changing stage or apply behavior now.

- **Reject broad consolidation.** Do not move artifact loading, seed validation, promotion, refresh reporting, or backend invocation policy into the lifecycle helper. Those operations have different result contracts and belong to their existing functions.

## Tests

### Tests for this step

- `TestRunLog::test_stage_run_lifecycle_keeps_existing_start_flags_events_and_terminal_result` — Assert a successful injected stage run retains its current run-start flags, stage event sequence, completed outcome, and snapshot cleanup.
- `TestRunLog::test_stage_run_preflight_error_ends_the_owned_writer_once` — Assert a known preflight error still emits its existing error terminal record and removes the owned `in-flight.json`.
- `TestRunLog::test_stage_run_keyboard_interrupt_is_reraised_after_owned_writer_cleanup` — Assert an interrupt keeps its existing error mapping, removes the owned snapshot, and propagates to the CLI boundary.
- `TestRunLog::test_caller_supplied_roadmap_logger_is_not_ended_by_the_command` — Assert `run_roadmap()` records through an injected writer without emitting that writer’s terminal event or removing its snapshot.
- `TestApplyRoadmapSeeds::test_apply_lifecycle_keeps_existing_flags_aggregate_event_and_terminal_result` — Assert a successful apply keeps its current start flags, aggregate apply event fields, terminal outcome, and snapshot cleanup.
- `TestApplyRoadmapSeeds::test_apply_error_ends_the_owned_writer_once` — Assert an exception from the apply path retains its current error terminal behavior and removes the owned snapshot.

Every listed test must be green before this refactor is complete.

## Acceptance criteria

- `plan_tool/roadmap.py:run_roadmap()` and `plan_tool/roadmap.py:apply_roadmap_seeds()` use one private lifecycle owner for owned `RunLogWriter` setup and terminal cleanup.
- A normal stage run retains its current `run_start`, stage events, terminal outcome, return-code mapping, and one completed JSONL record.
- `--apply` retains its current start flags, `roadmap_seed_apply_result` fields, terminal outcome, and return-code mapping.
- An owned writer emits exactly one `run_end()` on success, refusal or exhaustion, ordinary exception, and interrupt paths, then removes its matching `in-flight.json`.
- A caller-supplied `run_logger` is never ended or cleaned up by either public roadmap command.
- Invalid slug validation still happens before any writer startup.
- `plan_tool/roadmap.py:_run_stage()` remains the sole owner of per-attempt backend lifecycle events.
- `uv run pytest tests/test_roadmap.py -q` passes.

## References

- [Python signal — Asynchronous Event Handlers](https://docs.python.org/3.13/library/signal.html#general-rules) — Confirm the `SIGINT` to `KeyboardInterrupt` behavior the lifecycle must preserve.
- [Python os.replace](https://docs.python.org/3.13/library/os.html#os.replace) — Review the atomic snapshot-publication behavior owned by `RunLogWriter`, which this extraction must leave unchanged.

## Applicable guardrails

- **The plan’s step intent, existing stage and apply records:** Preserve the current stage-run and `--apply` lifecycle output; this step only creates a reusable owner.
- **The plan’s `## Out of scope`, seed behavior:** Do not change seed prompts, validation, retries, state, draft locations, promotion, or refresh-report behavior while extracting lifecycle setup.
- **The plan’s `## Out of scope`, observability surface:** Do not add a general logging rollout, new monitoring surface, or materialization-specific lifecycle records in this step.
- **The plan’s `## Out of scope`, redacted data:** Do not add payloads or fields that could persist seed bodies, prompts, replies, or tool input.

## Deferred

- Optional writer context and unchanged-record compatibility for opt-out callers — step 2 owns this writer feature.
- Redacted materialization attempt, retry, and backend-observer events — step 3 owns this behavior.
- Lifecycle adoption by `--materialize` and `--refresh-seeds` — steps 4 and 5 own those command paths.
