# Step 3 — Let jira read jira-grade details

## Summary

Add an explicit Jira-detail selection to `plan-tool jira` while keeping run-grade detail as the default input. Update `plan_tool/cli/jira_cmd.py` and `plan_tool/jira.py` so prompt rendering, exported plan-detail links, and append-mode refreshes use the selected detail grade. Create `plan_tool/prompts/jira-jira.md` for story generation grounded in the compact Jira-grade contract, and update the generated CLI reference plus `JIRA_FORMAT.md`. On green, an opt-in Jira export reads only the separate Jira-grade artifacts from step 2; ordinary Jira exports continue to read run-grade `Step.detail` files.

## Table of Contents

- [Summary](#summary) — Reviewer overview of the selected-detail Jira export.
- [Table of Contents](#table-of-contents) — Navigation for this detail.
- [Why](#why) — Why Jira needs a compact-detail input path.
- [Input](#input) — Step 2 artifacts and current Jira export contracts.
- [Files (creates vs edits)](#files-creates-vs-edits) — Prompt, CLI, export, documentation, and test footprint.
- [Implementation](#implementation) — Depth routing and append-mode rules.
- [Tests](#tests) — Unit, CLI, and generated-reference coverage.
- [Acceptance criteria](#acceptance-criteria) — Observable selected-detail export behavior.
- [References](#references) — Path and test APIs relevant to the change.
- [Deferred](#deferred) — Default changes and run consumption left to later work.

## Why

`plan_tool/jira.py:render_jira_prompt()` currently reads only `Step.detail`, which is the retained run-grade pointer. Step 2 creates compact Jira-grade files at separate paths and deliberately leaves that pointer unchanged, so Jira cannot use the new contract without an explicit depth-aware read path. The export must let the experiment compare story generation from either grade without silently treating a Jira-grade artifact as run-grade or changing the existing default.

## Input

- **Step 2 Jira-grade artifacts:** Step 2 produces validated compact files through `plan_tool/detail_artifacts.py:derive_jira_detail_path()`. Jira-grade selection must use that route and must not infer the file from `Step.detail`.
- **Run-grade control:** `plan_tool/schema.py:Step.detail` remains the run-grade pointer. `plan_tool/jira.py:_render_step_detail()` and the `step_detail_map` passed to `format_markdown()` and `format_json()` currently consume that control path.
- **Export lifecycle:** `plan_tool/jira.py:export_jira()` and `_export_jira_append()` preserve created tickets, while `_ticket_needs_detail_refresh()` decides whether an existing ticket must be re-emitted with the same id.
- **CLI reference:** `docs/cli/README.md` and `docs/cli/jira.md` are generated from `plan_tool/cli/jira_cmd.py:register()` through `plan_tool/cli_reference.py:write_reference()`.

## Files (creates vs edits)

- **New files:**
  - `plan_tool/prompts/jira-jira.md` — Define the Jira-story prompt variant that uses compact Jira-grade step details while retaining the existing JSON story response contract.

- **Existing files (edits only):**
  - `JIRA_FORMAT.md` — Document selected detail grades, the unchanged run-grade default, Jira-grade artifact links, and refresh behavior.
  - `docs/cli/README.md` — Regenerate the CLI reference index after adding the Jira detail-selection option.
  - `docs/cli/jira.md` — Regenerate the Jira command reference with the new option and its default.
  - `plan_tool/cli/jira_cmd.py` — Register the explicit selection option and forward it from `cmd_jira()` to the exporter.
  - `plan_tool/jira.py` — Select the prompt and per-step artifact paths by grade in `render_jira_prompt()`, `export_jira()`, `_export_jira_append()`, and refresh/rendering helpers.
  - `tests/cli/test_cli_reference.py` — Keep generated-reference drift coverage green for the Jira option.
  - `tests/cli/test_jira_cmds.py` — Cover parser and command forwarding behavior.
  - `tests/test_jira.py` — Cover selected prompt input, missing-artifact failure, output links, append refresh, and default compatibility.

## Implementation

- **Make Jira detail grade explicit.** Add one named selection at `plan_tool/cli/jira_cmd.py:register()` with run-grade as the default and Jira-grade as an opt-in. `cmd_jira()` should forward that selection to `plan_tool/jira.py:export_jira()`; use a compatibility-safe default when a programmatic caller’s namespace lacks the new field.

- **Keep run-grade as the control path.** A normal `plan-tool jira <plan>` invocation must keep selecting `Step.detail`, rendering `plan_tool/prompts/jira.md`, and producing the same `plan_detail_paths` or `## Plan details` entries as today. Do not repoint, rewrite, or reinterpret `Step.detail`.

- **Select artifacts through the shared route.** For explicit Jira-grade export, derive and validate every selected artifact through step 1’s `plan_tool/detail_artifacts.py:derive_jira_detail_path()` before `read_existing_export()` or append-mode no-op handling, and require each expected Jira-grade file to exist. Do not fall back to a run-grade pointer, a canonical run path, or a same-id filename when the user selected Jira-grade; a missing or mislabeled artifact must fail before invoking the model or writing an export, even when an existing export is fully covered.

- **Carry the selected detail context through prompt rendering.** Adapt `plan_tool/jira.py:render_jira_prompt()`, `_render_steps_block()`, and `_render_step_detail()` so they receive enough plan-path and grade context to read the selected file for each step. The Jira-grade branch should render the compact body and its actual repo-relative path; the run-grade branch keeps the current placeholder and missing-pointer wording.

- **Use a separate prompt without changing the story schema.** `plan_tool/prompts/jira-jira.md` should preserve the JSON object shape validated by `plan_tool/jira.py:parse_jira_response()`, including story ids, coverage, dependencies, estimates, layer metadata, and acceptance criteria. Tailor its guidance to turn `Intent`, `Change`, `Constraints`, `Done when`, and `Out of scope` into clear, atomic Jira stories; do not require run-grade mechanics, file-by-file instructions, or test rosters absent from the compact artifact.

- **Refresh only missing-detail placeholders.** Build the detail-path map in `export_jira()` from the chosen grade and pass it through formatting and `_export_jira_append()`. `_ticket_needs_detail_refresh()` may re-emit the same ticket id only when its stored detail is a documented missing-detail placeholder; detail-link differences alone must not refresh a fully detailed frozen ticket when Jira-grade is selected.

- **Keep frozen-ticket guarantees intact.** Preserve `read_existing_export()`, id sequencing, status reconciliation, and append-mode coverage rules. A grade change may refresh a documented missing-detail placeholder, but it must not renumber a created ticket or rewrite a fully detailed frozen ticket.

- **Regenerate rather than hand-edit CLI reference files.** After the parser help is final, run `python -m plan_tool.cli_reference --write` so `docs/cli/README.md` and `docs/cli/jira.md` match the live parser.

## Tests

- `tests/test_jira.py::test_render_jira_prompt_default_uses_run_detail — The default prompt includes the pointed run-grade detail and existing placeholder behavior.`
- `tests/test_jira.py::test_render_jira_prompt_jira_grade_uses_separate_artifact — Explicit Jira-grade rendering includes the compact artifact and never reads the run-grade pointer.`
- `tests/test_jira.py::test_jira_grade_export_rejects_missing_artifact — A selected Jira-grade file that is absent fails before model invocation, export writes, or append-mode no-op handling, including when an existing export is fully covered.`
- `tests/test_jira.py::test_jira_grade_export_links_selected_paths — Markdown and JSON exports record the Jira-grade paths for covered steps.`
- `tests/test_jira.py::test_append_refreshes_missing_detail_placeholder_for_selected_jira_detail — A ticket with the documented missing-detail placeholder is refreshed with the same id when Jira-grade detail is selected.`
- `tests/test_jira.py::test_append_preserves_fully_detailed_run_grade_ticket_when_jira_grade_is_selected — A fully detailed frozen run-grade ticket remains verbatim when Jira-grade detail is selected.`
- `tests/test_jira.py::test_export_jira_default_remains_run_grade — Existing callers without a grade argument retain current prompt, output, and append behavior.`
- `tests/cli/test_jira_cmds.py::test_cmd_jira_forwards_explicit_detail_grade — The command passes the selected grade to the module-local `export_jira` seam.`
- `tests/cli/test_jira_cmds.py::test_cmd_jira_missing_detail_grade_defaults_to_run — A compatibility namespace without the new field still exports as run-grade.`
- `tests/cli/test_jira_cmds.py::test_jira_detail_grade_parser_rejects_invalid_value — The public parser accepts only the supported detail grades.`
- `tests/cli/test_cli_reference.py::test_every_generated_file_matches_disk — Regenerated Jira reference files remain byte-identical to parser output.`

### Test-creation order (feature step)

1. Add `tests/test_jira.py` prompt and artifact-selection cases for default run-grade, explicit Jira-grade, missing Jira-grade files, and a fully covered existing export that cannot bypass the missing-artifact failure.
2. Add export and append-mode cases that prove selected paths reach rendered output without changing ticket ids.
3. Add `tests/cli/test_jira_cmds.py` parser and forwarding cases, including a namespace without the new option.
4. Regenerate `docs/cli/README.md` and `docs/cli/jira.md`, then run the CLI-reference drift test.

Every new test must be green before this step is considered finished.

## Acceptance criteria

- `plan-tool jira <plan>` without a detail-grade option continues to use `Step.detail` and `plan_tool/prompts/jira.md`.
- An explicit Jira-grade export reads only the compact artifact selected by `plan_tool/detail_artifacts.py:derive_jira_detail_path()`.
- A missing Jira-grade artifact produces a clear error before `read_existing_export()` can take an append-mode no-op, without invoking the model or writing `jira-stories.md` or `jira-stories.json`.
- Jira-grade prompt rendering uses `plan_tool/prompts/jira-jira.md` and retains the JSON response contract enforced by `parse_jira_response()`.
- Markdown `## Plan details` and JSON `plan_detail_paths` identify the selected grade’s files for every covered step.
- Append mode refreshes a ticket with its existing id only when its stored detail is the documented missing-detail placeholder; a fully detailed frozen run-grade ticket remains verbatim when Jira-grade detail is selected.
- Jira-grade selection does not mutate `Step.detail`, overwrite a run-grade artifact, or change the default Jira export behavior.
- `JIRA_FORMAT.md`, `tests/test_jira.py`, `tests/cli/test_jira_cmds.py`, and `tests/cli/test_cli_reference.py` pass with regenerated CLI reference files.

## References

- [pytest API Reference](https://docs.pytest.org/en/stable/reference/reference.html) — Use temporary paths, fixtures, and parametrization for grade-selection and append-mode tests.
- [pathlib — Object-oriented filesystem paths](https://docs.python.org/3/library/pathlib.html) — Use deterministic path operations when selecting separate detail artifacts.

## Deferred

- Opt-in run consumption of Jira-grade detail — Step 4 owns `plan_tool/cli/run_cmd.py`, `plan_tool/launcher.py`, and the run prompt.
- Paired evaluation and any default inversion — Steps 5 and 6 collect evidence; this step keeps run-grade as the default for Jira.
- Mechanically prescriptive Jira-detail supplements — Defer until the experiment shows the compact contract needs an escape hatch.
