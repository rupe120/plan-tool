> **Replaced**: this file has been superseded by `docs/implementation-plans/2-plan-quota-recovery.md`.
> Preserved here for history; do not edit.

# Plan seed: Plan quota recovery

## Outcome

`plan-tool` will recognize a provider's monthly plan-quota exhaustion as
different from a short rate limit. One completeness-audit invocation will end
with a bounded, actionable quota outcome instead of its one-hour fallback wait
or repeated pass-level retries; ordinary short rate limits will retain their
current recovery behavior.

## Overview

This resolves the confirmed BUG "A monthly plan-quota exhaustion is classified
and retried exactly like a short rate limit" in `BUG_BACKLOG.md`. It changes
only the classification and recovery path needed to distinguish a quota that
cannot clear during the invocation from a rate limit that can.

## Problem statement

At HEAD, `plan_tool/claude_errors.py:classify` maps provider-limit and
rate-limit copy into `RATE_LIMIT`; `parse_reset_epoch` cannot read "monthly
cycle ends on <date>". `plan_tool/rate_limit_loop.py:run_with_rate_limit_recovery`
therefore applies its 3600-second no-reset fallback and one retry to the quota.
`plan_tool/review.py:audit_plan_until_stable` invokes recovery separately for
its conceptual passes, so the same invocation can pay that hopeless wait again.

## Architecture

High-confidence plan-quota copy becomes distinguishable from generic
rate-limit copy while preserving the shared recovery leaf's caller-agnostic
boundary. The plan will define the smallest representation and mapping needed
to carry the quota's actionable hint and any parseable monthly-cycle reset date
to its consumers. A short rate limit remains recoverable under its current
wait, switch, prompt, and retry policy.

Quota memory is invocation-local. A later conceptual pass that receives the
same unresolved plan-quota condition will stop through the established
reporting path without launching another wait/retry cycle; a separate command
invocation starts without that memory. No persistent quota cache or global
backend state is introduced.

## In scope

- The error classification, monthly-cycle reset-date parsing, and recovery
  mapping that distinguish plan quotas from short rate limits.
- The completeness-audit invocation boundary that prevents duplicate handling
  of the same unresolved quota across conceptual passes.
- Shared batch and streaming consumer behavior where the new classification
  reaches the existing recovery seam.
- Deterministic regression coverage and the source `BUG_BACKLOG.md` closure
  once the shipped behavior is verified.

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
- **State leak:** sharing quota state beyond one audit could suppress a later,
  independent recovery. Keep the circuit breaker at the invocation boundary
  and prove a new invocation is independent.
- **Misleading recovery:** parsing a date without changing the fallback could
  still cause a long, futile wait. The selected mapping must make the quota
  outcome bounded and actionable before another backend call is attempted.

## Testing

Use deterministic classifier and parser fixtures for the observed monthly
quota wording, including a fixed clock for its reset date. Prove that the
quota outcome never takes the ordinary fallback wait or retries the same
provider in that invocation, while existing short-rate-limit fixtures keep
their wait/retry behavior. Exercise the conceptual multi-pass boundary with
injected invokers: identical quota evidence reaches the provider at most once
per audit invocation, later passes receive the bounded outcome, and a separate
invocation does not inherit the earlier state. No external backend is needed.

## Acceptance criteria

- Explicit plan-quota copy is distinguishable from an ordinary short rate
  limit and gives the operator an actionable bounded outcome with reset context
  when it is available.
- A plan quota does not enter the generic one-hour fallback wait or retry the
  same provider during the affected recovery attempt.
- One completeness-audit invocation does not repeat handling of identical
  unresolved plan-quota evidence across conceptual passes; independent
  invocations remain independent.
- Existing short-rate-limit recovery behavior remains covered and unchanged.
- Deterministic tests cover classification, reset parsing, recovery, and the
  multi-pass boundary; the resolved BUG entry is removed from `BUG_BACKLOG.md`.

## Deferred

File any provider-specific quota variants that lack the explicit plan-quota
markers, alternative-backend policy changes, or durable quota coordination in
`BUG_BACKLOG.md` or `BACKLOG.md`. This plan owns only the confirmed behavior
above.
