# Step 2 — Give purity scans and conceptual audits separate timeout settings

## Summary

Add separate environment settings for the per-step purity scan and the conceptual-audit phase in `plan_tool/cli/completeness_phases.py`. Update the phase helpers to obtain their timeout through the shell-owned resolver delivered by step 1, then enter the existing dynamic timeout scope around their Claude-calling work. The phase setting wins over the legacy global setting, while an explicit disabled phase value prevents fallback to that global value. On green, operators can tune the two audit call types independently without changing unscoped callers or audit findings.

## Table of Contents

- [Summary](#summary) — The step outcome and affected phases.
- [Table of Contents](#table-of-contents) — Links to each section.
- [Why](#why) — Why the two audit call types need separate controls.
- [Input](#input) — Timeout contracts supplied by step 1 and current phase behavior.
- [Files (creates vs edits)](#files-creates-vs-edits) — Scoped file changes.
- [Implementation](#implementation) — Required precedence, scope, and unchanged behavior.
- [Tests](#tests) — Focused phase and command coverage.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Primary API references for timeout scopes and test isolation.
- [Applicable guardrails](#applicable-guardrails) — Scope limits that bind this step.
- [Deferred](#deferred) — Shared audit path outside this step’s file list.

## Why

`plan_tool/cli/completeness_phases.py:_collect_purity_split_findings` has a 900-second default, while `_sample_conceptual_audit` has no phase-specific bound. Both currently depend on the one legacy `PLAN_TOOL_CLAUDE_TIMEOUT` setting, so an operator cannot size the short per-step scan and the broader conceptual audit independently. Step 1 moves precedence into the shell layer; this step uses that single owner to expose one setting per phase without changing the subprocess, retry, or finding contracts.

## Input

- **Step 1 timeout resolution:** Step 1 provides the shell-owned resolver near `plan_tool/shell.py:_parse_timeout_seconds`, `plan_tool/shell.py:scoped_claude_timeout`, and `plan_tool/shell.py:_effective_subprocess_timeout`. This step must use that resolver rather than reading environment variables in the phase module.

- **Purity phase contract:** `plan_tool/cli/completeness_phases.py:PURITY_CLAUDE_TIMEOUT_S` remains the purity default, and `_collect_purity_split_findings` must keep one timeout scope around its existing scan loop.

- **Conceptual-audit contract:** `plan_tool/cli/completeness_phases.py:_sample_conceptual_audit` calls `plan_tool/review.py:audit_plan_until_stable`, whose passes invoke the configured backend through `shell_review_invoker`. The setting must bound each backend call, not the audit loop’s total elapsed time.

## Files (creates vs edits)

- **New files:** None.

- **Existing files (edits only):**
  - `plan_tool/cli/completeness_phases.py` — Define the conceptual-audit default and both phase setting names, resolve each phase timeout through the step-1 shell API, scope `_sample_conceptual_audit`, and update purity timeout recovery text.
  - `tests/cli/test_completeness_cmd.py` — Test phase-level precedence, disabled values, scope placement, and the updated purity recovery wording.
  - `tests/test_cli.py` — Test that an audit-only `completeness-audit` command carries the conceptual setting through to its backend invoker.

## Implementation

- **Use two phase settings.** Define `PLAN_TOOL_PURITY_CLAUDE_TIMEOUT` for `_collect_purity_split_findings` and `PLAN_TOOL_CONCEPTUAL_AUDIT_CLAUDE_TIMEOUT` for `_sample_conceptual_audit`. Keep `PURITY_CLAUDE_TIMEOUT_S` as the purity fallback and add a separately named conceptual-audit fallback constant rather than borrowing the purity constant.

- **Use one precedence rule.** Delegate lookup to the shell resolver from step 1. A present phase setting wins; if it is absent, use `PLAN_TOOL_CLAUDE_TIMEOUT`; if both are absent, use that phase’s default. A present zero, negative, or malformed phase value means no timeout for that phase and must mask a positive legacy value.

- **Keep purity per call, not pass-wide.** Continue to enter `plan_tool/shell.py:scoped_claude_timeout` outside the existing loop in `plan_tool/cli/completeness_phases.py:_collect_purity_split_findings`. The shell reads the active scope for every backend subprocess, so each eligible step receives the same per-call allowance without turning it into one budget for all scans.

- **Scope the audit phase around the audit call.** Resolve the conceptual setting in `_sample_conceptual_audit` and keep `audit_plan_until_stable` inside that scope. Each audit pass must therefore receive the conceptual per-call timeout while the existing `max_passes`, `dry_rounds`, reporter, telemetry, advisory, and returned recommendations stay unchanged.

- **Keep timeout ownership in the shell layer.** Do not add direct `os.environ` reads or timeout parsing back to `plan_tool/cli/completeness_phases.py`. Do not add a timeout parameter to `plan_tool/review.py:audit_plan_until_stable`; the dynamic scope is sufficient for this phase helper and preserves that shared function’s public contract.

- **Update operator guidance.** Change the timeout recovery text produced by `_purity_scan_failed_finding` and `_render_grouped_report` to name `PLAN_TOOL_PURITY_CLAUDE_TIMEOUT`, not the legacy global setting.

- **Preserve audit meaning.** Do not alter purity cache behavior, skipped-step rules, timeout classification, retries, `purity-scan-failed` coverage findings, or the conceptual audit’s finding union.

## Tests

### Tests for this step

- `tests/cli/test_completeness_cmd.py:TestRunDeterministicChecks.test_purity_timeout_uses_its_phase_setting` — Records the active shell timeout during a real purity producer call and proves phase setting, legacy fallback, phase default, and explicit disabled phase values.

- `tests/cli/test_completeness_cmd.py:TestSampleConceptualAudit.test_conceptual_timeout_uses_its_phase_setting` — Records the active timeout inside the conceptual audit seam and proves it is scoped through `_sample_conceptual_audit`.

- `tests/cli/test_completeness_cmd.py:TestRenderGroupedReport.test_purity_timeout_recovery_hint_names_phase_setting` — Confirms purity coverage output recommends the purity-specific setting.

- `tests/test_cli.py:TestCmdCompletenessConceptWiring.test_audit_only_conceptual_timeout_reaches_invoker` — Runs `main()` with distinct conceptual and legacy values and confirms the conceptual backend sees the phase value.

Every listed test must be green before this step is complete.

## Acceptance criteria

- `PLAN_TOOL_PURITY_CLAUDE_TIMEOUT` affects only eligible calls made by `plan_tool/cli/completeness_phases.py:_collect_purity_split_findings`.

- `PLAN_TOOL_CONCEPTUAL_AUDIT_CLAUDE_TIMEOUT` affects each backend call made by `plan_tool/cli/completeness_phases.py:_sample_conceptual_audit`.

- With both phase settings absent, `PLAN_TOOL_CLAUDE_TIMEOUT` remains the fallback for both phases.

- With a phase setting and a different positive legacy value present, the phase setting is the effective timeout.

- A zero, negative, or malformed phase setting disables only that phase’s timeout and does not fall back to a positive legacy value.

- With no applicable setting, each phase uses its own named default; purity remains at `PURITY_CLAUDE_TIMEOUT_S`.

- Purity timeout recovery text names `PLAN_TOOL_PURITY_CLAUDE_TIMEOUT`.

- The focused tests in `tests/cli/test_completeness_cmd.py` and `tests/test_cli.py` pass.

## References

- [Python `contextvars`](https://docs.python.org/3/library/contextvars.html) — Verify token-based dynamic scope behavior and restoration.

- [Python `os.getenv`](https://docs.python.org/3/library/os.html#os.getenv) — Review environment lookup and absent-value behavior used by the shell resolver.

- [Python `subprocess`](https://docs.python.org/3/library/subprocess.html) — Confirm the scoped value continues to feed per-call subprocess timeout handling.

- [pytest monkeypatch fixture](https://docs.pytest.org/en/stable/how-to/monkeypatch.html) — Use reversible environment and domain-seam patches for precedence tests.

## Applicable guardrails

- **The plan’s “## Step intent”, separate audit sizing:** Limit the behavior change to the purity and conceptual-audit phase helpers. Preserve timeout behavior for unscoped callers.

- **The plan’s “## Out of scope”, backend and recovery policy:** Do not change timeout classification, retry behavior, rate-limit handling, or backend protocols while wiring the two settings.

- **The plan’s “## Out of scope”, command and configuration surface:** Do not add CLI flags or a persisted configuration format. The two environment settings are the only new operator controls in this step.

- **The plan’s “## Out of scope”, purity status and verdicts:** Keep `--purity` optional and preserve advisory MIXED-STEP verdict handling.

## Deferred

- `plan_tool/cli/completeness_phases.py:_run_iterate_convergence_loop` directly calls `plan_tool/review.py:audit_plan_until_stable` instead of `_sample_conceptual_audit`, so it bypasses this step’s conceptual scope. Reconcile whether iterate-mode conceptual calls must consume the same setting before widening this step’s declared file list.
