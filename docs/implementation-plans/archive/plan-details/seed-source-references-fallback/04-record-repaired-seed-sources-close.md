> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 4 — Record the repaired seed sources and close BACKLOG #351

## Summary

Record the completed References-fallback repair in `docs/reference/contracts/seed-ingestion.md`, `docs/implementation-plans/backlog-arcs/backlog-arc-seed-ingestion.md`, and `BACKLOG.md`. Update the producer inventory and arc order from pending work to verified compatibility, with BACKLOG #327 as the next scoped ingestion change. Keep the implementation contract unchanged: this step documents the evidence from steps 1–3 and changes no production code or tests. On green, no work queue or contract text presents #351 as active work.

## Table of Contents

- [Summary](#summary) — The documentation-only outcome and handoff.
- [Table of Contents](#table-of-contents) — Links to each section.
- [Why](#why) — Why the completed repair needs a consistent record.
- [Input](#input) — The dependency evidence this step records.
- [Files (creates vs edits)](#files-creates-vs-edits) — The three documentation surfaces updated.
- [Implementation](#implementation) — The source matrix, backlog closure, and #327 handoff.
- [Tests](#tests) — Non-code verification against the landed repairs.
- [Acceptance criteria](#acceptance-criteria) — Observable documentation and evidence checks.
- [References](#references) — Markdown heading reference.
- [Applicable guardrails](#applicable-guardrails) — Scope boundaries for this documentation step.
- [Deferred](#deferred) — Ingestion-routing work left with #327.

## Why

The current source-compatibility inventory, arc route, and working queue describe #351 as unfinished even though steps 1–3 establish every maintained References fallback. Leaving those claims in place sends a later session toward completed work and hides the real next decision: the bounded source-preparation route in BACKLOG #327.

## Input

- **Step 1 outcome** — Use the landed body-only preflight result from `plan_tool/create.py:validate_from_existing_seed`, plus the validator-clean checked-in seeds and annotate and scope-out outputs. Treat the committed code and green tests as the source of truth.

- **Step 2 outcome** — Use the landed roadmap admission result from `plan_tool/roadmap_gates.py:validate_draft_seed_content`, including its consumers in `plan_tool/roadmap.py:_materialize_plan_seed`, `plan_tool/roadmap.py:_accept_roadmap_seed`, and `plan_tool/roadmap_seed_manifest.py:classify_draft_seeds`.

- **Step 3 outcome** — Use the landed source-plan fallback from `plan_tool/reground.py:render_rebaseline_seed` and its create-preflight coverage.

- **Shared acceptance boundary** — Record compatibility against `plan_tool/create.py:validate_from_existing_seed`; do not infer completion from a producer’s provenance metadata alone.

## Files (creates vs edits)

- **New files:** None.

- **Existing files (edits only):**
  - `docs/reference/contracts/seed-ingestion.md` — refresh `## Generated-source compatibility`, `## Follow-up sequence`, and `## Evidence anchors` to describe the repaired producer set and the remaining #327 work.
  - `docs/implementation-plans/backlog-arcs/backlog-arc-seed-ingestion.md` — update `## Ordered route` and `## Exit and handoff` so #351 is complete and #327 is the next route.
  - `BACKLOG.md` — replace #351 in `### Now / Next / Blocked / Parked (working set)`, update the #331 and #333 status notes, and close the `#351 — Restore the References fallback...` entry with the execution record.

## Implementation

- **Foundational rule:** document a seed producer as repaired only when its output passes the shared `plan_tool/create.py:validate_from_existing_seed` boundary after steps 1–3 land.

- **Refresh the producer matrix from landed behavior.** In `docs/reference/contracts/seed-ingestion.md:## Generated-source compatibility`, record the current References result for the checked-in `plan-seeds/*.md` corpus, `plan_tool/annotate_render.py:render_create_seed`, both `plan_tool/scope_out.py` seed renderers, `plan_tool/reground.py:render_rebaseline_seed`, and the roadmap seed path. Keep the roadmap row clear that `plan_tool/roadmap_gates.py:validate_draft_seed_content` adds create-compatible References admission without replacing roadmap provenance validation.

- **Keep the contract’s future work narrow.** In `docs/reference/contracts/seed-ingestion.md:## Follow-up sequence`, mark #351 complete and leave #327 as the owner of direct-ready routing, preparation outcomes, and lifecycle decisions. Retain the existing ownership of #331, #102, and #332.

- **Correct code anchors that changed meaning.** Update `docs/reference/contracts/seed-ingestion.md:## Evidence anchors` so its description of roadmap admission matches the landed `validate_draft_seed_content` behavior rather than claiming it validates provenance only.

- **Advance the arc without rewriting it.** In `docs/implementation-plans/backlog-arcs/backlog-arc-seed-ingestion.md:## Ordered route`, retain #351 as a completed prerequisite and make #327 the next active route. Update `## Exit and handoff` to name the completed compatibility repair and preserve #327’s existing contract and #102’s separate decision.

- **Close every active #351 pointer in the backlog.** Update the working-set row, the #331 status note, the #333 status note, and the #351 entry in `BACKLOG.md`. Keep #351 as a closed delivery record with its execution date and `docs/implementation-plans/2-seed-source-references-fallback.md`; do not delete the entry or leave it presented as next work.

- **Do not change implementation surfaces.** No call site, seed producer, test, archived seed, routing rule, or model-call order changes in this step. A separate status note in one document is not enough because the contract, arc, and backlog serve different readers.

## Tests

No new automated tests belong to this non-code step.

### Verification (non-code step)

1. `verify_step_1_source_preflight` — confirm the green results for `tests/test_create.py`, `tests/cli/test_authoring_cmds.py`, `tests/test_annotate_render.py`, and `tests/test_scope_out.py` establish validator-clean checked-in, annotate, and scope-out sources.

2. `verify_step_2_roadmap_admission` — confirm the green results for `tests/test_roadmap_gates.py`, `tests/test_roadmap.py`, and `tests/test_roadmap_seed_manifest.py` establish body References admission across roadmap materialization, hand acceptance, and classification.

3. `verify_step_3_rebaseline_fallback` — confirm `tests/test_reground.py` proves `render_rebaseline_seed` emits source-plan References accepted by the create preflight.

4. `verify_documentation_handoff` — check the three edited files for no active wording such as “Land #351,” “#351 is next,” or a not-started #351 status, while retaining #351 as a closed record and #327 as the active handoff.

5. `verify_plan_test_command` — run `uv run pytest tests/ -q -n auto` after the upstream changes and documentation update.

## Acceptance criteria

- `docs/reference/contracts/seed-ingestion.md:## Generated-source compatibility` records current, create-preflight-compatible References behavior for all five maintained producer groups.

- `docs/reference/contracts/seed-ingestion.md:## Follow-up sequence` marks #351 complete and names #327 as the remaining ingestion-route owner.

- `docs/implementation-plans/backlog-arcs/backlog-arc-seed-ingestion.md:## Ordered route` and `## Exit and handoff` preserve #351 as a completed prerequisite and direct new work to #327.

- `BACKLOG.md:### Now / Next / Blocked / Parked (working set)` no longer lists #351 as active work, and the #331 and #333 status notes contain no future-tense #351 handoff.

- The `BACKLOG.md` #351 entry is closed with an execution record that points to `docs/implementation-plans/2-seed-source-references-fallback.md`.

- Step 4’s authored content changes only `docs/reference/contracts/seed-ingestion.md`, `docs/implementation-plans/backlog-arcs/backlog-arc-seed-ingestion.md`, and `BACKLOG.md`; the standard runner may also record the plan’s completion status in its own metadata update.

## References

- [CommonMark Spec — ATX headingshttps: — Check the visible `## References` contract that the repaired sources satisfy.

## Applicable guardrails

- **The plan’s “## Plan intent”** — record only compatibility evidence that lets maintained `--from-existing` sources reach their existing authoring route.

- **The plan’s “## Step intent”** — keep the change limited to the contract, arc, and work queue, with #327 as the next scoped handoff.

- **The plan’s “## Out of scope”** — do not turn this documentation step into a routing, schema, seed-archive, or model-call-order change.

## Deferred

- `74b73f49705a852b50f557668e68847846dfbb86c7128a8a3a3e8a8c026fd252` — Source-routing and model-call-order changes remain owned by BACKLOG #327; this step records that handoff without changing those rules.
