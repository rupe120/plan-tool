> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 4 — Remove the fixed receipt-persistence backlog records while preserving remaining evidence bugs and risks

## Summary

**Historical 2026-08-27:** Retire the resolved receipt-persistence bug record
and its queue and arc routing references. Update `BACKLOG.md`,
`BUG_BACKLOG.md`, and the two backlog arcs without selecting a replacement
priority item. The raw-YAML, version-1 evidence, and symlink-risk records were
then independent active work. On green, no declared backlog surface treats
receipt persistence as open work.

## Table of Contents

- [Summary](#summary) — The cleanup outcome and its boundaries.
- [Table of Contents](#table-of-contents) — Links to each detail section.
- [Why](#why) — Why stale routing must leave the active backlog.
- [Input](#input) — The completed plan outcome that permits retirement.
- [Files (creates vs edits)](#files-creates-vs-edits) — The four backlog artifacts this step updates.
- [Implementation](#implementation) — Required record removal and preservation rules.
- [Tests](#tests) — Non-code verification for the cleanup.
- [Acceptance criteria](#acceptance-criteria) — Observable retirement and preservation checks.
- [Applicable guardrails](#applicable-guardrails) — Plan boundaries for this documentation-only step.
- [Deferred](#deferred) — Remaining evidence work outside this cleanup.

## Why

`BUG_BACKLOG.md:## BUG`, `BACKLOG.md:## Priority`, and both backlog arcs still direct work to receipt persistence even though steps 1–3 provide the scoped commit, shared-read lifecycle, and public guidance. Those stale entries can send a later session toward work that no longer exists and obscure the remaining evidence defects and storage risk that still need their own decisions.

## Input

- **Completed receipt-persistence outcome:** Use the landed behavior and guidance from steps 1–3 of `docs/implementation-plans/2-escalation-receipt-persistence.md:steps` as the retirement precondition. Verify the implementation and public documentation, rather than treating this detail or the plan text as proof.

- **Fixed record boundary:** `BUG_BACKLOG.md:## BUG` contains the receipt-persistence entry headed `Escalation evidence receipts are never committed, so every one silently defeats its own accountability purpose`. Retire that whole record, including its scope and plan-routing bullets.

- **Historical remaining records:** At this detail's 2026-08-27 delivery,
  preserve the raw-YAML and version-1 BUG entries, plus `BUG_BACKLOG.md:## RISK`’s
  `Immutable evidence storage follows namespace and matching-final symlinks`
  record. The two BUG entries are later resolved in `ea6b41fe` and `606602f6`.

## Files (creates vs edits)

- **New files:** None.

- **Existing files (edits only):**
  - `BACKLOG.md` — Remove receipt persistence from `## Priority`’s queue facts, working-set table, bug-triage wording, and `Current selected concrete pick` text without promoting another item.
  - `BUG_BACKLOG.md` — Delete only the resolved top-level receipt-persistence BUG record.
  - `docs/implementation-plans/backlog-arcs/backlog-arc-roadmap.md` — Remove the selected receipt-persistence handoff from item 4 in `## Ordered route` while retaining the separate symlink-risk route.
  - `docs/implementation-plans/backlog-arcs/bug-backlog-draining-arc.md` — Remove the selected receipt-persistence route, its delivery checks, and its exit from `### Phase 4 — Restore durable escalation evidence`; remove the stale receipt-persistence prerequisite wording and avoid an obsolete BUG/RISK count in `## Purpose and boundary`.

## Implementation

- **Apply one retirement predicate.** Remove a record only when it says receipt persistence remains selected, unfinished, or necessary. Do not add a completed-entry summary; `BUG_BACKLOG.md` states that Git history is the delivery record.

- **Retire the BUG entry as a unit.** Delete the whole receipt-persistence record under `BUG_BACKLOG.md:## BUG`, not only its title or its `Plan` bullet. Leave the following BUG headings and the `## RISK` section unchanged.

- **Clear every queue selection without choosing a successor.** In `BACKLOG.md:## Priority`, remove the receipt-persistence queue fact, `Now` row, bug-triage selection claim, and `Current selected concrete pick` block. Keep the existing next, blocked, parked, and evidence-gated items in their current roles; selecting new work is outside this step.

- **Remove only the stale arc route.** In `docs/implementation-plans/backlog-arcs/backlog-arc-roadmap.md:## Ordered route`, delete the receipt-persistence plan reference from item 4 while retaining its matching-final and namespace-symlink risk. In `docs/implementation-plans/backlog-arcs/bug-backlog-draining-arc.md:### Phase 4 — Restore durable escalation evidence`, remove the selected route, its proof list, and its receipt-specific exit condition.

- **Preserve independent evidence work.** Do not alter the version-1 evidence BUG merely because it mentions escalation receipts. Keep `docs/implementation-plans/backlog-arcs/bug-backlog-draining-arc.md:### Phase 5 — Conditional risk closure` and its symlink-resistant-storage route unchanged except for removing wording that makes it depend on receipt persistence.

- **Use precise residual searches.** Search the four declared files for `escalation-receipt-persistence`, `receipt persistence`, and `shared-evidence failure`; each must be absent after the edit. Do not use a broad `receipt` zero-match rule, because the version-1 evidence BUG legitimately retains that word.

## Tests

**No unit-test file changes:** This non-code step is exempt from the plan’s test-authoring gate; verification must establish accurate backlog routing and preservation.

### Verification (non-code step)

1. `verify_receipt_persistence_route_is_absent` — A precise residual search finds no retired slug, receipt-persistence phrase, or shared-evidence-failure route in the four declared files.

2. `verify_fixed_bug_record_is_removed_as_one_unit` — `BUG_BACKLOG.md:## BUG` no longer contains the fixed entry or any of its fields.

3. `verify_remaining_evidence_records_survive` — The raw-YAML BUG, version-1 evidence BUG, and matching-final/namespace-symlink RISK retain their headings and content.

4. `verify_no_successor_is_selected` — `BACKLOG.md:### Now / Next / Blocked / Parked (working set)` and `Current selected concrete pick` do not silently promote another candidate.

5. `verify_drain_arc_has_no_stale_count_or_route` — `docs/implementation-plans/backlog-arcs/bug-backlog-draining-arc.md:## Purpose and boundary` avoids a stale BUG/RISK count, and Phase 4 has no open receipt-persistence action.

6. `verify_markdown_links_and_headings_remain_valid` — Review the edited local links and headings in all four files for valid targets and intact table structure.

## Acceptance criteria

- `BUG_BACKLOG.md` does not contain the fixed receipt-persistence BUG entry.

- `BACKLOG.md` does not identify `escalation-receipt-persistence` as current, selected, or open work.

- Neither backlog arc routes work to `docs/implementation-plans/2-escalation-receipt-persistence.md`.

- At this detail's delivery, the raw-YAML feedback BUG, version-1 evidence BUG,
  and immutable-evidence symlink RISK remained active records. The first two
  are later resolved in `ea6b41fe` and `606602f6`.

- `docs/implementation-plans/backlog-arcs/bug-backlog-draining-arc.md` retains its separate Phase 5 hardening route.

- No replacement `Now` item or current concrete pick is introduced by this step.

- Precise residual searches for the retired receipt-persistence route return no matches in the four declared files.

## Applicable guardrails

- **The plan’s `## Plan intent`** — Treat the landed shared-receipt behavior as the completion condition; this step changes only its backlog routing.

- **The plan’s step intent** — Stop directing work to receipt persistence while keeping unrelated evidence defects and risks visible.

- **The plan’s `## Out of scope`** — Do not introduce a general commit design, CLI change, or evidence-storage change while cleaning up the records.

## Deferred

- Raw-YAML feedback handling and version-1 evidence receipts — Keep their existing `BUG_BACKLOG.md` records for separately scoped work.

- Symlink-resistant evidence storage — Keep its `BUG_BACKLOG.md:## RISK` record and `docs/implementation-plans/backlog-arcs/bug-backlog-draining-arc.md:### Phase 5 — Conditional risk closure` route unchanged.

- Successor prioritization — Leave selection of the next backlog item to the normal triage process.
