> **Replaced**: this file has been superseded by `docs/implementation-plans/2-preserve-reused-audit-coverage.md`.
> Preserved here for history; do not edit.

## Overview

Persist the conceptual-audit coverage verdict in reusable `completeness-audit` sidecars so a fresh or fingerprint-fresh reused audit reports the same result in Markdown and `--json`. Reuse must preserve clean, budget-limited, and low-yield coverage without another Claude call, while coverage-less legacy sidecars remain reusable with an explicit conservative unknown result.

## Problem statement

`completeness-audit --reuse-audit` currently saves recommendations and fingerprints but not the conceptual audit's coverage and budget facts. When reuse skips the audit, rendering falls back to empty local state and can falsely present an unconfirmed or low-yield audit as clean or defaulted.

## Architecture

Treat coverage as conceptual-audit provenance alongside findings. The sidecar writer stores normalized public coverage fields, the saved-review loader exposes them, and the reusable-audit read seam provides the restored value to both audit-only and `--iterate` reuse paths.

The persisted value must match the existing public `coverage` contract: `budget_limited`, `passes_used`, `cap`, compatibility-null recommendation fields, and `confirmation_kind`. The sidecar field is additive and documented in `DATA_CONTRACT.md`; missing or invalid legacy coverage remains reusable for findings but renders an explicit conservative unknown coverage shape without re-running Claude.

## Out of scope

- Changing audit pass budgets, retry/timeout policy, coverage semantics, or the existing low-yield and blocking policy; this plan preserves current behavior.
- Re-running a fresh conceptual audit solely because a legacy sidecar omits the new optional field; legacy reuse must remain available.
- Changing general saved-review, reconcile, Jira-grade, convergence-history, checkpoint identity, or report filename behavior; these are unrelated behaviors.
- Addressing the distinct checkpoint identity risk; it remains separate backlog work.

## Risks

- Missing or invalid legacy coverage could be treated as proof of clean coverage, producing a false verdict; render an honest, stable unknown state while preserving reuse.
- Only fixing audit-only JSON/Markdown would leave `--iterate` reports incorrect; both reuse paths must share one restored value.
- Sidecar changes could break ordinary-review payload compatibility; additive reads must retain existing valid legacy sidecars.

## Testing

Exercise save/load and the real freshness/reuse boundary without a new conceptual call. Verify that budget-limited and confirmed-low-yield results retain coverage in audit-only and `--iterate` reuse output, legacy sidecars render the chosen unknown representation, and a fresh audit writes the normalized sidecar value. Run focused persistence/CLI suites and the contract test.

## Acceptance criteria

- A reused sidecar preserves the coverage verdict from its fresh conceptual audit in Markdown and `--json` on both reuse paths.
- A legacy coverage-less sidecar never reports a clean/default coverage verdict it cannot support and does not spend a replacement Claude call.
- `--reuse-audit` continues to skip the conceptual audit when fingerprints match; stale saves still re-audit under existing rules.
- Sidecar additions are documented in `DATA_CONTRACT.md`, remain backward-compatible, and leave unrelated review kinds and Jira-grade behavior unchanged.
- After shipment, remove the source RISK from `BUG_BACKLOG.md` and record the validation/audit outcome in the session handoff.

## Deferred

- Keep checkpoint/final artifact identity and historical checkpoint migration in the separately tracked pre-apply-checkpoint RISK; it is a separate concern.
