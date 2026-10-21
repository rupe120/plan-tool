> **Auto-archived**: this plan was swept on 2026-08-18 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 7 — Update BACKLOG entries and convergence policy docs

> **Post-ship (2026-08-11):** BACKLOG **#158** is **closed** as the
> recommend-only pause advisory; the loop-terminating `structural_stop`
> remainder this detail left open was **withdrawn** (soft pause + chat, not a
> machine stop). Treat “partially closed / Remaining structural_stop” prose
> below as historical recipe text from the ship day, not current backlog
> state.

## Summary

Close the documentation loop for the two recommend-only convergence advisories steps 5–6 ship: close BACKLOG **#158** as the recommend-only impact-recurrence pause advisory (hard loop stop withdrawn — do not leave `structural_stop` as open work), record **#248**’s thin edit-drift advisory as shipped with the hard exit still on **#231**, supersede the two blocked `impact-recurrence-0*` seeds in place, and extend `CLAUDE.md`’s **Convergence policy boundary** so assistants know the new signals exist and what they must not change. Touch only the four declared paths — no production code, no `docs/AUDIT_FLOW.md` (plan Deferred post-ship flow-doc prose). When green, backlog triage no longer treats the blocked seeds as pickable work, index prose matches what landed, and `CLAUDE.md` names `impact_recurrence` and `edit_drift` beside the three blocking predicates without widening any gate.

## Table of Contents

