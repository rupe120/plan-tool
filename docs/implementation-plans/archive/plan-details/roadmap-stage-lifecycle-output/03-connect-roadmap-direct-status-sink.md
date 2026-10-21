> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 3 — Connect roadmap’s direct status sink to stderr and add accepted-range plus normal terminal facts

## Summary

This step connects the optional status callback from step 2 to `plan_tool/style.py:note` in `plan_tool/cli/roadmap_cmd.py:cmd_roadmap`. It adds one accepted-range fact in `plan_tool/roadmap.py:_run_roadmap` and one terminal fact for every returned `RoadmapResult`. The roadmap-owned status formatter and fail-open delivery path remain the only way new lifecycle lines reach stderr. On green, normal stage runs show bounded progress on stderr while existing stdout summaries, exit codes, interrupt handling, run logs, and non-stage routes stay unchanged.

## Table of Contents

- [Summary](#summary) — The completed command and runner status behavior.
- [Table of Contents](#table-of-contents) — Links to every section in this detail.
- [Why](#why) — The command-level gap this step closes.
- [Input](#input) — The runner callback and result contracts this step consumes.
- [Files (creates vs edits)](#files-creates-vs-edits) — The four existing files this step changes.
- [Implementation](#implementation) — The status sink, accepted-range, and terminal ordering rules.
- [Tests](#tests) — Deterministic runner and CLI coverage.
- [Acceptance criteria](#acceptance-criteria) — Observable output and compatibility results.
- [References](#references) — The plan, code, and motivating run.
- [Applicable guardrails](#applicable-guardrails) — Boundaries that constrain this work.
- [Deferred](#deferred) — Status work outside this focused step.

## Why

`plan_tool/cli/roadmap_cmd.py:cmd_roadmap` currently waits for `plan_tool/roadmap.py:run_roadmap` to return before presenting its result, so an operator has no command-facing record of the accepted stage selection or final returned outcome. Step 2 supplies bounded runner transition facts but leaves the callback disconnected from stderr. This step makes those facts visible at the normal command boundary without changing what scripts receive on stdout or treating a quiet backend call as healthy.

## Input

- **Step 2 callback seam:** Read the landed optional callback contract from `plan_tool/roadmap.py:run_roadmap` and `plan_tool/roadmap.py:_run_roadmap`. Its default remains silent for direct callers.

- **Selected-stage identity:** `plan_tool/roadmap.py:RoadmapStage` and the ordered table in `plan_tool/roadmap.py:_run_roadmap` define the selected stages. Build the selection from actual selected `number` values, not an assumed contiguous range; render the ordered list through the same escaped, capped field and callback-body formatter used for every lifecycle status, so sparse injected tables remain truthful without unbounded output. That body has a 250-character printable budget because `style.note` adds the fixed six-character `note: ` prefix; the final textual stderr line therefore has a 256-character budget, excluding its newline and terminal styling.

- **Returned terminal vocabulary:** `plan_tool/roadmap.py:RoadmapResult` and `plan_tool/roadmap.py:OUTCOMES` define the four returned outcomes. The terminal fact names only those existing values.

- **Command ordering:** `plan_tool/cli/roadmap_cmd.py:cmd_roadmap` renders through `_print_completed`, `_print_completed_no_change`, `_print_invalid`, `_print_exhausted`, and the post-result summary helpers before returning. Its outer `KeyboardInterrupt` handler remains the interrupt owner.

## Files (creates vs edits)

- **New files:** None.

- **Existing files (edits only):**
  - `plan_tool/roadmap.py` — Emit the accepted selected-stage fact after admission and provide the roadmap-owned terminal-status path that reuses step 2’s safe delivery rules.
  - `plan_tool/cli/roadmap_cmd.py` — Supply `plan_tool/style.py:note` only to the normal stage-run call and emit a returned-result terminal fact after existing summaries.
  - `tests/test_roadmap.py` — Cover accepted-range placement, sparse and empty selections, pre-loop invalid results, terminal sanitization, and fail-open terminal delivery.
  - `tests/cli/test_roadmap_cmd.py` — Cover stderr wiring, terminal order for every returned outcome, unchanged stdout, view isolation, escaping errors, and interrupts.

## Implementation

- **Foundational logic:** bracket step 2’s confirmed stage facts with one admitted selection fact and one returned-result fact.

- **Emit accepted range only after admission.** In `plan_tool/roadmap.py:_run_roadmap`, emit one accepted-selection fact after `_load_and_regate_below` and `_load_predecessors` succeed, immediately before the selected-stage loop. A pre-loop invalid result has no accepted range because no selected stage began.

- **Use selected table rows, not arithmetic.** Build the accepted fact from the ordered `RoadmapStage` rows at or above `from_stage`. Preserve sparse stage numbers and render their actual ordered list through the bounded selection formatter; a clipped display carries the stable digest of the complete list. Make the existing empty-table completion report a fixed zero-stage selection before its normal terminal fact.

- **Keep status construction in the roadmap module.** Add only the narrow roadmap-owned path needed for `plan_tool/cli/roadmap_cmd.py:cmd_roadmap` to emit a terminal outcome through step 2’s safe formatter and callback delivery helper. The CLI must not recreate slug escaping, output prefixes, exception handling, or status text.

- **Connect the sink at one call site.** In the ordinary `run_roadmap` branch of `plan_tool/cli/roadmap_cmd.py:cmd_roadmap`, pass `plan_tool/style.py:note` as the optional sink. The runner must receive a body of at most 250 printable characters, not a 256-character body: `note` adds `note: `, and this step verifies the final textual stderr line remains at most 256 characters excluding its newline and terminal styling. Leave every early dispatch branch unchanged, including apply, seed, view, feedback, evidence, and structural routes.

- **Preserve result presentation order.** Emit the terminal fact only after the established result renderer and all post-result summary helpers finish. Each returned `RoadmapResult` gets exactly one terminal fact for `completed`, `completed-no-change`, `stage-exhausted`, or `stage-invalid`.

- **Do not fabricate terminals.** The `RoadmapError` and `RoadmapArtifactError` path has no `RoadmapResult`, so it keeps its existing error output without a terminal lifecycle fact. A post-start stopped fact remains the runner’s responsibility from step 2.

- **Keep delivery fail-open.** Terminal delivery must use the same `Exception`-swallowing boundary as runner facts. A sink failure drops that one fact without changing the result, output mapping, artifact state, or exit code. Do not catch `BaseException`.

- **Keep interrupts untouched.** Do not add an interrupt handler or terminal fact on the `KeyboardInterrupt` path. `cmd_roadmap` retains its existing `interrupted` stderr message and exit code 130.

- **Do not reuse the shared reporter.** `plan_tool/progress.py:StderrReporter` owns heartbeat and thread behavior for other commands. Reusing it would change this transition-only contract and is outside this step.

- **Update wiring expectations.** Extend `tests/cli/test_roadmap_cmd.py:TestOrchestratorWiring` so the normal stage-run call expects the new sink, while mode-specific tests continue to prove that non-stage branches never reach `run_roadmap`.

## Tests

### Tests for this step

- `test_accepted_range_follows_admission_and_precedes_first_stage_start` — `tests/test_roadmap.py` asserts one accepted-selection fact appears after both pre-loop admission paths and before the first selected stage fact.

- `test_accepted_range_uses_actual_sparse_selected_stage_numbers` — `tests/test_roadmap.py` uses a sparse injected table and proves the status reports selected row numbers without filling in absent stages; a large sparse table or huge stage numbers remains within the field and callback-body caps while retaining the complete-list digest.

- `test_empty_stage_table_reports_zero_selected_stages_then_completed` — `tests/test_roadmap.py` preserves the empty-table success result and asserts its bounded selection and terminal ordering.

- `test_preloop_invalid_skips_accepted_range` — `tests/test_roadmap.py` forces `_load_and_regate_below` or `_load_predecessors` to return an invalid result and asserts no accepted or stopped stage fact appears.

- `test_terminal_status_reuses_the_safe_slug_formatter` — `tests/test_roadmap.py` proves a terminal fact uses the step 2 formatter rather than writing a raw slug.

- `test_terminal_status_sink_exception_is_fail_open` — `tests/test_roadmap.py` makes terminal delivery raise `Exception` and asserts the returned result and roadmap behavior remain unchanged.

- `test_cmd_roadmap_passes_note_as_the_stage_status_sink` — `tests/cli/test_roadmap_cmd.py` drives the normal stage branch through a stub runner, invokes the received sink, and asserts the new fact reaches stderr.

- `test_stage_status_final_stderr_line_including_note_prefix_is_capped` — `tests/cli/test_roadmap_cmd.py` captures a maximal safe lifecycle body with styling disabled and asserts its rendered text includes `note: ` yet remains at most 256 characters, excluding its newline.

- `test_returned_outcomes_emit_one_terminal_after_existing_summaries` — `tests/cli/test_roadmap_cmd.py` covers `completed`, `completed-no-change`, `stage-exhausted`, and `stage-invalid`, each with one trailing terminal fact.

- `test_stage_status_does_not_change_existing_stdout` — `tests/cli/test_roadmap_cmd.py` captures both streams and proves normal result summaries remain exactly unchanged on stdout.

- `test_view_route_emits_no_stage_lifecycle_status` — `tests/cli/test_roadmap_cmd.py` proves a view returns without creating or using the stage status sink.

- `test_escaping_stage_error_has_no_terminal_status` — `tests/cli/test_roadmap_cmd.py` preserves the existing usage-shaped error path when no `RoadmapResult` returns.

- `test_keyboard_interrupt_keeps_rc_130_without_terminal_status` — `tests/cli/test_roadmap_cmd.py` extends the existing interrupt coverage to prove no terminal outcome is required after interruption.

Every named test and `uv run pytest tests/test_roadmap.py tests/cli/test_roadmap_cmd.py -q` must be green before this step is complete.

## Acceptance criteria

- `plan_tool/roadmap.py:_run_roadmap` emits one accepted-selection fact only after source and predecessor admission succeeds and before the selected-stage loop starts.

- The accepted-selection fact derives from actual selected `RoadmapStage.number` values, including sparse tables, renders them through the bounded selection formatter, and reports the empty table as a zero-stage selection.

- A pre-loop `stage-invalid` result emits no accepted-selection fact, while `plan_tool/cli/roadmap_cmd.py:cmd_roadmap` emits one terminal `stage-invalid` fact after its existing result output.

- The normal stage-run path passes a stderr sink to `plan_tool/roadmap.py:run_roadmap`; direct callers that omit the optional callback remain silent.

- Each returned `RoadmapResult` outcome emits exactly one terminal fact after existing result and summary output.

- A `RoadmapError`, `RoadmapArtifactError`, or `KeyboardInterrupt` does not gain a fabricated terminal outcome.

- New lifecycle facts reach stderr only. Stdout remains exactly unchanged for completed, no-change, exhausted, invalid, and view routes.

- The runner supplies a status body of at most 250 printable characters, and `style.note` renders its final textual stderr line, including `note: ` and excluding its newline and terminal styling, at no more than 256 characters.

- A status-sink `Exception` cannot alter roadmap execution, result mapping, artifacts, run-log records, or exit code.

- No non-stage roadmap route gains lifecycle status, heartbeat behavior, background work, or durable state.

## References

- [Roadmap lifecycle plan — Read the status order and command-boundary ownership rules.

- [plan_tool/roadmap.py — Read `run_roadmap`, `_run_roadmap`, `RoadmapStage`, `RoadmapResult`, and `OUTCOMES`.

- [plan_tool/cli/roadmap_cmd.py — Read `cmd_roadmap`’s stage dispatch, result rendering, and interrupt boundary.

- [docs/how-to/roadmap-demo.md](../../../how-to/roadmap-demo.md) — Read the long-running roadmap example that requires confirmed transition visibility.

## Applicable guardrails

- **The plan’s `## Scope guardrails`, normal stage-run boundary:** Connect the sink only at `cmd_roadmap`’s ordinary stage-run call; leave other roadmap routes unchanged.

- **The plan’s `## Scope guardrails`, output boundary:** Send only the new lifecycle facts to stderr and preserve all existing stdout content.

- **The plan’s `## Scope guardrails`, transition-only boundary:** Do not add shared reporter use, heartbeat behavior, timers, background workers, or durable status.

- **The plan’s `## Scope guardrails`, preserved execution contract:** Do not change attempts, prompts, gates, publication, source admission, result vocabularies, exit codes, or run-log records.

- **The plan’s `## Scope guardrails`, safe-content boundary:** Reuse step 2’s safe formatter and fixed lifecycle inputs; terminal facts must not include failure or model-derived content.

- **The plan’s `## Scope guardrails`, fail-open boundary:** A delivery `Exception` drops one fact, while control-flow exceptions retain their existing path.

- **The plan’s `## Out of scope`, liveness and route exclusions:** Do not treat silence as proof of health or add status to another command path.

## Deferred

- **Heartbeat or liveness reporting** — The plan’s `## Out of scope` reserves quiet-call diagnosis for a separate lifecycle and interrupt design.

- **Shared reporter integration** — `plan_tool/progress.py` remains unchanged because its cross-command heartbeat contract exceeds this step.

- **Status for non-stage roadmap routes or other commands** — The plan requires separate evidence and backlog direction before extending this surface.
