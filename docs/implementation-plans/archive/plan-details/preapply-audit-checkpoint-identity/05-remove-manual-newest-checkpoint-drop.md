> **Auto-archived**: this plan was swept on 2026-08-05 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 5 — Remove the manual newest-checkpoint drop from report rendering

## Summary

Remove the report renderer’s local `drop_checkpoint` handling from `plan_tool/cli/completeness_phases.py`. The final-report convergence diagnosis must consume the final-only history supplied by step 4, then append the current in-memory run once. Update `tests/cli/test_completeness_cmd.py` so an iterative run with a marked checkpoint proves that prior final reports are retained and the current run is counted once. On green, report rendering no longer treats the newest saved sidecar as a checkpoint based on its position.

## Table of Contents

- [Summary](#summary) — Scope and expected green result.
- [Table of Contents](#table-of-contents) — Section guide.
- [Why](#why) — Why positional checkpoint removal is no longer safe.
- [Input](#input) — Upstream checkpoint-role and history contracts.
- [Files (creates vs edits)](#files-creates-vs-edits) — Files changed by this step.
- [Implementation](#implementation) — Final-only history and current-run rendering rules.
- [Tests](#tests) — Focused regression coverage.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Pytest guidance for the regression case.
- [Applicable guardrails](#applicable-guardrails) — Plan boundaries that constrain this change.
- [Deferred](#deferred) — Checkpoint work owned by other steps.

## Why

`plan_tool/cli/completeness_phases.py:_completeness_convergence_diagnosis` currently assumes the newest completeness snapshot is this invocation’s checkpoint and removes it when iteration is enabled. After step 4 makes `plan_tool/convergence_diagnosis.py:load_report_history` return final reports only, that positional rule would discard a real prior final report. Rendering must trust the shared history boundary instead of inferring a sidecar’s role from recency.

## Input

- **Checkpoint identity:** step 1 supplies the normalized role on `plan_tool/review_persistence.py:SavedReview`, and step 2 marks the checkpoint written by `plan_tool/cli/completeness_phases.py:write_pre_apply_audit_checkpoint`.

- **Final-only history:** step 4 makes `plan_tool/convergence_diagnosis.py:load_report_history` the shared source of completed report history. Its `ReportHistory.runs` output is ordered oldest to newest and is the only persisted-history input this renderer should use.

- **Current-run rendering:** `plan_tool/cli/completeness_phases.py:_persist_and_present_report` computes the current findings and fingerprints before writing the final sidecar, so `plan_tool/cli/completeness_phases.py:_completeness_convergence_diagnosis` must continue to add one in-memory `RunSnapshot`.

## Files (creates vs edits)

- **New files:** None.

- **Existing files (edits only):**
  - `plan_tool/cli/completeness_phases.py` — remove the positional checkpoint-drop input and logic from `_completeness_convergence_diagnosis`, and update its caller and comments to rely on final-only history.
  - `tests/cli/test_completeness_cmd.py` — update the convergence count-once fixture to create a marked checkpoint and prove it is excluded by shared history handling.

## Implementation

- **Foundational logic:** render convergence from final-only saved history plus exactly one in-memory current snapshot.

- **Remove the local newest-sidecar rule.** Update `plan_tool/cli/completeness_phases.py:_completeness_convergence_diagnosis` so it scopes `load_report_history(path).runs` to `kind == "completeness"` and appends the current `RunSnapshot` without removing a list element. Remove the `drop_checkpoint` parameter and its branch.

- **Keep iteration out of history identity.** Update the call from `plan_tool/cli/completeness_phases.py:_persist_and_present_report` so `iterate_enabled` no longer decides whether the helper removes a saved run. It still controls existing presentation and persistence behavior outside this identity decision.

- **Trust the shared reader.** Let step 4 own which saved reviews count as completed history. Do not inspect filenames, timestamps, report ordering, or checkpoint text in `plan_tool/cli/completeness_phases.py` to identify checkpoints.

- **Refresh stale explanation.** Revise `_completeness_convergence_diagnosis` documentation and nearby comments that describe dropping this invocation’s newest checkpoint or retaining earlier checkpoint/final pairs. They must describe the final-only history contract instead.

- **Preserve checkpoint presentation behavior.** Keep `plan_tool/cli/completeness_phases.py:write_pre_apply_audit_checkpoint` passing `suppress_convergence=True` to `_persist_and_present_report`; checkpoint reports remain durable recovery evidence without their own convergence section.

- **Keep series scoping unchanged.** Continue to diagnose only the completeness series before calling `plan_tool.convergence_diagnosis:diagnose_convergence`; reconcile history must not affect a completeness report.

## Tests

All listed tests must be green before this step is complete.

### Tests for this step

- `test_current_run_counted_once_iterate_with_marked_checkpoint` — seed two ordinary final completeness sidecars and a newer confirmed checkpoint, then assert the rendered diagnosis counts the two finals plus the current in-memory run, for a total of three.

- `test_current_run_counted_once_audit_only` — retain the audit-only control case, where two prior finals and the current in-memory run produce a count of three without a checkpoint.

- `test_checkpoint_call_renders_no_section` — retain the checkpoint-report regression check that `suppress_convergence` keeps convergence output out of the pre-apply report.

## Acceptance criteria

- `plan_tool/cli/completeness_phases.py:_completeness_convergence_diagnosis` has no `drop_checkpoint` input or branch that removes the newest saved run.

- `plan_tool/cli/completeness_phases.py:_persist_and_present_report` does not use `iterate_enabled` to alter the saved history passed to convergence diagnosis.

- With two ordinary final completeness reports and a newer marked checkpoint on disk, an iterative final report’s completeness-series `run_count` is `3`.

- The marked checkpoint is excluded by the shared history contract, while neither ordinary final report is discarded by report rendering.

- `tests/cli/test_completeness_cmd.py` passes its updated count-once and checkpoint-presentation coverage.

## References

- [How to parametrize fixtures and test functions — pytest documentation](https://docs.pytest.org/en/stable/how-to/parametrize.html) — Use concise fixture variations when expanding the saved-review role regression coverage.

## Applicable guardrails

- **The plan’s “## Step intent”, shared-history rendering:** limit this step to removing the renderer’s positional checkpoint guess and consuming the history boundary from step 4.

- **The plan’s “## Out of scope”, sidecar compatibility:** do not rename, migrate, rewrite, or delete saved report artifacts.

- **The plan’s “## Out of scope”, checkpoint recovery:** do not change `write_pre_apply_audit_checkpoint` persistence or the apply-loop recovery order.

- **The plan’s “## Out of scope”, reader behavior:** do not alter reusable-audit selection or redesign convergence beyond removing this duplicate checkpoint handling.

## Deferred

- `plan_tool/convergence_diagnosis.py:load_report_history` checkpoint-role filtering — owned by step 4; this step consumes its final-only output without changing the reader.

- `plan_tool/completeness_report.py:resolve_reusable_audit` checkpoint eligibility — owned by step 3 and outside report-rendering scope.

- `plan_tool/review_persistence.py:SavedReview` role persistence and `plan_tool/cli/completeness_phases.py:write_pre_apply_audit_checkpoint` marker production — owned by steps 1 and 2.
