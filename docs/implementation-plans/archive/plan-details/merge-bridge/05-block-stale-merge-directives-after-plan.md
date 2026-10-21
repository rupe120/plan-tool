> **Auto-archived**: this plan was swept on 2026-07-07 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 5 — Block stale merge directives after a plan fingerprint change

## Summary

This step adds a conservative stale-directive gate to structural remedy dispatch in `plan_tool/cli/review_actions.py:_build_review_action_fn`. The gate compares the saved review’s `plan_fingerprint` against the current plan fingerprint before any merge-directive actuator can mutate the plan. The key design decision is to block on whole-plan fingerprint drift instead of trying to prove that the saved step ids still mean the same thing after edits or renumbering. On green, a stale saved `granularity-merge` directive is recorded as a skip/recommendation and no bridge is called.

## Table of Contents

- [Summary](#summary) — The step at a glance.
- [Why](#why) — Why saved merge directives need a freshness check before mutation.
- [Files creates vs edits](#files-creates-vs-edits) — The exact file set for this step.
- [Implementation](#implementation) — The behavior to add and the constraints to keep.
- [Tests](#tests) — The focused unit coverage to add or adjust.
- [Acceptance criteria](#acceptance-criteria) — Observable checks for done.
- [References](#references) — Relevant testing and typing references.
- [Deferred](#deferred) — Related work left out of this step.

## Why

Step 4 makes parsed merge directives dispatchable through the review walk, but those directives carry saved step ids. If the plan changes after the review was saved, those ids can point at different steps, especially after structural edits that renumber or fold steps. `plan_tool/cli/review_actions.py:_dispatch_reground_remedy` already has part of this guard in HEAD for `MERGE_ACTION_REGROUND`; this step should make that stale-fingerprint rule the explicit contract for merge-directive actuation, so a stale saved finding cannot call `plan_tool.reground.reground_bridge` or a later `plan_tool.detail.merge_bridge` against the wrong targets.

## Files (creates vs edits)

- **New files:** none.

- **Existing files (edits only):**
  - `plan_tool/cli/review_actions.py` — Keep `saved_plan_fingerprint` as the action-builder freshness input, apply the stale guard before any structural remedy bridge call, and make stale outcomes set `WalkState.apply_skip`.
  - `tests/cli/test_review_actions.py` — Add or adjust dispatch tests that prove stale saved fingerprints block bridge calls, legacy empty fingerprints do not block, and same-session re-ground redispatch is not mislabeled stale.

## Implementation

Foundational logic: **saved-plan-fingerprint stale directive gate**.

- **Use the saved review fingerprint as the freshness contract.** `plan_tool/cli/review_actions.py:_build_review_action_fn` already accepts `saved_plan_fingerprint`, and `plan_tool/cli/review_cmd.py` passes `saved.plan_fingerprint` or `loaded.plan_fingerprint` when building the action function. Keep that as the only freshness input for this step.

- **Compare against the current plan right before actuation.** In the structural directive dispatcher inside `plan_tool/cli/review_actions.py:_build_review_action_fn`, compute the current value with `plan_tool.review_persistence.compute_plan_fingerprint(plan_path)` only when `saved_plan_fingerprint` is non-empty. If it differs, do not call the bridge.

- **Block every mutating structural directive path.** The existing `plan_tool/cli/review_actions.py:_dispatch_reground_remedy` branch already parses `plan_tool.review.parse_merge_action`, checks `MERGE_ACTION_REGROUND`, and calls `plan_tool.reground.reground_bridge`. If step 4 has also added a `MERGE_ACTION_MERGE` branch that calls `plan_tool.detail.merge_bridge`, apply the same stale guard before that bridge call too. Do not leave merge and re-ground with different freshness rules.

- **Keep legacy saved reviews usable.** Treat an empty `saved_plan_fingerprint` as “unknown,” not stale. The guard should not block old sidecars or tests that build action functions without a persisted fingerprint.

- **Mark stale as skipped, not applied.** When the stale guard fires, set `state.apply_skip = True` and return a one-line message that tells the operator the plan changed and they should rerun the diagnosis or reconcile walk. No edit landed, so the saved recommendation must not be recorded as resolved.

- **Respect the same-session re-ground signal.** `plan_tool/review_walk.py:WalkState.applied_reground_finding_ids` exists to distinguish “this walk already applied this re-ground” from “the saved review is stale.” Preserve the current ordering in `plan_tool/cli/review_actions.py:_dispatch_reground_remedy`: a rec id already present in `state.applied_reground_finding_ids` resolves before the stale guard. Do not use this session signal for unrelated stale findings.

- **Do not infer freshness from directive shape.** `plan_tool.review.parse_merge_action` recovers `MergeAction.kind` and `MergeAction.step_ids`; it does not prove those ids still name the same logical steps. Keep the fingerprint gate separate from parsing.

- **Do not widen the step scope.** `plan_tool/review_walk.py:merge_remedy_target` and `plan_tool/review_walk.py:is_dispatchable` are step 4’s dispatchability gate. This step should not change them unless implementation finds that step 4 is missing entirely; if so, stop and reconcile the dependency rather than folding step 4 into this stale-guard step.

## Tests

- `test_stale_plan_fingerprint_downgrades_to_recommend` — a non-empty saved fingerprint that differs from the current plan prevents the bridge call, sets `state.apply_skip`, and returns a “changed since” message.
- `test_empty_saved_fingerprint_does_not_block` — an empty saved fingerprint reaches the bridge normally.
- `test_stale_reground_with_coincidental_done_ids_downgrades` — stale fingerprints are checked before the bridge can return `noop`, so coincidentally done ids do not resolve the finding.
- `test_applied_reground_resolves_on_redispatch` — a finding id in `WalkState.applied_reground_finding_ids` resolves before the stale guard and does not call the bridge again.
- `test_stale_merge_directive_does_not_call_merge_bridge` — if the step 4 merge branch exists, a stale `MERGE_ACTION_MERGE` directive does not call `plan_tool.detail.merge_bridge` and records skip.

### Test-creation order (feature step)

Add the stale-fingerprint tests alongside the dispatcher tests in `tests/cli/test_review_actions.py` while implementing the guard. Start with the re-ground branch because it exists in HEAD, then add the merge-branch test only when step 4’s `MERGE_ACTION_MERGE` dispatcher is present. Every new test must be green before this step is considered finished.

## Acceptance criteria

- `plan_tool/cli/review_actions.py:_build_review_action_fn` blocks structural directive actuation when `saved_plan_fingerprint` is non-empty and differs from `compute_plan_fingerprint(plan_path)`.
- A stale directive sets `WalkState.apply_skip = True` and returns an operator-facing message that names the plan-change reason.
- A stale directive does not call `plan_tool.reground.reground_bridge`, and if the step 4 merge branch exists, it does not call `plan_tool.detail.merge_bridge`.
- An empty saved fingerprint does not block bridge dispatch.
- A same-session re-ground rec id in `WalkState.applied_reground_finding_ids` resolves before the stale guard.
- `tests/cli/test_review_actions.py` covers stale, empty-fingerprint, coincidental-noop, and same-session redispatch behavior.

## References

- [unittest.mock — Mock Object Library](https://docs.python.org/3/library/unittest.mock.html) — Use for patching bridge functions on their owning modules in dispatcher tests.
- [pytest Monkeypatch Guide](https://docs.pytest.org/en/stable/how-to/monkeypatch.html) — Use for isolating bridge calls and filesystem fingerprint cases in `tests/cli/test_review_actions.py`.
- [typing — Support for Type Hints](https://docs.python.org/3/library/typing.html) — Useful when keeping the dispatcher’s optional state and callable typing clear.

## Deferred

- Precise per-step-id freshness — Whole-plan fingerprint drift is conservative and may block a still-valid directive after an unrelated edit. A narrower check would need a separate design for comparing saved step identities.
- Dispatchability changes in `plan_tool/review_walk.py` — Step 4 owns `merge_remedy_target` and `is_dispatchable`; this step only guards actuation after the directive reaches `plan_tool/cli/review_actions.py`.
- Persistence schema changes — This step uses the existing saved review `plan_fingerprint`; it does not add fields to saved reviews or recommendations.
