> **Auto-archived**: this plan was swept on 2026-11-05 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 3 — Preserve writer-guard origins and terminal records before or during a roadmap run

<!-- plan-tool:detail-format-version: 1 -->

## Summary

Preserve whether a roadmap writer-guard failure happens before the primary run starts or after stage work has begun. Update `plan_tool/roadmap.py` to carry that origin through the primary lifecycle and ensure either path has one complete run-log terminal record. Update `plan_tool/cli/roadmap_cmd.py` so the CLI selects the matrix-defined usage or incomplete-run exit code from that preserved origin. On green, preflight refusal and mid-run writer failure remain distinguishable without changing roadmap retries, publication recovery, or locking behavior.

## Table of Contents

- [Summary](#summary) — Gives the reviewer the step’s result.
- [Table of Contents](#table-of-contents) — Links to each section.
- [Why](#why) — Explains the lost writer-guard origin.
- [Input](#input) — Names the terminal matrix this step consumes.
- [Files (creates vs edits)](#files-creates-vs-edits) — Lists the code and test footprint.
- [Implementation](#implementation) — Defines the origin and terminal-record rules.
- [Tests](#tests) — Lists focused regression coverage.
- [Acceptance criteria](#acceptance-criteria) — States checkable completion conditions.
- [References](#references) — Points to the tracked contract and source locations.
- [Applicable guardrails](#applicable-guardrails) — Applies the plan fence.
- [Deferred](#deferred) — Separates later terminal handling work.

## Why

`plan_tool/roadmap.py:run_roadmap` currently acquires and validates its writer before `_run_roadmap` opens `_roadmap_command_lifecycle`, while a `RoadmapWriterGuardError` during `publish_stage_artifact` can escape after stage work starts. `plan_tool/cli/roadmap_cmd.py:cmd_roadmap` cannot tell those origins apart at its shared catch boundary, so it maps both to usage failure and the preflight path has no owned run-log terminal record. The step must preserve the real lifecycle boundary so operators and automation can distinguish an invalid invocation from a run that did not finish.

## Input

- **Step 1 terminal-disposition matrix:** Read the landed `ROADMAP_FORMAT.md` terminal-disposition section for the selected names, exit codes, run-log outcome, crash behavior, and operator action. Its contract wins if it differs from an older comment or test expectation.

- **Primary lifecycle:** Use `plan_tool/roadmap.py:run_roadmap`, `_run_roadmap`, `_roadmap_command_lifecycle`, and `_error_run_end_fields` as the current ownership boundary for writer acquisition, stage execution, and `run_end`.

- **Writer-guard failure sites:** Use `plan_tool/roadmap.py:_roadmap_writer_owner`, `require_unenrolled_roadmap_writer`, and the `publish_stage_artifact` path in `_run_roadmap` to preserve whether refusal occurred before or after the run started.

- **CLI mapping boundary:** Use `plan_tool/cli/roadmap_cmd.py:cmd_roadmap` and its `run_roadmap` exception handling as the only primary-run exit-code boundary.

## Files (creates vs edits)

- **New files:** None.

- **Existing files (edits only):**
  - `plan_tool/roadmap.py` — Preserve writer-guard origin at the primary-run boundary and ensure preflight refusal as well as mid-run failure reaches exactly one owned terminal record.
  - `plan_tool/cli/roadmap_cmd.py` — Select the matrix-defined CLI result from the preserved primary-run origin.
  - `tests/test_roadmap.py` — Cover origin preservation and owned run-log completion.
  - `tests/cli/test_roadmap_cmd.py` — Cover distinct CLI exit codes for the two origins.

## Implementation

- **Treat origin as part of the failure contract.** Preserve the distinction between writer-guard refusal before the primary lifecycle has started and a writer-guard failure after the run has started. Do not infer origin from an error message at `cmd_roadmap`.

- **Keep the primary lifecycle truthful.** Arrange the primary `run_roadmap` path so a writer-guard refusal before stage work receives an owned terminal record, while a mid-run failure uses the same run’s terminal record. The record must not claim a stage started when guard acquisition or validation refused first.

- **End each owned log once.** Reuse or extend `_roadmap_command_lifecycle` and `_error_run_end_fields` so each path writes one `run_end`, clears the in-flight record, and retains the matrix-selected result. A caller-supplied `run_logger` must keep its current ownership behavior.

- **Use a narrow origin-preserving error boundary.** One approach is a dedicated domain error or wrapper for the after-start writer-guard route, while retaining the existing preflight-facing exception behavior where callers depend on it. The exact type name is free, but `cmd_roadmap` must receive an explicit origin signal rather than a broad application-wide exception framework.

- **Keep stage behavior unchanged.** `_stage_run_guard` must still report a stopped stage for an exception raised during stage work. Do not add a stage status or phase for a preflight refusal.

- **Keep later terminal-output work separate.** This step establishes the origin and run-log facts needed by the terminal matrix. Step 5 owns applying every matrix disposition across primary, materialization, local-revision, status, and crash-report paths.

- **Do not widen writer semantics.** Retain `_roadmap_writer_owner`, writer-token checks, publication recovery, checkpoints, and retry behavior. The change classifies a failure after it occurs; it must not alter who can write or when publication happens.

## Tests

### Tests for this step

- `tests/test_roadmap.py::test_preflight_writer_guard_refusal_has_one_owned_terminal_record` — A guard acquisition or validation refusal before `_run_roadmap` produces one run-log ending and removes the in-flight record without any stage phase or stage-start fact.

- `tests/test_roadmap.py::test_mid_run_writer_guard_failure_preserves_after_start_origin` — A `publish_stage_artifact` writer-guard failure after stage start retains the after-start classification, emits the existing stopped-stage behavior, and produces one run-log ending.

- `tests/test_roadmap.py::test_caller_supplied_logger_is_not_ended_for_writer_guard_origin_paths` — An injected logger remains caller-owned for both origin paths.

- `tests/cli/test_roadmap_cmd.py::test_preflight_writer_guard_refusal_returns_matrix_usage_code` — The preserved preflight origin selects the matrix-defined invalid-invocation exit code.

- `tests/cli/test_roadmap_cmd.py::test_mid_run_writer_guard_failure_returns_matrix_incomplete_code` — The preserved after-start origin selects the matrix-defined failure-to-complete exit code rather than the preflight code.

- **Green-before-done gate:** Every focused test above and `uv run pytest tests/test_roadmap.py tests/cli/test_roadmap_cmd.py -q` must pass before this step is complete.

## Acceptance criteria

- A primary writer-guard refusal before stage work has one run-log terminal record and does not record a stage as started.

- A writer-guard failure during stage publication remains distinguishable from preflight refusal at `plan_tool/cli/roadmap_cmd.py:cmd_roadmap`.

- The CLI returns the Step 1 matrix-defined preflight code for preflight refusal and the matrix-defined incomplete-run code for after-start failure.

- Each owned primary-run path emits exactly one `run_end` and removes its in-flight record.

- Existing stage-stop behavior remains present for writer-guard errors raised during stage work.

- `tests/test_roadmap.py` and `tests/cli/test_roadmap_cmd.py` pass.

## References

- [BACKLOG.md #344](../../../../../BACKLOG.md) — Read the tracked preflight-versus-mid-run writer-guard exit-code problem.

- [ROADMAP_FORMAT.md](../../../../../ROADMAP_FORMAT.md) — Read Step 1’s terminal-disposition matrix before selecting classifications.

- [plan_tool/roadmap.py](../../../../../plan_tool/roadmap.py) — Read `run_roadmap`, `_run_roadmap`, and `_roadmap_command_lifecycle`.

- [plan_tool/cli/roadmap_cmd.py](../../../../../plan_tool/cli/roadmap_cmd.py) — Read `cmd_roadmap`’s primary-run exception and return-code boundary.

## Applicable guardrails

- **The plan’s “## Scope guardrails”, writer and lifecycle boundaries:** Limit this step to preserving failure origin and terminal records; do not redesign writer locking, publication recovery, checkpoints, result outcomes, or retries.

- **The plan’s “## Scope guardrails”, unexpected failures:** Keep unexpected programming defects outside the new domain classification so the application crash boundary remains available.

- **The plan’s “## Scope guardrails”, interrupt handling:** Do not catch or reclassify interrupt and process-exit paths in this step.

- **The plan’s “## Out of scope”, success behavior:** Leave successful output and retry behavior unchanged.

## Deferred

- Materialization and local-revision terminal-disposition application — Step 5 owns applying the shared terminal contract beyond the primary roadmap run.

- Exception terminal-status emission and crash-report integration — Step 5 owns the cross-route terminal-output and crash-boundary work.
