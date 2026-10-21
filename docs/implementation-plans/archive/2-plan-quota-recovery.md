> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

---
title: Plan Quota Recovery
intent: '`plan-tool` will recognize a provider''s monthly plan-quota exhaustion as
  different from a short rate limit. One completeness-audit invocation will end with
  a bounded, actionable quota outcome instead of its one-hour fallback wait or repeated
  pass-level retries; ordinary short rate limits will retain their current recovery
  behavior.'
status: completed
priority: medium
test_command: uv run pytest tests/ -q -n auto
enforce_step_tests: true
source_seed: docs/implementation-plans/plan-seeds/plan-quota-recovery.md
steps:
- id: 1
  title: Add provider-scoped plan-quota detection and date-only reset context
  intent: Make explicit monthly quota evidence and its stated reset date available
    as deterministic inputs without turning a date-only provider message into an invented
    local instant.
  files:
  - integrations/cursor/backend.json
  - plan_tool/backend.py
  - plan_tool/claude_errors.py
  - tests/test_backend.py
  - tests/test_claude_errors.py
  complexity: medium
  change_type: feature
  detail: docs/implementation-plans/plan-details/plan-quota-recovery/01-provider-scoped-plan-quota-detection.md
  status: done
- id: 2
  title: Return explicit plan quotas as terminal outcomes in batch and streaming recovery
  intent: Prevent monthly quotas from entering every rate-limit recovery action —
    fallback wait, prompt, switch, and retry — while preserving ordinary short- limit
    recovery in both callers.
  files:
  - plan_tool/claude_errors.py
  - plan_tool/launcher.py
  - plan_tool/rate_limit_loop.py
  - plan_tool/shell.py
  - tests/test_claude_errors.py
  - tests/test_launcher.py
  - tests/test_rate_limit_loop.py
  - tests/test_shell.py
  complexity: medium
  change_type: feature
  depends_on:
  - 1
  depends_on_notes:
    1: Uses the provider-scoped quota evidence and date-only reset context to select
      the terminal recovery outcome.
  detail: docs/implementation-plans/plan-details/plan-quota-recovery/02-return-explicit-plan-quotas-terminal.md
  status: done
- id: 3
  title: Stop the conceptual audit after a plan-quota outcome and keep coverage unconfirmed
  intent: Prevent one completeness audit from making any later conceptual-pass provider
    call after a terminal plan-quota outcome, while keeping the failed audit visibly
    incomplete.
  files:
  - DATA_CONTRACT.md
  - docs/cli/completeness-audit.md
  - plan_tool/cli/completeness_cmd.py
  - plan_tool/cli/completeness_phases.py
  - plan_tool/review.py
  - plan_tool/review_persistence.py
  - tests/cli/test_completeness_cmd.py
  - tests/test_convergence.py
  - tests/test_data_contract.py
  - tests/test_review.py
  - tests/test_review_persistence.py
  complexity: high
  change_type: feature
  depends_on:
  - 2
  depends_on_notes:
    2: Carries the terminal quota outcome to the audit's stop condition before a later
      conceptual pass can open another provider recovery loop.
  detail: docs/implementation-plans/plan-details/plan-quota-recovery/03-stop-conceptual-audit-after-plan-quota.md
  status: done
- id: 4
  title: Update quota recovery references for providers and operators
  intent: Keep every maintained description of failure kinds, recovery policy, and
    conceptual-audit behavior aligned with the shipped quota handling.
  files:
  - README.md
  - RUNBOOK.md
  - docs/ARCHITECTURE.md
  - docs/how-to/pipeline/audit.md
  - docs/reference/contracts/codex-cli.md
  - docs/reference/contracts/cursor-agent-cli.md
  - docs/how-to/pipeline/run.md
  - docs/how-to/roadmap-demo.md
  - docs/design-plans/BACKEND_SELECTION.md
  - DATA_CONTRACT.md
  - integrations/claude/SKILL.md
  - integrations/codex/SKILL.md
  - plan_tool/cli/parser.py
  - tests/cli/package_surface_help.golden.txt
  complexity: high
  change_type: non-code
  depends_on:
  - 1
  - 2
  - 3
  depends_on_notes:
    1: Documents the landed provider evidence and date-only reset-context contract.
    2: Documents the terminal shared-recovery behavior and unchanged short-limit policy.
    3: Documents the audit-stop rule and the resulting incomplete-audit outcome.
  detail: docs/implementation-plans/plan-details/plan-quota-recovery/04-update-quota-recovery-references.md
  status: done
- id: 5
  title: Remove the resolved quota bug and refresh its queue entries
  intent: Stop presenting the shipped quota fix as active work and leave the project
    queues pointing at the next live priority.
  files:
  - BACKLOG.md
  - BUG_BACKLOG.md
  - docs/implementation-plans/backlog-arcs/bug-backlog-draining-arc.md
  complexity: medium
  change_type: non-code
  depends_on:
  - 4
  depends_on_notes:
    4: Closes the source records only after the implementation, tests, and maintained
      documentation agree.
  detail: docs/implementation-plans/plan-details/plan-quota-recovery/05-remove-resolved-quota-bug-refresh-its.md
  status: done
---
# Plan Quota Recovery

## Overview

This resolves the confirmed BUG "A monthly plan-quota exhaustion is classified
and retried exactly like a short rate limit" in `BUG_BACKLOG.md`. It changes
only the classification and recovery path needed to distinguish a quota that
cannot clear during the invocation from a rate limit that can.

