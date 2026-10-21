> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 3 — Document the committed receipt path, replace stale receipt no-Git claims, and keep impact-analysis no-Git claims unchanged

## Summary

Update the six roadmap-facing documents to describe escalation receipts as shared evidence committed at their exact final path. Keep the receipt command’s existing non-backend, non-canonical, and non-stage boundaries clear while accurately noting its narrow Git effect. Preserve impact-analysis documentation as local evidence with no Git operation. On green, operators can find the receipt path, understand when Git changes, and distinguish receipts from impact analyses.

## Table of Contents

- [Summary](#summary) — The documentation outcome and visible behavior.
- [Table of Contents](#table-of-contents) — Links to every detail section.
- [Why](#why) — The stale receipt claim this step corrects.
- [Input](#input) — The landed receipt lifecycle and generated CLI reference contract.
- [Files (creates vs edits)](#files-creates-vs-edits) — The six documentation files this step edits.
- [Implementation](#implementation) — The receipt-versus-analysis wording and consistency rules.
- [Tests](#tests) — Non-code verification for generated and contract-backed documentation.
- [Acceptance criteria](#acceptance-criteria) — Reviewable documentation outcomes.
- [References](#references) — Git behavior underlying the operator guidance.
- [Applicable guardrails](#applicable-guardrails) — Scope limits for this documentation-only step.
- [Deferred](#deferred) — Lifecycle and contract work owned by step 2.

## Why

The current receipt guidance says creation does not change Git state, but step 2 makes a successful receipt shared only after its exact final is committed. That contradiction can cause an operator to miss a deliberate narrow commit or misunderstand why a receipt is not trusted yet. Impact analyses remain local runtime evidence, so their no-Git guidance must not be changed while correcting the receipt-only claim.

## Input

- **Step 2 shared receipt lifecycle:** Read the landed receipt success and failure behavior from `plan_tool/roadmap_escalation_run.py:run_roadmap_escalation_receipt` and `plan_tool/roadmap_escalation_run.py:EscalationRunResult`. Describe the observable shared-result boundary without re-documenting its implementation.

- **Evidence namespaces:** Use `plan_tool/roadmap_evidence_store.py:EvidenceNamespace`, `plan_tool/roadmap_evidence_store.py:namespace_relative_components`, and the architecture’s `<roadmap-dir>` notation. The receipt location is `<roadmap-dir>/.plan-tool/evidence/escalations/<RECEIPT_FINAL>`; do not present the impact-analysis namespace as committed.

- **Generated CLI reference:** Treat `plan_tool/cli/roadmap_cmd.py:register` as the source for `docs/cli/roadmap.md`. Regenerate the reference through `plan_tool/cli_reference.py:render_reference` after step 2 lands its command help.

## Files (creates vs edits)

- **New files:** None.

- **Existing files (edits only):**
  - `CAPABILITIES.md` — Update the `## Architecture roadmap` receipt capability text with the committed receipt-final boundary and retain the impact-analysis local-evidence boundary.
  - `README.md` — Update the roadmap command summary and the structural-feedback walkthrough to name the receipt path and its receipt-only Git commit.
  - `RUNBOOK.md` — Correct `### Record structural feedback without revising the roadmap` so operator guidance explains when receipt creation commits and what remains unchanged.
  - `docs/ARCHITECTURE.md` — Update `## Roadmap`’s structural-escalation receipt layer to distinguish committed receipt evidence from local impact-analysis evidence.
  - `docs/how-to/roadmap.md` — Update `### Record structural feedback, then analyze its current route` with the committed receipt path and the narrow Git boundary.
  - `docs/cli/roadmap.md` — Regenerate the `--escalate-feedback` option description from the landed `plan_tool/cli/roadmap_cmd.py:register` help text.

## Implementation

- **Document the receipt’s shared path and admission point.** State consistently that an escalation receipt final lives at `<roadmap-dir>/.plan-tool/evidence/escalations/<RECEIPT_FINAL>` and becomes trusted shared evidence only after the receipt command commits that exact final to `HEAD`.

- **Describe the narrow Git effect.** Replace receipt-creation claims that it changes no Git state with wording that the command commits only its exact receipt final. Keep the existing boundaries around backend calls, canonical roadmap artifacts, feedback state, seed state, and stage runs.

- **Preserve user-owned Git state.** Explain that receipt creation does not take unrelated staged or unstaged work into its commit. Do not broaden this into general Git workflow guidance or promise behavior beyond the receipt-only path supplied by step 2.

- **Keep impact analyses explicitly local.** Retain the no-Git statements for `--analyze-escalation` in `README.md` and `docs/ARCHITECTURE.md`. Keep `CAPABILITIES.md`, `RUNBOOK.md`, and `docs/how-to/roadmap.md` clear that impact-analysis publication remains separate local evidence and that its views remain read-only and log-free.

- **Keep the command reference generated.** Regenerate `docs/cli/roadmap.md` from `plan_tool/cli_reference.py:render_reference`; do not hand-edit generated option prose. The `--escalate-feedback` row must match the landed parser help from `plan_tool/cli/roadmap_cmd.py:register`.

- **Keep ownership boundaries intact.** Use these documents for operator-facing lifecycle guidance. Leave receipt schema, run-log fields, storage representation, and lifecycle code to the modules and reference documents step 2 updates.

## Tests

### Verification (non-code step)

1. `tests/cli/test_cli_reference.py::TestCliReferenceDrift::test_every_generated_file_matches_disk` — Confirms regenerated `docs/cli/roadmap.md` exactly matches the current parser reference.

2. `tests/test_capability_catalog.py::test_check_real_repo_catalog_is_honest` — Confirms `CAPABILITIES.md` remains valid against registered command surfaces and MISSION principles.

3. `tests/test_roadmap_format.py::test_architecture_reference_assigns_baseline_publication_to_writers_and_admission_to_readers` — Confirms architecture guidance still preserves the established roadmap evidence boundary.

4. Receipt documentation review — Verify every edited receipt section names `<roadmap-dir>/.plan-tool/evidence/escalations/<RECEIPT_FINAL>`, the `HEAD` admission boundary, and the receipt-only commit.

5. Analysis documentation review — Verify the impact-analysis no-Git statements in `README.md` and `docs/ARCHITECTURE.md` remain unchanged.

6. Link review — Verify each edited local Markdown link still resolves to its referenced roadmap command or format section.

## Acceptance criteria

- Every edited receipt guide identifies `<roadmap-dir>/.plan-tool/evidence/escalations/<RECEIPT_FINAL>` as the committed receipt location.

- Receipt creation guidance states that trusted success requires the exact receipt final in `HEAD`.

- Receipt guidance states that the command commits only its receipt final and preserves unrelated staged and unstaged work.

- No receipt-creation section in the declared files states that receipt creation changes no Git state.

- Impact-analysis no-Git guidance in `README.md` and `docs/ARCHITECTURE.md` remains unchanged.

- `docs/cli/roadmap.md` matches output from `plan_tool/cli_reference.py:render_reference`.

- `tests/cli/test_cli_reference.py`, `tests/test_capability_catalog.py`, and `tests/test_roadmap_format.py` pass.

## References

- [Git — git-commit Documentationhttps: — Confirm the path-limited commit behavior the operator guidance describes.

- [Git — git-status Documentationhttps: — Verify the distinction between the committed receipt and unrelated working-tree state.

- [Git — gitignore Documentationhttps: — Confirm why impact-analysis evidence remains local while escalation receipts are available for commit.

## Applicable guardrails

- **The plan’s `## Plan intent`, shared receipt authority** — Document only the receipt persistence needed to make shared evidence durable, while preserving the user-state boundary.

- **The plan’s `## Step intent`, operator and maintainer guidance** — Keep this step focused on accurate path and Git-state documentation.

- **The plan’s `## Out of scope`, general commit framework** — Do not add broader Git workflow documentation or imply a reusable commit system.

- **The plan’s `## Out of scope`, new CLI surface** — Document the existing receipt command only; do not add flags, prompts, or alternate commands.

- **The plan’s `## Out of scope`, roadmap evidence storage** — Describe the existing namespaces without changing their representation or claiming new storage behavior.

## Deferred

- Receipt lifecycle, evidence admission, run-log contracts, and related test changes — Step 2 owns the implementation and contract updates; this step presents their landed operator-facing behavior.

- Documentation outside the six declared files — Keep unrelated roadmap guides unchanged unless a later reconcile identifies a specific stale receipt claim.
