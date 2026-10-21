> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 3 — Refuse an ungrounded roadmap product before publication and retain its retry checkpoint

## Summary

Add a pre-publication gate in `plan_tool/create.py` that evaluates the per-product verdicts produced by step 2. A selected roadmap product passes only when its own verdict contains a decoded source or its own description is nonblank. Keep the failure as a non-interactive `CreateError` before publication, so cached proposal work survives for a corrected retry. On green, roadmap-selected iteration keeps the accepted References block instead of performing a later research pass.

## Table of Contents

- [Summary](#summary) — Scope and expected green result.
- [Table of Contents](#table-of-contents) — Quick links to this detail.
- [Why](#why) — Why valid empty evidence must stop publication.
- [Input](#input) — Step-2 verdicts and existing create lifecycle boundaries.
- [Files (creates vs edits)](#files-creates-vs-edits) — Files changed by the step.
- [Implementation](#implementation) — Refusal, checkpoint, and iteration rules.
- [Tests](#tests) — Focused regression coverage.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Relevant external contracts.
- [Applicable guardrails](#applicable-guardrails) — Scope limits that bind this step.
- [Deferred](#deferred) — Work deliberately left outside this refusal.

## Why

Step 2 makes a per-row empty source list an explicit, valid verdict, but `plan_tool/create.py:propose_references_from_claude` currently treats an empty References result as non-blocking and `plan_tool/create.py:_prepare_create_plan` continues toward publication. That would let a selected roadmap product appear to have researched guidance when neither a source nor an operator explanation supports it. The create flow already separates preparation from `plan_tool/create.py:_publish_create_plan`; use that boundary to reject the missing-grounding case without losing the completed proposal work.

## Input

- **Step 2 selected research state:** consume step 2’s immutable target snapshot and one validated source verdict per target. Each target retains its product text, field origin, and optional step-1 description; protocol failures — including an invalid member in a non-empty source list — remain step 2 failures, not missing-source verdicts.

- **Pre-publication lifecycle:** `plan_tool/create.py:_prepare_create_plan` finishes plan assembly and research before `plan_tool/create.py:_publish_create_plan` archives collisions, writes the plan, and updates the manifest.

- **Checkpoint lifecycle:** `plan_tool/create.py:propose_steps_from_claude`, `plan_tool/create.py:propose_references_from_claude`, and `plan_tool/create.py:_references_input_hash` own resumable proposal state. `plan_tool/create.py:_finalize_create_plan` discards those checkpoints only after a published create reaches a normal terminal outcome.

- **Post-publication iteration:** `plan_tool/create.py:_converge_create_plan` currently re-proposes both steps and References, then uses `plan_tool/create.py:_patch_plan_body_section` to replace a nonempty References block.

- **CLI failure boundary:** `plan_tool/cli/authoring.py:cmd_create` catches `CreateError` before its source-archive work. If its branch-collision gate created a temporary binding and switched branches, it then calls `_rollback_branch_collision`: that existing outer cleanup clears the binding and restores the invocation branch but leaves the candidate branch in place. This step must preserve and test that cleanup without allowing it to archive a source or discard checkpoints.

## Files (creates vs edits)

- **New files:** None.

- **Existing files (edits only):**
  - `plan_tool/create.py` — Evaluate selected product verdicts before publication, preserve failed-attempt checkpoints, and prevent roadmap-selected iteration from re-researching accepted References.
  - `tests/test_create.py` — Cover the refusal, recovery, no-write boundary, non-interactive behavior, and iteration carve-out.
  - `tests/cli/test_authoring_cmds.py` — Cover refusal after branch-collision disambiguation restores only the binding and invocation branch while preserving retry checkpoints.

## Implementation

- **Foundational logic:** reject a selected roadmap target when its own source verdict is empty and its own operator description is absent or whitespace-only.

- **Evaluate only step-2-valid verdicts:** inspect the selected snapshot after `plan_tool/create.py:propose_references_from_claude` returns its validated roadmap result. Do not reinterpret an unparseable, missing, duplicate, foreign, or invalid-reference-member target response as missing evidence; step 2 must keep reporting that as a research-protocol failure.

- **Keep the gate binary:** accept a target when it has at least one decoded `plan_tool/create.py:Reference`, or when its description has nonblank text after the presence check. Do not score source relevance, source freshness, description usefulness, or description quality. Preserve the stored description text; trimming decides only whether the fallback exists.

- **Fail before any publication effect:** run the gate in `plan_tool/create.py:_prepare_create_plan` after the initial proposal and selected research finish, but before it returns `PreparedCreatePlan` to `plan_tool/create.py:_publish_create_plan`. A failure must leave collision archives, plan and manifest writes, plan-detail renames, source archival, and References body changes unreached. A branch-collision rollback outside this boundary may restore the original branch and remove its temporary binding; it must not change those artifacts or the retained checkpoints.

- **Make the error actionable and deterministic:** raise `CreateError` that names the product and its exact field origin, and directs the operator to add a description or repair the source evidence. Do not add an input prompt, TTY branch, warning-only path, or generic fallback to seed prose.

- **Retain the useful retry state:** let the successful initial-step and research calls keep their checkpoints when the gate raises. Step 2’s selected-snapshot contribution to `plan_tool/create.py:_references_input_hash` must make a changed description re-run research, while the unchanged initial-step input continues to resume from its checkpoint.

- **Carry selection state to iteration:** retain enough roadmap-selection state through `plan_tool/create.py:PreparedCreatePlan` and `plan_tool/create.py:_CreatePlanConvergence` for `plan_tool/create.py:_converge_create_plan` to identify an already accepted roadmap result.

- **Freeze accepted References during roadmap iteration:** on that selected path, continue normal step re-proposal but skip the later `propose_references_from_claude` call and its `plan_tool/create.py:_patch_plan_body_section` update. The round-zero References block remains unchanged. Unselected create origins retain the current re-research and patch behavior.

## Tests

### Tests for this step

- `tests/test_create.py:test_roadmap_product_without_sources_or_description_refuses_before_publication` — An explicit empty verdict with no usable description raises `CreateError` naming the product and field origin.

- `tests/test_create.py:test_roadmap_product_description_allows_empty_source_verdict_without_quality_check` — A nonblank, plainly unhelpful description permits publication, proving the gate checks presence rather than quality.

- `tests/test_create.py:test_roadmap_refusal_checks_each_target_independently` — A source or description for one repeated or sibling target does not clear another target’s empty verdict.

- `tests/test_create.py:test_roadmap_protocol_failure_is_not_reported_as_an_ungrounded_product` — A step-2 protocol failure, including an invalid source-list member, keeps its protocol error and does not receive description-fallback advice.

- `tests/test_create.py:test_roadmap_refusal_leaves_publication_and_source_archival_unreached` — Refusal creates no plan or manifest entry and does not archive a collision or source seed.

- `tests/test_create.py:test_roadmap_refusal_keeps_checkpoints_and_description_retry_reuses_steps` — A failed attempt retains the initial proposal checkpoint; changing only the selected description re-runs research without re-proposing unchanged steps.

- `tests/cli/test_authoring_cmds.py:test_roadmap_refusal_after_branch_collision_restores_binding_without_losing_checkpoints` — A refusal after disambiguating branch setup restores the invocation branch and clears only the temporary binding; the candidate remains undeleted and the retry checkpoints remain available.

- `tests/test_create.py:test_roadmap_refusal_never_prompts_on_noninteractive_stdin` — Non-interactive stdin receives the same hard failure without an input call.

- `tests/test_create.py:test_roadmap_iteration_keeps_accepted_references_without_reresearch` — A selected `--iterate` create preserves its initial References body and makes no later References call.

- `tests/test_create.py:TestCreatePlanReferencesIteration.test_iteration_loop_updates_references_section` — Keep the existing generic iteration behavior as the control case for non-roadmap creates.

**Green-before-done:** every listed test and the existing References parsing, checkpoint, and iteration tests in `tests/test_create.py` are green before this step is complete.

## Acceptance criteria

- Every selected target with an empty verdict and no nonblank description raises `CreateError` before `plan_tool/create.py:_publish_create_plan`.

- The refusal message identifies the product and its field origin, with a correction path that does not require an interactive response.

- A source or nonblank description clears only its matching target; a description’s content is not judged.

- A refusal leaves no plan, manifest update, collision archive, source archive, or References body mutation.

- If branch-collision disambiguation preceded the refusal, its existing rollback clears only the temporary binding and restores the invocation branch; it neither deletes the candidate branch nor loses the proposal/research checkpoints.

- A failed attempt retains its proposal checkpoint; changing selected description data invalidates research reuse while preserving unchanged step-proposal reuse.

- Roadmap-selected `--iterate` does not invoke later References research or replace the accepted References block.

- Non-roadmap creates retain the current iteration References refresh behavior.

- `uv run pytest tests/test_create.py -q` passes.

## References

- [Claude Code CLI reference](https://code.claude.com/docs/en/cli-usage) — Review non-interactive execution and failure behavior for the research subprocess.

- [Claude Code Tools reference](https://code.claude.com/docs/en/tools-reference) — Review the web-search surface that produces source evidence.

- [json — JSON encoder and decoder](https://docs.python.org/3.13/library/json.html) — Review structured-response decoding and failure handling.

- [io — Core tools for working with streams](https://docs.python.org/3.13/library/io.html#io.IOBase.isatty) — Review terminal detection semantics for the non-interactive refusal test.

- [How to monkeypatch/mock modules and environments](https://docs.pytest.org/en/stable/how-to/monkeypatch.html) — Review hermetic stubbing of the invoker, stdin state, and checkpoint paths.

## Applicable guardrails

- **The plan’s “## Plan intent,” grounded research:** apply the refusal only to technology records selected from the roadmap, so published research does not claim more grounding than exists.

- **The plan’s “## Step intent,” preserved proposal:** reject missing grounding without discarding the already-proposed plan or forcing a new proposal after a description-only correction.

- **The plan’s “## Out of scope,” roadmap contract:** consume step 1’s description and step 2’s selected targets without changing roadmap schema, vocabularies, or gates.

- **The plan’s “## Out of scope,” research boundary:** do not extend this refusal to unselected research domains or later execution commands.

- **The plan’s “## Out of scope,” offline operation:** do not add an offline fallback or a bypass for unavailable source evidence.

## Deferred

- Source relevance, authority, currency, and completeness scoring — the plan’s `## Stop/defer` keeps these judgments outside the binary refusal.

- Re-research and staleness policy after a successful publication — this step only protects the initial selected result and its retry path.
