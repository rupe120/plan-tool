> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 5 — Publish route, exit, and --no-distill compatibility semantics

## Summary

Publish the selected file-backed ingestion route through `plan_tool/create.py:CreateResult` and `plan_tool/cli/authoring.py:cmd_create`. Make `direct`, `normalized`, `split`, and `refused` visible to library and CLI callers without guessing from a missing plan path or the `--no-distill` flag. Update `docs/cli/create.md` and focused tests for TTY, `--yes`, and non-TTY behavior. On green, published routes exit 0, split remains a discoverable no-plan success, and post-preflight refusal exits 2 with its reason.

## Table of Contents

- [Summary](#summary) — Reviewer overview of the route, exit, and compatibility change.
- [Table of Contents](#table-of-contents) — Links to each section in this detail.
- [Why](#why) — The current ambiguous no-plan result and flag behavior.
- [Input](#input) — Upstream route results and current CLI handoff contracts.
- [Files (creates vs edits)](#files-creates-vs-edits) — Files changed by this step.
- [Implementation](#implementation) — Route publication, output, exit, and compatibility rules.
- [Tests](#tests) — Focused route and caller-mode coverage.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — CLI and test references.
- [Applicable guardrails](#applicable-guardrails) — Scope limits for this step.
- [Deferred](#deferred) — Lifecycle and broader documentation work left to later steps.

## Why

`plan_tool/create.py:CreateResult` currently uses `plan_path=None` only for a split, while steps 3 and 4 introduce a second no-plan result: a post-preflight refusal. `plan_tool/cli/authoring.py:cmd_create` also treats `--no-distill` as a direct control over the existing first pass, so a file-backed caller can bypass the selected route. The CLI needs one explicit result contract so people, scripts, run logs, and direct pipelines can distinguish a published plan, a split to carve, and an input refusal.

## Input

- **Step 3 result contract:** Consume its closed file-backed preparation outcomes: `normalized`, `split`, and `refused`. Do not restore raw passthrough as a result.
- **Step 4 refusal:** Treat its unsupported-evidence result as the same post-preflight `refused` route, with a reason suitable for output and logging.
- **Current create handoff:** `plan_tool/create.py:_prepare_create_plan`, `plan_tool/create.py:create_plan`, and `plan_tool/create.py:CreateResult` carry the outcome from preparation or publication to callers.
- **Current CLI seams:** `plan_tool/cli/authoring.py:cmd_create` owns exit codes, `_create_result_sink`, `_rollback_branch_collision`, the success tail, and `_emit_split_proposal`.
- **Run-log surface:** Reuse `plan_tool/run_log.py:RunLogWriter` and its
  existing phase-end extra payload support through `run_logger`; this step does
  not change the run-log schema.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `plan_tool/create.py` — carry the selected file-backed route and refusal reason through the public create result, and record the route once when an active run logger exists.
  - `plan_tool/cli/authoring.py` — render route-aware completion or refusal output, select the required exit code, preserve split interaction rules, and keep `--no-distill` inline-only.
  - `docs/cli/create.md` — generated command reference that reflects the parser help; do not hand-edit it.
  - `tests/test_distill.py` — cover library-level route publication and inline compatibility.
  - `tests/cli/test_authoring_cmds.py` — cover CLI output, exits, logging, split interaction, and branch cleanup.

## Implementation

- **Foundational logic:** Publish one explicit selected file-backed route without inferring it from `CreateResult.plan_path`, `SplitProposal`, `distilled_seed`, or `distill`.

- **Carry a closed route result.** Extend the `plan_tool/create.py:CreateResult` handoff, or use an equivalent typed result visible to `create_plan` callers, so file-backed outcomes identify `direct`, `normalized`, `split`, or `refused`. Include a refusal reason only for `refused`; inline callers may retain no file-backed route value.

- **Keep the library non-destructive.** A public `create_plan(..., from_existing_path=...)` call returns the selected route and enough clean normalized payload for its caller to inspect, but never moves its supplied source or writes a normalized sibling. `cmd_create` is the sole command-level owner of destructive source/artifact archival; step 6 consumes this route result to decide whether that CLI action is eligible.

- **Keep existing result construction compatible.** `CreateResult` is re-exported by `plan_tool/__init__.py`, and test and in-process callers construct it directly. Preserve the existing constructor shape for ordinary and inline results while updating its current “no plan means split” documentation.

- **Route file-backed calls before consulting `distill`.** In `plan_tool/create.py:_prepare_create_plan`, use steps 3 and 4’s selected result for every call with `from_existing_path`. `distill=False`, including the CLI’s `--no-distill` value and the library default, must not skip file-backed classification, direct assessment, preparation, or refusal.

- **Retain inline behavior.** Calls without `from_existing_path` must keep their present `distill` behavior. In particular, `plan_tool/create.py:create_plan` library callers and `plan_tool create --from … --no-distill` must retain the existing raw-seed bypass rather than receiving a file-backed route.

- **Report each terminal route clearly.** In `plan_tool/cli/authoring.py:cmd_create`, name `direct` or `normalized` beside the existing successful creation summary. Name `split` while preserving `_emit_split_proposal`’s operator next action. Print `refused` and its reason as an input failure, without a created-plan summary, grounding stamp, audit hint, archive report, or split worksheet.

- **Keep split interaction stable.** `plan_tool/cli/authoring.py:_emit_split_proposal` must continue to ask a TTY operator whether to save the worksheet, while `--yes` and non-TTY calls save it automatically. All three modes must still print the split next action and return success.

- **Clean up every no-plan branch outcome.** A refused result returns 2 in
  TTY, --yes, and non-TTY modes without asking for confirmation; a split
  remains an exit-0 success. Both are no-plan outcomes for the branch-collision
  rollback helper, so either result clears a collision-created binding and
  restores the invocation branch before split rendering or refusal output. The
  empty disambiguated branch remains reported rather than deleted.

- **Record one selected route.** Emit one route observation through the existing `run_logger` seam after the run log is active. Include the selected route for every file-backed terminal outcome and include the refusal reason only for `refused`. Keep unmatched-fence input safety and `validate_from_existing_seed`’s References preflight outside this path: both return 2 before `RunLogWriter.start` and neither names a selected route.

- **Reuse direct-pipeline behavior unchanged.** `plan_tool/cli/direct_cmd.py:cmd_direct_jira` and `plan_tool/cli/direct_cmd.py:cmd_direct_run` already stop on a nonzero `cmd_create` return before reading `_create_result_sink`. Do not widen this step into direct-pipeline changes.

- **Leave lifecycle work to step 6.** Do not rework `archive_existing_source`, normalized-artifact writes, checkpoint versioning, or checkpoint cleanup here. This step only makes the selected route observable and applies its command behavior.

- **Update the generated CLI reference narrowly.** Change the parser help in `plan_tool/cli/authoring.py` for the inline-only `--no-distill` rule and route-specific exits, then regenerate `docs/cli/create.md` with `python -m plan_tool.cli_reference --write`. Do not hand-edit the generated reference or duplicate the broader ingestion-flow documentation.

## Tests

Every test below must be green before this step is complete.

### Tests for this step

- `tests/test_distill.py::test_file_backed_no_distill_uses_selected_route` — file-backed `create_plan` calls select the same route whether `distill` is true or false.
- `tests/test_distill.py::test_inline_no_distill_keeps_legacy_distill_bypass` — inline input with `distill=False` skips the existing distill call.
- `tests/test_distill.py::test_file_backed_result_distinguishes_published_split_and_refused_routes` — library results distinguish direct or normalized publication from split and refused no-plan outcomes.
- `tests/test_distill.py::test_file_backed_library_success_leaves_caller_source_untouched` — direct and normalized `create_plan` calls retain their supplied path while exposing the selected route.
- `tests/cli/test_authoring_cmds.py::test_cmd_create_route_output_and_run_log_agree` — direct, normalized, split, and refused routes emit one matching route record and user-visible outcome.
- `tests/cli/test_authoring_cmds.py::test_cmd_create_refused_exits_two_without_success_tail` — post-preflight refusal exits 2 in TTY, `--yes`, and non-TTY modes without plan completion output.
- `tests/cli/test_authoring_cmds.py::test_cmd_create_split_preserves_tty_and_headless_save_behavior` — TTY save choice remains optional while `--yes` and non-TTY calls save the worksheet and return 0.
- `tests/cli/test_authoring_cmds.py::test_file_backed_preflight_refusals_open_no_run_log` — unmatched-fence and missing, placeholder, or ambiguous References input remain explicit no-route, no-run-record refusals.
- `tests/cli/test_authoring_cmds.py::test_cmd_create_refusal_rolls_back_branch_collision` — a returned refused route removes the temporary branch binding before exit 2.
- `tests/cli/test_authoring_cmds.py::test_cmd_create_split_rolls_back_branch_collision_before_worksheet` — a split clears the temporary binding and restores the invocation branch while retaining its source and normal worksheet behavior.

## Acceptance criteria

- File-backed `create_plan` results expose exactly one of `direct`, `normalized`, `split`, or `refused`; inline results retain current `distill` compatibility.
- File-backed library calls are non-destructive: source and normalized-artifact writes remain CLI-only lifecycle work.
- `--no-distill` cannot bypass file-backed routing, preparation, or refusal.
- Direct and normalized results publish a plan and exit 0 with a visible route.
- Split exits 0, writes no plan or manifest entry, names the route, and retains its existing TTY versus headless worksheet behavior.
- Split and post-preflight refusal both roll back a collision-created branch
  binding because neither leaves a plan, without deleting the empty
  disambiguated branch.
- Post-preflight refusal exits 2 with its reason, writes no plan or manifest entry, skips all success-only CLI work, and rolls back branch-collision state.
- Post-preflight file-backed outcomes record their selected route once in the active run log; unmatched-fence and References preflight refusals open no run log.
- `docs/cli/create.md` states that `--no-distill` applies only to inline input and documents route exits.
- `uv run pytest tests/test_distill.py tests/cli/test_authoring_cmds.py -q` passes.

## References

- [Python argparse — Parser for command-line options, arguments and subcommandshttps: — Read for parser-controlled flags and command exit behavior.
- [Python enum — Support for enumerationshttps: — Read for keeping the file-backed route vocabulary closed and typed.
- [pytest — How to use temporary directories and files in testshttps: — Read for hermetic CLI, filesystem, and TTY-mode tests.

## Applicable guardrails

- **The plan’s “## Plan intent”** — preserve supplied file-backed authority and make preparation visible; do not add a second implicit rewriting path.
- **The plan’s “## Step intent”** — expose the route and terminal outcome consistently for interactive and headless callers while keeping inline compatibility.
- **The plan’s “## Out of scope”** — keep `SplitProposal` inside `create`, and do not expand this work into a broader source-quality policy or heading-alias change.

## Deferred

- Terminal route lifecycle (`22a740fdbaa54ae54299f4be8f7189fd05c322dc42e247bba3ec3e71d1b4abdc`) — step 6 owns checkpoint, archive, and normalized-artifact handling for each selected route.
- Broader ingestion, resume, seed-format, README, arc, and backlog documentation — step 7 owns the maintained cross-document contract.
