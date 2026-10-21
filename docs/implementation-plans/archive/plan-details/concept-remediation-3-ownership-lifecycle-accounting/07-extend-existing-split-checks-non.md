# Step 7 — Extend split conservation to non-delivery links and exact previews

## Summary

Extend the split flow so it conserves both `Step.concept_ids` and the durable non-delivery records introduced by steps 2 and 3. `plan_tool/concept_tree.py` will provide the pure accounting transformation, while `plan_tool/create.py:_propose_step_split` and `plan_tool/detail.py:split_step` will reject incomplete or invented allocations. Dry-run results must expose the exact candidate ownership and non-delivery distribution produced by the same transformation used for a real split. On green, a split cannot leave a record pointing to a removed or renumbered step, and previewed accounting matches applied accounting exactly.

## Table of Contents

- [Summary](#summary) — Overview of the split-accounting change and its result.
- [Why](#why) — The remaining gaps in the current split checks and preview.
- [Input](#input) — Contracts supplied by dependency steps and existing split code.
- [Files (creates vs edits)](#files-creates-vs-edits) — Production and test files changed by this step.
- [Implementation](#implementation) — Required conservation, mapping, preview, and publication behavior.
- [Tests](#tests) — Focused split-accounting and dry-run cases.
- [Acceptance criteria](#acceptance-criteria) — Observable conditions required for completion.
- [References](#references) — Relevant model and test documentation.
- [Deferred](#deferred) — Related lifecycle work owned by later steps.

## Why

Delivery ownership is partly protected already: `plan_tool/create.py:_propose_step_split` compares the proposed concept-ID union with the source step, and `plan_tool/create.py:_apply_step_split` rejects dropped or invented IDs. The direct proposer test covers a dropped ID, but not an invented extra ID, and `tests/test_detail.py:TestSplitStepOnDemand.test_split_step_dry_run_preserves_concept_ids_without_writing` proves only that the plan file stays unchanged. More importantly, the split path does not yet apply the same conservation rule to step-linked non-delivery records, so a valid record can retain a source reference to a step that the split removed or renumbered. This step closes those gaps without making titles or generated prose an accounting authority.

## Input

- **Step 2 output:** Consume its durable non-delivery record as the only structured representation of deliberate non-delivery. Preserve its record identity, concept ID, disposition, evidence, approval state, and stable source/artifact fields; do not define another split-only record shape.
- **Step 3 output:** Consume its reviewed decision-transition rules. A split may remap a valid record, but it must not approve an unsigned record or preserve approval across a change that step 3 defines as requiring review.
- **Delivery ownership:** Treat `Step.concept_ids` as the exact many-owner link. A concept may appear on more than one replacement, but the replacement union must equal the source set.
- **Current split candidate:** Use the replacement steps produced by `plan_tool/create.py:_propose_step_split` or constructed by `plan_tool/detail.py:split_step`; do not infer allocation from replacement titles.
- **Current preview contract:** Preserve `plan_tool/detail.py:SplitResult.renumber` and `SplitResult.new_plan` for existing callers. Extend the result with structured accounting data rather than changing the tuple layout consumed by the CLI.
- **Verification limit:** Legacy concept sidecars with no step-2 non-delivery records have no structured links to remap. They must retain the current delivery-only behavior rather than receiving fabricated records.

## Files (creates vs edits)

**New files:**

- None.

**Existing files (edits only):**

- `plan_tool/concept_tree.py` — Add a pure split-accounting transformation and validation surface for durable non-delivery records.
- `plan_tool/create.py` — Complete proposal-side exact-ID validation and keep `_apply_step_split` as the delivery-conservation gate.
- `plan_tool/detail.py` — Apply the non-delivery transformation in `split_step`, expose the exact accounting candidate in `SplitResult`, and publish the plan and concept changes through the existing publication seam.
- `tests/test_create.py` — Add direct split-proposal coverage for invented IDs and retain the current dropped/shared-owner cases.
- `tests/test_detail.py` — Add non-delivery remapping, ambiguity, no-mutation, preview, and preview/apply parity coverage.

## Implementation

The foundational logic is **exact split accounting conservation: every source delivery or non-delivery link must map to a valid replacement or surviving step, with no dropped, invented, ambiguous, or dangling link**.

- **Keep delivery validation exact.** `plan_tool/create.py:_propose_step_split` must accept a proposal only when the union of replacement `concept_ids` equals the source step’s set. Retain many-owner behavior, where the same ID may appear on several replacements. Make both missing and extra IDs explicit rejection cases; do not silently remove an invented ID.

- **Keep `_apply_step_split` pure.** `plan_tool/create.py:_apply_step_split` should continue to transform a supplied step list without loading or saving a concept sidecar. Preserve its current graph, status, dependency, and non-mutation guarantees while retaining the final exact concept-ID check as defense in depth.

- **Transform non-delivery records in `plan_tool/concept_tree.py`.** Add a pure helper that receives the original accounting record, the source and replacement step accounting, and the exact old-to-new step mapping. It should return a validated candidate or a clear failure; persistence remains the caller’s job.

- **Preserve stable references when possible.** A non-delivery record whose source/artifact identity does not depend on a mutable step number should remain unchanged. Do not rewrite a stable artifact identity merely because nearby step IDs changed.

- **Remap mutable step references explicitly.** References to unaffected downstream steps must follow the same renumber map represented by `plan_tool/detail.py:_split_renumber_map`. A reference to the removed target must map only to replacement children supported by the structured allocation supplied to the split.

- **Reject ambiguous target links.** If a target-linked record cannot be assigned from exact structured data, stop before mutation. Do not choose a child by title similarity, title order, body text, or a “first/last child” convention. The caller must provide an explicit allocation or leave the split unapplied.

- **Conserve record identity and concept identity separately.** Remapping a record’s source reference must not change its durable record ID or concept ID. Reject replacement data that introduces a record or concept ID absent from the source candidate, drops a required record, duplicates an identity illegally under the step-2 contract, or points at a step absent from the candidate plan.

- **Preserve approval across routing-only transformation.** Remap the record’s ordered `linked_step_ids` to one or more replacement children and remap current `artifact_ref` when the detail path changes, while preserving `record_id`, immutable `origin_ref`, reviewed disposition/evidence, review state, and approval. Step 3 classifies these exact structural routing changes as non-reviewed fields. If the split changes disposition, evidence, origin, or another operator-reviewed field, return an unsigned candidate and require review instead of carrying approval forward.

- **Represent fan-out in one record.** A valid shared-child allocation updates one record’s duplicate-free `linked_step_ids` tuple; it does not clone the record. Preview and apply reject ambiguous allocations, empty required links, duplicate children, or child IDs outside the split mapping.

- **Remap artifact paths with the same transaction.** When downstream detail migration renames the referenced file, update current `artifact_ref` to the final repo-relative path in the prepared concept candidate. Publish the plan, concept record, and detail rename through one prerequisite transaction so no committed generation contains a dangling old path.

- **Prepare one candidate for preview and apply.** In `plan_tool/detail.py:split_step`, parse the plan and current `ConceptTree`, build `new_steps` through `_apply_step_split`, derive the renumber map, and prepare the transformed accounting candidate before any write, detail rename, or authoring call. The dry-run and real paths must branch only after this preparation succeeds.

- **Make previews structurally exact.** Extend `plan_tool/detail.py:SplitResult` with a structured accounting preview that contains each replacement’s exact `concept_ids` and the resulting non-delivery links or records. Preserve `new_plan` as the existing `(id, title, depends_on)` projection so callers that unpack it do not break.

- **Keep dry-run read-only.** `plan_tool/detail.py:split_step(dry_run=True)` must return the prepared step and accounting projections without calling `save_concepts`, `write_plan`, `_migrate_downstream_details_after_split`, or `generate_detail`.

- **Publish the prepared candidate, not a reconstruction.** On a real split, pass the already-validated plan and concept candidates through the publication contract supplied by the prerequisite work. Do not rerun the mapping after preview or after detail authoring; a second derivation could differ from the reviewed candidate.

- **Preserve existing split ordering.** Validate both candidates first, publish through the existing single-writer seam, then continue the established downstream detail migration and replacement-detail authoring flow around `plan_tool/detail.py:_migrate_downstream_details_after_split`. A validation or publication failure must leave the original plan, concept sidecar, and detail files unchanged.

- **Retain legacy behavior when no concept record exists.** `split_step` must still split a plan with no sidecar. In that case the accounting preview contains the exact replacement `concept_ids` and no non-delivery records.

## Tests

### Test-creation order (feature step)

1. `tests/test_create.py:test_propose_step_split_rejects_invented_concept_id` — proves an otherwise complete proposal containing one extra ID returns `None`.
2. `tests/test_create.py:test_apply_step_split_rejects_invented_concept_id_without_mutating_input` — pins defense-in-depth rejection and unchanged input steps.
3. `tests/test_detail.py:test_split_accounting_remaps_downstream_non_delivery_source` — proves a record linked to a renumbered surviving step receives the exact new step reference.
4. `tests/test_detail.py:test_split_accounting_maps_target_link_to_explicit_children` — proves a target-linked record maps only to the named replacement allocation, including a valid shared-child allocation.
5. `tests/test_detail.py:test_split_accounting_rejects_dropped_invented_and_dangling_links` — parametrizes malformed candidates and proves each is rejected.
6. `tests/test_detail.py:test_split_accounting_rejects_ambiguous_target_link_without_title_inference` — proves an unallocated target record cannot be assigned from replacement titles or order.
7. `tests/test_detail.py:test_split_step_dry_run_previews_exact_accounting_distribution` — asserts the returned replacement `concept_ids`, non-delivery links, and renumber map while all plan, sidecar, and detail bytes remain unchanged.
8. `tests/test_detail.py:test_split_step_apply_matches_dry_run_accounting_preview` — runs preview and apply from equivalent fixtures and compares the previewed accounting with the persisted result.
9. `tests/test_detail.py:test_split_step_without_concept_sidecar_retains_delivery_only_behavior` — preserves the current no-sidecar split path.
10. `tests/test_detail.py:test_split_validation_failure_writes_nothing` — proves an invalid accounting transformation stops before plan publication, sidecar publication, detail migration, or authoring.

Add these tests with the implementation. Every new test and the existing split suites in `tests/test_create.py` and `tests/test_detail.py` must be green before this step is finished.

## Acceptance criteria

- `plan_tool/create.py:_propose_step_split` rejects both a dropped source concept ID and an invented replacement concept ID.
- `plan_tool/create.py:_apply_step_split` continues to allow shared ownership while requiring exact set conservation.
- Splitting a step with durable non-delivery records leaves no mutable source reference pointing to the removed target or an old downstream step ID.
- A stable source/artifact reference remains unchanged when the split does not invalidate it.
- An ambiguous target-linked non-delivery record blocks the split before any write; no title or body matching chooses a replacement.
- `plan_tool/detail.py:SplitResult` exposes exact replacement ownership and non-delivery accounting without changing the existing `new_plan` tuple contract.
- `split_step(dry_run=True)` returns the same accounting candidate a corresponding real split persists and performs no writes, renames, authoring calls, or approval changes.
- A failed accounting validation or publication leaves the original plan, concept sidecar, and detail files unchanged.
- Plans without a concept sidecar retain the existing delivery-only split behavior.
- The focused split tests in `tests/test_create.py` and `tests/test_detail.py` pass.

## References

- [Pydantic Models](https://docs.pydantic.dev/latest/concepts/models/) — Review model copying and validation behavior used by the existing pure split candidate.
- [pytest: How to Parametrize Fixtures and Test Functions](https://docs.pytest.org/en/stable/how-to/parametrize.html) — Use for the dropped, invented, ambiguous, and dangling accounting test matrix.

## Deferred

- Merge accounting conservation — step 7 extends the existing ownership merge to the same durable non-delivery links.
- Detail regeneration publication timing — step 4 owns removal or replacement of accounting only after regenerated details are durable.
- Re-baseline and carved-seed restoration — steps 9 through 11 own machine-readable seed accounting and explicit create restoration review.
- CLI presentation of the added accounting preview — this step preserves the existing CLI-consumed `new_plan` shape; any expanded human-facing rendering requires a separately scoped edit to the CLI owner.
