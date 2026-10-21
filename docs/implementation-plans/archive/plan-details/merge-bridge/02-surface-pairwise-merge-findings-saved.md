> **Auto-archived**: this plan was swept on 2026-07-07 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 2 — Surface pairwise merge findings in saved reconcile recommendations

## Summary

This step makes `plan-tool reconcile` save deterministic pairwise `granularity-merge` findings alongside the existing reconcile recommendations. The primary edit is in `plan_tool/review.py`, where the reconcile recommendation assembly should include the granularity advisor’s merge findings when running the full-plan reconcile lane. Coverage belongs in `tests/test_review.py`, focused on `extract_recommendations` and `review_plan_full`. The key design choice is to consume the existing `plan_tool/granularity.py:assess_granularity` output with its valid no-Claude `stage="completeness"` mode rather than re-implementing pairwise merge detection in review code. On green, a saved reconcile review can carry both the plan-wide re-ground finding and the pairwise merge findings while passing producer fields through unchanged.

## Table of Contents

- [Summary](#summary) — The step at a glance.
- [Why](#why) — Why saved reconcile recommendations need pairwise merge findings.
- [Files creates vs edits](#files-creates-vs-edits) — The exact file footprint for this step.
- [Implementation](#implementation) — The behavior to add and the constraints to keep.
- [Tests](#tests) — The focused unit coverage to add or adjust.
- [Acceptance criteria](#acceptance-criteria) — Observable checks for done.
- [References](#references) — Relevant Python and pytest docs for this step.
- [Deferred](#deferred) — Related bridge work that stays out of this step.

## Why

`plan_tool/granularity.py` already owns deterministic pairwise merge detection through `assess_granularity`, `_merge_signal_identical_file_sets`, `_merge_signal_trivial_refactor_feeding_one_feature`, and `_merge_rec`, while `plan_tool/review.py` currently saves only review-local findings plus the plan-wide re-ground `granularity-merge` finding from `_reground_already_built_recommendation`. That leaves the saved reconcile artifact missing pairwise merge advice even though the walk and later bridge work need saved `Recommendation` objects, not just report prose. Step 1 owns the producer-side machine-readable merge directive; this step makes the reconcile save path include those producer findings unchanged.

## Files (creates vs edits)

- **New files:** none.

- **Existing files (edits only):**
  - `plan_tool/review.py` — Add a reconcile-lane path for pairwise granularity recommendations, thread it through recommendation assembly, and call the granularity advisor from `review_plan_full`.
  - `tests/test_review.py` — Add focused tests that pairwise merge findings appear in reconcile recommendations and survive the full `review_plan_full` saved-review source path.

## Implementation

Foundational logic: **reconcile-lane granularity recommendation aggregation**.

- **Reuse the granularity advisor as the source of truth.** Pairwise merge detection lives in `plan_tool/granularity.py:assess_granularity`, which calls `_merge_findings` and `_merge_rec`. Call it from the reconcile producer with an existing valid no-Claude stage, `stage="completeness"`, rather than inventing a reconcile stage. Do not copy the identical-file or trivial-refactor predicates into `plan_tool/review.py`.

- **Keep the import one-way at module load.** `plan_tool/granularity.py` imports `plan_tool.review` for `Recommendation`, `_make_rec_id`, and `Invoker`, so `plan_tool/review.py` should not add a top-level import from `plan_tool.granularity`. Use a body-local import in `review_plan_full`, near the other deterministic reconcile checks, so the existing import direction remains safe.

- **Thread advisor findings explicitly.** One clean shape is to add an optional `granularity_recommendations: Optional[list[Recommendation]] = None` parameter to `plan_tool/review.py:extract_recommendations`. When `reconcile_lane=True` and `step_filter is None`, append the pairwise `granularity-merge` items from that list before or beside `_reground_already_built_recommendation`. Keep the existing default behavior unchanged when callers do not pass the list.

- **Filter to pairwise merge findings.** `assess_granularity` can return `granularity-split` and `granularity-merge` findings. This step’s target is pairwise merge findings only, so include only recommendations whose `source` is `_GRANULARITY_MERGE_SOURCE` and whose `step_id` is not `None`. The plan-wide re-ground finding remains owned by `_reground_already_built_recommendation`, where `step_id` is `None`.

- **Preserve reconcile-only gating.** The pairwise merge findings should follow the same broad gate as the re-ground finding in `extract_recommendations`: only full-plan reconcile, not default helper calls and not `step_filter` runs. `collect_deterministic_findings` should continue to omit these findings unless a later step deliberately changes that surface.

- **Preserve producer fields.** Step 1 owns the pairwise producer’s directive and id-stability work in `plan_tool/granularity.py:_merge_rec`. This step should pass those `Recommendation` objects through unchanged, including the current `suggested_action`, without asserting parseability in `plan_tool/review.py`. Do not rebuild them in `plan_tool/review.py`, and do not alter `render_merge_action`, `parse_merge_action`, `_make_rec_id`, or the pairwise fingerprint shape.

- **Keep info-level severity at save time.** Pairwise merge findings should be saved with the producer's existing severity rather than promoted in `plan_tool/review.py`. Step 4 owns the walk contract that parseable merge directives bypass the default info filter for structural dispatch, so this step should not require `--include-info` to make the saved recommendation useful later.

- **Keep saved review persistence generic.** `plan_tool/review_persistence.py:save_review` already serializes `Recommendation` objects with `dataclasses.asdict`, and `load_review` rebuilds them with `Recommendation(**r)`. No persistence schema change is needed as long as this step only adds more normal `Recommendation` objects to `ReviewResult.recommendations`.

- **Update the report only through existing recommendation flow.** `review_plan_full` already computes `recommendations` before `assemble_report`, and `assemble_report` receives that list for the severity banner. If pairwise findings need to show in the rendered report, prefer letting the existing recommendation/report flow account for them rather than adding a separate report-only section.

- **Do not make merge findings apply-eligible here.** `plan_tool/review.py:APPLY_ELIGIBLE_SOURCES`, `STRUCTURAL_SOURCES`, `is_apply_eligible`, and `is_structural` should keep their current treatment of `granularity-merge`. The bridge dispatch is a later step; this one only makes saved reconcile recommendations complete.

## Tests

- `test_extract_emits_pairwise_merge_in_reconcile_lane` — `extract_recommendations` includes a passed pairwise `granularity-merge` recommendation when `reconcile_lane=True` and `step_filter=None`.
- `test_extract_omits_pairwise_merge_by_default` — `extract_recommendations` does not include pairwise merge findings when the reconcile lane is not enabled.
- `test_extract_omits_pairwise_merge_under_step_filter` — `extract_recommendations` does not include pairwise merge findings for single-step reconcile runs.
- `test_pairwise_merge_recommendation_is_passed_through_unchanged` — the surfaced pairwise merge recommendation preserves the producer’s `suggested_action` and identity fields without rebuilding them in `plan_tool/review.py`.
- `test_review_plan_full_surfaces_pairwise_merge_finding` — a fixture with dependency-adjacent equal file sets produces a pairwise `granularity-merge` recommendation in `ReviewResult.recommendations`.
- `test_review_plan_full_can_surface_pairwise_merge_and_reground` — when a fixture triggers both pairwise merge and re-ground, `ReviewResult.recommendations` carries both `granularity-merge` shapes without one replacing the other.

### Test-creation order (feature step)

Add the `extract_recommendations` tests first because they define the new aggregation contract without invoking the full review orchestration. Then add the `review_plan_full` integration-style test to prove the body-local `assess_granularity` call is wired into the saved recommendation path. Every new test in `tests/test_review.py` must pass before this step is finished.

## Acceptance criteria

- `plan_tool/review.py:review_plan_full` calls the granularity advisor for full reconcile runs with `stage="completeness"` and passes pairwise merge recommendations into `extract_recommendations`.
- `plan_tool/review.py:extract_recommendations` includes pairwise `granularity-merge` recommendations only when `reconcile_lane=True` and `step_filter is None`.
- Pairwise merge recommendations are passed through unchanged, including `id`, `source`, `step_id`, `body`, `severity`, and `suggested_action`.
- Existing re-ground behavior from `_reground_already_built_recommendation` still emits one plan-wide `granularity-merge` finding when at least two distinct step ids with heuristic hits are present.
- `pytest tests/test_review.py` passes.

## References

- [dataclasses — Data Classes](https://docs.python.org/3/library/dataclasses.html) — Read for the `Recommendation` dataclass shape and why persistence can keep using `asdict`.
- [typing — Support for Type Hints](https://docs.python.org/3/library/typing.html) — Read for optional sequence/list typing used when threading advisor recommendations.
- [pytest Monkeypatch Guide](https://docs.pytest.org/en/stable/how-to/monkeypatch.html) — Read if a test needs to isolate the body-local granularity import or full `review_plan_full` orchestration.

## Deferred

- `plan_tool/granularity.py` producer edits — Step 1 owns adding the pairwise merge directive to `_merge_rec`; this step only consumes those recommendations.
- `plan_tool/review_walk.py` and `plan_tool/cli/review_actions.py` bridge dispatch — Later bridge steps decide whether saved `granularity-merge` findings become dispatchable and how merge vs re-ground routes to actuators.
- `plan_tool/review.py:APPLY_ELIGIBLE_SOURCES` and `STRUCTURAL_SOURCES` changes — This step keeps pairwise merge findings saved and advisory, not apply-eligible.
- `plan_tool/review_persistence.py` changes — Saved reviews already store normal `Recommendation` objects, so no persistence shape change belongs here.
