> **Auto-archived**: this plan was swept on 2026-07-12 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 4 — Update BACKLOG #72 to mark the linkage-schema slice shipped and leave phases 2–3 as remaining scope

## Summary

Record in `BACKLOG.md` that this plan shipped the outcome-linkage **schema** slice of #72, while leaving the resolver, the analysis-and-recommend surface, and the broader key backfill as remaining phase 2–3 work. The only file this step touches is `BACKLOG.md`. The one real decision: #72 **stays open** — this is a partial-progress update to its `Status` line, not a whole-entry retirement, so the entry block, the priority roll-ups that name it, and every cross-entry citation to its still-unshipped outcome-linkage stay in place. Before writing "shipped," grep-confirm the shipped surfaces exist at HEAD (the five `DecisionEvent` base fields `decision_id`/`run_id`/`plan_fingerprint`/`code_fingerprint`/`anchor`, schema v2, the run-entrypoint `run_id` binding); on any gap, stop and route back to steps 1–3 rather than patching code here. On green, #72's `Status` names the shipped schema slice and points at this plan, and "Remaining (phase 2–3)" describes only what genuinely still needs building.

## Table of Contents

- [Why](#why) — why this docs update is the plan's final step and what it must and must not touch
- [Input](#input) — the shipped surfaces (steps 1–3) this update claims and the #72 entry it edits
- [Files (creates vs edits)](#files-creates-vs-edits) — the one file this step touches
- [Implementation](#implementation) — the Status-line edit, the verify-before-write gate, and the sweep of #72's other references
- [Tests](#tests) — verification appropriate to a docs-only step
- [Acceptance criteria](#acceptance-criteria) — checkable outcomes
- [References](#references) — the entry and the plan this update points at
- [Deferred](#deferred) — what this step deliberately does not touch

## Why

`BACKLOG.md` #72's `Status` line currently says "Phase 1 (the recorder + three wired decisions) is live" and lists the whole of outcome-linkage as remaining. This plan ships a concrete, separable piece of that remaining work: the **join-key schema** — `decision_id`, `run_id`, `plan_fingerprint`/`code_fingerprint`, and the frozen-for-phase-2 `anchor` on the base `DecisionEvent`, the `TELEMETRY_SCHEMA_VERSION` bump, and the run-entrypoint `run_id` binding — but no consumer. Leaving #72 saying the schema is unbuilt makes the doc assert unshipped work that now exists, and the next reconcile audit flags the drift. This step is the plan's final bookkeeping: it records the schema slice as shipped so the entry stays honest, and it re-scopes "Remaining" to the resolver, the analysis surface, and the un-wired decision sites — the parts this plan explicitly left out (see the plan's `## Out of scope`). It is a **non-code** step: it changes prose only, and its deletion/edit of a tracking record is a claim about code the earlier steps landed, so that code must be verified before the claim is written.

## Input

This step's `Status`-line edit is a claim about surfaces that steps 1–3 ship. Verify each at HEAD before recording it as shipped (the edit is gated on `depends_on: 1, 2, 3`):

- **Step 1 — base-event schema.** The five defaulted fields (`decision_id`, `run_id`, `plan_fingerprint`, `code_fingerprint`, `anchor`) on `DecisionEvent`, the `TELEMETRY_SCHEMA_VERSION` value `2`, and the old-line-tolerant `read_decisions` in `plan_tool/telemetry.py`; the matching `DecisionEvent` section in `DATA_CONTRACT.md`.
- **Step 2 — recorder migration.** The 8 wrappers in `plan_tool/telemetry.py` forwarding the keys, and `record_plan_criteria_breakdown`'s fingerprints **dual-homed** onto the base event (also written to the base fields, still kept in `context` — the `context`-drop is phase 2).
- **Step 3 — run_id binding.** The telemetry `run_id` scope helper on `RunLogWriter` (`plan_tool/run_log.py`) wired at the two run entrypoints (`plan_tool/cli/run_cmd.py`, `cmd_run` and `_cmd_run_sweep`); the `run --reconcile` lane and standalone `reconcile*` commands stay phase-2.

Do not re-specify how these steps work — cite them by outcome. If a surface is missing at HEAD, that is a gap to route back to the owning step (1, 2, or 3), not something to fix inside this docs step.

The entry being edited is the `**#72 — Decision/outcome telemetry …**` block in `BACKLOG.md`, whose `Status` and `Remaining (phase 2–3)` sub-bullets are the primary edit target.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `BACKLOG.md` — rewrite the #72 `Status` line to record the shipped schema slice and narrow "Remaining (phase 2–3)"; check (and lightly reword only if now inaccurate) the priority roll-ups that name #72; leave the entry open and its outcome-linkage cross-citations intact.

## Implementation

**Rewrite #72's `Status` sub-bullet to record the shipped schema slice.** In the `**#72 — Decision/outcome telemetry …**` block, the `- **Status:**` line today credits phase 1 (the recorder + three wired decisions) as live and treats all of outcome-linkage as remaining. Add that the outcome-linkage **schema** shipped: the base-event join keys (`decision_id`, `run_id`, `plan_fingerprint`/`code_fingerprint`, and the frozen `anchor`), the `TELEMETRY_SCHEMA_VERSION` bump to `2` with old-line tolerance, and the run-entrypoint `run_id` binding. Point at the authored plan `docs/implementation-plans/2-telemetry-linkage-schema.md` as the shipped work, mirroring how the line already cites `plan_tool/telemetry.py` and `CLAUDE.md`. Keep the spike/schema-first design notes in the entry — the `First concrete consumer` split-criteria drift-diff bullet and the "Spike the event schema first" note in `Scope (phased)` — so the retained spike reference the plan's acceptance criteria calls for survives.

**Narrow "Remaining (phase 2–3)" to what genuinely still needs building.** The current line names three remaining things: outcome-linkage, the `plan-tool telemetry` aggregation/recommend surface, and more decision sites. After this plan, the *schema* for outcome-linkage exists but nothing consumes it, so "Remaining" should describe: the read-only resolver / `plan-tool telemetry` analysis-and-recommend surface, deriving outcome verdicts (`acted-on`/`no-op`/`reverted`), and **backfilling the keys across the decision sites this plan did not wire** (create-side granularity, `--refresh`/reconcile drift-gate, `apply_finding` verdicts, escalate-to-split). Keep this list consistent with the plan's own `## Deferred` and `## Out of scope` — those are the authoritative statement of what phase 2–3 still owns.

**Gate the "shipped" claim on a HEAD verification; never patch code here.** Before recording the schema as shipped, grep the shipped surfaces named in [Input](#input) — e.g. the five field names (`decision_id`/`run_id`/`plan_fingerprint`/`code_fingerprint`/`anchor`) and `TELEMETRY_SCHEMA_VERSION = 2` in `plan_tool/telemetry.py`, the run_id scope helper in `plan_tool/run_log.py` and its call sites in `plan_tool/cli/run_cmd.py`. This mirrors the established rule for a docs step whose act of recording work-shipped is a claim about code: verify the surfaces exist first, and on any gap stop and route back to the owning step (1/2/3) — do not add or fix production code inside this non-code step.

**Keep #72 open; do not delete the entry.** This is a partial-progress update. #72's phases 2–3 remain unbuilt, so the entry block stays. That means the retire-an-entry sweep does *not* apply the way it would for a whole-entry deletion:

- **Priority roll-ups that name #72 stay pointing at #72**, because it is still the highest open concrete telemetry item. Three surfaces name it as the top concrete pick — the **T3 tier bullet** (`- **T3 — deterministic verifiability & grounding (P2), larger:**`), the Readiness-lens **"Highest open by tier"** chain, and the **"Next concrete pick:"** line. Read each and reword only if the schema-slice-shipped state makes the wording wrong; if #72 stays the correct "highest concrete item still to author" (its remaining resolver/backfill work is still unauthored), leave the pointer on #72. Do not re-point them at a successor — that rule is for a *retired* item, and #72 is not retiring.
- **The Quality/accuracy lens `heuristic-tuning` bullet** and the two grounding-cluster mentions (the bucket-A note "the #72-backed future plan-level size signal" and the T3 grounding-band line) describe #72's foundational role, which is unchanged. Leave them.
- **Cross-entry citations to #72's outcome-linkage / analysis surface stay untouched** — this plan did not ship those. #97's "`#72` telemetry optional … for tuning", #117's "once #72's outcome-linkage lands, its acted-on / false-positive rate … is read from telemetry" and "feeds #72 (the analysis surface that will read this decision)", and #82's companion note (companion-to-#72, gated-on-#74) all reference the still-unshipped phase 2–3 and remain accurate.

The foundational logic here is a single prose edit — "record shipped progress on an open tracking entry" — and its one shared hazard is the set of forward-pointing priority/roll-up surfaces elsewhere in `BACKLOG.md` that name #72; the sweep above covers them. There is no code-level duplicated logic to consolidate.

## Tests

### Verification (non-code step)

This step changes no production code. Verify the artifact instead:

- **shipped-surface grep — steps 1–3 landed** — before writing "shipped", `grep` confirms `decision_id`/`run_id`/`plan_fingerprint`/`code_fingerprint`/`anchor` and `TELEMETRY_SCHEMA_VERSION = 2` in `plan_tool/telemetry.py`, and the run_id scope helper wired in `plan_tool/cli/run_cmd.py`; a gap routes back to the owning step.
- **#72 stays discoverable and open** — after the edit, `grep -n '#72' BACKLOG.md` still finds the entry block and every roll-up/citation that legitimately names it; no line now frames the *schema slice* as unbuilt.
- **Status/Remaining consistency** — the rewritten "Remaining (phase 2–3)" matches the plan's `## Deferred` and `## Out of scope` (resolver + analysis surface, outcome-verdict derivation, un-wired decision-site backfill); no item is claimed both shipped and remaining.
- **spike reference retained** — the entry still carries its spike/schema-first design notes (`First concrete consumer` drift-diff, "Spike the event schema first").
- **priority pointers read true** — the T3 tier bullet, "Highest open by tier" chain, and "Next concrete pick" line each still describe #72 accurately after the schema slice shipped.
- **link/path accuracy** — the plan path `docs/implementation-plans/2-telemetry-linkage-schema.md` cited in the Status line resolves to a real file at HEAD.

## Acceptance criteria

- `BACKLOG.md` #72's `Status` line records the outcome-linkage schema slice as shipped (`decision_id`/`run_id`/`plan_fingerprint`/`code_fingerprint`/`anchor`, schema v2 with old-line tolerance, run-entrypoint `run_id` binding) and points at `docs/implementation-plans/2-telemetry-linkage-schema.md`.
- #72's "Remaining (phase 2–3)" names only unbuilt work: the resolver / `plan-tool telemetry` analysis-and-recommend surface, outcome-verdict derivation, and backfilling the keys across the decision sites this plan did not wire.
- #72 remains an **open** entry; the entry block is not deleted, and `grep -n '#72' BACKLOG.md` still returns it plus its roll-up and cross-entry references.
- No line in `BACKLOG.md` frames the join-key schema as unbuilt after this edit.
- The #72 outcome-linkage/analysis-surface citations in #97 and #117, and #82's companion note (companion-to-#72, gated-on-#74), are unchanged (this plan shipped no resolver or analysis surface).
- The "Remaining" list matches the plan's `## Deferred` / `## Out of scope`; nothing is both shipped and remaining.

## References

- [`BACKLOG.md` — #72 entry and the Priority (mission-grounded) roll-ups](BACKLOG.md) — the entry block to edit plus the T3 tier bullet, "Highest open by tier" chain, and "Next concrete pick" line to sweep.
- [`docs/implementation-plans/2-telemetry-linkage-schema.md`](docs/implementation-plans/2-telemetry-linkage-schema.md) — this plan; its `## Out of scope` and `## Deferred` are the authoritative statement of what phase 2–3 still owns, and its `## Acceptance criteria` pins this step's bookkeeping.

## Deferred

- **Retiring #72 entirely** — out of scope; phases 2–3 (resolver, analysis surface, decision-site backfill) remain unbuilt, so the entry stays open.
- **Editing the #72 cross-citations in #97, #117, and #82** — those reference outcome-linkage/analysis-surface work this plan did not ship (#82's companion note is gated-on-#74); they stay accurate and untouched.
- **Any production-code change** — this is a non-code step; a missing shipped surface routes back to step 1, 2, or 3 rather than being fixed here.
- **Re-pointing the priority roll-ups at a successor item** — that applies only to a retired entry; #72 stays the named highest open concrete telemetry item.
