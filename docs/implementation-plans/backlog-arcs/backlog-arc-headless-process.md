# Headless-process backlog arc

## File intent

This file is the execution guide for deferred headless human-input and
human-availability work. It sequences the remaining routes behind #322 and
the explicitly parked artifact-contention route in #353 so a proof that one
route works does not become a repository-wide migration claim.

## Details

It records the completed prerequisites, the fresh inventory required before
any next plan, and the decision boundaries between confirmation, defaulting,
free-text feedback, artifact contention, and response-record lifecycle.
`BACKLOG.md` owns #322 and #353; this file owns only their working routes.

## Choose this arc when

A named remaining direct-input or human-availability route prevents an
already-running process from operating without a terminal, and its operator
consequence needs evaluation. Do not choose this arc merely because a route
contains `input()` or resembles a completed proof. Do not use it to select a
Integration transport, a browser interface, or an all-command headless policy.

## Delivery cadence

Commit the inventory, each selected seed or plan, and each bounded result
before starting the next stage. Plan-tool work starts from a committed
baseline, uses its required bare-plan and detail-grounded audits, and keeps
green steps committed. Direct changes include focused regression coverage and
the related backlog update in one bounded commit. Do not push automatically;
push only when the user explicitly requests it.

## Completed prerequisites

- `human-input-seam` proves a `review_walk` already in progress can obtain
  command and feedback text through fail-closed filesystem request/resolution
  records. See [the implementation plan](../archive/2-human-input-seam.md).
- `headless-review-annotation-entry` proves one additional entry: eligible
  non-TTY `cmd_review` aliases can enter a closed remote skip-or-quit
  annotation walk. It adds neither feedback/action handling nor a policy for
  other callers. See [the implementation plan](../archive/2-headless-review-annotation-entry.md).
- `headless-review-walk-annotation-entry` proves the separate standalone
  entry: eligible non-TTY `cmd_review_walk` aliases can enter the same closed
  remote skip-or-quit annotation walk while retaining their final-sidecar
  selection and terminal behavior. See
  [the implementation plan](../archive/2-headless-review-walk-annotation-entry.md).
- `HUMAN_IO_FORMAT.md` is the current record-protocol contract. #322 still
  owns whether a remaining route needs a different response contract or a
  record-lifecycle policy.

## Ordered route

1. Begin #322 from post-proof code, not from the completed proofs. Confirm
   the baseline is committed; no follow-on seed exists yet.
2. Enumerate the remaining candidates before editing. Sweep both identifiers
   and vocabulary: direct input, `isatty` aliases, readiness checks, and
   helpers that decide whether prompting runs. Record every match and why it
   migrates, stays terminal-only, or has a different owner. The completed
   `cmd_review` entry is excluded unless its selected contract demonstrably
   fails.
3. Partition candidates by their observable decision contract. Destructive
   confirmations, absent-mode defaults, free-text feedback, and lifecycle
   ownership do not share a policy merely because a person is involved.
4. Select at most one route group whose named property requires a change.
   Author one bounded seed for that group, or record no action when the
   inventory shows no justified shared migration. Generalize response
   delivery only when that group proves the focused record interface cannot
   supply its selected contract.

## Parked artifact-contention route

#353 is a separate, unselected follow-on to the normalized-artifact collision
correction. It starts only after that narrow correction reaches external review
convergence and the user selects the item. Its trigger is specific: a
destination reappears after one recovery and one publication retry, leaving a
new generated payload that must not displace an unknown writer's content.

The route preserves the raw source, the competing destination, and the pending
generated payload; records one durable, typed human decision; and lets the same
decision resume from a terminal or a headless orchestrator such as Integration. It may
reuse `HUMAN_IO_FORMAT.md` only if the authored plan proves that format can
carry the artifact and stale-choice contracts. It does not join #322's general
remaining-input inventory merely because both routes can wait for a person.

## Decision gates

- A response-delivery proof does not authorize a caller to bypass its safety,
  approval, default, or TTY gate.
- An artifact collision is evidence that a path changed, not evidence of a
  writer's identity or liveness. #353 reports the observable and revalidates
  before resolution; it does not turn that signal into a lock claim.
- A route migrates only after its caller, absent-mode behavior, operator
  consequence, and required response set are verified against its goal.
- Retention or cleanup is selected only with a named record owner and a
  route group that requires it; current no-cleanup behavior is not a global
  policy.
- HTTP, external transports, advisory events, multi-reader resolution,
  default-policy tables, and timeouts remain deferred until a selected route
  cannot meet its property without one.
- Before every cut, split, or scope expansion, sweep affected identifiers and
  vocabulary across the plan, details, seeds, and backlog. Confirm the
  proposed mechanic serves headless human response, not merely a matching
  call site.

## Exit and handoff

This arc hands off only after #322 has a committed, classed inventory and one
of two outcomes: a single evidence-backed seed names the next route group, or
the backlog records why no route group is justified. The next session follows
that selected seed or backlog decision, not this arc. The arc never certifies
every plan-tool command as headless-capable.

## Out of scope

This arc does not create a Integration or browser transport, relax destructive-action
safeguards, choose a remote-answer authority, replace `plan-tool`'s CLI, turn
the existing record protocol into a pluggable transport framework, or create a
generic multi-writer lock manager.
