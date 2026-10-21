> **Auto-archived**: this plan was swept on 2026-07-07 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 4 — Route merge directives to merge_bridge in the review walk

## Summary

This step completes structural-remedy routing for `granularity-merge` findings in the review walk. The main edits are in `plan_tool/cli/review_actions.py:_build_review_action_fn`, with small predicate/doc updates in `plan_tool/review_walk.py` if HEAD does not already include `merge_remedy_target`, plus focused tests in `tests/cli/test_review_actions.py` and `tests/test_review_walk.py`. The key design decision is to route by `plan_tool.review.parse_merge_action()`'s directive kind, not by `Recommendation.source` or `Recommendation.step_id`. On green, a `merge` directive calls `plan_tool.detail.merge_bridge`, a `reground` directive continues to call `plan_tool.reground.reground_bridge`, and non-mutating bridge outcomes are recorded as skips rather than resolved applies.

## Table of Contents

- [Summary](#summary) — The step at a glance.
- [Why](#why) — Why directive findings need a walk dispatcher.
- [Files creates vs edits](#files-creates-vs-edits) — The exact file list for this step.
- [Implementation](#implementation) — The behavior to add and the constraints to keep.
- [Tests](#tests) — The focused unit coverage to add or adjust.
- [Acceptance criteria](#acceptance-criteria) — Observable checks for done.
- [References](#references) — Relevant Python and pytest docs for this step.
- [Deferred](#deferred) — Related bridge and docs work left out of this step.

## Why

Steps 1 and 3 are expected to give the system the two pieces it needs: pairwise merge findings should carry a parseable `merge` directive, and step 3 is expected to add the `plan_tool/detail.py:merge_bridge` apply-or-recommend gate around `merge_steps`. The review walk still needs to connect those pieces. Before implementing this step, confirm step 1 has updated `plan_tool/granularity.py:_merge_rec` to emit the shared merge directive format, such as `render_merge_action(MERGE_ACTION_MERGE, ...)`, instead of only the legacy `Consider merging steps ...` text. Also confirm the step 3 exported bridge name, call signature, result type, `allow_merge` gate parameter, and outcome strings; treat the producer directive shape plus `merge_bridge` and `MergeBridgeResult` below as dependency-step contracts until those APIs exist in HEAD. In current HEAD, part of this lane may already be present: `plan_tool/review_walk.py:merge_remedy_target` makes directive findings dispatchable, and `plan_tool/cli/review_actions.py:_dispatch_reground_remedy` routes the `reground` directive. The missing piece for this step is the matching `merge` directive branch that calls the confirmed merge bridge without conflating it with re-ground.

## Files (creates vs edits)

- **New files:** none.

- **Existing files (edits only):**
  - `plan_tool/review_walk.py` — Ensure `merge_remedy_target` parses `plan_tool.review.parse_merge_action()` and `is_dispatchable` treats any parsed merge/re-ground directive as dispatchable. If this is already present, keep it as the predicate the action builder uses.
  - `plan_tool/cli/review_actions.py` — Add the structural merge dispatcher inside `_build_review_action_fn`, route parsed `MERGE_ACTION_MERGE` directives to `plan_tool.detail.merge_bridge`, and keep `MERGE_ACTION_REGROUND` routed to `plan_tool.reground.reground_bridge`.
  - `tests/cli/test_review_actions.py` — Add merge-dispatch coverage beside the existing re-ground-dispatch tests.
  - `tests/test_review_walk.py` — Add or extend predicate/walk tests proving directive findings are dispatchable through the walk and non-directive `granularity-merge` findings are not.

## Implementation

Foundational logic: **directive-kind structural remedy dispatch**.

- **Parse once from the shared marker.** Use `plan_tool.review.parse_merge_action` as the source of truth for both the remedy kind and the target step ids. Do not infer the target from `Recommendation.step_id`: pairwise merge findings use the low member id there, and re-ground findings use `None`.

- **Keep `plan_tool/review_walk.py` as the dispatchability gate.** `plan_tool/review_walk.py:merge_remedy_target` should sit beside `file_check_create_target`, and `plan_tool/review_walk.py:is_dispatchable` should return true when that predicate returns a `MergeAction`. This lets the normal apply path, run path, and apply-all path all reach the action function through the same gate.

- **Bypass the default info filter for directive merges.** Pairwise `granularity-merge` findings may remain `severity="info"`, but a parseable `MERGE_ACTION_MERGE` directive is part of the targeted structural walk surface. When `walk_recommendations` is called with `skip_info=True`, it should still present directive-bearing merge findings for dispatch; directive-less info findings should keep the existing `--include-info` behavior.

- **Split by directive kind in `plan_tool/cli/review_actions.py`.** Add a dispatcher near `_dispatch_reground_remedy`; a name like `_dispatch_merge_remedy` fits the existing `_dispatch_structural_escalation` and `_dispatch_file_check_create` pattern. The branch in `action(rec)` should stay after `file_check_create_target(rec)` and before the terminal no-suggestion/manual-run notices. The branch must re-check `parse_merge_action(rec)` internally, because the walk's `(r)un` key can call `action_fn` on a recommendation that did not pass `is_dispatchable`.

- **Call the actuator on its owning module.** Import `plan_tool.detail.merge_bridge` inside the dispatcher body, the same way `_dispatch_reground_remedy` imports `plan_tool.reground.reground_bridge`. Tests should patch `plan_tool.detail.merge_bridge`, not a `plan_tool.cli.review_actions` module global.

- **Use the existing structural opt-in.** Reuse `_build_review_action_fn`'s `allow_structural_remedy` parameter for merge dispatch. Pass `allow_merge=allow_structural_remedy and not state.yes_to_all`, and pass `yes=False` so a blanket apply-all never silently confirms a structural mutation. This mirrors `_dispatch_reground_remedy` and `_dispatch_structural_escalation`.

- **Forward real execution seams.** `merge_bridge` wraps `plan_tool/detail.py:merge_steps`, whose applied path may need the same seams as direct merge execution. Forward `plan_path`, `repo_root=ctx.repo_root`, the parsed directive ids as `merge_ids` or the bridge's actual merge-id parameter from step 3, plus `run_logger` and any detail-authoring seams that `merge_bridge` exposes. Do not call `merge_steps` directly from `plan_tool/cli/review_actions.py`.

- **Map outcomes to annotations deliberately.** Leave `state.apply_skip` false only when `merge_bridge` returns `outcome == "applied"`. Set `state.apply_skip = True` for every non-mutating merge outcome: `recommended`, `unsafe`, `invalid`, and any other deterministic refusal the step 3 bridge exposes. A recommended or refused merge did not edit the plan, so the walk must persist `skip`, not `applied`.

- **Render one-line results from bridge data.** Keep action messages short and outcome-specific. For `applied`, name the folded ids and survivor if `MergeBridgeResult` exposes them through its embedded `MergeResult`. For `recommended`, tell the operator the merge is available behind `--apply-structural` and a TTY confirmation. For `unsafe`, report the blocking ids. For `invalid`, report the bridge's refusal reason or the requested ids, depending on the result fields step 3 provides.

- **Do not route on `granularity-merge` alone.** A directive-less `granularity-merge` finding must keep returning the existing manual-run notice. A `reground` directive must keep using `reground_bridge`; a `merge` directive must use `merge_bridge`. The shared source string is not enough to choose a remedy.

- **Preserve current re-ground safeguards.** If `plan_tool/cli/review_actions.py:_dispatch_reground_remedy` already has stale-fingerprint handling through `saved_plan_fingerprint` and `compute_plan_fingerprint`, leave that behavior in place. Do not copy that exact guard to merge unless the step 3 bridge contract requires it; `merge_bridge` owns merge validation and safety, while this step owns routing.

## Tests

- `tests/test_review_walk.py::test_merge_directive_is_dispatchable` — a `granularity-merge` recommendation with a `MERGE_ACTION_MERGE` marker returns a non-`None` `merge_remedy_target` and `is_dispatchable(rec) is True`.
- `tests/test_review_walk.py::test_info_level_merge_directive_visible_without_include_info` — an info-level `MERGE_ACTION_MERGE` recommendation is still yielded by the walk when `skip_info=True`.
- `tests/test_review_walk.py::test_granularity_merge_without_directive_not_dispatchable` — a same-source recommendation without the marker is not dispatchable through the merge-remedy predicate.
- `tests/cli/test_review_actions.py::test_merge_directive_routes_to_merge_bridge` — applying a `merge` directive calls `plan_tool.detail.merge_bridge` with the directive's full step id set.
- `tests/cli/test_review_actions.py::test_merge_step_ids_forwarded_from_directive_not_rec_step_id` — the dispatcher ignores `rec.step_id` and forwards only the parsed directive ids.
- `tests/cli/test_review_actions.py::test_merge_opt_in_forced_off_under_yes_to_all` — `WalkState(yes_to_all=True)` forces `allow_merge=False` and passes `yes=False`.
- `tests/cli/test_review_actions.py::test_merge_opt_in_passed_when_apply_structural_enabled` — `allow_structural_remedy=True` and no fast-forward passes `allow_merge=True`.
- `tests/cli/test_review_actions.py::test_merge_applied_outcome_records_applied` — an `applied` bridge result leaves `state.apply_skip is False`.
- `tests/cli/test_review_actions.py::test_merge_recommended_outcome_sets_apply_skip` — a `recommended` bridge result sets `state.apply_skip is True`.
- `tests/cli/test_review_actions.py::test_merge_unsafe_outcome_sets_apply_skip` — an `unsafe` bridge result sets `state.apply_skip is True` and names blocking ids.
- `tests/cli/test_review_actions.py::test_merge_invalid_outcome_sets_apply_skip` — an `invalid` bridge result sets `state.apply_skip is True` and does not mark the finding resolved.
- `tests/cli/test_review_actions.py::test_reground_directive_still_routes_to_reground_bridge` — the existing re-ground branch still calls `plan_tool.reground.reground_bridge`, not `merge_bridge`.

### Test-creation order (feature step)

Add the predicate tests in `tests/test_review_walk.py` first, then add the merge-dispatch tests in `tests/cli/test_review_actions.py` with `plan_tool.detail.merge_bridge` patched on its owning module. Once the dispatcher branch exists, keep the existing re-ground tests green to prove the new merge branch did not steal `MERGE_ACTION_REGROUND`. This step is done only when every new test is green and the existing review-walk/action tests still pass.

## Acceptance criteria

- `plan_tool/review_walk.py:is_dispatchable` returns true for a `granularity-merge` recommendation whose `suggested_action` contains a valid `→ merge steps:` marker.
- `plan_tool/review_walk.py:walk_recommendations` presents info-level `MERGE_ACTION_MERGE` recommendations under the default `skip_info=True` walk filter.
- `plan_tool/review_walk.py:is_dispatchable` returns false for a `granularity-merge` recommendation with no parseable directive marker.
- `plan_tool/cli/review_actions.py:_build_review_action_fn` routes `MERGE_ACTION_MERGE` directives to `plan_tool.detail.merge_bridge`.
- `plan_tool/cli/review_actions.py:_build_review_action_fn` routes `MERGE_ACTION_REGROUND` directives to `plan_tool.reground.reground_bridge`.
- The merge dispatcher forwards the parsed directive step ids, not `Recommendation.step_id`.
- `WalkState.yes_to_all` never causes `allow_merge=True` or `yes=True`.
- Only `merge_bridge` outcome `applied` records the walk annotation as applied; `recommended`, `unsafe`, and `invalid` record skip through `state.apply_skip`.
- `pytest tests/test_review_walk.py tests/cli/test_review_actions.py` passes.

## References

- [dataclasses — Data Classes](https://docs.python.org/3/library/dataclasses.html) — Useful for reading the frozen bridge result types returned by the merge and re-ground actuators.
- [typing — Support for Type Hints](https://docs.python.org/3/library/typing.html) — Covers the optional callable and structured return typing used by the walk/action seams.
- [unittest.mock — Mock Object Library](https://docs.python.org/3/library/unittest.mock.html) — Relevant for patching `plan_tool.detail.merge_bridge` on its owning module in tests.
- [pytest Monkeypatch Guide](https://docs.pytest.org/en/stable/how-to/monkeypatch.html) — Relevant for isolating the body-local bridge imports in `tests/cli/test_review_actions.py`.

## Deferred

- Documentation updates in `CLAUDE.md` and `RUNBOOK.md` — a later docs step should describe the new apply path and remove any recommend-only merge wording.
- New CLI flags or parser wiring — this step reuses the existing structural opt-in passed into `_build_review_action_fn`; adding a separate merge-only flag needs a plan-level decision.
- Changes to `plan_tool/review.py` directive grammar — steps 1 and 2 own the producer/parser shape; this step consumes `parse_merge_action`.
- Changes to `plan_tool/detail.py:merge_bridge` — step 3 owns the bridge contract and merge safety behavior; this step only calls it.
