> **Auto-archived**: this plan was swept on 2026-07-12 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 6 — Update BACKLOG #72 to mark the phase-2 backfill shipped and narrow its remaining scope to phase 3

## Summary

This is a docs-only step. It edits one file, `BACKLOG.md`, to record that this plan (the phase-2 telemetry-linkage backfill) shipped, and to narrow `#72`'s remaining scope to phase 3. The only real edits are inside the `**#72 — Decision/outcome telemetry …**` entry: rewrite its `**Status:**` bullet to credit the backfilled fingerprint sites and the three new decision families (drift-gate, apply-verdict, escalate-to-split) as done, and rewrite the `**Remaining (phase 2–3):**` clause so it lists only the still-unshipped phase-3 work (the resolver / `plan-tool telemetry` analysis surface and outcome-verdict derivation). The key design decision: `#72` is a **phased entry that stays open** — this is a partial-progress update, not a retirement, so the priority roll-ups and the `#97`/`#117`/`#74`/`#82` cross-citations stay untouched. On green, `BACKLOG.md` names this plan's shipped work and points the reader at phase 3 as the only open remainder, with no other `#72` surface changed.

## Table of Contents

- [Why](#why) — why the backlog needs the partial-progress update now
- [Input](#input) — where "shipped" and "remaining" scope are sourced from
- [Files (creates vs edits)](#files-creates-vs-edits) — the one file this step edits
- [Implementation](#implementation) — the Status/Remaining rewrite and everything that must stay put
- [Verification (non-code step)](#verification-non-code-step) — doc-accuracy and shipped-surface checks
- [Acceptance criteria](#acceptance-criteria) — observable checks a reviewer runs
- [References](#references) — the backlog and plan surfaces this step reads
- [Deferred](#deferred) — `#72` surfaces this step deliberately does not touch

## Why

`BACKLOG.md`'s `#72` entry is the forward-looking record for the decision/outcome telemetry effort. Its `**Status:**` bullet today lists "backfilling the join keys across the decision sites the schema slice did not wire (create-side granularity, `--refresh`/reconcile drift-gate, `apply_finding` verdicts, escalate-to-split)" as **remaining** work. This plan is exactly that work — steps 1–5 land the fingerprint backfill on the six existing recorder sites plus the three new decision families. Once they are green, the backlog's "remaining" list is stale: it still claims as unshipped work that now exists in the code. This step corrects that record so `#72`'s remaining scope reads as phase 3 only, keeping the backlog an honest source for the next pick. The plan's own acceptance criteria name this update as the plan's closing bookkeeping.

## Input

This step does not invent scope — it copies "shipped" and "remaining" from two authoritative sources this plan already owns.

- **What shipped** is owned by steps 1–5 and by the plan's `## Acceptance criteria` in `docs/implementation-plans/2-telemetry-linkage-backfill.md`. The shipped surfaces are: fingerprints now on the six backfilled recorder sites (create ×2, code-reveals-split, granularity[completeness], audit-coverage, convergence), and three new decision families (drift-gate `no-baseline`/`no-drift`/`drifted`, per-finding apply verdict, escalate-to-split outcome). Cite these by their plan-level outcome; do not restate step 1–5 mechanics here.
- **What remains** is owned by the plan's `## Out of scope` and `## Deferred` sections in `docs/implementation-plans/2-telemetry-linkage-backfill.md`. Take the phase-3 remainder from there — the resolver / `plan-tool telemetry` analysis-and-recommend surface, and deriving outcome verdicts (`acted-on`/`no-op`/`reverted`/`still-open`) — rather than re-deriving it from memory. The plan's Out-of-scope also confirms this plan ships **no** consumer and **no** `TELEMETRY_SCHEMA_VERSION` bump, which the Status rewrite must not claim otherwise.
- **The current `#72` text** in `BACKLOG.md` is the third input: its `**Status:**` bullet already credits the phase-1 recorder and the earlier schema slice (`docs/implementation-plans/2-telemetry-linkage-schema.md`). This step adds this plan's slice beside those, not in place of them.

Limit on verifying the "shipped" claim: a status bullet asserting code shipped is a claim about code, so it gets the same verify-before-write check a deletion would — confirm the shipped surfaces exist at HEAD before writing them as done (see Verification). If a surface is missing, that is a gap in the owning code step (1–5), not something to paper over in this docs edit.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `BACKLOG.md` — inside the `**#72 — Decision/outcome telemetry …**` entry only: (1) rewrite the `**Status:**` bullet to add this plan's shipped slice (the six fingerprint-backfilled sites + the three new decision families), citing the **tracked, durable** plan docs as provenance — `docs/implementation-plans/2-telemetry-linkage-backfill.md` (phase 2) alongside the existing `2-telemetry-linkage-schema.md` (phase 1) credit. **Do not cite `.tmp/72-telemetry-linkage.spike.md` in `BACKLOG.md`**: `.tmp/` is gitignored transient scratch (routine `rm .tmp/<slug>.*` cleanup removes it), so a citation there would dangle in a durable, tracked file — the spike's design record is already distilled into the two tracked plan docs, which are the honest provenance pointer. (2) rewrite the `**Remaining (phase 2–3):**` clause to `**Remaining (phase 3):**` listing only the resolver/analysis surface and outcome-verdict derivation.

## Implementation

**Treat this as a partial-progress update to an open entry, not a retirement.** `#72` is a phased entry; shipping one phase narrows its scope but leaves it open. The retirement moves — scrubbing the `#72` id, re-pointing "highest open / next pick" priority lines at a successor, cleaning up cross-citations — do **not** apply here. Change only the `**Status:**` and `**Remaining:**` text inside the `#72` entry block. Everything else about `#72` stays exactly as it is.

- **Rewrite the `**Status:**` bullet to credit this plan's slice.** The bullet currently names phase 1 (recorder + three wired decisions) and the schema slice (`2-telemetry-linkage-schema.md`) as shipped. Add this plan's slice: the fingerprint backfill now landing on the six recorder sites (create ×2, code-reveals-split, granularity[completeness], audit-coverage, convergence) and the three new decision families — the reconcile/`--refresh` drift-gate, per-finding `apply_finding` verdicts, and escalate-to-split outcomes. Cite `docs/implementation-plans/2-telemetry-linkage-backfill.md` as the shipped surface, mirroring how the bullet already cites `2-telemetry-linkage-schema.md` for the schema slice. Keep it terse — one added clause, not a re-narration of steps 1–5.
- **Narrow the `**Remaining:**` clause to phase 3.** The bullet reads `**Remaining (phase 2–3):**` and lists three things: the resolver/analysis surface, deriving outcome verdicts, and "backfilling the join keys across the decision sites …". That third item is what this plan ships, so drop it. Relabel the clause `**Remaining (phase 3):**` and leave the resolver / `plan-tool telemetry` analysis-and-recommend surface and outcome-verdict derivation, **plus the phase-2 hardening items this plan documented but deferred** (from the plan's `## Known limitations` / step-4 `## Deferred`): recording backend-invocation-failure applies as a distinct `apply-verdict` verdict, routing `completeness-apply --jobs N` worker telemetry to the canonical repo, and a dropped-event counter (or drift-gate map scoping) for the `_MAX_LINE_BYTES` cutoff. Source that wording from the plan's `## Out of scope` / `## Deferred` / `## Known limitations` so the backlog and the plan agree on what remains.
- **Cite durable provenance, not the transient spike.** The Status rewrite points at the tracked plan docs (`2-telemetry-linkage-schema.md`, `2-telemetry-linkage-backfill.md`) — not `.tmp/72-telemetry-linkage.spike.md`, which is gitignored scratch that cleanup can remove, leaving a dangling citation in the durable `BACKLOG.md`. The spike file itself is left untouched (a local design breadcrumb); it is simply not cited from a tracked file.
- **Leave every other `#72` surface unchanged.** Do **not** touch: the `**heuristic-tuning:**` priority line, the "Highest open by tier" chain, or the "Next concrete pick" line — `#72` is still the highest open item, so those pointers stay on it. Do **not** touch the cross-citations from `#97`, `#117`, `#74`, and `#82` — they reference the still-unshipped phase-3 analysis surface and must survive. Do **not** touch `#72`'s `**What**`/`**Scope (phased)**`/`**Risks**`/`**Dependencies**`/`**First concrete consumer**`/`**Origin**` bullets; the phase model there is still accurate.
- **This is the plan's backlog-reconciliation step.** The seed for this plan required carrying the originating backlog forward. This step is where that lands: `#72` is updated to reflect shipped-vs-remaining, and because work still remains it stays open (marked, not removed) — matching CLAUDE.md's rule for backlog-derived plans.

## Verification (non-code step)

This step changes no production code, so verification is doc-accuracy and shipped-surface checks, not unit tests.

- **Verify the shipped surfaces exist at HEAD before writing them as done** — grep the code the new Status text claims shipped: the fingerprint carry on the six recorder sites and the three new recorder families' `kind`/`decision` constants in `plan_tool/telemetry.py`, the drift-gate recorder call in `plan_tool/refresh.py`, the apply-verdict record at the `parse_apply_verdict` consumption site in `plan_tool/launcher.py`, and the escalate-to-split record in `plan_tool/launcher.py:escalate_to_split`. If any surface is absent, stop and route the gap back to its owning step (1–5) — do not soften the Status claim to match a missing surface, and do not edit code in this docs step.
- **Confirm the Remaining text matches the plan** — the rewritten `**Remaining (phase 3):**` clause lists only what the plan's `## Out of scope` / `## Deferred` in `docs/implementation-plans/2-telemetry-linkage-backfill.md` still defer (resolver/analysis surface + outcome-verdict derivation), with nothing that the plan's `## Acceptance criteria` says shipped.
- **Confirm no unintended `#72` edits** — a `git diff BACKLOG.md` touches only the `**Status:**` and `**Remaining:**` lines inside the `#72` entry. The `**heuristic-tuning:**` line, the "Highest open by tier" chain, the "Next concrete pick" line, and the `#97`/`#117`/`#74`/`#82` cross-citations are unchanged.
- **Confirm durable provenance** — the rewritten `#72` `**Status:**` bullet cites the tracked plan docs (`2-telemetry-linkage-backfill.md`, `2-telemetry-linkage-schema.md`) and does **not** cite the gitignored `.tmp/` spike path.

## Acceptance criteria

- `BACKLOG.md`'s `#72` `**Status:**` bullet names this plan's shipped slice (the six fingerprint-backfilled sites + the drift-gate / apply-verdict / escalate-to-split families) and cites `docs/implementation-plans/2-telemetry-linkage-backfill.md`.
- The `**Remaining:**` clause is relabeled to phase 3 and lists only the resolver / `plan-tool telemetry` analysis surface and outcome-verdict derivation — the "backfilling the join keys across the decision sites" item is gone.
- `#72` is still present and open; it is not deleted or retired.
- `git diff BACKLOG.md` shows no change to the `**heuristic-tuning:**` priority line, the "Highest open by tier" chain, the "Next concrete pick" line, or the `#97`/`#117`/`#74`/`#82` cross-citations.
- The rewritten `#72` `**Status:**` bullet cites the tracked plan docs and does **not** cite the gitignored `.tmp/72-telemetry-linkage.spike.md` path (no dangling citation in a durable file).
- Every surface the new Status text claims shipped is present at HEAD (grep-confirmed).

## References

- `BACKLOG.md` — the file this step edits; the `**#72 — Decision/outcome telemetry …**` entry whose `**Status:**` and `**Remaining:**` bullets are rewritten.
- `docs/implementation-plans/2-telemetry-linkage-backfill.md` — the plan's `## Acceptance criteria` (what shipped), `## Out of scope`, and `## Deferred` (the phase-3 remainder) that source the shipped-vs-remaining wording.
- `plan_tool/telemetry.py` — grep target: the three new recorder families' `kind`/`decision` constants the new Status text claims shipped.
- `plan_tool/create.py` — grep target: the fingerprint carry on the two create-side recorder sites.
- `plan_tool/review.py` — grep target: the fingerprint carry on the code-reveals-split (reconcile lane) recorder site.
- `plan_tool/cli/completeness_phases.py` — grep target: the fingerprint carry on the granularity and audit-coverage recorder sites.
- `plan_tool/cli/convergence_cmd.py` — grep target: the fingerprint carry on the convergence recorder site.
- `plan_tool/refresh.py` — grep target: the drift-gate recorder call in `refresh_plan`.
- `plan_tool/launcher.py` — grep target: the apply-verdict record at the `parse_apply_verdict` consumption site and the escalate-to-split record in `escalate_to_split`.

## Deferred

- **The phase-3 resolver / `plan-tool telemetry` analysis-and-recommend surface** — remains open under `#72`; this step records it as the remaining scope, it does not build it.
- **Deriving outcome verdicts** (`acted-on`/`no-op`/`reverted`/`still-open`) — phase-3 work, left as remaining scope in the entry.
- **Re-pointing `#72`'s priority roll-ups or its `#97`/`#117`/`#74`/`#82` cross-citations** — a retirement-only move; `#72` stays open and highest, so those surfaces are deliberately untouched.
- **Editing production code to satisfy the shipped claim** — if verification finds a missing surface, it is fixed in the owning code step (1–5), never in this docs step.

## Tests

N/A — this is a non-code (docs-only) step with no unit tests; see [Verification (non-code step)](#verification-non-code-step) for the doc-accuracy and shipped-surface checks that stand in for tests here.

