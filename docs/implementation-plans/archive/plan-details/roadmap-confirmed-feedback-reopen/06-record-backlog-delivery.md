> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 6 — Record the delivered feedback reopen in the backlog

## Summary

Retire #315’s active-candidate framing and record the delivered confirmed feedback reopen proof across `BACKLOG.md`, `BUG_BACKLOG.md`, and `docs/implementation-plans/backlog-arcs/backlog-arc-roadmap.md`. Keep the record limited to the shipped operator-confirmed recovery, its redacted transition, and fresh receipt identity. Update #242’s dependency wording so it treats the proof as an input to later retention work, not as a solution to it. On green, none of the three tracking surfaces says that no supported reopen path exists, and none claims a general recovery capability or a Integration reissue shipped.

## Table of Contents

- [Summary](#summary) — The documentation outcome this step records.
- [Table of Contents](#table-of-contents) — Links to each section in this detail.
- [Why](#why) — Why the tracking records must change after delivery.
- [Input](#input) — The shipped proof and current tracking statements this step reads.
- [Files (creates vs edits)](#files-creates-vs-edits) — The three documentation files updated here.
- [Implementation](#implementation) — How to align the delivered-state wording without widening scope.
- [Tests](#tests) — Non-code verification for the tracking updates.
- [Acceptance criteria](#acceptance-criteria) — Observable conditions for complete backlog retirement.
- [Applicable guardrails](#applicable-guardrails) — Scope limits that bind this documentation update.
- [Deferred](#deferred) — Work this record must continue to leave open.

## Why

`BACKLOG.md`’s #315 entry, `BUG_BACKLOG.md`’s version-1 receipt incident, and the roadmap arc all currently describe a missing reopen path. Once step 5 delivers and verifies the confirmed command, that wording becomes false and can send a later session toward work that is already complete. #242 still needs the proof’s bounded result as design input, but it must not treat the proof as retention, response history, or a general evidence-recovery solution.

## Input

- **Step 5’s shipped behavior:** step 5 supplies the landed `--reopen-feedback` action, its explicit confirmation, and its focused regression coverage. Read the landed command behavior and tests before writing delivery language; the shipped code and tests win if a planned term differs.

- **Active #315 record:** `BACKLOG.md:**#315 — Give a feedback row a way back to eligible when the evidence backing its response becomes invalid**` contains the candidate framing that this step retires.

- **Retention dependency:** `BACKLOG.md:**#242 — A roadmap revision discards what it resolves**` contains the paused retention route that must retain #315 as a bounded input.

- **Incident record (historical 2026-08-27):** the version-1 receipt BUG then
  owned the still-unreadable Integration receipts. It is later closed as an
  archive-safe, Integration-local won't-do in `606602f6`; the broader #313 question
  remains conditional.

- **Roadmap route:** `docs/implementation-plans/backlog-arcs/backlog-arc-roadmap.md:## Real-world evidence source` and its `## Ordered route` entry for #242 describe the current planning route and its decision gate.

## Files (creates vs edits)

- **New files:** None.

- **Existing files (edits only):**
  - `BACKLOG.md` — Replace #315’s active candidate with a compact dated delivery record, and update `#242`’s status/dependency wording.
  - `BUG_BACKLOG.md` — Replace the incident’s stale no-reopen claim with the delivered proof’s limited relationship to the still-open receipt problem.
  - `docs/implementation-plans/backlog-arcs/backlog-arc-roadmap.md` — Mark the #315 route delivered in `## Real-world evidence source` and keep the #242 route scoped to its remaining work.

## Implementation

- **Foundational logic: delivery-state rewrite.** Change every #315 tracking statement from an unshipped capability claim to the same bounded delivered outcome, while preserving each document’s own owner and purpose.

- **Use the landed proof as the source of truth.** Describe only the behavior step 5 has actually delivered: an explicitly confirmed operator path for one safe selected row, a redacted reopen transition, and a fresh next-receipt identity. State that confirmation is the authority for the unavailable-evidence determination; do not restate implementation mechanics that the code and plan own.

- **Retire #315 as active work.** In `BACKLOG.md:**#315 — Give a feedback row a way back to eligible when the evidence backing its response becomes invalid**`, use the established compact delivered-record form, such as `BACKLOG.md:#164`, rather than leave #315 selectable as future capability work. Remove candidate-only fields whose future-tense scope no longer applies.

- **Keep the delivery record narrow.** Name the canonical delivered plan, `docs/implementation-plans/2-roadmap-confirmed-feedback-reopen.md`, and state the actual delivery date. Do not claim that the proof validates legacy evidence, reissues a receipt, preserves response history, or permits ordinary feedback reopening.

- **Correct #242’s dependency text.** In `BACKLOG.md:**#242 — A roadmap revision discards what it resolves**`, replace the claim that a responded row has no return path with the delivered proof’s limited role. Keep #242 paused on its existing preflight and redesign conditions; the proof informs its future design but does not complete or reduce its retention scope.

- **Historical incident boundary.** At this detail's delivery, the version-1
  BUG stated that #315 provided a bounded recovery path for a safety-checked,
  operator-confirmed row without proving either cited Integration row was reopened or
  reissued. The later archive-safe disposition closes that narrow incident;
  this detail does not change #315's bounded proof.

- **Update both roadmap-arc references.** In `docs/implementation-plans/backlog-arcs/backlog-arc-roadmap.md:## Real-world evidence source`, change the canonical route from planning to delivered and retain the warning that `roadmap-feedback-evidence-reopen` is not an authorized follow-up. In the #242 entry under `## Ordered route`, keep the delivered proof as a constraint on later redesign without presenting it as #242 delivery.

- **Sweep the shared wording.** Before finishing, search all three declared files for #315, `proposed_response`, and the stale no-supported-reopen wording. Apply the same delivery boundary at every matching tracking statement, or leave a match only when it accurately describes a separate unresolved fact.

- **Do not manufacture production evidence.** The roadmap arc’s `### Canonical Plan-tool delivery gate` still controls Integration testing. This documentation step may record the shipped tool behavior, but it must not claim the incident rows were exercised in Integration unless that separately recorded evidence exists.

## Tests

**No test files:** This is a `non-code` step, so the plan’s test-authoring gate does not apply. It changes only tracked documentation and uses the following verification instead.

### Verification (non-code step)

1. **#315 delivery record check** — Confirm `BACKLOG.md` no longer presents #315 as an active candidate and names only the delivered bounded proof.

2. **#242 dependency check** — Confirm `BACKLOG.md:**#242 — A roadmap revision discards what it resolves**` treats #315 as a delivered input without claiming #242 shipped or changed scope.

3. **Historical incident-boundary check** — Confirm the then-live incident
   record distinguished the delivered command from a verified reissue of either
   historic receipt. `606602f6` later closes that record as a Integration-local
   archive-safe won't-do.

4. **Arc consistency check** — Confirm `docs/implementation-plans/backlog-arcs/backlog-arc-roadmap.md:## Real-world evidence source` and its #242 `## Ordered route` entry use the same delivered-proof boundary.

5. **Stale-wording sweep** — Search `BACKLOG.md`, `BUG_BACKLOG.md`, and `docs/implementation-plans/backlog-arcs/backlog-arc-roadmap.md` for the former no-supported-reopen claim and confirm no remaining match describes #315 as unimplemented.

## Acceptance criteria

- `BACKLOG.md` records #315 as delivered rather than active future work and identifies `docs/implementation-plans/2-roadmap-confirmed-feedback-reopen.md` as its canonical delivery record.

- `BACKLOG.md`’s #242 entry names the delivered proof as a bounded input while preserving #242’s paused retention work and existing decision gate.

- `BUG_BACKLOG.md` no longer says the incident has no reopen mechanism, but still does not claim either historic version-1 receipt is readable, reopened, or reissued.

- `docs/implementation-plans/backlog-arcs/backlog-arc-roadmap.md` identifies #315 as delivered and keeps `roadmap-feedback-evidence-reopen` unauthorized.

- A search across the three declared files finds no stale statement that #315 has no supported reopen path, and the replacement wording does not claim a general recovery, response-history, or #242 capability shipped.

## Applicable guardrails

- **The plan’s “## Plan intent”, bounded recovery proof:** Record only the operator-confirmed feedback reopen and fresh-receipt result that shipped; do not turn the outcome text into a broader capability claim.

- **The plan’s “## Step intent”, tracking-surface update:** Limit edits to retiring stale #315 framing and aligning #242, the bug record, and the roadmap arc with that delivery.

- **The plan’s “## Out of scope”, excluded capability work:** Do not document general evidence recovery, response provenance, retention, or lifecycle editing as delivered behavior.

## Deferred

- General evidence recovery and response provenance — Require a new seed based on an observed limitation; this delivery record must not imply either capability exists.

- Reopening or reissuing the historic Integration rows — Remains separate from recording the delivered tool behavior and stays with the version-1 receipt incident in `BUG_BACKLOG.md`.

- #242 retention redesign — Remains owned by `BACKLOG.md`’s #242 route and its separate plan.
