> **Replaced**: this file has been superseded by `docs/implementation-plans/2-completeness-stage-bar-reporting.md`.
> Preserved here for history; do not edit.

# Seed: completeness stage-bar reporting polish

## Outcome

Make completeness-audit results accurately explain what happened and what to
do next. Every human-readable report, JSON result, failure explanation, and
Jira-grade handoff distinguishes the headline result (clean, advisory-only, or
human-action stop) from independent coverage and saved-evidence qualifiers,
without changing the settled blocking, exit, or automatic-apply policy.

## In scope

- One complete, precedence-defined stop-reason vocabulary across stderr,
  persisted report, JSON, and `--fail-on-findings` guidance.
- One clear bare-plan handoff for medium completeness findings that were
  deliberately non-blocking. Existing report and stderr variants already say
  they are informational until detail exists; consolidate that wording and
  route rather than adding a second deferred-finding mechanism.
- Stage-accurate labels and next-step guidance for bare versus detail-grounded
  bars, including the post-detail/create and Jira-grade presentation paths.
- An explicit audit-input qualification when an output reuses or replays saved
  audit evidence: state whether the saved plan/detail/code snapshot still
  matches current inputs, using existing fingerprints and freshness checks.
  A live audit is already grounded on its current captured inputs and must not
  be labelled stale merely because the report is persisted afterward.
- Tests that pin the output contract at its actual CLI/report consumers.

## Overview

`stage-differentiated-blocking` shipped the core two-bar policy. Its Gate 1
reporting arm was intentionally deferred so the bar could stabilize first.
The logic now needs language that tells the operator whether work is truly
clean, deliberately advisory, awaiting a human, budget-limited, or stale.

## Problem statement

The same short output currently has to carry several distinct facts. An
operator can mistake a non-blocking bare completeness finding for a clean
plan, mistake a coverage-limited audit for a fully confirmed result, mistake
saved evidence for a current-input verdict, or receive a next command that
does not fit the grade/result. This is a communication/traceability gap, not
evidence that the blocking policy is wrong.

## Architecture

Treat stop reason, audit stage, coverage confidence, and saved-audit freshness
as independent report facts, with one documented order for the headline and
its qualifiers. Render them consistently at each consumer rather than
re-deriving a prose verdict at each call site. The bare-plan handoff
consolidates the existing informational completeness route and names its
detail-stage re-evaluation; a detail-grounded result uses its own bar name.
Reuse/replay output never receives clean-sounding guidance when the saved
audit inputs no longer match.

## Out of scope

- Changing the bare-plan or detail-grounded blocking bars, severity thresholds,
  domain classification, or pass-count policy.
- Changing which findings automatic iteration applies or placing conceptual
  findings into an apply-eligible convergence state.
- #261 policy-channel ownership, #231 bad-fix provenance, and #262 generic
  detail-readiness guidance.
- New audit scoring, new exit-code semantics beyond accurately reflecting the
  existing finalization contract, or broad report-layout restyling.

## Allowed behavior changes

- Reports, JSON, and next-step suggestions may become more specific and may
  qualify coverage-limited or stale saved evidence.
- Bare-plan medium completeness findings may receive one consolidated
  informational handoff in output.
- Existing exit, pass/fail, and apply decisions remain unchanged for the same
  inputs; `--fail-on-findings` prose may explain its established result but
  this work does not change its exit rule.

## Allowed reorganization

Extract or consolidate only shared reason/qualification rendering needed to
prevent consumer-specific prose from drifting. Keep the underlying bar and
finding predicates in their settled owners.

## Risks

- A more explicit status line can accidentally become a new gate; preserve
  existing exit/finalization semantics and test them.
- Repeating derived state across reporters can create contradictory messages;
  define precedence once and reuse it.
- A stale-saved-audit qualifier must use existing freshness evidence without
  claiming the plan is invalid or discarding useful findings.
- Jira-grade has no findings sidecar and no iterate/apply replay; its handoff
  must remain manual rather than borrowing run-grade commands.

## Testing

Exercise representative bare clean, bare advisory-only medium completeness,
detail-grounded clean, human-action stop, coverage-limited, fresh saved-audit,
and stale saved-audit outcomes. Assert one headline/qualifier order at stderr,
persisted Markdown, JSON, and next-step surfaces where applicable. Pin the
existing `--fail-on-findings` result and Jira-grade manual handoff, and prove
the same finding sets retain their previous blocking and apply decisions; only
the explanation changes.

## Acceptance criteria

- An operator can tell the headline result—clean, advisory-only, or awaiting
  action—and any coverage or saved-evidence qualifier without reading
  implementation code.
- A bare-plan medium completeness finding is visibly deferred for
  detail-grounded re-evaluation, not silently treated as absence of work.
- No stage label, stop reason, JSON field, or Jira-grade handoff claims a
  current-input clean verdict when reused evidence is stale or coverage is
  unconfirmed.
- Existing exit, blocking, and automatic-apply decisions are unchanged by this
  work.

## Deferred

Policy changes belong to #261 only if a new overlapping finding channel is
introduced; #261 is currently closed. Bad-fix provenance (#231) remains
deferred. Generic readiness recommendations remain #262. Any proposal to
change audit thresholds, pass caps, or exit behavior is separate work.
