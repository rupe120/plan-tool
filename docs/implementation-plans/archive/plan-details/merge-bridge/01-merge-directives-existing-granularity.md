> **Auto-archived**: this plan was swept on 2026-07-07 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 1 — Add merge directives to granularity merge findings

## Summary

This step makes deterministic `granularity-merge` findings from `plan_tool/granularity.py` carry the same parseable merge directive shape already used by the re-ground lane. The primary code edit is `plan_tool/granularity.py:_merge_rec`, with coverage added in `tests/test_granularity.py` and a small grammar round-trip guard in `tests/test_review.py`. The key design choice is to append the directive to `Recommendation.suggested_action` through the existing `plan_tool/review.py:render_merge_action` helper, not to add fields to `Recommendation` or change the rec id fingerprint. On green, a pairwise merge finding still reads well to a person, but `plan_tool/review.py:parse_merge_action` can recover `kind="merge"` and the full step id set.

## Table of Contents

- [Summary](#summary) — The step at a glance.
- [Why](#why) — Why deterministic merge findings need a machine-readable target.
- [Files creates vs edits](#files-creates-vs-edits) — The exact file footprint for this step.
- [Implementation](#implementation) — The behavior to add and the constraints to keep.
- [Tests](#tests) — The focused unit coverage to add or adjust.
- [Acceptance criteria](#acceptance-criteria) — Observable checks for done.
- [References](#references) — Relevant language docs for the existing structured helper.
- [Deferred](#deferred) — Related bridge work that stays out of this step.

## Why

`granularity-merge` is shared by two producers with different remedies: `plan_tool/granularity.py:_merge_rec` emits adjacent-step merge advice, while `plan_tool/review.py:_reground_already_built_recommendation` emits re-ground advice. `plan_tool/review.py` already has the shared directive grammar (`MergeAction`, `render_merge_action`, `parse_merge_action`) and the re-ground producer already uses it, but the granularity producer still emits only free-form “Consider merging…” text. That leaves downstream routing unable to recover the full merge target from the finding without guessing from prose or under-reading `rec.step_id`, which only carries the low member id.

## Files (creates vs edits)

- **New files:** none.

- **Existing files (edits only):**
  - `plan_tool/granularity.py` — Import the existing merge directive helper symbols from `plan_tool.review` and append a `merge` directive in `_merge_rec` while leaving the `_make_rec_id` fingerprint unchanged.
  - `tests/test_granularity.py` — Add assertions that deterministic merge findings parse through `plan_tool.review.parse_merge_action`, carry both step ids, and keep stable ids.
  - `tests/test_review.py` — Extend `TestMergeActionGrammar` with a `merge` round-trip guard for `render_merge_action` and `parse_merge_action`.

## Implementation

Foundational logic: **machine-readable merge directive on `suggested_action`**.

- **Reuse the existing directive grammar.** `plan_tool/review.py:MergeAction`, `MERGE_ACTION_MERGE`, `MERGE_ACTION_REGROUND`, `render_merge_action`, and `parse_merge_action` already exist and are the shared grammar. This step should treat `plan_tool/review.py` as a read-only dependency, not a file to edit.

- **Update only the granularity merge producer.** In `plan_tool/granularity.py:_merge_rec`, keep the human-readable action text, but append the canonical marker from `render_merge_action(MERGE_ACTION_MERGE, (lo_id, hi_id))`. One acceptable shape is the current sentence followed by the rendered marker, so operators still see plain advice and consumers can parse the directive.

- **Preserve ids.** Keep `_make_rec_id(lo_id, GRANULARITY_MERGE_SOURCE, f"merge:{key}:{lo_id}+{hi_id}")` unchanged in `plan_tool/granularity.py:_merge_rec`. The directive belongs only on `suggested_action`; do not fold it into the fingerprint, body, title, or source.

- **Import direction is allowed.** `plan_tool/granularity.py` already imports `Recommendation` and `_make_rec_id` from `plan_tool.review`, so importing `MERGE_ACTION_MERGE` and `render_merge_action` there does not add a new reverse dependency. Do not import `plan_tool.granularity` from `plan_tool/review.py`; `review.py` deliberately duplicates `_GRANULARITY_MERGE_SOURCE` to avoid that cycle.

- **Parse by marker, not prose.** `plan_tool/review.py:parse_merge_action` keys on the marker emitted by `render_merge_action`. Tests should not assert that downstream code can infer a directive from “Consider merging steps…” without the marker.

- **Keep the two producers distinct.** `plan_tool/review.py:_reground_already_built_recommendation` already appends `render_merge_action(MERGE_ACTION_REGROUND, step_ids)`. This step should not change re-ground behavior except for any tests that prove the shared grammar handles both `merge` and `reground`.

- **Do not make merge findings apply-eligible.** `granularity-merge` must remain outside `APPLY_ELIGIBLE_SOURCES` and `STRUCTURAL_SOURCES` in `plan_tool/review.py`. This step only makes the target recoverable for later bridge dispatch; it does not make the finding auto-apply.

## Tests

- `tests/test_granularity.py::test_merge_rec_carries_merge_directive` — A deterministic pairwise merge finding parses to `MergeAction(kind=MERGE_ACTION_MERGE, step_ids=(lo_id, hi_id))`.
- `tests/test_granularity.py::test_merge_directive_does_not_change_rec_id` — The finding id still equals the existing `_make_rec_id` fingerprint shape for the same merge pair.
- `tests/test_granularity.py::test_ids_are_stable` — Existing id stability still holds after adding the directive.
- `tests/test_review.py::TestMergeActionGrammar::test_render_parse_round_trip_for_merge` — The shared grammar renders and parses a `merge` marker, not only a `reground` marker.
- `tests/test_review.py::TestMergeActionGrammar::test_reground_directive_kind_is_reground_despite_merge_prose` — Existing guard stays green, proving prose containing “merge” does not override the marker kind.

### Test-creation order (feature step)

Add the grammar round-trip test in `tests/test_review.py` first, because it proves the existing helper accepts the `merge` kind this step will emit. Then add the `tests/test_granularity.py` tests around `_merge_rec` through `assess_granularity`, and implement the producer change. Every new test plus the existing granularity and review tests named above must be green before this step is considered finished.

## Acceptance criteria

- A deterministic adjacent-step merge finding from `plan_tool/granularity.py:assess_granularity` has `source == "granularity-merge"` and a `suggested_action` containing the canonical `→ merge steps: <lo>, <hi>` marker.
- `plan_tool/review.py:parse_merge_action` returns `MergeAction(kind=MERGE_ACTION_MERGE, step_ids=(lo_id, hi_id))` for that finding.
- The same finding keeps its previous id fingerprint shape from `_make_rec_id(lo_id, GRANULARITY_MERGE_SOURCE, f"merge:{key}:{lo_id}+{hi_id}")`.
- `plan_tool/review.py:_reground_already_built_recommendation` continues to parse as `MERGE_ACTION_REGROUND`.
- `pytest tests/test_granularity.py tests/test_review.py` passes.

## References

- [dataclasses — Data Classes](https://docs.python.org/3/library/dataclasses.html) — Read for the frozen `MergeAction` value object shape already used by the directive parser.
- [typing — Support for Type Hints](https://docs.python.org/3/library/typing.html) — Read for the existing typed helper signatures around `Optional`, iterables, and tuple payloads.

## Deferred

- `plan_tool/review_walk.py` dispatchability and action routing — later bridge steps should consume `parse_merge_action`; this step only makes deterministic merge findings carry the directive.
- `plan_tool/cli/review_actions.py` merge or re-ground actuator calls — later bridge steps should decide how parsed directives invoke `merge_bridge` or `reground_bridge`.
- `plan_tool/review.py` source membership changes — `granularity-merge` remains non-apply-eligible and non-structural in this step.