## Problem statement

At HEAD, `plan_tool/claude_errors.py:classify` maps provider-limit and
rate-limit copy into `RATE_LIMIT`; `parse_reset_epoch` has only a time-bearing
epoch contract, so it cannot safely represent "monthly cycle ends on <date>"
without inventing a local reset hour. `plan_tool/rate_limit_loop.py:run_with_rate_limit_recovery`
therefore applies its 3600-second no-reset fallback and one retry to the quota.
`plan_tool/review.py:audit_plan_until_stable` invokes recovery separately for
its conceptual passes, so the same invocation can pay that hopeless wait again.

## Architecture

High-confidence plan-quota copy becomes distinguishable from generic
rate-limit copy while preserving the shared recovery leaf's caller-agnostic
boundary. A monthly-cycle date remains date-only operator context: it is shown
without an invented hour or time zone and never enters the epoch-based wait
path. A plan quota is terminal in both batch and streaming callers, bypassing
every rate-limit recovery action — wait, prompt, switch, and retry. A short
rate limit remains recoverable under its current policy.

The first plan-quota outcome ends the current conceptual-audit pass loop through
the established incomplete-coverage reporting path. It does not cache, compare,
or replay quota evidence: later passes simply do not start. A separate command
invocation starts fresh. No persistent quota cache or global backend state is
introduced.

## References

- [Models & Pricing | Cursor Docshttps: — Defines Cursor's monthly usage pools, billing-cycle resets, and operator options after included usage is exhausted.
- [Output format | Cursor Docshttps: — Specifies batch and streaming CLI output, nonzero failure behavior, and stderr error delivery.
- [Cursor Python SDK — Errorshttps: — Documents Cursor's error taxonomy, retryability metadata, and Retry-After handling for rate and usage limits.
- [RFC 6585 — 429 Too Many Requestshttps: — Defines HTTP 429 rate-limiting semantics and the optional delay before retrying.
- [RFC 9110 — Retry-Afterhttps: — Defines Retry-After delay-seconds and HTTP-date forms for standards-compliant recovery logic.
- [datetime — Basic date and time typeshttps: — Covers Python date parsing, timezone-aware timestamps, arithmetic, and deterministic clock injection primitives.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

- New fallback backends, credential or spend-limit management, provider-account
  APIs, quota forecasting, persistent rate-limit/quota caches, or cross-command
  throttling coordination.
- Changing normal short-rate-limit wait, switch, prompt, or transient-retry
  behavior; generic `usage limit` copy without plan-quota evidence remains on
  its current path.
- Broader audit scheduling, audit-pass count changes, purity-pass observation,
  timeout-budget policy, or any external-backend test.

## Risks

- **False special case:** a broad pattern could turn an ordinary short rate
  limit into a terminal quota. Require the plan-quota markers that distinguish
  the observed provider copy and preserve generic-rate-limit regressions.
- **State leak:** an audit-local cache could suppress a later, independent
  recovery or hide a distinct failure. Stop the current audit loop instead of
  caching evidence, and prove a new invocation is independent.
- **Misleading recovery:** inventing a reset instant from a date-only message
  would both mislead the operator and re-enter a futile wait. Preserve the date
  as date-only context and surface the terminal quota outcome before another
  backend call is attempted.

## Testing

Use deterministic classifier and date-context fixtures for the observed monthly
quota wording. Prove that its date stays date-only and that the terminal quota
outcome bypasses wait, prompt, switch, and retry in both recovery callers,
while existing short-rate-limit fixtures keep their current policy behavior.
Exercise the conceptual multi-pass boundary with injected invokers: the first
plan-quota outcome stops the current audit, marks coverage unconfirmed, and
prevents every later pass's provider call; a separate invocation starts fresh.
The public audit coverage identifies that state as an early quota stop rather
than a pass-cap result, and it cannot become reusable evidence.
No external backend is needed.

**Per-step test strategy** (derived from each step's `change_type`):

- step 1 (feature) — tests covering the behavior this step changes; green before completion.
- step 2 (feature) — tests covering the behavior this step changes; green before completion.
- step 3 (feature) — tests covering the behavior this step changes; green before completion.
- step 4 (non-code) — verification appropriate to the artifacts rather than unit tests.
- step 5 (non-code) — verification appropriate to the artifacts rather than unit tests.

## Acceptance criteria

- Explicit plan-quota copy is distinguishable from an ordinary short rate
  limit and gives the operator an actionable bounded outcome with any monthly
  reset date shown as date-only context.
- A plan quota bypasses every rate-limit recovery action — generic fallback
  wait, prompt, switch, and retry — in both batch and streaming callers.
- The first plan-quota outcome stops the current completeness audit before a
  later conceptual pass can invoke the provider; it reports coverage
  unconfirmed with an explicit early quota-stop reason, cannot be reused, and
  leaves independent invocations independent.
- Existing short-rate-limit recovery behavior remains covered and unchanged.
- Deterministic tests cover classification, date-context extraction, recovery,
  and the multi-pass boundary; the resolved BUG entry is removed from
  `BUG_BACKLOG.md`.

## Deferred

File any provider-specific quota variants that lack the explicit plan-quota
markers, alternative-backend policy changes, or durable quota coordination in
`BUG_BACKLOG.md` or `BACKLOG.md`. This plan owns only the confirmed behavior
above.
