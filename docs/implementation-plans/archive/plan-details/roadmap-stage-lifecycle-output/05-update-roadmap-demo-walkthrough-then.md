> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 5 — Update the roadmap demo and walkthrough, close the narrowed backlog entry, and advance the seed-ingestion queue

## Summary

Update `docs/how-to/roadmap-demo.md` and `docs/how-to/roadmap.md` so operators can interpret roadmap lifecycle lines as confirmed stderr transitions, not a liveness signal. Keep `plan_tool/run_log.py:run_log_path`’s JSONL record as the detailed diagnostic source. Close the uniquely identified lifecycle backlog item in `BACKLOG.md` and `docs/implementation-plans/backlog-arcs/backlog-arc-roadmap.md`, then advance the seed-ingestion arc to #333. On green, the demo, walkthrough, active queue, and both arcs describe the same delivered boundary.

## Table of Contents

- [Summary](#summary) — The completed documentation and backlog result.
- [Table of Contents](#table-of-contents) — Links to each section in this detail.
- [Why](#why) — The operator-facing gap this step closes.
- [Input](#input) — The landed lifecycle and run-log contracts this step reads.
- [Files (creates vs edits)](#files-creates-vs-edits) — The documentation and backlog records this step changes.
- [Implementation](#implementation) — The demo, walkthrough, and closure approach.
- [Tests](#tests) — Non-code verification for the delivered documentation.
- [Acceptance criteria](#acceptance-criteria) — Observable operator and queue outcomes.
- [References](#references) — The plan, runtime, and documentation sources.
- [Applicable guardrails](#applicable-guardrails) — Boundaries that constrain these edits.
- [Deferred](#deferred) — Work that remains outside this bounded status delivery.

## Why

`docs/how-to/roadmap-demo.md` currently calls its captured terminal transcript “full stdout,” although its command already combines stderr into the log, and `docs/how-to/roadmap.md` does not explain the new live status surface. Without the distinction, an operator can mistake a quiet backend call for a healthy one or diagnose an exhausted stage from the terse terminal line instead of the JSONL attempt record. Closing the narrowed queue item after documentation lands prevents the active backlog from advertising already-delivered work.

## Input

- **Step 1 backlog identity:** Use the unique lifecycle-entry identifier that step 1 lands, normally `#337`. Do not close `#323`, which step 1 preserves for the unrelated `--view walk` / `--view html` reconciliation entry.

- **Seed-ingestion handoff:** Step 1 makes #337 the active prerequisite in `docs/implementation-plans/backlog-arcs/backlog-arc-seed-ingestion.md`. Once this step closes #337, that arc must select #333 before #327 or the unimplemented portion of #331.

- **Step 3 lifecycle contract:** Read the landed behavior from `plan_tool/roadmap.py:run_roadmap`, `plan_tool/roadmap.py:_run_roadmap`, and `plan_tool/cli/roadmap_cmd.py:cmd_roadmap`. Step 3’s code and coverage define the final status wording and result ordering.

- **Durable diagnostic record:** Preserve `plan_tool/run_log.py:run_log_path`’s per-run JSONL location and the existing `attempt_failed`, `roadmap_stage_written`, and `run_end` records. Lifecycle lines help an operator follow the current transition; they do not replace that record.

- **Documentation homes:** Update `docs/how-to/roadmap-demo.md:## 4. Phase 1 — the four roadmap stages` and its later diagnostic guidance, plus `docs/how-to/roadmap.md:## 2. Generate the roadmap`. Keep step 4’s `README.md`, `RUNBOOK.md`, and `docs/ARCHITECTURE.md` ownership unchanged.

## Files (creates vs edits)

- **New files:** None.

- **Existing files (edits only):**
  - `docs/how-to/roadmap-demo.md` — Correct the stage-run capture guidance and retain JSONL-first diagnosis for exhausted or unclear attempts.
  - `docs/how-to/roadmap.md` — Explain normal stage-run lifecycle status beside `## 2. Generate the roadmap`.
  - `BACKLOG.md` — Remove the completed lifecycle work from active selection and retain a dated completion record under its unique entry.
  - `docs/implementation-plans/backlog-arcs/backlog-arc-roadmap.md` — Change the lifecycle route from immediate work to completed evidence without widening its scope.
  - `docs/implementation-plans/backlog-arcs/backlog-arc-seed-ingestion.md` — Replace #337's active-prerequisite wording with the selected #333 handoff.

## Implementation

- **Foundational logic:** keep live transition status, durable JSONL diagnostics, and backlog state consistent.

- **Correct the demo transcript description.** In `docs/how-to/roadmap-demo.md:## 4. Phase 1 — the four roadmap stages`, describe the existing `2>&1 | tee` capture as a combined terminal record. Make clear that lifecycle lines arrive on stderr while stdout remains the command’s existing output.

- **Teach the status boundary once.** Near the demo’s `**Capture for the demo:**` guidance, describe the lines supplied by step 3 as confirmed run and stage transitions. State that a quiet period after a transition does not prove the backend remains live. Do not add examples that imply periodic reporting or show backend-derived content.

- **Keep the diagnostic route intact.** In `docs/how-to/roadmap-demo.md`’s failure table and `**Two diagnostic notes this run proved out:**`, preserve the instruction to inspect `.plan-tool/runs/<slug>/*.jsonl` and `attempt_failed` before diagnosing an exhausted run. The recommended wording must distinguish the current terminal display from the detailed per-attempt record.

- **Add the same operator rule to the walkthrough.** In `docs/how-to/roadmap.md:## 2. Generate the roadmap`, describe lifecycle output only for normal roadmap stage runs. It must say that the lines report the last confirmed transition on stderr and point readers to the JSONL record for detailed diagnosis. Keep views, seed actions, and other non-stage routes outside this description.

- **Close only the lifecycle item.** In `BACKLOG.md`, use the identifier supplied by step 1 to remove the lifecycle item from `### Now / Next / Blocked / Parked (working set)` and mark its full entry completed with the delivered plan path. Sweep the execution-routing catalog and the entry’s references by identifier and by lifecycle-status vocabulary. Retain `#323` exclusively for the view-reconciliation work.

- **Make the roadmap arc a completed record.** In `docs/implementation-plans/backlog-arcs/backlog-arc-roadmap.md:## Real-world evidence source`, `## Ordered route`, `## Exit and handoff`, and `## Out of scope`, replace active lifecycle-routing language with a completed, bounded result. Keep the evidence source, direct stderr scope, and exclusions for liveness, streaming, cancellation, and broader observability intact.

- **Advance, do not broaden, the seed-ingestion queue.** In `docs/implementation-plans/backlog-arcs/backlog-arc-seed-ingestion.md:## Ordered route`, record #337 as complete and make #333 the selected next item. Preserve the existing order that holds #327 and #331 behind #333; do not turn this roadmap-status delivery into seed-ingestion implementation.

- **Do not widen the documentation sweep.** `README.md`, `RUNBOOK.md`, and `docs/ARCHITECTURE.md` already belong to step 4. Reuse their landed wording as the command-level reference rather than editing them again.

## Tests

No test file is added or modified because this is a non-code step.

### Verification (non-code step)

1. **Lifecycle regression coverage** — Run `uv run pytest tests/test_roadmap.py tests/cli/test_roadmap_cmd.py -q` to confirm the documentation matches step 3’s landed behavior.

2. **Demo capture check** — Verify that `docs/how-to/roadmap-demo.md:## 4. Phase 1 — the four roadmap stages` identifies stderr lifecycle lines as part of the existing combined `tee` transcript without saying stdout changes.

3. **Diagnostic-boundary check** — Verify that the demo and walkthrough both direct detailed attempt diagnosis to `.plan-tool/runs/<slug>/*.jsonl` and do not call live status a heartbeat or liveness proof.

4. **Backlog identity and handoff check** — Search `BACKLOG.md`, `docs/implementation-plans/backlog-arcs/backlog-arc-roadmap.md`, and `docs/implementation-plans/backlog-arcs/backlog-arc-seed-ingestion.md` for the step-1 lifecycle identifier and lifecycle vocabulary. Confirm the item is completed and absent from the active board, `#323` remains only the view-reconciliation entry, and the seed-ingestion arc selects #333 before #327 or #331.

5. **Documentation-link check** — Confirm all edited relative links resolve and `git diff --check` reports no whitespace errors.

## Acceptance criteria

- `docs/how-to/roadmap-demo.md` describes the existing stage-run capture as combined stdout and stderr output, with lifecycle lines identified as stderr output.

- `docs/how-to/roadmap-demo.md` and `docs/how-to/roadmap.md` state that lifecycle lines report only the last confirmed transition and do not prove a quiet backend call remains live.

- Both documents retain JSONL as the detailed diagnostic record and direct exhausted-stage diagnosis to `.plan-tool/runs/<slug>/*.jsonl`.

- `docs/how-to/roadmap.md:## 2. Generate the roadmap` limits lifecycle guidance to normal roadmap stage runs and does not extend the feature to views or seed actions.

- `BACKLOG.md` has no active-board row for the unique lifecycle entry, retains a dated completion record linked to `docs/implementation-plans/2-roadmap-stage-lifecycle-output.md`, and preserves `#323` for view reconciliation.

- `docs/implementation-plans/backlog-arcs/backlog-arc-roadmap.md` records the bounded lifecycle work as complete while preserving its stated exclusions.

- `docs/implementation-plans/backlog-arcs/backlog-arc-seed-ingestion.md` records #337 as complete and selects #333 without changing the later #327/#331 ordering.

- `uv run pytest tests/test_roadmap.py tests/cli/test_roadmap_cmd.py -q` passes.

## References

- [`docs/implementation-plans/2-roadmap-stage-lifecycle-output.md` — Read the lifecycle contract, documentation work, and scope fence.

- [`plan_tool/roadmap.py` — Read `run_roadmap`, `_run_roadmap`, `RoadmapResult`, and `OUTCOMES`.

- [`plan_tool/cli/roadmap_cmd.py` — Read `cmd_roadmap` and the existing result-rendering helpers.

- [`plan_tool/run_log.py` — Read `run_log_path`, `RunLogWriter`, and the roadmap attempt and completion event records.

- [`docs/how-to/roadmap-demo.md`](../../../how-to/roadmap-demo.md) — Read the stage-run capture and diagnostic sections.

- [`docs/implementation-plans/backlog-arcs/backlog-arc-roadmap.md` — Read the lifecycle route, exit, and retained exclusions.

## Applicable guardrails

- **The plan’s `## Scope guardrails`, normal stage-run boundary:** Document lifecycle output only for ordinary roadmap stage runs; do not imply coverage for views, seed actions, or other commands.

- **The plan’s `## Scope guardrails`, output boundary:** Describe stderr status without claiming that stdout changes.

- **The plan’s `## Scope guardrails`, transition-only boundary:** State the confirmed-transition limit and do not describe a heartbeat, timer, or liveness signal.

- **The plan’s `## Scope guardrails`, preserved execution contract:** Keep JSONL, retry behavior, stage gates, artifact publication, outcomes, and exit behavior as unchanged records.

- **The plan’s `## Scope guardrails`, safe-content boundary:** Do not document prompts, replies, exception details, or other backend content as lifecycle status.

- **The plan’s `## Out of scope`, other-route exclusion:** Leave status for other roadmap modes and commands to a separate evidence-backed backlog decision.

## Deferred

- **A heartbeat or liveness signal for quiet backend calls** — Requires separate lifecycle and interrupt design.

- **Status for non-stage roadmap routes or other commands** — Requires separate evidence and backlog direction.

- **Retaining unusable backend replies** — Remains the separate diagnostic-storage question in `BACKLOG.md` #217.
