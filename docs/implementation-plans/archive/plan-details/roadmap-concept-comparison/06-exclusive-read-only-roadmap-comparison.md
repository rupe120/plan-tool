> **Auto-archived**: this plan was swept on 2026-11-05 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 6 — Add the exclusive read-only roadmap comparison CLI while preserving the HTML view overwrite path

<!-- plan-tool:detail-format-version: 1 -->

## Summary

Add one exclusive, model-free comparison route to `plan_tool/cli/roadmap_cmd.py` that selects the comparison snapshots, calls the read-only operation from step 4, and renders cards, patches, or JSON through step 5. Extend `tests/cli/test_roadmap_cmd.py` with parser, dispatch, refusal, and no-write coverage. Update `docs/cli/roadmap.md` to document the shipped selector and output contract. The comparison route must remain separate from existing roadmap views, while `--view html` keeps its current derived-page overwrite behavior unchanged.

## Table of Contents

- [Summary](#summary) — Reviewer overview of the CLI addition and compatibility boundary.
- [Table of Contents](#table-of-contents) — Links to each detail section.
- [Why](#why) — Why one-snapshot roadmap views do not meet comparison review needs.
- [Input](#input) — Read-only operation and renderer contracts supplied by earlier steps.
- [Files (creates vs edits)](#files-creates-vs-edits) — CLI, focused tests, and command documentation changes.
- [Implementation](#implementation) — Exclusive dispatch, selector, output, and compatibility requirements.
- [Tests](#tests) — CLI behavior and safety cases.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Roadmap comparison and existing CLI contracts.
- [Applicable guardrails](#applicable-guardrails) — Read-only, evidence, identity, and scope boundaries.
- [Deferred](#deferred) — Adjacent work that remains outside this step.

## Why

`plan_tool/cli/roadmap_cmd.py:cmd_roadmap` currently offers views over one working roadmap and lifecycle actions, but no route can bind two selected snapshots to the same concept report and complete Git evidence. Step 4 supplies that read-only comparison boundary and step 5 supplies its presentations; this step makes them available without mixing comparison into the lifecycle or existing view behavior.

## Input

- **Step 4 comparison operation:** Consume the read-only result and explicit refusal outcomes from `plan_tool/roadmap_compare_run.py`. It owns snapshot selection validation, complete bundle loading, and controlled Git evidence; the CLI must not recreate those rules.
- **Step 5 renderers:** Consume the terminal-card, complete-patch, and deterministic JSON renderers from `plan_tool/roadmap_compare_render.py`. The CLI selects an output form but must not reformat or filter the returned evidence.
- **Existing roadmap command surface:** Preserve `plan_tool/cli/roadmap_cmd.py:cmd_roadmap`, `_TrackRoadmapMode`, `_reject_incompatible_broad_modes`, `_cmd_roadmap_view`, and `register` contracts for existing routes.
- **Existing HTML behavior:** Preserve the `--view html` branch in `plan_tool/cli/roadmap_cmd.py:_cmd_roadmap_view`, including `plan_tool/roadmap_html.py:review_path` and `plan_tool/fileio.py:atomic_write_text` behavior.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `plan_tool/cli/roadmap_cmd.py` — Register and dispatch the exclusive comparison command, validate its closed selector and output choices, call the step 4 operation and step 5 renderer, and retain existing HTML-view behavior.
  - `tests/cli/test_roadmap_cmd.py` — Add focused parser and dispatch tests for comparison, exclusivity, refusals, output selection, and state preservation.
  - `docs/cli/roadmap.md` — Document the final comparison invocation, selectors, output forms, refusal behavior, and read-only boundary.

## Implementation

- **Foundational logic:** Dispatch one exclusive read-only comparison command from parsed CLI arguments to the bound comparison operation and one selected renderer.

- **Keep comparison exclusive.** Add one explicit comparison route in `plan_tool/cli/roadmap_cmd.py:register` and `cmd_roadmap`. It must reject every companion roadmap action, view refinement, confirmation, lifecycle option, and stage option rather than relying on precedence.

- **Use the existing route structure as the boundary.** Keep broad mode tracking and `_reject_incompatible_broad_modes` correct for existing `--apply`, seed, stage, and `--view` routes. One reasonable approach is a dedicated comparison predicate and dispatch branch, modeled on the typed exclusive actions already handled before ordinary broad-mode dispatch.

- **Keep selector choices closed.** Expose only the base and target forms defined by the plan: a working target or stored target, and an accepted-head default base or explicit stored base. Pass the selected values to the step 4 public operation unchanged; do not add fallback selection, migration, repair, or generalized path inputs.

- **Require an explicit base when no accepted head exists.** Surface step 4’s refusal through the command’s normal error and exit-code conventions. The CLI must not infer a base from working files, a candidate, or another lifecycle record.

- **Select one output form.** Support the card report as the default plus explicit complete-patch and JSON forms. Use the step 5 renderer that matches the requested form, print its returned text directly, and keep output ordering and raw evidence intact.

- **Preserve HTML’s writer exception.** The comparison route must never use `review_path`, `atomic_write_text`, or `render_roadmap_html`. Retain `_cmd_roadmap_view`’s current `--view html` default-file, explicit-output, overwrite, and stdout behavior without routing comparison output through it.

- **Stay model-free and log-free.** The comparison branch must not call `run_roadmap`, `apply_roadmap_seeds`, lifecycle writers, or a backend invoker. It must not create a run log, mutate Git state, or write comparison artifacts.

- **Document only shipped names.** Update `docs/cli/roadmap.md` after the parser names settle. Describe the exact selector combinations, default card output, patch and JSON forms, accepted-head absence refusal, and no-write guarantee without claiming comparison is an ordinary `--view`.

## Tests

- `tests/cli/test_roadmap_cmd.py:test_comparison_default_target_uses_the_read_only_operation` — the default comparison invocation calls the step 4 operation with the working target and accepted-head base selection.
- `tests/cli/test_roadmap_cmd.py:test_comparison_explicit_stored_base_and_target_reach_the_operation_unchanged` — explicit stored selectors reach the operation without CLI-side reinterpretation.
- `tests/cli/test_roadmap_cmd.py:test_comparison_default_renders_cards` — the default form uses the step 5 card renderer and prints its text unchanged.
- `tests/cli/test_roadmap_cmd.py:test_comparison_patch_form_prints_complete_patch_renderer_output` — the patch form uses only the complete-patch renderer.
- `tests/cli/test_roadmap_cmd.py:test_comparison_json_form_prints_deterministic_renderer_output` — the JSON form uses only the JSON renderer and does not add report framing.
- `tests/cli/test_roadmap_cmd.py:test_comparison_refusal_returns_usage_without_rendering` — an operation refusal reports the command error and does not call a renderer.
- `tests/cli/test_roadmap_cmd.py:test_comparison_requires_explicit_base_when_accepted_head_is_absent` — the operation’s missing-accepted-head refusal remains visible without a CLI fallback.
- `tests/cli/test_roadmap_cmd.py:test_comparison_rejects_companion_roadmap_modes_before_disk_or_backend_work` — comparison combined with every incompatible route returns usage before dispatch.
- `tests/cli/test_roadmap_cmd.py:test_comparison_does_not_call_lifecycle_or_writer_paths` — a successful comparison does not call stage, seed, HTML-write, or backend paths.
- `tests/cli/test_roadmap_cmd.py:test_html_view_default_output_still_overwrites_the_review_page` — `--view html` retains its existing default derived-page write and overwrite behavior.
- `tests/cli/test_roadmap_cmd.py:test_html_view_output_dash_still_prints_without_writing` — `--view html --output -` remains the HTML stdout escape hatch.

Every listed test must be green before this step is complete.

## Acceptance criteria

- The roadmap CLI exposes one exclusive comparison route with working/stored target selection and accepted-head/explicit-stored base selection.
- A missing accepted-head selector with no explicit base returns a refusal; the command does not select another base.
- Default output prints the step 5 card report, while explicit patch and JSON output print their matching renderer results unchanged.
- Comparison invokes no backend and writes no roadmap artifact, metadata, seed state, version selector, receipt, run log, comparison file, or Git index entry.
- Comparison rejects incompatible roadmap options before comparison loading or rendering begins.
- `--view html` retains its current default review-page overwrite behavior and `--output -` stdout behavior.
- `tests/cli/test_roadmap_cmd.py` passes with the added comparison and HTML-regression cases.
- `docs/cli/roadmap.md` names the shipped comparison route, its closed selectors and output forms, and its read-only refusal behavior.

## References

- [BACKLOG.md](BACKLOG.md) — Read #402 for the comparison feature contract, evidence role, and scope limits.
- [ROADMAP_FORMAT.md](ROADMAP_FORMAT.md) — Read the fixed artifact inventory, version identity, and existing roadmap presentation rules.
- [plan_tool/roadmap_versions.py](plan_tool/roadmap_versions.py) — Read `VERSION_ARTIFACT_INVENTORY`, `load_accepted_version`, and stored-version loading ownership.
- [plan_tool/roadmap_view.py](plan_tool/roadmap_view.py) — Read `display_label` and existing read-only view ownership.
- [docs/cli/roadmap.md](docs/cli/roadmap.md) — Preserve the documented `--view html` output contract while adding comparison documentation.

## Applicable guardrails

- **The plan’s “## Step intent”, one model-free command:** Keep this step to CLI selection, dispatch, and presentation choice over steps 4 and 5; do not change comparison semantics.
- **The plan’s “## Scope guardrails”, read-only behavior:** The comparison branch in `plan_tool/cli/roadmap_cmd.py` must not enter any roadmap writer or lifecycle action.
- **The plan’s “## Scope guardrails”, raw evidence role:** Pass the complete patch output through the step 5 renderer without filtering, replacing, or treating cards as the evidence source.
- **The plan’s “## Scope guardrails”, stable identity:** Do not add CLI-side label, prose, or similarity matching for selected comparison results.
- **The plan’s “## Scope guardrails”, deterministic model-free output:** Do not invoke a model or add generated summaries, recommendations, or acceptance advice.
- **The plan’s “## Scope guardrails”, compatibility:** Keep ordinary views and lifecycle writers unchanged, especially the HTML output path.
- **The plan’s “## Out of scope”:** Do not add HTML comparison output, acceptance actions, candidate-policy changes, or comparisons outside the fixed roadmap inventory.

## Deferred

- **HTML or interactive comparison rendering** — The plan’s out-of-scope boundary leaves this for a separately evidenced follow-up after terminal and JSON behavior ships.
- **Additional snapshot families and lifecycle recovery selectors** — The closed selector contract must stay limited to the snapshot types the plan names.
