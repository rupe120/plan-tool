> **Auto-archived**: this plan was swept on 2026-11-05 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 8 — Update run-grade-only documentation and tracking

<!-- plan-tool:detail-format-version: 1 -->

## Summary

Update the live documentation to present run-grade detail as the only supported detail input for authoring, auditing, execution, and Jira export. Revise the format references, capability catalog, operator guides, architecture notes, and generated CLI pages while retaining the Jira story and paired developer-handoff contracts. Regenerate the affected `docs/cli/` pages from the parser after upstream selector removal, then verify documentation honesty and the full test suite. On green, remove BACKLOG #308’s IPPT-17 promotion stub; leave BACKLOG #149 blocked for a later run-grade re-baseline.

## Table of Contents

- [Summary](#summary) — The documentation and tracking outcome.
- [Table of Contents](#table-of-contents) — Links to each section.
- [Why](#why) — Why live documentation must match the retired reader surface.
- [Input](#input) — Upstream retirement results and retained output contracts.
- [Files (creates vs edits)](#files-creates-vs-edits) — Documentation and tracking files this step changes.
- [Implementation](#implementation) — The run-grade-only documentation sweep and preservation rules.
- [Tests](#tests) — Existing automated coverage and non-code verification.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — The CLI-reference source.
- [Applicable guardrails](#applicable-guardrails) — Boundaries on retirement documentation.
- [Deferred](#deferred) — Follow-up work that remains outside this step.

## Why

The code retirement from steps 2 through 7 removes Jira-grade selectors, readers, paths, and schema authority, but the live documentation still describes those routes as supported. That mismatch can direct operators to rejected commands, make a removed artifact look valid, and keep the promotion stub open after the implementation has shipped. This step makes the supported workflow clear without changing the separate Jira story or developer-handoff output contract.

## Input

- **Steps 2 through 7 retirement outcome:** Treat the removed `--grade` and `--detail-grade` selectors, `plan_tool/jira_grade.py`, and Jira-grade detail paths as absent. Document the surviving run-grade behavior from the landed parser and command help, not from earlier detail files.
- **Run-grade detail contract:** Read `plan_tool/detail.py:parse_detail_response`, `plan_tool/detail_artifacts.py:derive_detail_path`, and `plan_tool/detail_artifacts.py:require_supported_detail_format_version` for the enforced input contract.
- **Paired export contract:** Preserve `plan_tool/jira.py:capture_companion_export_input` and `plan_tool/jira.py:export_jira` as the source for Jira story and developer-handoff publication behavior.
- **Generated CLI contract:** Treat `plan_tool/cli_reference.py:render_reference` and the assembled parser as authoritative for `docs/cli/` content.

## Files (creates vs edits)

- **New files:** None.

- **Existing files (edits only):**
  - `plan-seeds/disable-jira-grade-detail-authoring.md` — Retire the superseded writer-only brief from active authoring inputs; preserve any needed provenance as explicitly historical evidence.
  - `.plan-tool/lessons/project.md` — Remove stale instructions to author, route, execute, or audit Jira-grade detail; preserve general lessons that still apply to the supported workflow.
  - `RUNBOOK.md` — Remove retired grade selection from the convergence procedure.
  - `docs/reference/contracts/process.md` — Remove selected-grade and legacy-reader claims while preserving the story/handoff output contract.
  - `docs/explanations/nondeterministic-plan-design.md` — Remove the live compact-detail capability claim; retain dated evidence supporting the design guidance.
  - `DETAIL_FORMAT.md` — Replace the two-grade description and compact-contract section with the canonical run-grade detail schema; retain source-of-truth and format-version guidance.
  - `JIRA_FORMAT.md` — State that Jira export always grounds stories and the handoff on declared run-grade detail; retain paired-export paths, provenance, publication, and story contracts.
  - `CAPABILITIES.md` — Remove retired Jira-grade surfaces and describe the retained run-grade behavior for authoring, completeness, execution, and export.
  - `CLAUDE.md` — Update live architecture and reference-document statements that name Jira-grade schema or selectors; retain warranted historical evidence only where it remains needed to interpret current rules.
  - `TESTING.md` — Update test guidance so it names retained run-grade and paired-export coverage without describing removed Jira-grade test lanes.
  - `integrations/shared/DIRECTIVES.md` — Remove live workflow guidance that instructs an operator to use retired detail-grade routes while preserving independently relevant process rules.
  - `docs/ARCHITECTURE.md` — Remove the retired grade-selection and `jira_grade.py` ownership descriptions; retain the Jira export and run-grade detail architecture.
  - `docs/how-to/use-cases.md` — Remove the compact Jira-grade use case and route users through the supported run-grade workflow.
  - `docs/how-to/pipeline/detail.md` — Describe run-grade authoring only and remove the retired-selector procedure.
  - `docs/how-to/pipeline/run.md` — Remove alternate-detail execution flow, grade-specific gates, and stale source-map entries; preserve normal run gates and missing-detail behavior.
  - `docs/how-to/pipeline/audit.md` — Remove Jira-grade audit and evidence-lane guidance while retaining run-grade audit, report, and convergence procedures.
  - `docs/cli/detail.md` — Regenerate after selector removal.
  - `docs/cli/run.md` — Regenerate after selector removal.
  - `docs/cli/jira.md` — Regenerate after selector removal.
  - `docs/cli/completeness-audit.md` — Regenerate after selector removal.
  - `docs/cli/convergence.md` — Regenerate after selector removal.
  - `docs/cli/gate-status.md` — Regenerate after selector removal.
  - `BACKLOG.md` — Remove the completed #308 / IPPT-17 promotion stub only after every retirement acceptance check passes; retain #149’s blocked re-baseline status.

## Implementation

- **Describe one supported detail input.** Make `DETAIL_FORMAT.md` name the run-grade file selected by `steps[].detail` as the only detail artifact contract. Keep its source-of-truth banner tied to the surviving enforcement anchors and retain the seven-section schema, canonical path, format marker, and pointer-resolution rules.

- **Keep Jira output separate from Jira-grade detail.** Update `JIRA_FORMAT.md` around “Which detail bundle grounds the export” so `plan_tool/jira.py:capture_companion_export_input` always captures supported run-grade detail. Preserve the paired-story and developer-handoff snapshot, destination, provenance, adoption, and publication rules; do not redesign either output.

- **Sweep live operator instructions by behavior, not only flag names.** Remove references to compact bundles, explicit grade selection, legacy readers, alternate preflights, and grade-specific audit evidence from the declared live guides. Replace them with the normal run-grade command only where a command example remains useful. Keep the existing run-grade audit, execution, and detail workflow ordering intact.

- **Sweep active authoring guidance too.** Include the declared seed and project lessons in the identifier and vocabulary searches. Retire the superseded writer-only seed from active inputs and remove stale lesson directives rather than allowing them to teach removed behavior. Preserve applicable general lessons and historical evidence; do not bulk-rewrite unrelated plans or archived seeds.

- **Keep archived evidence intact.** Do not rewrite historical evidence or fixtures merely because they mention the retired lane. In `CLAUDE.md` and `integrations/shared/DIRECTIVES.md`, retain dated or otherwise necessary historical context only when it still explains a current rule; remove stale live claims that present retired behavior as available.

- **Update capability and architecture ownership.** In `CAPABILITIES.md`, `docs/ARCHITECTURE.md`, and `CLAUDE.md`, remove `plan_tool/jira_grade.py` and grade-selector claims from live surfaces. Preserve the existing capability identifiers and mission-principle mappings unless the live surface itself no longer exists.

- **Regenerate, do not hand-maintain, CLI references.** Run `python -m plan_tool.cli_reference --write` after the parser changes from upstream steps are present. Review the generated diffs for the six declared pages and ensure removed selector options do not remain. Do not edit generated option tables manually.

- **Close tracking only after verification.** Remove BACKLOG #308’s promotion stub after the documentation sweep, generated-reference check, full suite, paired-export coverage, and retired-evidence rejection coverage pass. Keep BACKLOG #149 explicitly deferred because its compact-schema work needs a separate run-grade re-baseline.

## Tests

- `tests/cli/test_cli_reference.py::TestCliReference::test_every_generated_file_matches_disk` — Generated CLI references match the current parser after retired selector removal.
- `tests/test_capability_catalog.py::test_check_real_repo_catalog_is_honest` — `CAPABILITIES.md` names only real live command and module surfaces.
- `tests/test_jira.py::TestCompanionExportInput::test_companion_capture_preserves_plan_body_details_and_excerpts_after_source_changes` — The paired export continues to use one captured run-grade input snapshot.
- `tests/test_jira.py::TestPairedJiraExport::test_companion_publication_uses_one_captured_snapshot_and_complete_provenance_for_both_sources` — Story and handoff publication retain shared provenance.
- `tests/test_jira.py::test_run_grade_paired_export_rejects_unmatched_fence_before_target_write` — Invalid run-grade detail fails before paired-output publication.
- `tests/test_review_persistence.py::test_audit_snapshot_rejects_unmatched_archived_source_seed` — Invalid persisted evidence remains rejected rather than becoming usable provenance.
- `tests/test_review_persistence.py::test_sampler_checkpoint_lifecycles_are_rejected_by_each_final_evidence_reader` — Rejected evidence cannot certify a final audit result.
- `uv run pytest tests/ -q -n auto` — Full suite passes after the documentation and generated-reference changes.

### Verification (non-code step)

1. Run `rg` across the declared live documentation files for retired selector names, Jira-grade reader paths, and compact-contract claims; investigate each remaining match and retain it only when it is clearly historical evidence.
2. Run `python -m plan_tool.cli_reference --write`, then confirm the declared generated pages contain no retired detail-grade option.
3. Run the capability-catalog and generated-reference tests before the full suite.
4. Run the full pytest suite, including the paired-export and evidence-rejection coverage named above.
5. Confirm BACKLOG #308 no longer appears after all checks pass and BACKLOG #149 remains marked for re-baselining.

## Acceptance criteria

- `DETAIL_FORMAT.md` describes only the enforced run-grade detail schema and names no supported Jira-grade artifact, selector, reader, or path.
- `JIRA_FORMAT.md` states that stories and developer handoffs use declared run-grade detail while preserving their current output and publication contracts.
- `CAPABILITIES.md`, `CLAUDE.md`, `TESTING.md`, `integrations/shared/DIRECTIVES.md`, `docs/ARCHITECTURE.md`, and the declared operator guides contain no live instruction to select Jira-grade detail.
- `python -m plan_tool.cli_reference --write` produces current versions of all declared CLI pages, with no retired grade selector shown.
- Existing paired-export tests and evidence-rejection tests pass alongside `uv run pytest tests/ -q -n auto`.
- BACKLOG #308’s IPPT-17 promotion stub is removed only after the preceding checks pass.
- BACKLOG #149 remains deferred and identifies its required run-grade re-baseline.

## References

- [argparse — Parser for command-line options, arguments and subcommands](https://docs.python.org/3.13/library/argparse.html) — Use when confirming that generated help reflects removed option registration.

## Applicable guardrails

- **The plan’s “## Plan intent”** — Keep Jira export grounded on run-grade detail without creating another detail input route.
- **The plan’s “## Scope guardrails”** — Complete the retirement without adding compatibility readers, migrations, replacement grades, or unrelated cleanup.
- **The plan’s “## Out of scope”** — Preserve Jira story and developer-handoff rendering, destinations, provenance, and publication behavior.
- **The plan’s “## Out of scope”** — Leave archived historical evidence unchanged outside the minimum live-reference corrections.

## Deferred

- BACKLOG #149 compact-detail re-baseline — Keep deferred until it is re-scoped around a run-grade-owned schema after this retirement.
