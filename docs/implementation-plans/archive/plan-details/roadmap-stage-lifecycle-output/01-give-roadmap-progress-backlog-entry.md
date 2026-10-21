> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 1 — Give the roadmap-progress backlog entry a unique identifier, narrow its promise, and repoint every live queue reference

## Summary

This step assigns the roadmap transition-status backlog entry the currently unused identifier `#337` and retains `#323` for view-reconciliation work. It updates `BACKLOG.md` and both declared backlog arcs so every live queue reference names the intended entry. The key decision is that the entry promises visibility into the last confirmed transition, not evidence that a quiet backend call remains live. On green, the active queue and both arcs consistently route the bounded roadmap-status work under one identifier.

## Table of Contents

- [Summary](#summary) — The completed documentation and queue-routing result.
- [Table of Contents](#table-of-contents) — Links to each section in this detail.
- [Why](#why) — The ambiguity and promise mismatch this step removes.
- [Input](#input) — The current duplicate identifier and live routing records.
- [Files (creates vs edits)](#files-creates-vs-edits) — The three documentation files this step changes.
- [Implementation](#implementation) — The identifier, promise, and reference sweep.
- [Tests](#tests) — Non-code verification for the documentation change.
- [Acceptance criteria](#acceptance-criteria) — Observable identity and routing outcomes.
- [References](#references) — The backlog and arc sources that define this work.
- [Applicable guardrails](#applicable-guardrails) — Plan boundaries the wording must preserve.
- [Deferred](#deferred) — Adjacent work that remains outside this step.

## Why

`BACKLOG.md` currently gives both roadmap transition status and unrelated view reconciliation the identifier `#323`, so queue selections can point at the wrong work. The status entry also reads as though it lets an operator distinguish a healthy quiet call from a stalled one, while the plan deliberately provides only confirmed transitions. A unique identifier and a smaller promise keep the active queue, the roadmap arc, and the seed-ingestion route accurate before implementation begins.

## Input

- **Current identifier collision:** `BACKLOG.md` contains both the roadmap-progress entry and the `#323 — Share the ordering/plan reconciliation between \`--view walk\` and \`--view html\`` entry.
- **Live queue consumers:** `BACKLOG.md`'s `## Execution-routing arcs` and `### Now / Next / Blocked / Parked (working set)`, plus `docs/implementation-plans/backlog-arcs/backlog-arc-roadmap.md` and `docs/implementation-plans/backlog-arcs/backlog-arc-seed-ingestion.md`, currently use the progress entry’s duplicated number.
- **Identifier availability:** `#337` is unassigned in `BACKLOG.md` at HEAD. Confirm that it remains unassigned immediately before editing.

## Files (creates vs edits)

- **New files:** None.

- **Existing files (edits only):**
  - `BACKLOG.md` — Rename the roadmap-progress entry to `#337`, narrow its contract to confirmed transition status, and repoint its live catalog and Now-board references.
  - `docs/implementation-plans/backlog-arcs/backlog-arc-roadmap.md` — Repoint the progress item in `## Real-world evidence source`, `## Ordered route`, `## Exit and handoff`, and `## Out of scope`; preserve its transition-only limitation.
  - `docs/implementation-plans/backlog-arcs/backlog-arc-seed-ingestion.md` — Repoint the active-queue prerequisite in `## Ordered route` without changing the existing handoff order to `#333`.

## Implementation

- **Foundational logic:** give the roadmap transition-status queue item one unambiguous identity and one bounded operator-facing promise.

- **Reserve `#337` for roadmap progress.** Confirm `#337` is unassigned immediately before editing, then change only the entry headed by the roadmap transition-status title to `#337`. Retain `#323` for the view-reconciliation entry headed `Share the ordering/plan reconciliation between \`--view walk\` and \`--view html\``. If `#337` is occupied, stop this step and return the plan for re-grounding; do not select a replacement inside this delivery, because every later step closes this exact identifier.

- **Inventory by identifier and meaning before editing.** Search the declared files for `#323` and for progress-specific wording such as `roadmap operator progress` and `concise lifecycle output`. Classify each match by the entry it means instead of replacing every `#323` mechanically. The `BACKLOG.md` execution-routing catalog and Now board refer to roadmap progress; the view-reconciliation heading remains a `#323` reference.

- **Narrow the progress entry’s promise.** Update the roadmap-progress entry’s `What`, `Outcome`, and related scope language in `BACKLOG.md` so it commits to concise stderr facts about accepted range and confirmed stage transitions on the normal roadmap stage-run path. It must state that a quiet period after a transition remains ambiguous and is not a liveness claim. Do not turn the entry into a heartbeat, job-control, streaming, or cross-command observability proposal.

- **Keep queue ordering intact.** Update `BACKLOG.md`’s `## Execution-routing arcs` summary and `### Now / Next / Blocked / Parked (working set)` row so they name `#337` for progress while keeping the existing next-work ordering. In `docs/implementation-plans/backlog-arcs/backlog-arc-seed-ingestion.md`’s `## Ordered route`, make `#337` the active prerequisite that must ship or be parked before `#333` is selected.

- **Repoint the roadmap arc by heading.** In `docs/implementation-plans/backlog-arcs/backlog-arc-roadmap.md`, update every progress-specific reference under `## Real-world evidence source`, `## Ordered route`, `## Exit and handoff`, and `## Out of scope` to `#337`. Preserve the existing relationship to `#328`, `#329`, and `#330`; only the roadmap-progress identifier and its transition-only wording change.

- **Leave the separate view-reconciliation owner alone.** `plan_tool/roadmap_html.py` contains a `BACKLOG.md` reference for view-reconciliation sharing. It already names the entry that keeps `#323`, so this documentation-only step must not edit that code comment or widen into the view-rendering backlog item.

## Tests

No automated test file applies. This is a `change_type: non-code` step, so the plan’s test-authoring gate does not require a production or unit-test change.

### Verification (non-code step)

1. **Unique backlog headings** — Confirm `BACKLOG.md` has one `#323` heading for view reconciliation and one `#337` heading for roadmap transition status.
2. **Scoped identifier sweep** — Search all three declared files for `#323` and verify every remaining match means view reconciliation, not roadmap progress.
3. **Progress-reference sweep** — Search the three declared files for the roadmap-progress title and related queue wording; verify every live reference uses `#337`.
4. **Queue-order check** — Read `BACKLOG.md`’s Now board and `docs/implementation-plans/backlog-arcs/backlog-arc-seed-ingestion.md`’s `## Ordered route` to confirm `#337` remains ahead of `#333`.
5. **Promise check** — Read the revised `BACKLOG.md` entry and `docs/implementation-plans/backlog-arcs/backlog-arc-roadmap.md` sections to confirm they describe confirmed transitions only and do not claim liveness from silence.
6. **Footprint check** — Confirm the diff changes only `BACKLOG.md`, `docs/implementation-plans/backlog-arcs/backlog-arc-roadmap.md`, and `docs/implementation-plans/backlog-arcs/backlog-arc-seed-ingestion.md`.

## Acceptance criteria

- `BACKLOG.md` contains exactly one `#323` entry, and it is the view-reconciliation entry.
- `BACKLOG.md` contains exactly one `#337` entry, and it is the roadmap transition-status entry.
- Every live queue reference to roadmap progress in the three declared files names `#337`.
- `docs/implementation-plans/backlog-arcs/backlog-arc-seed-ingestion.md` keeps `#337` as the active item before `#333`.
- The revised progress entry promises only the last confirmed roadmap transition; it must not imply that a quiet backend call is healthy or live.
- The revised backlog and arc wording preserves the plan’s bounded normal-route status scope without adding another command, durable state, or observability surface.
- No file outside the declared three-file scope changes.

## References

- [BACKLOG.md — Read the duplicate entries, execution-routing catalog, and Now board that require semantic repointing.
- [docs/implementation-plans/backlog-arcs/backlog-arc-roadmap.md — Read the roadmap arc’s evidence, route, exit, and scope wording for the progress entry.
- [docs/implementation-plans/backlog-arcs/backlog-arc-seed-ingestion.md — Read the active-queue prerequisite that must continue to precede `#333`.
- [docs/how-to/roadmap-demo.md](../../../how-to/roadmap-demo.md) — Read the operator observation that supports transition status but does not prove a liveness requirement.

## Applicable guardrails

- **Normal roadmap stage-run only:** The plan’s `## Scope guardrails`, normal-path boundary limits this step’s backlog wording to the selected stage-run path.
- **Preserved command interfaces:** The plan’s `## Scope guardrails`, interface-preservation boundary requires the documentation to avoid promising changed stdout, exit, artifact, retry, or run-log behavior.
- **Transition status, not liveness:** The plan’s `## Scope guardrails`, no-heartbeat boundary requires the revised promise to describe confirmed transitions without presenting silence as a health signal.
- **No widened command coverage:** The plan’s `## Scope guardrails`, other-route exclusion requires this step to leave progress for other roadmap routes and commands outside the entry’s contract.

## Deferred

- **View-reconciliation consolidation** — `BACKLOG.md` `#323` and its supporting `plan_tool/roadmap_html.py` reference remain the separate view-rendering concern.
- **Status-line implementation and later user documentation** — Steps 2 through 5 own the code, command presentation, and delivered-behavior documentation; this step only prepares their unambiguous backlog contract.
