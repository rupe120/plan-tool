> **Auto-archived**: this plan was swept on 2026-08-18 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 5 — Extract behavior-preserving roadmap command-mode parsing

## Summary

Replace `plan_tool/cli/roadmap_cmd.py:register`’s broad-mode mutual-exclusion group with occurrence-preserving parsing and one compatibility check before ordinary dispatch. Keep `plan_tool/cli/roadmap_cmd.py:cmd_roadmap`’s current stage, seed, local-revision, and view behavior unchanged for every existing well-formed command. The key decision is to separate collecting mode facts from deciding whether existing modes may coexist, without adding receipt flags or receipt dispatch yet. When green, future receipt wiring can inspect raw option occurrences, while current commands keep the same result, output, and exit status.

## Table of Contents

- [Summary](#summary) — Reviewer-level outcome and compatibility boundary.
- [Table of Contents](#table-of-contents) — Links to each section.
- [Why](#why) — Why parser-level exclusion must become an explicit compatibility rule.
- [Input](#input) — Current parser, namespace, and dispatch contracts this refactor preserves.
- [Files (creates vs edits)](#files-creates-vs-edits) — Production and regression-test changes.
- [Implementation](#implementation) — Required parsing split and unchanged dispatch behavior.
- [Tests](#tests) — Regression coverage for parser state and ordinary command behavior.
- [Acceptance criteria](#acceptance-criteria) — Observable compatibility checks.
- [References](#references) — Primary parser and test references.
- [Applicable guardrails](#applicable-guardrails) — Plan boundaries that limit this refactor.
- [Deferred](#deferred) — Receipt features and unrelated parser consolidation left outside this step.

## Why

`plan_tool/cli/roadmap_cmd.py:register` currently lets `argparse` reject distinct broad modes before `plan_tool/cli/roadmap_cmd.py:cmd_roadmap` can see them. That is correct for existing commands, but it prevents the next step from classifying an overlapping receipt request before broad dispatch begins. Extracting the compatibility decision now gives later receipt wiring the parser facts it needs while isolating and proving that existing roadmap commands do not change.

## Input

- **Current broad-mode contract:** `plan_tool/cli/roadmap_cmd.py:register` defines `--apply`, `--refresh-seeds`, `--accept-seed`, `--materialize`, `--from-stage`, and `--view` as current broad-mode inputs. Preserve their defaults, value shapes, and accepted values.

- **Explicit-stage contract:** `plan_tool/cli/roadmap_cmd.py:_TrackFromStage` distinguishes the default stage from an explicit `--from-stage 1`. Keep both `from_stage` and `from_stage_supplied` available to `plan_tool/cli/roadmap_cmd.py:_revise_feedback_has_conflict`.

- **Existing dispatch order:** `plan_tool/cli/roadmap_cmd.py:cmd_roadmap` routes local revision before ordinary broad actions, then dispatches apply, seed actions, views, or `run_roadmap`. Preserve that order and each handler’s inputs.

- **Test seam:** `tests/cli/test_roadmap_cmd.py:_parse`, `_ns`, `_stub_run`, `TestArgparseWiring`, and `TestViewValidation` provide the parser and command-level regression seams. Extend them rather than creating a parallel test harness.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `plan_tool/cli/roadmap_cmd.py` — Separate broad-mode occurrence collection from compatibility rejection while retaining current parser validation and command dispatch.
  - `tests/cli/test_roadmap_cmd.py` — Replace parser-group-only assertions with parser-state and command-result compatibility coverage.

## Implementation

- **Foundational logic:** Collect broad-mode occurrences, then reject only incompatible existing non-receipt mode combinations before ordinary roadmap work starts.

- **Remove only the parser-level broad-mode exclusion.** Change `plan_tool/cli/roadmap_cmd.py:register` so syntactically valid combinations of current broad-mode options reach a `Namespace` instead of being discarded by `argparse`’s mutual-exclusion group. Keep `--view` choices, `--mode` choices, and `--from-stage` integer conversion strict; malformed values must retain their normal `argparse` usage failure.

- **Preserve occurrence facts without changing current values.** Add private tracking near `plan_tool/cli/roadmap_cmd.py:_TrackFromStage` that retains the order and cardinality needed to distinguish absent, single, and repeated mode options. Keep the existing final namespace values for current consumers: repeated value-taking options, including `--view` occurrences that contain no future `escalations` value, retain the current last-value behavior, and an explicit `--from-stage 1` remains distinguishable from its default.

- **Make one private compatibility boundary.** Have `plan_tool/cli/roadmap_cmd.py:cmd_roadmap`, or a focused helper it calls before ordinary dispatch, decide whether the collected current broad modes are compatible. For a non-receipt invocation, reproduce the current usage result before resolving paths, reading roadmap artifacts, opening a lifecycle, or calling any broad-mode handler.

- **Keep existing ordinary behavior exact.** A valid stage run must still call `run_roadmap` with the same slug, paths, brief, and stage number. Apply, refresh, seed acceptance, materialization, and the five current views must reach their existing helpers unchanged. Preserve the existing `--mode` and `--id` checks around `plan_tool/cli/roadmap_cmd.py:_cmd_roadmap_view`.

- **Protect local revision compatibility.** Keep `plan_tool/cli/roadmap_cmd.py:_cmd_roadmap_revise_feedback` and `_revise_feedback_has_conflict` as the owner of local-revision mode rejection. A single existing companion beside `--revise-feedback` must still reach its typed local preflight rather than a new broad-mode path.

- **Do not add receipt behavior.** Do not register `--escalate-feedback`, `--escalation-reason`, or `--view escalations` in this step. Leave the occurrence-tracking boundary ready for step 6 to attach those inputs and decide their precedence.

- **Do not broaden the refactor.** `plan_tool/cli/run_cmd.py:cmd_run` and `plan_tool/cli/review_cmd.py:cmd_review` also enforce command-mode compatibility, but they govern different command contracts. Keep this extraction local to the roadmap command.

## Tests

### Tests for this step

- `tests/cli/test_roadmap_cmd.py::TestArgparseWiring::test_broad_mode_options_reach_occurrence_preserving_namespace` — Confirms syntactically valid distinct broad modes parse into retained mode state instead of failing in the parser.

- `tests/cli/test_roadmap_cmd.py::TestArgparseWiring::test_repeated_current_broad_option_keeps_current_final_value` — Proves repeated current options keep their existing accepted and last-value behavior.

- `tests/cli/test_roadmap_cmd.py::TestArgparseWiring::test_repeated_ordinary_view_preserves_each_occurrence_and_current_final_value` — Proves repeated non-`escalations` `--view` values remain visible to later wiring while the current view consumer still receives its final value.

- `tests/cli/test_roadmap_cmd.py::test_nonreceipt_broad_mode_conflicts_keep_current_usage_output_and_status` — Compares every distinct broad-mode conflict with the current usage failure, including complete error text and status `2`, before any handler runs.

- `tests/cli/test_roadmap_cmd.py::test_nonreceipt_broad_mode_conflict_has_no_path_or_orchestrator_side_effect` — Proves a compatibility rejection reaches no resolver-dependent command action, view loader, seed helper, or `run_roadmap` call.

- `tests/cli/test_roadmap_cmd.py::test_single_broad_modes_keep_existing_dispatch_contracts` — Covers each current broad mode and verifies it still reaches its existing helper with unchanged arguments and result status.

- `tests/cli/test_roadmap_cmd.py::test_explicit_default_from_stage_remains_visible_after_mode_extraction` — Proves `--from-stage 1` still sets `from_stage_supplied` while an omitted flag does not.

- `tests/cli/test_roadmap_cmd.py::test_revise_feedback_single_mode_conflicts_keep_local_preflight_owner` — Proves current `--revise-feedback` conflicts continue to reach `run_local_feedback_revision` with `mode_rejected` state.

- `tests/cli/test_roadmap_cmd.py::TestViewValidation` — Keeps the current `--mode` and `--id` validation cases green after broad-mode parsing moves.

Every listed test must be green before this step is complete.

## Acceptance criteria

- Existing broad-mode combinations that `argparse` can parse retain enough occurrence state for a later command-mode classifier to distinguish their order and repetition.

- Every existing valid roadmap invocation reaches the same current dispatch branch, receives the same arguments, and returns the same status as before this refactor.

- Every incompatible non-receipt broad-mode combination exits with status `2` and the same complete usage/error output as the current parser rejection, before any ordinary roadmap side effect.

- Repeated current options retain current behavior, including the final value for repeated non-`escalations` views and explicit `--from-stage` tracking; step 6 alone reserves any repeated view containing `escalations` for receipt-inspection rejection.

- Existing `--revise-feedback`, `--view`, `--mode`, and `--id` behavior remains covered and unchanged.

- `tests/cli/test_roadmap_cmd.py` passes.

## References

- [argparse — Parser for command-line options and arguments](https://docs.python.org/3.13/library/argparse.html) — Use for custom actions, defaults, and compatibility-safe command parsing.

- [pytest monkeypatch](https://docs.pytest.org/en/stable/how-to/monkeypatch.html) — Use to prove rejected commands never reach existing handlers.

## Applicable guardrails

- **The plan’s “## Step intent”, compatibility boundary** — Limit this step to behavior-preserving command-mode parsing and the ordinary non-receipt compatibility result.

- **The plan’s “## Plan intent”, receipt-only record** — Do not create a receipt, invoke a backend, or add a receipt handoff while preparing the parser seam.

- **The plan’s “## Out of scope”, local revision compatibility** — Preserve `--revise-feedback` routing, writer behavior, and typed rejection path.

- **The plan’s “## Out of scope”, stage and seed behavior** — Do not change `--from-stage` execution semantics or any seed operation while moving compatibility checks.

## Deferred

- Receipt creation flags, receipt-option validation, and receipt-view parsing — Step 6 owns the public receipt command surface and its precedence rules.

- Receipt lifecycle dispatch and rendering — Step 6 consumes step 4’s runner after this refactor supplies compatible parser state.

- Shared command-mode infrastructure outside `plan_tool/cli/roadmap_cmd.py` — `plan_tool/cli/run_cmd.py:cmd_run` and `plan_tool/cli/review_cmd.py:cmd_review` have separate contracts and remain outside this roadmap-scoped change.
