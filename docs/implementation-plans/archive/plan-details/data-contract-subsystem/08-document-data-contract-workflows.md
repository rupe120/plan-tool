> **Auto-archived**: this plan was swept on 2026-07-07 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 8 — Document Data Contract Workflows And Refresh CLI Docs

## Summary

This step updates the human-facing documentation for the data-contract subsystem delivered by steps 3-6. The main edits are `DATA_CONTRACT.md`, `RUNBOOK.md`, `README.md`, `PLAN_FORMAT.md`, `DETAIL_FORMAT.md`, and the generated CLI reference under `docs/cli/`. The key design decision is to document observable operator workflow and authoring contracts, not re-state implementation details owned by earlier steps. On green, users can find how `data-contract` findings are reported, how `plan-tool data-contract-apply` replays fresh structured contract-document payloads, how `## Input` contract references work, and the generated CLI docs include `docs/cli/data-contract-apply.md`.

## Table of Contents

- [Summary](#summary) — The docs this step refreshes and the expected end state.
- [Why](#why) — Why the shipped workflow needs one clear documentation pass.
- [Files (creates vs edits)](#files-creates-vs-edits) — The exact docs touched by this non-code step.
- [Implementation](#implementation) — The documentation contract, generated CLI refresh, and constraints.
- [Tests](#tests) — The drift and link checks that cover this docs-only change.
- [Acceptance criteria](#acceptance-criteria) — Concrete checks a reviewer can run.
- [References](#references) — Primary references for Markdown and generated CLI docs.
- [Deferred](#deferred) — Work intentionally left outside this documentation step.

## Why

Steps 3-6 add a new saved-finding workflow, a new apply command, and conditional `## Input` contract sections, but the current user docs only describe generic completeness audits and conceptual apply. Without a focused docs pass, operators will not know which `data-contract` findings are applyable contract-document drift versus non-applyable plan/detail `## Input` findings, authors will not know when and how to cite persisted fields in `## Input`, and the generated `docs/cli/` reference will fail drift checks once `data-contract-apply` exists in the parser.

## Files (creates vs edits)

- **New files:**
  - `docs/cli/data-contract-apply.md` — Generated reference for `plan-tool data-contract-apply`, created by `python -m plan_tool.cli_reference --write` after step 3 has registered the command.

- **Existing files (edits only):**
  - `DATA_CONTRACT.md` — Add the operator-facing data-contract drift and apply workflow, anchored near the source-of-truth note, `SavedReview` sidecar section, or `CLI JSON payloads` section as fits the final upstream implementation.
  - `RUNBOOK.md` — Add `data-contract-apply` to the quick reference and completeness workflow, especially `RUNBOOK.md:Quick reference`, `RUNBOOK.md:Command families and ordering`, and `RUNBOOK.md:Workflow: completeness checks`.
  - `README.md` — Update the CLI cheat sheet, audit workflow, and completeness gates so the new command and `data-contract` findings are discoverable from `README.md:CLI usage`, `README.md:Common workflows`, and `README.md:Completeness gates`.
  - `PLAN_FORMAT.md` — Document the conditional `## Input` plan-body section from step 5 and the explicit contract-reference/code-location check from step 6 under `PLAN_FORMAT.md:Body sections (advisory-checked)`.
  - `DETAIL_FORMAT.md` — Document `## Input` as an optional detail H2 for contract-consuming steps and explain that explicit data-contract references in that section are checked against HEAD.
  - `docs/cli/README.md` — Regenerated command index; do not hand-edit.
  - `docs/cli/completeness-audit.md` — Regenerated help after upstream command/help changes; do not hand-edit.
  - `docs/cli/completeness-apply.md` — Regenerated help after upstream command/help changes; do not hand-edit.

## Implementation

- **Foundational logic: data-contract workflow documentation.** Document the user-visible rule: `completeness-audit` can emit saved `source="data-contract"` findings, and `data-contract-apply` replays only fresh, structured `DATA_CONTRACT.md` drift payloads rather than re-running detection or inferring edits from prose. The docs should cite the outcome of steps 3 and 4 instead of re-specifying their internals.

- **Keep code as source of truth in `DATA_CONTRACT.md`.** Preserve the opening source-of-truth rule in `DATA_CONTRACT.md`: the tool does not load the markdown at runtime. Add prose that explains `data-contract` recommendations are persisted as normal `Recommendation` records inside the existing `SavedReview` sidecar, applyable contract-document findings also have structured payload/fingerprint data, and `data-contract-apply` annotates the saved audit through the same saved-review workflow. Do not imply a saved-review schema change unless an earlier step actually changed `SavedReview`.

- **Document the operator path in `RUNBOOK.md`.** Update `RUNBOOK.md:Quick reference` and `RUNBOOK.md:Workflow: completeness checks` so an operator sees the full path: run `plan-tool completeness-audit <name>`, inspect `data-contract` drift in the grouped report or `--json`, run `plan-tool data-contract-apply <name>` to walk fresh saved `DATA_CONTRACT.md` drift findings, then re-run the audit to verify they dropped off. Also document that stale `## Input` references are plan/detail repair findings, and that stale payload fingerprints require rerunning the audit before applying. If adding a new subsection under `RUNBOOK.md:Workflow: completeness checks`, keep it near `RUNBOOK.md:Address conceptual gaps (completeness-apply)` rather than creating a new top-level chapter.

- **Keep `completeness-apply` distinct.** In `RUNBOOK.md` and `README.md`, make the split clear: `completeness-apply` remains the conceptual gap workflow, while `data-contract-apply` is the documentation-repair workflow for saved `DATA_CONTRACT.md` findings with structured payloads. If step 4 also routes data-contract findings through serial completeness replay, describe that as redirect/report behavior without making `completeness-apply --jobs` sound like a data-contract batch mode.

- **Refresh `README.md` as the short guide.** Add `data-contract-apply` to `README.md:CLI usage`, include `<name>` in `README.md:Placeholders` for the new command, and update `README.md:Completeness gates` so the high-level command list names data-contract drift. Keep this concise; detailed recovery and sequencing belong in `RUNBOOK.md`.

- **Update authoring-format docs for `## Input`.** In `PLAN_FORMAT.md:Body sections (advisory-checked)`, document `## Input` as a conditional section from step 5 and explain that it records upstream artifacts, persisted contracts, sidecars, fields, and HEAD code-location anchors the plan consumes. In `DETAIL_FORMAT.md:Section schema` and `DETAIL_FORMAT.md:Field semantics`, add `## Input` as an optional H2 for contract-consuming steps and state the same contract-reference rule from step 6: explicit registered-owner references such as `SavedReview.recommendations` must be paired with anchors such as `plan_tool/review_persistence.py:SavedReview`, both are checked against HEAD, and ordinary commands and backticked prose are not treated as contract references.

- **Regenerate CLI docs, do not hand-edit them.** Once step 3 has added the parser entry for `data-contract-apply`, run `python -m plan_tool.cli_reference --write`. The generator is `plan_tool/cli_reference.py:write_reference`, and drift is checked by `tests/cli/test_cli_reference.py:TestCliReferenceDrift`. Review the resulting `docs/cli/data-contract-apply.md`, `docs/cli/README.md`, `docs/cli/completeness-audit.md`, and `docs/cli/completeness-apply.md` for accuracy, but make wording fixes in the parser help owned by step 3 or upstream command docs, not by manually editing generated files.

- **Respect generated-doc boundaries.** `docs/cli/README.md`, `docs/cli/completeness-audit.md`, `docs/cli/completeness-apply.md`, and `docs/cli/data-contract-apply.md` must match `plan_tool/cli_reference.py:render_reference`. Handwritten narrative belongs in `README.md` and `RUNBOOK.md`.

- **Avoid restating upstream mechanisms.** Reference step 3 for the `data-contract-apply` command, step 4 for saved-walk routing, step 5 for conditional `## Input`, and step 6 for HEAD-backed contract-reference validation. This step should not introduce new behavior, schema fields, parser flags, or source constants.

## Tests

- `tests/cli/test_cli_reference.py::TestCliReferenceDrift::test_every_generated_file_matches_disk` — regenerated `docs/cli/` files match `plan_tool/cli_reference.py:render_reference`.
- `tests/cli/test_cli_reference.py::TestCliReferenceDrift::test_no_orphan_reference_files` — `docs/cli/data-contract-apply.md` is generated by the parser and not an orphan.
- `tests/cli/test_cli_reference.py::TestCliReferenceDrift::test_index_links_every_command` — `docs/cli/README.md` links the new command reference.
- `tests/test_data_contract.py` data-contract doc checks — `DATA_CONTRACT.md` still names the registered persisted fields, aliases, schema constants, and data-contract workflow facts required by steps 1-6.

### Verification (non-code step)

This is a non-code step. Verify the docs and generated artifacts directly:

- Run `python -m plan_tool.cli_reference --write` after upstream command registration.
- Run `uv run pytest tests/cli/test_cli_reference.py tests/test_data_contract.py tests/test_create.py tests/test_detail.py`.
- Check `docs/cli/data-contract-apply.md` exists and starts with ``# `plan-tool data-contract-apply` ``.
- Check every `docs/cli/*.md` edit came from the generator, not manual prose edits.
- Manually confirm `PLAN_FORMAT.md` and `DETAIL_FORMAT.md` agree with the conditional `## Input` contract from step 5 and the HEAD-checked contract-reference/code-location rule from step 6.
- Check all new links in `README.md`, `RUNBOOK.md`, `PLAN_FORMAT.md`, `DETAIL_FORMAT.md`, and `DATA_CONTRACT.md` point to existing headings or files.

## Acceptance criteria

- `DATA_CONTRACT.md` explains that `data-contract` findings are saved as normal `Recommendation` records in completeness sidecars, applyable contract-document findings have structured payload/fingerprint data, and apply uses the saved-audit workflow without saying the markdown is loaded at runtime.
- `RUNBOOK.md` shows the audit/apply/re-audit path for data-contract drift, distinguishes `data-contract-apply` from `completeness-apply`, and explains freshness-blocked applies plus non-applyable stale `## Input` findings.
- `README.md` includes `plan-tool data-contract-apply <name>` in the CLI usage or audit workflow and names it in the completeness-gate overview.
- `PLAN_FORMAT.md` documents `## Input` as a conditional plan body section and describes the field-plus-code-anchor requirement.
- `DETAIL_FORMAT.md` documents `## Input` as an optional detail H2 for contract-consuming steps and describes HEAD-checked explicit contract references with required code-location anchors.
- `python -m plan_tool.cli_reference --write` creates `docs/cli/data-contract-apply.md` and updates `docs/cli/README.md`, `docs/cli/completeness-audit.md`, and `docs/cli/completeness-apply.md` as needed.
- `uv run pytest tests/cli/test_cli_reference.py` passes with no generated CLI reference drift.
- A grep for `data-contract-apply` finds the new command in `README.md`, `RUNBOOK.md`, `docs/cli/README.md`, and `docs/cli/data-contract-apply.md`.

## References

- [CommonMark Specification](https://spec.commonmark.org/) — Use for portable Markdown heading and link behavior when adding or checking doc sections.
- [Python argparse](https://docs.python.org/3/library/argparse.html) — Use for understanding the parser help surface that `plan_tool/cli_reference.py` renders into `docs/cli/`.

## Deferred

- `BACKLOG.md` reconciliation — Step 9 owns retiring or reshaping the shipped backlog entry after the docs are updated.
- Production behavior changes — Steps 3-6 own command registration, saved-walk routing, `## Input` generation, and HEAD-backed validation.
- New data-contract schema fields — This step documents existing outcomes only; schema changes need a plan-level decision and code step.
