# Step 4 — Reject invalid accounting before concept publication

## Summary

This step adds semantic accounting validation to `plan_tool/concept_tree.py` and applies it at both concept publication paths: `save_concepts()` and `plan_tool/concept_sync.py:synchronize_concepts()`. The validator checks a candidate against the current plan and repository artifacts while leaving structural loading permissive enough to diagnose old dangling records. The key design decision is to keep this plan-aware validation separate from `_validate_tree()` and `load_concepts()`. On green, unknown concepts, dangling routes, missing artifacts, and contradictory delivery state return a clear invalid-state result before any plan or sidecar write.

## Table of Contents

- [Summary](#summary) — Overview of the publication guard and its result.
- [Why](#why) — Why structural sidecar validation cannot protect new accounting.
- [Input](#input) — Contracts supplied by steps 2 and 3.
- [Files (creates vs edits)](#files-creates-vs-edits) — Production and test files changed by this step.
- [Implementation](#implementation) — Semantic rules, publication placement, and required invariants.
- [Tests](#tests) — Focused validator and no-write publication cases.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Relevant model-validation and pytest documentation.
- [Deferred](#deferred) — Review, transition, completeness, and lifecycle work left to later steps.

## Why

`plan_tool/concept_tree.py:_validate_tree()` can prove that a sidecar is structurally sound, but it intentionally cannot tell whether a record names a concept in the tree, routes to current plan steps, points to a current artifact, or conflicts with committed delivery. That separation lets `load_concepts()` retain bad historical evidence for diagnostics, but it also means a newly prepared candidate needs a stricter check before publication. Step 4 establishes that check now so the migrated records from step 3 cannot become durable accounting when their plan-aware meaning is invalid.

## Input

- **Step 2 output:** Use the persisted `NonDeliveryRecord` fields and structural rules planned by step 2. This step does not change the schema, record identity, reference syntax, or allowed review states.
- **Step 3 output:** Validate the fully migrated candidate produced by step 3, after legacy keys have been removed and before the candidate is serialized. Do not repeat legacy decoding or migration rules here.
- **Delivery ownership:** The plan's `steps[].concept_ids` field supplies exact ownership. Only ownership on a `StepScope.COMMITTED` step counts as current delivery; the same concept may have several committed owners.
- **Plan routing:** Each step's persisted ID, detail pointer, and scope provide the current step and artifact context. Use the final candidate plan when synchronization changes scopes.
- **Validation limit:** This step rejects bad accounting that is present. It does not require every reviewed concept to have an owner or non-delivery record; step 8 owns that conservation check.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `plan_tool/concept_tree.py` — Add a pure plan-aware candidate validator and invoke it from `save_concepts()` before creating or replacing the sidecar.
  - `plan_tool/concept_sync.py` — Validate the migrated tree against the final candidate plan before fingerprinting, serialization, or either publisher call.
  - `tests/test_concept_tree.py` — Add direct semantic-validation tests and prove structurally valid dangling records still load.
  - `tests/test_concept_sync.py` — Add invalid-candidate integration tests that assert `SyncStatus.INVALID_STATE` and no writes.

## Implementation

The foundational logic is: **reject a concept candidate when any ownership, non-delivery route, artifact reference, or delivery disposition is inconsistent with the current candidate plan.**

- **Add one pure semantic boundary.** Add a clearly named helper such as `plan_tool/concept_tree.py:validate_concept_accounting_candidate()` that accepts the candidate `ConceptTree`, current `Plan`, and enough path context to check repository-backed artifact references. Return normally for a valid candidate and raise `InvalidConceptTreeError` with the offending concept, record, step, or artifact identifier for invalid state. Do not mutate either input or perform writes.

- **Keep structural loading permissive.** Leave `plan_tool/concept_tree.py:_validate_tree()`, `_decode_tree()`, and `load_concepts()` responsible only for the structural contract established by step 2. A structurally valid record with an unknown concept, unknown step, or missing artifact must remain loadable so step 8 can report durable corruption.

- **Validate exact ownership references.** Every ID in `plan_tool/schema.py:Step.concept_ids` must name a current `ConceptNode.id`. Reject an unknown ownership ID even when the step is parked, because it still claims membership in this exact concept tree. Preserve many-owner delivery; the same known concept may appear on several steps.

- **Validate each non-delivery record against the tree.**
  - Require `NonDeliveryRecord.concept_id` to name exactly one current concept.
  - Require the record disposition to agree with that concept’s current `defer` or `wont_do` decision.
  - Allow several records for one concept when their step-2 identities are distinct and their dispositions agree.
  - Do not require the record to be approved here. Step 5 must be able to publish an unreviewed proposal, and step 8 decides whether that proposal counts as accounting.

- **Validate step routing.** Every value in `NonDeliveryRecord.linked_step_ids` must name a current step. When the concept has exact step owners, each linked step must be one of those owners; retain step 3’s rule that an ownerless parked concept may still have a valid route. Preserve the step-2 allowance for an empty route when the record’s artifact contract does not require a step link.

- **Validate current artifacts.** Resolve `NonDeliveryRecord.artifact_ref` according to the reference form defined by step 2. A repository-relative reference must stay within the repository and point to the current artifact; reject missing targets and path escapes. Do not derive a likely detail path from a title or immutable `origin_ref`, and do not require every future namespaced artifact to equal a `Step.detail` value. Step 3 remains responsible for making migrated detail records use the linked step’s exact stored detail reference.

- **Reject simultaneous effective delivery and non-delivery.** An approved non-delivery record cannot coexist with an owner for the same concept on a committed step in the final candidate plan. Ownership on deferred or `wont_do` steps is routing, not committed delivery. Do not reject several committed owners when no approved non-delivery record exists.

- **Do not turn validation into completeness.** Accept a concept with no owner and no non-delivery record, and accept an unapproved record as proposed state when its references are otherwise coherent. `plan_tool/review.py:check_concept_coverage()` in step 8 owns missing-accounting and unsigned-accounting findings.

- **Reject stale approval bindings.** Recompute step 2's semantic review digest for every approved record. Reject an approved record with a missing or mismatched digest before publication; unreviewed records must not carry an approval digest. Never infer approval validity from `review_state` alone.

- **Guard direct sidecar saves.** In `plan_tool/concept_tree.py:save_concepts()`, run structural validation first, obtain the current plan and repository context from `plan_path`, then run semantic validation before creating the parent directory or temporary file. This placement covers the existing direct callers in `plan_tool/create.py`, `plan_tool/detail.py:generate_detail()`, and `plan_tool/scope_out.py:apply_narrow()` without moving their transaction logic or editing those files.

- **Guard synchronization’s separate writer.** `plan_tool/concept_sync.py:synchronize_concepts()` serializes and publishes its own sidecar rather than calling `save_concepts()`, so invoke the same semantic helper explicitly. Validate the migrated candidate against the `updated_plan` produced after `_mapped_scopes()` and `Plan.model_validate()`, because committed-owner contradictions depend on final scopes.

- **Preserve synchronization ordering.** Keep the original-tree compare-and-swap check against durable sidecar state. After that check, migrate the reviewed candidate as supplied by step 3, build the final candidate plan, run semantic validation, and only then calculate `_fingerprint()`, serialize, or call `publish`. Map `InvalidConceptTreeError` to `SyncStatus.INVALID_STATE`; neither `SOURCE_DIVERGENCE` nor `MAPPING_CONFLICT` should be used for a semantically invalid candidate.

- **Preserve transaction behavior.** Do not change `plan_tool/concept_sync.py:_atomic_publish()`, `_restore()`, publisher order, rollback reporting, or provenance refresh. Validation failure happens before publication, so rollback is neither needed nor attempted.

## Tests

- `tests/test_concept_tree.py:test_publication_validation_accepts_many_committed_owners` — A known concept may have several committed owners when it has no approved non-delivery record.
- `tests/test_concept_tree.py:test_publication_validation_rejects_unknown_owned_concept` — A `Step.concept_ids` entry absent from the candidate tree is invalid.
- `tests/test_concept_tree.py:test_publication_validation_rejects_unknown_record_concept` — A record cannot name a concept absent from the candidate tree.
- `tests/test_concept_tree.py:test_publication_validation_rejects_unknown_linked_step` — Every non-delivery route points to a current step.
- `tests/test_concept_tree.py:test_publication_validation_rejects_owner_incompatible_route` — A linked step must be an exact owner when owners exist.
- `tests/test_concept_tree.py:test_publication_validation_allows_ownerless_parked_route` — An ownerless parked concept may retain a valid current route.
- `tests/test_concept_tree.py:test_publication_validation_rejects_missing_artifact` — A repository-backed `artifact_ref` must point to the current artifact.
- `tests/test_concept_tree.py:test_publication_validation_rejects_disposition_mismatch` — A record’s disposition agrees with its concept decision.
- `tests/test_concept_tree.py:test_publication_validation_rejects_committed_delivery_and_approved_non_delivery` — Effective delivery and approved non-delivery cannot coexist.
- `tests/test_concept_tree.py:test_publication_validation_allows_missing_accounting` — This validator does not implement step 8’s conservation check.
- `tests/test_concept_tree.py:test_dangling_record_loads_but_cannot_be_saved` — Structural loading retains a dangling record while candidate publication rejects it.
- `tests/test_concept_tree.py:test_invalid_save_creates_no_sidecar_or_temporary_file` — `save_concepts()` stops before any filesystem publication work.
- `tests/test_concept_sync.py:test_sync_rejects_invalid_accounting_without_writes` — Semantic failure returns `SyncStatus.INVALID_STATE` and preserves both artifacts.
- `tests/test_concept_sync.py:test_sync_validates_against_final_mapped_scopes` — The committed-owner check uses the candidate plan after `_mapped_scopes()`.
- `tests/test_concept_sync.py:test_sync_invalid_accounting_never_calls_publisher` — A publisher spy receives zero calls on semantic failure.
- `tests/test_concept_sync.py:test_sync_valid_accounting_preserves_publication_and_fingerprint` — A valid migrated candidate retains the existing success, fingerprint, and publication behavior.

### Test-creation order (feature step)

1. Add direct predicate tests in `tests/test_concept_tree.py` for known concepts, owners, routes, artifacts, dispositions, and committed-owner contradictions.
2. Add boundary tests proving `load_concepts()` remains structurally permissive while `save_concepts()` rejects the same semantic defect without writes.
3. Add `tests/test_concept_sync.py` integration tests for final-scope validation, invalid-state mapping, and zero publisher calls.
4. Re-run the existing synchronization success, divergence, mapping-conflict, and rollback tests to confirm their behavior remains unchanged.

Every new test must be green before this step is considered finished.

## Acceptance criteria

- `plan_tool/concept_tree.py:load_concepts()` still loads structurally valid records with unknown concepts or dangling routes.
- `plan_tool/concept_tree.py:save_concepts()` rejects unknown ownership IDs, unknown record concepts, dangling step routes, missing repository artifacts, disposition mismatches, and approved non-delivery that conflicts with committed ownership.
- Invalid `save_concepts()` input creates or replaces no sidecar or temporary publication file.
- Many committed steps may own the same known concept when no approved non-delivery record conflicts with that delivery.
- A concept without either delivery or non-delivery accounting is not rejected by this step.
- `plan_tool/concept_sync.py:synchronize_concepts()` validates the migrated tree against the final candidate plan.
- Semantic synchronization failure returns `SyncStatus.INVALID_STATE` before either publisher call.
- Existing compare-and-swap, fingerprint, publication order, rollback, and provenance behavior remains green for valid candidates.
- All new tests in `tests/test_concept_tree.py` and `tests/test_concept_sync.py` pass.

## References

- [Pydantic Models](https://docs.pydantic.dev/latest/concepts/models/) — Review candidate model validation and copied-model behavior used when synchronization builds the final `Plan`.
- [Pydantic Validators](https://docs.pydantic.dev/latest/concepts/validators/) — Review cross-field validation principles relevant to ownership, scope, and disposition consistency.
- [pytest API and Built-in Fixtures](https://docs.pytest.org/en/stable/builtin.html) — Use fixtures and spies to prove invalid candidates perform no writes or publisher calls.

## Deferred

- Explicit record review and approval invalidation — step 5 owns operator review, semantic-change approval invalidation, and unattended approval restrictions.
- Pending `defer|wont_do -> include` state — steps 6 and 7 add the temporary retained-record exception and transactional regeneration flow.
- Missing, unsigned, or stale accounting findings — step 8 updates `plan_tool/review.py:check_concept_coverage()` and reporting; this publication validator does not replace completeness.
- Split, merge, scope-out, and seed routing transforms — the later remediation plans update valid routes and artifact references during lifecycle transactions.
