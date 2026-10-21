> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 3 — Refuse an ungrounded roadmap product before publication and retain its retry checkpoint

## Summary

Add a pre-publication refusal in `plan_tool/create.py` for a selected roadmap product whose valid source verdict is empty and whose row has no nonblank description. A local or unmarked target reaches this check without an outbound query; step 2 refuses it earlier if that required description is absent. Keep the decision binary: a decoded source or recorded description permits publication; neither does not. Preserve the proposal and research checkpoints when refusing, so a corrected retry can reuse unchanged step work. On green, a fully description-backed zero-source result publishes with a fixed disclosure, and roadmap-selected `--iterate` preserves that accepted References block.

## Table of Contents

- [Summary](#summary) — Scope and expected green result.
- [Table of Contents](#table-of-contents) — Quick links to this detail.
- [Why](#why) — Why an empty selected verdict must stop publication.
- [Input](#input) — Upstream evidence and create lifecycle boundaries.
- [Files (creates vs edits)](#files-creates-vs-edits) — Files changed by the step.
- [Implementation](#implementation) — Refusal, disclosure, checkpoint, and iteration rules.
- [Tests](#tests) — Focused regression coverage.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Relevant external contracts.
- [Applicable guardrails](#applicable-guardrails) — Scope limits that bind this step.
- [Deferred](#deferred) — Work deliberately left outside this refusal.

## Why

`plan_tool/create.py:propose_references_from_claude` currently allows an empty References result to continue, and `plan_tool/create.py:_prepare_create_plan` can then render seed References or `_(TODO)_`. After step 2 has selected an actual roadmap product and recorded an explicit empty verdict, that behavior would publish guidance that appears researched without either source evidence or an operator fallback. The preparation/publication split at `plan_tool/create.py:_prepare_create_plan` and `plan_tool/create.py:_publish_create_plan` provides the required refusal boundary without losing the completed proposal.

## Input

- **Step 1 outcome:** consume the optional operator description and disclosure decision preserved beside each hosting or store product. Treat nonblank presence as the local fallback; do not judge its wording.

- **Step 2 outcome:** consume its immutable selected-target snapshot and one validated source verdict per target. Product text, field origin, description, and disclosure decision remain associated with their own target throughout this step; local no-source verdicts never came from an external request.

- **Preparation boundary:** `plan_tool/create.py:_prepare_create_plan` completes research before `plan_tool/create.py:_publish_create_plan` handles collision archival, plan writing, and manifest updates.

- **Checkpoint boundary:** `plan_tool/create.py:propose_steps_from_claude`, `plan_tool/create.py:propose_references_from_claude`, and `plan_tool/create.py:_references_input_hash` own resumable work. `plan_tool/create.py:_finalize_create_plan` clears checkpoints only after a successful published create.

- **Iteration boundary:** `plan_tool/create.py:_converge_create_plan` currently refreshes References through `plan_tool/create.py:propose_references_from_claude` and `plan_tool/create.py:_patch_plan_body_section`.

## Files (creates vs edits)

- **New files:** None.

- **Existing files (edits only):**
  - `plan_tool/create.py` — Refuse ungrounded selected targets before publication, choose the selected zero-source References state, retain retry state, and carry accepted selected state into convergence.
  - `tests/test_create.py` — Cover refusal, fallback, disclosure, retry, non-interactive, and iteration behavior.
  - `tests/cli/test_authoring_cmds.py` — Cover the existing branch-collision rollback path when the new refusal reaches `plan_tool/cli/authoring.py:cmd_create`.

## Implementation

- **Foundational logic:** reject a selected roadmap target when its valid source verdict is empty and its own description is absent or whitespace-only.

- **Evaluate only validated target verdicts:** run the refusal after step 2 has established its complete selected result. Do not turn malformed, missing, duplicate, foreign, or invalid-reference responses into empty verdicts; those remain step 2 protocol failures. A local no-source verdict is valid only after step 2 has already required the row's nonblank description.

- **Keep the rule binary:** permit a target when it has at least one decoded `plan_tool/create.py:Reference` or a nonblank description. Do not add relevance, freshness, authority, format, or quality scoring.

- **Fail before publication:** raise `CreateError` in `plan_tool/create.py:_prepare_create_plan` before returning `PreparedCreatePlan` to `plan_tool/create.py:_publish_create_plan`. The error must name the product and its field origin, and tell the operator to add a description or repair source evidence.

- **Do not add a bypass:** refusal must not prompt, branch on TTY state, downgrade to a warning, or fall back to seed prose. Non-interactive callers receive the same error.

- **Publish an explicit zero-source state:** when every selected result is source-free—an external verdict is explicitly empty or a local result is derived—and every target passes through its description, render this exact `## References` body: `No external references were returned for the selected roadmap products; publication proceeds under their recorded operator descriptions.` Treat it as complete References content, not a `Reference` row, seed fallback, or placeholder.

- **Keep mixed results honest:** when at least one selected verdict has decoded sources, render the flattened decoded References followed by one disclosure line naming any description-backed target(s) still in the selection. Do not retain seed References, and never invent a `Reference` row — a URL or title standing in for a target that has none — for a description-backed target; naming it in the disclosure line is not inventing a citation, since it discloses the real recorded description rather than presenting it as a decoded source.

- **Retain the retry checkpoint:** let a refusal escape before `plan_tool/create.py:_finalize_create_plan` clears successful checkpoints. Step 2’s selected snapshot must remain part of `plan_tool/create.py:_references_input_hash`, so a description-only correction refreshes source research while unchanged initial-step work resumes.

- **Carry accepted selection into convergence:** extend the prepared and convergence handoff at `plan_tool/create.py:PreparedCreatePlan` and `plan_tool/create.py:_CreatePlanConvergence` enough to identify a roadmap-selected result that passed pre-publication checks.

- **Freeze selected References during iteration:** for that selected path, `plan_tool/create.py:_converge_create_plan` may re-propose steps but must skip its later References call and `plan_tool/create.py:_patch_plan_body_section` update. Unselected creates retain the current refresh behavior covered by `tests/test_create.py:TestCreatePlanReferencesIteration`.

- **Preserve CLI cleanup:** `plan_tool/cli/authoring.py:cmd_create` must continue routing this `CreateError` through `_rollback_branch_collision` when applicable. That cleanup restores the invocation branch and clears its temporary binding, but must not archive the source or discard checkpoints.

## Tests

### Tests for this step

- `test_roadmap_target_without_sources_or_description_refuses_before_publication` — An explicit empty verdict without a nonblank description raises `CreateError` naming the product and field origin.

- `test_roadmap_target_description_allows_empty_verdict_without_quality_check` — A plainly unhelpful but nonblank description permits publication, proving presence rather than quality is the rule, including a local target that never queried research.

- `test_roadmap_refusal_checks_each_target_independently` — Evidence or a description for one target does not clear another target’s empty verdict.

- `test_all_description_backed_empty_verdicts_render_fixed_no_source_disclosure` — The fully empty selected result publishes the fixed disclosure rather than seed References or `_(TODO)_`, including on the non-iterating path.

- `test_all_local_description_backed_targets_render_disclosure_without_research` — A fully local selected result publishes the fixed disclosure without a generic or external research call.

- `test_mixed_selected_verdicts_render_decoded_references_and_description_disclosure` — A source-backed target and a description-backed empty target publish the decoded source entries plus a disclosure line naming the description-backed product, never a fabricated `Reference` row for it.

- `test_roadmap_refusal_leaves_publication_and_source_archive_unreached` — Refusal leaves plan, manifest, collision archive, and source archive unchanged.

- `test_roadmap_refusal_keeps_checkpoints_and_description_retry_reuses_steps` — A failed attempt preserves checkpoints; changing selected description data refreshes research without re-proposing unchanged steps.

- `test_roadmap_refusal_never_prompts_on_noninteractive_stdin` — Non-interactive stdin receives the same hard refusal without an input call.

- `test_roadmap_iteration_preserves_accepted_references_without_reresearch` — A selected `--iterate` run keeps its initial References body, including the zero-source disclosure, and makes no later References call.

- `TestCreateBranchCollisionMain.test_main_create_authoring_failure_rolls_back_binding` — Extend the existing CLI failure control case to cover the refusal path’s branch restoration and binding cleanup without source archival.

**Green-before-done:** every listed test and the existing References checkpoint and iteration coverage in `tests/test_create.py` are green before this step is complete.

## Acceptance criteria

- A selected target with an empty verdict and no nonblank description raises `CreateError` before `plan_tool/create.py:_publish_create_plan`.

- The refusal names the product and field origin and never requires interactive input.

- A decoded source or nonblank description clears only its matching target; description quality is not evaluated.

- A fully description-backed selected zero-source result publishes with the fixed disclosure, never seed References or `_(TODO)_`.

- A mixed selected result publishes decoded References plus one disclosure line naming any description-backed products still in the selection, never a fabricated Reference row for them.

- Refusal leaves plan, manifest, collision archive, source archive, and accepted References bytes unchanged.

- A corrected selected description invalidates reference reuse while unchanged initial-step work resumes from its checkpoint.

- Roadmap-selected `--iterate` neither re-researches nor replaces accepted References; unselected iteration retains its existing refresh behavior.

- `uv run pytest tests/test_create.py -q` and the affected cases in `tests/cli/test_authoring_cmds.py` pass.

## References

- [Claude Code CLI referencehttps: — Review non-interactive subprocess behavior and failure handling.

- [json — JSON encoder and decoderhttps: — Review structured-response decoding boundaries.

- [io — Core tools for working with streamshttps: — Review terminal detection for the non-interactive refusal case.

- [How to monkeypatch/mock modules and environmentshttps: — Review hermetic invoker, stdin, and checkpoint tests.

## Applicable guardrails

- **The plan’s “## Plan intent,” grounded research:** apply the refusal only to selected roadmap technology records, so published research makes no unsupported grounding claim.

- **The plan’s “## Step intent,” preserved proposal:** reject missing grounding without discarding completed proposal work needed for a corrected retry.

- **The plan’s “## Out of scope,” roadmap contract:** consume the upstream description and selected verdicts without changing roadmap vocabularies, blocks, or gates.

- **The plan’s “## Out of scope,” research boundary:** do not extend this behavior to other research subjects or later execution commands.

- **The plan’s “## Out of scope,” offline operation:** do not add an offline fallback or bypass for unavailable source evidence.

## Deferred

- `7f957293972de2d3834443890f509fe3f08b6a184c3402a69940a78522fa7beb` — The plan’s `## Stop/defer` source-quality questions remain outside this binary presence check.
