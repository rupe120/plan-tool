> **Auto-archived**: this plan was swept on 2026-08-18 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 5 — Document local feedback revision and the explicit broad-reentry boundaries

## Summary

Document the new bounded feedback route across the roadmap reference, operator guides, architecture description, capability catalog, and generated CLI reference. Make `--revise-feedback` the documented choice for one eligible same-artifact row request, while preserving `--from-stage` as the existing broad revision route. The main decision is a clear route boundary: local revision changes one selected row presentation and one feedback response; broader work stays broad. Green means every operator-facing entry point gives the same command choice and the generated CLI reference matches the parser.

## Table of Contents

- [Summary](#summary) — Scope, main decision, and green result.
- [Table of Contents](#table-of-contents) — Links to every section in this detail.
- [Why](#why) — Why the existing broad-only guidance becomes misleading.
- [Input](#input) — Contracts and existing documentation this step reads.
- [Files (creates vs edits)](#files-creates-vs-edits) — Documentation and drift-guard edits.
- [Implementation](#implementation) — Route-selection guidance and each document’s ownership.
- [Tests](#tests) — Documentation and generated-reference checks.
- [Acceptance criteria](#acceptance-criteria) — Reviewable documentation outcomes.
- [References](#references) — CLI-reference source material.
- [Applicable guardrails](#applicable-guardrails) — Plan boundaries this documentation must preserve.
- [Deferred](#deferred) — Work left outside this documentation step.

## Why

Current roadmap guidance tells an operator to re-enter an artifact’s own stage for any feedback. `plan_tool/roadmap.py:run_roadmap` treats that as a broad staged rewrite: `--from-stage` re-gates lower stages and rewrites the selected stage and everything above it. After step 4 lands, routine same-artifact feedback has a safer bounded command, so the docs must make that choice clear without suggesting that the new command replaces broad structural revision or recovery workflows.

## Input

- **Existing broad revision:** Use `plan_tool/roadmap.py:run_roadmap`, `plan_tool/roadmap.py:STAGES`, and `plan_tool/cli/roadmap_cmd.py:cmd_roadmap` as the source for the unchanged `--from-stage` behavior and stage artifact tokens.

- **Feedback schema:** Keep the lifecycle described by `plan_tool/roadmap_artifacts.py:FeedbackRow`, `FeedbackTarget`, and `FeedbackState`. The reviewer still owns closing, reopening, and deferring feedback.

- **Steps 1–4:** Read the landed local-revision contract and command surface before documenting names or limits. The shipped code and generated CLI help win over wording in earlier detail files if they differ.

- **Generated CLI reference:** `plan_tool.cli_reference.render_reference` owns `docs/cli/roadmap.md`; its output, not a hand-maintained option table, is the command reference.

## Files (creates vs edits)

- **New files:**

  - None.

- **Existing files (edits only):**

  - `ROADMAP_FORMAT.md` — Add route-selection guidance beside the review lifecycle and keep the format contract as the source for local eligibility and preservation limits.

  - `README.md` — Update the roadmap cheat sheet and the `### 0. roadmap` workflow so routine local feedback and broad re-entry have distinct commands and outcomes.

  - `docs/cli/roadmap.md` — Regenerate the reference after step 4 changes `plan_tool/cli/roadmap_cmd.py:register`.

  - `docs/ARCHITECTURE.md` — Extend `## Roadmap` with the local runner’s bounded role and its separation from `plan_tool/roadmap.py:run_roadmap`.

  - `docs/ROADMAP_WALKTHROUGH.md` — Rework `## 5. Ask for a revision with feedback` into a practical local-first route guide followed by broad-reentry cases.

  - `CAPABILITIES.md` — Update `## Architecture roadmap` to include the landed local-revision modules and describe the two revision routes without creating a second capability or subcommand.

  - `tests/test_roadmap_format.py` — Extend the existing documentation drift guard for the local-route wording and examples.

## Implementation

- **Foundational logic: document route selection.** State that `plan-tool roadmap <slug> --revise-feedback <artifact>:<feedback-id>` is for one eligible, same-artifact `open` feedback row that targets one live design row. Document the accepted artifact tokens from the landed `plan_tool/roadmap.py:STAGES` table, not a separately maintained list.

- **Describe the local result precisely.** Explain that the local command can change only the selected target row’s allowed presentation field and the selected feedback row’s response state. It preserves every other row, relation, identifier, feedback row, removal, and prose body in the selected artifact.

- **State local failure and seed consequences accurately.** Explain that accepted local work invalidates tracked seed state before backend work, makes one backend request, and does not silently retry or refresh seed content. Direct operators to the existing explicit seed-refresh guidance after review; do not describe a hidden local recovery path.

- **Draw the broad boundary once and reuse it.** Route artifact-wide requests, work requiring more than one artifact, structural or relationship changes, prose rewrites, and ordinary broad re-entry to `--from-stage`. Keep its existing meaning: lower stages are read and re-gated, while the selected stage and later stages are rewritten.

- **Correct stale broad wording.** Update `README.md`’s roadmap re-entry explanation so it does not claim that existing design-row identifiers are generally unstable across a revision while other documentation and `plan_tool/roadmap_gates.py:check_design_row_continuity` describe their retention. Keep the distinction between preserved review data and broad rewriting of unprotected prose.

- **Keep format and workflow roles separate.** Use `ROADMAP_FORMAT.md` for eligibility, local preservation, and the route boundary; use `docs/ROADMAP_WALKTHROUGH.md` for the operator sequence and examples. Do not duplicate the step-1 field table or operation JSON contract in every guide.

- **Keep the command reference generated.** Regenerate `docs/cli/roadmap.md` with `python -m plan_tool.cli_reference --write` after the parser lands. Review the resulting `--revise-feedback` usage and exclusivity wording; do not hand-edit generated option text.

- **Keep architecture and capability descriptions current.** In `docs/ARCHITECTURE.md`, describe the local modules as a bounded path beside the existing broad orchestrator. In `CAPABILITIES.md`, retain `roadmap` as the capability surface and add the landed local module paths; a flag does not warrant a new command or capability id.

- **Preserve reviewer authority.** Every document must continue to say that `awaiting-review`, reopening, deferral, and closure are reviewer actions. The local command proposes a response; it does not accept feedback for the reviewer.

## Tests

- `tests/test_roadmap_format.py::test_local_revision_reference_matches_the_contract_module` — Confirms the documented selector, artifact tokens, field table, and operation example match the landed local contract.

- `tests/test_roadmap_format.py::test_local_feedback_route_reference_marks_broad_reentry_boundaries` — Confirms the format guide presents local eligibility and directs broader work to `--from-stage`.

- `tests/cli/test_cli_reference.py::TestCliReferenceDrift::test_every_generated_file_matches_disk` — Confirms `docs/cli/roadmap.md` matches the live argparse parser.

- `tests/test_capability_catalog.py::test_check_real_repo_catalog_is_honest` — Confirms the updated roadmap capability cites only registered or existing surfaces.

### Verification (non-code step)

1. Run `python -m plan_tool.cli_reference --write` and confirm the intended generated diff is `docs/cli/roadmap.md`.

2. Check every local command example against `plan_tool/cli/roadmap_cmd.py:register` after step 4 lands.

3. Check links and section references in `README.md`, `ROADMAP_FORMAT.md`, and `docs/ROADMAP_WALKTHROUGH.md` after adding the route guidance.

4. Run `uv run pytest tests/test_roadmap_format.py tests/cli/test_cli_reference.py tests/test_capability_catalog.py -q`.

## Acceptance criteria

- `ROADMAP_FORMAT.md`, `README.md`, and `docs/ROADMAP_WALKTHROUGH.md` present `--revise-feedback` as the routine route for one eligible same-artifact feedback request.

- The same documents direct requests beyond that bounded contract to the existing `--from-stage` workflow and describe its rewrite boundary correctly.

- Local-route documentation states that unselected canonical content remains unchanged and that seed state becomes invalidated before the backend request.

- No documentation presents local revision as a retrying, cross-artifact, structural, prose-editing, or automatic seed-refresh workflow.

- `docs/cli/roadmap.md` is generated from the landed parser and includes the final `--revise-feedback` syntax and help text.

- `docs/ARCHITECTURE.md` and `CAPABILITIES.md` describe the landed local modules without registering a separate subcommand or capability.

- The listed documentation, generated-reference, and capability-catalog tests pass.

## References

- [Python argparse documentation](https://docs.python.org/3.13/library/argparse.html) — Use it to verify that the generated CLI reference reflects the final option and exclusivity surface.

## Applicable guardrails

- **The plan’s “## Plan intent”, bounded local revision:** Document the local command as preserving unselected canonical content and using the established seed-state lifecycle.

- **The plan’s “## Step intent”, routine versus broad feedback:** Make the local-first operator choice clear while retaining broad re-entry for work outside the routine contract.

- **The plan’s “## Out of scope”, excluded revision shapes:** Do not document local revision as an alternative for work that the plan keeps on broader surfaces.

- **The plan’s “## Out of scope”, recovery and seed behavior:** Keep recovery and seed guidance on their existing explicit workflows; do not promise new automatic behavior.

## Deferred

- Changes to `plan_tool/roadmap.py:run_roadmap` or its broad retry and overwrite rules — Steps 1–4 leave that path separate; this step only documents its boundary.

- Local response parsing, merging, publication, and run-log implementation — Steps 1–4 own those contracts; this step reports their landed behavior.

- A persistent local-revision recovery workflow — Requires a separate plan-level design before documentation can promise one.
