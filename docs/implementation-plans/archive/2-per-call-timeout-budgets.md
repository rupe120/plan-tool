> **Archived:** this completed plan moved here on 2026-08-20 after all steps reached `done`.

---
title: Per Call Timeout Budgets
intent: '`completeness-audit` independently bounds conceptual-audit calls and optional
  per-step purity scans, while a pass-wide purity ceiling prevents a stalled scan
  battery from consuming one full per-call budget for every remaining step.'
status: completed
priority: medium
enforce_step_tests: true
steps:
- id: 1
  title: Move the existing purity timeout lookup into the shell layer
  intent: Keeps timeout precedence in one shared place before completeness phases
    gain their own settings.
  files:
  - plan_tool/shell.py
  - plan_tool/cli/completeness_phases.py
  - tests/test_shell.py
  - tests/cli/test_completeness_cmd.py
  complexity: medium
  change_type: refactor
  detail: docs/implementation-plans/plan-details/per-call-timeout-budgets/01-move-existing-purity-timeout-lookup.md
  status: done
  status_note: 'delivered in b173b51b (2026-08-04), an ancestor of HEAD, before
    this plan was authored — resolve_claude_timeout/scoped_claude_timeout already
    live in plan_tool/shell.py and completeness_phases.py already calls them.
    Confirmed by reconcile-plan 2026-08-19; see plan Overview.'
- id: 2
  title: Give purity scans and conceptual audits separate timeout settings
  intent: Lets operators size conceptual audit calls and purity scan calls independently
    without changing unscoped callers.
  files:
  - plan_tool/cli/completeness_phases.py
  - tests/cli/test_completeness_cmd.py
  - tests/test_cli.py
  complexity: medium
  change_type: feature
  depends_on:
  - 1
  detail: docs/implementation-plans/plan-details/per-call-timeout-budgets/02-give-purity-scans-conceptual-audits.md
  status: done
  status_note: 'delivered in b173b51b (2026-08-04): PURITY_CLAUDE_TIMEOUT_ENV
    and CONCEPTUAL_AUDIT_CLAUDE_TIMEOUT_ENV are both live in
    completeness_phases.py with dedicated tests. Confirmed by reconcile-plan
    2026-08-19; see plan Overview.'
- id: 3
  title: Cap the full purity scan and report skipped steps
  intent: Prevents a stalled purity battery from starting more backend calls while
    making lost scan coverage visible and blocking.
  files:
  - plan_tool/cli/completeness_phases.py
  - tests/cli/test_completeness_cmd.py
  - tests/test_cli.py
  complexity: high
  change_type: feature
  depends_on:
  - 2
  detail: docs/implementation-plans/plan-details/per-call-timeout-budgets/03-cap-full-purity-scan-report-skipped.md
  status: done
  status_note: 'delivered in b173b51b (2026-08-04): PURITY_SCAN_BUDGET_S/
    PURITY_SCAN_BUDGET_ENV, the monotonic pass-budget clamp, and the blocking
    purity-scan-skipped coverage finding are all live in completeness_phases.py
    with tests. Confirmed by reconcile-plan 2026-08-19; see plan Overview.'
- id: 4
  title: Document the timeout controls and close the fixed bug entry
  intent: Tells operators how the phase budgets and disabled escape hatches work,
    then records the originating bug as shipped.
  files:
  - docs/cli/completeness-audit.md
  - docs/AUDIT_FLOW.md
  - BUG_BACKLOG.md
  complexity: medium
  change_type: non-code
  depends_on:
  - 2
  - 3
  detail: docs/implementation-plans/plan-details/per-call-timeout-budgets/04-document-timeout-controls-close-fixed.md
  status: done
  status_note: 'delivered in b173b51b (2026-08-04): docs/cli/completeness-audit.md
    and docs/AUDIT_FLOW.md already document all three settings, and
    BUG_BACKLOG.md no longer carries the "Per-call timeout budgets are still one
    global knob" entry it named (removed in the same commit). Confirmed by
    reconcile-plan 2026-08-19; see plan Overview.'
---
# Per Call Timeout Budgets

## Overview

**Retroactively marked complete 2026-08-19.** This plan (authored
2026-08-04, `5bc8acd8`) and commit `b173b51b` ("fix(completeness): isolate
audit timeout budgets", also 2026-08-04) landed within seconds of each
other; `b173b51b` shipped this plan's full four-step scope directly — the
shell-owned timeout resolver, the separate purity/conceptual-audit env
settings, the pass-wide purity scan budget with a blocking skipped-step
finding, and the accompanying docs and `BUG_BACKLOG.md` closure — before
this plan/detail bundle was ever executed. `plan-tool reconcile-plan
--all` confirmed every deliverable already on disk and tested at HEAD
(2026-08-19). No implementation work remains; the section below records
the design this plan called for, all of which the direct commit already
satisfies.

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

## References

- [Python subprocess — Subprocess management](https://docs.python.org/3/library/subprocess.html) — Defines subprocess.run timeout behavior, including child termination and TimeoutExpired handling for the backend call boundary.
- [Python time — time.monotonic](https://docs.python.org/3/library/time.html#time.monotonic) — Documents the non-adjustable monotonic clock appropriate for enforcing a pass-wide wall-clock budget.
- [Python contextvars — Context Variables](https://docs.python.org/3/library/contextvars.html) — Covers ContextVar set/reset semantics needed to preserve nested dynamic per-call timeout scopes.
- [Python os — os.getenv](https://docs.python.org/3/library/os.html#os.getenv) — Specifies environment-variable lookup behavior relevant to resolving phase overrides, legacy fallback, and defaults.
- [pytest monkeypatch fixture](https://docs.pytest.org/en/stable/how-to/monkeypatch.html) — Shows reversible environment and attribute patching for precedence and injected-clock regression tests.
- [Anthropic Claude Code CLI reference](https://docs.anthropic.com/en/docs/claude-code/cli-usage) — Documents Claude's non-interactive print mode and output controls used by the subprocess-backed invoker.

## Steps

See the `steps:` block in the frontmatter.

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

**Per-step test strategy** (derived from each step's `change_type`):

- step 1 (refactor) — tests covering the behavior this step changes; green before completion.
- step 2 (feature) — tests covering the behavior this step changes; green before completion.
- step 3 (feature) — tests covering the behavior this step changes; green before completion.
- step 4 (non-code) — verification appropriate to the artifacts rather than unit tests.

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
