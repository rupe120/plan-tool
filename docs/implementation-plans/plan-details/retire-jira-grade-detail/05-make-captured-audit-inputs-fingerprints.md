# Step 5 — Make audit evidence run-grade-only

<!-- plan-tool:detail-format-version: 1 -->

## Summary

Make saved audit inputs, revisions, fingerprints, freshness checks, and reuse operate only on run-grade detail. Update `plan_tool/review_persistence.py`, `plan_tool/fingerprint.py`, and `plan_tool/completeness_report.py` to preserve supported run-grade revision records, including older supported revision versions, while rejecting retired Jira-grade evidence. Keep saved-review and sampler-checkpoint replacement writes durable without rewriting archived records merely to remove retired fields. On green, only valid run-grade evidence can be current or reusable, and malformed or retired evidence fails closed.

## Table of Contents

- [Summary](#summary) — The retained run-grade evidence behavior.
- [Table of Contents](#table-of-contents) — Links to each section.
- [Why](#why) — Why retired-grade evidence must not certify audits.
- [Input](#input) — Saved-review and revision records this step reads.
- [Files (creates vs edits)](#files-creates-vs-edits) — The focused source, test, and contract changes.
- [Implementation](#implementation) — Run-grade-only capture, normalization, freshness, and reuse rules.
- [Tests](#tests) — Unit coverage for supported, retired, malformed, and stale evidence.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Relevant test-parametrization guidance.
- [Applicable guardrails](#applicable-guardrails) — Scope limits for the retirement.
- [Deferred](#deferred) — Work outside this evidence-focused step.

## Why

`plan_tool/review_persistence.py` currently accepts grade-selected audit revisions and `plan_tool/fingerprint.py` can fingerprint Jira-grade detail, which leaves retired evidence able to look like ordinary missing or legacy provenance. That is unsafe because a rejected Jira-grade revision must not qualify through a fallback freshness or reuse path. This step keeps durable historical records readable only where their run-grade evidence remains supported, while making the active audit-evidence path honestly run-grade-only.

## Input

- **Captured audit inputs:** `plan_tool/review_persistence.py:AuditInputSnapshot` (its `capture` method), `AuditInputSnapshot.revision`, and `_audit_input_fingerprint` define the immutable prompt inputs and revision identity. The retained capture selects the run-grade `Step.detail` resolution through `plan_tool/detail_artifacts.py:resolve_detail_artifact`.

- **Persisted revision shape:** `plan_tool/review_persistence.py:normalize_audit_revision` reads revision versions 1 through 3 and normalizes omitted historical optional digests. Existing supported run-grade records must remain usable without rewriting them.

- **Saved-review lifecycle:** `plan_tool/review_persistence.py:save_review`, `save_sampler_checkpoint`, `load_review`, and `load_sampler_checkpoint` own durable final-review and replacement-checkpoint records. Archived saved records remain immutable unless an existing explicit write path replaces its own active artifact.

- **Freshness and reuse:** `plan_tool/review_persistence.py:project_saved_completeness_result` and `plan_tool/completeness_report.py:resolve_reusable_audit` compare saved revisions to a current capture. They must distinguish retired evidence from absent or malformed provenance.

## Files (creates vs edits)

- **New files:** None.

- **Existing files (edits only):**
  - `plan_tool/review_persistence.py` — Remove Jira-grade capture and freshness selection; make revision normalization accept only supported run-grade records, preserve supported historical decoding, and reject retired-grade evidence explicitly.
  - `plan_tool/fingerprint.py` — Make audit-input and detail-bundle fingerprint production run-grade-only while preserving the established run-grade map and revision digests.
  - `plan_tool/completeness_report.py` — Make reusable-audit freshness use the one run-grade capture path and fail closed for retired or malformed evidence.
  - `tests/test_review_persistence.py` — Cover supported historical revisions, retired evidence rejection, malformed revisions, checkpoints, and immutable archived-record handling.
  - `tests/test_fingerprint.py` — Remove retired Jira-grade fingerprint expectations and pin unchanged run-grade fingerprint behavior.
  - `tests/test_completeness_report.py` — Cover reuse and freshness boundaries for supported, retired, malformed, changed, and missing evidence.
  - `DATA_CONTRACT.md` — Document run-grade-only saved audit evidence, supported historical revision decoding, and retired-evidence rejection.
  - `tests/test_data_contract.py` — Update drift checks for the saved-evidence contract.

## Implementation

- **Make run grade the only live audit-input selection.** Update `plan_tool/review_persistence.py:AuditInputSnapshot` (its `capture` method) and `_audit_input_fingerprint` so captured details always come from the existing run-grade pointer-or-canonical resolution. Remove the Jira-derived path branch and avoid retaining a public grade selector that implies a supported alternate input.

- **Keep the revision identity stable for supported records.** Preserve the existing run-grade output of `plan_tool/fingerprint.py:audit_input_detail_revision`, `audit_input_detail_fingerprint`, and `audit_input_revision`, including revision versions 1 through 3 decoding in `plan_tool/review_persistence.py:normalize_audit_revision`. Older records that omit later optional digests must normalize as they do today when their detail grade is run.

- **Reject retired evidence as retired evidence.** A revision that explicitly names Jira grade must not normalize into a record with missing provenance, a stale-but-eligible record, or a run-grade record. Keep malformed revisions unavailable as well, but preserve the distinction in the reader path so `project_saved_completeness_result` and `resolve_reusable_audit` cannot substitute another freshness route for rejected Jira evidence.

- **Use one current-capture comparison.** Update `plan_tool/review_persistence.py:project_saved_completeness_result` and `plan_tool/completeness_report.py:resolve_reusable_audit` to compare supported saved revisions against a run-grade `AuditInputSnapshot`. Do not derive an alternate capture from a persisted grade field.

- **Keep generic code fingerprint behavior unchanged.** `plan_tool/fingerprint.py:compute_code_fingerprint` and `diff_code_fingerprint` remain the code-side drift surface. Retiring Jira detail selection must not change content-drift or footprint-added/removed results for a supported run-grade audit.

- **Keep detail-bundle fingerprinting run-grade-only.** Simplify `plan_tool/fingerprint.py:compute_detail_bundle_fingerprint` to the existing run-grade `resolve_detail_artifact` path. Preserve its current behavior for missing files, pointer resolution, relative POSIX keys, sorted output, and byte digests.

- **Do not migrate historical files during reads.** `plan_tool/review_persistence.py:load_review` and normalization helpers may decode supported old records in memory, but they must not rewrite archived sidecars to remove retired fields. Preserve `save_review` and `save_sampler_checkpoint` durable replacement behavior for new final records and the active sampler checkpoint.

- **Keep checkpoint safety aligned with final-review safety.** `plan_tool/review_persistence.py:load_sampler_checkpoint` must not treat a retired or malformed checkpoint revision as valid resumable evidence. A supported run-grade checkpoint remains valid when its other checkpoint-role requirements hold.

- **Build on step 1 without restoring the retired lane.** Step 1 removes review’s fence-parser dependency from `plan_tool/jira_grade.py`; this step must remove its remaining evidence-path dependency rather than moving another audit concern into that retired module.

## Tests

### Tests for this step

- `tests/test_review_persistence.py:test_supported_run_grade_audit_revision_round_trips_without_rewriting_archived_record` — Assert a current run-grade revision persists and reloads with the same evidence while an archived input file remains unchanged after reading.

- `tests/test_review_persistence.py:test_supported_v1_v2_and_v3_run_grade_revisions_normalize_with_historical_optional_digests` — Assert every supported historical run-grade revision decodes to the current in-memory shape with only its documented absent optional inputs filled as `None`.

- `tests/test_review_persistence.py:test_retired_jira_grade_audit_revision_is_rejected_not_normalized_as_missing` — Assert explicit retired Jira evidence is unavailable rather than being treated as legacy missing provenance.

- `tests/test_review_persistence.py:test_malformed_audit_revision_is_unavailable_without_breaking_saved_review_inspection` — Assert invalid revision shape leaves the saved review inspectable but unavailable for trusted freshness or reuse.

- `tests/test_review_persistence.py:test_sampler_checkpoint_with_retired_or_malformed_revision_is_not_resumable` — Assert a checkpoint cannot become valid merely because its role and sampler state otherwise look correct.

- `tests/test_review_persistence.py:test_save_sampler_checkpoint_replaces_active_checkpoint_durably` — Retain or strengthen the active-checkpoint replacement case so the run-grade-only change does not alter its durable write lifecycle.

- `tests/test_fingerprint.py:test_run_grade_detail_bundle_fingerprint_preserves_pointer_and_canonical_resolution` — Assert the retained fingerprint reads the same run-grade artifact selection and emits the same digest map.

- `tests/test_fingerprint.py:test_run_grade_detail_bundle_fingerprint_omits_missing_detail` — Assert missing run-grade artifacts remain absent from the map.

- `tests/test_fingerprint.py:test_audit_input_revision_is_run_grade_only` — Assert a new captured revision identifies run-grade detail and has the existing plan, detail, seed, and project-context digest behavior.

- `tests/test_completeness_report.py:test_resolve_reusable_audit_reuses_matching_supported_run_grade_revision` — Assert matching plan and run-grade detail inputs remain reusable.

- `tests/test_completeness_report.py:test_resolve_reusable_audit_rejects_retired_jira_revision_without_fallback` — Assert a candidate carrying retired evidence cannot qualify through a fresh run-grade capture or an older unpinned sidecar.

- `tests/test_completeness_report.py:test_resolve_reusable_audit_marks_supported_run_grade_revision_stale_at_each_input_boundary` — Parametrize plan, selected detail, source seed, project context, and code changes to assert the existing freshness boundary for each axis.

- `tests/test_completeness_report.py:test_saved_completeness_result_reports_retired_or_malformed_revision_as_unavailable` — Assert saved-result projection fails closed without rewriting the immutable result.

- `tests/test_data_contract.py:test_saved_review_qualified_result_contract_documents_run_grade_only_evidence` — Assert the contract names supported older run-grade revisions and the rejection rule for retired Jira evidence.

Every listed test must be green before this step is considered finished.

## Acceptance criteria

- New `AuditInputSnapshot` captures use only run-grade `Step.detail` resolution and emit the established run-grade revision and fingerprint behavior.

- `normalize_audit_revision` accepts supported version 1, 2, and 3 run-grade records and preserves their documented optional-digest compatibility.

- A revision explicitly carrying retired Jira-grade evidence is unavailable for result freshness, checkpoint resume, and reusable-audit selection; it does not qualify as legacy or missing evidence.

- Malformed revision data leaves its surrounding saved-review record inspectable but unavailable as trusted audit evidence.

- `compute_detail_bundle_fingerprint` retains the current run-grade pointer, canonical-path, missing-file, ordering, and digest behavior.

- Matching supported run-grade plan and detail inputs remain reusable; edits at each documented freshness boundary invalidate the matching result.

- `save_review` and `save_sampler_checkpoint` retain durable replacement writes for active artifacts, while read-only decoding does not rewrite archived sidecars.

- `DATA_CONTRACT.md` describes run-grade-only audit evidence, supported historical revision decoding, and retired-evidence rejection, and `tests/test_data_contract.py` passes.

## References

- [pytest parametrization — Use it to cover supported, retired, malformed, and freshness-boundary evidence cases without duplicating the same test flow.](https://docs.pytest.org/en/stable/how-to/parametrize.html)

## Applicable guardrails

- **The plan’s “## Step intent”** — Limit this step to evidence grounded in supported detail; do not change authoring, execution, or Jira output behavior.

- **The plan’s “## Scope guardrails”** — Remove retired evidence handling without adding a compatibility reader, replacement grade, migration, or unrelated consolidation.

- **The plan’s “## Out of scope”** — Preserve archived historical evidence rather than rewriting it, and leave run-grade detail-contract changes and Jira publication behavior untouched.

## Deferred

- Jira story and developer-handoff rendering — The plan’s “## Out of scope” keeps output behavior outside this evidence-focused step.
