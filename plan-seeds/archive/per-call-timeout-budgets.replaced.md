> **Replaced**: this file has been superseded by `docs/implementation-plans/archive/2-per-call-timeout-budgets.md`.
> Preserved here for history; do not edit.

# Plan seed: phase-specific completeness timeout budgets

This seed implements the `BUG_BACKLOG.md` entry **“Per-call timeout budgets
are still one global knob.”** Remove that entry only when the shipped behavior
and focused regression tests below are green.

## Outcome

`completeness-audit` independently bounds conceptual-audit calls and optional
per-step purity scans, while a pass-wide purity ceiling prevents a stalled
scan battery from consuming one full per-call budget for every remaining step.

## In scope

- Timeout resolution in `plan_tool/shell.py` and its unit tests.
- The conceptual-audit and purity-scan call scopes in
  `plan_tool/cli/completeness_phases.py`, including truthful coverage reporting
  when the purity ceiling leaves readable steps unscanned.
- Focused completeness CLI tests, operator-facing timeout guidance, and the
  originating `BUG_BACKLOG.md` entry.

## Overview

Replace the one-size global operational dial with phase-specific environment
settings. Keep `PLAN_TOOL_CLAUDE_TIMEOUT` as the compatibility fallback when a
phase has no explicit setting; it continues to govern unscoped callers. A
phase-specific variable wins when present, including its existing `0`,
negative, and malformed-value meaning of no timeout. Absent both overrides,
purity and conceptual calls use independently documented defaults.

Purity needs two limits: a per-scan deadline and a finite wall-clock allowance
for the whole scan battery. Once the total allowance is exhausted, do not start
another backend call. Record every otherwise-readable skipped step as a
blocking coverage gap whose wording makes the cause explicit, rather than
calling it a failed or clean scan. This preserves the current honesty rule:
no missing MIXED-STEP verdict may look like a clean or low-yield audit.

## Problem statement

The current global `PLAN_TOOL_CLAUDE_TIMEOUT` can shorten or lengthen every
backend call but cannot express the different cost profiles of a conceptual
audit and a bounded per-step purity probe. With no pass-wide purity limit, a
plan with many slow steps can spend the full per-scan allowance repeatedly
after the audit has already lost coverage. Operators need independent, named
knobs and the report must distinguish an unavailable scan from a legitimate
empty verdict.

## Architecture

- Add a single shell-owned resolver for a named phase setting, the legacy
  global fallback, and a phase default. Preserve the parser's established
  positive-seconds-only semantics and dynamic timeout scopes; do not add a CLI
  flag or a persisted configuration schema.
- Give the conceptual audit and purity scan separate named environment
  settings and defaults. The generic setting remains a fallback, so existing
  invocation recipes retain their current behavior until a phase setting is
  deliberately supplied.
- Add a purity-only total wall-clock setting with a conservative finite
  default. Measure it monotonically across the scan loop, use no more than the
  remaining allowance for an in-flight scan, and abandon subsequent scans when
  no allowance remains. A disabled total setting explicitly retains the
  unbounded batch behavior for diagnosis.
- Preserve completed or non-code step skipping, cache reuse, terminal timeout
  classification, and the non-blocking status of genuine purity split advice.
  Only uncovered readable steps become blocking coverage findings.

## Out of scope

- Changing retry classification, rate-limit recovery, backend protocols, or
  timeout policy for create, detail, run, Jira, review, or unrelated batch
  calls.
- CLI flags, config-file schema, adaptive timeout tuning, parallel scans, or
  changing the optional status of `--purity`.
- Rejudging a returned purity verdict or making advisory MIXED-STEP findings
  block execution.

## Risks

- A precedence mistake can silently break established global timeout recipes.
  Pin explicit-phase, legacy-fallback, default, and disabled-value cases.
- A total ceiling can under-report unscanned steps or launch a call after the
  limit. Use an injected/patchable monotonic clock and assert both the exact
  backend-call count and a coverage finding for each skipped readable step.
- A scope around the whole conceptual multi-pass loop must still limit each
  backend call rather than treating all passes as one call. Test that its
  dynamic scope reaches the invoker and that purity and conceptual settings do
  not bleed into each other.

## Testing

Test the shell resolver's precedence and compatibility contract, the timeout
value observed by each completeness phase, and purity-ceiling behavior with
controlled elapsed time. Cover successful scans, timeout/empty scans, cached
or unreadable steps, and the zero/invalid escape hatch. Run the focused shell
and completeness CLI classes plus the full affected test modules and lint.

## Acceptance criteria

- An operator can set purity and conceptual per-call budgets independently;
  an unset phase uses the legacy global setting when present and otherwise its
  documented default.
- The legacy global variable continues to bound unscoped callers and remains a
  backward-compatible fallback for both completeness phases.
- A purity battery never starts a call beyond its enabled pass-wide allowance;
  every skipped readable step is reported as unscanned coverage and blocks the
  audit instead of reading clean or low-yield.
- Disabling or supplying a malformed phase setting preserves the existing
  no-timeout escape-hatch semantics without changing any unrelated caller.
- `BUG_BACKLOG.md` removes this entry only after the implementation and its
  focused regression coverage are complete.

## Deferred

- Adaptive budgets from historical telemetry, a user-visible timeout dashboard,
  and timeout-policy changes outside completeness belong in separate backlog
  work if evidence warrants them.
