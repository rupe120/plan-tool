> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 6 — Add an opt-in Jira companion CLI mode with explicit output behavior

> **Historical delivery evidence — superseded 2026-08-23.** This detail records
> the completed opt-in companion design. The unified paired-export contract in
> `JIRA_FORMAT.md` replaces its story-only compatibility claims.

## Summary

Add `--developer-handoff` and `--handoff-output` to `plan_tool/cli/jira_cmd.py:register`, then route the opt-in mode through the companion-export contract completed by step 5. Keep `--format` and `--output` as story-source selectors, derive the companion destination from the resolved story destination, and make mode-specific output deterministic. Preserve the existing story-only, lint, config, and direct-jira workflows when the new mode is absent. On green, operators can request both generated sources safely, see clear destinations and Jira-update notices, and rely on documented flag precedence.

## Table of Contents

- [Summary](#summary) — Reviewer-level outcome and affected surfaces.
- [Table of Contents](#table-of-contents) — Links to each section in this detail.
- [Why](#why) — Why the companion needs a distinct CLI boundary.
- [Input](#input) — Existing Jira command and completed companion-export contracts.
- [Files (creates vs edits)](#files-creates-vs-edits) — Exact CLI, test, and reference-doc footprint.
- [Implementation](#implementation) — Mode validation, path derivation, output rules, and compatibility boundaries.
- [Tests](#tests) — Focused parser, command, and direct-pipeline coverage.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Primary references for parser, paths, and fixtures.
- [Applicable guardrails](#applicable-guardrails) — Plan boundaries that constrain this command surface.
- [Deferred](#deferred) — Work intentionally left outside this CLI step.

## Why

`plan_tool/cli/jira_cmd.py:cmd_jira` currently turns one story-export result into one of several story-only output paths, while `plan_tool/cli/direct_cmd.py:cmd_direct_jira` builds a hand-written namespace for that handler. Step 5 adds a paired generated-source result, but without an explicit mode the CLI could accidentally change existing exports, mutate Jira configuration during a dry run, or print ambiguous output for two artifacts.

## Input

- **Companion export contract:** Step 5 provides the opt-in companion-export path beside `plan_tool/jira.py:export_jira`, including pre-render target validation, paired publication, shared fingerprint provenance, and created-ticket update or created-to-dropped lifecycle metadata. Keep those domain rules in that layer; this step selects the mode, supplies resolved destinations, and presents its result.

- **Existing command flow:** `plan_tool/cli/jira_cmd.py:cmd_jira` dispatches `jira config`, resolves epic and tag assignment, calls `plan_tool/jira.py:export_jira`, and formats the current story-only result. Preserve those branches when companion mode is off.

- **Existing output types:** `plan_tool/jira.py:JiraResult` supplies `output`, `written_path`, story records, and current Jira follow-up fields. Use step 5’s companion additions as returned; do not recompute provenance, target ownership, or ticket-change status in the CLI.

- **Direct pipeline:** `plan_tool/cli/direct_cmd.py:cmd_direct_jira` constructs the Jira-stage namespace itself. New CLI attributes need compatibility defaults there and in `plan_tool/cli/jira_cmd.py:cmd_jira` so an older hand-built namespace remains story-only.

- **Command reference:** `docs/cli/jira.md:Usage` and its `## Options` table describe the parser surface. Step 7 owns the broader companion format and lifecycle documentation.

## Files (creates vs edits)

- **New files:** None.

- **Existing files (edits only):**
  - `plan_tool/cli/jira_cmd.py` — Register the opt-in flags, validate incompatible modes before side effects, derive resolved destinations, call the completed companion-export path, and render companion-specific output.
  - `tests/cli/test_jira_cmds.py` — Add command-level coverage for path derivation, rejected combinations, read-only dry runs, output precedence, and created-ticket notices.
  - `tests/cli/test_direct_cmd.py` — Pin the hand-built direct-jira namespace to companion mode off with no handoff destination.
  - `tests/test_jira.py` — Keep the domain-result fixtures and story-only `plan_tool/jira.py:export_jira` regressions explicit as the CLI begins consuming the paired companion result.
  - `docs/cli/jira.md` — Update usage and option descriptions for the companion flags, destinations, rejected combinations, and output precedence without duplicating step 7’s format guidance.
  - `tests/cli/package_surface_help.golden.txt` — Rebaseline only if `plan-tool --help` changes. The new `jira` options should not alter this top-level snapshot because the registered subcommand name remains `jira`.

## Implementation

- **Foundational logic — choose companion mode before configuration or export side effects.** In `plan_tool/cli/jira_cmd.py:cmd_jira`, decide whether the invocation requests a developer handoff before `cmd_jira_config`, lint handling, assignment helpers, or `plan_tool/jira.py:export_jira` run.

- **Add a narrow opt-in parser surface.** Extend `plan_tool/cli/jira_cmd.py:register` with `--developer-handoff` and `--handoff-output PATH`. Keep both false or unset by default. `--format` and `--output` continue to select the story artifact; `--handoff-output` selects only the Markdown companion.

- **Reject invalid combinations before effects.** Reject `--handoff-output` without `--developer-handoff`, and reject companion mode with `jira config` or `--lint`, before configuration resolution, model invocation, or output writes. Keep the existing `jira config` and lint behavior unchanged when companion mode is absent.

- **Derive the companion path from the resolved story path.** Resolve the explicit `--output` path before use; otherwise start with `plan_tool/jira.py:derive_jira_output_path`. For the default companion location, use `plan_tool/jira.py:plan_slug_from_path` and derive `<plan-dir>/jira-handoffs/<plan-slug>/<normalized-story-stem>.developer-handoff.md`. Remove exactly one final suffix from the resolved story basename, retaining all preceding suffixes and leaving a suffix-free basename unchanged. Resolve an explicit `--handoff-output` path by the same path-normalization rule.

- **Pass both resolved paths to the domain boundary.** The companion call into `plan_tool/jira.py:export_jira` must receive the resolved story and handoff destinations plus the opt-in request. Step 5’s domain path remains the single owner of the complete two-destination-plus-format pair identity, pre-render generated-target ownership and all-grade detail collision checks, and final replacement checks; do not recreate those checks in `plan_tool/cli/jira_cmd.py`.

- **Keep dry-run read-only.** In companion mode, `--dry-run` validates inputs and prints the domain-provided generation material with both planned destinations, but does not invoke a model, publish either output, create an epic assignment, or persist a plan tag. Resolve an existing assignment or validate explicit `--epic` and `--jira-tag` values without using `plan_tool/cli/jira_cmd.py:_assign_epic_for_plan` or `plan_tool/cli/jira_cmd.py:_assign_plan_tag_for_plan`.

- **Make output precedence explicit.** Apply the companion-only order `--dry-run` first, `--no-write` second, then `--stdout`.
  - `--dry-run` prints the labeled dry-run material and both destinations only.
  - `--no-write` invokes companion generation but publishes nothing; it prints both labeled generated artifacts whether or not `--stdout` is also present.
  - A successful write prints a concise summary naming both destinations; `--stdout` additionally prints both labeled generated artifacts.
  - Keep the current story-only `--dry-run`, `--no-write`, and `--stdout` branches unchanged.

- **Report ticket changes without claiming a Jira update.** Extend `plan_tool/cli/jira_cmd.py:_print_jira_followups` or add a companion-only adjacent reporter that names each changed regenerated story id and its Jira key from step 5’s result. It must also name each keyed created-to-dropped story id and Jira key and say the operator must cancel, close, or repurpose that live ticket. Never imply that plan-tool posted, synchronized, or changed Jira itself.

- **Preserve hand-built namespace compatibility.** Read new attributes through `getattr` defaults in `plan_tool/cli/jira_cmd.py:cmd_jira`, matching its existing grade compatibility rule. Also set explicit false/empty companion values in the Jira-stage namespace assembled by `plan_tool/cli/direct_cmd.py:cmd_direct_jira`; direct-jira stays on the story-only path unless a later plan deliberately adds a companion surface.

- **Keep documentation parser-focused.** Update `docs/cli/jira.md:Usage` and `docs/cli/jira.md:Options` from the landed parser behavior, including path derivation and output precedence. Leave the generated handoff’s format, provenance layout, and broader lifecycle explanation to step 7.

## Tests

### Tests for this step

- `tests/cli/test_jira_cmds.py:test_developer_handoff_derives_normalized_path_from_default_json_and_explicit_story_outputs` — Markdown, JSON, multi-suffix, and suffix-free story destinations produce the required resolved handoff path.

- `tests/cli/test_jira_cmds.py:test_handoff_output_without_developer_handoff_rejects_before_config_or_export` — The command exits with an error and reaches neither configuration resolution nor the exporter.

- `tests/cli/test_jira_cmds.py:test_developer_handoff_rejects_lint_and_config_modes_without_side_effects` — Companion mode combined with lint or `jira config` exits before publication or configuration mutation.

- `tests/cli/test_jira_cmds.py:test_developer_handoff_dry_run_is_read_only_and_precedes_no_write_and_stdout` — Dry run validates and prints its labeled material and both destinations, without invoking, writing, or persisting an epic or tag assignment.

- `tests/cli/test_jira_cmds.py:test_developer_handoff_no_write_prints_both_artifacts_even_with_stdout` — No-write invokes the companion path, publishes neither artifact, and wins over stdout.

- `tests/cli/test_jira_cmds.py:test_developer_handoff_stdout_prints_both_artifacts_after_successful_write` — A successful write prints a two-destination summary and stdout adds both labeled artifacts.

- `tests/cli/test_jira_cmds.py:test_developer_handoff_reports_changed_story_id_and_jira_key` — Each created-ticket update notice identifies both the regenerated story and the live Jira key without claiming an external update occurred.

- `tests/cli/test_jira_cmds.py:test_developer_handoff_reports_created_to_dropped_story_and_jira_key` — A keyed created story that leaves committed coverage produces a distinct manual cancel/close/repurpose notice without claiming an external action.

- `tests/cli/test_jira_cmds.py:test_story_only_jira_output_and_config_flow_remain_unchanged_without_companion_mode` — Existing story-only output and assignment behavior stay on their current branch.

- `tests/cli/test_direct_cmd.py:test_direct_jira_pins_companion_mode_off_and_handoff_output_empty` — The hand-built direct-jira stage namespace carries explicit safe defaults and cannot select companion behavior accidentally.

- `tests/test_jira.py:test_story_only_export_result_remains_unchanged_when_companion_is_not_requested` — The default domain export continues to expose its current story-only output and write behavior.

Every listed case must be green before this step is complete.

## Acceptance criteria

- `plan-tool jira <name> --developer-handoff` requests paired companion export, while the command without that flag retains story-only behavior.

- The default companion destination uses the resolved story destination, removes exactly one final suffix from its basename, and sits under `jira-handoffs/<plan-slug>/`.

- `--handoff-output` without companion mode, and companion mode with lint or config, fail before configuration mutation, backend invocation, or output publication.

- Companion dry-run is read-only and takes precedence over no-write and stdout; no-write takes precedence over stdout.

- Companion no-write and stdout output label both generated artifacts; successful writes name both destinations, report every changed created ticket by story id and Jira key, and report every keyed created-to-dropped lifecycle transition for manual Jira action.

- `direct-jira` explicitly remains story-only, and `plan_tool/cli/jira_cmd.py:cmd_jira` tolerates hand-built namespaces without the new attributes.

- `docs/cli/jira.md` matches the landed flags and output rules, and `tests/cli/package_surface_help.golden.txt` remains valid.

## References

- [argparse — Parser for command-line options, arguments and subcommandshttps: — Use for optional flags, defaults, and parser help text.

- [pathlib — Object-oriented filesystem pathshttps: — Use for resolved destination comparison and final-suffix handling.

- [How to use temporary directories and files in testshttps: — Use isolated plan, configuration, and output fixtures for command tests.

## Applicable guardrails

- **The plan’s “## Plan intent”, one captured source state:** Route companion requests into step 5’s paired result without rereading inputs or recomputing its provenance in the CLI.

- **The plan’s step 6 intent, explicit output behavior:** Make path selection, flag precedence, source-pair handoff, and created-ticket notices visible to the operator.

- **The plan’s “## Out of scope”, authority boundary:** Do not change detail-grade defaults, mutate plans, post to Jira, or add source-conflict classification.

- **The plan’s “## Risks”, compatibility and failure boundary:** Preserve story-only behavior and present partial-publication or ticket-update facts honestly through the domain result.

## Deferred

- A companion-selection surface for `plan_tool/cli/direct_cmd.py:cmd_direct_jira` — direct-jira remains story-only in this step; adding an unattended companion workflow needs separate scope.

- Expanded companion format, provenance, and safe-regeneration documentation — Step 7 owns the broader user-facing documentation.

- Jira-native attachment, posting, or synchronization — remains outside the generated local-source workflow.
