> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 4 — Stage malformed iteration research before step or References writes and record its outcome, while keeping valid empty non-failing

## Summary

Update `plan_tool/create.py` so `_converge_create_plan` evaluates generic reference research after its existing deterministic applies but before it re-proposes or writes iteration steps and before it patches `## References`. A terminal unparseable result must use the existing iteration-stage failure result and record `propose_references` as an error, while a valid empty result remains a non-failing skipped result. Focused coverage in `tests/test_create.py` and `tests/cli/test_authoring_cmds.py` must prove the post-apply steps and References stay intact on failure and ordinary `create` still exits 0 for the resumable published plan.

## Table of Contents

- [Summary](#summary) — Reviewer overview of the iteration failure boundary.
- [Table of Contents](#table-of-contents) — Links to each section in this detail.
- [Why](#why) — The ambiguity and unsafe ordering this step removes.
- [Input](#input) — Upstream result and existing failure-path contracts.
- [Files (creates vs edits)](#files-creates-vs-edits) — Files changed by this step.
- [Implementation](#implementation) — Required ordering, outcome handling, and preserved behavior.
- [Tests](#tests) — Focused iteration, run-log, and CLI coverage.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Primary references for JSON semantics and test tooling.
- [Applicable guardrails](#applicable-guardrails) — Scope boundaries that bind this step.
- [Deferred](#deferred) — Adjacent work left outside this iteration boundary.

## Why

`plan_tool/create.py:_converge_create_plan` currently obtains iteration references after `plan_tool/create.py:propose_steps_from_claude`, then uses false-value handling that cannot tell malformed research from a valid empty result. That ordering allows a terminal malformed refresh to look like an intentional absence while the iteration continues to write re-proposed steps. The convergence loop's deterministic `apply_finding` phase remains an earlier, separate mutation boundary; after it, failed research must surface through the existing resumable stage-failure path before either new proposed content can alter the post-apply plan.

## Input

- **Step 2 result contract:** Step 2 supplies the typed generic-reference outcome that distinguishes populated, valid-empty, and terminal unparseable research. This step consumes that result without changing its retry, parser, or checkpoint rules.

- **Iteration writer boundary:** `plan_tool/create.py:_converge_create_plan` owns the re-proposal order, `plan_tool/parser.py:write_plan` writes re-proposed steps, and `plan_tool/create.py:_patch_plan_body_section` replaces the `References` body only for populated research.

- **Failure and observability boundary:** `plan_tool/create.py:CreateResult` carries a post-publication failure, while `plan_tool/run_log.py:RunLogWriter` records the iteration phase outcome.

- **CLI contract:** `plan_tool/cli/authoring.py:cmd_create` treats a populated `iteration_stage_failure` as `iteration_incomplete` with exit 0. `plan_tool/cli/direct_cmd.py:cmd_direct_jira` and `plan_tool/cli/direct_cmd.py:cmd_direct_run` already stop their chained workflows from that field.

## Files (creates vs edits)

- **New files:** None.

- **Existing files (edits only):**
  - `plan_tool/create.py` — stage generic iteration research before step re-proposal, classify all typed outcomes, record the research phase outcome, and route terminal malformed research through the existing iteration-stage failure path.
  - `tests/test_create.py` — cover terminal malformed iteration research, valid-empty preservation, populated-reference behavior when step re-proposal fails, and iteration run-log outcomes.
  - `tests/cli/test_authoring_cmds.py` — preserve the ordinary create CLI contract for a published plan carrying a malformed-reference iteration failure.

## Implementation

- **Foundational logic: iteration reference-result gate.** In `plan_tool/create.py:_converge_create_plan`, obtain and inspect Step 2’s generic research result before calling `plan_tool/create.py:propose_steps_from_claude` for that iteration and before any later `plan_tool/parser.py:write_plan` or `plan_tool/create.py:_patch_plan_body_section` work.

- **Fail terminal malformed research before proposed writes.** A terminal unparseable result must set the existing `stage_failure` path with an iteration-specific reference-research reason and return through `CreateResult.iteration_stage_failure`. The iteration must not invoke its step re-proposal or replace its References body after this outcome. The preservation baseline is the state after the existing `apply_finding` phase: earlier deterministic edits retain their behavior, while this boundary protects the iteration’s newly proposed steps and refreshed References content.

- **Correct the shared failure presentation.** Update the stage-failure banner and its nearby comments in `plan_tool/create.py:_converge_create_plan` so they name the failed stage rather than always naming step re-proposal, and so they state the established published-plan, exit-0 contract. The banner remains a visible incomplete-iteration signal; it must not claim a non-zero exit or a failed step proposal for terminal reference research.

- **Record the actual research outcome.** Wrap each generic iteration refresh in its own `propose_references` phase through `plan_tool/run_log.py:RunLogWriter`, carrying the iteration number. A populated result ends `ok`, a valid-empty result ends `skipped`, and a terminal unparseable result ends `error`; malformed research must never be recorded as `skipped`.

- **Keep valid empty non-failing.** A valid-empty result must permit normal step re-proposal and must not populate `CreateResult.iteration_stage_failure`. It must also keep the existing no-overwrite rule for `## References`, so an empty refresh does not replace the already-published section.

- **Retain independent populated-reference publication.** Keep the existing relationship between populated iteration research and `plan_tool/create.py:_patch_plan_body_section`: a populated result can update `## References` even when the later step re-proposal fails. Staging research first must not couple that valid patch to step-proposal success.

- **Reuse existing failure consumers.** Keep `plan_tool/create.py:_finalize_create_plan`, `plan_tool/cli/authoring.py:cmd_create`, and `plan_tool/cli/direct_cmd.py:cmd_direct_jira` / `plan_tool/cli/direct_cmd.py:cmd_direct_run` unchanged. The existing `iteration_stage_failure` field already preserves checkpoints, keeps ordinary `create` resumable at exit 0, and prevents direct pipelines from continuing.

- **Keep adjacent boundaries intact.** Step 2 retains retry, parse diagnostics, and checkpoint eligibility. Step 3 retains the initial-create failure boundary in `plan_tool/create.py:_prepare_create_plan`. Preserve `preserve_selected_roadmap_references` so selected roadmap research does not enter the generic refresh path.

## Tests

### Tests for this step

- `tests/test_create.py::TestCreatePlanIterationLoop::test_iteration_terminal_unparseable_references_stops_before_step_reproposal` — drive a valid initial create followed by terminal malformed iteration research; snapshot the state after any iteration `apply_finding` edits, then assert the iteration step proposal is not invoked, `iteration_stage_failure` identifies the failed iteration, the stage-failure banner names reference research and the established exit-0 contract, and the step frontmatter and `## References` body remain unchanged from that snapshot.

- `tests/test_create.py::TestCreatePlanIterationLoop::test_iteration_terminal_unparseable_references_records_error_phase` — assert the iteration’s `propose_references` phase has matching start and end events, carries the iteration number, and ends with `error` rather than `skipped`.

- `tests/test_create.py::TestCreatePlanReferencesIteration::test_iteration_loop_preserves_references_when_refs_empty` — update the valid-empty case to assert normal step re-proposal runs, no stage failure occurs, the reference phase ends `skipped`, and the existing References body remains unchanged.

- `tests/test_create.py::TestCreatePlanIterationLoop::test_iteration_references_patched_despite_step_failure` — retain coverage that populated iteration research reaches `## References` even when the later step proposal fails.

- `tests/cli/test_authoring_cmds.py::test_iteration_incomplete_still_runs_completed_create_tail` — use a malformed-reference iteration failure message and assert `cmd_create` returns 0 and registered-plan completion behavior remains intact. It continues to test the returned result contract; the real `_converge_create_plan` test owns banner wording.

Every listed test must be green before this step is complete.

## Acceptance criteria

- A terminal unparseable generic reference refresh enters the iteration-stage failure path after the iteration's existing `apply_finding` phase but before it invokes `propose_steps_from_claude`, `write_plan`, or `_patch_plan_body_section`; its presentation names the failed reference stage and retains the ordinary create exit-0 contract.

- A malformed iteration refresh records `propose_references` with outcome `error` and its iteration number.

- A malformed iteration refresh leaves the post-apply plan’s step frontmatter and `## References` body unchanged, without making a new proposal-side write.

- A valid-empty iteration refresh records `propose_references` with outcome `skipped`, runs normal step re-proposal, does not set `CreateResult.iteration_stage_failure`, and preserves the existing References body.

- A populated iteration refresh can still replace `## References` when the independent step re-proposal fails.

- `CreateResult.iteration_stage_failure` remains compatible with `plan_tool/cli/authoring.py:cmd_create`: the published plan completes the ordinary create tail and exits 0.

- `uv run pytest tests/test_create.py tests/cli/test_authoring_cmds.py -q` passes.

## References

- [json — JSON encoder and decoderhttps: — Review array parsing semantics behind the valid-empty versus malformed distinction.

- [pytest API Referencehttps: — Use fixtures, monkeypatching, temporary paths, and assertions for hermetic ordering and side-effect tests.

## Applicable guardrails

- **The plan’s “## Plan intent”, trustworthy and resumable create behavior.** Make the terminal malformed result visible through the existing failure and run-log surfaces rather than treating it as an empty result.

- **The plan’s “## Step intent”, preserve the post-apply plan.** Do not write re-proposed steps or replace References after terminal malformed iteration research; do not roll back the earlier deterministic `apply_finding` phase.

- **The plan’s “## Out of scope”, bounded generic research work.** Keep this change local to the generic iteration caller; do not extend roadmap research, recovery policy, CLI flags, or shared result infrastructure.

## Deferred

- **Initial-create malformed-research refusal** — Step 3 owns the pre-publication boundary in `plan_tool/create.py:_prepare_create_plan`.

- **Generic research retry and checkpoint policy** — Step 2 owns repair attempts, response diagnostics, and parseable-response persistence.

- **Shared retry or phase-result framework** — Keep the existing local create-flow seams because this step needs only the iteration boundary.
