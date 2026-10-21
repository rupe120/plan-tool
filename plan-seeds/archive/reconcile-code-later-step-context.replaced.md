> **Replaced**: this file has been superseded by `docs/implementation-plans/archive/2-reconcile-code-later-step-context.md`.
> Preserved here for history; do not edit.

# Reconcile completed steps against cumulative delivery

## Outcome

`reconcile-code --step N` evaluates a completed step against its own detail
while treating code delivered by other completed steps as context. It never
recommends removing a sibling step's completed work merely because that work is
outside the selected step's declared files.

## In scope

- Run-reconcile context and prompt composition for a selected completed step.
- The recommendation/report path that can surface later completed work as
  selected-step drift.
- Focused prompt, CLI, and persistence/report tests using a multi-step
  completed-plan fixture.

## Out of scope / non-goals

- Weakening plan-canonical reconciliation or hiding genuine drift in the
  selected step.
- Changing plan steps or details to omit delivered work.
- Generic review-walk routing or unrelated reconcile behavior.

## Allowed behavior changes

- Provide the selected-step reconciliation path enough cumulative completed-step
  context to classify sibling-owned code correctly.
- Suppress or reclassify only removal recommendations whose sole premise is
  sibling completed work outside the selected step's footprint.
- Emit a clear clean or scoped diagnostic when no selected-step drift remains.

## Allowed reorganization

- Extract or move local context-building/filtering helpers within the
  reconcile command only when it keeps the selected-step contract testable.

## Verification

- Reconcile every step of a completed multi-step fixture: later-step-only code
  produces no recommendation for an earlier selected step.
- A deliberate mismatch in the selected step still produces a reconciliation
  finding.
- Saved report wording distinguishes sibling context from real selected-step
  drift.

## Stop / defer

- Defer any request to alter completed-plan semantics beyond the selected
  run-reconcile path.
