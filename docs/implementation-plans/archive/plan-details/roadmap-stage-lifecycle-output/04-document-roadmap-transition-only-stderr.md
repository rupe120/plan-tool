> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 4 — Document roadmap’s transition-only stderr status without changing shared heartbeat reporting

## Summary

This step updates `README.md`, `RUNBOOK.md`, and `docs/ARCHITECTURE.md` to describe roadmap’s confirmed lifecycle status on stderr. It documents the normal stage-run boundary and the transition types operators can observe after step 3 lands. The key decision is that roadmap owns these direct lines; `plan_tool/progress.py` remains the separate shared heartbeat reporter. On green, readers know that a quiet roadmap call has no liveness guarantee and that stdout remains unchanged.

## Table of Contents

- [Summary](#summary) — The completed documentation result.
- [Table of Contents](#table-of-contents) — Links to each section.
- [Why](#why) — The documentation gap this step closes.
- [Input](#input) — The landed status and reporter contracts this step reads.
- [Files (creates vs edits)](#files-creates-vs-edits) — Documentation files updated by this step.
- [Implementation](#implementation) — The wording, ownership, and boundary rules.
- [Tests](#tests) — Upstream lifecycle coverage and non-code verification.
- [Acceptance criteria](#acceptance-criteria) — Observable documentation outcomes.
- [References](#references) — Plan and implementation sources.
- [Applicable guardrails](#applicable-guardrails) — Scope limits that bind the documentation.
- [Deferred](#deferred) — Status work that remains outside this step.

## Why

`README.md` and `RUNBOOK.md` describe heartbeat-based progress for several commands, while `docs/ARCHITECTURE.md` assigns that behavior to `plan_tool/progress.py`. Step 3 adds a different roadmap-only stderr surface, so the public guides must explain its bounded transition facts without implying that roadmap has a heartbeat or that silence proves the backend remains healthy.

## Input

- **Step 3 status contract:** Read the landed behavior from `plan_tool/roadmap.py:run_roadmap`, `plan_tool/roadmap.py:_run_roadmap`, and `plan_tool/cli/roadmap_cmd.py:cmd_roadmap`. Step 3’s implementation and tests define the final wording and ordering; landed code wins over this detail if they differ.

- **Shared reporter contract:** Read `plan_tool/progress.py:ProgressReporter`, `plan_tool/progress.py:StderrReporter`, and `plan_tool/progress.py:NullReporter` to preserve their heartbeat-only documentation boundary.

- **Existing documentation homes:** Keep roadmap guidance in `README.md:### 0. roadmap`, `RUNBOOK.md:## Workflow: turn a concept brief into architecture artifacts (roadmap)`, and `docs/ARCHITECTURE.md:## Roadmap`. Keep shared heartbeat guidance in `README.md:## Console progress reporting`, `RUNBOOK.md:## Progress output during long claude calls`, and `docs/ARCHITECTURE.md:## Progress reporting`.

## Files (creates vs edits)

- **New files:** None.

- **Existing files (edits only):**
  - `README.md` — Document roadmap’s normal stage-run transition status near `### 0. roadmap`; keep `## Console progress reporting` scoped to the shared heartbeat reporter.
  - `RUNBOOK.md` — Add operator-facing lifecycle guidance to `## Workflow: turn a concept brief into architecture artifacts (roadmap)` and distinguish it from `## Progress output during long claude calls`.
  - `docs/ARCHITECTURE.md` — Describe the direct roadmap status ownership beside `## Roadmap` while preserving `## Progress reporting` as the `plan_tool/progress.py` heartbeat contract.

## Implementation

- **Foundational logic:** keep documentation ownership split between roadmap’s confirmed transition lines and the shared reporter’s heartbeat lines.

- **Describe confirmed transitions, not activity.** In `README.md:### 0. roadmap` and `RUNBOOK.md:## Workflow: turn a concept brief into architecture artifacts (roadmap)`, state that a normal stage run writes bounded status to stderr after confirmed selection, stage, retry or stop, write, and returned-result transitions. Make clear that these lines show the last confirmed transition, not backend liveness.

- **Keep the command boundary narrow.** Document that `plan_tool/cli/roadmap_cmd.py:cmd_roadmap` supplies the direct stderr presentation only for its ordinary call to `plan_tool/roadmap.py:run_roadmap`, including an active-feedback re-entry selected within that normal stage run. State that views, seed operations, the separate `--revise-feedback` command, structural operations, and other non-stage routes do not gain this status surface.

- **Preserve stdout’s contract.** Explain that lifecycle lines go only to stderr and do not change roadmap summaries or result payloads on stdout. Do not add examples that require consumers to parse lifecycle text.

- **Keep heartbeat reporting separate.** Retain `README.md:## Console progress reporting`, `RUNBOOK.md:## Progress output during long claude calls`, and `docs/ARCHITECTURE.md:## Progress reporting` as documentation for `plan_tool/progress.py:ProgressReporter`. Name roadmap as a separate transition-only surface where needed, but do not add it to the shared reporter’s command list or heartbeat examples.

- **Use architecture-level ownership.** In `docs/ARCHITECTURE.md:## Roadmap`, connect the status facts to `plan_tool/roadmap.py:_run_roadmap` and the direct command sink in `plan_tool/cli/roadmap_cmd.py:cmd_roadmap`. Keep `plan_tool/style.py:note` presentation-only; roadmap remains responsible for deciding when a transition exists.

- **Keep unsafe and speculative content out.** Documentation must not promise timing, periodic output, a status file, backend health, prompt or reply content, exception details, altered retries, altered run logs, or changed exit behavior.

## Tests

- `test_returned_outcomes_emit_one_terminal_after_existing_summaries` — `tests/cli/test_roadmap_cmd.py` proves the documented returned-result boundary across roadmap outcomes.

- `test_stage_status_does_not_change_existing_stdout` — `tests/cli/test_roadmap_cmd.py` proves lifecycle facts stay off stdout.

- `test_view_route_emits_no_stage_lifecycle_status` — `tests/cli/test_roadmap_cmd.py` proves the documentation’s non-stage-route exclusion.

- `test_terminal_status_sink_exception_is_fail_open` — `tests/test_roadmap.py` proves one failed stderr delivery does not alter roadmap execution.

### Verification (non-code step)

1. Run `uv run pytest tests/test_roadmap.py tests/cli/test_roadmap_cmd.py -q` after step 3 lands.

2. Compare the updated prose with `plan_tool/roadmap.py:run_roadmap`, `plan_tool/roadmap.py:_run_roadmap`, and `plan_tool/cli/roadmap_cmd.py:cmd_roadmap`; confirm it names only confirmed lifecycle transitions.

3. Review the roadmap and shared-progress sections together; confirm roadmap is never described as a `ProgressReporter` consumer or a heartbeat source.

4. Confirm each updated document states that roadmap status uses stderr and leaves stdout unchanged.

## Acceptance criteria

- `README.md:### 0. roadmap` tells operators that normal roadmap stage runs emit confirmed transition status on stderr and that silence does not prove a backend call is healthy.

- `RUNBOOK.md:## Workflow: turn a concept brief into architecture artifacts (roadmap)` states the normal stage-run scope, observed transition categories, stderr-only destination, and non-stage-route exclusion.

- `README.md:## Console progress reporting`, `RUNBOOK.md:## Progress output during long claude calls`, and `docs/ARCHITECTURE.md:## Progress reporting` retain `plan_tool/progress.py` as the shared heartbeat owner without adding roadmap to that contract.

- `docs/ARCHITECTURE.md:## Roadmap` assigns direct lifecycle ownership to `plan_tool/roadmap.py:_run_roadmap` and `plan_tool/cli/roadmap_cmd.py:cmd_roadmap`.

- The documentation does not claim a heartbeat, timing guarantee, liveness signal, durable status record, model-content output, changed stdout, or changed execution behavior.

- `uv run pytest tests/test_roadmap.py tests/cli/test_roadmap_cmd.py -q` passes.

## References

- [Roadmap lifecycle plan — Read the status order and scope fence.

- [plan_tool/roadmap.py — Read `run_roadmap`, `_run_roadmap`, `RoadmapStage`, and `RoadmapResult`.

- [plan_tool/cli/roadmap_cmd.py — Read `cmd_roadmap`’s normal stage dispatch and result rendering.

- [docs/how-to/roadmap-demo.md](../../../how-to/roadmap-demo.md) — Read the motivating long-running stage-run scenario.

## Applicable guardrails

- **The plan’s `## Scope guardrails`, normal stage-run boundary:** Document status only for the ordinary roadmap stage-run path and identify other routes as excluded.

- **The plan’s `## Scope guardrails`, output boundary:** Describe stderr-only lifecycle facts without changing or reclassifying stdout.

- **The plan’s `## Scope guardrails`, transition-only boundary:** Keep roadmap outside the shared reporter and do not describe periodic or background reporting.

- **The plan’s `## Scope guardrails`, preserved execution contract:** Do not imply changes to retries, gates, publication, source admission, outcomes, exit handling, or run logs.

- **The plan’s `## Scope guardrails`, safe-content boundary:** Do not document backend-derived or failure-detail content as lifecycle status.

- **The plan’s `## Out of scope`, other-route exclusion:** Keep progress for other roadmap routes and commands out of these documentation changes.

## Deferred

- **Heartbeat or liveness reporting for quiet roadmap calls** — Requires separate lifecycle and interrupt design.

- **Shared reporter integration** — Requires a separate decision because it changes the cross-command `plan_tool/progress.py` contract.

- **Status for non-stage roadmap routes or other commands** — Requires separate evidence and backlog direction.
