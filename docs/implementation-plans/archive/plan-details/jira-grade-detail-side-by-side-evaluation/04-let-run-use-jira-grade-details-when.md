# Step 4 — Let run use jira-grade details when requested

## Summary

Add an explicit Jira-grade detail selection to `plan-tool run` while keeping run-grade detail as the default. Update `plan_tool/cli/run_cmd.py`, `plan_tool/launcher.py`, and `plan_tool/renderer.py` so an opted-in execution reads the separate compact artifact and renders `plan_tool/prompts/run-jira.md`. Keep all execution lifecycle behavior—preflight, plan advancement, test-order guidance, commit support, and sweep behavior—available for both execution detail grades. On green, ordinary runs remain unchanged and an explicit Jira-grade run fails clearly if its selected artifact is absent.

## Table of Contents

- [Summary](#summary) — Reviewer overview of the selected run-detail grade.
- [Table of Contents](#table-of-contents) — Navigation for this detail.
- [Why](#why) — Why run needs an opt-in compact-detail path.
- [Input](#input) — Upstream artifact and run lifecycle contracts this step consumes.
- [Files (creates vs edits)](#files-creates-vs-edits) — Prompt, CLI, runtime, renderer, docs, and test footprint.
- [Implementation](#implementation) — Grade routing, execution invariants, and prompt selection rules.
- [Tests](#tests) — Unit, command, renderer, and generated-reference coverage.
- [Acceptance criteria](#acceptance-criteria) — Observable selected-detail execution behavior.
- [References](#references) — Primary APIs for path handling and test fixtures.
- [Deferred](#deferred) — Work left to later evaluation and adoption decisions.

## Why

`plan_tool/renderer.py:render_prompt()` always loads the run-grade `Step.detail` body, so `plan-tool run` cannot execute against the compact Jira-grade artifact created by step 2. The experiment needs the same execution lifecycle and repository grounding for either detail contract while preserving run-grade as the control. Selecting the compact artifact must be explicit and must never silently fall back to a run-grade pointer, or the paired evaluation would not be trustworthy.

## Input

- **Step 2 Jira-grade artifacts (prerequisite):** Before implementing this step, confirm that Step 2 exports `plan_tool/detail_artifacts.py:derive_jira_detail_path()` and its plan-path-dependent signature and separate artifact path. This step consumes the confirmed path and must not derive another Jira-grade naming rule.
- **Run-grade control:** `plan_tool/schema.py:Step.detail` remains the stored run-grade pointer. A run without the new selection continues to load it through `plan_tool/renderer.py:_load_detail()`.
- **Execution lifecycle:** `plan_tool/cli/run_cmd.py:cmd_run()`, `_cmd_run_sweep()`, and `plan_tool/launcher.py:run_step()` own the single-step and `--all` execution paths. The selected detail grade must not change their success, failure, or plan-state contracts.
- **Generated CLI reference:** `docs/cli/README.md` and `docs/cli/run.md` are generated from `plan_tool/cli/run_cmd.py:register()` through `plan_tool/cli_reference.py:write_reference()`.

## Files (creates vs edits)

- **New files:**
  - `plan_tool/prompts/run-jira.md` — Define the execution prompt variant for compact Jira-grade detail.

- **Existing files (edits only):**
  - `docs/cli/README.md` — Regenerate the CLI index after adding run detail-grade selection.
  - `docs/cli/run.md` — Regenerate the run command reference with the selection option and unchanged default.
  - `plan_tool/cli/run_cmd.py` — Register the option, select the execution detail grade, preserve execution-only gates, and make missing-detail preflight grade-aware.
  - `plan_tool/launcher.py` — Treat the Jira-grade execution prompt as mutating so successful runs retain the full `run` lifecycle.
  - `plan_tool/renderer.py` — Select the requested detail artifact and prompt template without changing the run-grade renderer.
  - `tests/cli/test_cli_reference.py` — Keep generated-reference drift coverage green.
  - `tests/cli/test_run_cmd.py` — Cover parser selection, command forwarding, compatibility namespaces, preflight, and sweep behavior.
  - `tests/test_launcher.py` — Cover plan-state advancement and execution directives for the Jira-grade run mode.
  - `tests/test_renderer.py` — Cover selected artifact loading, missing-artifact failure, and template shipping/rendering.

## Implementation

- **Make the detail grade explicit.** Add a run option near `plan_tool/cli/run_cmd.py:register()` that accepts the supported grades and defaults to run-grade. Use a named grade rather than a boolean so invalid values fail at the parser boundary and future grade additions stay clear.

- **Keep `--mode run` as the execution entry point.** Let `plan_tool/cli/run_cmd.py:cmd_run()` translate an explicit Jira-grade selection into the internal execution prompt mode used by `plan_tool/launcher.py:run_step()`. Reject an explicit Jira-grade selection with any review `--mode` or `--reconcile` before logs or backend invocation, because those paths render their own audit prompts and cannot consume the selected execution artifact. Keep existing review `--mode` values read-only, and do not expose the internal prompt mode as a general review choice through `plan_tool.cli.app:AVAILABLE_MODES`.

- **Preserve every mutating-run rule.** Update `plan_tool/launcher.py:MUTATING_MODES` and the related `run_step()` branches so a successful Jira-grade execution marks the selected step done, advances the plan, appends lessons when configured, applies the feature test-order directive, captures mutation snapshots, and remains eligible for existing commit handling. Thread `run_step()`'s plan path into the renderer for Jira-grade artifact resolution. A selected Jira-grade run must not be treated like an audit merely because it uses a different prompt file.

- **Keep execution guards grade-aware.** Adapt `plan_tool/cli/run_cmd.py:_warn_missing_step_detail()` and `_confirm_missing_step_details()` so the selected grade determines which artifact is checked. A missing Jira-grade artifact is a grade-aware hard error before backend invocation: it bypasses the warning/confirmation gate and must fail under `-y` or non-interactive stdin. Jira-grade selection must require each expected Jira-grade artifact; do not accept `Step.detail`, a canonical run-grade path, or a same-id sibling as a substitute. Preserve the current run-grade warning and confirmation behavior when the option is omitted.

- **Keep `--all` execution available.** `_cmd_run_sweep()` must continue to reject review modes but allow the explicit Jira-grade execution selection. Its whole-plan preflight must check the selected grade for every runnable step, and each `run_step()` call must receive the matching internal execution mode. Resolve the grade through the same compatibility-safe `getattr(..., "run")` helper used by `cmd_run()`, because direct callers may supply hand-built namespaces without the new field.

- **Preserve the selected grade on rate-limit resume.** Update `plan_tool/cli/run_cmd.py:_build_run_resume_command()` to forward an explicit detail-grade option, so a resumed Jira-grade execution selects the same artifact contract instead of silently reverting to run-grade. Use the shared compatibility-safe grade resolver here too, so direct calls with legacy hand-built namespaces default to run-grade rather than raising `AttributeError`.

- **Load the selected body in one renderer path.** Extend `plan_tool/renderer.py:render_prompt()` and `_build_variables()` so the detail block is chosen by the requested execution mode and accepts the plan path needed for artifact routing. `plan_tool/launcher.py:run_step()` must supply that path before the Jira-grade branch calls `derive_jira_detail_path()`; the branch must not infer it from `Step.detail`. Keep direct renderer calls compatible for run-grade selection, while Jira-grade direct callers must provide the plan path. Keep `_load_detail()` as the run-grade control behavior; add a focused Jira-grade branch that reads only the step 2 artifact route and reports a clear missing-artifact error. Do not change `Step.detail` or reinterpret legacy files.

- **Create a compact execution prompt.** `plan_tool/prompts/run-jira.md` should retain the normal plan context, declared files, scope limits, repository grounding, validation output contract, and test-order directive supplied by `run_step()`. Tailor its detail guidance to the compact `Intent`, `Change`, `Constraints`, `Done when`, and `Out of scope` contract; do not require run-grade file-by-file mechanics or test rosters that the selected artifact does not contain.

- **Keep run-grade behavior unchanged.** A caller without the new field, including hand-built test namespaces passed to `cmd_run()`, `_cmd_run_sweep()`, or `_build_run_resume_command()`, must default to run-grade through one shared compatibility-safe `getattr(..., "run")` grade resolver. Run-grade uses `plan_tool/prompts/run.md`, the existing `Step.detail` resolution, and all current lifecycle behavior.

- **Regenerate generated docs.** After finalizing parser help in `plan_tool/cli/run_cmd.py:register()`, run `python -m plan_tool.cli_reference --write` rather than editing `docs/cli/README.md` or `docs/cli/run.md` by hand.

## Tests

- `tests/cli/test_run_cmd.py::test_run_detail_grade_defaults_to_run` — A parser-produced and compatibility namespace without the new field select the existing run-grade execution path.
- `tests/cli/test_run_cmd.py::test_run_forwards_explicit_jira_detail_grade` — `cmd_run()` passes the Jira-grade execution mode to the module-local `run_step` seam.
- `tests/cli/test_run_cmd.py::test_run_detail_grade_parser_rejects_invalid_value` — The public option accepts only supported detail grades.
- `tests/cli/test_run_cmd.py::test_jira_detail_grade_rejects_review_mode` and `tests/cli/test_run_cmd.py::test_jira_detail_grade_rejects_reconcile` — An explicit Jira-grade selection fails before logs or backend invocation when paired with a review `--mode` or `--reconcile`.
- `tests/cli/test_run_cmd.py::test_jira_grade_preflight_rejects_missing_selected_artifact` — A missing Jira-grade detail stops before backend invocation and does not accept a present run-grade pointer.
- `tests/cli/test_run_cmd.py::test_jira_grade_missing_artifact_hard_fails_noninteractive` — A missing Jira-grade detail fails before backend invocation under `-y` or non-interactive stdin instead of proceeding through confirmation.
- `tests/cli/test_run_cmd.py::test_run_all_jira_grade_checks_selected_artifacts` — `--all` checks Jira-grade artifacts for runnable steps and still permits the execution sweep.
- `tests/cli/test_run_cmd.py::test_run_resume_command_forwards_jira_detail_grade` — A rate-limit resume command preserves explicit Jira-grade selection.
- `tests/cli/test_run_cmd.py::test_run_sweep_legacy_namespace_defaults_to_run_grade` and `tests/cli/test_run_cmd.py::test_run_resume_legacy_namespace_defaults_to_run_grade` — Direct sweep and resume helper calls with hand-built namespaces lacking the new field default to run-grade without raising `AttributeError`.
- `tests/test_launcher.py::test_jira_run_mode_is_mutating` — A successful Jira-grade run advances plan state and is included in `MUTATING_MODES`.
- `tests/test_launcher.py::test_jira_run_mode_adds_feature_test_directive` — A feature-classified step receives the same execution-only test-order directive under Jira-grade selection.
- `tests/test_renderer.py::test_render_jira_run_prompt_reads_jira_detail_artifact` — Jira-grade rendering receives the plan path, includes the separate compact body, and does not read `Step.detail`.
- `tests/test_renderer.py::test_render_jira_run_prompt_requires_plan_path` — Direct Jira-grade rendering fails clearly without the plan path required for artifact routing, while direct run-grade rendering remains compatible.
- `tests/test_renderer.py::test_render_jira_run_prompt_rejects_missing_artifact` — Selected Jira-grade rendering fails clearly when its required artifact is absent.
- `tests/test_renderer.py::test_run_jira_template_ships_and_renders` — `plan_tool/prompts/run-jira.md` exists, substitutes all template variables, and includes plan and step context.
- `tests/cli/test_cli_reference.py::test_every_generated_file_matches_disk` — Regenerated run reference files match the live parser.

### Test-creation order (feature step)

1. `tests/test_renderer.py` selected-artifact and missing-artifact cases — Prove the prompt reads the chosen grade before wiring command dispatch.
2. `tests/test_launcher.py` mutating-mode and test-directive cases — Prove Jira-grade execution preserves the run lifecycle.
3. `tests/cli/test_run_cmd.py` parser, forwarding, hard-error preflight, and sweep cases — Prove the public command selects and enforces the grade.
4. `tests/cli/test_cli_reference.py` drift gate — Regenerate the reference after parser help is final.

Every new test must be green before this step is considered finished.

## Acceptance criteria

- `plan-tool run <plan>` without a detail-grade option uses `plan_tool/prompts/run.md` and the existing run-grade `Step.detail` behavior.
- An explicit Jira-grade run passes its plan path to the renderer and reads only the path returned by `plan_tool/detail_artifacts.py:derive_jira_detail_path()`; it never infers that route from `Step.detail`.
- An explicit Jira-grade selection rejects review `--mode` values and `--reconcile` before logs or backend invocation rather than silently ignoring the selected execution artifact.
- A missing Jira-grade artifact hard-fails before backend invocation, including under `-y` or non-interactive stdin, and is never replaced by a run-grade pointer or fallback path.
- A successful Jira-grade run advances the plan and follows the same test-order, lesson, commit, and failure behavior as a normal `--mode run` execution.
- `plan-tool run <plan> --all` supports explicit Jira-grade execution while preserving its review-mode rejection and selected-grade preflight.
- Jira-grade selection does not write, replace, or reinterpret `Step.detail` and does not overwrite the run-grade artifact.
- `plan_tool/prompts/run-jira.md` grounds execution in the compact contract while retaining the normal run prompt’s scope and completion requirements.
- `docs/cli/README.md`, `docs/cli/run.md`, `tests/cli/test_run_cmd.py`, `tests/test_launcher.py`, `tests/test_renderer.py`, and `tests/cli/test_cli_reference.py` pass with regenerated CLI references.

## References

- [pytest API Reference](https://docs.pytest.org/en/stable/reference/reference.html) — Use fixtures, temporary directories, and parametrization for grade-routing cases.
- [pathlib — Object-oriented filesystem paths](https://docs.python.org/3/library/pathlib.html) — Use path operations when checking separate selected detail artifacts.

## Deferred

- Jira-grade export behavior — Step 3 owns `plan_tool/cli/jira_cmd.py` and `plan_tool/jira.py`.
- Paired evaluation and adoption threshold — Steps 5 and 6 own the evidence and recommendation process.
- Making Jira-grade the default for `run` — Require a later evidence-backed plan; this step keeps run-grade as the default.
- Mechanically prescriptive supplements for individual compact details — Defer until evaluation results show the base Jira-grade contract is insufficient.
