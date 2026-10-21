> **Replaced**: this file has been superseded by `docs/implementation-plans/2-preserve-reused-audit-coverage.md`.
> Preserved here for history; do not edit.

# Plan seed: preserve coverage verdict when reusing completeness audits

This file is a `plan-tool create` input. Use it via:

```
plan-tool create --from-existing plan-seeds/reuse-audit-coverage-verdict.md
```

Source: `BUG_BACKLOG.md` — **`completeness-audit --reuse-audit` loses its
original coverage verdict**. The resulting plan updates that backlog entry
only after the implementation ships.

## Outcome

A fresh and a fingerprint-fresh reused `completeness-audit` report the same
conceptual-audit coverage verdict in both Markdown and `--json`, including a
budget-limited or low-yield result, without making another Claude call.

## Overview

The reusable completeness sidecar persists recommendations and fingerprints,
but not the conceptual audit's coverage/budget facts. Reuse therefore skips
the audit and renders defaults from empty local state, falsely reporting an
unconfirmed or low-yield audit as a clean/defaulted result. Make the saved
audit carry the exact normalized coverage verdict that produced its report and
restore that verdict whenever its findings are reused.

## Architecture

Treat coverage as provenance of the conceptual audit, alongside its findings:
the sidecar writer records the normalized public coverage fields; the saved
review loader exposes them; the reusable-audit read seam supplies them to both
the audit-only and `--iterate` reuse paths. Legacy sidecars that lack coverage
remain reusable for findings but report an explicit conservative unknown
coverage shape rather than fabricating a clean result. Do not re-run Claude to
repair a fresh legacy record.

The persisted value and public `coverage` block must agree on the existing
contract: `budget_limited`, `passes_used`, `cap`, compatibility-null
recommendation fields, and `confirmation_kind`. Keep the public key set and
normalization rules stable; the sidecar field is an additive persistence
contract documented in `DATA_CONTRACT.md`.

## In scope

- Saved-review sidecar serialization, load compatibility, and reusable-audit
  data flow for completeness-only coverage provenance.
- Both reuse consumers: audit-only rendering and the iterative loop's final
  report/checkpoint flow.
- Markdown and JSON coverage rendering plus focused persistence and CLI
  fixtures that distinguish clean, budget-limited, low-yield, and legacy
  saved audits.
- `DATA_CONTRACT.md` and the source `BUG_BACKLOG.md` record when shipped.

## Out of scope

- Changing audit pass budgets, retry/timeout policy, coverage semantics, or
  the existing low-yield and blocking policy.
- Re-running a fresh conceptual audit solely because a legacy sidecar omits
  the new optional field.
- Changing general saved-review, reconcile, Jira-grade, convergence-history,
  checkpoint identity, or report filename behavior. The distinct checkpoint
  identity risk remains separate backlog work.

## Risks

- A missing/invalid legacy field must not be interpreted as proof of clean
  coverage. Preserve reuse but make the unknown state honest and stable.
- The two reuse paths must share one restored value; fixing only audit-only
  JSON/Markdown would leave `--iterate` reports wrong.
- Persisted fields are data-contract surfaces. Additive reads must retain
  existing ordinary-review payload compatibility and reject no valid old
  sidecar.

## Testing

Exercise save/load and the real freshness/reuse boundary with no new
conceptual call: a budget-limited result and a confirmed-low-yield result
retain their coverage in audit-only and `--iterate` reuse output; legacy
sidecars report the chosen unknown representation; a fresh audit still writes
the normalized sidecar value. Run focused persistence/CLI suites and the
contract test.

## Acceptance criteria

- A reused sidecar preserves the coverage verdict that its fresh conceptual
  audit produced in Markdown and JSON, on both reuse paths.
- A legacy coverage-less sidecar never reports a clean/default coverage
  verdict it cannot support and does not spend a replacement Claude call.
- `--reuse-audit` continues to skip the conceptual audit when fingerprints
  match; stale saves still re-audit under the existing rules.
- Sidecar additions are documented and backward-compatible; unrelated review
  kinds and Jira-grade behavior remain unchanged.
- After shipment, remove the source RISK from `BUG_BACKLOG.md` and record the
  validation/audit outcome in the session handoff.

## Deferred

Keep checkpoint/final artifact identity and historical checkpoint migration in
the separately tracked pre-apply-checkpoint RISK.
