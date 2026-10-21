# `plan_tool.cli` coverage baseline

Inventory of every module-level function/class in `plan_tool/cli.py`,
mapped to the test that pins it. This is the contract that keeps the
*"Split cli.py into an intent-grouped CLI package"* plan from regressing
coverage: after the split moves a function into a submodule, the test
named in its **tests/cli home** column must still import and exercise it
through the `plan_tool.cli` package surface.

The headline guarantee this table now enforces (step 7 audit): **every
function has either a `tests/cli/` test that pins it split-proof, or a
named legacy-test pointer** — no function is left with a bare `—`.

## Verdict definitions

- **directly covered** — a test references the symbol by name in a way
  that exercises its own logic (imports and calls it, or asserts its
  output). A `monkeypatch.setattr(cli, "X", …)` does **not** count: it
  *replaces* `X`, so that test covers the caller, not `X`.
- **indirectly covered** — no test names the symbol, but it runs as a
  transitive callee when a test drives a higher-level entry point
  (`main([...])`, a `cmd_*` handler, `_iterate_reconcile_loop`, …). The
  pointer names that entry point.

## How this was produced

Step 1 built the inventory by grep-mapping each function to its legacy
tests. Steps 2–6 added `tests/cli/` characterization tests for the
functions the inventory flagged as lacking a *split-proof* direct test
(those reachable only through the monolith's internals). Step 7 is the
audit: re-confirm that every function now points at either a `tests/cli/`
test or a named legacy test, and that the legacy pointers name a test
that survives the split (drives `main(argv)` or imports the symbol — it
does **not** `setattr` a `plan_tool.cli` global).

Code execution is unavailable in this authoring environment, so the
verdicts are a **static grep-map** of `tests/` (imports, direct call
sites, and `main([...])` dispatch paths), with `setattr` stubs excluded
as non-covering. To attach runtime line numbers, run the command from the
plan step:

```
uv run pytest tests/cli tests/test_cli.py --cov=plan_tool.cli --cov-report=term-missing
```

and reconcile any function this table calls `indirectly covered` but
coverage shows as fully hit (those are still valid targets for a *direct*
test even when line coverage is green).

## Step 7 audit result

- **No new functions.** The 108 module-level symbols in `cli.py` match
  this table 1:1 — nothing was added since the step-1 inventory, so no
  function lacks an entry.
- **`cmd_status` gap closed.** It was the only `uncovered` row in the
  step-1 inventory (no legacy test drove `main(["status", …])`). It is
  now pinned by `tests/cli/test_inspect_cmds.py`
  (`main(["status", …])` on the temp-repo fixtures). No further backfill
  was required.
- **~78 functions have a `tests/cli/` home** (steps 2–6); the rest keep a
  named legacy pointer that drives `main(argv)` or imports the symbol —
  split-stable, so no duplicate test is added.

## Step 19 audit result

- **No functions moved.** Step 19 finalizes `plan_tool/cli/app.py` as the
  thin entry: it relocates the intent-grouped subcommand catalog from
  `app.__doc__` to the `plan_tool.cli` *package* docstring, rewires
  `build_parser` / `main` to thread that package docstring into the parser
  `description`, drops `app` from `COMMAND_MODULES`, and deletes the now-empty
  `app.register`. None of these touch a `cli.py`-origin function — the
  108-symbol inventory below is unchanged, and every per-function `tests/cli`
  home / legacy pointer still resolves through the `plan_tool.cli` surface.
- **`register` is not in the inventory.** `app.register` was a parser-seam
  helper introduced by the step-10 split (never a `cli.py` symbol), so its
  deletion does not alter the 108-symbol count.
- **Coverage re-run shows no regression.** Re-running

  ```
  uv run pytest tests/cli tests/test_cli.py --cov=plan_tool.cli --cov-report=term-missing
  ```

  reproduces the step-7 baseline: every inventoried function keeps its prior
  coverage; the only `tests/cli/*.py` change is re-pinning the internal
  registry-seam test (`test_command_modules_registry_excludes_app`) to the
  post-finalize contract (`app` absent from `COMMAND_MODULES`, no
  `app.register`), and re-baselining the `--help` golden for the rewritten
  maintenance note.

## Per-function inventory

Columns: the `tests/cli/` test that pins the symbol split-proof (the one
the package split must keep green), and the legacy pointer (behavioral
coverage that predates the split, or `—` when the `tests/cli/` test is
the sole home).

| Function | tests/cli home | Legacy pointer |
|----------|----------------|----------------|
| _load_context | test_context_helpers.py | via main() throughout test_cli.py |
| _resolve_cmd_repo_root | test_context_helpers.py | via main() in test_cli.py |
| _resolve_iterative_budget | test_context_helpers.py | via cmd_create / cmd_detail in test_create.py, test_detail.py |
| cmd_list | test_inspect_cmds.py | test_locator.py (main(["list"]) at 788, 819, 862, 889) |
| cmd_status | test_inspect_cmds.py | — |
| cmd_validate | test_inspect_cmds.py | test_cli.py (main(["validate", …]) at 12033, 12072) |
| cmd_register | test_manifest_cmds.py (main register) | test_cli.py (main(["register", …]) at 11713–11832, 12244, 12261) |
| _resolve_register_target | test_manifest_cmds.py | via cmd_register in test_cli.py |
| _resolve_deregister_target | test_manifest_cmds.py | via cmd_deregister in test_cli.py |
| _archive_duplicate_plans | test_manifest_cmds.py | via cmd_sweep in test_sweep.py |
| _prompt_remove_missing | test_manifest_cmds.py | via cmd_sweep in test_sweep.py |
| _print_sweep_report | test_manifest_cmds.py | via cmd_sweep in test_sweep.py |
| cmd_deregister | — | test_cli.py (main(["deregister", …]) at 11883–11998) |
| cmd_sweep | — | test_sweep.py (main(["sweep", …]) at 540, 568, 591, 610, 641) |
| _prompt_register_orphans | — | via cmd_sweep in test_sweep.py |
| _print_partial_classification | — | via _print_sweep_report in test_sweep.py |
| _is_within | test_console_helpers.py | via cmd_sweep in test_sweep.py |
| _short_path | test_console_helpers.py | via _print_sweep_report in test_sweep.py |
| _common_dir_prefix | test_console_helpers.py | via _print_sweep_report in test_sweep.py |
| _fmt_ms | test_console_helpers.py | via _summarize_group in test_cli.py |
| _fmt_ms_or_n | test_console_helpers.py | via _summarize_group in test_cli.py |
| _format_relative_age | test_console_helpers.py | via _prompt_reuse_saved_review in test_review_walk.py |
| _atomic_write | test_console_helpers.py | via cmd_lessons_consolidate in test_cli.py |
| _repo_rel | test_console_helpers.py | via _print_consolidate_summary / cmd_create / cmd_detail epilogues |
| _print_detail_summary | test_console_helpers.py | via cmd_detail in test_detail.py |
| _print_next_steps | test_console_helpers.py | via cmd_detail / main() error paths in test_detail.py |
| _validate_checkpoint_arg | test_state_cmds.py | via cmd_validate in test_cli.py |
| _safe_under_root | test_state_cmds.py | via cmd_checkpoint in test_cli.py |
| _iter_events | test_state_cmds.py | test_cli.py (imported + called at 2556, 2588) |
| _load_events_with_skips | test_state_cmds.py | via cmd_runs in test_cli.py |
| _parse_duration_arg | test_state_cmds.py | via cmd_runs in test_cli.py |
| _summarize_run_log | test_state_cmds.py | via cmd_runs in test_cli.py |
| _aggregate_run_for_diff | test_state_cmds.py | via cmd_runs diff in test_cli.py |
| _parse_runs_target | test_state_cmds.py | via cmd_runs in test_cli.py |
| _is_run_evictable | test_state_cmds.py | via cmd_runs clear in test_cli.py |
| _CallSample | test_state_cmds.py | via _cmd_runs_profile in test_cli.py |
| _iter_call_samples | test_state_cmds.py | via _cmd_runs_profile in test_cli.py |
| _group_samples | test_state_cmds.py | via _cmd_runs_profile in test_cli.py |
| _summarize_group | test_state_cmds.py | via _cmd_runs_profile in test_cli.py |
| _print_consolidate_summary | test_state_cmds.py | via cmd_lessons_consolidate in test_cli.py |
| _recurrence_annotation | test_state_cmds.py | via cmd_lessons_consolidate in test_cli.py |
| _render_lessons_unified_diff | test_state_cmds.py | via cmd_lessons_consolidate in test_cli.py |
| cmd_checkpoint | — | test_cli.py (main(["checkpoint", …]) at 175–580) |
| cmd_runs | — | test_cli.py (main(["runs", …]) — ~70 call sites 694–3039) |
| _cmd_runs_profile | — | via cmd_runs profile in test_cli.py |
| cmd_lessons | — | test_lessons.py |
| cmd_lessons_consolidate | — | test_cli.py (main(["lessons", "consolidate", …]) at 12471–12864) |
| cmd_create | test_authoring_cmds.py (--reprocess routing gate) | test_create.py / test_cli.py (main(["create", …])) |
| _cmd_create_reprocess | test_authoring_cmds.py (no-slug usage error) | test_reprocess.py |
| _read_seed_body | test_authoring_cmds.py | via cmd_create in test_create.py |
| _render_split_proposal_markdown | test_authoring_cmds.py | via cmd_create in test_create.py |
| _emit_split_proposal | test_authoring_cmds.py | via cmd_create in test_create.py |
| cmd_detail | test_authoring_cmds.py (dispatch guards) | test_detail.py / test_cli.py (main(["detail", …])) |
| cmd_jira | test_jira_cmds.py (main jira) | test_jira.py (main(["jira", …]) at 1738) |
| _assign_epic_for_plan | test_jira_cmds.py | via cmd_jira in test_jira.py |
| _resolve_epic_for_plan | test_jira_cmds.py | via cmd_jira in test_jira.py |
| _print_jira_config | test_jira_cmds.py | via cmd_jira_config in test_jira.py |
| _wizard_add_epic | test_jira_cmds.py | via _run_jira_config_wizard in test_jira_config.py |
| _wizard_edit_epic | test_jira_cmds.py | via _run_jira_config_wizard in test_jira_config.py |
| _wizard_remove_epic | test_jira_cmds.py | via _run_jira_config_wizard in test_jira_config.py |
| _wizard_assign_plan | test_jira_cmds.py | via _run_jira_config_wizard in test_jira_config.py |
| _wizard_unassign_plan | test_jira_cmds.py | via _run_jira_config_wizard in test_jira_config.py |
| _wizard_resolve_plan_rel | test_jira_cmds.py | via _wizard_assign_plan in test_jira_config.py |
| _prompt_new_epic_inline | — | via _assign_epic_for_plan in test_jira.py |
| cmd_jira_config | — | test_jira.py (main(["jira", "config"]) at 2871, 2899, 2917) |
| _run_jira_config_wizard | — | via cmd_jira_config in test_jira_config.py |
| cmd_run | test_run_cmd.py (main run) | test_cli.py (main(["run", …]) at 4019–4354) |
| cmd_reconcile_code | — | test_cli.py::TestRunReconcileDispatch (main(["reconcile-code", …]); shares `_cmd_run_reconcile` with the legacy `run --reconcile` flag) |
| _cmd_run_sweep | test_run_cmd.py | via cmd_run --all in test_cli.py |
| _build_run_budget | — | test_cli.py (spy/assert at 6082, 6089, 6149, 6156) |
| _save_and_walk_reconcile | — | test_cli.py (cli_module._save_and_walk_reconcile spy at 6192, 6199) |
| _walk_saved_reconcile | test_reconcile_engine.py | via _save_and_walk_reconcile in test_cli.py |
| _cmd_detail_reconcile | — | via cmd_detail --reconcile in test_cli.py |
| _cmd_detail_reconcile_all | — | via cmd_detail --all --reconcile in test_cli.py |
| _run_detail_reconcile_path | — | test_cli.py (cli_module._run_detail_reconcile_path at 4484–4622) |
| _walk_saved_detail_reconcile | test_reconcile_engine.py | via _run_detail_reconcile_path in test_cli.py |
| _cmd_run_reconcile | — | via cmd_run --iterate in test_cli.py |
| _save_and_walk_run_reconcile | — | via _cmd_run_reconcile in test_cli.py |
| _walk_saved_run_reconcile | test_reconcile_engine.py | via _cmd_run_reconcile in test_cli.py |
| _print_attributed_files | — | test_cli.py (imported + called at 9408, 9418, 9436, 9439) |
| _emit_drift_halt_warning | test_reconcile_engine.py | via _iterate_reconcile_loop in test_cli.py |
| _run_auto_reconcile_on_drift | — | test_auto_reconcile.py / test_cli.py (cli_module._run_auto_reconcile_on_drift, 7 call sites) |
| _emit_scope_guard_plan | test_reconcile_engine.py | via _iterate_reconcile_loop in test_cli.py |
| _iterate_reconcile_loop | — | test_cli.py (cli_module._iterate_reconcile_loop, ~20 call sites) |
| _walk_with_reconcile_phase | — | via _iterate_reconcile_loop in test_cli.py |
| _find_saved_reconcile_for_step | test_reconcile_engine.py | via _ask_reuse_saved_reconcile in test_cli.py |
| _ask_reuse_saved_reconcile | test_reconcile_engine.py | via cmd_run/cmd_detail in test_cli.py |
| _prompt_reuse_saved_reconcile | test_reconcile_engine.py | via _ask_reuse_saved_reconcile in test_cli.py |
| _find_saved_detail_reconcile_for_step | test_reconcile_engine.py | via _ask_reuse_saved_detail_reconcile in test_cli.py |
| _ask_reuse_saved_detail_reconcile | test_reconcile_engine.py | via cmd_detail --reconcile in test_cli.py |
| _prompt_reuse_saved_detail_reconcile | test_reconcile_engine.py | via _ask_reuse_saved_detail_reconcile in test_cli.py |
| _find_saved_run_reconcile_for_step | test_reconcile_engine.py | via _ask_reuse_saved_run_reconcile in test_cli.py |
| _ask_reuse_saved_run_reconcile | test_reconcile_engine.py | via cmd_run --iterate in test_cli.py |
| _prompt_reuse_saved_run_reconcile | test_reconcile_engine.py | via _ask_reuse_saved_run_reconcile in test_cli.py |
| _build_review_action_fn | test_review_actions.py | test_review_walk.py (direct calls at 1667–3142) |
| _prompt_reuse_saved_review | — | via cmd_review_walk in test_review_walk.py |
| _review_walk_environment_allows | — | test_review.py (imported at 3305) |
| cmd_review | — | test_review.py (main(["reconcile-plan", …]) at 2050–4706; canonical command is `reconcile-plan`, handler keeps `cmd_review`) |
| cmd_review_walk | — | test_review_walk.py (main(["reconcile-plan-walk", …]) throughout) |
| cmd_review_all | test_review_cmds.py (audit-only gate) | test_cli.py — `verify-all --mode` sweep worker (reached via `cmd_verify_all`) |
| cmd_completeness_apply | — | test_cli.py (main(["completeness-apply", …])) |
| cmd_verify | — | test_launcher.py / test_cli.py — `verify-all --rollup` worker (reached via `cmd_verify_all`; `verify` alias defaults to it) |
| cmd_verify_all | test_review_cmds.py (mode/rollup gate) | dispatcher for `verify-all` (+ aliases `reconcile-all` / `review-all` / `verify`) |
| cmd_completeness | test_completeness_cmd.py (main completeness-audit) | test_cli.py (cli.cmd_completeness + main(["completeness-audit", …])) |
| _fmt_finding_counts | test_completeness_cmd.py | via cmd_completeness in test_cli.py |
| _finding_progress_label | test_completeness_cmd.py | via cmd_completeness in test_cli.py |
| _completeness_has_blocking_findings | test_completeness_cmd.py | via cmd_completeness in test_cli.py |
| _print_status | — | test_cli.py (imported + called at 12917–12928) |
| build_parser | test_package_surface.py | test_cli.py (imported + called at 33, 48, 5172–5582, 12874, 12877) |
| main | test_package_surface.py | test_cli.py + most suites (imported + called, 200+ invocations) |

> **Note on `_dispatch_apply_finding`** — this is a *nested* helper inside
> `_build_review_action_fn`, not a module-level function, so it is not a
> row above. It is pinned split-proof via the `_build_review_action_fn`
> direct tests in `tests/cli/test_review_actions.py`, and the package
> split must keep it reachable through that builder (see
> `test_package_surface.py`).
