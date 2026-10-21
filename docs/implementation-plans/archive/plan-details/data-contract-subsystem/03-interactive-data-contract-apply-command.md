> **Auto-archived**: this plan was swept on 2026-07-07 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 3 — Add Interactive Data Contract Apply Command

## Summary

This step adds `plan-tool data-contract-apply` as the interactive replay command for contract-documentation drift findings saved by the step 2 completeness audit integration. The main implementation lives in `plan_tool/cli/data_contract_cmd.py`, with parser registration in `plan_tool/cli/app.py` and ordering in `plan_tool/cli/parser.py`. The key design decision is to reuse the saved-review and walk machinery instead of creating a second annotation format: load a saved completeness audit, filter to step 2's applyable `DATA_CONTRACT.md` recommendations, load their structured drift payloads, verify freshness, and drive them through `walk_recommendations`. On green, an operator can review and apply `DATA_CONTRACT.md` drift fixes one at a time, annotations persist back into the saved audit JSON, and `plan-tool --help` plus package-surface tests know about the new command.

## Table of Contents

- [Summary](#summary) — The behavior this step adds and the main files it touches.
- [Why](#why) — Why data-contract drift needs its own apply path.
- [Files (creates vs edits)](#files-creates-vs-edits) — The exact files this step creates or changes.
- [Implementation](#implementation) — The command shape, saved-review replay flow, and constraints.
- [Tests](#tests) — The test cases that cover the command.
- [Test-creation order feature step](#test-creation-order-feature-step) — The order to add tests while building the feature.
- [Acceptance criteria](#acceptance-criteria) — Observable checks for completion.
- [References](#references) — Primary docs relevant to this step.
- [Deferred](#deferred) — Work intentionally left out.

## Why

Steps 1 and 2 make data-contract drift visible, but visibility alone still leaves the operator hand-editing `DATA_CONTRACT.md` from an audit report. That is weaker than the rest of plan-tool's saved-finding workflow: reconcile and completeness findings can be walked, annotated, retried, or skipped with their decisions persisted. Data-contract drift should have the same operator loop, especially because the code is the source of truth and the correct fix is usually a focused documentation edit, not a schema change.

## Files (creates vs edits)

- **New files:**
  - `plan_tool/cli/data_contract_cmd.py` — Add the `data-contract-apply` command module, saved-audit loading, recommendation filtering, action callback, and `register(subparsers)`.
  - `tests/cli/test_data_contract_cmd.py` — Add focused command tests for loading, filtering, walking, apply dispatch, annotation persistence, and non-interactive behavior.

- **Existing files (edits only):**
  - `plan_tool/cli/__init__.py` — Add `data-contract-apply` to the live top-level help catalog so the module docstring stays in sync with registered commands.
  - `plan_tool/cli/app.py` — Import `plan_tool.cli.data_contract_cmd`, re-import `cmd_data_contract_apply`, append the module to `COMMAND_MODULES`, and add `data-contract-apply` to `_LOCKED_MUTATING_COMMANDS`.
  - `plan_tool/cli/parser.py` — Add `data-contract-apply` to `CANONICAL_COMMAND_ORDER`, likely near `completeness-apply` because it consumes completeness-audit saves.
  - `plan_tool/review_persistence.py` — Preserve existing saved-review metadata such as `detail_bundle_fingerprint` and `detail_bundle_fingerprint_present` when `update_annotation` rewrites completeness saves.
  - `tests/cli/test_package_surface.py` — Add any handler-name exception only if the command name does not map mechanically to `cmd_data_contract_apply`; otherwise keep the parser/dispatch correspondence tests unchanged.
  - `tests/cli/package_surface_help.golden.txt` — Regenerate the golden help after the new command is registered.
  - `tests/test_data_contract.py` — Add only targeted doc checks needed for this command's documented source or operator-facing contract; do not change schema-field tests unless upstream steps changed the registry.
  - `DATA_CONTRACT.md` — Document the data-contract drift finding source and the apply workflow at the human contract level, without implying the tool loads this markdown at runtime.

## Implementation

- **Foundational logic: saved contract-doc finding replay.** Build the command around replaying data-contract documentation-drift recommendations already persisted by step 2, not around re-running drift detection. The command should load a saved completeness audit, filter to the data-contract finding source defined by steps 1 and 2, load the structured payload for each applyable `DATA_CONTRACT.md` finding, verify freshness, then let the existing review walk own prompts and annotations.

- **Use the command-module seam.** Follow the existing pattern in `plan_tool/cli/completeness_cmd.py:register` and `plan_tool/cli/review_cmd.py:cmd_review_walk`: `plan_tool/cli/data_contract_cmd.py` should expose `register(subparsers) -> dict[str, Handler]` and a module-level `cmd_data_contract_apply(args)` handler. Add the module to `plan_tool/cli/app.py:COMMAND_MODULES`, and import `cmd_data_contract_apply` in `plan_tool/cli/app.py` so `plan_tool.cli` re-exports it through the existing package mirror.

- **Hold the repo mutation lock.** Add `data-contract-apply` to `plan_tool/cli/app.py:_LOCKED_MUTATING_COMMANDS` because the command mutates `DATA_CONTRACT.md` and writes saved-review annotations. The lock requirement belongs with the command registration so this apply path cannot bypass the same repo mutation guard used by other mutating commands.

- **Keep parser ordering and catalog help explicit.** Add `data-contract-apply` to `plan_tool/cli/parser.py:CANONICAL_COMMAND_ORDER`. A good location is after `completeness-apply`, because the command consumes the data-contract recommendations that completeness audits persist. Update `plan_tool/cli/__init__.py`'s command catalog docstring in the same step because `build_parser` uses it as live top-level help, then update `tests/cli/package_surface_help.golden.txt`.

- **Resolve the saved audit like an apply command.** Use `plan_tool/cli/completeness_cmd.py:cmd_completeness_apply` as the closest shape: `_load_context(args)`, `resolve_plan_for_context(ctx, args.name)`, `resolve_saved_review`, `load_review`, and a `kind == "completeness"` guard. Support `--id` for a specific saved audit and default to the newest `-completeness.json` that contains data-contract recommendations. If none exists, print a clear error telling the operator to run `plan-tool completeness-audit <name>` first.

- **Filter by source and apply target.** Do not duplicate detector logic in the CLI. Prefer an exported source constant or classifier from the step 1 registry/result module if it exists; otherwise keep one private constant in `plan_tool/cli/data_contract_cmd.py` only when a producer-facing test proves it matches the step 2 persisted recommendation source. The filter should keep only saved data-contract recommendations whose structured payload declares `target="DATA_CONTRACT.md"` and an applyable operation such as `add`, `update`, `remove`, or `intentional-exclusion`. Recommendations for stale plan/detail `## Input` references must be reported as non-applyable here, because they target plan/detail prose rather than the contract document. Preserve saved order, and support `--anchor` matching both `Recommendation.id` and `Recommendation.anchor`, mirroring `plan_tool/cli/completeness_cmd.py:cmd_completeness_apply`.

- **Reuse `walk_recommendations`.** Load the `SavedReview` from disk so `SavedReview.path` is populated, narrow `saved.recommendations` in memory to the filtered data-contract findings, then call `plan_tool.review_walk:walk_recommendations`. Pass the command-local action callback and make the data-contract source dispatchable with `extra_apply_sources` or an equivalent reviewed dispatchability hook, alongside `rewalk=args.rewalk` and `skip_info=not args.include_info` if the command exposes `--include-info`. Let `update_annotation` persist decisions through the walk only after its rewrite path preserves existing saved-review metadata, including `detail_bundle_fingerprint` and `detail_bundle_fingerprint_present`; do not create a data-contract-specific annotations file.

- **Apply with a data-contract document actuator.** Do not route data-contract edits through `plan_tool.launcher:apply_finding`, because that launcher is scoped to plan and detail files. Build a command-local action callback that treats `DATA_CONTRACT.md` as the only editable target, reads the structured drift payload rather than inferring edits from `Recommendation.body`, applies the approved contract-document change, confirms the file changed as expected, and leaves production code alone while saved-review writes are limited to annotations plus preserved existing metadata.

- **Require freshness before mutation.** Each applyable payload must carry the registry/code fingerprint and `DATA_CONTRACT.md` fingerprint captured when the audit saved the finding. Before applying, recompute or reload the current fingerprints and refuse to mutate if either side changed. The refusal should record a clear skipped/blocked annotation telling the operator to rerun `plan-tool completeness-audit <name>` so stale saved findings cannot update a contract section after code or docs moved underneath them.

- **Present operator choices from payload metadata.** For candidate fields or sections, the command should show the structured owner, field/key, target section, current code facts, and candidate operation, then ask the operator for stable/internal, required/optional, invariant/migration notes, or intentional-exclusion decisions when those choices are missing from the payload. Persist only the resulting `DATA_CONTRACT.md` edit and annotation; do not try to encode these decisions in free-form recommendation text.

- **Reuse only generic walk behavior whose contract fits.** `plan_tool/cli/review_actions.py:_build_review_action_fn` is useful background for carried findings, run logging, revert behavior, and failure-to-annotation signaling, but its `apply_finding` dispatch must not be the actuator for this command unless that contract is expanded in a later step to include `DATA_CONTRACT.md`. Keep the apply callback local to `plan_tool/cli/data_contract_cmd.py` for this step.

- **Protect non-interactive runs.** Match `plan_tool/cli/completeness_cmd.py:cmd_completeness_apply`: when stdin is not a TTY, report the matching findings and exit 0 without blocking on prompts. Do not silently auto-apply in CI. A future non-interactive mode can be separate.

- **Document only the operator contract.** In `DATA_CONTRACT.md`, mention that data-contract drift findings can be persisted by completeness audits and walked by `data-contract-apply`. Keep the existing source-of-truth rule intact: the markdown is for humans and agents, and code-owned registry/checks from steps 1 and 2 remain authoritative.

## Tests

- `test_registers_data_contract_apply_command` — `plan_tool.cli.build_parser()` includes `data-contract-apply`, and `assemble(app.__doc__, app.COMMAND_MODULES)` maps it to `cmd_data_contract_apply`.
- `test_data_contract_apply_is_locked_mutating_command` — `plan_tool/cli/app.py:_LOCKED_MUTATING_COMMANDS` includes `data-contract-apply`.
- `test_help_golden_includes_data_contract_apply` — `tests/cli/package_surface_help.golden.txt` matches the regenerated `plan-tool --help` output.
- `test_errors_when_no_completeness_audit_exists` — the command returns usage-style failure and tells the operator to run `completeness-audit` first.
- `test_errors_on_non_completeness_save` — `--id` pointing at a non-`kind="completeness"` sidecar returns a clear error.
- `test_filters_saved_review_to_applyable_contract_doc_findings` — mixed saved recommendations that use the step 2 persisted data-contract source walk only those with structured `DATA_CONTRACT.md` payloads.
- `test_input_reference_findings_are_reported_non_applyable` — stale `## Input` reference recommendations are listed or skipped with a clear plan/detail-target message and are not passed to the `DATA_CONTRACT.md` actuator.
- `test_anchor_filters_by_id_or_anchor` — `--anchor` accepts both `Recommendation.id` and `Recommendation.anchor`, and warns for misses.
- `test_non_interactive_reports_without_walking` — non-TTY stdin prints matching findings and does not call `walk_recommendations`.
- `test_walk_persists_annotations_to_saved_audit` — an apply/skip decision writes through `update_annotation` to the original saved JSON while preserving existing detail bundle fingerprint fields.
- `test_apply_dispatch_updates_data_contract_for_data_contract_rec` — choosing apply makes the data-contract source dispatchable, calls the command's `DATA_CONTRACT.md` action callback, and records `applied` on success.
- `test_apply_requires_structured_payload` — a saved data-contract recommendation without a matching payload is blocked with a rerun-audit message rather than inferred from prose.
- `test_apply_refuses_stale_fingerprints` — a changed registry/code or `DATA_CONTRACT.md` fingerprint blocks mutation and asks the operator to rerun `completeness-audit`.
- `test_failed_apply_records_failed_annotation` — the command-local actuator catches exceptions or non-zero apply results, sets `WalkState.apply_failed`, and records a non-terminal `failed` annotation through `plan_tool.review_walk:walk_recommendations`.

### Test-creation order (feature step)

Add the parser/registration and mutation-lock tests first, then the saved-audit loading and filtering tests, then the interactive walk tests, then the apply-dispatch tests. Build the command alongside those tests so each behavior has a failing test before its implementation lands. The green-before-done gate is: every new test in `tests/cli/test_data_contract_cmd.py`, the updated package-surface tests in `tests/cli/test_package_surface.py`, and the updated drift/doc checks in `tests/test_data_contract.py` must pass.

## Acceptance criteria

- `plan-tool --help` lists `data-contract-apply`, the live command catalog in `plan_tool/cli/__init__.py` includes it, and the golden snapshot in `tests/cli/package_surface_help.golden.txt` is updated.
- `plan_tool.cli.build_parser()` registers `data-contract-apply`, and the dispatch map routes it to `cmd_data_contract_apply`.
- `plan_tool/cli/app.py:_LOCKED_MUTATING_COMMANDS` includes `data-contract-apply` so `DATA_CONTRACT.md` edits and saved annotation writes run under the repo mutation lock.
- `plan-tool data-contract-apply <name>` loads the newest saved `kind="completeness"` audit with applyable data-contract documentation-drift recommendations and matching structured payloads, or `--id` loads the requested save.
- The command walks only `DATA_CONTRACT.md` drift recommendations with structured payloads and leaves unrelated completeness findings plus stale `## Input` plan/detail findings in the saved JSON untouched.
- `--anchor` narrows the walk by `Recommendation.id` or `Recommendation.anchor`.
- Non-interactive stdin reports matching findings and exits 0 without prompting or applying.
- Interactive apply attempts make the data-contract source dispatchable, route through the command's `DATA_CONTRACT.md` action callback, verify saved payload freshness before mutation, and successful, skipped, blocked, and failed decisions persist as `Annotation` entries on the saved audit because the local actuator catches failures and sets `WalkState.apply_failed`; existing detail bundle fingerprint metadata is preserved during annotation write-back.
- `DATA_CONTRACT.md` documents the data-contract drift apply workflow without changing the persisted saved-review schema.
- `pytest tests/cli/test_data_contract_cmd.py tests/cli/test_package_surface.py tests/test_data_contract.py` passes.

## References

- [Python argparse](https://docs.python.org/3/library/argparse.html) — Read for subparser registration, command handlers, hidden aliases, and help output behavior.
- [Python json](https://docs.python.org/3/library/json.html) — Read for saved-review sidecar parsing and write-back expectations.
- [pytest Documentation](https://docs.pytest.org/en/stable/) — Read for fixtures, monkeypatching command seams, and assertion style.
- [CommonMark Specification](https://spec.commonmark.org/) — Read for stable `DATA_CONTRACT.md` section and anchor wording.

## Deferred

- Parallel data-contract apply — This command is an interactive review-and-apply path only; no `--jobs` mode or non-interactive auto-apply belongs in this step.
- New saved-review schema fields — The command reuses `SavedReview.recommendations` and `SavedReview.annotations`; schema additions require a plan-level decision.
- Live drift detection rerun — The command consumes the saved recommendations and payloads from step 2. Re-running the step 1 detector inside the apply command would create a second audit path and is out of scope; freshness mismatches should block and ask the operator to rerun `completeness-audit`.
