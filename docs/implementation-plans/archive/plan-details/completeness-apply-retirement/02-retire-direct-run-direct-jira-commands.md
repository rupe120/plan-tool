> **Auto-archived**: this plan was swept on 2026-11-05 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 2 — Retire the direct pipeline commands

<!-- plan-tool:detail-format-version: 1 -->

## Summary

Delete `plan_tool/cli/direct_cmd.py` and remove `direct-run` and `direct-jira` from command registration, dispatch, mutation locking, and capability coverage. Delete their generated reference pages and command-specific tests, then refresh the reference index and help snapshot. Retire the direct pipelines’ commit and relocated-root guard logic with the module rather than moving it elsewhere. The standalone authoring, export, execution, and code-reconciliation commands keep their existing behavior.

## Table of Contents

- [Summary](#summary) — Result and main boundaries.
- [Table of Contents](#table-of-contents) — Section index.
- [Why](#why) — Why the direct pipelines retire outright.
- [Input](#input) — Command registration and generated-reference contracts.
- [Files (creates vs edits)](#files-creates-vs-edits) — Deletions, edits, and verification-only files.
- [Implementation](#implementation) — Removal approach and surviving behavior.
- [Tests](#tests) — Removal checks and regression coverage.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Relevant decisions and code contracts.
- [Applicable guardrails](#applicable-guardrails) — Boundaries imposed by the plan.
- [Deferred](#deferred) — Work owned outside this step.

## Why

`plan_tool/cli/direct_cmd.py:cmd_direct_jira()` and `plan_tool/cli/direct_cmd.py:cmd_direct_run()` chain conceptual application between detail authoring and their final export or execution stages. Their unattended application stage is the behavior the plan retires, so keeping the commands would require inventing a different pipeline contract. Delete the commands outright and preserve the standalone commands developers already use to drive those stages with their own judgment. The `CAPABILITIES.md` “Direct pipeline” entry still advertises both commands and their module; the heuristic hit confirms an existing removal target, not completed retirement.

## Input

- **Command registry:** `plan_tool/cli/app.py:COMMAND_MODULES` supplies modules to `plan_tool/cli/parser.py:assemble()`. Removing the direct module must remove both parser registrations and dispatch entries.
- **Mutation locking:** `plan_tool/cli/app.py:_LOCKED_MUTATING_COMMANDS` names commands covered by the shared lock policy. Remove only the retiring command names.
- **Capability coverage:** `plan_tool/capability_catalog.py:check_capabilities()` checks registered commands and module paths against `CAPABILITIES.md`. Remove the direct capability alongside its surfaces.
- **Generated references:** `plan_tool/cli_reference.py:render_reference()` derives pages from the parser. `plan_tool/cli_reference.py:write_reference()` writes generated files but does not delete obsolete pages.

## Files (creates vs edits)

- **New files:** None.
- **Existing files (edits only):**
  - `plan_tool/cli/direct_cmd.py` — delete the module and all exclusive pipeline machinery.
  - `plan_tool/cli/app.py` — remove direct-module imports, handler re-exports, registry membership, and lock-set entries.
  - `plan_tool/cli/parser.py` — remove both names from `CANONICAL_COMMAND_ORDER`.
  - `CAPABILITIES.md` — remove the “Direct pipeline” capability.
  - `docs/cli/direct-jira.md` — delete the retired command reference.
  - `docs/cli/direct-run.md` — delete the retired command reference.
  - `docs/cli/README.md` — regenerate the command index.
  - `tests/cli/package_surface_help.golden.txt` — refresh the public help snapshot.
  - `tests/cli/test_direct_cmd.py` — delete tests belonging exclusively to the removed module.
  - `tests/cli/test_cli_reference.py` — replace direct-command presence expectations with absence checks.
  - `tests/cli/test_cli_parser.py` — add focused rejection and surviving-registration checks.
  - `tests/test_cli.py` — remove the stale `direct_cmd._is_code_step` comparison from the surviving reconcile test’s docstring; retain its behavior assertions.
- **Declared files to verify without a required edit:**
  - `plan_tool/cli/jira_cmd.py` — preserve `cmd_jira()` and its write paths.
  - `plan_tool/cli/run_cmd.py` — preserve `cmd_run()`, `_cmd_run_sweep()`, and `cmd_reconcile_code()`.
  - `tests/cli/test_run_cmd.py` — retain execution, commit, and guard coverage; edit only if an actual retired-command dependency appears.

## Implementation

- **Foundational logic: remove direct-command reachability.** Delete `plan_tool/cli/direct_cmd.py`, including `register()`, `cmd_direct_jira()`, and `cmd_direct_run()`. Do not replace them with aliases, error-only handlers, or a private pipeline.

- **Remove every registration layer together.** In `plan_tool/cli/app.py`, remove `_direct_commands`, the imported direct handlers, their `COMMAND_MODULES` entry, and their `_LOCKED_MUTATING_COMMANDS` entries. Remove the corresponding names from `plan_tool/cli/parser.py:CANONICAL_COMMAND_ORDER`. Surviving commands must retain their handlers, ordering, and lock behavior.

- **Retire exclusive helpers with their owner.** Delete the size gate, stage-namespace construction, root derivation, relocation checks, and mid-chain commits with `plan_tool/cli/direct_cmd.py`. This includes `gate_create_result_size()`, `_resolve_created_repo_root()`, `_guard_relocated_root_clean()`, and the authoring/applied-gap commit branches. Moving these into surviving commands would broaden the removal into a workflow change.

- **Reuse shared owners unchanged.** `plan_tool/cli/gitcommit.py:commit_all()`, `working_tree_dirty()`, and `unexpected_dirty_paths()` have surviving consumers. In particular, `plan_tool/cli/authoring.py` uses the shared commit helper, and `plan_tool/cli/run_cmd.py` uses shared dirt checks. Removing a caller must not remove or weaken these helpers.

- **Preserve standalone writes.** Keep `plan_tool/cli/jira_cmd.py:cmd_jira()` and `plan_tool/cli/run_cmd.py:cmd_run()`, `_cmd_run_sweep()`, and `cmd_reconcile_code()` behavior unchanged. Do not transfer the deleted pipelines’ commit policy, root guard, forced flags, or stage sequencing into them. Create and detail retain their existing owners outside this step’s edits.

- **Remove live catalog entries.** Delete the “Direct pipeline” section from `CAPABILITIES.md` in the same change as command removal. Do not repurpose its capability ID for a replacement route.

- **Regenerate references and delete obsolete output explicitly.** Run `python -m plan_tool.cli_reference --write` after changing registration, then delete `docs/cli/direct-jira.md` and `docs/cli/direct-run.md`. Refresh `tests/cli/package_surface_help.golden.txt` using the existing `UPDATE_CLI_GOLDEN=1` mechanism in `tests/cli/test_package_surface.py`.

- **Keep surviving tests independent of deleted code.** Delete `tests/cli/test_direct_cmd.py`; its size, relocation, commit, and propagation cases describe a removed contract. In `tests/test_cli.py:test_sweep_skips_explicit_non_code_steps()`, remove the comparison to the deleted helper while retaining the assertion that standalone code reconciliation skips explicit non-code steps.

## Tests

Use hermetic tests and existing backend stubs. Every added or changed test and the affected regression suites must be green before this step finishes.

### Tests for this step

- `tests/cli/test_cli_parser.py:test_retired_direct_commands_are_rejected` — parameterize both command names and assert argparse rejects each with `SystemExit(2)`.
- `tests/cli/test_cli_parser.py:test_standalone_pipeline_commands_remain_registered` — assert create, detail, jira, run, and reconcile-code remain registered after removing the direct module.
- `tests/cli/test_cli_reference.py:test_retired_direct_verbs_have_no_generated_reference` — replace `test_direct_verbs_reference_is_generated`; assert neither page key nor index link is generated.
- `tests/cli/test_cli_reference.py:TestCliReferenceDrift.test_every_generated_file_matches_disk` — verify regenerated files match the live parser.
- `tests/cli/test_cli_reference.py:TestCliReferenceDrift.test_no_orphan_reference_files` — verify both retired pages are deleted from disk.
- `tests/test_cli.py:test_sweep_skips_explicit_non_code_steps` — preserve the standalone reconcile skip behavior while removing its stale helper citation.
- `tests/test_cli.py:test_commit_makes_one_commit_per_green_step` — retain the standalone run commit contract.
- `tests/test_cli.py:test_all_without_commit_makes_no_commits` — retain standalone execution without implicit commits.
- `tests/test_cli.py:test_single_step_commit_requires_clean_tree` — retain the standalone run dirt guard.

Run the affected parser, reference, package-surface, execution, and CLI suites, then the full pytest suite. Review the complete diff for surviving caller changes and unintended generated-reference churn.

## Acceptance criteria

- `plan_tool/cli/direct_cmd.py` and `tests/cli/test_direct_cmd.py` do not exist.
- Parsing either retired command raises `SystemExit(2)` before command execution.
- `plan_tool/cli/app.py` contains no direct-module imports, direct-handler re-exports, registry membership, or direct-command lock entries.
- `plan_tool/cli/parser.py:CANONICAL_COMMAND_ORDER` contains neither command name.
- `CAPABILITIES.md` contains no `direct-pipeline` capability or references to its removed surfaces.
- Neither retired reference page exists or appears in generated output; the reference drift and orphan checks pass.
- The help snapshot matches the live parser and lists neither retired command.
- Standalone command registration, execution commits, dirt guards, and reconcile skip tests pass.
- Shared commit and dirt helpers retain their existing implementation; standalone write paths gain no replacement pipeline behavior.
- The affected suites and full pytest suite pass.

## References

- [BACKLOG.md](BACKLOG.md) — Read item #376 for the retire-outright decision and item #369 for separately scoped application callers.
- [plan_tool/cli/direct_cmd.py](plan_tool/cli/direct_cmd.py) — Inspect the retiring handlers and their exclusive sequencing before deletion.
- [plan_tool/capability_catalog.py](plan_tool/capability_catalog.py) — Read `check_capabilities()` for command and module coverage requirements.
- [plan_tool/cli_reference.py](plan_tool/cli_reference.py) — Read `render_reference()` and `write_reference()` for generated output ownership.
- [tests/cli/test_package_surface.py](tests/cli/test_package_surface.py) — Use the existing help snapshot and parser-to-dispatch checks.

## Applicable guardrails

- **Plan intent, conceptual-command retirement:** Remove the direct entry points completely; do not preserve their conceptual application through another callable pipeline.
- **Plan “Scope guardrails,” exclusive machinery:** Confine helper deletion to the direct module. Shared git helpers and surviving command owners retain their contracts.
- **Plan “Out of scope,” surviving application routes:** Leave other application callers, review/reconcile behavior, and deterministic repairs unchanged.
- **Plan “Scope guardrails,” legacy readability:** Delete command availability and live reference entries without changing saved-report or run-log readers.

## Deferred

- `plan_tool/cli/completeness_cmd.py:cmd_completeness_apply()` — Removal belongs to the plan’s dedicated application-command retirement work; this step removes its direct-pipeline callers.
- `plan_tool/cli/__init__.py` command catalog and broader narrative guidance — Keep the plan’s documentation sweep responsible for text outside this step’s declared files.
- Other `apply_finding` callers — BACKLOG.md item #369 owns their separate inventory; this removal provides no basis for changing them.
- Historical reports, run logs, and implementation-plan artifacts — Preserve their contents and readers under the plan’s legacy-artifact boundary.
