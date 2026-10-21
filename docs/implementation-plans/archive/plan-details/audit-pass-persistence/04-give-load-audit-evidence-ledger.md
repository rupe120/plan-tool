> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 4 — Make the audit evidence ledger recognize sampler checkpoint lifecycles

## Summary

Extend `plan_tool/convergence_diagnosis.py:load_audit_evidence_ledger` to load and display step 1’s stable sampler checkpoint as diagnostic evidence. Keep its discovery separate from timestamped completeness report pairs, and give its standalone ledger row the explicit `in-progress-checkpoint` or `terminal-sampler-residue` state. Preserve every existing final-evidence gate in `plan_tool/completeness_report.py`, `plan_tool/cli/review_cmd.py`, `plan_tool/cli/data_contract_cmd.py`, and `plan_tool/cli/completeness_phases.py`. Green means either lifecycle is visible in the ledger but cannot enter reuse, apply, walk, or convergence history.

## Table of Contents

- [Summary](#summary) — The completed behavior and its visible result.
- [Table of Contents](#table-of-contents) — Links to each section.
- [Why](#why) — Why the stable checkpoint needs a diagnostic-only ledger row.
- [Input](#input) — The persisted role and artifact contracts supplied by earlier steps.
- [Files (creates vs edits)](#files-creates-vs-edits) — The ledger change and reader verification targets.
- [Implementation](#implementation) — Discovery, classification, and fail-closed reader rules.
- [Tests](#tests) — Focused coverage for visibility and reader rejection.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — JSON loading guidance for the saved artifact reader.
- [Applicable guardrails](#applicable-guardrails) — Scope limits that keep the checkpoint diagnostic-only.

## Why

`plan_tool/convergence_diagnosis.py:load_audit_evidence_ledger` currently loads only timestamped `COMPLETENESS_SIDECAR_SUFFIX` artifacts before pairing them with reports, so step 1’s stable checkpoint cannot reach its saved-review cache or ledger row. The checkpoint must remain visible to an operator as incomplete diagnostic evidence, but it must keep failing the existing ordinary-final role checks that protect reuse, apply, saved-review walks, data-contract application, and convergence diagnosis.

## Input

- **Step 1 role and path contract** — Step 1 supplies the stable sampler checkpoint path, its positive lifecycle discriminator, and its fail-closed `SavedReview` loading behavior. Read that landed contract rather than duplicating its persistence or schema rules.

- **Step 2 lifecycle contract** — Step 2 writes the stable artifact only at completed continuing-pass boundaries and changes its role before terminal cleanup. Treat the on-disk role as the only evidence of whether a residue is resumable.

- **Ledger snapshot contract** — `plan_tool/convergence_diagnosis.py:_artifact_snapshot_for_plan`, `load_saved_reviews`, and `load_audit_evidence_ledger` must continue to use one caller-supplied reports-directory snapshot and reject a cache from another plan.

- **Raw listing contract** — `plan_tool/review_persistence.py:list_saved_reviews` returns every JSON file in the reports directory. Downstream readers, not the listing function, own final-evidence eligibility.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `plan_tool/convergence_diagnosis.py` — Load the stable checkpoint into the ledger cache, discover it as a standalone artifact, and add the two sampler lifecycle ledger states.
  - `plan_tool/completeness_report.py` — Keep `is_reusable_audit_sidecar` and `resolve_reusable_audit` as ordinary-final-only readers; use them in the shared rejection coverage.
  - `plan_tool/cli/review_cmd.py` — Keep `_direct_walk_role_ineligibility`, `_review_reuse_ineligibility`, and `cmd_review_walk` fail-closed; use them in the shared rejection coverage.
  - `plan_tool/cli/data_contract_cmd.py` — Keep `_newest_saved_completeness_with_contract_payload` and `cmd_data_contract_apply` final-qualified-only; use them in the shared rejection coverage.
  - `plan_tool/cli/completeness_phases.py` — Keep `_saved_audit_revision_is_current` as an ordinary-final gate; use it in the shared rejection coverage.
  - `tests/test_convergence_diagnosis.py` — Add ledger discovery, state, ordering, and malformed-artifact coverage.
  - `tests/test_review_persistence.py` — Add the parameterized final-reader rejection matrix, including the direct saved-review walk.

## Implementation

- **Make the stable checkpoint a third artifact shape.** In `plan_tool/convergence_diagnosis.py:load_audit_evidence_ledger`, continue pairing timestamped completeness Markdown and JSON artifacts, then add a separate branch for step 1’s stable checkpoint path. It must produce one standalone row with a `sidecar_path`, no `report_path`, and the existing unknown filename-time behavior for a non-timestamped filename.

- **Load before classifying.** Extend `plan_tool/convergence_diagnosis.py:load_saved_reviews` so its completeness-only cache includes the stable checkpoint as well as `COMPLETENESS_SIDECAR_SUFFIX` files. This must happen before `load_audit_evidence_ledger` validates cache coverage, including when `plan_tool/cli/convergence_cmd.py:cmd_convergence` passes one snapshot and one cache to both history and ledger readers.

- **Name only a valid sampler artifact.** Add `in-progress-checkpoint` and `terminal-sampler-residue` states to `AUDIT_EVIDENCE_STATES`. Assign the first only to the step-1 `in-progress` lifecycle and the second only to its published non-resumable lifecycle. A filename alone is not proof: unreadable, wrong-kind, unknown-role, or otherwise invalid stable artifacts retain the existing fail-closed malformed or unknown treatment.

- **Keep pre-apply and sampler states distinct.** A timestamped pre-apply checkpoint must remain `checkpoint`. The stable sampler artifact must not be called a pre-apply checkpoint in `AuditEvidenceRow.state`, `render_audit_evidence_ledger`, or its next-action output.

- **Preserve ledger-only behavior.** `plan_tool/convergence_diagnosis.py:_is_final_report_role` must continue to exclude the new role from `load_report_history`; the ledger is the only reader in this step that classifies it positively. Do not consult live plan, code, freshness, or resumability state while rendering saved metadata.

- **Keep every final reader narrow.** Both step-1 sampler lifecycles must fail the current final predicates without a new universal admission framework:
  - `plan_tool/completeness_report.py:is_reusable_audit_sidecar` and `resolve_reusable_audit` must not reuse it.
  - `plan_tool/cli/completeness_phases.py:_saved_audit_revision_is_current` must not open it for `completeness-apply`.
  - `plan_tool/cli/review_cmd.py:_direct_walk_role_ineligibility`, `_review_reuse_ineligibility`, and `cmd_review_walk` must reject it before any recommendation walk.
  - `plan_tool/cli/data_contract_cmd.py:_newest_saved_completeness_with_contract_payload` must skip it, and `cmd_data_contract_apply` must reject an explicit stable-path selection before reading a contract payload.
  - `plan_tool/convergence_diagnosis.py:_is_final_report_role` must keep it out of `load_report_history`.

- **Keep the two protections independent.** The stable filename must stay outside the timestamped completeness-sidecar namespace, while the loaded role remains non-final. Do not loosen `plan_tool/review_persistence.py:list_saved_reviews`, change reusable-final precedence, add a CLI flag, or add a `completeness-audit --json` field.

## Tests

### Tests for this step

- `tests/test_convergence_diagnosis.py::test_load_audit_evidence_ledger_discovers_stable_in_progress_checkpoint` — Normal checkpoint-aware loading creates one standalone row with state `in-progress-checkpoint`, no Markdown report, the stable sidecar path, and rendered diagnostic output.

- `tests/test_convergence_diagnosis.py::test_load_audit_evidence_ledger_does_not_promote_invalid_stable_checkpoint` — A malformed, wrong-kind, or role-invalid file at the stable path receives neither sampler lifecycle state and never enters history.
- `tests/test_convergence_diagnosis.py::test_load_audit_evidence_ledger_names_terminal_sampler_residue` — A valid terminal-residue artifact receives its non-resumable diagnostic label and never enters history.

- `tests/test_convergence_diagnosis.py::test_load_report_history_excludes_in_progress_checkpoint` — The history reader skips the checkpoint while retaining ordinary final reports.

- `tests/test_review_persistence.py::test_sampler_checkpoint_lifecycles_are_rejected_by_each_final_evidence_reader` — A parameterized matrix proves rejection of both sampler lifecycles by reusable-audit selection, completeness-apply, review reuse, direct saved-review walking, both data-contract gates, and convergence-history admission.

- `tests/test_review_persistence.py::test_direct_saved_review_walk_rejects_stable_in_progress_checkpoint` — `plan_tool/cli/review_cmd.py:cmd_review_walk` rejects both default discovery and explicit selection without starting a recommendation walk.

Every listed test must be green before this step is complete.

## Acceptance criteria

- `plan_tool/convergence_diagnosis.py:load_audit_evidence_ledger` includes a valid stable checkpoint as exactly one standalone row with the lifecycle’s diagnostic state.

- The stable checkpoint has no synthetic Markdown report, does not use timestamp-pair semantics, and remains visible in rendered ledger output.

- A malformed or role-invalid file at the stable checkpoint path receives neither sampler lifecycle state.

- `plan_tool/convergence_diagnosis.py:load_report_history` excludes both sampler lifecycle states from every convergence verdict.

- `plan_tool/completeness_report.py:resolve_reusable_audit`, `plan_tool/cli/completeness_phases.py:_saved_audit_revision_is_current`, `plan_tool/cli/review_cmd.py:cmd_review_walk`, and both `plan_tool/cli/data_contract_cmd.py` selection paths reject the checkpoint.

- Existing timestamped final and pre-apply checkpoint behavior remains unchanged.

- `tests/test_convergence_diagnosis.py` and `tests/test_review_persistence.py` pass.

## References

- [json — JSON encoder and decoderhttps: — Use the loader and `JSONDecodeError` behavior when preserving malformed saved artifacts as fail-closed diagnostic rows.

## Applicable guardrails

- **Diagnostic-only checkpoint** — The plan’s “## Step intent” requires the ledger to show partial evidence without allowing it into reuse, apply, walk, or history.

- **Final-evidence boundary** — The plan’s “## Out of scope” final-evidence and reuse rules prohibit promoting the checkpoint or changing reusable-final selection.

- **Surface boundary** — The plan’s “## Out of scope” CLI and JSON rules prohibit new flags and `completeness-audit --json` fields.

- **Semantic stability** — The plan’s “## Out of scope” finding-semantics rule prohibits changes to finding severity, union, confirmation, blocking, continuation, or exit behavior.
