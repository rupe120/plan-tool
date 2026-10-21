> **Auto-archived**: this plan was swept on 2026-08-18 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 4 — Give selected and all-eligible --materialize commands one lifecycle

## Summary

Update `plan_tool/cli/roadmap_cmd.py:_cmd_roadmap_materialize()` to own one materialization lifecycle from safe command setup through selection, row work, report handling, and termination. Use the lifecycle owner from step 1, the context envelope from step 2, and the redacting materialization observer from step 3. The key decision is to start the lifecycle before artifact loading and classification, not only around backend calls. On green, selected, all-eligible, partial, refused, no-op, exhausted, interrupted, and unexpected-error materializations leave one durable JSONL record and clean up their owned `in-flight.json`.

## Table of Contents

- [Summary](#summary) — The change and its observable result.
- [Table of Contents](#table-of-contents) — Links to each section.
- [Why](#why) — Why materialization needs command-level ownership.
- [Input](#input) — Contracts from the materializer and prior steps.
- [Files (creates vs edits)](#files-creates-vs-edits) — Files this step changes.
- [Implementation](#implementation) — Lifecycle, attribution, outcome, and cleanup rules.
- [Tests](#tests) — Deterministic CLI coverage for every terminal path.
- [Acceptance criteria](#acceptance-criteria) — Checkable completion conditions.
- [References](#references) — Lifecycle and durable-record guidance.
- [Applicable guardrails](#applicable-guardrails) — Scope limits that bind this step.
- [Deferred](#deferred) — Follow-up work owned elsewhere.

## Why

`plan_tool/cli/roadmap_cmd.py:_cmd_roadmap_materialize()` currently selects rows and calls `plan_tool/roadmap.py:materialize_and_diff_one_plan()` without owning a run writer, so an operator cannot inspect selection refusals, zero-eligible no-ops, row preparation, or terminal cleanup through the normal roadmap liveness surface. Adding a writer only around the backend call would still miss those command outcomes. This step gives the whole materialize command one lifecycle while keeping seed mutation, report replacement, and exit-code behavior unchanged.

## Input

- **Step 1 lifecycle owner:** Step 1 supplies the private owned-writer setup and terminal cleanup already used by `plan_tool/roadmap.py:run_roadmap()` and `plan_tool/roadmap.py:apply_roadmap_seeds()`. Use its landed interface rather than creating a second CLI-specific writer pattern.

- **Step 2 context envelope:** Step 2 supplies the writer-owned `roadmap_action`, `roadmap_slug`, `requested_plan_id`, and `active_plan_id` context path. This step owns the materialize values and row-boundary updates.

- **Step 3 observer:** Step 3 makes `plan_tool/roadmap.py:materialize_and_diff_one_plan()` accept the redacting, phase-scoped materialization instrumentation. This step selects the phase and supplies that instrumentation; it does not rebuild backend counters or redaction rules.

- **Selection and ordering contract:** `plan_tool/cli/roadmap_cmd.py:_MATERIALIZE_ALL`, `_MATERIALIZABLE_STATES`, and `plan_tool/roadmap_seed_manifest.py:classify_draft_seeds()` determine eligibility. The `plans` field of `plan_tool/roadmap_artifacts.py:PlansArtifact` remains the source-order input; `PlansArtifact.ordering` does not become an execution order.

- **Result and report contract:** `plan_tool/roadmap.py:materialize_and_diff_one_plan()` returns changes or a row failure, while `write_seed_refresh_report()` and `_render_seed_refresh_result()` retain the current report and operator-result behavior. A returned exhausted row failure continues the batch; a known raised command or row-preparation error retains the current halt-and-usage behavior.

- **Interrupt boundary:** `plan_tool/cli/roadmap_cmd.py:cmd_roadmap()` remains the one dispatcher-level `KeyboardInterrupt` mapper. The materialize lifecycle must finish its terminal record and cleanup before that handler returns exit code 130.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `plan_tool/cli/roadmap_cmd.py` — Give `_cmd_roadmap_materialize()` a command-owned lifecycle, materialize context, row phases, observer handoff, terminal mapping, and cleanup.
  - `tests/cli/test_roadmap_cmd.py` — Extend `TestMaterializeMode` with lifecycle, ordering, refusal, error, interrupt, and snapshot-cleanup coverage.

## Implementation

- **Make one command lifecycle the foundational logic.** Start the lifecycle after the slug is safe for the slug-scoped run path and before `_cmd_roadmap_materialize()` loads `04-roadmap.md` or classifies drafts. Keep it open through row selection, row work, `write_seed_refresh_report()`, `_render_seed_refresh_result()`, and every return or exception path.

- **Use the shared lifecycle, not a new CLI writer.** Adopt the private helper supplied by step 1 in `plan_tool/roadmap.py`. It must remain the sole owned-writer and `run_end()` path for this action, while `plan_tool/cli/roadmap_cmd.py:cmd_roadmap()` continues to own dispatch and user-facing interrupt rendering.

- **Set the materialize context at command start.** Initialize immutable `command: "roadmap"`, use `roadmap_action: "materialize"` and the CLI slug for `roadmap_slug`, set `requested_plan_id` to the explicit `--materialize PLAN_ID` value or literal `null` for all-eligible materialization, and start with `active_plan_id: null`.

- **Keep source-row selection and report behavior unchanged.** Continue selecting recoverable rows from `artifact.plans` and iterating those rows in that same source order. Do not sort rows, consult `artifact.ordering`, merge returned failures into exceptions, or change the existing changes-then-failures report grouping.

- **Give each attempted row one attributed phase.** Before calling `materialize_and_diff_one_plan()` for a selected row, set `active_plan_id` and start `seed-materialize:<plan-id>`. The phase must begin before that helper’s baseline reads, artifact reload, prompt setup, and backend call. Before phase end, clear both attempt counters while retaining the row ID; after phase end, clear the row ID to literal `null` so the next snapshot is an inactive inter-phase snapshot and every terminal record, including `error`, has no active row.

- **Pass the active observer through the materializer seam.** Supply the step-3 redacting observer or equivalent landed instrumentation for the active phase when invoking `materialize_and_diff_one_plan()`. Preserve the conditional `invoker` forwarding rule in `_cmd_roadmap_materialize()`: pass a supplied test invoker, but leave the materializer’s default invoker intact when none was supplied. Do not log `failure_detail` or construct backend events in the CLI.

- **Keep inactive counter state explicit.** At command start, row phase boundaries, the cleared inter-phase snapshot, and ordinary terminal handling, preserve the plan’s null inactive `seed_attempt` and `backend_attempt` values. Let the step-3 observer own child-attempt values while a backend call is active.

- **Map command outcomes without changing command results.** Preserve exit code 0 for successful selected or all-eligible work, 3 for a mixed landed/exhausted batch, 1 for an all-exhausted batch, and 2 for known usage/refusal paths. Record the matching lifecycle outcomes: `completed`, `partial`, `exhausted`, and `preflight-refused`; record `no-op` with exit code 0 when all-eligible selection finds no recoverable row and do not create a row phase or report.

- **Separate expected refusal from escaping errors.** Record known artifact, classification, selection, and row-preparation refusals as `preflight-refused`, preserving the current halt behavior and diagnostics. If one happens after a row phase begins, close that phase with its row attribution and null backend counters. For an unexpected exception during active row work, retain active-row attribution only on its safe per-row failure event and phase end, then clear the envelope before recording terminal `error` with its static safe class. If the later `write_seed_refresh_report()` call fails after all row phases, record command-scoped `error` directly with inactive row context and no invented row failure or phase. Both paths clean up the snapshot and preserve current exception or dispatcher behavior.

- **Keep non-materialize modes untouched.** Do not add this lifecycle to the `--refresh-seeds`, `--apply`, `--accept-seed`, `--view`, or stage-run branches in `plan_tool/cli/roadmap_cmd.py:cmd_roadmap()`. Step 5 owns refresh; existing apply and stage lifecycles remain single-owned.

- **Reject backend-only wrapping.** A writer scoped only around `materialize_and_diff_one_plan()` would omit command-level refusal and no-op records. The lifecycle must instead cover the entire `_cmd_roadmap_materialize()` decision path.

## Tests

### Tests for this step

- `TestMaterializeMode::test_selected_materialize_emits_one_attributed_lifecycle_and_cleans_snapshot` — A selected recoverable row produces one run start, one `seed-materialize:<plan-id>` phase, step-3 safe events, a `completed` terminal record, and no remaining `in-flight.json`.

- `TestMaterializeMode::test_materialize_passes_the_active_phase_observer_and_preserves_the_invoker_seam` — Each row receives the landed observer while an explicitly supplied invoker is forwarded, and the default path does not inject a replacement invoker.

- `TestMaterializeMode::test_selected_materialize_preflight_refusal_records_requested_id_without_a_phase` — An unknown or nonrecoverable selected ID preserves exit code 2, records `preflight-refused` with the requested ID and inactive row context, starts no backend work, and removes the snapshot.

- `TestMaterializeMode::test_materialize_row_preparation_refusal_closes_the_active_phase` — A known raised row-preparation failure ends the active row phase as `preflight-refused`, preserves the current halt-and-usage result, keeps backend counters null, and cleans up.

- `TestMaterializeMode::test_materialize_all_eligible_uses_plans_source_order_for_phases_and_calls` — A fixture whose `PlansArtifact.ordering` differs from `PlansArtifact.plans` proves row calls, phase events, and active IDs follow source-row order.

- `TestMaterializeMode::test_materialize_batch_records_partial_and_exhausted_terminal_outcomes` — Returned exhausted row failures continue to later selected rows and preserve the existing partial and exhausted exit-code mappings, report inputs, and terminal cleanup.

- `TestMaterializeMode::test_materialize_all_with_no_eligible_rows_records_no_op_without_a_report` — An all-current batch emits a no-phase `no-op` lifecycle with both plan IDs null, keeps exit code 0, skips report replacement, and removes the snapshot.

- `TestMaterializeMode::test_materialize_interrupt_ends_the_owned_lifecycle_before_exit_130` — `KeyboardInterrupt` during an active row produces the interrupted terminal record, closes the active phase, removes `in-flight.json`, and reaches the existing CLI exit-130 handler.

- `TestMaterializeMode::test_materialize_escaping_row_error_records_only_a_safe_error_class` — An unexpected setup or baseline error leaves the current command behavior intact while retaining the row on its failure/phase-end records, recording terminal `error` with literal-null active row, excluding exception text and seed content, and cleaning up the snapshot.

- `TestMaterializeMode::test_materialize_report_publication_error_is_command_scoped` — A `write_seed_refresh_report()` failure after every row phase records only command-scoped terminal `error` with inactive row context, no fabricated row failure or phase, and normal cleanup.

Every listed test must be green before this step is complete.

## Acceptance criteria

- `_cmd_roadmap_materialize()` owns one materialize lifecycle from safe setup through selection, row work, report handling, and termination.

- A selected materialization records `roadmap_action`, `roadmap_slug`, its requested plan ID, the active row phase, and a completed terminal result before removing `in-flight.json`.

- All-eligible materialization invokes and logs recoverable rows in the `plans` field of `plan_tool/roadmap_artifacts.py:PlansArtifact` source order, even when `PlansArtifact.ordering` differs.

- Every row phase begins before `materialize_and_diff_one_plan()` preparation, retains its plan ID through phase end, then publishes an inactive literal-null row context before the next row or every terminal result.

- A zero-eligible all-eligible command writes one `no-op` run record, has no row phase, does not replace the report, returns 0, and removes its snapshot.

- Known command and row-preparation refusals retain their current halt-and-usage behavior while recording `preflight-refused`; exhausted model rows retain the existing batch-continuation behavior and partial/exhausted result mapping.

- An interrupt or unexpected exception after writer startup writes one terminal record, cleans up the owned snapshot, and does not expose exception text, prompts, seed bodies, reply-derived text, validation prose, or tool-input data.

- `--apply`, `--accept-seed`, `--view`, stage runs, and `--refresh-seeds` gain no materialize lifecycle behavior from this step.

- `uv run pytest tests/cli/test_roadmap_cmd.py -q` passes without a live backend.

## References

- [Python signal — Asynchronous Event Handlers](https://docs.python.org/3.13/library/signal.html#general-rules) — Review `KeyboardInterrupt` delivery and cleanup ordering.

- [Python os.replace](https://docs.python.org/3.13/library/os.html#os.replace) — Review the atomic snapshot-publication behavior the writer preserves.

- [JSON Lines Format](https://jsonlines.org/) — Keep each terminal lifecycle record independently parseable.

- [OWASP Logging Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html) — Keep exception and materializer data out of durable structured records.

## Applicable guardrails

- **The plan’s “## Plan intent”, durable liveness contract:** Use the existing run-log and snapshot surfaces for the complete materialize command, including no-op and refusal outcomes.

- **The plan’s “## Step intent”, unchanged materialization behavior:** Preserve current report replacement, row selection, seed mutation, and command-result semantics while adding observability.

- **The plan’s “## Out of scope”, seed behavior and reports:** Do not change prompts, validation, retry budgets, seed-state data, draft or promotion behavior, or refresh-report formatting.

- **The plan’s “## Out of scope”, limited rollout:** Keep this lifecycle limited to `--materialize`; do not widen it to other backend callers or alter same-slug snapshot isolation.

- **The plan’s “## Out of scope”, durable data:** Pass only the step-3 safe observer data into logs and snapshots.

## Deferred

- `--refresh-seeds` lifecycle, empty-batch handling, and refresh-row attribution — Step 5 owns that command path.

- Operator-facing documentation for materialization phases, outcomes, and redaction — Step 6 owns the documentation surface.

- General lifecycle rollout for other commands and concurrent same-slug snapshot isolation — These remain outside this plan’s command-path scope.
