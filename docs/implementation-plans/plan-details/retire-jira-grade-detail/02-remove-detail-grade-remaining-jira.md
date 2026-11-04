# Step 2 — Remove Jira-grade detail authoring

<!-- plan-tool:detail-format-version: 1 -->

## Summary

Remove the Jira-grade authoring path from `plan_tool/detail.py`, including its prompt renderer, writer dispatch, and grade selectors. Remove `detail --grade` from `plan_tool/cli/authoring.py` so argparse rejects the old selector instead of routing it to a second rejection layer. Delete `plan_tool/prompts/detail-jira.md` and retire tests that exercise compact-detail authoring. Preserve the run-grade writer and its replacement, migration, rollback, orphan-archive, and saved-output behavior.

## Table of Contents

- [Summary](#summary) — The authoring surface that is removed and the behavior retained.
- [Table of Contents](#table-of-contents) — Links to each section.
- [Why](#why) — Why the dead authoring lane must be removed rather than retained as a refusal path.
- [Files (creates vs edits)](#files-creates-vs-edits) — The focused source, prompt, and test changes.
- [Implementation](#implementation) — The remaining run-grade-only authoring flow and its preserved lifecycle.
- [Tests](#tests) — Unit and CLI coverage for the retained and rejected behavior.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — The argparse reference for selector removal.
- [Applicable guardrails](#applicable-guardrails) — The plan boundaries this step must keep.
- [Deferred](#deferred) — Jira-grade reader and consumer work outside this authoring step.

## Why

`plan_tool/cli/authoring.py:cmd_detail` currently accepts a Jira-grade selector only to reject it, while `plan_tool/detail.py` still carries unreachable prompt, parse, dispatch, overwrite, and archive code for that grade. Keeping both the selector and the dormant writer makes the supported run-grade route harder to understand and leaves code that can drift despite having no valid authoring use. This step makes detail authoring honestly run-grade-only while leaving existing Jira-grade consumers to their owning work.

## Files (creates vs edits)

- **New files:** None.

- **Existing files (edits only):**
  - `plan_tool/detail.py` — Remove Jira-grade authoring constants, prompt rendering, direct writer dispatch, grade-based branches, and Jira-only overwrite/archive lifecycle code; retain the run-grade lifecycle and helpers it needs.
  - `plan_tool/cli/authoring.py` — Remove the `detail --grade` parser argument, grade-resolution and refusal helpers, grade imports, and grade plumbing into detail generation and follow-up handling.
  - `plan_tool/prompts/detail-jira.md` — Delete the retired Jira-grade authoring prompt.
  - `tests/test_detail.py` — Remove tests for retired Jira-grade prompt and writer behavior; retain and strengthen run-grade lifecycle coverage.
  - `tests/cli/test_authoring_cmds.py` — Replace grade-routing tests with class-marked integration coverage that argparse rejects the removed `--grade` selector, and preserve run-grade CLI behavior coverage.

## Implementation

- **Make `generate_detail` run-grade-only.** Remove its `grade` selector and the defensive Jira-grade rejection in `plan_tool/detail.py:generate_detail`. Its public contract must continue to author the canonical run-grade detail path and update the plan’s `Step.detail` pointer without requiring callers to select a grade.

- **Remove the unreachable Jira authoring lane.** Delete Jira-only authoring surfaces such as `render_jira_detail_prompt`, `_generate_jira_detail`, and the Jira-specific authoring branches in `_author_detail_step`. Remove associated direct path selection through `derive_jira_detail_path` from this module. Keep Jira-grade parsing or reading behavior only where it serves a surviving non-authoring consumer; this step must not add a replacement authoring route or a compatibility writer.

- **Keep the run-grade writer lifecycle intact.** Preserve the canonical run-grade path derived through `plan_tool/detail_artifacts.py:derive_detail_path`, the existing replacement behavior, split migration and rollback renames, `plan_tool/detail.py:_archive_existing_detail`, `plan_tool/detail.py:_archive_orphan_details`, checkpoint handling, and saved-output writes. Removing Jira branches must not alter the ordering that keeps an old run-grade artifact recoverable while its replacement becomes canonical.

- **Remove CLI selection instead of retaining a custom refusal.** In `plan_tool/cli/authoring.py:register`, remove the `--grade` argument from the `detail` parser. Remove `_detail_grade`, `_reject_disabled_detail_authoring_grade`, the disabled-authoring message import, and downstream grade forwarding from `cmd_detail`. The intended rejected behavior is argparse’s normal unknown-option error before context loading, run-log creation, or detail generation—not another authoring-layer rejection.

- **Keep normal CLI orchestration unchanged.** `plan_tool/cli/authoring.py:cmd_detail` must still invoke the run-grade generator, retain its completeness-tail behavior, and emit the same run-grade follow-up paths. Remove grade-specific conditionals where the only remaining possibility is the run-grade path rather than preserving unnecessary selector plumbing.

- **Avoid widening into reader retirement.** Existing Jira-grade detail reading, export, audit, run, or diagnostic selectors are outside this step’s declared files and must remain untouched. Do not change the run-grade detail contract, Jira story rendering, or developer-handoff output.

Run-grade invocation passes prompt text directly to `claude_invoke`; no temporary-input lifecycle is part of this route. This corrects the detail claim to the existing implementation.

## Tests

### Tests for this step

- `tests/test_detail.py::test_orphan_sweep_archives_only_stale_same_step_files` — Unit coverage that archives stale same-step siblings while preserving canonical and other-step files.

- `tests/test_detail.py::test_generate_detail_replaces_existing_run_grade_detail_and_preserves_archive` — Assert forced run-grade replacement writes the canonical detail, keeps the plan pointer on that file, and archives the prior run-grade content.
- `tests/test_detail.py::test_generate_detail_archives_run_grade_orphans_without_moving_the_canonical_output` — Assert stale same-step run-grade siblings move to `archive/` while the newly written canonical detail remains in place.
- `tests/test_detail.py::test_generate_detail_preserves_run_grade_split_migration_and_rollback_renames` — Assert the existing split and rollback recovery path still restores or migrates run-grade detail artifacts correctly.
- `tests/test_detail.py::test_jira_grade_authoring_symbols_are_not_exposed` — Assert retired Jira prompt/writer entry points are no longer imported or exercised by the detail authoring module.
- `tests/cli/test_authoring_cmds.py::TestDetailSelectorRemoval::test_detail_rejects_removed_grade_selector` — Class-marked integration test that `plan-tool detail … --grade jira` exits with argparse’s usage error before invoking authoring.
- `tests/cli/test_authoring_cmds.py::TestDetailSelectorRemoval::test_detail_without_grade_keeps_run_grade_generator_contract` — Class-marked integration test that ordinary `detail` still reaches the run-grade generation and completeness-tail route.

Every listed test must be green before this step is finished.

## Acceptance criteria

- `plan_tool/cli/authoring.py:register` defines no `--grade` option for `detail`.
- `plan-tool detail <plan> --grade jira` is rejected by argparse with exit code 2, before context loading, run-log creation, or `generate_detail` invocation.
- `plan_tool/detail.py` exposes no Jira-grade detail authoring prompt renderer, direct Jira writer, or grade selector for its authoring flow.
- `plan_tool/prompts/detail-jira.md` is absent.
- Ordinary `plan-tool detail <plan>` continues to author run-grade detail and run its existing completion flow.
- Forced run-grade replacement, split migration and rollback renames, orphan archiving, and durable saved-output behavior remain covered and green.
- The focused unit tests in `tests/test_detail.py` and class-marked integration tests in `tests/cli/test_authoring_cmds.py` pass.

## References

- [argparse — Parser for command-line options, arguments and subcommands](https://docs.python.org/3.13/library/argparse.html) — Use its normal unknown-option behavior as the rejected-selector contract.

## Applicable guardrails

- **The plan’s “## Step intent.”** Expose only the supported implementation-detail authoring route; do not retain a second authoring mode behind a rejection or compatibility layer.
- **The plan’s “## Scope guardrails.”** Remove the legacy lane without adding a replacement grade, artifact migration, output redesign, or compact-schema baseline.
- **The plan’s “## Out of scope.”** Preserve the run-grade authoring and Jira export/developer-handoff contracts; do not alter Jira story or handoff rendering.
- **Step 1 dependency.** Use the ownership boundary established by step 1 so deleting authoring code does not remove a dependency that a surviving reader still needs.

## Deferred

- Jira-grade detail readers and their export, audit, run, and diagnostic selectors — These consumer surfaces are outside this step’s declared files and require their own retirement work.
- Jira-grade schema and historical evidence handling — This step removes authoring only; it does not rewrite archived artifacts or change remaining reader contracts.
