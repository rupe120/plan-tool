> **Auto-archived**: this plan was swept on 2026-08-18 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 4 — Extract Phase B as the first post-loop split handler

## Summary

Extract Phase B from `plan_tool/detail.py:generate_detail` into a private same-file post-loop handler. The handler owns mixed-step split resolution, split-half re-authoring, result rebuilding, and recommend-only reporting; `tests/test_detail.py` pins its boundary and ordering. Keep the handler before the still-inline Trigger 2 path, with a narrow exclusion handoff for targets already split in the authoring loop. On green, `generate_detail` reads as lifecycle, Phase B, Trigger 2, then persistence, without changing split outcomes or result reporting.

## Table of Contents

- [Summary](#summary) — Reviewer overview of the extracted Phase B boundary.
- [Table of Contents](#table-of-contents) — Links to each section in this detail.
- [Why](#why) — Why Phase B needs its own owner before Trigger 2.
- [Input](#input) — Lifecycle handoff and split-bridge contracts this phase reads.
- [Files (creates vs edits)](#files-creates-vs-edits) — Files changed by this refactor.
- [Implementation](#implementation) — Required Phase B ownership, ordering, and behavior.
- [Tests](#tests) — Regression coverage for the handler and its ordering.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Primary references for explicit state transfer and tests.
- [Applicable guardrails](#applicable-guardrails) — Plan boundaries that constrain this extraction.
- [Deferred](#deferred) — Later post-loop and persistence work left outside this step.

## Why

`plan_tool/detail.py:generate_detail` currently keeps Phase B’s mixed-step policy inline beside the distinct Trigger 2 re-entry path. Both paths can split steps and rebuild results, but they start from different signals and have different follow-up rules. Giving Phase B one named owner makes the required ordering clear and stops a later cleanup from combining policies that must remain separate.

## Input

- **Step 3 handoff:** consume the authored `DetailResult` sequence, mixed-step findings, and the in-loop applied-split identifiers returned by step 3. Phase B reads the applied-split identifiers only to exclude stale mixed-step targets; it does not own or alter Trigger 2 state.

- **Split bridge:** preserve `plan_tool/launcher.py:escalate_to_split` and `plan_tool/launcher.py:EscalateResult` as the only path for proposing, applying, or recommending a mixed-step split.

- **Result and reporting helpers:** retain `plan_tool/detail.py:_detail_slug_key` for renumber-safe result attribution and `plan_tool/detail.py:_emit_split_recommendations` for the single post-handler recommendation surface.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `plan_tool/detail.py` — extract the inline Phase B block from `generate_detail` into one private same-file handler and call it before Trigger 2.
  - `tests/test_detail.py` — add handler-order and exclusion coverage, then retarget Phase B regressions to the extracted boundary.

## Implementation

- **Foundational logic:** resolve mixed-step findings after authoring before any in-loop structural-split re-entry runs.

- **Give Phase B one private owner.** Extract the block introduced by the `Phase B: refactor-then-feature split recommendation / apply` marker in `plan_tool/detail.py:generate_detail` into a private handler, such as `_handle_phase_b_splits`. Keep `generate_detail` as the coordinator: receive step 3’s lifecycle handoff, invoke Phase B, then continue to Trigger 2.

- **Use an explicit handoff.** Pass Phase B’s results, mixed-step findings, applied in-loop split identifiers, and dependencies needed for recursive authoring explicitly. Return the updated `list[DetailResult]` to `generate_detail`; do not rely on newly captured local state.

- **Keep the exclusion narrow.** Filter only mixed-step entries whose target id appears in the lifecycle’s applied in-loop split set. This prevents Phase B from acting on a newly created half, while leaving Trigger 2’s identifiers and recommend-only findings for step 5.

- **Preserve the split bridge seam.** Process mixed-step targets in descending id order and call `plan_tool/launcher.py:escalate_to_split` with the current `plan_path`, `repo_root`, invoker, `allow_split`, and prompt callback. Do not call split proposal or plan-mutation primitives directly from the handler.

- **Retain every bridge outcome.** Keep the current handling for `applied`, `recommended`, `unsafe`, `proposal-unusable`, and `step-missing` results. A recommendation remains deferred until the handler has completed applied-split recovery, and unsafe or unusable outcomes keep their current operator-visible messages.

- **Keep Phase B re-entry local to Phase B.** For an applied Phase B split, freshly parse the plan and select every current `Step.detail is None` target: the new split halves and any later detail-less step a targeted invocation had not reached. Re-author those targets by explicit id and prevent recursive split application. Preserve the current resume, callback, logging, budget, and commit behavior rather than introducing a new recovery path.

- **Preserve recursive persistence timing.** Each explicit-id re-entry follows the existing public `generate_detail` path and therefore performs its own final persistence after its own child lifecycle and post-loop handlers. Do not defer that nested save to the enclosing Phase B handler; preserve a nested persistence failure in its returned half result so the outer rebuild cannot report it as complete.

- **Preserve truthful rebuilt results.** Keep the current `plan_tool/detail.py:_detail_slug_key`-based distinction between files written in this invocation and downstream files carried through renumbering. Retain failed half results so a partial recovery cannot look successful.

- **Emit recommendations once.** Call `plan_tool/detail.py:_emit_split_recommendations` only after Phase B has finished re-authoring and rebuilding results. Do not reuse the in-loop reporting path.

- **Do not merge structural policies.** Keep Trigger 2’s `BLOCKED-STRUCTURAL` handoff, re-entry, and reporting outside this handler. A shared post-loop split handler would hide which signal owns a split and would break the plan’s required ordering.

## Tests

### Tests for this step

- `test_phase_b_handler_completes_before_trigger_2_reentry` — assert that, when both post-loop paths have work, Phase B finishes bridge resolution, recovery, and reporting before Trigger 2 begins.

- `test_phase_b_excludes_applied_in_loop_split_target` — assert that a mixed-step entry matching the in-loop applied-split identifier never reaches `plan_tool/launcher.py:escalate_to_split`.

- `TestInteractiveSplit.test_phase_b_delegates_to_escalate_to_split` — retarget the bridge spy to the extracted handler and assert it forwards the split controls unchanged.

- `TestInteractiveSplit.test_phase_b_no_inline_engine_calls` — retain the proof that Phase B uses only `plan_tool/launcher.py:escalate_to_split`.

- `TestInteractiveSplit.test_multiple_splits_renumber_and_rewire` — assert descending target handling preserves the final split order and dependency rewiring.

- `TestInteractiveSplit.test_carried_downstream_reported_as_skip_not_write` — assert result rebuilding does not mark renumbered prior-run detail files as newly written.

- `test_phase_b_reentry_targets_all_and_only_current_detail_less_steps` — run a targeted Phase B split with unrelated later unset steps and assert recovery re-authors every current `Step.detail is None` target while leaving existing details untouched.

- `test_phase_b_reentry_preserves_nested_persistence_result` — force persistence to fail in an explicit-id recovery call and assert Phase B retains the returned incomplete result rather than replacing it during rebuilding.

- `TestUnattendedSplitRecommendation.test_guard_enters_bridge_without_opt_in_or_tty` — assert recommend-only mixed-step handling still enters the bridge without mutating the plan.

- `TestUnattendedSplitRecommendation.test_no_mixed_steps_skips_bridge_and_emission` — assert an empty mixed-step handoff is a no-op.

Every listed test must be green before this step is complete.

## Acceptance criteria

- `plan_tool/detail.py:generate_detail` invokes one private Phase B handler after the step 3 lifecycle and before Trigger 2.

- The Phase B handler owns mixed-step bridge calls, half re-authoring, Phase B result rebuilding, and Phase B recommendation emission.

- A mixed-step target already split in the lifecycle is excluded from Phase B without changing Trigger 2’s state.

- A recommended split leaves plan structure unchanged and surfaces the existing `plan-tool split` guidance once.

- An applied Phase B split re-authors every current detail-less target, including new halves and later targets left unset by a targeted invocation, and returns results that distinguish fresh writes from carried-through files.

- Phase B preserves each recursive call's existing final-persistence timing and failure result while its outer handler still completes before Trigger 2 begins.

- `plan_tool/detail.py:generate_detail` retains its public signature and existing observable run-grade behavior.

- `tests/test_detail.py` passes without weakening existing assertions.

## References

- [Python 3.13 Execution Model](https://docs.python.org/3.13/reference/executionmodel.html) — Review local binding and explicit state transfer when extracting orchestration code.

- [Python dataclasses](https://docs.python.org/3.13/library/dataclasses.html) — Use a small private state carrier if the step 3 handoff needs one.

- [pytest Monkeypatching Guide](https://docs.pytest.org/en/stable/how-to/monkeypatch.html) — Use scoped spies to prove handler ordering and bridge delegation.

- [pytest Assertion and Exception Testing](https://docs.pytest.org/en/stable/how-to/assert.html) — Assert unchanged results, ordering, and no-op behavior.

## Applicable guardrails

- **The plan’s “## Plan intent”, named phase map:** keep Phase B as a private same-file phase between lifecycle work and Trigger 2.

- **The plan’s “## Step intent”, Phase B ownership:** let this handler own mixed-step policy and use the in-loop structural handoff only for exclusion.

- **The plan’s “## Out of scope”, behavior preservation:** preserve the public callable contract and all existing authoring, split, checkpoint, and error behavior.

- **The plan’s “## Out of scope”, separate structural mechanisms:** do not combine Phase B with Trigger 2 or with another convergence loop.

## Deferred

- Trigger 2 extraction — step 5 owns the second post-loop handler and its in-loop structural re-entry policy.

- Final concept persistence extraction — step 6 owns the persistence tail after both post-loop handlers finish.

- Shared convergence logic with `plan_tool/create.py:create_plan` — the plan’s separately scoped follow-up owns any cross-command abstraction.
