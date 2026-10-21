> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 2 — Add `--confirm-brief-rebind` only to stage runs

## Summary

Add `--confirm-brief-rebind` to `plan-tool roadmap` as a boolean that only reaches the ordinary stage-run call to `plan_tool/roadmap.py:run_roadmap`. Reject the flag with every non-stage roadmap route before that route can read or write state. Update the CLI catalog, generated roadmap reference, and package-help snapshot from the parser surface. On green, headless stage runs can pass explicit rebind consent; the runner treats it as a no-op when no changed or legacy rebind is needed, while non-stage writers retain their existing behavior when the flag is absent.

## Table of Contents

- [Summary](#summary) — The completed CLI behavior at a glance.
- [Table of Contents](#table-of-contents) — Links to each major section.
- [Why](#why) — Why stage-run consent needs a route boundary.
- [Input](#input) — The upstream admission API and generated-doc contracts.
- [Files (creates vs edits)](#files-creates-vs-edits) — The exact source, test, and generated files changed.
- [Implementation](#implementation) — Parser, dispatch, and non-stage rejection rules.
- [Tests](#tests) — Focused CLI, help, and generated-reference coverage.
- [Acceptance criteria](#acceptance-criteria) — Observable completion conditions.
- [References](#references) — Source-admission and CLI contracts to consult.
- [Applicable guardrails](#applicable-guardrails) — Scope limits for this flag.
- [Deferred](#deferred) — Work intentionally left to later scope.

## Why

`plan_tool/cli/roadmap_cmd.py:cmd_roadmap` currently forwards a repeated `--from-existing` path to the stage runner without a separate consent signal. Step 1 supplies the confirmation-aware admission API; this step exposes it to operators without letting unrelated roadmap writers treat it as authority to change their own source or artifact routes.

## Input

- **Step 1 admission API:** Step 1 adds the keyword-only `confirm_brief_rebind` input to `plan_tool/roadmap.py:run_roadmap` and its `_run_roadmap` admission path. The CLI must forward a boolean only for the ordinary stage-run route and leave the source-path and digest decision to that API.

- **Route selection:** `plan_tool/cli/roadmap_cmd.py:cmd_roadmap`, `_has_candidate_lifecycle_action`, `_has_feedback_reopen`, `_has_structural_rewrite`, and the existing broad-mode branches identify requests that do not run stages.

- **Generated references:** `plan_tool/cli_reference.py:render_reference` derives `docs/cli/roadmap.md` from `plan_tool/cli/roadmap_cmd.py:register`. Regenerate the reference instead of hand-editing it.

## Files (creates vs edits)

- **New files:** None.

- **Existing files (edits only):**
  - `plan_tool/cli/roadmap_cmd.py` — Parse the new boolean, reject it for non-stage routes before dispatch, and forward it only to `run_roadmap`.
  - `plan_tool/cli/__init__.py` — Update the Roadmap catalog in the package docstring so top-level help describes confirmed stage rebinds accurately.
  - `tests/cli/test_roadmap_cmd.py` — Cover parsing, forwarding, stage compatibility, and rejection before every non-stage route.
  - `tests/cli/package_surface_help.golden.txt` — Refresh the top-level help snapshot after the catalog and parser changes.
  - `docs/cli/roadmap.md` — Regenerate the parser-derived roadmap reference.

## Implementation

- **Foundational logic:** add a stage-route-only confirmation predicate. `--confirm-brief-rebind` is valid for the ordinary stage dispatch and invalid whenever the request selects a non-stage roadmap route.

- **Keep the parser input simple:** add `--confirm-brief-rebind` in `plan_tool/cli/roadmap_cmd.py:register` as a false-by-default boolean. Its help must identify explicit rebind consent, stage-run-only scope, and the fact that it does not create an interactive confirmation path.

- **Forward only at the stage seam:** in `plan_tool/cli/roadmap_cmd.py:cmd_roadmap`, pass the parsed boolean to the sole `run_roadmap` call using the upstream keyword name. Do not inspect brief contents, compare paths, or classify changed, legacy, matching, initial, or different-path requests in the CLI; Step 1 owns that admission decision.

- **Keep ordinary stage calls composable:** a true flag remains a valid stage-run input when the runner observes matching or initial source state; it is a no-op there. Do not reject it in the CLI merely because no baseline replacement is needed.

- **Reject non-stage requests before their writers:** place the route check before candidate lifecycle, feedback reopen, baseline enrollment, structural rewrite, escalation, impact-analysis, local-feedback revision, seed, and view dispatch. A rejected combination must use the established usage exit and a concise error that exposes no brief content, and it must not invoke a non-stage handler or writer.

- **Cover every non-stage route family:** treat `--apply`, `--refresh-seeds`, `--accept-seed`, `--materialize`, ordinary and HTML `--view`, `--enroll-baselines`, `--revise-feedback`, candidate lifecycle actions, feedback reopening, escalation receipts, impact analyses, and structural rewrite as non-stage requests for this flag. Keep their existing behavior unchanged when the flag is absent.

- **Do not make the flag a broad mode:** retain `_TrackRoadmapMode`, `_TrackFromStage`, and `_broad_mode_companions_present` as the owners of existing broad-mode parsing and conflict output. The confirmation flag must remain compatible with `--from-stage`, so it must not join the mutually exclusive broad-mode group or be routed through non-stage `mode_rejected` work.

- **Keep the catalog and generated docs aligned:** update the Roadmap entry in `plan_tool/cli/__init__.py`, then regenerate `docs/cli/roadmap.md` through `python -m plan_tool.cli_reference --write`. Refresh `tests/cli/package_surface_help.golden.txt` through the existing `TestHelpGoldenSnapshot` update path.

## Tests

### Tests for this step

- `tests/cli/test_roadmap_cmd.py:test_confirm_brief_rebind_parses_false_by_default_without_joining_broad_modes` — The parser defaults the flag to false, accepts it with a stage run, and keeps `--from-stage` in the existing stage-route path.

- `tests/cli/test_roadmap_cmd.py:test_stage_run_forwards_confirm_brief_rebind` — The ordinary `cmd_roadmap` stage call passes true when requested and false when omitted.

- `tests/test_roadmap.py:test_rebind_confirmation_is_noop_for_matching_baseline` and `tests/test_roadmap.py:test_rebind_confirmation_is_noop_for_initial_recording` — A true stage-run flag remains an upstream no-op whenever no changed or legacy rebind is needed.

- `tests/cli/test_roadmap_cmd.py:test_confirm_brief_rebind_leaves_source_admission_to_run_roadmap` — Stage dispatch does not add local path, digest, or baseline classification before forwarding the flag.

- `tests/cli/test_roadmap_cmd.py:test_confirm_brief_rebind_rejects_every_non_stage_route_before_dispatch` — A parameterized matrix of non-stage routes returns the usage status, emits the stage-only error, and reaches no selected handler or writer.

- `tests/cli/test_roadmap_cmd.py:test_non_stage_routes_keep_existing_dispatch_when_confirm_brief_rebind_is_absent` — Existing non-stage routes retain their handler, arguments, result mapping, and normal write path without the new flag.

- `tests/cli/test_roadmap_cmd.py:test_help_documents_confirm_brief_rebind_as_stage_only` — Parser help names the flag and its route-local scope.

- `tests/cli/test_package_surface.py:TestHelpGoldenSnapshot.test_help_matches_golden` — The refreshed package-help snapshot matches the parser and catalog.

- `tests/cli/test_cli_reference.py:TestCliReferenceDrift.test_every_generated_file_matches_disk` — The regenerated `docs/cli/roadmap.md` matches the live parser output.

Every listed test and the plan’s full test command must be green before this step is complete.

## Acceptance criteria

- `plan-tool roadmap <slug> --confirm-brief-rebind` reaches `plan_tool/roadmap.py:run_roadmap` with `confirm_brief_rebind=True`.

- A stage run without the flag reaches `run_roadmap` with `confirm_brief_rebind=False`.

- The flag remains valid with `--from-stage N` and does not join the broad-mode mutual-exclusion group.

- Matching and initial stage dispatches accept the flag and receive the no-op behavior owned by `run_roadmap`; the CLI does not reject them as superfluous.

- Every request that selects a non-stage roadmap route with `--confirm-brief-rebind` exits with the established usage status before the route’s handler, writer, backend, or HTML output path runs.

- Non-stage routes without the flag preserve their existing dispatch and write behavior.

- `plan_tool/cli/__init__.py`, `tests/cli/package_surface_help.golden.txt`, and generated `docs/cli/roadmap.md` describe the parser’s confirmed stage-run surface consistently.

## References

- [Roadmap Brief Rebind Confirmation plan](../../2-roadmap-brief-rebind-confirmation.md) — Read the stage-only authority boundary and step dependencies.

- [BACKLOG.md](../../../../BACKLOG.md) — Read #367’s confirmed operator-consent scope contract.

- [plan_tool/roadmap.py](../../../../plan_tool/roadmap.py) — Read `run_roadmap` and `_run_roadmap` for the admission API this CLI exposes.

- [plan_tool/cli/roadmap_cmd.py](../../../../plan_tool/cli/roadmap_cmd.py) — Read `cmd_roadmap`, `register`, and route-conflict helpers for dispatch ownership.

- [ROADMAP_FORMAT.md](../../../../ROADMAP_FORMAT.md#concept-brief-source-admission-and-lifecycle) — Read the baseline-only and redacted source-admission lifecycle.

- [DATA_CONTRACT.md](../../../../DATA_CONTRACT.md#roadmap-source-admission-lifecycle-event) — Read the persisted admission-event vocabulary that this step must preserve.

## Applicable guardrails

- **The plan’s “## Scope guardrails”, admission condition:** Limit this CLI work to carrying the explicit boolean into the stage-run admission boundary; do not add new source facts or decision logic.

- **The plan’s “## Scope guardrails”, non-interactive behavior:** Do not add prompts, TTY checks, or infer consent from `--yes`, a repeated path, or automation context.

- **The plan’s “## Scope guardrails”, narrow implementation:** Keep the route check local to roadmap CLI dispatch; do not extract generic confirmation infrastructure or change exit-code conventions.

- **The plan’s “## Out of scope”, non-stage writer policy:** Reject the new flag before non-stage routes without changing their independent writer or changed-brief policies.

- **The plan’s “## Out of scope”, ordinary stage runs:** Preserve matching-baseline, initial, and different-path behavior by forwarding the flag to Step 1 rather than adding CLI-side admission rules.

## Deferred

- Broader source-lifecycle and operator-guide wording — Step 3 owns the durable contract and guide sweep outside this CLI-generated reference.

- Confirmation for any non-stage roadmap authority — Keep it outside this route-local flag and record separate evidence-backed work if needed.
