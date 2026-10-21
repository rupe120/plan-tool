# Step 3 — Cap the full purity scan and report skipped steps

## Summary

Add a finite wall-clock budget for the complete optional purity battery in `plan_tool/cli/completeness_phases.py`. Keep step 2’s per-call purity timeout, but limit each new backend call to the smaller of that timeout and the pass time remaining. Record every eligible readable step skipped after the budget expires as a blocking purity-coverage finding, and surface it in the existing human and JSON reports. On green, a stalled scan cannot start one full-timeout call for every remaining step.

## Table of Contents

- [Summary](#summary) — The completed behavior in one view.
- [Table of Contents](#table-of-contents) — Links to the detail sections.
- [Why](#why) — Why per-call limits alone do not bound the battery.
- [Input](#input) — Timeout, cache, and reporting contracts this step consumes.
- [Files (creates vs edits)](#files-creates-vs-edits) — Scoped implementation and test files.
- [Implementation](#implementation) — Pass-budget, coverage, and report rules.
- [Tests](#tests) — Focused unit and command-level coverage.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Primary documentation for timing and dynamic scopes.
- [Applicable guardrails](#applicable-guardrails) — Plan boundaries that apply here.
- [Deferred](#deferred) — Related work left outside this step.

## Why

`plan_tool/cli/completeness_phases.py:_collect_purity_split_findings` gives each eligible step the same per-call allowance, so a series of slow calls can consume that allowance repeatedly. The audit already treats a failed scan as blocking lost coverage through `_DeterministicReport.purity_coverage_recs`; it needs the same honesty when the battery deliberately stops before later scans begin. This step adds the missing whole-battery limit without changing what a completed purity verdict means.

## Input

- **Step 1 and step 2 timeout contract:** Use the shell-owned timeout parsing and resolution path delivered by step 1, plus step 2’s `PLAN_TOOL_PURITY_CLAUDE_TIMEOUT` and `PURITY_CLAUDE_TIMEOUT_S` per-call result. The new pass budget must not reinterpret the legacy global per-call setting as a batch budget.

- **Purity cache contract:** `plan_tool/detail.py:_cached_purity_findings` is the existing read-through cache boundary. Its successful cache entries represent real verdicts, while a failed or unreadable scan has no successful verdict.

- **Coverage-report contract:** `plan_tool/cli/completeness_phases.py:_DeterministicReport.purity_coverage_recs` already reaches `_render_completeness_json`, `_render_grouped_report`, and `plan_tool/cli/completeness_cmd.py:_completeness_has_blocking_findings`. Keep skipped coverage in that bucket.

## Files (creates vs edits)

- **New files:** None.

- **Existing files (edits only):**
  - `plan_tool/cli/completeness_phases.py` — Add the pass-wide purity budget, clamp each eligible backend call to the remaining allowance, create skipped-scan coverage findings, and distinguish skipped coverage in report text.
  - `tests/cli/test_completeness_cmd.py` — Add controlled-clock tests for budget resolution, call admission, timeout clamping, skipped coverage, and rendering.
  - `tests/test_cli.py` — Add an end-to-end `completeness-audit --purity --json` case proving skipped coverage reaches the command output and blocking gate.

## Implementation

- **Use one pass-wide setting.** Define `PLAN_TOOL_PURITY_SCAN_BUDGET` with a named fallback such as `PURITY_SCAN_BUDGET_S = 1_800.0`. The 1,800-second default allows several normal scans while stopping a run after two full 900-second per-call timeouts.

- **Keep total and per-call policy separate.** Resolve the new setting through the step-1 shell-owned parsing path, with no fallback to `PLAN_TOOL_CLAUDE_TIMEOUT`. A missing setting uses the finite default; zero, negative, or malformed values disable only the pass-wide cap and retain the existing unbounded-battery behavior.

- **Measure the whole purity loop monotonically.** In `plan_tool/cli/completeness_phases.py:_collect_purity_split_findings`, take one `time.monotonic()` start point for the battery and check the remaining allowance before each eligible scan. Do not start a backend call when the enabled budget has no time left.

- **Clamp, rather than stack, timeout scopes.** Replace the one fixed scope around the whole loop with a scope for each admitted scan. Its effective timeout must be the smaller positive value of the step-2 per-call timeout and the pass time remaining; if the per-call timeout is disabled but the pass budget is enabled, the remaining allowance still bounds the call. This prevents an in-flight call from extending past the pass ceiling.

- **Report skipped scans separately from failed scans.** Keep `PURITY_SCAN_FAILED_SOURCE` for a scan that ran but returned no usable verdict. Add a distinct stable source such as `PURITY_SCAN_SKIPPED_SOURCE` for an otherwise-readable pending code step that the exhausted pass budget did not scan. Use a stable per-step recommendation id, `high` severity, and wording that names budget exhaustion and `PLAN_TOOL_PURITY_SCAN_BUDGET` as the recovery control.

- **Keep eligibility rules unchanged.** Continue to ignore done steps, non-code steps, and missing or empty detail files. Only readable steps that would otherwise be scanned become skipped coverage gaps after the cap expires.

- **Preserve verdict meaning and cache behavior.** Continue to route returned medium `granularity-split` findings and cache-reuse advisories to `smell_recs`. Route both failed and skipped coverage sources to `purity_coverage_recs`; `plan_tool/cli/completeness_cmd.py:finalize_completeness_run` and `_completeness_has_blocking_findings` already carry that bucket into JSON and `--fail-on-findings`.

- **Make the report truthful.** Update `_render_grouped_report` and `_render_completeness_json` so a skipped step cannot read as a timeout, empty response, clean verdict, or advisory smell. Keep the existing `### Purity coverage` section if it can clearly describe both failed and budget-skipped scans.

- **Do not reuse convergence policy.** `plan_tool/convergence.py:IterativeBudget` has a similar wall-clock concept but controls convergence rounds, not individual purity calls. Keep this small purity-specific rule in the phase helper.

## Tests

### Tests for this step

- `tests/cli/test_completeness_cmd.py:TestRunDeterministicChecks.test_purity_scan_budget_clamps_call_to_remaining_time` — Uses a patched monotonic clock and invoker seam to show each admitted call sees no more than the remaining pass allowance.

- `tests/cli/test_completeness_cmd.py:TestRunDeterministicChecks.test_purity_scan_budget_skips_each_remaining_readable_step` — Exhausts the budget after one scan, proves no later backend calls start, and asserts one high skipped-coverage finding per remaining readable eligible step.

- `tests/cli/test_completeness_cmd.py:TestRunDeterministicChecks.test_purity_scan_budget_ignores_done_non_code_and_unreadable_steps` — Confirms existing exclusions do not become skipped coverage findings.

- `tests/cli/test_completeness_cmd.py:TestRunDeterministicChecks.test_disabled_purity_scan_budget_keeps_scanning` — Parameterizes zero, negative, and malformed budget values and proves they disable only the total cap.

- `tests/cli/test_completeness_cmd.py:TestRunDeterministicChecks.test_purity_timeout_failure_is_not_reclassified_as_budget_skip` — Keeps a real attempted timeout in the existing failed-scan source and coverage behavior.

- `tests/cli/test_completeness_cmd.py:TestRenderGroupedReport.test_purity_coverage_distinguishes_skipped_scans` — Checks the Markdown report names budget-skipped coverage and the correct recovery setting.

- `tests/test_cli.py:TestCmdCompletenessConceptWiring.test_purity_budget_skips_surface_in_json_and_block` — Drives `main()` with `--purity --json --fail-on-findings` and asserts the skipped coverage payload, `has_blocking_findings`, and blocking exit result.

Every listed test must be green before this step is complete.

## Acceptance criteria

- `PLAN_TOOL_PURITY_SCAN_BUDGET` defaults to 1,800 seconds when absent and disables the pass-wide limit when set to zero, a negative value, or malformed text.

- An enabled purity pass never starts a backend call after its wall-clock allowance is exhausted.

- Every admitted backend call receives the smaller of its step-2 per-call timeout and the remaining pass allowance.

- A readable pending code step skipped because the pass budget expired produces one stable high `purity-scan-skipped` finding in `purity_coverage_recs`.

- Done, non-code, missing-detail, and empty-detail steps produce no skipped coverage finding.

- A timeout, empty reply, or truncated reply from a call that started remains a `purity-scan-failed` finding rather than a skipped finding.

- The grouped report and `checks.purity_coverage` JSON distinguish skipped coverage from failed coverage, and skipped coverage makes `has_blocking_findings` true.

- The focused tests in `tests/cli/test_completeness_cmd.py` and `tests/test_cli.py` pass.

## References

- [Python `time.monotonic`](https://docs.python.org/3/library/time.html#time.monotonic) — Use the non-adjustable clock for the whole-battery deadline and remaining-time calculation.

- [Python `contextvars`](https://docs.python.org/3/library/contextvars.html) — Verify nested dynamic timeout scopes restore the active value after each scan.

- [Python `subprocess`](https://docs.python.org/3/library/subprocess.html) — Confirm the scoped remaining timeout continues to bound the backend subprocess.

- [pytest monkeypatch fixture](https://docs.pytest.org/en/stable/how-to/monkeypatch.html) — Use reversible environment, clock, and invoker patches for deterministic coverage.

## Applicable guardrails

- **The plan’s “## Plan intent”, independent phase budgets:** Apply the total budget only to `plan_tool/cli/completeness_phases.py:_collect_purity_split_findings`; do not change conceptual-audit or unscoped caller timing.

- **The plan’s “## Step intent”, coverage visibility:** Stop future purity backend calls at the pass boundary and report the lost coverage through the blocking bucket.

- **The plan’s “## Out of scope”, command and backend policy:** Keep the existing optional command surface, backend protocol, and recovery behavior unchanged while adding this phase-local environment setting.

- **The plan’s “## Out of scope”, verdict handling:** Do not rejudge completed purity verdicts or make returned MIXED-STEP advice blocking; only failed or skipped scan coverage blocks.

## Deferred

- `plan_tool/detail.py:_cached_purity_findings` cache-only admission after a pass budget expires — keep the existing cache boundary unchanged here; a future cache-only API would need a separate cross-module design.

- `plan_tool/convergence.py:IterativeBudget` consolidation — its round-level cap is related but serves a different caller and should not become a dependency of the purity phase in this feature step.
