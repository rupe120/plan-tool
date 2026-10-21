# Step 3 — Migrate valid legacy deferrals into non-delivery records

## Summary

This step converts valid `ConceptNode.source_metadata["detail_deferral_step_ids"]` values into the durable `NonDeliveryRecord` shape added by step 2. `plan_tool/concept_tree.py` owns a pure migration helper, while `plan_tool/concept_sync.py:synchronize_concepts()` and `plan_tool/detail.py:generate_detail()` apply it inside their existing publication flows. The key design decision is to create one record per concept-and-detail-step occurrence and to reject malformed or ambiguous metadata instead of guessing missing fields. On green, every newly persisted current-schema sidecar contains deterministic non-delivery records and no legacy deferral keys, while failed migration leaves the prior sidecar unchanged.

## Table of Contents

- [Summary](#summary) — Overview of the migration and its publication boundaries.
- [Why](#why) — Why schema compatibility alone does not establish durable accounting.
- [Input](#input) — Contracts supplied by steps 1 and 2 and the legacy facts migration may use.
- [Files (creates vs edits)](#files-creates-vs-edits) — Production and test files changed by this step.
- [Implementation](#implementation) — Migration rules, rejection cases, and writer integration.
- [Tests](#tests) — Focused deterministic migration and publication cases.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — JSON and pytest documentation relevant to the work.
- [Deferred](#deferred) — Later validation, review, and lifecycle work excluded here.

## Why

Step 2 makes version-1 sidecars readable but deliberately preserves `detail_deferral_step_ids` without treating it as accounting. Leaving those values in place would give current-schema writers two representations of the same decision and would force later review and completeness code to keep choosing between them. This step creates durable records only when the legacy data supplies every required fact, removes the legacy key only from a successfully prepared candidate, and rejects the whole migration when conversion would require inventing rationale, routing, or occurrence identity.

## Input

- **Step 1 output:** Use the shared legacy decoder and copy-on-write preparation helpers in `plan_tool/concept_tree.py` as the only interpretation of `"detail_deferral_step_ids"`. Migration must also distinguish an absent key from a present malformed value; fail-soft reads must not silently turn malformed persisted data into an empty successful migration.
- **Step 2 output:** Build only the planned `NonDeliveryRecord` shape and identity contract supplied by step 2. Use step 2's identity helper rather than implementing a second digest.
- **Legacy concept state:** A migratable `ConceptNode` must have `review_state == "approved"`, `decision == "defer"`, a non-empty rationale/evidence value accepted by the step-2 record contract, and a valid legacy list.
- **Plan routing:** Each migrated step ID must name a current non-committed parked step. A concept that already has exact committed ownership is not safely migratable: reject it for explicit review rather than manufacturing simultaneous delivery and non-delivery or parking an owner in this transform.
- **Artifact routing:** Use the linked step’s exact stored `Step.detail` value as `artifact_ref`. Missing or structurally invalid detail references make migration invalid; do not search for a likely detail file or derive one from a title.
- **Compatibility limit:** Loading an old sidecar still does not migrate or write it. Migration occurs only when an owning publication flow is already preparing a new sidecar.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `plan_tool/concept_tree.py` — Add pure deterministic migration preparation, strict legacy classification, collision handling, and legacy-key removal from the copied candidate.
  - `plan_tool/concept_sync.py` — Apply migration to the reviewed candidate inside `synchronize_concepts()` without changing compare-and-swap, fingerprint, publication, or rollback ownership.
  - `plan_tool/detail.py` — Publish successful detail deferrals as migrated records through the existing serial tail of `generate_detail()`, retaining one sidecar save and existing failure reporting.
  - `plan_tool/create.py` and `plan_tool/scope_out.py` — Route current-schema sidecar candidates through the same migration/legacy-free preflight. This is compatibility enforcement only; create restoration and scope-out lifecycle publication remain owned by 3C and 3B.
  - `tests/test_concept_tree.py` — Add direct tests for valid conversion, deterministic identity inputs, rejection, idempotence, ordering, and copy-on-write behavior.
  - `tests/test_concept_sync.py` — Add synchronization tests for successful migration and no-write rejection.
  - `tests/test_detail.py` — Update structured-deferral assertions to the durable record shape and cover serial, concurrent, failed, and malformed migration paths.
  - `tests/test_create.py` and `tests/test_scope_out.py` — Prove current-schema writers cannot preserve or re-emit the retired legacy key.

## Implementation

The foundational logic is: **convert each fully valid legacy concept-to-detail-step link into one deterministic non-delivery record, or reject the candidate without partial conversion.**

- **Keep migration pure.** Add a helper in `plan_tool/concept_tree.py` that accepts a `ConceptTree`, the current plan context, and the plan slug or equivalent stable routing context. Return a deep-copied candidate or a clear migration error; do not mutate the source tree, call `save_concepts()`, or inspect unrelated files.

- **Treat absence and corruption differently.** A missing legacy key needs no work. A present value that is empty, malformed JSON, not a list, or contains booleans, non-integers, non-positive values, or duplicates that make occurrence meaning unclear must reject migration. Step 1’s fail-soft decoder remains suitable for display and legacy reads, but migration needs a strict result that cannot confuse “bad value” with “no value.”

- **Create one record per legacy step link.** Each concept-and-step pair represents one detail occurrence and gets its own `NonDeliveryRecord`. Do not combine several legacy step IDs into one record because they can point at different detail artifacts. Initialize `linked_step_ids` with only that occurrence’s step ID; later split and merge work may change routing without changing identity.

- **Derive a stable legacy origin.** One recommended convention is a helper such as `legacy_detail_origin_ref(plan_slug, step_id)` producing a canonical value like `legacy-detail:<plan-slug>:step:<original-step-id>`. Keep the original legacy step ID in this immutable reference even if routing changes later. The record’s concept ID already separates different concepts at the same detail occurrence.

- **Carry only facts present in legacy state.**
  - Set `concept_id` from the owning `ConceptNode.id`.
  - Set `disposition` to `defer`; other decisions are not valid legacy detail deferrals.
  - Carry the approved node’s rationale/evidence without synthesizing prose.
  - Persist the converted record as `unreviewed` with no approval digest. Legacy concept sign-off did not approve the synthesized immutable origin or full record, so migration must never fabricate record approval.
  - Set `artifact_ref` from the linked step’s exact `Step.detail`.
  - Set `linked_step_ids` to the single validated step ID.
  - Derive `record_id` through step 2’s `non_delivery_record_id()`.

- **Reject incomplete facts.** Fail the whole candidate when any referenced concept is unsigned, has a decision other than `defer`, lacks acceptable rationale/evidence, names an unknown or owner-incompatible step, or lacks a usable stored detail reference. Do not migrate the valid subset of one sidecar while leaving bad legacy keys behind.

- **Make reruns safe.** If the target `record_id` already exists and every persisted field agrees with the deterministic migration result, keep one record and remove the redundant legacy key. If the same identity has different mutable or semantic values, reject the candidate rather than overwriting reviewed data.

- **Preserve deterministic order.** Keep existing `ConceptTree.non_delivery_records` in their stored order. Append migrated records in concept-tree order and then in each legacy ID’s stored order. This keeps serial and concurrent publication reproducible.

- **Remove legacy data only from the candidate.** After every legacy value has converted successfully, delete `"detail_deferral_step_ids"` from each copied node while preserving all unrelated `source_metadata`. A rejected migration must leave both the caller’s tree and the durable sidecar unchanged.

- **Integrate synchronization without changing its transaction.** In `plan_tool/concept_sync.py:synchronize_concepts()`, compare current durable state against `original_tree` as today, but prepare plan effects and the final sidecar from a migrated copy of `reviewed_tree`. Run migration before final fingerprint assignment and `_validate_tree()`. Map migration errors to `SyncStatus.INVALID_STATE` and return before either publisher call.

- **Retain synchronization rendering.** `plan_tool/concept_sync.py:render_scope_decisions()` and `_mapped_scopes()` may continue reading reviewed concept decisions in this step. Migration adds accounting records; it does not transfer plan-section or `Step.scope` authority yet.

- **Integrate detail publication as one generation.** Prepare detail bytes before any live write, migrate the complete concept candidate, refresh `ConceptTree.plan_fingerprint`, and submit details, plan-pointer/accounting changes, and the sidecar through the prerequisite typed publication transaction. Do not call `save_concepts()` after a `DetailResult` is already durable. A restored failure leaves the old details and legacy sidecar together; rollback failure reports every uncertain path.

- **Close every current-schema writer.** Make `save_concepts()` reject a current-schema candidate that still contains the legacy key, then update `synchronize_concepts()`, `generate_detail()`, `create()`, and `apply_narrow()` to run the pure migration/legacy-free preflight before their owning publication boundary. This does not grant 3A authority to redesign create restoration or scope-out generation; it prevents those existing writers from emitting a contradictory current schema.

- **Preserve failed-regeneration behavior.** A failed detail regeneration remains absent from the replacement list, so its old accounting survives. If another step succeeds in the same batch, migrating the retained old link into an equivalent durable record is valid; if no step succeeds, `generate_detail()` performs no sidecar write.

- **Preserve publication failure reporting.** A detail migration or save error must use `generate_detail()`’s existing concept-persistence failure path: mark already-written results unsuccessful, identify the durable detail path for recovery, and retain the prior sidecar. Do not add a worker-side save or a second writer.

- **Reject a global load-time migration.** Do not migrate inside `plan_tool/concept_tree.py:load_concepts()` or infer records during `_decode_tree()`. Those functions lack the current plan, exact owner set, and stored detail routing needed to decide whether a legacy occurrence is valid.

## Tests

- `tests/test_concept_tree.py:test_valid_legacy_deferral_migrates_to_record` — One approved deferred concept and one valid step link produce the expected durable fields and remove the legacy key.
- `tests/test_concept_tree.py:test_legacy_migration_creates_one_record_per_step_link` — Several valid links create separate records with their own artifact references and single-step routing.
- `tests/test_concept_tree.py:test_legacy_migration_order_is_deterministic` — Existing records stay first and migrated records follow concept and stored-step order.
- `tests/test_concept_tree.py:test_legacy_migration_is_copy_on_write` — Neither successful nor rejected preparation mutates the input tree.
- `tests/test_concept_tree.py:test_legacy_migration_preserves_unrelated_metadata` — Removing the legacy key leaves every unrelated metadata entry unchanged.
- `tests/test_concept_tree.py:test_legacy_migration_rejects_malformed_or_ambiguous_values` — Present malformed JSON, invalid element types, invalid IDs, and duplicate occurrence values reject the whole candidate.
- `tests/test_concept_tree.py:test_legacy_migration_rejects_missing_record_facts` — Unsigned decisions, non-defer decisions, empty rationale, unknown steps, owner conflicts, and missing detail references do not produce records.
- `tests/test_concept_tree.py:test_legacy_migration_is_idempotent_for_equivalent_record` — An exact existing record is retained once and its redundant legacy key is removed.
- `tests/test_concept_tree.py:test_legacy_migration_rejects_identity_collision` — An existing record with the same identity but different stored values causes rejection.
- `tests/test_concept_sync.py:test_sync_migrates_legacy_deferrals_before_publication` — Successful synchronization writes current records, removes legacy keys, and retains the existing plan/sidecar fingerprint contract.
- `tests/test_concept_sync.py:test_sync_rejects_invalid_legacy_migration_without_writes` — Migration failure returns `SyncStatus.INVALID_STATE` before either artifact changes.
- `tests/test_concept_sync.py:test_sync_migration_publication_failure_rolls_back` — Existing rollback behavior restores both artifacts when publication fails after migration.
- `tests/test_detail.py:TestStructuredDetailDeferrals.test_valid_deferral_persists_after_detail_write` — A successful detail write persists a durable record rather than legacy metadata.
- `tests/test_detail.py:TestStructuredDetailDeferrals.test_include_transition_regenerates_and_clears_link` — Successful regeneration removes obsolete parked accounting without restoring a legacy key.
- `tests/test_detail.py:TestStructuredDetailDeferrals.test_failed_regeneration_retains_link_and_old_body` — A failed regeneration retains the prior parked accounting and detail body.
- `tests/test_detail.py:TestStructuredDetailDeferrals.test_concurrent_deferrals_save_once_in_step_order` — Concurrent authoring produces deterministic records and one sidecar save.
- `tests/test_detail.py:TestStructuredDetailDeferrals.test_migration_failure_retains_prior_sidecar` — Invalid retained legacy state cannot be partially replaced after a detail write.

### Test-creation order (feature step)

1. Add pure valid-conversion, one-record-per-link, ordering, and copy-on-write tests in `tests/test_concept_tree.py` with the migration helper.
2. Add malformed-input, missing-fact, idempotence, and collision tests in `tests/test_concept_tree.py` with strict migration validation.
3. Add successful and rejected publication tests in `tests/test_concept_sync.py` with the synchronization call site.
4. Update the structured-deferral expectations and add serial, concurrent, failed-regeneration, and migration-failure cases in `tests/test_detail.py`.

Every new test listed for this step must be green before the step is considered finished.

## Acceptance criteria

- A valid approved legacy `defer` link produces one `NonDeliveryRecord` for each linked detail step.
- Migrated records use step 2’s identity helper and contain deterministic immutable origins, exact stored artifact references, and single-step `linked_step_ids`.
- Existing records retain their order; new records follow concept-tree order and stored legacy step order.
- Successful migration removes every `"detail_deferral_step_ids"` key while preserving unrelated `source_metadata`.
- Missing legacy keys are accepted without creating records.
- Present malformed, ambiguous, unsigned, unroutable, or incomplete legacy values reject the complete candidate without mutation.
- Equivalent existing records make migration idempotent; conflicting identity collisions are rejected.
- `plan_tool/concept_tree.py:load_concepts()` remains read-only and does not invent records during schema compatibility loading.
- `plan_tool/concept_sync.py:synchronize_concepts()` returns `SyncStatus.INVALID_STATE` and writes neither artifact when migration fails.
- `plan_tool/detail.py:generate_detail()` publishes one migrated sidecar after successful serial or concurrent authoring and never saves from a worker.
- Failed regeneration retains the prior parked accounting, and a migration or save failure retains the prior durable sidecar.
- Newly persisted current-schema sidecars contain no legacy detail-deferral metadata.
- Focused tests in `tests/test_concept_tree.py`, `tests/test_concept_sync.py`, and `tests/test_detail.py` pass.

## References

- [RFC 8259: The JavaScript Object Notation (JSON) Data Interchange Format](https://www.rfc-editor.org/rfc/rfc8259.html) — Use its array, number, and object rules when classifying legacy JSON without guessing.
- [Python json — JSON encoder and decoder](https://docs.python.org/3.13/library/json.html) — Use the standard decoder behavior for strict legacy-array inspection.
- [pytest API and Built-in Fixtures](https://docs.pytest.org/en/stable/builtin.html) — Use fixtures and monkeypatching for isolated candidate, publisher, rollback, and save-call tests.

## Deferred

- General semantic publication validation — Step 4 validates unknown concepts, dangling routing, contradictory accounting, and other newly authored candidate defects beyond the legacy migration checks required here.
- Explicit record authoring and approval transitions — Step 5 owns interactive review, approval invalidation, and unattended/non-TTY restrictions for new or changed records.
- Pending include regeneration — Steps 6 and 7 own durable requests and atomic removal of retained non-delivery accounting after replacement delivery succeeds.
- Read-only conservation enforcement — Step 8 updates `plan_tool/review.py:check_concept_coverage()` to count durable records and retire legacy metadata as an accounting source.
- Split, merge, scope-out, and seed routing transforms — The later `concept-remediation-3b-lifecycle-publication` and `concept-remediation-3c-seed-restoration` plans consume these records without changing this migration step.
