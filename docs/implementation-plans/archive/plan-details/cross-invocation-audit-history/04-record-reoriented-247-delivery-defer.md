> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 4 — Record the reoriented #247 delivery and defer trusted trajectory comparison

## Summary

Update `BACKLOG.md` and `docs/implementation-plans/backlog-arcs/backlog-arc-convergence-evidence.md` to close #247 as the delivered saved-audit ledger. Keep #303 as the separate deferred route for a comparison feature that has not earned implementation. The key decision is that delivered evidence visibility does not establish comparison eligibility. On green, the backlog and convergence arc state one consistent lifecycle: #247 is delivered, while #303 remains deferred and fails closed until its own evidence boundary exists.

## Table of Contents

- [Summary](#summary) — Reviewer overview of the lifecycle-record update.
- [Table of Contents](#table-of-contents) — Quick links to each section.
- [Why](#why) — Why the delivered ledger and deferred comparison need separate records.
- [Input](#input) — Landed ledger boundary and existing backlog ownership this step uses.
- [Files (creates vs edits)](#files-creates-vs-edits) — Backlog and arc documents updated by this step.
- [Implementation](#implementation) — Delivery recording and deferred-route boundaries.
- [Tests](#tests) — Existing ledger coverage and non-code verification.
- [Acceptance criteria](#acceptance-criteria) — Observable lifecycle and scope checks.
- [Applicable guardrails](#applicable-guardrails) — Plan limits that this record must preserve.
- [Deferred](#deferred) — Future comparison work left with #303.

## Why

The active #247 entry still reads as planned even though steps 1–3 define and document the delivered ledger, while #303 already owns the missing evidence-admission work for any trusted comparison. Leaving those lifecycle states loose makes the ledger look like an unfinished trajectory feature or makes the future comparison look authorized by saved metadata alone. This step records the completed bounded delivery and keeps the larger comparison decision separate.

## Input

- **Step 3’s landed boundary:** Use `docs/implementation-plans/plan-details/cross-invocation-audit-history/03-document-audit-evidence-ledger-its.md` and its landed documentation as the source for what #247 delivered. Do not promote wording from an earlier proposal over the delivered ledger behavior.

- **Current backlog ownership:** Read `BACKLOG.md:**#247 — Render a saved audit-evidence ledger**` and `BACKLOG.md:**#303 — Compare saved audit history only with provenance-backed admission**` together. The first owns the delivered display; the second owns any later comparison.

- **Arc ordering:** Update `docs/implementation-plans/backlog-arcs/backlog-arc-convergence-evidence.md:## Ordered route` without changing its evidence boundary in `## Evidence requirements` or its operator-owned limit in `## Exit and handoff`.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `BACKLOG.md` — Mark #247 delivered, preserve its ledger-only scope, and retain #303 as the separately deferred comparison route.
  - `docs/implementation-plans/backlog-arcs/backlog-arc-convergence-evidence.md` — Record #247’s delivered position and keep #303 ordered after it as a deferred, fail-closed follow-up.

## Implementation

- **Foundational logic:** Close #247 as a delivered evidence ledger while keeping trusted cross-invocation comparison exclusively with #303.

- **Record #247’s actual delivery:** In `BACKLOG.md:**#247 — Render a saved audit-evidence ledger**`, replace the active planning lifecycle with a dated delivered record after steps 1–3 have landed. State the shipped result in terms of the read-only saved-artifact ledger, not a trajectory, comparison, or convergence verdict.

- **Keep historical text clearly historical:** Leave the existing superseded #247 draft unavailable as an active contract. Do not restore its old trajectory mechanism, and do not let its obsolete details alter the delivered entry’s scope.

- **Keep #303 independent:** In `BACKLOG.md:**#303 — Compare saved audit history only with provenance-backed admission**`, retain the deferred status and its own scope contract. Make the dependency direction clear: #247’s delivery is a prerequisite for visibility, not evidence that comparison is safe.

- **Update the arc as one route:** In `docs/implementation-plans/backlog-arcs/backlog-arc-convergence-evidence.md:## Ordered route`, mark #247 as delivered and retain #303 as the next deferred comparison route. Preserve the rule that incomplete, malformed, stale, copied, or incompatible evidence returns the operator to the #247 ledger instead of producing a comparison.

- **Do not broaden the record sweep:** `docs/implementation-plans/2-cross-invocation-audit-history.md:## Decision` and `## Deferred`, plus the earlier step-detail files, already describe this boundary and are outside this step’s file list. Report a conflict if one appears; do not rewrite prior plan records as part of this lifecycle update.

- **Reject a merged entry:** Do not fold #303 into #247 or add comparison mechanics, persisted provenance, schema changes, CLI behavior, or tests to this documentation-only step. A separate backlog entry keeps the missing trust design visible and reviewable.

## Tests

- `tests/test_convergence_diagnosis.py` — Run the landed ledger coverage to confirm #247’s delivered behavior remains an evidence display rather than a comparison feature.

- `tests/cli/test_convergence_cmd.py` — Run the landed command-isolation coverage to confirm the delivered ledger does not change the convergence command’s verdict or exit behavior.

### Verification (non-code step)

1. Read the active #247 and #303 entries in `BACKLOG.md`; confirm #247 is delivered and #303 remains deferred with separate ownership.

2. Read `docs/implementation-plans/backlog-arcs/backlog-arc-convergence-evidence.md:## Ordered route`; confirm its #247 and #303 entries use the same lifecycle and dependency direction as `BACKLOG.md`.

3. Search both edited files for `#247`, `#303`, `trajectory`, and `comparison`; inspect every active match to confirm no text treats ledger visibility as trusted comparison evidence.

4. Run `uv run pytest tests/test_convergence_diagnosis.py tests/cli/test_convergence_cmd.py -q`.

5. Review the diff and confirm it changes only `BACKLOG.md` and `docs/implementation-plans/backlog-arcs/backlog-arc-convergence-evidence.md`.

## Acceptance criteria

- `BACKLOG.md:**#247 — Render a saved audit-evidence ledger**` records the delivered ledger with the actual completion date and no active trajectory promise.

- `BACKLOG.md:**#303 — Compare saved audit history only with provenance-backed admission**` remains deferred as the sole backlog route for trusted cross-invocation comparison.

- `docs/implementation-plans/backlog-arcs/backlog-arc-convergence-evidence.md:## Ordered route` records #247 as delivered before #303 and preserves the fail-closed return to the ledger when comparison evidence is inadequate.

- No edited text claims that saved metadata, multiple ledger rows, or #247 delivery establishes finding identity, provenance, freshness, comparison eligibility, or a trajectory verdict.

- `uv run pytest tests/test_convergence_diagnosis.py tests/cli/test_convergence_cmd.py -q` passes.

## Applicable guardrails

- **The plan’s `## Plan intent`, separate read-only ledger:** Record #247 as evidence visibility only; do not describe it as a cross-invocation decision.

- **The plan’s `## Step intent`, reoriented delivery:** Preserve #303 as a separate route rather than treating the delivered ledger as a partial implementation of comparison.

- **The plan’s `## Out of scope`, no new authority:** Do not add or describe new command behavior, persistence, validation, gates, or comparison policy in either document.

## Deferred

- Trusted cross-invocation comparison — #303 owns the future provenance, lifecycle, and admission design; this step records that boundary but does not implement it.
