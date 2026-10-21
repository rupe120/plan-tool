> **Replaced**: this file has been superseded by `docs/implementation-plans/archive/2-reconcile-code-later-step-context.md`.
> Preserved here for history; do not edit.

## Overview

Update `reconcile-code --step N` so it evaluates a completed step against its own detail while using other completed steps as context. It must not recommend removing sibling-owned completed work that falls outside the selected step's declared files, while still reporting genuine selected-step drift.

## Problem statement

The selected-step reconciliation path can surface later completed work as drift for an earlier selected step. This produces removal recommendations for code owned by sibling completed steps rather than findings about the selected step itself.

## Architecture

Provide the selected-step reconciliation path with cumulative completed-step context during run-reconcile prompt composition. Use that context in the recommendation/report path to suppress or reclassify removal recommendations whose only premise is sibling completed work outside the selected step's footprint, while preserving findings for genuine selected-step mismatches.

Local context-building or filtering helpers may be extracted or moved within the reconcile command when that keeps the selected-step contract testable. When no selected-step drift remains, emit a clear clean or scoped diagnostic.

## Out of scope

- Weakening plan-canonical reconciliation or hiding genuine drift in the selected step.
- Changing plan steps or details to omit delivered work.
- Generic review-walk routing or unrelated reconcile behavior.

## Testing

- Use focused prompt, CLI, and persistence/report tests with a multi-step completed-plan fixture.
- Reconcile every step of the fixture and verify later-step-only code produces no recommendation for an earlier selected step.
- Verify a deliberate mismatch in the selected step still produces a reconciliation finding.
- Verify saved report wording distinguishes sibling context from real selected-step drift.

## Acceptance criteria

- `reconcile-code --step N` evaluates a completed step against its own detail while treating code delivered by other completed steps as context.
- Later-step-only code produces no removal recommendation when an earlier completed step is selected.
- A deliberate mismatch in the selected step produces a reconciliation finding.
- Saved report wording distinguishes sibling context from real selected-step drift.
- When no selected-step drift remains, the selected-step path emits a clear clean or scoped diagnostic.

## Deferred

- Altering completed-plan semantics beyond the selected run-reconcile path is deferred.
