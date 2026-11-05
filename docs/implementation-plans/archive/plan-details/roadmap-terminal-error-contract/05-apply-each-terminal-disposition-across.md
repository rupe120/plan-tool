> **Auto-archived**: this plan was swept on 2026-11-05 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 5 — Apply each terminal disposition across roadmap exits

<!-- plan-tool:detail-format-version: 1 -->

## Summary

Apply the terminal-disposition contract to the primary stage run, draft-seed materialization, and local feedback revision. Update `plan_tool/roadmap.py`, `plan_tool/roadmap_revision_run.py`, and `plan_tool/cli/roadmap_cmd.py` so known failures produce matching human output, terminal status, run-log completion, and exit codes. Keep `plan_tool/cli/app.py` responsible for crash persistence only when an unexpected exception escapes these known routes. On green, the three execution routes report the same matrix-defined disposition for the same failure class.

## Table of Contents

- [Summary](#summary) — Gives the reviewer the completed behavior.
- [Table of Contents](#table-of-contents) — Links to each detail section.
- [Why](#why) — Explains the current disagreement among roadmap exits.
- [Input](#input) — Names the upstream terminal-contract inputs.
- [Files (creates vs edits)](#files-creates-vs-edits) — Lists the bounded code and test footprint.
- [Implementation](#implementation) — Defines terminal-disposition ownership and route coverage.
- [Tests](#tests) — Lists focused regression coverage.
- [Acceptance criteria](#acceptance-criteria) — States observable completion checks.
- [References](#references) — Points to the governing roadmap contracts.
- [Applicable guardrails](#applicable-guardrails) — Keeps the work inside the terminal-error fence.
- [Deferred](#deferred) — Separates adjacent lifecycle work.

## Why

`plan_tool/cli/roadmap_cmd.py:cmd_roadmap` currently emits a terminal status only for returned primary-run results, while `_cmd_roadmap_materialize_owned` and `_cmd_roadmap_revise_feedback` own separate terminal paths. Known failures can therefore reach different combinations of error text, status output, run-log outcome, exit code, and generic crash handling. This step makes the terminal contract consistent at the three real execution exits without changing their underlying execution policies.

## Input

- **Step 1 terminal-disposition matrix:** Use the landed `ROADMAP_FORMAT.md` terminal-disposition section as the authority for disposition names, precedence, run-log outcome, exit code, status text, and crash-report behavior.

- **Step 3 primary origin facts:** Preserve the writer-guard origin carried through `plan_tool/roadmap.py:run_roadmap`, `_roadmap_command_lifecycle`, and `_error_run_end_fields`. Select the disposition from that fact, not from error-message text.

- **Step 4 normalized renderer failures:** Treat the named template failures from `plan_tool/roadmap.py` and `plan_tool/roadmap_revision_run.py` as ordinary roadmap failures under the matrix. Do not recreate route-local read classification.

- **Existing terminal facts:** Keep `plan_tool/roadmap.py:RoadmapResult`, `plan_tool/roadmap_revision_run.py:LocalRevisionResult`, and `RoadmapSeedRefreshResult` as the route-specific result boundaries. This step consumes their facts; it does not redesign their outcome vocabularies.

## Files (creates vs edits)

- **New files:** None.

- **Existing files (edits only):**
  - `plan_tool/roadmap.py` — Extend the terminal-status seam around `emit_roadmap_terminal_status`, `_roadmap_command_lifecycle`, and primary-run failure handling so matrix-selected primary dispositions can be emitted without changing stage retries or publication behavior.
  - `plan_tool/roadmap_revision_run.py` — Carry the local revision’s known terminal category and outcome through `run_local_feedback_revision`, `_attempt_result`, and `_result_return_code` for matrix-consistent rendering and logging.
  - `plan_tool/cli/roadmap_cmd.py` — Apply one disposition-aware rendering and exit mapping at the primary, outer `_cmd_roadmap_materialize` preflight boundary, `_cmd_roadmap_materialize_owned`, and `_cmd_roadmap_revise_feedback` exits.
  - `tests/test_roadmap.py` — Cover primary terminal status and owned run-log completion for each relevant disposition.
  - `tests/test_roadmap_revision_run.py` — Cover local revision preflight, expected failure, publication, and run-log terminal facts.
  - `tests/cli/test_roadmap_cmd.py` — Cover human output, terminal status, exit codes, and no-crash behavior across all three routes.
  - `tests/cli/test_app.py` — Prove unexpected roadmap defects still reach the generic crash-report boundary.

## Implementation

- **Use disposition, not route, as the terminal decision.** Apply step 1’s matrix to each ordinary exit from the primary run, materialization batch, and local revision. The same classified failure must produce the same operator-facing category and exit code regardless of which route encountered it.

- **Keep each route’s lifecycle owner.** `plan_tool/roadmap.py:_roadmap_command_lifecycle` remains the primary-run `run_end` owner. `_cmd_roadmap_materialize_owned` remains the materialization lifecycle owner, including its partial-batch facts. `run_local_feedback_revision` remains the local revision logger owner. Do not move lifecycle ownership into `plan_tool/cli/roadmap_cmd.py`.

- **Emit terminal status for every terminal disposition.** Extend `plan_tool/roadmap.py:emit_roadmap_terminal_status`, or use a small adjacent adapter, so the CLI reports matrix-defined terminal status for returned results and classified expected failures. Before an unexpected exception is rethrown to `plan_tool/cli/app.py`, make exactly one best-effort unexpected-disposition status attempt; that attempt must not replace the original exception or suppress crash persistence.

- **Preserve primary writer-guard precedence.** Use the origin preserved by step 3 to keep a refusal before the primary lifecycle distinct from a writer failure after work starts. Do not classify either path by matching its detail string.

- **Cover materialization before and during its lifecycle.** At `plan_tool/cli/roadmap_cmd.py:_cmd_roadmap_materialize`, record a matrix-selected pre-lifecycle terminal disposition when outer `_roadmap_writer_owner` acquisition refuses before `_cmd_roadmap_materialize_owned` starts. In `_cmd_roadmap_materialize_owned`, retain the distinction among no-op, completed work, partial work, and exhausted row attempts. Do not turn partial materialization into a simple all-or-nothing failure or claim that a preflight refusal started row work.

- **Keep local revision’s one-shot boundary.** In `plan_tool/roadmap_revision_run.py:run_local_feedback_revision` and `_run_accepted_revision`, preserve the rule that accepted preflight permits at most one backend request. Prompt-build, invocation, merge, validation, and publication failures must retain their existing local attempt record while receiving the matrix-defined terminal treatment.

- **Keep expected failures out of the crash boundary.** Known `RoadmapError`, `RoadmapEnvironmentalError`, artifact errors, and normalized prompt failures must be handled before `plan_tool/cli/app.py:main` reaches its generic `except Exception` branch. Unexpected programming errors must still escape there and retain crash persistence.

- **Do not widen exception handling.** Do not add handling for `KeyboardInterrupt`, `SystemExit`, or arbitrary `BaseException` merely to force a disposition. Preserve the existing interruption path and its `130` result.

- **Avoid a second application-wide framework.** One focused roadmap terminal mapping is enough. A shared helper is appropriate only if it keeps the matrix lookup and rendering consistent inside the declared roadmap files.

## Tests

### Tests for this step

- `tests/test_roadmap.py::test_primary_preflight_refusal_records_matrix_terminal_disposition` — asserts a primary preflight refusal records one matrix-selected `run_end` and does not start stage work.

- `tests/test_roadmap.py::test_primary_mid_run_failure_records_incomplete_terminal_disposition` — asserts a failure after primary work begins keeps the step-3 origin, records the expected terminal outcome, and does not become a usage refusal.

- `tests/test_roadmap.py::test_primary_expected_failure_emits_terminal_status_without_raising` — asserts a classified primary failure reaches the status seam and preserves its human-safe terminal text.

- `tests/test_roadmap_revision_run.py::test_local_revision_preflight_rejection_uses_terminal_disposition` — asserts selector or admission rejection returns the matrix-defined local category, usage exit fact, and one `run_end`.

- `tests/test_roadmap_revision_run.py::test_local_revision_expected_prompt_or_invocation_failure_uses_terminal_disposition` — asserts a normalized expected failure records one local attempt and one matching terminal record without a second backend call.

- `tests/test_roadmap_revision_run.py::test_local_revision_published_result_keeps_success_terminal_disposition` — asserts publication remains successful and does not receive an error status.

- `tests/cli/test_roadmap_cmd.py::test_primary_known_error_renders_matrix_error_status_and_exit_code` — asserts the primary command path agrees on error text, terminal status, and matrix-selected return code.

- `tests/cli/test_roadmap_cmd.py::test_materialize_preflight_refusal_renders_matrix_error_status_and_exit_code` — asserts materialization refusal reports its terminal status and retains no backend activity.

- `tests/cli/test_roadmap_cmd.py::test_materialize_outer_writer_guard_refusal_records_pre_lifecycle_terminal_disposition` — asserts refusal before the owned materialization lifecycle records exactly one matrix-selected status, run-log ending, exit code, and no row work.

- `tests/cli/test_roadmap_cmd.py::test_materialize_partial_batch_keeps_partial_result_and_terminal_disposition` — asserts completed earlier rows remain reported while the terminal status and return code reflect the matrix-defined partial outcome.

- `tests/cli/test_roadmap_cmd.py::test_local_revision_known_failure_renders_matrix_error_status_and_exit_code` — asserts local revision uses the same terminal treatment as an equivalent primary failure.

- `tests/cli/test_app.py::test_unexpected_roadmap_exception_emits_status_then_writes_crash_report` — asserts an unclassified defect makes exactly one best-effort unexpected-disposition status attempt, reaches `plan_tool/cli/app.py:main`’s generic crash path, and preserves the original exception.

Every listed test must be green before this step is complete.

## Acceptance criteria

- Primary stage-run preflight refusal and post-start expected failure select different matrix rows when their preserved origins differ.

- A known primary, materialization, or local-revision failure produces matching matrix-defined human error, terminal status, run-log outcome, and exit code.

- Each owned primary, materialization, and local revision run writes exactly one `run_end` event for an ordinary terminal disposition.

- A materialization writer-guard refusal before its owned lifecycle starts records exactly one pre-lifecycle terminal disposition without claiming row work began.

- Materialization retains its completed, no-op, partial, and exhausted batch facts while adding terminal-status coverage.

- Local revision never makes more than one backend call after accepted preflight, including when its terminal disposition is an expected failure.

- Normalized template failures do not create a generic crash report.

- An unexpected roadmap defect makes exactly one best-effort terminal-status attempt, then still reaches `plan_tool/cli/app.py:main`’s crash-report path with its original exception.

- `tests/test_roadmap.py`, `tests/test_roadmap_revision_run.py`, `tests/cli/test_roadmap_cmd.py`, and `tests/cli/test_app.py` pass.

## References

- [ROADMAP_FORMAT.md — terminal-disposition matrix and roadmap terminal vocabulary](../../../../ROADMAP_FORMAT.md)

- [BACKLOG.md #344 — writer-guard origin and exit-code distinction](../../../../BACKLOG.md)

- [BACKLOG.md #347 — roadmap text-read exception-family boundary](../../../../BACKLOG.md)

- [BACKLOG.md #348 — roadmap-level terminal status on exception exits](../../../../BACKLOG.md)

- [BUG_BACKLOG.md — prompt-template failures that must avoid the generic crash path](../../../../BUG_BACKLOG.md)

## Applicable guardrails

- **The plan’s “## Scope guardrails”, model replies:** Do not capture or persist model replies while adding terminal facts or error rendering.

- **The plan’s “## Scope guardrails”, interrupts:** Keep interruption behavior outside this step’s ordinary-disposition handling.

- **The plan’s “## Scope guardrails”, execution behavior:** Do not redesign result outcomes, retry loops, publication recovery, checkpoints, or writer locking to make terminal mapping easier.

- **The plan’s “## Scope guardrails”, unexpected defects:** Preserve `plan_tool/cli/app.py` crash reporting for unclassified programming errors.

- **The plan’s “## Scope guardrails”, framework scope:** Keep terminal handling focused on roadmap exits and do not introduce an application-wide exception system.

- **The plan’s “## Out of scope”, adjacent lifecycle work:** Do not add response receipts, rollback behavior, normal-break enforcement, or success-output changes.

## Deferred

- Cross-command exception normalization — broader command families need separate scope because this step only aligns the three roadmap execution exits.

- Interrupt and second-interrupt semantics — remain with the plan’s cited out-of-scope tracking rather than being folded into ordinary terminal dispositions.
