> **Auto-archived**: this plan was swept on 2026-08-18 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 5 — Extract Trigger 2 as the second post-loop split handler

## Summary

Extract Trigger 2’s post-loop recovery from `plan_tool/detail.py:generate_detail` into a private same-file handler. The handler receives the lifecycle’s results and in-loop structural state after step 4’s Phase B handler finishes, then owns Trigger 2 re-entry, result rebuilding, and recommendation emission. Update `tests/test_detail.py` to pin the handler order and the distinct recovery policy. On green, `generate_detail` remains behaviorally unchanged while reading as lifecycle, Phase B, Trigger 2, then persistence.

## Table of Contents

- [Summary](#summary) — Reviewer overview of the Trigger 2 extraction.
- [Table of Contents](#table-of-contents) — Links to each section in this detail.
- [Why](#why) — Why Trigger 2 needs its own post-loop owner.
- [Input](#input) — Lifecycle state and split contracts the handler consumes.
- [Files (creates vs edits)](#files-creates-vs-edits) — Files changed by this refactor.
- [Implementation](#implementation) — Required handler boundary, ordering, and recovery behavior.
- [Tests](#tests) — Regression coverage for Trigger 2’s extraction.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Primary references for state transfer and tests.
- [Applicable guardrails](#applicable-guardrails) — Plan constraints that bind this extraction.
- [Deferred](#deferred) — Work intentionally left outside this step.

## Why

`plan_tool/detail.py:generate_detail` currently keeps Trigger 2’s in-loop structural recovery inline after Phase B, even though it starts from a `BLOCKED-STRUCTURAL` decision rather than a mixed-step finding. It must remain separate because an applied in-loop split stops the authoring loop and leaves every later detail-less step for re-entry, while Phase B has its own bridge and recovery policy. Naming this second handler makes that difference and the required ordering clear without changing either path.

## Input

- **Step 3 lifecycle handoff:** consume the authored `list[DetailResult]`, the applied in-loop split identifiers in `structural_split_ids`, and recommend-only findings in `inloop_structural_recs`. Step 3 continues to own detection of `BLOCKED-STRUCTURAL`, snapshot restoration, finding de-duplication, and `plan_tool/launcher.py:escalate_to_split`.

- **Step 4 result handoff:** start from the results returned after Phase B completes. Do not read or reset Phase B’s mixed-step findings or its recommendation list.

- **Renumbered plan state:** use the current plan from `plan_tool/parser.py:parse_plan` and `Step.detail` to find recovery targets after an applied split has changed step ids.

- **Result attribution:** retain `plan_tool/detail.py:_detail_slug_key` as the id-independent identity for deciding whether a post-split detail file was written in this invocation or only carried through renumbering.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `plan_tool/detail.py` — extract Trigger 2’s post-loop re-entry, result rebuilding, and recommendation emission from `generate_detail` into a private same-file handler.
  - `tests/test_detail.py` — add handler-order coverage and retarget Trigger 2 recovery tests to the extracted boundary.

## Implementation

- **Foundational logic:** recover from an applied in-loop structural split only after Phase B has finished.

- **Give Trigger 2 one private owner.** Extract the block introduced by the `Trigger-2 post-loop` marker in `plan_tool/detail.py:generate_detail` into a handler such as `_handle_trigger_2_splits`. Keep `plan_tool/detail.py:generate_detail` as the coordinator: call step 4’s Phase B handler first, call this handler second, then leave final concept persistence for step 6.

- **Use an explicit handoff.** Pass the current results, `structural_split_ids`, `inloop_structural_recs`, and every dependency needed for re-authoring as explicit inputs. Return the rebuilt `list[DetailResult]`; do not depend on new closures or mutate Phase B state.

- **Keep the trigger boundary at the lifecycle.** Leave the per-step `BLOCKED-STRUCTURAL` route in step 3’s lifecycle, including the required restore-before-escalate ordering around `plan_tool/launcher.py:escalate_to_split`. The new handler consumes only the lifecycle’s accumulated outcomes; it must not re-run the bridge or treat mixed-step findings as Trigger 2 input.

- **Run after Phase B, never inside it.** Phase B completes its own split recovery and recommendation emission before Trigger 2 starts. Do not merge their accumulators or coalesce their recommendation output merely because both paths can revise post-loop results.

- **Re-enter only the affected plan state.** When `structural_split_ids` is non-empty, re-parse the plan and select every step whose `Step.detail` is unset. This includes the new split halves and targets the stopped authoring loop did not reach; do not revisit already detailed steps or prompt to replace their files.

- **Preserve recursive re-entry rules.** One low-risk approach is to retain the existing explicit-id calls through `plan_tool/detail.py:generate_detail`. Keep the current `resume=False`, nested `allow_split=False`, iteration budget, invocation seams, logging, and other authoring inputs so each current detail-less target receives its normal convergence work without starting another structural split path. Each nested call also retains its own final persistence after its own child work; do not defer that save to the enclosing Trigger 2 handler, and retain a nested persistence failure in the rebuilt result.

- **Keep split commits out of half recovery.** Preserve the current absence of `commit_step` on Trigger 2 re-entry. The split’s structural changes and its re-authored halves remain part of the enclosing run’s final commit rather than being attributed to an individual half.

- **Rebuild results from final plan state.** After recovery, keep results below the lowest applied split id and rebuild the renumbered region from the final parsed plan. Use `plan_tool/detail.py:_detail_slug_key` to mark only this invocation’s authored files as written; report pre-existing renumbered files as carried-through skips and retain failed half results.

- **Emit Trigger 2 recommendations once.** Pass only `inloop_structural_recs` to `plan_tool/detail.py:_emit_split_recommendations`, after Trigger 2 recovery completes. An empty list remains silent, and this reporting does not replace Phase B’s earlier recommendation surface.

## Tests

### Tests for this step

- `test_phase_b_handler_precedes_trigger_2_handler` — assert that when both post-loop paths have work, Phase B completes its bridge, recovery, and reporting before Trigger 2 begins.

- `TestInLoopStructuralEscalation.test_applied_split_breaks_all_loops` — retain the integration proof that an applied in-loop split stops further authoring and reaches post-loop recovery with no result for the removed original step.

- `TestInLoopStructuralEscalation.test_applied_split_reauthors_detail_less_halves` — retarget the existing case to the Trigger 2 handler and assert that the renumbered halves are authored in the same run.

- `test_trigger_2_reentry_targets_all_and_only_detail_less_steps` — assert that recovery includes later targets left unset by the stopped loop while never replacing an existing detail file.

- `test_trigger_2_reentry_preserves_budget_without_nested_split_or_half_commit` — assert that re-entry keeps the parent convergence budget but disables recursive splitting and does not invoke the per-step commit callback.

- `test_trigger_2_rebuilds_renumbered_results_by_slug_key` — assert that final results distinguish newly written detail files from pre-existing files carried through renumbering and retain failed recovery results.

- `TestInLoopStructuralEscalation.test_recommend_only_collects_and_surfaces_rec` — retarget the recommendation case to the extracted handler and assert that it leaves plan structure unchanged while emitting `plan-tool split` guidance once.

Every listed test must be green before this step is complete.

## Acceptance criteria

- `plan_tool/detail.py:generate_detail` invokes a private Trigger 2 handler after Phase B and before concept persistence.

- The Trigger 2 handler consumes only lifecycle-returned in-loop structural state and returns the final rebuilt results.

- An applied in-loop split re-authors every current detail-less target, including new halves and later targets the stopped loop did not reach, without revisiting existing details, starting nested split handling, or committing a half independently.

- Trigger 2 preserves each recursive call's existing final-persistence timing and failure result while its outer handler completes before the outer invocation reaches final persistence.

- Final results use `plan_tool/detail.py:_detail_slug_key` to distinguish this run’s writes from carried-through detail files after renumbering.

- Trigger 2 recommend-only findings are emitted once after Trigger 2 recovery and remain separate from Phase B recommendations.

- `plan_tool/detail.py:generate_detail` retains its public signature and observable behavior.

- `tests/test_detail.py` passes without weakening existing assertions.

## References

- [Python 3.13 Execution Model](https://docs.python.org/3.13/reference/executionmodel.html) — Review explicit argument passing and local state when extracting orchestration code.

- [Python dataclasses](https://docs.python.org/3.13/library/dataclasses.html) — Use a small private state carrier if the post-loop handoff needs one.

- [pytest Monkeypatching Guide](https://docs.pytest.org/en/stable/how-to/monkeypatch.html) — Use spies and controlled outcomes to prove handler ordering and re-entry arguments.

- [pytest Assertion and Exception Testing](https://docs.pytest.org/en/stable/how-to/assert.html) — Assert recovery results, no-op behavior, and unchanged plan state.

## Applicable guardrails

- **The plan’s “Plan intent”, named phase map:** keep Trigger 2 as the second same-file post-loop phase, immediately before persistence.

- **The plan’s “Step intent”, distinct Trigger 2 policy:** consume only in-loop structural state and retain its re-entry policy outside Phase B.

- **The plan’s “Out of scope”, behavior preservation:** keep the public API, checkpoint behavior, error behavior, and existing split results unchanged.

- **The plan’s “Out of scope”, separate structural mechanisms:** do not combine Phase B and Trigger 2 into one handler or one shared accumulator.

## Deferred

- Shared split-half recovery helper — Phase B and Trigger 2 have similar re-authoring and result-rebuild shapes, but consolidating them would need a separately scoped reconcile decision that preserves their separate policies.

- Final concept persistence extraction — step 6 owns the persistence tail after both post-loop handlers return for each invocation; recursive re-entry keeps its own existing tail before the enclosing handler resumes.
