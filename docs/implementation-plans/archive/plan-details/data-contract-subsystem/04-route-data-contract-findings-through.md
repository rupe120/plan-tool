> **Auto-archived**: this plan was swept on 2026-07-07 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 4 — Route Data Contract Findings Through Saved Audit Walks

## Summary

This step teaches the saved-review walk and completeness replay path to recognize data-contract recommendations from steps 2 and 3 without routing them through the generic plan-edit actuator. The primary changes are in `plan_tool/review_walk.py:should_apply_as_finding`, `plan_tool/cli/review_actions.py:_build_review_action_fn`, and `plan_tool/cli/completeness_cmd.py:cmd_completeness_apply`, with coverage in `tests/cli/test_review_actions.py` and `tests/cli/test_completeness_cmd.py`. The key design decision is to reuse the existing saved-walk filtering, ordering, annotation, and carried-context machinery while keeping actual `DATA_CONTRACT.md` edits owned by step 3's dedicated `data-contract-apply` command and keeping stale plan/detail `## Input` references non-applyable unless a separate plan-edit path owns them. On green, saved data-contract findings can be walked, annotated in the original saved audit JSON, and included in carried-finding context, while generic `completeness-apply` either leaves them non-applying or redirects contract-doc findings to `data-contract-apply`.

## Table of Contents

