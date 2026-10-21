> **Auto-archived**: this plan was swept on 2026-08-05 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 4 — Keep marked checkpoints out of convergence history

## Summary

Update `plan_tool/convergence_diagnosis.py:load_report_history` and its focused tests in `tests/test_convergence_diagnosis.py`. Filter saved reviews by the normalized checkpoint role before creating `RunSnapshot` objects, so convergence sees only ordinary final reports. Preserve the existing kind filter, ordering, and tolerant handling of unreadable sidecars. On green, confirmed checkpoints and unknown roles remain on disk for recovery and inspection but never affect a convergence verdict.

## Table of Contents

- [Summary](#summary) — Scope and green result.
- [Table of Contents](#table-of-contents) — Section guide.
- [Why](#why) — Why pre-apply evidence cannot count as a completed run.
- [Input](#input) — Persisted role and report-history contracts this step reads.
- [Files (creates vs edits)](#files-creates-vs-edits) — Files changed by this step.
- [Implementation](#implementation) — Shared history-filtering rule and boundaries.
- [Tests](#tests) — Focused regression coverage.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — JSON-role and pytest references.
- [Applicable guardrails](#applicable-guardrails) — Compatibility and reader-scope boundaries.
- [Deferred](#deferred) — Follow-up owned by other plan steps.

## Why

`plan_tool/convergence_diagnosis.py:load_report_history` currently turns every saved review with a `HISTORY_KINDS` kind into a `RunSnapshot`. After step 2 marks the pre-apply completeness sidecar, that sidecar still has the same kind and filename shape as a final report, even though it records findings before apply work finishes. Counting it as a completed run can create false recurrence, growth, or readiness signals for every convergence consumer.

## Input

- **Normalized role from step 1:** `plan_tool/review_persistence.py:SavedReview` distinguishes an ordinary final role from a confirmed checkpoint and an unknown role. Treat only the ordinary final role, including explicit `false` and legacy absence, as history-eligible.

- **Checkpoint producer from step 2:** `plan_tool/cli/completeness_phases.py:write_pre_apply_audit_checkpoint` writes the confirmed checkpoint role on the durable pre-apply completeness sidecar.

- **Existing reader seam:** `plan_tool/convergence_diagnosis.py:load_report_history` already uses `plan_tool/review_persistence.py:list_saved_reviews` and `plan_tool/review_persistence.py:load_review`, then applies `HISTORY_KINDS` before flattening through `plan_tool/convergence_diagnosis.py:_snapshot_from_saved_review`.

## Files (creates vs edits)

- **New files:** None.

- **Existing files (edits only):**
  - `plan_tool/convergence_diagnosis.py` — exclude confirmed checkpoints and unknown roles from loaded convergence snapshots.
  - `tests/test_convergence_diagnosis.py` — cover final, marked-checkpoint, legacy, and unknown-role history cases.

## Implementation

- **Foundational logic:** admit only ordinary-final saved reviews into convergence history.

- **Filter before flattening.** In `plan_tool/convergence_diagnosis.py:load_report_history`, keep the existing successful-load and `HISTORY_KINDS` checks, then use the normalized `SavedReview` role to decide whether the review becomes a `RunSnapshot`. A confirmed checkpoint and an unknown role must be skipped before `plan_tool/convergence_diagnosis.py:_snapshot_from_saved_review` runs.

- **Fail closed for unsafe metadata.** Step 1 defines malformed, misplaced, role/version-mismatched, and marker-less-version-3 metadata as an unknown role. Exclude that role for every eligible history kind, not only completeness, so an unexpected marked reconcile sidecar cannot enter a diagnostic series.

- **Keep final compatibility.** Raw version-3 `false` and unmarked version-1/2 sidecars remain ordinary finals. Historical unmarked sidecars must continue through the existing oldest-to-newest sort without migration, rewriting, or filename inference.

- **Keep the snapshot model final-only.** Do not add checkpoint state to `plan_tool/convergence_diagnosis.py:RunSnapshot` or teach downstream verdict logic to ignore it. The shared reader should return only eligible snapshots, leaving `partition_series`, `build_region_trends`, `diagnose_convergence`, `_latest_blocking_findings`, and `_code_drifted_since_prior` unchanged.

- **Keep one shared filter.** `plan_tool/cli/convergence_cmd.py:cmd_convergence`, `plan_tool/split_criteria.py:evaluate_split_criteria`, and the history reads in `plan_tool/telemetry_analysis.py` should inherit the rule through `load_report_history`; do not add parallel role checks at those callers.

- **Preserve tolerant reads.** Keep `ReviewLoadError` skipping and malformed timestamp ordering as they are. A sidecar with a loadable unknown role is excluded by role, while an unparseable sidecar remains skipped by the existing error path.

## Tests

Every test below must be green before this step is complete.

### Tests for this step

- `test_load_report_history_excludes_marked_pre_apply_checkpoint` — a marked completeness sidecar does not add a `RunSnapshot`, while surrounding ordinary final sidecars remain in chronological order.

- `test_load_report_history_keeps_ordinary_final_roles` — raw version-3 explicit `false` and unmarked version-1/2 legacy sidecars remain eligible final history entries.

- `test_load_report_history_excludes_unknown_checkpoint_roles` — a non-boolean marker and a marker on a non-completeness history kind stay loadable but do not enter history.

- `test_load_report_history_final_snapshot_count_drives_diagnosis` — marked checkpoints do not inflate the run count or alter the convergence result derived from the final snapshots.

## Acceptance criteria

- `plan_tool/convergence_diagnosis.py:load_report_history` creates `RunSnapshot` objects only for saved reviews with the ordinary-final role.

- Confirmed checkpoints and unknown-role sidecars remain readable through `plan_tool/review_persistence.py:load_review` but are absent from `ReportHistory.runs`.

- Unmarked version-1/2 legacy and raw version-3 explicit-final sidecars remain in the history, sorted by the existing `created_at` rule.

- All callers of `load_report_history` receive the same role-filtered history without caller-specific checkpoint filtering.

- `pytest tests/test_convergence_diagnosis.py` passes.

## References

- [json — JSON encoder and decoder](https://docs.python.org/3/library/json.html) — Review JSON boolean and invalid-value distinctions used by the persisted role contract.

- [How to parametrize fixtures and test functions — pytest documentation](https://docs.pytest.org/en/stable/how-to/parametrize.html) — Use a compact role matrix for ordinary, checkpoint, and unknown sidecars.

## Applicable guardrails

- **Durable recovery evidence:** the plan’s “## Plan intent” requires this step to leave checkpoint sidecars persisted and inspectable; only their history eligibility changes.

- **Final-snapshot history:** the plan’s “## Step intent” limits this work to convergence inputs, not a wider change to verdict or recommendation policy.

- **Path compatibility:** the plan’s “## Out of scope”, report naming and filename compatibility, keeps report paths and timestamped names unchanged.

- **Historical compatibility:** the plan’s “## Out of scope”, historical sidecars, keeps legacy unmarked final sidecars in place without migration or rewriting.

- **Reader boundary:** the plan’s “## Out of scope”, allowed behavior changes, limits this step to checkpoint-role filtering rather than redesigning convergence or reusable-audit behavior.

## Deferred

- Removal of positional checkpoint handling in `plan_tool/cli/completeness_phases.py:_completeness_convergence_diagnosis` — step 5 owns replacing its `drop_checkpoint` behavior after this shared filter lands.

- Reusable-audit selection in `plan_tool/completeness_report.py:resolve_reusable_audit` — step 3 owns its separate marked-and-unknown role filter.

- Saved-review migration, deletion, or filename changes — outside the plan’s compatibility boundary.
