# Step 8 — Extend merge conservation to non-delivery links

## Summary

Extend the existing ownership-preserving merge so it also conserves the structured non-delivery records supplied by steps 2 and 3. Add the shared, write-free remapping rule in `plan_tool/concept_tree.py` and apply it from `plan_tool/detail.py:merge_steps` alongside the existing step merge. Keep `plan_tool/create.py:_apply_step_merge` unchanged as the authority for delivery ownership and step renumbering. On green, a preview or applied merge maps every step-linked non-delivery record to the correct surviving step, removes equivalent duplicates, and leaves no record pointing to a folded-away step.

## Table of Contents

- [Summary](#summary) — The merge accounting result and affected modules.
- [Why](#why) — Why delivery-only merge conservation is incomplete.
- [Input](#input) — The upstream accounting contracts and existing merge map.
- [Files (creates vs edits)](#files-creates-vs-edits) — The four scoped files and their changes.
- [Implementation](#implementation) — The required remapping, deduplication, and publication rules.
- [Tests](#tests) — Focused coverage for direct, preview, and applied merges.
- [Acceptance criteria](#acceptance-criteria) — Observable completion requirements.
- [References](#references) — Model and test guidance relevant to the change.
- [Deferred](#deferred) — Related lifecycle work owned by other steps.

## Why

`plan_tool/create.py:_apply_step_merge` already preserves the ordered union of member `Step.concept_ids`, so the delivery half of merge accounting is complete. Structured non-delivery records can still identify a folded-away or renumbered step after `plan_tool/detail.py:merge_steps`, leaving a reviewed concept linked to the wrong source even though its delivery ownership survived. This step completes the merge conservation rule by applying the same old-to-new step mapping to non-delivery links and by removing only records that become equivalent after the fold.

## Input

- **Step 2 output:** consume the durable non-delivery record and its stable identity/link contract from `plan_tool/concept_tree.py`. Do not recreate the record shape or store replacement links in `ConceptNode.source_metadata`.
- **Step 3 output:** preserve the review and decision-transition rules for approved, unsigned, replaced, and conflicting records. A merge remaps existing accounting; it does not approve or change a concept decision.
- **Delivery ownership:** `plan_tool/create.py:_apply_step_merge` remains the source for the merged survivor’s `concept_ids`, dependencies, status, and step renumbering.
- **Merge orchestration:** `plan_tool/detail.py:merge_steps` uses the shared transform for both `dry_run=True` and applied merges. Its `MergeResult.renumber` describes the old-to-new step mapping exposed by previews.
- **Link limits:** remap only fields that the step-2 contract defines as step references. Stable artifact references and unrelated provenance remain unchanged.

## Files (creates vs edits)

- **New files:**

  - None.

- **Existing files (edits only):**

  - `plan_tool/concept_tree.py` — extend the shared accounting transformation with deterministic merge remapping and equivalent-record deduplication.
  - `plan_tool/detail.py` — have `merge_steps` prepare and validate the remapped concept accounting from the same merge mapping used for the plan, then include it in the existing publication boundary for an applied merge.
  - `tests/test_create.py` — strengthen `TestApplyStepMerge` regression coverage showing the existing delivery-owner union remains unchanged and supplies the survivor mapping used by accounting.
  - `tests/test_detail.py` — add direct preview and applied-merge coverage for non-delivery remapping, deduplication, shared ownership, and failure-before-write behavior.

## Implementation

The foundational logic is: **map every step-linked non-delivery record through the merge’s old-to-new step map, then deduplicate records that become equivalent without changing their reviewed meaning.**

- **Extend the shared accounting helper.** Build on the write-free preparation API delivered by steps 1–3 in `plan_tool/concept_tree.py`. It should accept the current accounting state and the completed old-to-new mapping, return a fresh candidate, and perform no persistence.

- **Use the existing merge map.** Derive one mapping for all original steps: every folded member maps to `min(merge_ids)`, earlier steps keep their IDs, and later steps shift down by the number of removed members. Keep this consistent with `plan_tool/create.py:_apply_step_merge` and `plan_tool/detail.py:merge_steps`; do not add a second independent renumber algorithm that can drift.

- **Remap all step-linked non-delivery records.** A record linked to any folded member must identify the merged survivor afterward. A record linked to an unaffected step must follow that step’s renumbered ID. No applied candidate may retain an ID absent from the merged plan.

- **Preserve reviewed identity while remapping routing.** Keep the concept ID, record ID, immutable `origin_ref`, disposition, rationale or evidence, review state, approval data, and unrelated provenance unchanged. Replace merged members in `linked_step_ids` with the surviving step, deduplicate in deterministic order, and update current `artifact_ref` when detail migration renames the referenced file. These routing-only changes do not invalidate approval under step 3.

- **Deduplicate by the step-2 contract.** When records become equivalent because several member links collapse to one survivor, keep one deterministic record in the existing accounting order. Do not merge records that differ in reviewed meaning or provenance merely because they now share a step ID; let the step-3 validation contract reject a contradictory result.

- **Preserve many-owner semantics.** A concept may retain a committed owner outside the merge, gain the merged survivor as an owner, or have non-delivery accounting linked to the survivor. Apply the upstream contradiction rules without assuming one exclusive owner.

- **Prepare before mutation.** In `plan_tool/detail.py:merge_steps`, compute and validate the merged plan and accounting candidate before renaming details or publishing live artifacts. Invalid, dangling, or conflicting accounting must raise the merge’s normal domain error before any plan, detail, or concept artifact changes.

- **Keep preview and apply aligned.** The dry-run path must execute the same pure accounting preparation and validation as the real path, while writing nothing. An applied merge must submit the prepared plan and concept state through the publication boundary available at implementation time; do not repair the sidecar afterward with a separate direct `save_concepts` call.

- **Keep delivery ownership single-sourced.** Do not edit or duplicate `plan_tool/create.py:_apply_step_merge` in production. `plan_tool/detail.py:merge_steps` should continue receiving the survivor’s ordered, deduplicated `concept_ids` from that transform.

- **Preserve callers.** `plan_tool/cli/authoring.py:cmd_merge` and `plan_tool/cli/review_actions.py:_dispatch_merge_remedy` should inherit the behavior through `plan_tool/detail.py:merge_steps` without new accounting logic or file changes.

- **Leave unrelated merge behavior unchanged.** Keep the rules in `plan_tool/detail.py:_merge_is_safe`, downstream detail migration in `plan_tool/detail.py:_migrate_downstream_details_after_merge`, mixed-scope rejection, detail re-authoring, and archive handling intact.

## Tests

- `tests/test_create.py:TestApplyStepMerge.test_unions_member_concept_ids` — the existing delivery-owner union still places every member concept on the survivor.
- `tests/test_create.py:TestApplyStepMerge.test_deduplicates_overlapping_concept_ids_in_first_seen_order` — delivery ownership remains ordered and unique while member IDs collapse.
- `tests/test_detail.py:test_merge_accounting_maps_each_folded_member_to_survivor` — non-delivery links from different folded members identify the merged step.
- `tests/test_detail.py:test_merge_accounting_renumbers_unaffected_links` — links after the folded region follow the same downward renumbering as their steps.
- `tests/test_detail.py:test_merge_accounting_deduplicates_equivalent_records` — equivalent records created by the fold produce one deterministic retained record.
- `tests/test_detail.py:test_merge_accounting_preserves_distinct_reviewed_records` — records with different reviewed meaning or provenance are not silently combined.
- `tests/test_detail.py:test_merge_accounting_remaps_current_artifact_reference` — immutable origin and approval remain unchanged while the current path follows the transactionally renamed detail.
- `tests/test_detail.py:test_merge_with_shared_delivery_owner_preserves_all_accounting` — many-owner delivery and valid non-delivery data survive without imposing exclusive ownership.
- `tests/test_detail.py:test_merge_dry_run_validates_accounting_without_writes` — preview uses the real transformation while plan, details, and concept state remain unchanged.
- `tests/test_detail.py:test_merge_invalid_accounting_fails_before_writes` — dangling or contradictory prepared accounting leaves every live artifact unchanged.
- `tests/test_detail.py:test_applied_merge_publishes_plan_and_remapped_accounting_together` — the durable plan and concept record agree on the survivor and contain no folded-away step links.

### Test-creation order (feature step)

1. Add pure accounting-remap tests for folded members, downstream renumbering, unchanged links, and equivalent-record deduplication with the `plan_tool/concept_tree.py` change.
2. Add conflict, stable-reference, and many-owner cases to pin the step-2 and step-3 contracts.
3. Add dry-run and applied `merge_steps` tests, including failure before any write.
4. Run the existing `TestApplyStepMerge` and `TestMergeSteps` cases to prove delivery ownership, graph rewiring, scope checks, detail migration, and re-authoring remain unchanged.

Every new test and the existing focused merge suites must be green before this step is considered finished.

## Acceptance criteria

- Every non-delivery link to a folded member identifies the merged survivor after an applied merge.
- Every non-delivery link to a renumbered non-member identifies that step’s new ID.
- No applied concept record contains a link to a step removed by the merge.
- Equivalent records created by the fold are retained once in deterministic order.
- Records with different reviewed meaning or provenance are not silently coalesced.
- Concept IDs, record IDs, immutable origins, dispositions, review state, rationale or evidence, approval data, and unrelated provenance remain unchanged; routing links and current artifact paths match the final merged generation.
- `plan_tool/create.py:_apply_step_merge` continues to supply the survivor’s ordered, deduplicated delivery ownership without production changes.
- Dry-run and applied merges use the same accounting transformation, while dry-run changes no files.
- Invalid or contradictory merged accounting fails before any plan, detail, or concept artifact is changed.
- The persisted plan and concept record agree after a successful merge, and all focused tests in `tests/test_create.py` and `tests/test_detail.py` pass.

## References

- [Pydantic Models](https://docs.pydantic.dev/latest/concepts/models/) — Use the model copying, validation, defaults, and serialization rules when producing a fresh accounting candidate.
- [JSON Schema Validation Draft 2020-12](https://json-schema.org/draft/2020-12/json-schema-validation) — See the uniqueness and conditional-validation rules relevant to structured non-delivery records.
- [pytest: How to Parametrize Fixtures and Test Functions](https://docs.pytest.org/en/stable/how-to/parametrize.html) — Use parametrization for the folded-member, downstream, unchanged, duplicate, and invalid-link matrix.

## Deferred

- **Defining or migrating the durable non-delivery schema** — step 2 owns the record shape, identity, defaults, and persisted validation.
- **Changing approval or concept decisions during merge** — step 3 owns explicit review and decision transitions; merge only conserves existing reviewed data.
- **Split link distribution** — step 6 owns mapping one source step to several replacements and its exact preview checks.
- **Scope-out non-delivery publication** — step 8 owns conversion of final-owner loss into reviewed structured accounting.
- **Lifecycle-wide integration coverage** — step 12 exercises merge together with create, split, re-ground, scope-out, regeneration, and completeness.