- [Summary](#summary) — The behavior this step adds and the main files it touches.
- [Why](#why) — Why saved data-contract findings need the same apply path as other audit findings.
- [Files (creates vs edits)](#files-creates-vs-edits) — The exact files this step edits and what each edit owns.
- [Implementation](#implementation) — The source-routing rule and the saved-walk wiring.
- [Tests](#tests) — The test cases that cover the routing and replay behavior.
- [Test-creation order feature step](#test-creation-order-feature-step) — The order to add tests while building the feature.
- [Acceptance criteria](#acceptance-criteria) — Observable checks for completion.
- [References](#references) — Primary docs relevant to this step.
- [Deferred](#deferred) — Related work this step leaves out.

## Why

Steps 2 and 3 make data-contract drift visible and save it as recommendations, but the shared saved-walk code still needs to carry those recommendations through filtering, ordering, annotations, and resolution context. Without this step, a data-contract recommendation can appear in a saved audit replay but still be invisible to the dedicated data-contract apply flow or absent from carried context. The fix matters because data-contract drift should follow the same durable loop as conceptual completeness gaps, while still using a different edit actuator: saved artifact first, data-contract-specific apply when requested, persisted annotation, and later findings seeing earlier resolutions.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `plan_tool/review_walk.py` — Update the dispatchability documentation around `should_apply_as_finding`, `is_dispatchable`, `walk_recommendations`, and `_auto_apply` so caller-supplied apply sources are described as the supported extension point for saved audit families such as data-contract drift.
  - `plan_tool/cli/review_actions.py` — Keep `extra_apply_sources` threaded into `should_apply_as_finding` inside `_build_review_action_fn`, but ensure generic action building does not dispatch `source="data-contract"` to `plan_tool.launcher:apply_finding`; data-contract callers must supply a command-local action callback.
  - `plan_tool/cli/completeness_cmd.py` — Extend the saved serial completeness replay source set only far enough to surface or redirect data-contract recommendations predictably, include them in carried-finding state, and exclude them from the non-interactive parallel `--jobs` path and generic plan-edit apply path.
  - `tests/cli/test_review_actions.py` — Add focused tests that a caller-provided data-contract source can be considered walkable with a caller-owned action callback and still defaults to the terminal no-op outside that opt-in.
  - `tests/cli/test_completeness_cmd.py` — Add saved-audit replay tests for filtering, ordering, anchor narrowing, redirect/no-op behavior in generic completeness apply, and carried-finding context for data-contract recommendations.

## Implementation

- **Foundational logic: saved data-contract walk routing.** Treat recommendation source `data-contract` as walkable only for saved audit flows that explicitly opt into it, after the step 2 producer precondition is satisfied. Do not add a data-contract dispatcher to `plan_tool/cli/review_actions.py:_build_review_action_fn`, and do not send these documentation repairs through `plan_tool.launcher:apply_finding`; step 3's `data-contract-apply` command owns the `DATA_CONTRACT.md` editing callback.

- **Keep the generic walker conservative.** `plan_tool/review_walk.py:_APPLY_AS_FINDING_SOURCES` currently covers base sources such as `detail-reconcile`, `claude`, and `plan-completeness`, while `plan-correctness` is enabled only by `cmd_completeness_apply` through `extra_apply_sources`. Follow that pattern for `data-contract` unless the source is later made safe for every review/reconcile walk. This prevents a generic `reconcile-plan-walk` over a completeness sidecar from bypassing completeness replay gates.

- **Require the upstream source producer.** Step 4 hard-depends on step 2 having already added persisted data-contract drift recommendations with `Recommendation.source == "data-contract"`. Before changing routing, verify that `plan_tool/cli/completeness_phases.py:_persist_and_present_report` saves those recommendations; if the producer is absent, stop rather than creating it in this step.

- **Use one source plus explicit target metadata.** In `plan_tool/cli/completeness_cmd.py`, name source `data-contract` through a small local constant or a clearly named serial apply-source rank; do not re-detect data-contract drift or infer it from title/body text. When deciding whether a finding is applyable, also inspect the structured payload target produced by steps 1 and 2. `target="DATA_CONTRACT.md"` can redirect to `data-contract-apply`; `target="plan-detail"` or missing payload must remain non-applyable in this command.

- **Extend the serial replay filter without generic mutation.** `plan_tool/cli/completeness_cmd.py:cmd_completeness_apply` builds the saved recommendation subset from `_CONCEPTUAL_APPLY_SOURCE_RANK`, sorts by that rank, narrows by `--anchor`, then branches between serial walking and non-interactive parallel apply. Add data-contract recommendations to the serial saved-audit context only if the command can either hand applyable `DATA_CONTRACT.md` payloads to the step 3 data-contract action callback or report a clear "use data-contract-apply" redirect. Stale `## Input` findings and missing-payload data-contract findings should be shown as non-applyable plan/detail issues. Keep all data-contract findings out of the parallel `--jobs` subset and out of `_dispatch_apply_finding`.

- **Pick a stable apply order.** Keep `plan-correctness` before `plan-completeness`, because the current command fixes design gaps before filling missing coverage. Put source `data-contract` after conceptual plan edits; data-contract repairs update documentation and should not change the plan semantics that conceptual findings depend on.

- **Preserve carried-finding context.** `cmd_completeness_apply` seeds `_carried_resolution` from `saved.annotations`, builds `_build_carried()` from `_all_saved_recs`, and updates it after each `_recording_action`. Data-contract findings should be part of the saved recommendation set used for carried context, so a later apply can see that a data-contract finding was applied by `data-contract-apply`, skipped, open, redirected, or blocked in the same replay session.

- **Propagate routing intent consistently.** The walker and whichever action callback is active must agree on whether data-contract recommendations are actionable in that command. For `data-contract-apply`, both seams should opt into the source and use the command-local `DATA_CONTRACT.md` actuator from step 3. For generic `completeness-apply`, both seams should either leave the source non-actionable or record a redirect/no-op consistently, avoiding a half-wired path that records an applied annotation without a contract edit.

- **Keep annotation semantics unchanged.** `plan_tool/review_walk.py:_auto_apply` and `_prompt_for_annotation` already downgrade failed apply attempts to `status="failed"` and deliberate no-ops to `status="skip"` through `WalkState.apply_failed` and `WalkState.apply_skip`. Data-contract findings should use those existing statuses; do not add a data-contract-specific annotation status or saved-review schema field.

- **Keep non-TTY and parallel behavior unchanged.** `cmd_completeness_apply` is still an interactive replay path for serial walks. Data-contract findings should be reported or skipped under the command's existing non-TTY behavior and must not be passed to `run_parallel_apply` when `--jobs` selects the non-interactive mutating path.

- **Update comments where they would mislead.** `plan_tool/review_walk.py:walk_recommendations` still describes apply as invoking the action handler only for recognized reconcile/detail shapes, while the actual predicate is `is_dispatchable(..., extra_apply_sources=...)`. Refresh that prose while editing this area so future changes do not mistake data-contract routing for a special case.

## Tests

- `tests/cli/test_review_actions.py::test_data_contract_source_requires_command_local_action_callback` — A recommendation with source `data-contract` is not dispatched to `apply_finding` by `_build_review_action_fn`; a caller that wants mutation must supply the command-local action callback from `data-contract-apply`.
- `tests/cli/test_review_actions.py::test_data_contract_source_without_opt_in_is_terminal_noop` — The same recommendation does not call `apply_finding` without the caller opt-in and returns the existing no-suggested-action notice.
- `tests/cli/test_completeness_cmd.py::test_apply_redirects_data_contract_findings_from_saved_audit` — A saved completeness audit containing a data-contract recommendation does not route through generic `apply_finding`; it is either skipped as non-actionable in `completeness-apply` or points the operator at `data-contract-apply`.
- `tests/cli/test_completeness_cmd.py::test_input_reference_findings_are_non_applyable_in_completeness_apply` — A stale `## Input` data-contract finding is displayed as a plan/detail correctness issue and not redirected to the `DATA_CONTRACT.md` actuator.
- `tests/cli/test_completeness_cmd.py::test_apply_orders_data_contract_after_conceptual_sources` — Mixed saved findings are walked in the intended source order, with `plan-correctness` before `plan-completeness` and data-contract drift after the conceptual findings.
- `tests/cli/test_completeness_cmd.py::test_apply_anchor_targets_data_contract_source` — `--anchor` matches a data-contract recommendation by `Recommendation.id` or `Recommendation.anchor`.
- `tests/cli/test_completeness_cmd.py::test_data_contract_routing_intent_reaches_walker_and_action_builder` — The command passes consistent data-contract routing intent into `walk_recommendations` and the active action callback.
- `tests/cli/test_completeness_cmd.py::test_data_contract_carried_resolution_updates_after_apply` — A fresh data-contract apply verdict updates the carried-finding resolution map used by later replay applies.
- `tests/cli/test_completeness_cmd.py::test_parallel_apply_excludes_data_contract_findings` — A `--jobs` replay keeps data-contract recommendations out of the `run_parallel_apply` input while preserving the existing conceptual findings.

### Test-creation order (feature step)

1. Add the `tests/cli/test_review_actions.py` opt-in routing tests first; they pin that generic action building does not send data-contract findings to `apply_finding`.
2. Add the `tests/cli/test_completeness_cmd.py` saved-audit filtering and ordering tests next; they define which saved recommendations enter the walk.
3. Add the `--anchor` test before implementation is finished; it protects the operator targeting path from only matching conceptual findings.
4. Add the propagation test for `extra_apply_sources` on both `walk_recommendations` and `_build_review_action_fn`; this catches half-wired implementations.
5. Add the parallel exclusion test before the carried-resolution test; it protects the deferred `--jobs` boundary while the shared saved-recommendation filtering changes.
6. Add the carried-resolution test last; it verifies data-contract findings participate in the same replay history as conceptual gaps.

Every new test in these two files must be green before this step is considered finished.

## Acceptance criteria

- `plan_tool/cli/completeness_cmd.py:cmd_completeness_apply` includes source `data-contract` in saved completeness recommendation context only when it can redirect or hand off consistently, not when building generic plan-edit apply inputs.
- `plan_tool/cli/completeness_phases.py:_persist_and_present_report` already saves data-contract recommendations with `Recommendation.source == "data-contract"` before this step changes replay routing.
- `plan_tool/cli/completeness_cmd.py:cmd_completeness_apply` passes consistent data-contract routing intent to both the walker and active action callback.
- `plan_tool/cli/completeness_cmd.py:cmd_completeness_apply` excludes source `data-contract` from the recommendation list passed to `run_parallel_apply` when `--jobs` is used.
- A saved completeness audit with one data-contract recommendation and a TTY stdin does not call `apply_finding`; it uses the step 3 data-contract actuator when running through `data-contract-apply`, or reports a redirect/no-op from generic `completeness-apply`.
- A saved stale `## Input` data-contract recommendation does not call `apply_finding` and does not redirect to the `DATA_CONTRACT.md` actuator; it remains a plan/detail repair finding.
- The same data-contract recommendation does not become generally applyable in unrelated generic walks unless a caller opts in through `extra_apply_sources`.
- `--anchor` can narrow a completeness replay to a data-contract finding by saved `Recommendation.id` or `Recommendation.anchor`.
- Existing `plan-correctness` and `plan-completeness` replay behavior stays green, including correctness-first ordering and run-log threading.
- `pytest tests/cli/test_review_actions.py tests/cli/test_completeness_cmd.py` passes.

## References

- [Python json](https://docs.python.org/3/library/json.html) — Read for saved sidecar record behavior and why this step should not add a new annotation schema.
- [pytest Documentation](https://docs.pytest.org/en/stable/) — Use for focused monkeypatch and fixture patterns in the CLI replay tests.

## Deferred

- `plan_tool/cli/data_contract_cmd.py` command wiring — Step 3 owns the dedicated `data-contract-apply` command; this step only updates the shared saved-walk routing in its declared files.
- Saved-review schema changes — Data-contract findings are still `Recommendation` records with normal `Annotation` updates, so adding fields or schema versions is out of scope.
- Re-running data-contract detection during apply — Saved replay must use the persisted audit findings from step 2 instead of re-detecting drift from current `DATA_CONTRACT.md`.
- Parallel `--jobs` behavior for data-contract findings — This step targets the saved interactive walk path; extending non-interactive parallel apply needs a separate plan decision if the source should participate there.
