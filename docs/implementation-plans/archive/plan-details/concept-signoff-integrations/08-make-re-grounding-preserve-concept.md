> **Auto-archived**: this plan was swept on 2026-07-16 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 8 — Make re-grounding preserve concept ownership

## Summary

Make `plan_tool/reground.py` preserve each step’s explicit `concept_ids` through both re-ground dispositions. The mark-done path must change lifecycle state without changing ownership, while `render_rebaseline_seed` must carry the exact ownership of flagged, remaining, and deferred steps into the re-planning input. Keep ownership attached to its source step rather than combining or inferring IDs. Add focused coverage in `tests/test_reground.py`; on green, re-grounding cannot silently remove or invent a signed-off concept link.

## Table of Contents

- [Summary](#summary) — Overview of ownership preservation during re-grounding.
- [Why](#why) — Why status changes and re-baseline seeds must retain explicit links.
- [Input](#input) — Ownership and completeness contracts supplied by earlier steps.
- [Files (creates vs edits)](#files-creates-vs-edits) — The two existing files changed by this step.
- [Implementation](#implementation) — Required conservation rules for mark-done and re-baseline paths.
- [Tests](#tests) — Unit and persisted-plan cases for ownership preservation.
- [Acceptance criteria](#acceptance-criteria) — Observable conditions for completion.
- [References](#references) — Identifier-array validation semantics.
- [Deferred](#deferred) — Related ownership transitions owned by other steps.

## Why

Step 5 makes an exact concept ID on a committed step the authoritative ownership link for completeness. `plan_tool/reground.py:mark_steps_done` currently changes step status in place, while `plan_tool/reground.py:render_rebaseline_seed` reduces each step to its title, files, and change type. Without an explicit conservation rule, a future actuator change could replace a step and lose its IDs, and a re-baseline seed could send the next create pass enough prose to rebuild scope but not enough metadata to keep the signed-off ownership mapping.

## Input

- **Step 1 — explicit ownership:** step 1 adds `plan_tool/schema.py:Step.concept_ids` as the persisted list of stable concept IDs owned by a step.
- **Step 5 — explicit-link completeness:** step 5 counts exact ownership on committed steps and structured deferrals. Re-grounding must preserve those links without inferring ownership from titles, features, files, or seed prose.
- **Existing actuator contract:** `plan_tool/reground.py:mark_steps_done` mutates the existing `Step` objects, preserves IDs and ordering, and re-establishes the current-step cursor once after all requested steps are marked.
- **Existing bridge contract:** `plan_tool/reground.py:reground_bridge` reparses the plan, applies its existence, scope, no-op, opt-in, and confirmation gates, then calls `mark_steps_done` and `plan_tool.parser.write_plan`.
- **Existing re-baseline contract:** `plan_tool/reground.py:render_rebaseline_seed` renders flagged steps under `Done-context`, remaining committed steps under `Scope to re-plan`, and parked steps under `Deferred (parked)` before `reground_bridge` writes that seed.

## Files (creates vs edits)

- **New files:**

  - None.

- **Existing files (edits only):**

  - `plan_tool/reground.py` — make concept ownership an explicit invariant of `mark_steps_done` and include each source step’s ownership in the re-baseline seed.
  - `tests/test_reground.py` — extend step fixtures and add actuator, bridge, renderer, and refusal-path tests for exact ownership preservation.

## Implementation

- **Use exact per-step conservation as the foundational rule.** For every source step processed by re-grounding, the resulting plan step or seed entry must carry the same ordered `concept_ids` list. Re-grounding must not drop IDs, add IDs, sort them, or union ownership across separate steps.

- **Keep mark-done limited to lifecycle state.** `plan_tool/reground.py:mark_steps_done` should continue mutating the existing objects returned by `Plan.step_by_id`. Marking a step `DONE`, promoting the next runnable step to `CURRENT`, or setting the plan to `PlanStatus.COMPLETED` must leave `Step.concept_ids` unchanged on every step, including already-done steps and steps outside `step_ids`.

- **Do not add an ownership rewrite to the bridge.** `plan_tool/reground.py:reground_bridge` should rely on the parsed plan’s existing ownership and the actuator’s conservation rule. Its apply path may change status and write the plan, but it must not reassign ownership from the concept record, infer it from other step fields, or merge the flagged steps’ IDs.

- **Carry ownership into re-baseline input.** Extend the step representation used by `plan_tool/reground.py:render_rebaseline_seed`, likely through `_rebaseline_step_bullet` or a nearby renderer helper, so each step with concept ownership names its exact IDs in a clear machine-readable or unambiguous authored form. The same representation must be used in `_rebaseline_done_context_block`, `_rebaseline_scope_block`, and `_rebaseline_deferred_block`.

- **Keep ownership attached to its source entry.** A flagged step’s IDs belong with that step in `Done-context`; an unbuilt committed step’s IDs belong with it in `Scope to re-plan`; and a parked step’s IDs belong with it in `Deferred (parked)`. Do not emit one plan-wide union because that loses the owner mapping needed by the create integration from step 3.

- **Keep legacy seeds concise.** A step with `concept_ids == []` does not need a fabricated placeholder or ownership claim. Preserve the existing title, file, change-type, section, and provenance content around the optional ownership annotation.

- **Preserve gate behavior.** The `step-missing`, `unsafe`, `noop`, and `recommended` branches of `plan_tool/reground.py:reground_bridge` must remain non-mutating. Re-baseline must still write its seed before the plan update, and mark-done must still write no seed.

- **Reject inference as the main alternative.** Do not reconstruct ownership from concept titles, `Step.features`, file names, or the re-baseline prose. Step 5 deliberately defines completeness through explicit links, so re-grounding must carry the stored identifiers themselves.

- **Keep the leaf boundary unchanged.** Ownership preservation needs no import from `plan_tool.detail`, `plan_tool.launcher`, or `plan_tool.scope_out`. Continue using the existing `Step` data already available in `plan_tool/reground.py`.

## Tests

- `test_mark_steps_done_preserves_concept_ids` — marking one or more owned steps done leaves each ordered ownership list unchanged.
- `test_cursor_promotion_preserves_all_concept_ids` — marking the current step and promoting the next runnable step changes only lifecycle fields.
- `test_bridge_round_trip_preserves_concept_ids` — an applied mark-done re-ground retains ownership after `parse_plan` reads the rewritten plan.
- `test_bridge_preserves_ownership_when_plan_completes` — completing the plan does not remove ownership from the final marked step.
- `test_recommended_reground_leaves_owned_plan_unchanged` — a declined or disabled apply path leaves the persisted ownership unchanged.
- `test_rebaseline_seed_carries_flagged_step_concept_ids` — `Done-context` includes the exact IDs owned by each flagged step.
- `test_rebaseline_seed_carries_remaining_step_concept_ids` — `Scope to re-plan` keeps ownership attached to each remaining committed step.
- `test_rebaseline_seed_carries_deferred_step_concept_ids` — `Deferred (parked)` keeps ownership attached to each parked step.
- `test_rebaseline_seed_does_not_union_concept_ids` — IDs shared or split across source steps remain represented per step without invented ownership.
- `test_rebaseline_seed_omits_empty_concept_ownership` — a legacy step with no IDs retains the existing concise seed representation.

### Test-creation order (feature step)

Add the actuator and persisted round-trip tests with the lifecycle change, then add the three section-specific renderer tests and the no-union and empty-list cases with the seed change. Run the existing gate-matrix and re-baseline tests after each change to catch mutations to refusal behavior or seed ordering. Every new test and all existing tests in `tests/test_reground.py` must be green before this step is finished.

## Acceptance criteria

- `plan_tool/reground.py:mark_steps_done` leaves every step’s ordered `concept_ids` unchanged while marking requested steps done and updating the cursor or plan status.
- An applied `plan_tool/reground.py:reground_bridge` mark-done operation preserves ownership after the plan is written and parsed again.
- `plan_tool/reground.py:render_rebaseline_seed` carries the exact concept IDs for owned steps in `Done-context`, `Scope to re-plan`, and `Deferred (parked)`.
- Re-baseline output keeps concept IDs attached to their original step entries and never replaces them with a plan-wide union.
- Empty ownership remains valid and does not require a placeholder in the seed.
- Missing-step, unsafe, no-op, declined, and recommend-only outcomes remain non-mutating.
- All tests in `tests/test_reground.py` pass.

## References

- [JSON Schema Validation: A Vocabulary for Structural Validation of JSON](https://json-schema.org/draft/2020-12/json-schema-validation) — Use the array and uniqueness semantics as background for preserving validated concept-ID lists without changing their membership.

## Deferred

- **Create-time interpretation of re-baseline ownership** — step 3 owns assignment and review of concept IDs during create; this step only makes the source seed retain the mapping.
- **Split ownership distribution** — step 6 enforces conservation across replacement steps.
- **Merge ownership union** — step 7 derives the merged survivor’s ownership from its members.
- **Scope-out ownership transitions** — step 9 records a structured deferral when no committed owner survives.
