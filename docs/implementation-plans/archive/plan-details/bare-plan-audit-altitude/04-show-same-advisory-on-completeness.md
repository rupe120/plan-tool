> **Auto-archived**: this plan was swept on 2026-08-18 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 4 — Show the same advisory on completeness stderr without changing audit outcomes

## Summary

Extend the completed run-grade completeness-audit stderr path to show the mechanism advisory and same-finding edit-drift composition that step 3 adds to convergence output. Update `plan_tool/cli/completeness_cmd.py` and the command-path coverage in `tests/cli/test_completeness_cmd.py`. Reuse the step-3 advisory composition rather than rebuilding its eligibility or matching rules in the CLI. On green, eligible bare findings receive the same standalone or combined guidance on stderr, while audit results, exit codes, and Jira-grade suppression stay unchanged.

## Table of Contents

- [Summary](#summary) — The stderr presentation change and its outcome.
- [Table of Contents](#table-of-contents) — Links to each section.
- [Why](#why) — Why completeness needs the convergence guidance.
- [Input](#input) — The saved-history and post-persistence contracts this step reads.
- [Files (creates vs edits)](#files-creates-vs-edits) — The two existing files to update.
- [Implementation](#implementation) — Reuse, timing, suppression, and outcome boundaries.
- [Tests](#tests) — Command-path cases that prove presentation without enforcement changes.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Test-seam guidance.
- [Applicable guardrails](#applicable-guardrails) — Plan boundaries that bind this presentation work.
- [Deferred](#deferred) — Related work this step leaves out.

## Why

`plan_tool/cli/completeness_cmd.py:_convergence_loop_advisory_lines()` already loads completed report history and sends selected convergence advice to stderr after a run-grade sidecar is written, but it currently knows only the older impact-recurrence and edit-drift renderers. Without step 3’s shared mechanism/edit-drift composition, an operator can see different advice from `convergence` and from the audit that just produced the saved bare pass.

## Input

- **Step 3 advisory contract:** Step 3 supplies the shared standalone, combined, and residual edit-drift guidance from completed run-grade history only. This step consumes that rendering result and does not repeat mechanism classification, grade selection, or same-finding matching.

- **Completed history:** `plan_tool/convergence_diagnosis.py:load_report_history()` and `plan_tool/convergence_diagnosis.py:diagnose_convergence()` read the saved run-grade sidecar after `plan_tool/cli/completeness_phases.py:_persist_and_present_report()` finishes.

- **Presentation lifecycle:** `plan_tool/cli/completeness_cmd.py:finalize_completeness_run()` calls `plan_tool/cli/completeness_cmd.py:_emit_convergence_loop_advisories()` only after report persistence. Its `detail_grade`, `report_path`, `skip_sidecar_write`, and `audit_stage` inputs remain the boundary for whether stderr advice can be shown.

- **Verification limit:** Command tests can prove that seeded completed history produces the intended stderr text and unchanged outcomes. They cannot prove that future model-generated finding prose receives the mechanism label; step 2 owns that classifier coverage.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `plan_tool/cli/completeness_cmd.py` — Extend the post-persistence convergence-advisory line selection to use step 3’s shared mechanism/edit-drift composition while retaining existing impact-recurrence output and suppression checks.
  - `tests/cli/test_completeness_cmd.py` — Extend `TestCompletenessStderrConvergenceAdvisories` with bare-stage, composition, suppression, and unchanged-outcome command coverage.

## Implementation

- **Foundational logic: completed run-grade bare-pass advisory presentation.** After a fresh run-grade completeness audit persists its sidecar, render the same mechanism and edit-drift guidance that step 3 exposes through `plan_tool/convergence_diagnosis.py:render_diagnosis()`.

- **Reuse step 3’s composition as one unit.** Update `plan_tool/cli/completeness_cmd.py:_convergence_loop_advisory_lines()` to consume the reusable mechanism/edit-drift line composer that step 3 lands. Do not recreate the classifier check, prior-apply comparison, or same-current-finding intersection in `plan_tool/cli/completeness_cmd.py`.

- **Keep existing advisory ordering intact.** Preserve the current `plan_tool/convergence_diagnosis.py:_impact_recurrence_lines()` output, then add the shared mechanism/edit-drift guidance in the same order as convergence output. A matching finding must receive one combined message, not a locally reconstructed mechanism line plus the old full edit-drift line.

- **Preserve residual advice.** Let the shared composer retain standalone mechanism guidance for eligible non-matches and separate edit-drift guidance for drift matches outside the intersection. Do not make a matching finding hide unrelated advice.

- **Use the existing stage-aware diagnosis path.** Keep `plan_tool/cli/completeness_cmd.py:_convergence_loop_advisory_lines()` calling `diagnose_convergence()` with the final audit-stage handoff and the existing domain-classification callback. Step 3 owns the rule that detail-stage, closed, non-`plan-correctness`, and unclassified findings produce no mechanism guidance.

- **Keep stderr tied to a completed run-grade save.** Retain `plan_tool/cli/completeness_cmd.py:_emit_convergence_loop_advisories()` as the sole printer. Its Jira-grade return, missing-report guard, and skipped-sidecar guard prevent advice from being derived from absent or non-run-grade history; step 3 also prevents a Jira or ungraded saved pass from shaping the shared advice.

- **Do not change outcomes.** This path reads persisted history and prints recommendation-only text after report persistence. It must not alter `has_blocking`, the qualified audit result, `--fail-on-findings`, iteration continuation, stop reasons, or any saved review payload.

- **Leave the convergence command as the source surface.** `plan_tool/cli/convergence_cmd.py:cmd_convergence()` and `plan_tool/convergence_diagnosis.py:render_diagnosis()` remain step 3’s shared source for advisory semantics; this step adds no parallel policy or persistence surface.

## Tests

### Tests for this step

- `test_completeness_stderr_prints_standalone_mechanism_advisory_after_one_completed_bare_pass` — verifies one open, positively classified bare `plan-correctness` finding emits the standalone guidance after the current run saves its sidecar.

- `test_completeness_stderr_combines_same_current_mechanism_and_edit_drift` — verifies a current finding shared with edit drift produces one combined message and no duplicate advice for that finding.

- `test_completeness_stderr_keeps_unmatched_mechanism_and_edit_drift_advice_separate` — verifies an eligible mechanism non-match and a distinct drift match each retain their own guidance.

- `test_completeness_stderr_omits_mechanism_advisory_for_detail_stage` — verifies an otherwise eligible classified finding in a completed detail-stage pass produces no mechanism stderr advice.

- `test_completeness_stderr_skips_mechanism_advisory_on_jira_grade` — extends the existing grade-suppression case to prove Jira-grade completeness output does not show the new guidance.

- `test_completeness_stderr_skips_mechanism_advisory_when_sidecar_not_written` — verifies reuse or another no-sidecar path does not emit newly derived advice.

- `test_completeness_mechanism_advisory_does_not_change_audit_only_rc_or_fail_on_findings` — compares the same audit outcome with and without advisory history and proves stderr guidance does not change the return code.

- `test_completeness_mechanism_advisory_does_not_change_iterate_stop_reason` — verifies advisory history does not change the convergence loop’s stop reason.

Every listed test and affected existing tests in `tests/cli/test_completeness_cmd.py` must be green before this step is complete:

`uv run pytest tests/cli/test_completeness_cmd.py -q`

## Acceptance criteria

- A completed run-grade bare pass with one step-3-eligible finding prints the standalone mechanism advisory on completeness stderr.

- A current finding shared with edit drift prints one combined advisory, while unrelated eligible mechanism and edit-drift findings retain separate advice.

- Detail-stage findings do not print the mechanism advisory.

- Jira-grade completeness output and runs without a newly written run-grade sidecar do not print the mechanism advisory.

- The advisory does not change `has_blocking`, qualified-result classification, `--fail-on-findings` behavior, iteration stop reasons, or audit return codes.

- `uv run pytest tests/cli/test_completeness_cmd.py -q` passes.

## References

- [How to monkeypatch/mock modules and environments — pytest documentation](https://docs.pytest.org/en/stable/how-to/monkeypatch.html) — Use for focused command-path seams while keeping saved-history behavior real.

## Applicable guardrails

- **The plan’s “## Plan intent”, advisory-only enforcement boundary:** Keep the new stderr text outside every gate and final audit decision.

- **The plan’s “## Step intent”, shared run-grade guidance:** Reuse step 3’s eligible, standalone, and same-finding-composed result for completed run-grade bare audits.

- **The plan’s “## Out of scope”, audit-policy boundary:** Do not change blocking predicates, convergence continuation, failure behavior, audit-pass counts, or the detail-stage bar.

- **The plan’s “## Out of scope”, grade-specific presentation boundary:** Retain Jira-grade advisory suppression.

- **The plan’s “## Out of scope”, provenance boundary:** Present edit drift as a comparison signal and do not add a causal or persisted provenance claim.

## Deferred

- **Jira-grade advisory presentation** — The plan keeps this grade’s existing suppression; this step only presents run-grade stderr guidance.

- **Report, JSON, and saved-review schema changes** — This step adds no new payload or persistence surface because stderr presentation can reuse completed history.

- **Mechanism classification and advisory composition** — Steps 2 and 3 own the classifier and shared composition; this step only consumes their landed result.
