> **Auto-archived**: this plan was swept on 2026-08-18 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 5 — Give --refresh-seeds one ordered run and clean up its snapshot

## Summary

Give `plan_tool/roadmap.py:refresh_roadmap_seeds()` one command-owned run lifecycle covering roadmap loading, every refresh row, report publication, and termination. Keep `plan_tool/cli/roadmap_cmd.py:_cmd_roadmap_refresh_seeds()` thin: it invokes the orchestrator, renders the existing result, and keeps its exit-code mapping. Use steps 1–3’s lifecycle, context, and redacting observer so each attempted source-order row is visible without logging seed content. On green, successful replacements, failed-row state, aggregate results, and the changes-then-failures report remain unchanged, while every terminal path removes the owned `in-flight.json`.

## Table of Contents

- [Summary](#summary) — The change and its observable result.
- [Table of Contents](#table-of-contents) — Links to each section.
- [Why](#why) — Why refresh needs command-level ownership.
- [Input](#input) — Contracts from the refresh path and prior steps.
- [Files (creates vs edits)](#files-creates-vs-edits) — Files changed by this step.
- [Implementation](#implementation) — Ordered lifecycle, row attribution, and failure rules.
- [Tests](#tests) — Deterministic refresh and CLI coverage.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Lifecycle and durable-record guidance.
- [Applicable guardrails](#applicable-guardrails) — Plan boundaries for this step.
- [Deferred](#deferred) — Work left outside this step.

## Why

`plan_tool/roadmap.py:refresh_roadmap_seeds()` runs backend materialization for every plan row but has no owned run writer, row phase, or terminal cleanup. An operator therefore cannot see which refresh row is active, distinguish a completed empty refresh from an absent run, or rely on the normal snapshot cleanup after a partial result, error, or interrupt. Add observability around the established refresh contract without changing the seed and report behavior it already owns.

## Input

- **Steps 1 and 2:** Use the private roadmap lifecycle owner and the writer-owned context envelope that these steps provide. Refresh supplies `roadmap_action: "refresh-seeds"`, the roadmap slug, and null `requested_plan_id`.

- **Step 3:** Pass its redacting, phase-scoped materialization instrumentation to `plan_tool/roadmap.py:materialize_and_diff_one_plan()`. Step 3 owns attempt counters, backend events, and redaction.

- **Refresh result contract:** Preserve `RoadmapSeedRefreshResult`, `RoadmapSeedRefreshChange`, `RoadmapSeedRefreshFailure`, and the `SEED_REFRESH_OUTCOME_*` result mapping in `plan_tool/roadmap.py`.

- **Ordering contract:** Use the `plans` field of `plan_tool/roadmap_artifacts.py:PlansArtifact` as the refresh order. Do not use `plan_tool/roadmap.py:ordered_plan_seed_targets()`, which follows `PlansArtifact.ordering` for apply-only promotion.

- **Report and mutation contract:** Keep `plan_tool/roadmap.py:materialize_and_diff_one_plan()`, `_render_seed_refresh_report()`, and `write_seed_refresh_report()` responsible for the established comparison and report shape. Preserve `materialize_plan_seed()`’s draft, published-copy, then seed-state write order.

- **CLI boundary:** Keep `plan_tool/cli/roadmap_cmd.py:cmd_roadmap()` as the `KeyboardInterrupt` mapper. Refresh must finish its owned terminal record before the dispatcher returns exit code 130.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `plan_tool/roadmap.py` — Give `refresh_roadmap_seeds()` the shared lifecycle, refresh context, ordered row phases, observer handoff, terminal mapping, and snapshot cleanup.
  - `plan_tool/cli/roadmap_cmd.py` — Keep `_cmd_roadmap_refresh_seeds()` as the thin refresh caller and result-to-output mapper while preserving its interrupt boundary.
  - `tests/test_roadmap.py` — Extend `TestRefreshRoadmapSeeds` with lifecycle, ordering, state-preservation, error, and cleanup coverage.
  - `tests/cli/test_roadmap_cmd.py` — Extend refresh dispatch and real interrupt coverage without using a live backend.

## Implementation

- **Make the foundational logic one ordered refresh lifecycle.** Start the step-1 lifecycle after `plan_tool/roadmap.py:roadmap_dir()` accepts the slug and before `refresh_roadmap_seeds()` loads the stage-four artifact through `_load_stage_artifact()`.

- **Keep lifecycle ownership in the orchestrator.** `refresh_roadmap_seeds()` must own its writer so direct callers and the CLI receive the same run record. Do not create another writer in `plan_tool/cli/roadmap_cmd.py:_cmd_roadmap_refresh_seeds()`.

- **Set refresh context before roadmap loading.** Initialize immutable `command: "roadmap"`, set `roadmap_action` to `"refresh-seeds"`, `roadmap_slug` to the supplied slug, and both plan-ID fields to literal null. Retain that context on run start, all writer events including shell call-end, snapshots, and the terminal record through the step-2 writer path.

- **Process rows only in source order.** Iterate `PlansArtifact.plans` once for calls, phases, replacements, and accumulated result entries. Do not sort rows or use `PlansArtifact.ordering` as an execution order.

- **Attribute the full row operation.** Before calling `materialize_and_diff_one_plan()` for a row, set `active_plan_id`, start `seed-materialize:<plan-id>`, and attach the step-3 observer. The phase must include that helper’s baseline reads, artifact reload, prompt preparation, backend attempts, writes, and result handling.

- **Clear row state after every phase.** Clear both attempt counters through the step-2 context update before `phase_end` while retaining the row ID, then clear `active_plan_id` before the next row or every terminal record. The immediate inter-phase snapshot must show literal-null inactive fields.

- **Preserve independent exhausted-row handling.** A returned `RoadmapSeedRefreshFailure` ends that row as exhausted, retains its prior draft and seed-state entry, appends the failure, and continues with later source rows. A successful row appends its changes without changing the behavior of later rows.

- **Preserve report and replacement behavior.** Publish the refresh report only after all planned rows finish, keep change blocks before failure blocks, and keep source order within each group. Do not roll back a successful draft or promoted-copy replacement when a later seed-state or report write fails; the resulting mismatch remains the recovery signal.

- **Keep known failures distinct from escaping errors.** A command-level artifact error records `preflight-refused` before any row phase and preserves the current usage result. A known row-scoped setup refusal closes its active phase as `preflight-refused` before it propagates. An unexpected exception during active row work retains the active row on its safe per-row failure event and phase end, clears the envelope, then records terminal `error` with only a static safe error class. A report-publication error after every row phase is command-scoped: it records terminal `error` with inactive row context and no fabricated row failure or phase. Both paths clear the snapshot and preserve current exception behavior.

- **Map terminal outcomes from the established aggregate result.** Map an all-successful refresh, including an empty `PlansArtifact.plans`, to `completed`; map mixed changes and exhausted rows to `partial`; map all-exhausted rows to `exhausted`; and map an interrupt to `interrupted` with return code 130. Terminal context must have no active plan.

- **Keep sensitive values out of this layer.** Let the step-3 observer emit only safe lifecycle facts. Do not add prompts, seed text, reply-derived detail, validation messages, or tool-input summaries to CLI code, refresh events, or snapshots.

## Tests

### Tests for this step

- `TestRefreshRoadmapSeeds::test_refresh_emits_source_ordered_row_phases_and_clears_context` — Refresh calls, phase starts and ends, active plan IDs, and cleared snapshots follow `PlansArtifact.plans` source order when `ordering` differs.

- `TestRefreshRoadmapSeeds::test_refresh_passes_the_active_phase_observer_without_replacing_the_invoker_default` — Each row receives step 3’s observer, while a supplied invoker remains forwarded and the default invoker seam remains intact.

- `TestRefreshRoadmapSeeds::test_refresh_completed_preserves_seed_replacements_and_writes_one_terminal_record` — Successful draft, promoted-copy, seed-state, and report behavior remains intact before a completed terminal record removes the snapshot.

- `TestRefreshRoadmapSeeds::test_refresh_partial_and_exhausted_rows_preserve_failed_row_state_and_report_grouping` — Exhausted rows continue independently, retain their prior draft and seed-state data, preserve successful rows, and keep report changes before failures.

- `TestRefreshRoadmapSeeds::test_empty_refresh_records_completed_with_zero_row_phases` — A roadmap with no plan rows writes one completed lifecycle, starts no row phase, and cleans up `in-flight.json`.

- `TestRefreshRoadmapSeeds::test_refresh_row_setup_refusal_closes_the_active_phase_and_halts` — A known row-scoped failure keeps its row attribution through `preflight-refused`, leaves attempt counters inactive, and preserves the current raised usage path.

- `TestRefreshRoadmapSeeds::test_refresh_row_write_errors_keep_prior_recovery_state_and_record_safe_error` — Draft, promoted-copy, or seed-state write failures retain already-published work as applicable, emit only a safe error class with row-phase attribution, and clean up the snapshot.

- `TestRefreshRoadmapSeeds::test_refresh_report_publication_error_is_command_scoped` — A report write failure after all row phases retains prior work, emits only a safe terminal error class with inactive row context, creates no fabricated row failure or phase, and cleans up the snapshot.

- `TestKeyboardInterruptRunEndPairing::test_interrupted_refresh_records_interrupt_run_end` — A real refresh path interrupted during an active row ends its phase, records `interrupted` with return code 130, removes the snapshot, and reaches the CLI mapper.

- `TestApplyMode::test_cmd_refresh_seeds_keeps_result_rendering_and_exit_mappings` — The CLI still renders refresh results and maps completed, partial, and exhausted results to the established return codes without owning a second lifecycle.

Every listed test must be green before this step is complete.

## Acceptance criteria

- `refresh_roadmap_seeds()` owns one refresh lifecycle from safe slug validation through report handling and terminal cleanup.

- Every attempted refresh row has one `seed-materialize:<plan-id>` phase that starts before row preparation and follows `PlansArtifact.plans` source order.

- Refresh run records and snapshots carry refresh context; phase-end records retain their row ID, while inter-phase and terminal state use literal-null inactive plan and attempt fields.

- A successful row keeps the established draft, published-copy, seed-state, change, and report behavior.

- An exhausted row retains its prior draft and seed-state entry, does not prevent later source rows from running, and contributes to the established partial or exhausted aggregate result.

- An empty refresh records `completed`, has zero row phases, returns the existing successful result, and removes its owned `in-flight.json`.

- Command-level and row-scoped known failures record `preflight-refused`; unexpected post-start failures record only a safe error class; interrupts record `interrupted` before the CLI returns 130.

- The refresh report still renders all changes before all failures, with source order preserved within each group.

- `plan_tool/cli/roadmap_cmd.py:_cmd_roadmap_refresh_seeds()` remains the result-rendering and exit-code layer, not a second writer owner.

- `uv run pytest tests/test_roadmap.py tests/cli/test_roadmap_cmd.py -q` passes without a live backend.

## References

- [Python signal — Asynchronous Event Handlers](https://docs.python.org/3.13/library/signal.html#general-rules) — Review `KeyboardInterrupt` delivery and cleanup ordering.

- [Python os.replace](https://docs.python.org/3.13/library/os.html#os.replace) — Review atomic publication of the current snapshot.

- [JSON Lines Format](https://jsonlines.org/) — Keep each lifecycle event independently parseable.

- [OWASP Logging Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html) — Keep seed and backend content out of durable records.

## Applicable guardrails

- **The plan’s “## Plan intent”, durable liveness contract:** Use the established run-log and snapshot surfaces for the complete refresh command, including empty, partial, exhausted, and interrupted runs.

- **The plan’s “## Step intent”, row evidence and report grouping:** Preserve source-row attribution and the refresh report’s grouped output while adding lifecycle records.

- **The plan’s “## Out of scope”, seed behavior and reports:** Do not change materialization prompts, validity checks, retry budgets, seed-state data, draft paths, promotion behavior, or report content.

- **The plan’s “## Out of scope”, limited observability rollout:** Keep this work inside refresh and its roadmap-local seams; do not extend generic backend callers or same-slug snapshot behavior.

- **The plan’s “## Out of scope”, durable data:** Use only the step-3 safe observer fields in JSONL and `in-flight.json`.

## Deferred

- Consolidating the inline refresh report publication with `plan_tool/roadmap.py:write_seed_refresh_report()` — Handle this as a separate behavior-preserving refactor; this step preserves report timing and content while adding observability.

- Operator documentation for refresh phases, outcomes, and redaction — Step 6 owns the documentation surface.

- Broader observability rollout beyond roadmap materialization and refresh — The plan’s scope fence keeps that work out of this step.
