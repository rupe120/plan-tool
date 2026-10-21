> **Auto-archived**: this plan was swept on 2026-08-18 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 2 — Add an optional per-run context envelope to the shared run-log writer

## Summary

Add an optional, writer-owned context envelope to `plan_tool/run_log.py:RunLogWriter` and make it reach run-start, writer-emitted JSONL events, and `in-flight.json` snapshots. Extend step 1’s private roadmap lifecycle owner in `plan_tool/roadmap.py` so later seed-action commands can opt in without changing current stage-run or apply behavior. Keep the envelope flat and mutable only through the writer, so a row’s active plan ID can change without stale snapshot data. On green, context-enabled runs carry the defined attribution fields everywhere, while all current callers that omit context keep the same records and snapshots.

## Table of Contents

- [Summary](#summary) — The change and its observable result.
- [Table of Contents](#table-of-contents) — Links to each section.
- [Why](#why) — Why shared writer context is needed.
- [Input](#input) — Existing writer and lifecycle contracts this step extends.
- [Files (creates vs edits)](#files-creates-vs-edits) — Files changed by this step.
- [Implementation](#implementation) — Context propagation, updates, and compatibility rules.
- [Tests](#tests) — Focused regression and propagation coverage.
- [Acceptance criteria](#acceptance-criteria) — Checkable completion conditions.
- [References](#references) — Storage and logging contracts used here.
- [Applicable guardrails](#applicable-guardrails) — Plan boundaries that limit this work.
- [Deferred](#deferred) — Follow-up work owned by later steps.

## Why

`plan_tool/run_log.py:RunLogWriter` can attach one-off fields to individual records, but it has no safe shared state that automatically follows a command through its events and current snapshot. Seed materialization needs stable command and plan attribution even for shell-sink events and snapshot refreshes, where threading fields through each call would be easy to miss. This step establishes that shared path before steps 3–5 add materialization and refresh lifecycles.

## Input

- **Step 1 lifecycle owner:** Step 1 supplies the private owned-writer setup and terminal cleanup in `plan_tool/roadmap.py`; this step adds an optional context path to that owner without changing `run_roadmap()` or `apply_roadmap_seeds()` public signatures.
- **Writer event paths:** `plan_tool/run_log.py:RunLogWriter.start()`, `RunLogWriter._emit()`, `RunLogWriter._refresh_in_flight()`, `RunLogWriter.bind_shell_sink()`, `RunLogWriter.install_call_end_sink()`, and `RunLogWriter.run_end()` together cover startup, normal events, shell call-end events, snapshots, and termination.
- **Existing compatibility boundary:** `plan_tool/roadmap.py:RunLoggerLike` intentionally permits lightweight test recorders. Legacy roadmap stage and apply paths must not require those recorders to implement a context-update method.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `plan_tool/run_log.py` — Add the optional context input, writer-owned context updates, and flat propagation to every writer event and snapshot.
  - `plan_tool/roadmap.py` — Let step 1’s private lifecycle owner opt into writer context while leaving current stage and apply callers opted out.
  - `tests/test_run_log.py` — Cover context propagation, update ordering, shell-sink coverage, and no-context compatibility.
  - `tests/test_roadmap.py` — Prove existing roadmap stage and apply lifecycles remain context-free.

## Implementation

- **Make writer-owned context propagation the foundational logic.** Add an optional context mapping to `plan_tool/run_log.py:RunLogWriter.start()` and retain a copied current mapping on the writer. Do not add the fields to each frozen event dataclass: the envelope is optional shared metadata, not a new required event schema.

- **Flatten the context into records and snapshots.** A context-enabled seed action carries immutable `command: "roadmap"` plus `roadmap_action`, `roadmap_slug`, `requested_plan_id`, and `active_plan_id` as top-level fields, not under a nested `context` object. Preserve literal `null` values for the two plan-ID fields whenever context is enabled; callers without context must not gain any of these keys.

- **Cover both writer paths.** Route ordinary writer methods through `RunLogWriter._emit()` with the current envelope, and update `plan_tool/run_log.py:_make_call_end_sink()` or its callers so `claude_call_end` records receive the same current envelope. `RunLogWriter.start()` must add it to the initial JSONL record and snapshot, while `RunLogWriter.run_end()` must use the final context.

- **Provide a controlled context update.** Add a small writer-level operation that replaces or updates the held envelope and immediately republishes the in-flight snapshot. Use the same synchronization boundary as `RunLogWriter._refresh_in_flight()` so an update cannot leave a snapshot with fields from two different row states. Copy mappings at the writer boundary; later caller mutation must not change already-owned context.

- **Keep row-boundary ordering available to later steps.** The lifecycle owner must be able to set `active_plan_id` before a phase starts, clear `seed_attempt` and `backend_attempt` to literal null while retaining that row ID before `phase_end`, then clear the row ID in an immediate inter-phase snapshot. The clearing operations emit no synthetic lifecycle event. This step supplies the mechanism only; steps 4 and 5 own the materialization and refresh phase calls.

- **Keep envelope fields authoritative.** Context must not replace event identity fields such as `run_id`, `event`, or event-specific data; `command` is initialized once by the lifecycle and remains immutable; and per-event extras must not override active context keys. Preserve the existing serialization, string-size limits, append behavior, and snapshot readability.

- **Keep legacy callers unchanged.** `plan_tool/roadmap.py:run_roadmap()` and `plan_tool/roadmap.py:apply_roadmap_seeds()` pass no context, retain their current start flags, and keep `RunLoggerLike` injection behavior. All other current `RunLogWriter.start()` callers in `plan_tool/bench.py`, `plan_tool/cli/authoring.py`, `plan_tool/cli/completeness_cmd.py`, `plan_tool/cli/gates_cmd.py`, `plan_tool/cli/lessons_cmd.py`, `plan_tool/cli/reconcile.py`, `plan_tool/cli/review_cmd.py`, and `plan_tool/cli/run_cmd.py` remain deliberate zero-diff callers.

- **Reject per-event threading and flag-only attribution.** Do not require every writer method or backend observer call to accept new roadmap fields, and do not store changing plan attribution only in `flags`. Neither approach reaches every event and snapshot reliably.

## Tests

### Tests for this step

- `test_context_enabled_writer_flattens_context_into_run_start_and_snapshot` — A context-enabled `RunLogWriter.start()` writes the four top-level fields, including literal-null plan IDs, to both initial outputs.
- `test_context_reaches_regular_shell_sink_terminal_and_snapshot_paths` — A normal emitter, `RunLogWriter.bind_shell_sink()`, `RunLogWriter.run_end()`, and every snapshot refresh each retain immutable `command: "roadmap"` with the active context.
- `test_context_update_preserves_phase_end_attribution_then_clears_snapshot` — A phase-end record keeps its active plan ID, while the immediately refreshed snapshot and later terminal event show `active_plan_id` as `null`.
- `test_context_update_preserves_snapshot_lifecycle_fields` — Updating context retains the current snapshot’s required identity, status, and lifecycle fields.
- `test_context_is_copied_and_cannot_override_event_identity` — Caller mutation and reserved-key collisions cannot alter writer identity or prior records.
- `test_writer_without_context_keeps_existing_event_and_snapshot_shape` — A default writer emits no context fields and retains the current schema version and serialized shape.
- `TestRunLog::test_stage_run_does_not_opt_into_context` — `run_roadmap()` retains context-free stage lifecycle records.
- `TestApplyRoadmapSeeds::test_apply_does_not_opt_into_context` — `apply_roadmap_seeds()` retains context-free apply records.

Every listed test must be green before this step is complete.

## Acceptance criteria

- `RunLogWriter.start()` accepts optional per-run context without requiring it.
- A context-enabled writer includes its flat context fields in `run_start`, all writer-emitted events including shell call-end events, `run_end`, and every published `in-flight.json` snapshot.
- A context update publishes a complete snapshot and does not discard existing snapshot identity or lifecycle fields.
- A row’s `active_plan_id` remains present through its `phase_end` and can be cleared to literal `null` before the next phase or terminal event.
- Context fields cannot overwrite event identity or event-specific fields.
- Writers started without context emit no new context keys, retain `RUN_LOG_SCHEMA_VERSION == 2`, and keep existing record and snapshot shapes.
- `run_roadmap()` and `apply_roadmap_seeds()` keep their current logs and do not require injected `RunLoggerLike` objects to support context updates.
- `uv run pytest tests/test_run_log.py tests/test_roadmap.py -q` passes.

## References

- [Python os.replace](https://docs.python.org/3.13/library/os.html#os.replace) — Defines the atomic replacement behavior required for context-bearing snapshot updates.
- [POSIX write() Specification](https://pubs.opengroup.org/onlinepubs/9699919799/functions/write.html) — Defines append guarantees that continue to protect flattened JSONL events.
- [JSON Lines Format](https://jsonlines.org/) — Defines the independent, newline-delimited record format that context fields extend.
- [OWASP Logging Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html) — Guides safe, structured context fields and exclusion of sensitive content.

## Applicable guardrails

- **The plan’s “## Plan intent”, durable liveness contract:** Keep context attached to the existing run-log and snapshot surfaces; do not create a second tracking store.
- **The plan’s “## Step intent”, optional context path:** Preserve the same output for callers that do not opt in.
- **The plan’s “## Out of scope”, command-path observability:** Do not change prompts, seed validity, retry behavior, seed-state data, draft handling, promotion behavior, or refresh reporting.
- **The plan’s “## Out of scope”, redacted lifecycle data:** Limit this envelope to safe identifiers and null values; do not persist seed bodies, prompts, replies, tool inputs, or failure text.
- **The plan’s “## Out of scope”, limited rollout:** Do not update unrelated `RunLogWriter.start()` callers or change same-slug snapshot isolation.

## Deferred

- Materialization phase ownership and row-context transitions — Steps 4 and 5 use this capability for selected, batch, and refresh command lifecycles.
- Materializer attempt, recovery, and redaction events — Step 3 owns the observer and safe event vocabulary.
- Operator-facing documentation of the context fields — Step 6 owns the reference and capability updates.
