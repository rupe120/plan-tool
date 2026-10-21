> **Auto-archived**: this plan was swept on 2026-08-05 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 2 — Mark pre-apply checkpoint sidecars without changing their names

## Summary

Mark the sidecar written before `--iterate` applies findings as a pre-apply checkpoint. Update `plan_tool/cli/completeness_phases.py` to identify that one producer and `plan_tool/completeness_report.py` to pass the role through the existing completeness-sidecar writer. Keep final report saves unmarked, including final reports produced by an iterative run. On green, checkpoint and final sidecars keep their existing timestamped names and locations, reserve distinct canonical stems even within one second, and the checkpoint carries `is_pre_apply_checkpoint: true` behind the version-3 compatibility fence.

## Table of Contents

- [Summary](#summary) — Scope and green result.
- [Table of Contents](#table-of-contents) — Section guide.
- [Why](#why) — Why the producer must identify checkpoints.
- [Input](#input) — Persisted role and report-writing contracts this step consumes.
- [Files (creates vs edits)](#files-creates-vs-edits) — Files changed by this step.
- [Implementation](#implementation) — Checkpoint-only role propagation rules.
- [Tests](#tests) — Focused regression coverage.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — JSON role-marker references.
- [Applicable guardrails](#applicable-guardrails) — Compatibility and scope limits.
- [Deferred](#deferred) — Reader behavior owned by later steps.

## Why

`plan_tool/cli/completeness_phases.py:write_pre_apply_audit_checkpoint` currently uses the same persistence path as a final completeness report. Step 1 makes the saved-review role available, but this producer must now write the confirmed checkpoint value so later reuse and convergence readers can distinguish recovery evidence from a completed run.

## Input

- **Checkpoint role from step 1:** `plan_tool/review_persistence.py:SavedReview` and `plan_tool/review_persistence.py:save_review` now accept and persist the safe `is_pre_apply_checkpoint` role contract. This step supplies the first production `true` request and therefore must emit version 3; it relies on step 1’s validation, legacy handling, and downgrade fence.
- **Completeness writer:** `plan_tool/completeness_report.py:write_completeness_report` writes the timestamped Markdown report and, when recommendations are present, its `kind="completeness"` JSON sidecar.
- **Checkpoint call order:** `plan_tool/cli/completeness_cmd.py:_run_iterate_convergence_loop` invokes `write_pre_apply_audit_checkpoint` before its apply loop. Keep that crash-recovery ordering intact without changing the orchestrator.

## Files (creates vs edits)

- **New files:** None.

- **Existing files (edits only):**
  - `plan_tool/cli/completeness_phases.py` — identify the pre-apply persistence call as a checkpoint and carry that identity through the report-persistence helper.
  - `plan_tool/completeness_report.py` — let the completeness-report writer pass an explicit checkpoint request to `save_review`, reserve a collision-safe shared report stem before either writer runs, and preserve normal final-save omission.
  - `tests/cli/test_completeness_cmd.py` — cover the pre-apply producer and iterative final-report distinction.
  - `tests/test_completeness_report.py` — cover writer-level marker serialization and default final behavior.

## Implementation

- **Foundational logic:** propagate an explicit checkpoint role from the pre-apply producer to the saved completeness sidecar.

- **Mark only the pre-apply producer.** Have `plan_tool/cli/completeness_phases.py:write_pre_apply_audit_checkpoint` explicitly request the checkpoint role when it delegates to `plan_tool/cli/completeness_phases.py:_persist_and_present_report`. Do not infer checkpoint status from `iterate_enabled`, a stop reason, report text, or filename: both the checkpoint and the final report can be iterative completeness artifacts.

- **Keep the generic persistence tail final by default.** Extend `plan_tool/cli/completeness_phases.py:_persist_and_present_report` with an internal, default-final way to carry the role to `plan_tool/completeness_report.py:write_completeness_report`. Calls from `plan_tool/cli/completeness_cmd.py:finalize_completeness_run` must retain that default, including after an iterative run.

- **Pass the request through the existing writer chain.** Extend `plan_tool/completeness_report.py:write_completeness_report` so its completeness-sidecar call to `plan_tool/review_persistence.py:save_review` receives the checkpoint request. A keyword-only optional argument is a suitable shape, provided ordinary callers need no changes.

- **Write only version-3 `true` for checkpoints.** The pre-apply path must serialize version 3 plus `is_pre_apply_checkpoint: true`, so a role-unaware version-1/2 reader rejects the sidecar rather than treating it as final. Final writers must not serialize `false`; leave the optional key absent and retain their current version so final and historical unmarked sidecars retain the step 1 legacy-final policy.

- **Reserve the complete artifact set before writing it.** In `plan_tool/completeness_report.py:write_completeness_report`, choose one logical UTC timestamp for the Markdown report, completeness JSON sidecar, and optional data-contract payload before `durable_write_text` writes any of them. If any existing complete-report artifact already uses that canonical whole-second stem, advance by whole seconds until the whole set is free. Pass the selected timestamp to `save_review`, so the filename and persisted `created_at` agree. The serial writer keeps the existing `<timestamp>-completeness.{md,json}` convention; do not add a checkpoint suffix, a sequence component, a second directory, or a parallel allocation path.

- **Preserve all report contents and paths.** Keep the same report Markdown, recommendations, fingerprints, audit coverage, advisory payload, error handling, and timestamp naming. A collision advances only the logical whole-second timestamp; it does not alter the reports directory, `-completeness` suffix, or report kind. Do not add a checkpoint suffix or create a second directory or sidecar type.

- **Keep unrelated checkpoint behavior unchanged.** `write_pre_apply_audit_checkpoint` must still persist before apply work, skip the duplicate purity pass, and suppress checkpoint convergence rendering. This step identifies the sidecar; it does not change what the checkpoint captures.

- **Use the existing single writer.** `plan_tool/completeness_report.py:write_completeness_report` is the production path that emits `kind="completeness"` sidecars. Do not add another `save_review` call or duplicate sidecar-writing logic in `plan_tool/cli/completeness_phases.py`.

## Tests

Every test below must be green before this step is complete.

### Tests for this step

- `test_write_report_emits_json_sidecar_when_recommendations_given` — extend the existing writer test to confirm a normal completeness sidecar omits the raw checkpoint-marker key and loads as an ordinary final artifact.
- `test_write_report_marks_checkpoint_sidecar_when_requested` — an explicit checkpoint request writes raw JSON version 3 plus `is_pre_apply_checkpoint: true` while preserving the normal `*-completeness.md` and `*-completeness.json` names.
- `test_pre_apply_checkpoint_sidecar_is_marked_and_v3` — `write_pre_apply_audit_checkpoint` produces a marked version-3 saved sidecar through the real report-persistence path.
- `test_iterate_final_report_omits_checkpoint_marker` — a normal `_persist_and_present_report` final write with `iterate_enabled=True` remains unmarked, proving iteration mode alone does not classify a report as a checkpoint.
- `test_same_second_checkpoint_and_final_allocate_distinct_report_pairs` — fixed-clock checkpoint and final writes receive distinct canonical whole-second stems; both Markdown/JSON pairs remain readable, their `created_at` values match their allocated stems, and the checkpoint marker survives.
- `test_same_second_allocation_preserves_data_contract_payload` — an occupied complete-report stem including the sibling data-contract payload makes the next write reserve a different full artifact set without overwriting any member.

## Acceptance criteria

- `plan_tool/cli/completeness_phases.py:write_pre_apply_audit_checkpoint` writes a version-3 completeness JSON sidecar whose persisted checkpoint role is confirmed `true`.
- `plan_tool/cli/completeness_phases.py:_persist_and_present_report` writes ordinary final sidecars by default, including iterative final reports.
- `plan_tool/completeness_report.py:write_completeness_report` forwards an explicit checkpoint request to `plan_tool/review_persistence.py:save_review` without changing its existing report and sidecar write rules.
- Final completeness sidecars omit `is_pre_apply_checkpoint` rather than serializing `false` and retain their current version; a role-unaware version-1/2 reader rejects the emitted checkpoint sidecar.
- Checkpoint and final outputs retain the existing reports directory and timestamped `-completeness` filenames.
- A checkpoint and final report written in the same wall-clock second occupy distinct whole-second canonical stems, preserve every artifact in each pair, and use matching filename/`created_at` timestamps.
- `pytest tests/cli/test_completeness_cmd.py tests/test_completeness_report.py` passes.

## References

- [json — JSON encoder and decoder](https://docs.python.org/3/library/json.html) — Review optional-field serialization and raw payload assertions.
- [RFC 8259: The JavaScript Object Notation (JSON) Data Interchange Format](https://www.rfc-editor.org/rfc/rfc8259.html) — Use the JSON boolean form required for the checkpoint marker.

## Applicable guardrails

- **Durable recovery evidence:** the plan’s “## Plan intent” requires the existing pre-apply save to remain durable and available after a failed apply loop.
- **Checkpoint identity only:** the plan’s “## Step intent” limits this step to marking the producer output, not changing audit findings or recovery flow.
- **Path compatibility:** the plan’s “## Out of scope”, report naming and filename compatibility, keeps `plan_tool/completeness_report.py:write_completeness_report` paths and names unchanged.
- **Historical data:** the plan’s “## Out of scope”, historical sidecars, forbids migration, rewriting, or deletion of existing reports.
- **Reader boundaries:** the plan’s “## Out of scope”, convergence and reuse behavior, leaves reader filtering to later steps.

## Deferred

- Reusable-audit filtering in `plan_tool/completeness_report.py:resolve_reusable_audit` — step 3 excludes marked and unknown sidecars from selection.
- Convergence-history filtering in `plan_tool/convergence_diagnosis.py:load_report_history` — step 4 excludes marked and unknown sidecars from snapshots.
- Removal of the positional newest-checkpoint drop in `plan_tool/cli/completeness_phases.py:_completeness_convergence_diagnosis` — step 5 replaces it after shared history filtering exists.
- Migration or deletion of historical sidecars — outside the plan’s compatibility boundary.
