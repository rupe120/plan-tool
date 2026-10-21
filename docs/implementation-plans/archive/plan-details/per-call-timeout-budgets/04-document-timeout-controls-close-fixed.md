# Step 4 — Document the timeout controls and close the fixed bug entry

## Summary

Document the completed completeness-audit timeout controls in `docs/cli/completeness-audit.md` and their execution order in `docs/AUDIT_FLOW.md`. Remove the resolved `Per-call timeout budgets are still one global knob` card from `BUG_BACKLOG.md`. Keep the operator guidance centered on the difference between per-call phase limits, the purity battery’s total limit, and the legacy fallback. On green, operators can select or disable the right control without confusing it with the convergence-loop time budget, and the backlog contains no open card for the shipped defect.

## Table of Contents

- [Summary](#summary) — The completed documentation and backlog outcome.
- [Table of Contents](#table-of-contents) — Links to each section in this detail.
- [Why](#why) — Why the new controls need one accurate operator explanation.
- [Input](#input) — The step-2 and step-3 contracts the documentation must reflect.
- [Files (creates vs edits)](#files-creates-vs-edits) — The three documentation-only edits.
- [Implementation](#implementation) — Required timeout meanings, flow placement, and backlog closure.
- [Tests](#tests) — Non-code verification for the documentation and its source anchors.
- [Acceptance criteria](#acceptance-criteria) — Reviewable outcomes for the completed step.
- [References](#references) — Primary references for the documented timeout behavior.
- [Applicable guardrails](#applicable-guardrails) — Plan boundaries that limit this docs step.

## Why

After steps 2 and 3, `completeness-audit` has separate controls for purity calls, conceptual-audit calls, and the whole purity battery, while `docs/cli/completeness-audit.md` currently explains only the `--purity` switch and `docs/AUDIT_FLOW.md` does not place the optional battery in the audit sequence. Without a clear distinction, an operator can change the legacy global setting or `--time-budget` expecting it to control the wrong work. `BUG_BACKLOG.md` must stop describing the shipped behavior as an open defect once the implementation, tests, and documentation agree.

## Input

- **Step 2 phase controls:** Read the landed `PLAN_TOOL_PURITY_CLAUDE_TIMEOUT` and `PLAN_TOOL_CONCEPTUAL_AUDIT_CLAUDE_TIMEOUT` behavior from `plan_tool/cli/completeness_phases.py:_collect_purity_split_findings` and `plan_tool/cli/completeness_phases.py:_sample_conceptual_audit`. The landed code, including its defaults, wins over either earlier detail file.

- **Step 3 purity-battery control:** Read the landed `PLAN_TOOL_PURITY_SCAN_BUDGET` behavior from `plan_tool/cli/completeness_phases.py:_collect_purity_split_findings` and its `purity_coverage_recs` output. The docs must distinguish a scan that ran and failed from a readable eligible step skipped after the battery budget expired.

- **Shared timeout and existing CLI contract:** `plan_tool/shell.py:scoped_claude_timeout` and `plan_tool/shell.py:_effective_subprocess_timeout` establish that a phase limit applies to each backend call. The `--time-budget` row in `docs/cli/completeness-audit.md` remains the separate cooperative convergence-loop cap.

## Files (creates vs edits)

- **New files:** None.

- **Existing files (edits only):**
  - `docs/cli/completeness-audit.md` — Add a timeout-controls section and update the `--purity` guidance to point operators to it.
  - `docs/AUDIT_FLOW.md` — Add the optional purity battery and its timeout boundaries to the completeness flow, then update the `## Source map`.
  - `BUG_BACKLOG.md` — Remove only the `### Per-call timeout budgets are still one global knob` card after verifying the shipped behavior.

## Implementation

- **Make `docs/cli/completeness-audit.md` the operator reference.** Add a clearly named timeout-controls section after the option table. Keep CLI syntax unchanged: these are environment settings, not new flags.

- **Document the three scopes separately.** Explain that `PLAN_TOOL_PURITY_CLAUDE_TIMEOUT` bounds each eligible purity scan, `PLAN_TOOL_CONCEPTUAL_AUDIT_CLAUDE_TIMEOUT` bounds each backend call made by the conceptual audit, and `PLAN_TOOL_PURITY_SCAN_BUDGET` limits the full optional purity battery.

- **Document the legacy fallback precisely.** State that an absent phase-specific per-call setting allows `PLAN_TOOL_CLAUDE_TIMEOUT` to supply the per-call limit, while the global setting still serves its existing unscoped callers. Do not describe the global setting as the purity battery’s total budget.

- **Document disabled values precisely.** State the landed meaning of zero, negative, and malformed values for each phase setting and the purity-battery setting. A disabled phase setting must be described as masking a positive legacy setting for that phase; a disabled purity-battery setting must be described as retaining the unbounded battery behavior.

- **Publish real defaults and units.** Copy the shipped defaults from the landed constants and express them in seconds. Keep `plan_tool/cli/completeness_phases.py:PURITY_CLAUDE_TIMEOUT_S` as the orientation point for the purity default; do not guess or duplicate a conceptual-audit default from an earlier plan detail.

- **Preserve purity’s meaning.** Update the `--purity` row only to explain that it enables the optional battery and to point to the timeout section. Keep returned MIXED-STEP split advice advisory, while explaining that failed or budget-skipped coverage is blocking.

- **Add the flow at the right level.** In `docs/AUDIT_FLOW.md`’s `## completeness — conceptual audit (deterministic + multi-pass claude audit)` section, describe the optional purity battery as a separate Claude-backed check between the free deterministic checks and the conceptual-audit explanation. State that each call has its phase limit, the battery stops admitting calls when its total allowance ends, and skipped eligible scans become blocking coverage gaps.

- **Keep flow and reference-doc roles separate.** Let `docs/cli/completeness-audit.md` own the full settings table, values, and precedence rule. Let `docs/AUDIT_FLOW.md` explain execution order and outcomes, with a link to the CLI reference instead of repeating the full table.

- **Update the source map.** Add or extend a `docs/AUDIT_FLOW.md` `## Source map` row for timeout control selection, citing `plan_tool/cli/completeness_phases.py:_collect_purity_split_findings`, `plan_tool/cli/completeness_phases.py:_sample_conceptual_audit`, `plan_tool/shell.py:scoped_claude_timeout`, and `plan_tool/shell.py:_effective_subprocess_timeout`.

- **Keep `--time-budget` distinct.** Do not imply that the convergence-loop budget kills an in-flight conceptual or purity call, and do not make the new environment variables sound like replacements for that flag.

- **Close the backlog entry last.** After verifying the implementation and focused timeout regressions, delete the complete `### Per-call timeout budgets are still one global knob` card from `BUG_BACKLOG.md`. Leave the `## BUG` heading and adjacent cards unchanged; do not replace the removed card with a shipped-status note.

## Tests

### Verification (non-code step)

This step is `change_type: non-code`, so the plan’s `enforce_step_tests: true` gate does not require new test coverage. Verify the documentation against the landed implementation and the upstream regression suites.

- **Timeout regression suites** — Run `tests/test_shell.py`, `tests/cli/test_completeness_cmd.py`, and `tests/test_cli.py`; the step-1 through step-3 timeout, scope, skipped-coverage, and command-wiring cases pass.

- **Control inventory** — Confirm `docs/cli/completeness-audit.md` names `PLAN_TOOL_PURITY_CLAUDE_TIMEOUT`, `PLAN_TOOL_CONCEPTUAL_AUDIT_CLAUDE_TIMEOUT`, `PLAN_TOOL_PURITY_SCAN_BUDGET`, and `PLAN_TOOL_CLAUDE_TIMEOUT`.

- **Precedence check** — Compare the CLI reference’s phase-specific, legacy-fallback, default, and disabled-value statements with the resolver used by `plan_tool/shell.py:_effective_subprocess_timeout`.

- **Scope check** — Confirm the CLI and flow docs say the conceptual setting applies per backend call, the purity setting applies per eligible scan, and only `PLAN_TOOL_PURITY_SCAN_BUDGET` limits the whole purity battery.

- **Source-map freshness** — Grep each timeout symbol cited in `docs/AUDIT_FLOW.md` against `plan_tool/` and confirm every anchor exists.

- **Backlog closure check** — Confirm `BUG_BACKLOG.md` has no `### Per-call timeout budgets are still one global knob` heading and no remaining text that calls the shipped defect open.

## Acceptance criteria

- `docs/cli/completeness-audit.md` contains a timeout-controls section that names all four timeout environment settings.

- The CLI reference accurately states the per-call precedence order: phase setting, legacy global fallback, then that phase’s default.

- The CLI reference accurately states the disabled-value behavior for phase settings and for `PLAN_TOOL_PURITY_SCAN_BUDGET`.

- The CLI reference distinguishes the purity battery’s total limit from `--time-budget`.

- `docs/AUDIT_FLOW.md` describes the optional purity battery’s position in the audit flow, per-call limits, total-budget admission rule, and blocking skipped-coverage outcome.

- `docs/AUDIT_FLOW.md`’s `## Source map` cites live timeout-control symbols.

- `BUG_BACKLOG.md` no longer contains the fixed per-call-timeout card, while adjacent backlog entries remain.

- The timeout-focused suites in `tests/test_shell.py`, `tests/cli/test_completeness_cmd.py`, and `tests/test_cli.py` pass.

## References

- [Python subprocess — Subprocess management](https://docs.python.org/3/library/subprocess.html) — Confirm that the documented per-call timeout corresponds to the subprocess boundary.

- [Python time — time.monotonic](https://docs.python.org/3/library/time.html#time.monotonic) — Confirm why the purity-battery limit measures elapsed wall-clock time independently of individual calls.

- [Python contextvars — Context Variables](https://docs.python.org/3/library/contextvars.html) — Confirm the dynamic timeout-scope behavior described by the flow source map.

- [Python os — os.getenv](https://docs.python.org/3/library/os.html#os.getenv) — Confirm environment lookup and absent-value behavior behind the documented precedence rule.

## Applicable guardrails

- **The plan’s “## Plan intent”, independent bounds** — Document the separate conceptual, per-step purity, and full-battery controls without merging their meanings.

- **The plan’s “## Step intent”, operator guidance and bug closure** — Limit this step to explaining the landed controls and closing the originating backlog entry.

- **The plan’s “## Out of scope”, command and configuration surface** — Do not document a new command option or configuration format beyond the controls delivered by steps 2 and 3.

- **The plan’s “## Out of scope”, purity semantics** — Keep `--purity` optional and preserve the distinction between advisory returned verdicts and blocking lost coverage.
