> **Retired 2026-08-19** — The proposed causal-provenance feature cannot prove
> its claimed relationship from saved model findings. Preserve this seed only
> as the rejected scope; do not re-seed it.

# Seed: re-seed bad-fix provenance from the withdrawn plan's audit evidence

## Outcome

This seed would have produced an implementation-ready Bad Fix Provenance plan
with an advisory grounded in immutable remedy evidence, a deterministic temporal
order, and a conservative same-issue identity rule. The 2026-08-19 review
rejected that design before implementation.

## In scope

- The provenance model for qualified automated and operator-recorded remedies:
  preserve every accepted annotation event together with the original finding
  evidence it resolved; later collapsed snapshots may summarize state but may
  not replace that evidence for recurrence matching.
- One explicitly persisted, deterministic event order for remedy and
  recurrence comparisons. It must not infer real occurrence order from a
  collision-reserved report filename or storage timestamp; equal-time events
  have a stable tie-breaker.
- A conservative same-issue comparator: use a usable normalized body skeleton
  when available, otherwise only a usable normalized title; absent or
  punctuation-only identifiers never match.
- The operator record command, shared annotation persistence boundary,
  compatibility handling for existing saved review data, and convergence
  rendering needed to make the evidence model observable, including the
  advisory-only `requires-scope-review` route for an auto-driven session.
- Detail authoring must name resolvable code/data-contract anchors for every
  referenced persisted field or symbol, and its acceptance tests must exercise
  ordering, history retention, identity rejection, and original-evidence
  preservation.

## Overview

The previous plan reached detail creation with an attractive outcome but an
underspecified evidence model. Its final detail audit exposed that report
timestamps can be reserved out of real-time order, annotations are currently
overwritten rather than retained as a history, collapsed passes replace a
finding snapshot, and empty identity inputs can score as a title match. The
replacement must settle these contracts before decomposing implementation.

## Problem statement

A bad-fix advisory is useful only when it can distinguish a real recurrence
after a specific remedy from a re-audit artifact or an unrelated finding. The
prior design allowed the stored representation to redefine chronology and
allowed summarized state to stand in for original evidence. That makes a
warning untrustworthy, so this effort starts from provenance correctness rather
than from rendering or audit-loop messaging.

## Architecture

Treat qualified remedy annotations as append-only provenance events and retain
the exact finding snapshot and source-report identity associated with each
event. Derive collapsed views in memory for display or run-level analysis, but
match a later recurrence against the event's preserved source evidence. A
qualifying match emits a preserved-evidence reference and
`requires-scope-review`; it suppresses only that recurrence's structural
recommendation and never asserts that the earlier remedy caused it.

Define the recurrence relation against the explicit event-order key selected
by this plan, not `created_at` merely because it is available. The order key
and its collision tie-breaker are part of the persisted compatibility contract.

Identity matching is a guarded comparison, not a similarity fallback: each
candidate must have a usable identity signal before it may enter the comparator.

## Out of scope

- Changing the generic `detail --commit` readiness policy or exit behavior.
  The cross-cutting readiness signal remains backlog #262.
- Broad audit-scoring redesign, generic annotation analytics, or migration of
  unrelated review sidecars.
- Treating a human note as proof that an implementation was correct; this
  feature reports provenance and recurrence, not correctness judgment.
- Reopening unrelated convergence, report naming, or audit-backend work.

## Allowed behavior changes

- Persisted qualified remedy records may gain the minimum event/order/source
  fields required by the stated provenance contract, with read compatibility
  for earlier saved reviews.
- The convergence output may emit a bad-fix advisory only for a qualified,
  later, same-issue recurrence supported by retained evidence, plus the
  advisory-only `requires-scope-review` route. The CLI keeps its exit behavior;
  an auto-driven session stops further hand applies or re-audits and surfaces
  the operator's choice.
- The operator-facing record flow may require the information necessary to
  create an unambiguous remedy event.

## Allowed reorganization

Only extract or consolidate the shared annotation writer and identity
comparison boundary when that is necessary to make the provenance contract
single-sourced. Do not mix broad CLI or report-layer cleanup into this effort.

## Risks

- An append-only representation can create duplicate-looking history during
  rewalks; the plan must define idempotency separately from display collapse.
- Existing sidecars lack new provenance fields; compatibility must preserve
  their prior meaning without fabricating historical evidence.
- Overly permissive identity fallback produces false advisories, while overly
  strict matching hides real recurrence; choose the conservative failure mode
  and make it testable.

## Testing

Prove the binary observable: a bad-fix advisory and `requires-scope-review`
route are emitted exactly when an eligible remedy event precedes a later
recurrence of the same usable issue, using the event's preserved evidence.

Test remedies recorded after a recurrence even when report storage timestamps
collide; multiple remedy events with equal wall-clock time; repeated writes for
one recommendation; a finding changed in a later collapsed pass; blank or
punctuation-only body/title candidates; legacy saved-review data; and the
operator record path. Verify the details' code/data-contract references resolve
against HEAD before implementation begins.

## Acceptance criteria

- Every emitted advisory identifies its preserved remedy event and source
  evidence, its order relation is deterministic, and its matching recurrence
  carries `requires-scope-review` without changing the CLI exit behavior.
- No advisory can arise from a storage timestamp that changed real occurrence
  order, from an overwritten remedy event, from a replaced collapsed finding,
  or from an unusable identity signal.
- Legacy data remains readable and cannot be silently promoted into invented
  remedy evidence.
- The replacement plan's detail audit has no unresolved high-severity
  correctness finding in this feature's evidence, ordering, or identity
  contract before implementation starts.

## Deferred

Generic readiness messaging after repeated audit churn is backlog #262. Any
audit-policy change, quality judgment, agreement check between prose artifacts,
shape/length cap, gate/exit-code flip, or unrelated report chronology issue is
deferred there or to a separate seed.
