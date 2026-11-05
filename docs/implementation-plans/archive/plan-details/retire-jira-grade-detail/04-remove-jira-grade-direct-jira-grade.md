> **Auto-archived**: this plan was swept on 2026-11-05 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 4 — Retire Jira-grade export input

<!-- plan-tool:detail-format-version: 1 -->

## Summary

Make Jira export run-grade-only by removing `jira --grade` and the Jira-grade capture and prompt branches. Update `plan_tool/jira.py` and `plan_tool/cli/jira_cmd.py` while keeping the current story rendering, developer-handoff rendering, provenance, destinations, target checks, staging cleanup, and paired publication unchanged. Update `tests/test_jira.py` and `tests/cli/test_jira_cmds.py` to cover the retained run-grade pair and argparse rejection of the removed selector. On green, every Jira export uses `Step.detail` run-grade input and produces the same paired artifacts through the existing publication path.

## Table of Contents

- [Summary](#summary) — The retained run-grade export path and expected result.
- [Table of Contents](#table-of-contents) — Links to this detail’s sections.
- [Why](#why) — Why export must stop carrying a retired input lane.
- [Input](#input) — Existing paired-export contracts this step consumes.
- [Files (creates vs edits)](#files-creates-vs-edits) — The focused source and test changes.
- [Implementation](#implementation) — Remove selection while preserving paired export behavior.
- [Tests](#tests) — Unit and CLI integration coverage for the retained and removed behavior.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — The argparse reference for removed options.
- [Applicable guardrails](#applicable-guardrails) — Plan boundaries for this retirement.
- [Deferred](#deferred) — Related work outside this step’s declared files.

## Why

`plan_tool/jira.py` currently selects between two detail inputs and changes the prompt for Jira-grade input, while `plan_tool/cli/jira_cmd.py` still exposes that choice to users. The supported detail contract is run grade, so keeping an alternate capture path makes export behavior harder to follow and leaves retired artifacts able to affect output. This step makes the paired story and handoff export honestly use one input source without changing the established output or publication contracts.

## Input

- **Run-grade detail input:** `plan_tool/jira.py:_capture_run_grade_step_detail` reads `Step.detail`, validates the supported detail marker, code fences, and required run-grade sections, and supplies the captured text to both paired renderers.

- **Paired export snapshot:** `plan_tool/jira.py:capture_companion_export_input` freezes plan, detail, file-excerpt, output-target, and story-source state before rendering. Preserve this single-snapshot rule so stories and handoffs continue to describe the same inputs.

- **Step 1 outcome:** Step 1 removes the shared fence-parser dependency from the retiring Jira-grade module. This step must remove its export-only Jira-grade imports and branches without restoring that dependency.

## Files (creates vs edits)

- **New files:** None.

- **Existing files (edits only):**
  - `plan_tool/jira.py` — Remove Jira-grade imports, validation, detail capture, prompt additions, and grade-selection parameters; retain the run-grade capture and paired rendering/publication path.
  - `plan_tool/cli/jira_cmd.py` — Remove `--grade`, grade imports, lint-grade handling, and grade forwarding from Jira export dispatch.
  - `tests/test_jira.py` — Remove Jira-grade export cases and retain focused run-grade capture, rendering, output-safety, staging, and publication coverage.
  - `tests/cli/test_jira_cmds.py` — Replace grade-forwarding coverage with class-marked CLI integration coverage for successful run-grade paired export and argparse rejection of `--grade`.

## Implementation

- **Keep one export input:** Make `plan_tool/jira.py:capture_companion_export_input` capture every committed step through `plan_tool/jira.py:_capture_run_grade_step_detail`. Remove the alternate capture route, grade validation, and public grade arguments from `capture_companion_export_input`, `render_jira_export`, and `export_jira`.

- **Keep run-grade validation strict:** Preserve the existing distinction between a done step with missing detail and a committed non-done step without valid detail. A present run-grade file must still pass `plan_tool/detail_artifacts.py:require_supported_detail_format_version`, required-section checking in `plan_tool/jira.py:_run_grade_detail_missing_sections`, and unmatched-fence rejection before model invocation or output writes.

- **Remove prompt divergence:** Make `plan_tool/jira.py:render_companion_export_prompt` always render `plan_tool/prompts/jira.md` from the captured run-grade data. Remove the Jira-grade-only prose directive rather than replacing it with another prompt mode.

- **Preserve rendering and provenance:** Continue building story output through `plan_tool/jira.py:regenerate_companion_stories` and handoff output through `plan_tool/jira.py:_build_handoff_render_input`. Feed the existing run-grade provenance value through the established handoff/provenance contract; do not redesign output text, output paths, or provenance fields.

- **Preserve destination safety:** Keep `plan_tool/jira.py:_capture_target_preflight`, `plan_tool/jira.py:_all_detail_artifact_paths`, and `plan_tool/jira.py:_companion_target_preflight` protecting generated story and handoff paths from collisions with detail artifacts and detail-bundle locations. Remove checks that exist only to identify the retired Jira-grade lane, but do not weaken the remaining run-grade collision and containment checks.

- **Preserve paired publication ordering:** Do not alter `plan_tool/jira.py:_publish_companion_pair`, `plan_tool/jira.py:_stage_companion_output`, `_confirm_target_unchanged`, `_replace_staged_output`, or `_cleanup_staged_outputs`. Both outputs must stage before either target is rechecked or replaced; staged files must still be cleaned up after success or failure; publication may still report a partial pair if the second `os.replace` fails.

- **Remove the CLI selector at registration:** Delete `--grade` from `plan_tool/cli/jira_cmd.py:register` so argparse rejects it. Simplify `cmd_jira` and `_cmd_jira_paired_export` to use the fixed run-grade export contract, including `--no-write`; do not add a manual compatibility refusal that leaves the selector registered.

- **Keep direct Jira behavior on the default:** `plan_tool/cli/direct_cmd.py:cmd_direct_jira` supplies a hand-built namespace without a grade attribute. The simplified `plan_tool/cli/jira_cmd.py:cmd_jira` must continue to accept that caller without adding a new namespace requirement.

## Tests

### Tests for this step

- `tests/test_jira.py:test_companion_capture_uses_declared_run_grade_detail_for_story_and_handoff` — asserts one run-grade detail snapshot supplies both rendered artifacts and retains the detail path in story and handoff output.
- `tests/test_jira.py:test_run_grade_export_rejects_invalid_detail_before_invoker_or_target_write` — asserts unsupported markers, missing required sections, and unmatched fences stop export before the backend or either final target is written.
- `tests/test_jira.py:test_run_grade_paired_export_preserves_matching_provenance` — asserts published story and handoff retain matching provenance from the same run-grade capture.
- `tests/test_jira.py:test_companion_target_preflight_rejects_run_grade_detail_collision_before_model_or_renderer` — asserts story or handoff destinations cannot overwrite a run-grade detail artifact or land inside its protected bundle.
- `tests/test_jira.py:test_companion_second_final_replace_failure_reports_partial_pair_and_cleans_staging` — retains the second-replace failure case, including removal of staged temporary files and the required recovery diagnostic.
- `tests/cli/test_jira_cmds.py:TestCmdJiraPairedExport.test_default_export_uses_run_grade_without_grade_argument` — class-marked integration test that drives `main()` and asserts normal paired export succeeds without a grade selector.
- `tests/cli/test_jira_cmds.py:TestCmdJiraPairedExport.test_jira_grade_selector_is_rejected_by_argparse` — class-marked integration test that asserts `jira ... --grade jira` exits with argparse’s option-rejection path before export dispatch.

Every listed test must be green before this step is finished.

## Acceptance criteria

- `plan_tool/cli/jira_cmd.py:register` does not register `jira --grade`, and argparse rejects both `--grade jira` and any other `--grade` value.
- `plan_tool/jira.py:capture_companion_export_input`, `render_jira_export`, and `export_jira` have no caller-selectable detail-grade input.
- A committed non-done step with a valid `Step.detail` run-grade file produces both a concise story export and developer handoff from one captured snapshot.
- Run-grade structural failures stop before backend invocation and before either output target is written.
- Existing story and handoff destinations, formatting, provenance, target ownership checks, and default path derivation remain unchanged.
- `plan_tool/jira.py:_publish_companion_pair` still stages both files before replacement, uses paired `os.replace` publication, and cleans staged files on every exit path.
- `tests/test_jira.py` and the class-marked `tests/cli/test_jira_cmds.py:TestCmdJiraPairedExport` cases pass.

## References

- [argparse — Parser for command-line options, arguments and subcommands](https://docs.python.org/3.13/library/argparse.html) — Use the option-registration behavior to verify removal rejects the retired selector.

## Applicable guardrails

- **The plan’s “## Step intent”:** Keep Jira stories and developer handoffs on the same supported run-grade source.
- **The plan’s “## Scope guardrails”:** Remove the retired lane without adding compatibility readers, migrations, replacement grades, output redesign, or compact-schema work.
- **The plan’s “## Out of scope”:** Preserve run-grade authoring and the current story and handoff rendering, destination, provenance, and publication contracts.

## Deferred

- `plan_tool/jira_handoff.py` schema and renderer redesign — retain its existing provenance/rendering contract with the fixed run-grade input; changing that shared output surface is outside this step’s declared files.
- Documentation and remaining Jira-grade consumers outside the declared file list — handle through their owning retirement steps rather than widening this export-focused change.