- [Why](#why) — operators and triage still see pre-ship backlog and seed state after steps 5–6 land.
- [Input](#input) — shipped symbols and backlog contracts this step must describe accurately.
- [Files (creates vs edits)](#files-creates-vs-edits) — the four declared paths and what each gains.
- [Implementation](#implementation) — per-file edit shape, partial-closure wording, and vocabulary sweeps.
- [Tests](#tests) — non-code verification checklist.
- [Acceptance criteria](#acceptance-criteria) — grep-able doc and backlog outcomes.
- [References](#references) — docs and symbols to read first.
- [Applicable guardrails](#applicable-guardrails) — plan fences that bind this docs-only step.
- [Deferred](#deferred) — follow-ups this step only points at.

## Why

Steps 1–6 add deterministic impact-recurrence and edit-drift classifiers, wire them through `diagnose_convergence` / `render_diagnosis`, and print them on completeness stderr when history is sufficient — but HEAD still tells a different story. BACKLOG **#158** reads as fully unimplemented and still points at two **BLOCKED** seeds that assume retired `spinning` / `FORK_*` machinery; **#248** still lists “edit-drift exit” as wholly open even though this plan ships only the thin advisory; `CLAUDE.md`’s convergence policy boundary names `arm-clustering` as the sole non-blocking advisory consumer of settled material evidence but not the two new diagnosis signals. Without this step, backlog triage over-prioritizes loop-stop work that was deliberately carved out, operators may run the blocked seeds, and assistants treat severity-clean convergence as the only stderr signal completeness already supplements.

## Input

**From steps 5–6** (must exist before this step runs; names per those detail files):

- `plan_tool/convergence_diagnosis.py` — `classify_impact_recurrence`, `classify_edit_drift`, frozen `ImpactRecurrenceAdvisory` / `EditDriftAdvisory`, optional fields on `ConvergenceDiagnosis`, `_impact_recurrence_lines`, `_edit_drift_lines`, and `render_diagnosis` loop-signal block (same `⚠` pattern as `_finding_churn_lines` / `_structural_recurrence_lines`).
- `plan_tool/cli/completeness_cmd.py` — stderr emitter (e.g. `_emit_convergence_loop_advisories`) after `_persist_and_present_report`, gated on run-grade sidecar write; prints advisory lines only, not full `render_diagnosis`.
- **Unchanged by design:** `plan_tool/convergence.py` iterate `stop_reason` vocabulary, `--fail-on-findings`, exit-code convention, and the three blocking predicates (`is_blocking`, `is_blocking_finding`, `is_blocking_impact`).

**Backlog contracts to reconcile:**

- **#158** — full entry body still describes loop-terminating `recurring_high_impact_seam` / `structural_stop`; this plan ships only the classifier + recommend-only advisory portion.
- **#248** — status already **Partially closed** for the bare-stage bar (`stage-differentiated-blocking`); “Remaining: edit-drift exit” must split into *advisory shipped here* vs *hard exit / provenance → #231*.
- **#231** — stays **not started**; this step cross-links it as the owner of durable apply→finding provenance and a hard edit-drift exit, not implement it.

**Seed state:** both `docs/implementation-plans/plan-seeds/impact-recurrence-01-classifier.md` and `docs/implementation-plans/plan-seeds/impact-recurrence-02-loop-stop.md` (the declared `files:` pair; shorthand `impact-recurrence-0*` in prose) carry **BLOCKED — do not run** banners from #251 retirement; this plan supersedes them with an advisory-only design in `docs/implementation-plans/2-convergence-non-severity-advisories.md`.

## Files (creates vs edits)

- **New files:** none.

- **Existing files (edits only):**
  - `BACKLOG.md` — partially close **#158**; update **#248** remaining-work line for edit-drift advisory shipment; add executed-plan row for `convergence-non-severity-advisories`; sweep index/T2/Related prose that still claims #158 issues a live structural stop or that the blocked seeds are the authoring path.
  - `CLAUDE.md` — extend **Convergence policy boundary** with the two recommend-only advisories (symbols, surfaces, explicit non-gate rule); at most one terse forward reference elsewhere if an existing bullet would otherwise contradict (prefer fixing the boundary section only).
  - `docs/implementation-plans/plan-seeds/impact-recurrence-01-classifier.md` — replace BLOCKED banner with **Superseded** pointer to `docs/implementation-plans/2-convergence-non-severity-advisories.md`; record which seed decisions shipped vs what remains on #158.
  - `docs/implementation-plans/plan-seeds/impact-recurrence-02-loop-stop.md` — same supersession treatment; state loop-stop half is **not** shipped and remains on #158 (or a future plan), not this seed.

## Implementation

### Doc ownership

| Fact class | Home in this step | Do not duplicate here |
| --- | --- | --- |
| Partial closure of #158 / #248 | `BACKLOG.md` | Long classifier mechanics (plan Architecture) |
| Assistant-facing “advisory vs gate” rule | `CLAUDE.md` **Convergence policy boundary** | Full `render_diagnosis` output shape |
| Seeds are not pickable | Superseded banners on the two seed files | Re-authoring plan bodies |

**Rejected alternative:** deleting the seed files — the plan keeps them in `files:` for an in-place supersede edit; moving to `plan-seeds/archive/` is out of scope unless the implementer adds that path explicitly (it is not declared).

### `BACKLOG.md` — partial closure and index hygiene

**#158 — Partially closed**

- Replace **Status** (and any “ready for replacement-plan authoring” / “closed only when part 2 ships” language that implies the blocked two-seed split is still the path) with something in the **Partially closed — …** family, e.g. **Partially closed — recommend-only advisory shipped in `convergence-non-severity-advisories`.** Name what shipped: `classify_impact_recurrence`, collapsed compatible-pass window, `plan-tool convergence` + completeness stderr advisory lines, explicit `impact=high` eligibility, reuse-collapse via adjacent identical finding-id sets, no ramp-in (live against existing sidecar history).
- **Remaining / follow-up:** none for #158 — hard loop-terminating
  `recurring_high_impact_seam` / `structural_stop` **withdrawn** with #158
  closed 2026-08-11. Do **not** leave that stop as open backlog work.
- **Decisions to record as settled** (from the superseded seeds, now implemented in the advisory plan): no “offered to `completeness-apply`” marker; openness from eligibility + still-open in newest pass only; no `RegionTrend` / `spinning` substrate.
- **Rewrite seed pointers:** the two `impact-recurrence-0*` paths are **superseded** by `docs/implementation-plans/2-convergence-non-severity-advisories.md`, not active authoring inputs.
- Trim or qualify acceptance bullets that require completeness/reconcile **termination** with `structural_stop` — move those to **Remaining** (or strike with “not shipped”).
- Update **Related** entries that say #158 “already issues a structural stop” (e.g. **#248** Related bullet) to **recommend-only advisory** unless/until loop-stop work ships.

**#248 — Edit-drift advisory portion shipped**

- Keep the existing **Partially closed** bare-bar status from `stage-differentiated-blocking`.
- Under **Remaining**, split edit-drift:
  - **Shipped here:** deterministic edit-drift *advisory* (`classify_edit_drift`, strict-majority of new `is_blocking_finding`-eligible findings matching window-local prior-apply set, `_matches` identity, `plan-tool convergence` + completeness stderr) — recommend-only, no iterate stop.
  - **Still open → #231:** hard edit-drift exit, durable apply→finding provenance, loop-terminating behavior tied to “audit-induced growth” / bad-fix vs mis-decomposition (per #248’s second stop-condition prose and #231’s Outcome).
- Do not claim the bare-stage bar or stage-differentiated blocking changed in this plan.

**Index / board hygiene** (same file; grep-driven):

- **Authored plans** table — add `convergence-non-severity-advisories` with disposition **Shipped (YYYY-MM-DD)** — #158 closed (hard loop stop withdrawn).
- **T2 — convergence & structural-remedy machinery** — **#158** closed as recommend-only pause advisory; drop live structural stop from the open #159/#160 cluster.
- **Quality/accuracy `gate-signal` rollup** — same: #158 closed, no open structural-stop promise.
- Leave **#231** status unchanged except cross-links from #248 Remaining.

### `CLAUDE.md` — Convergence policy boundary

Extend the section after the three blocking predicates (and the existing `arm-clustering` non-blocking bullet). Add a short **Recommend-only convergence advisories** block:

- **`impact_recurrence`** — `classify_impact_recurrence` over collapsed completeness history; fires on explicit `RunFinding.impact == "high"` seam recurrence without shrinkage across `WINDOW_SIZE` compatible passes; rendered via `_impact_recurrence_lines` on `plan-tool convergence` and completeness stderr when history qualifies (step 6).
- **`edit_drift`** — `classify_edit_drift` with `is_blocking_finding` at the window’s persisted `audit_stage` (same bar as `_open_medium_plus`); strict-majority match to window-local prior-apply set; rendered via `_edit_drift_lines` on the same surfaces.
- **Explicit boundaries (required):** neither advisory feeds `should_continue`, `ConvergenceState.has_blocking_findings`, `_completeness_has_blocking_findings`, `--fail-on-findings`, or exit codes; neither revives `spinning` / `FORK_*` / `recurring_regions`; `self-seeded-finding` in `plan_tool/audit_shapes.py` stays `judgment_only` — edit-drift complements it, does not gate on it; impact-recurrence does not use `is_blocking_impact` for eligibility.
- **Precedent:** same stance as `finding_churn` and `structural_recurrence` on `ConvergenceDiagnosis` — diagnosis signals only.

Keep edits **terse** (a few bullets); depth stays in the plan and `plan_tool/convergence_diagnosis.py`. Do not paste the plan Architecture table.

**Heading / anchor guard:** if any new heading is added, `rg` inbound `#` links to changed anchors under `CLAUDE.md` consumers (usually none).

### Seed files — in-place supersede

For **both** `impact-recurrence-01-classifier.md` and `impact-recurrence-02-loop-stop.md`:

1. Replace the top **BLOCKED** blockquote with a **Superseded** blockquote, e.g. `> **Superseded (YYYY-MM-DD):** do not author from this seed. Shipped in docs/implementation-plans/2-convergence-non-severity-advisories.md as recommend-only advisories; hard loop-terminating structural stop withdrawn with BACKLOG #158 closed.`
2. Keep the file (do not empty-delete body unless backlog hygiene requires a one-line stub — prefer retaining body as historical context with the superseded banner winning).
3. Update **Backlog reconciliation** sections so they no longer instruct future plans to “update #158 on part 1 ship” — point at the shipped plan and #158 partial closure instead.

Record in the part-1 seed: classifier half concepts shipped without `plan_tool/impact_recurrence.py` as a separate module if the implementer landed classifiers in `convergence_diagnosis.py` per plan Architecture.

Record in the part-2 seed: loop wiring **withdrawn** with #158 closed — do not leave Remaining open work.

### Vocabulary sweep (required on the four edited files)

| Stale claim | Replace with |
| --- | --- |
| #158 “not implemented” / “ready for replacement-plan authoring” | **Partially closed** — advisory shipped |
| #158 Outcome = live `structural_stop` as shipped | **Withdrawn** — #158 closed as advisory-only |
| #248 “Remaining: edit-drift exit” (undifferentiated) | advisory **shipped**; hard exit → **#231** |
| Seeds “BLOCKED — do not run” without supersede pointer | **Superseded** + link to `2-convergence-non-severity-advisories.md` |
| CLAUDE.md implies only `arm-clustering` is non-blocking advisory | also `impact_recurrence` / `edit_drift` on convergence diagnosis |
| `spinning` / `FORK_*` / `recurring_regions` as active paths | retired (#251); cite only as history in BACKLOG if needed |

Also run: `rg 'impact-recurrence-0[12]' BACKLOG.md` — every hit should read superseded or historical, not “author from seed”.

### Constraints and gotchas

- **Non-code only** — if steps 5–6 are not landed, fix execution order; do not edit code in this step.
- **Do not** mark #158 fully closed or remove it.
- **Do not** implement or close **#231**.
- **Do not** edit `docs/AUDIT_FLOW.md`, `integrations/shared/DIRECTIVES.md`, or `RUNBOOK.md` (not in `files:`).
- **Do not** widen blocking predicates or document loop-terminating stops as shipped.
- When correcting **#248** Related text about #158, change only the false “structural stop ships” implication — do not rewrite the measurement table or bare-bar prose.

## Tests

### Verification (non-code step)

The test-authoring gate does not apply (`change_type: non-code`). Run before marking the step done:

1. `rg -n 'Closed — shipped' BACKLOG.md` — **#158** status includes closed wording; **#248** still shows partially closed for bare bar.
2. `rg -n 'structural_stop|recurring_high_impact_seam' BACKLOG.md` — under **#158**, these appear only as **withdrawn** / do-not-author history, not as open Remaining work.
3. `rg -n 'edit-drift' BACKLOG.md` — **#248** distinguishes advisory shipped vs hard exit → **#231**.
4. `rg -n 'impact-recurrence-01-classifier|impact-recurrence-02-loop-stop' BACKLOG.md` — no “author from seed” without **superseded** qualification.
5. `rg -n 'Superseded|superseded' docs/implementation-plans/plan-seeds/impact-recurrence-01-classifier.md docs/implementation-plans/plan-seeds/impact-recurrence-02-loop-stop.md` — both seeds point at `2-convergence-non-severity-advisories.md`.
6. `rg -n 'BLOCKED — do not run' docs/implementation-plans/plan-seeds/impact-recurrence-0*.md` — returns nothing (or only inside quoted history).
7. `rg -n 'impact_recurrence|edit_drift|classify_impact_recurrence|classify_edit_drift' CLAUDE.md` — convergence policy boundary names both advisories.
8. `rg -n 'should_continue|fail-on-findings|is_blocking_impact' CLAUDE.md` — new advisory bullets state they do **not** alter those gates (wording need not use every symbol, but the non-gate rule must be explicit).
9. `rg -n 'convergence-non-severity-advisories' BACKLOG.md` — executed-plan / disposition row present.
10. `git diff --stat` — only the four declared files changed.

## Acceptance criteria

- BACKLOG **#158** status reads **Closed — shipped** with hard loop
  `structural_stop` / `recurring_high_impact_seam` marked **withdrawn**; entry
  is not deleted (provenance).
- BACKLOG **#248** records the thin edit-drift **advisory** as shipped in `convergence-non-severity-advisories` and routes hard exit / provenance to **#231**.
- Both `impact-recurrence-0*` seeds carry a **Superseded** banner linking `docs/implementation-plans/2-convergence-non-severity-advisories.md` and do not read as pickable blocked work.
- `CLAUDE.md` **Convergence policy boundary** documents `impact_recurrence` and `edit_drift` as recommend-only diagnosis signals on `plan-tool convergence` and completeness stderr, separate from the three blocking predicates and from `arm-clustering`.
- Index/board prose (T2, Quality rollup, #248 Related, authored-plans table) no longer claims #158’s structural stop shipped or the two seeds are the active authoring path.
- Verification checklist items 1–10 pass.
- No edits outside the four declared `files:` paths.

## References

- `docs/implementation-plans/2-convergence-non-severity-advisories.md` — shipped plan Architecture, Out of scope, and acceptance criteria this step must mirror in backlog wording.
- `docs/implementation-plans/plan-details/convergence-non-severity-advisories/05-wire-both-advisories-diagnose.md` — `ConvergenceDiagnosis` fields and `render_diagnosis` wiring to name in `CLAUDE.md`.
- `docs/implementation-plans/plan-details/convergence-non-severity-advisories/06-surface-advisories-on-completeness.md` — completeness stderr hook and sidecar gating to mention in #158 shipped bullets.
- `docs/implementation-plans/plan-details/stage-differentiated-blocking/07-update-gate-docs-close-backlog-91-248.md` — partial-closure and index-hygiene pattern for #248’s prior half.
- `plan_tool/convergence_diagnosis.py` — `classify_impact_recurrence`, `classify_edit_drift`, `render_diagnosis`, advisory line helpers (landed names).
- `plan_tool/audit_shapes.py` — `self-seeded-finding` registry entry stays `judgment_only`.

## Applicable guardrails

- **Plan intent** — document two recommend-only advisories; do not describe them as iterate stops or exit-code flips.
- **Plan Out of scope** — do not mark loop-terminating stops, `--fail-on-findings` changes, `spinning` / `FORK_*` revival, automatic structural remedies, or #231 provenance as shipped; route hard edit-drift exit to **#231**.
- **Step intent** — BACKLOG partial closure accuracy for #158 and #248; seed supersede; `CLAUDE.md` policy boundary only — not a full doc sweep of every convergence surface.

## Deferred

- `docs/AUDIT_FLOW.md` stderr advisory hook and source-map rows — plan Deferred (post-ship doc work); not this step’s `files:` list. Step 6 ships emission only.
- Live completeness/reconcile `structural_stop` loop integration — **withdrawn**
  with BACKLOG **#158** closed (supersedes `impact-recurrence-02-loop-stop`
  seed scope; do not re-open as open work).
- Hard edit-drift exit and apply→finding provenance — BACKLOG **#231**; not implemented here.
- `integrations/shared/DIRECTIVES.md` operator-facing convergence advisory prose — out of scope; assistants use `CLAUDE.md` for the policy boundary update.
- Reporting polish **#260** and four-loop blocking **#261** — unchanged by this plan; do not fold into this step.
