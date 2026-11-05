> **Auto-archived**: this plan was swept on 2026-11-05 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 3 — Retire Jira-grade execution

<!-- plan-tool:detail-format-version: 1 -->

## Summary

Remove the Jira-grade execution selector and alternate detail path so every `run` invocation uses the existing run-grade renderer and `Step.detail` handling. Update `plan_tool/renderer.py`, `plan_tool/launcher.py`, `plan_tool/plan_merge_guard.py`, and `plan_tool/cli/run_cmd.py`; delete `plan_tool/prompts/run-jira.md`. Keep single-step and `--all` sweep execution on their current missing-detail, prompt-budget, preference-write, run-log, and merge-check paths. On green, `--detail-grade` is rejected by argparse, the default run prompt is unchanged, and merge validation always checks declared run-grade details.

## Table of Contents

- [Summary](#summary) — The retained run-grade execution path.
- [Table of Contents](#table-of-contents) — Links to this detail’s sections.
- [Why](#why) — Why execution must stop carrying a retired detail lane.
- [Input](#input) — Existing run-grade contracts this step preserves.
- [Files (creates vs edits)](#files-creates-vs-edits) — Source, prompt, and test changes.
- [Implementation](#implementation) — Remove grade selection while retaining execution behavior.
- [Tests](#tests) — Unit and integration coverage for the removed selector and retained path.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Argparse behavior for removed options.
- [Applicable guardrails](#applicable-guardrails) — Plan boundaries for the retirement.
- [Deferred](#deferred) — Surviving Jira export work outside this execution step.

## Why

The run lane currently carries a second detail reader, prompt template, CLI option, preflight path, run-log field, resume suffix, and merge-check exception for an artifact that this plan retires. That split makes normal execution harder to follow and lets a removed artifact contract affect safety checks. Execution needs one supported input: the canonical run-grade detail declared by the plan.

## Input

- **Run-grade detail contract:** `plan_tool/renderer.py:_load_detail` and `plan_tool/renderer.py:render_prompt` define the current permissive missing-detail rendering and supported detail-format validation. Preserve this behavior.

- **Execution paths:** `plan_tool/cli/run_cmd.py:cmd_run` and `plan_tool/cli/run_cmd.py:_cmd_run_sweep` already use the same run-grade missing-detail helpers, preference writes, run logs, and `plan_tool/launcher.py:run_step` lifecycle.

- **Step 1 outcome:** Step 1 moves review’s fence parser away from `plan_tool/jira_grade.py`; this step can remove execution-only Jira-grade imports without restoring that dependency.

## Files (creates vs edits)

- **New files:** None.

- **Existing files (edits only):**
  - `plan_tool/renderer.py` — Remove grade selection, Jira-grade detail loading, and `run-jira` template selection; retain the run-grade renderer and prompt-byte accounting.
  - `plan_tool/launcher.py` — Make `run_step` run-grade-only and remove grade-specific validation and forwarding.
  - `plan_tool/plan_merge_guard.py` — Remove the grade argument and Jira-derived-detail exception from `check_plan_merged`.
  - `plan_tool/cli/run_cmd.py` — Remove `--detail-grade`, its preflight/conflict/resume/run-log plumbing, and grade branches; retain existing single-step and sweep behavior.
  - `plan_tool/prompts/run-jira.md` — Delete the retired execution prompt.
  - `tests/test_renderer.py` — Remove Jira-grade rendering coverage and add focused checks for rejection of the retired reader surface and unchanged default rendering.
  - `tests/test_launcher.py` — Remove Jira-grade `run_step` cases while retaining run-grade prompt, dry-run, lifecycle, and accounting coverage.
  - `tests/test_plan_merge_guard.py` — Remove Jira-grade merge-guard cases and pin declared run-grade-detail enforcement.
  - `tests/cli/test_run_cmd.py` — Replace grade-routing/preflight tests with parser rejection and class-marked integration coverage for single-step and sweep execution.

## Implementation

- **Keep one renderer input.** Make `plan_tool/renderer.py:render_prompt` and `_build_variables` read only the run-grade body through `_load_detail`. Remove `load_jira_grade_step_detail`, Jira-grade constants and imports used only by execution, and the `run-jira` template selection. A caller must not be able to select an alternate detail body through the renderer.

- **Preserve default output exactly where it matters.** Continue loading `plan_tool/prompts/run.md` for execution, preserving its response-tail contract, scope-fence block, lessons block, and `collect_blocks` measurement of the actual embedded run-grade detail. The prompt-budget advisory and run-log accounting must continue to describe the rendered body.

- **Make `run_step` run-grade-only.** Remove `detail_grade` from `plan_tool/launcher.py:run_step` and its call into `render_prompt`. Retain the prompt-build ordering that converts renderer failures into `LauncherError`, including behavior under `dry_run`, and do not change normal execution writes, step advancement, test-authoring checks, or lesson handling.

- **Return both CLI paths to their existing missing-detail behavior.** Remove `_detail_grade`, `_grade_flag_suffix`, `_reject_detail_grade_conflicts`, and `_preflight_jira_grade_details` from `plan_tool/cli/run_cmd.py`. `cmd_run` must again use `_confirm_missing_step_details` for normal execution, while `_cmd_run_sweep` must retain its whole-plan confirmation and per-step `_warn_missing_step_detail` behavior. Do not add a replacement strict preflight.

- **Remove grade metadata without changing persistence.** Stop adding a detail-grade value to resume commands and run-log flags. Keep `_save_run_prefs` ordering and its existing overwrite behavior unchanged, and preserve all existing run-log creation and execution-result writes.

- **Use declared plan details for merge validation.** Simplify `plan_tool/plan_merge_guard.py:check_plan_merged` to inspect each committed step’s declared `Step.detail`, including its existing undeclared-detail diagnostic. Remove Jira-derived paths and the grade parameter; `plan_tool/cli/run_cmd.py:_preflight_branch_guard` must call the simplified check.

- **Delete the retired prompt rather than leaving a compatibility template.** Remove `plan_tool/prompts/run-jira.md`. Do not add a replacement compact execution prompt or a compatibility reader.

## Tests

### Tests for this step

- `tests/test_renderer.py::TestRenderRunPrompt::test_default_run_rendering_uses_declared_run_grade_detail` — assert normal rendering embeds the declared run-grade detail and retains the existing run prompt framing.

- `tests/test_renderer.py::TestRenderRunPrompt::test_retired_jira_detail_reader_is_not_exposed` — assert the renderer no longer exposes a Jira-grade detail-loading surface.

- `tests/test_renderer.py::TestRenderRunPrompt::test_render_prompt_rejects_removed_detail_grade_selector` — assert direct use of the removed grade-selection argument is rejected rather than selecting another detail source.

- `tests/test_launcher.py::TestRunStep::test_run_step_default_prompt_budget_measures_embedded_run_grade_detail` — assert `run_step` keeps prompt accounting on the run-grade body.

- `tests/test_plan_merge_guard.py::test_merge_check_requires_declared_run_grade_details` — assert merged-plan validation reports missing declared detail paths and does not derive Jira artifact paths.

- `tests/cli/test_run_cmd.py::TestRunHelpSurface::test_run_parser_rejects_removed_detail_grade_for_single_step_execution` — class-marked integration test that `main()` rejects `run <name> --detail-grade jira` before execution.

- `tests/cli/test_run_cmd.py::TestRunAllSweep::test_run_parser_rejects_removed_detail_grade_for_sweep_execution` — class-marked integration test that `main()` rejects `run <name> --all --detail-grade jira` before a sweep begins.

- **Green-before-done gate:** every listed test must pass before this step is complete.

## Acceptance criteria

- `plan-tool run --help` does not list `--detail-grade`.

- `plan-tool run <name> --detail-grade jira` exits through argparse option rejection before opening a run log or invoking execution.

- `plan-tool run <name> --all --detail-grade jira` exits through the same parser rejection before starting a sweep.

- Default `plan_tool.renderer.render_prompt(..., mode="run")` renders `plan_tool/prompts/run.md` with the declared run-grade detail, including existing prompt accounting.

- Both `cmd_run` and `_cmd_run_sweep` retain their run-grade missing-detail confirmation or warning behavior.

- `plan_tool.plan_merge_guard.check_plan_merged` checks declared `Step.detail` paths for committed steps and reports an undeclared detail file as it does on the run-grade path.

- `plan_tool/prompts/run-jira.md` no longer exists, and no run-lane source imports or calls a Jira-grade detail reader.

## References

- [argparse — Parser for command-line options, arguments and subcommands](https://docs.python.org/3.13/library/argparse.html) — Use its option-registration behavior to verify the removed selector is rejected.

## Applicable guardrails

- **The plan’s “## Step intent”.** Limit this work to making execution use the supported run-grade detail and its existing safeguards.

- **The plan’s “## Scope guardrails”.** Do not add compatibility readers, artifact migration, a replacement grade, or an output redesign while removing this lane.

- **The plan’s “## Out of scope”.** Do not change run-grade authoring, Jira export or developer-handoff rendering, publication behavior, or archived evidence.

## Deferred

- **Jira export and developer-handoff consumers** — They remain outside this execution-focused step and must retain their existing rendering and publication contracts.
