> **Auto-archived**: this plan was swept on 2026-07-16 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 7 — Make merge remedies union concept ownership

## Summary

Make the shared merge transform preserve every concept owned by the steps it folds. Update `plan_tool/create.py:_apply_step_merge` so the merged survivor receives the ordered, deduplicated union of the member steps’ `concept_ids`, regardless of the placeholder value supplied on the caller-built `Step`. Keep `plan_tool/detail.py:merge_steps` on that shared transform and make concept ownership visible in its merge tests. On green, dry-run, direct-transform, and applied merge paths cannot drop or invent concept ownership.

## Table of Contents

- [Summary](#summary) — The ownership-preserving merge result.
- [Why](#why) — Why merges must keep explicit completeness links.
- [Input](#input) — The ownership and completeness contracts this step consumes.
- [Files (creates vs edits)](#files-creates-vs-edits) — The four existing files changed by this step.
- [Implementation](#implementation) — The union rule and where to enforce it.
- [Tests](#tests) — Unit and integration coverage for merged ownership.
- [Acceptance criteria](#acceptance-criteria) — Observable requirements for completion.
- [References](#references) — Validation semantics relevant to identifier lists.
- [Deferred](#deferred) — Related concept-state work owned elsewhere.

## Why

Step 5 makes `Step.concept_ids` and structured deferrals the only valid links from signed-off concepts to planned work. A merge currently combines files, features, gates, dependencies, and lifecycle state, but a caller-built merged `Step` can omit the folded members’ concept ownership. That would turn a structurally valid remedy into a new completeness failure, so concept ownership must be part of the merge transform’s required state rather than optional caller-supplied content.

## Input

- **Step 1 — explicit ownership:** step 1 supplies `plan_tool/schema.py:Step.concept_ids`, with uniqueness within one step and permission for the same ID to appear on several steps.
- **Step 5 — explicit-link completeness:** step 5 treats a concept ID on a committed step as authoritative coverage. A merge must keep those exact IDs on its survivor.
- **Shared merge transform:** `plan_tool/create.py:_apply_step_merge` owns fields that must be derived from the folded members, including the survivor ID, external dependencies, and status.
- **Merge orchestrator:** `plan_tool/detail.py:merge_steps` assembles combined authored fields, calls `plan_tool.create._apply_step_merge`, and uses the result for both dry-run previews and persisted merges.
- **Union rule:** the merged survivor must contain every distinct concept ID found on any folded member and no concept ID found only on the caller-built placeholder. Preserve deterministic first-seen order by member order and each member’s authored list order.

## Files (creates vs edits)

- **New files:**

  - None.

- **Existing files (edits only):**

  - `plan_tool/create.py` — make `_apply_step_merge` derive and assign the folded members’ concept-ID union.
  - `plan_tool/detail.py` — keep `merge_steps` aligned with the transform-owned ownership rule and update its merge contract where combined fields are described.
  - `tests/test_create.py` — add direct tests for union, deduplication, empty ownership, and rejection of caller-invented ownership.
  - `tests/test_detail.py` — add dry-run and persisted-merge tests proving ownership survives the full merge remedy.

## Implementation

- **Make concept union the foundational rule.** In `plan_tool/create.py:_apply_step_merge`, derive the survivor’s `concept_ids` from the original steps whose IDs are in `merge_ids`. The result must be the set union, represented as a deterministic list with duplicates removed.

- **Preserve stable order.** Walk merge members in their plan order, then each member’s `concept_ids` in authored order. Keep the first occurrence of each ID. Do not sort IDs, because sorting would rewrite valid authored ordering without improving the conservation rule.

- **Let the transform own the field.** Apply the derived union in the same `merged.model_copy(update=...)` operation that assigns the survivor’s `id`, `depends_on`, and `status`. Do not trust `merged.concept_ids`: the transform has the original members and is the only shared point that can guarantee every caller preserves ownership.

- **Ignore placeholder-only IDs.** A concept ID present on the caller-built `merged` step but absent from every folded member must not appear in the result. This keeps a structural remedy from inventing ownership without a concept review decision.

- **Keep the transform pure.** `plan_tool/create.py:_apply_step_merge` must continue returning fresh models without mutating the input steps or the caller-built `merged` object. Ownership derivation must happen before the dry-run `Plan` validation so the validated output is the same shape later returned or written.

- **Use one rule for every merge path.** `plan_tool/detail.py:merge_steps` must continue routing both `dry_run=True` and real merges through `plan_tool.create._apply_step_merge`. Do not add a second ownership merge after the transform or only in the write path; that would let previews and persisted results disagree.

- **Keep combined-step assembly readable.** Update the combined-field description around `plan_tool/detail.py:merge_steps` and its construction of `merged = Step(...)` to state that concept ownership is transform-derived. The placeholder may use the field’s default; it must not be treated as the source of ownership.

- **Leave other merge behavior unchanged.** Contiguous and dependency-connected membership, mixed-scope rejection, run-state safety, dependency rewiring, status inheritance, downstream detail migration, and re-authoring order remain governed by `plan_tool/create.py:_apply_step_merge`, `plan_tool/detail.py:_merge_is_safe`, and `plan_tool/detail.py:merge_steps`.

## Tests

- `tests/test_create.py:TestApplyStepMerge.test_unions_member_concept_ids` — distinct concept IDs from all folded members appear on the survivor.
- `tests/test_create.py:TestApplyStepMerge.test_deduplicates_overlapping_concept_ids_in_first_seen_order` — shared ownership appears once and keeps deterministic member/list order.
- `tests/test_create.py:TestApplyStepMerge.test_empty_member_ownership_produces_empty_union` — merging members without ownership leaves the survivor unowned.
- `tests/test_create.py:TestApplyStepMerge.test_ignores_concept_ids_supplied_only_by_merged_placeholder` — the caller-built step cannot introduce ownership absent from the members.
- `tests/test_create.py:TestApplyStepMerge.test_concept_union_does_not_mutate_inputs` — member steps and the caller-built merged step remain unchanged.
- `tests/test_detail.py:TestMergeSteps.test_dry_run_unions_concept_ownership_without_writes` — the dry-run plan preview contains the same union and leaves disk unchanged.
- `tests/test_detail.py:TestMergeSteps.test_persisted_merge_preserves_all_member_concept_ids` — parsing the written plan shows every folded member’s concept ID on the survivor.
- `tests/test_detail.py:TestMergeSteps.test_persisted_merge_deduplicates_shared_concept_ownership` — overlapping ownership remains valid under `Step`’s within-step uniqueness rule.

### Test-creation order (feature step)

1. Add the direct `_apply_step_merge` union and placeholder-rejection tests with the transform change.
2. Add overlap, empty-input, ordering, and no-mutation cases to pin the full invariant.
3. Add dry-run and persisted `merge_steps` coverage so both orchestration paths prove they use the shared rule.
4. Run the existing merge suites in `tests/test_create.py` and `tests/test_detail.py` to confirm dependency, status, scope, migration, and re-authoring behavior remains unchanged.

Every new test and the existing merge tests must be green before this step is considered finished.

## Acceptance criteria

- `_apply_step_merge` returns a survivor whose `concept_ids` equal the ordered set union of all folded members’ `concept_ids`.
- A concept ID owned by more than one folded member appears only once on the survivor.
- A concept ID supplied only on the caller-built merged `Step` does not appear in the result.
- Members with no concept ownership merge to a survivor with `concept_ids == []`.
- Dry-run and real `merge_steps` calls produce the same concept ownership for the survivor.
- A persisted merge remains covered under step 5’s explicit-link completeness rule for every concept covered by any folded member before the merge.
- Existing merge graph, safety, scope, renumbering, detail migration, and re-authoring tests remain green.

## References

- [JSON Schema Validation: A Vocabulary for Structural Validation of JSON](https://json-schema.org/draft/2020-12/json-schema-validation) — See the array and uniqueness rules that support a deduplicated persisted concept-ID list.

## Deferred

- **Changing concept review or sign-off state during a merge** — a merge only transfers existing ownership; concept decisions remain owned by the shipped concept-record review contract.
- **Reassigning concepts among several survivors** — a merge has one survivor, while distribution across several replacement steps belongs to step 6’s split-conservation work.
- **Changing structured detail deferrals after a merge** — step 4 owns deferral validation and regeneration; this step changes only `Step.concept_ids`.
