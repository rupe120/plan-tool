> **Auto-archived**: this plan was swept on 2026-07-16 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 9 — Make scope-out defer concepts with no surviving owner

## Summary

Update `plan_tool/scope_out.py` so an applied carve changes each removed step’s concept commitments deliberately: keep concepts covered when a committed survivor still owns them, and mark them `defer` when no committed owner survives. Carry the carved steps’ exact `concept_ids` into both single-step and region forward-seeds so later re-planning can restore ownership without guessing from prose. Extend `tests/test_scope_out.py` and `tests/cli/test_scope_out_cmd.py` to cover shared ownership, ownerless deferral, dry-run and refusal behavior, region carves, and failure rollback. On green, scope-out cannot turn an explicitly covered concept into an unexplained completeness gap.

## Table of Contents

- [Summary](#summary) — Overview of concept handling during scope-out.
- [Why](#why) — Why dropping an owner must produce a recorded concept decision.
- [Input](#input) — Ownership, completeness, and concept-record contracts consumed by this step.
- [Files (creates vs edits)](#files-creates-vs-edits) — The three existing files changed by this step.
- [Implementation](#implementation) — Owner-survival predicate, seed rendering, persistence, and failure rules.
- [Tests](#tests) — Unit and CLI cases for concept-aware scope-out.
- [Acceptance criteria](#acceptance-criteria) — Observable requirements for completion.
- [References](#references) — Validation and safe-publication references.
- [Deferred](#deferred) — Related concept changes owned elsewhere.

## Why

`plan_tool/scope_out.py:compute_narrow` removes carved steps and preserves the remaining plan graph, but it has no concept-aware disposition for ownership links removed with those steps. After steps 1 and 5 make `Step.concept_ids` the explicit completeness link, a carve could leave a signed-off included concept with no committed owner and no structured explanation. Scope-out must therefore use one deterministic rule: if a concept owned by the carved region has no committed surviving owner, record it as deferred; otherwise leave its concept decision unchanged.

## Input

- **Step 1 — explicit ownership:** step 1 supplies `plan_tool/schema.py:Step.concept_ids`. Exact IDs are authoritative; titles, feature tags, files, and detail prose are not alternate ownership signals.
- **Step 5 — explicit-link completeness:** step 5 defines coverage in terms of a valid committed owner or structured deferral. The narrowed plan and updated concept record must satisfy that same rule immediately after a successful carve.
- **Shipped concept-record core:** use the landed public read, decision-update, synchronization, and save contracts from the execution prerequisite. Confirm their names and signatures at implementation time; do not recreate concept dataclasses, state validation, fingerprint checks, or sidecar serialization in `plan_tool/scope_out.py`.
- **Scope-out preview:** `plan_tool/scope_out.py:NarrowPreview.new_steps` and `NarrowPreview.narrowed_plan` contain the post-carve survivors after renumbering. Determine surviving ownership from that result, not from the source plan with carved steps manually filtered a second time.
- **Apply ordering:** `plan_tool/scope_out.py:scope_out_step` currently reparses, computes blockers, checks opt-in and confirmation, writes the forward-seed, then calls `apply_narrow`. Concept changes must obey the same recommend-only and refusal gates.

## Files (creates vs edits)

- **New files:**

  - None.

- **Existing files (edits only):**

  - `plan_tool/scope_out.py` — render concept IDs in carved seeds, compute which carved concepts lose every committed owner, update those concepts through the shipped concept-record contract, and keep concept publication aligned with narrow failure handling.
  - `tests/test_scope_out.py` — add focused renderer, preview, orchestrator, persistence, no-write, shared-owner, and rollback tests.
  - `tests/cli/test_scope_out_cmd.py` — prove single-step and `--through` applies defer only concepts whose last committed owner is carved.

## Implementation

The foundational logic is: **defer each concept owned by the carved region only when no committed step in the narrowed plan still owns that exact ID**.

- **Use exact identifier membership.** Start from the ordered, deduplicated union of `concept_ids` on the carved steps selected by `scope_out_step`. For each ID, inspect `NarrowPreview.new_steps` or `NarrowPreview.narrowed_plan.steps`; keep the concept unchanged if any surviving step has that ID and `scope is StepScope.COMMITTED`.

- **Ignore parked survivors as active owners.** A `deferred` or `wont_do` survivor does not prevent the concept from becoming ownerless under step 5’s completeness rule. Do not treat matching titles, `Step.features`, files, or detail text as ownership.

- **Change only concepts that lose their last owner.** Apply `defer` through the shipped concept-record decision API. Preserve the node’s stable ID, hierarchy, source links, rationale, and unrelated review state according to that API. Concepts still owned by a committed survivor and concepts not owned by the carved region must remain unchanged.

- **Keep the operation deterministic.** Scope-out needs no model call and no new `invoker=` seam. The owner-survival predicate depends only on carved `Step.concept_ids`, the narrowed survivors, and the loaded concept record.

- **Carry ownership into the forward-seed.** Extend `plan_tool/scope_out.py:_scope_block`, which is shared by `render_carved_seed` and `render_carved_region_seed`, with a clear concept-ID list for each carved step. Preserve each step’s authored order and keep IDs attached to their source step; do not combine region ownership into one anonymous list. Omit the block when `concept_ids` is empty.

- **Treat the seed as re-planning evidence, not live ownership.** The seed should tell the later `create --from-existing` flow which stable IDs the carved work owned, while the source plan no longer claims those IDs after narrowing. Do not infer successor assignment inside scope-out.

- **Calculate concept effects before writes.** After `compute_narrow` returns a safe preview and before the seed is published, load and validate the concept record through the shipped core and prepare the updated record in memory. This keeps stale, malformed, or unknown concept IDs from being discovered after the plan has already narrowed.

- **Keep legacy plans working.** A plan with no concept record and no carved `concept_ids` should follow the existing scope-out path unchanged. If carved ownership is present but the required concept record cannot be safely loaded or an owned ID is absent from it, refuse mutation through an existing blocker or typed `NarrowError` path that the current CLI can report without inventing a new result vocabulary. Do not silently drop the required deferral.

- **Honor every existing no-write gate.** A blocked preview, `allow_scope_out=False`, non-TTY decline, or rejected confirmation must not change the plan, details, seed directory, or concept record. Preparing an in-memory concept update before confirmation is acceptable; saving it is not.

- **Keep seed-first recovery useful.** `plan_tool/scope_out.py:scope_out_step` intentionally writes the seed before narrowing so the carved work survives a later apply failure. Preserve that property. If plan or concept publication fails after the seed write, the seed may remain, but the plan, detail layout, and concept record must return to their pre-carve state.

- **Extend the apply boundary rather than adding a second uncoordinated writer.** One likely approach is to let `apply_narrow` receive the validated concept update or a narrow-owned callback and include the previous sidecar state in its rollback work. The exact shape may follow the landed concept persistence API, but callers must not be able to commit the narrowed plan while leaving the old included-and-ownerless concept state behind.

- **Preserve stale-preview checks.** `apply_narrow` must continue rejecting a changed plan frontmatter before mutation. Apply the concept core’s equivalent stale or fingerprint validation before replacing its record, and ensure the saved record is synchronized to the final narrowed plan state as required by the shipped core.

- **Avoid a second owner-survival implementation.** Seed rendering may display the original per-step IDs, but only one helper in `plan_tool/scope_out.py` should decide which IDs become deferred. Use that result for preview, apply, and tests so single-step and region carves cannot disagree.

- **Keep existing graph behavior unchanged.** Concept handling must not alter renumbering, dependency repair, feature pruning, cursor selection, detail migration, archive ordering, or `ScopeOutResult` outcomes except where a concept-record safety failure requires refusing the carve.

## Tests

- `tests/test_scope_out.py:test_scope_block_renders_concept_ids_in_authored_order` — a single carved step’s seed lists its exact concept ownership.
- `tests/test_scope_out.py:test_scope_block_omits_empty_concept_ids` — legacy steps do not gain an empty ownership section.
- `tests/test_scope_out.py:test_region_seed_keeps_concept_ids_attached_to_source_steps` — a multi-step seed does not merge or reassign ownership.
- `tests/test_scope_out.py:test_ownerless_carved_concept_is_selected_for_deferral` — an ID owned only by the carved step is marked for `defer`.
- `tests/test_scope_out.py:test_shared_surviving_owner_prevents_deferral` — the same ID on a committed survivor keeps its existing concept decision.
- `tests/test_scope_out.py:test_parked_surviving_owner_does_not_prevent_deferral` — ownership on a non-committed survivor does not count as active coverage.
- `tests/test_scope_out.py:test_region_carve_deduplicates_ownerless_concept_ids` — the same ID on several carved steps is deferred once.
- `tests/test_scope_out.py:test_region_carve_preserves_concept_with_owner_outside_region` — an owner outside `N..M` keeps the concept unchanged.
- `tests/test_scope_out.py:test_scope_out_changes_only_ownerless_carved_concepts` — unrelated nodes and still-owned carved concepts remain equal to their input values.
- `tests/test_scope_out.py:test_recommend_only_does_not_save_concept_record` — `allow_scope_out=False` leaves every artifact unchanged.
- `tests/test_scope_out.py:test_declined_confirm_does_not_save_concept_record` — an interactive decline performs no concept write.
- `tests/test_scope_out.py:test_blocked_narrow_does_not_save_concept_record` — graph refusal leaves the sidecar unchanged.
- `tests/test_scope_out.py:test_empty_ownership_without_sidecar_keeps_legacy_apply_path` — old plans can still be carved without a concept record.
- `tests/test_scope_out.py:test_owned_concept_without_usable_record_refuses_before_writes` — missing, stale, malformed, or mismatched concept state cannot be silently ignored.
- `tests/test_scope_out.py:test_unknown_owned_concept_id_refuses_before_writes` — an ownership link absent from the record does not disappear during carve.
- `tests/test_scope_out.py:test_concept_save_failure_rolls_back_narrow` — a concept publication failure restores plan and detail state while retaining the seed-first recovery artifact.
- `tests/test_scope_out.py:test_plan_write_failure_preserves_original_concept_record` — a failed narrow cannot publish the prepared concept deferrals alone.
- `tests/test_scope_out.py:test_successful_apply_persists_narrow_and_deferrals` — the plan, details, and concept record all reflect one completed carve.
- `tests/cli/test_scope_out_cmd.py:test_apply_yes_defers_last_owned_concept` — `scope-out --apply -y` removes the owner and persists `defer`.
- `tests/cli/test_scope_out_cmd.py:test_apply_yes_keeps_shared_concept_included` — a committed survivor prevents a concept decision change.
- `tests/cli/test_scope_out_cmd.py:test_through_defers_only_concepts_with_no_owner_outside_region` — a region carve handles mixed shared and ownerless IDs correctly.
- `tests/cli/test_scope_out_cmd.py:test_recommend_only_leaves_concept_record_unchanged` — the default CLI mode writes neither seed nor concept changes.

### Test-creation order (feature step)

1. Add renderer tests for empty, single-step, and region `concept_ids` with the `_scope_block` change.
2. Add pure owner-survival tests using carved steps and `NarrowPreview.new_steps`.
3. Add orchestrator tests for shared owners, parked owners, missing records, unknown IDs, and every no-write gate.
4. Add failure tests around plan, detail, and concept publication before enabling the successful persisted path.
5. Add CLI integration tests for single-step and `--through` carves using the shipped concept-record fixtures.

Every new test in `tests/test_scope_out.py` and `tests/cli/test_scope_out_cmd.py` must be green before this step is considered finished.

## Acceptance criteria

- `render_carved_seed` and `render_carved_region_seed` include each carved step’s non-empty `concept_ids` in authored order.
- A concept owned by a carved step changes to `defer` when no committed step in the narrowed plan retains that ID.
- A concept remains unchanged when at least one committed survivor retains its ID.
- A parked survivor does not count as a surviving owner.
- A concept shared by several carved steps is deferred at most once.
- Concepts unrelated to the carved region remain unchanged.
- Recommend-only, blocked, and declined scope-out paths do not write the seed, plan, details, or concept record.
- A plan with no carved ownership and no concept record retains the existing scope-out behavior.
- A carve with concept ownership refuses mutation when the required concept record is stale, malformed, missing, or lacks an owned ID.
- A failed apply does not leave the narrowed plan and concept record in different ownership states.
- A successful CLI single-step or region carve leaves every affected signed-off concept covered by a committed survivor or recorded as deferred.
- All new tests in `tests/test_scope_out.py` and `tests/cli/test_scope_out_cmd.py` pass.

## References

- [JSON Schema Validation: A Vocabulary for Structural Validation of JSON](https://json-schema.org/draft/2020-12/json-schema-validation) — Use the identifier and array validation rules when checking explicit concept ownership and record membership.
- [os.replace — Python documentation](https://docs.python.org/3/library/os.html#os.replace) — Read the atomic replacement contract used by the shipped concept-record saver during coordinated publication.

## Deferred

- **Assigning deferred concepts to replacement steps** — the later `create --from-existing` flow owns reviewed successor assignment; scope-out only carries the original IDs in its seed.
- **Inferring ownership from prose, features, titles, or files** — the plan explicitly keeps exact `Step.concept_ids` as the ownership source.
- **Changing concepts that retain a committed owner** — scope-out changes only concepts made ownerless by its carve.
- **General transaction recovery across all plan-tool sidecars** — this step must keep its own plan/detail/concept operation consistent, but a shared multi-artifact transaction framework requires a separate plan.
