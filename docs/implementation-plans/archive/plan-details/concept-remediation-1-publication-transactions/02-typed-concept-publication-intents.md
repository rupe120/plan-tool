# Step 2 — Add typed concept publication intents

## Summary

This step adds a typed request vocabulary for concept publication in `plan_tool/concept_sync.py`, with concept-specific reference validation in `plan_tool/concept_tree.py`. The variants cover signed decisions, unsigned proposals, ownership changes, detail-deferral replacement, and scope-out publication inputs without using one request full of optional fields. Validation produces write-free prepared state and rejects incompatible requests before any staging or filesystem change. On green, later callers have explicit intent types for step 3’s coordinator, while existing synchronization and concept persistence behavior remains compatible.

## Table of Contents

- [Summary](#summary) — The request vocabulary and observable result.
- [Why](#why) — Why publication needs distinct typed requests.
- [Input](#input) — The existing plan, concept, and preparation contracts.
- [Files (creates vs edits)](#files-creates-vs-edits) — The four files changed by this step.
- [Implementation](#implementation) — Intent variants, validation rules, and boundaries.
- [Tests](#tests) — Unit coverage for every request shape and rejection path.
- [Acceptance criteria](#acceptance-criteria) — Checks that prove the typed contract is ready.
- [References](#references) — Primary guidance for tagged request unions.
- [Deferred](#deferred) — Coordination and caller migrations owned by later steps.

## Why

`plan_tool/concept_sync.py:synchronize_concepts` accepts one signed-review-shaped argument set, while unsigned create, detail deferrals, ownership changes, and scope-out need different combinations of plan, concept, and supporting artifacts. Without explicit request variants, callers must pass loosely related optional values and decide for themselves which combinations are valid. Step 1 supplies shared write-free preparation; this step adds the missing typed boundary so invalid combinations stop before step 3 introduces staging and recovery.

## Input

- **Step 1 preparation outcome** — use the shared, write-free preparation entry points from step 1 for copying, transformation, and validation. Do not recreate the rules in the intent layer.
- **Plan state** — `plan_tool/schema.py:Plan`, `plan_tool/schema.py:Step`, `plan_tool/schema.py:StepScope`, and `Step.concept_ids` define valid step ownership and target scope.
- **Concept state** — `plan_tool/concept_tree.py:ConceptTree`, `plan_tool/concept_tree.py:ConceptNode`, and `_validate_tree` define valid in-memory concept records. Intent validation must not change the persisted `ConceptTree` or `ConceptNode` shape.
- **Review policy** — `plan_tool/concept_review.py:review_concept_scope` remains the source of truth for complete review payloads, approval transitions, and sign-off metadata. The intent layer validates publication shape, not review policy.
- **Existing synchronization contract** — `plan_tool/concept_sync.py:synchronize_concepts` must preserve the original-tree versus reviewed-tree distinction, `SyncStatus`, `ConceptSyncResult`, scope rendering, mapping behavior, and current compare-and-swap inputs.
- **Detail-deferral metadata** — step 1’s shared replacement helper owns the existing `detail_deferral_step_ids` whole-step replacement rules. An empty replacement means removal; it is not an omitted or unknown request.
- **Scope-out preparation** — step 1’s shared scope-out preparation identifies concepts that lose their final committed owner. The scope-out intent consumes that prepared result and its forward-seed input without recalculating ownership.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `plan_tool/concept_sync.py` — add the tagged publication-intent union, common prepared-publication result, and write-free validation/dispatch entry point.
  - `plan_tool/concept_tree.py` — add transient typed values and reusable validation for concept ownership and structured deferral references; leave sidecar serialization unchanged.
  - `tests/test_concept_sync.py` — cover each intent variant, incompatible field combinations, preparation dispatch, immutability, and compatibility with `synchronize_concepts`.
  - `tests/test_concept_tree.py` — cover ownership and deferral reference validation independently of publication.

## Implementation

The foundational logic is: **accept exactly one tagged publication intent and reject every incompatible request shape before staging or writing**.

- **Use distinct intent variants in `plan_tool/concept_sync.py`.** Define one public tagged union, with clear variants for:
  - Signed decision publication.
  - Unsigned proposal publication.
  - Explicit step-ownership change.
  - Structured detail-deferral replacement or removal.
  - Scope-out publication, including the prepared include-to-defer change and forward-seed publication input.

  Names may follow the existing `ConceptSyncResult` style; favor direct names such as `SignedDecisionIntent` and `DetailDeferralIntent`. Keep one stable discriminator such as `kind` on every variant.

- **Reject the all-optional request alternative.** A single model with optional review, ownership, deferral, and seed fields would allow states such as an unsigned proposal carrying sign-off changes or an ordinary ownership request carrying a forward seed. A tagged union should make those combinations unrepresentable where practical and reject them during validation otherwise.

- **Keep common snapshot fields consistent.** Each applicable variant should identify the plan path, immutable source plan snapshot, original concept snapshot or explicit absence, and prepared target inputs needed by step 1’s helpers. Signed publication must keep the original tree as the compare-and-swap source and the reviewed tree as the intended candidate. Do not replace either role with the other.

- **Model unsigned publication explicitly.** The unsigned variant must preserve existing `Deferred` and `Out of scope` plan prose and must not claim that review approval occurred. It may carry proposed concept decisions, but validation must reject approval or sign-off transitions that only the signed variant can publish.

- **Model ownership as a complete target fact.** A concept ownership value should name a real concept ID and its intended step owners, rather than encode an ambiguous add/remove instruction. Validate IDs against `plan_tool/concept_tree.py:ConceptTree` and step IDs against `plan_tool/schema.py:Plan`. Reject duplicate concept entries, duplicate owners, unknown concepts, unknown steps, and any target `Plan` whose `Step.concept_ids` disagree with the declared ownership result.

- **Model detail deferrals as whole-step replacements.** Reuse step 1’s replacement behavior rather than exposing low-level metadata edits. Each replacement names one real step and its complete ordered set of deferred concept IDs; an empty set explicitly removes that step’s old links. Reject duplicate step replacements, duplicate concept IDs within a replacement, unknown steps, unknown concepts, and malformed existing `detail_deferral_step_ids` values instead of silently treating malformed persisted metadata as empty.

- **Keep scope-out as an explicit composite variant.** It may combine a narrowed target plan, the prepared ownerless include-to-defer transitions, ownership removal, and one forward-seed publication input because those parts form one scope-out operation. Reject a concept transition unless the source is an approved `include`, the target is an approved `defer`, and the concept loses its final committed owner. Require the seed path and seed content together; reject partial seed input.

- **Return prepared state, not writes.** Add a write-free dispatch function in `plan_tool/concept_sync.py` that validates the tagged request, delegates transformations to step 1’s preparation helpers, and returns a common prepared-publication value. That value should retain the intent kind plus the original and target plan/concept states and any intent-specific artifact input needed by step 3. It must not stage files, call `_atomic_publish`, refresh provenance, acquire locks, or perform rollback.

- **Represent the complete bounded artifact bundle.** The common prepared value must carry typed artifact actions for exact file replacement/creation/removal, paired directory moves, collision archives, manifest mutations, prepared detail bytes, and resume promotion/cleanup. Each file action includes its source/target path, original existence and digest or compare-and-swap provenance, candidate bytes or staged source, and deterministic ordering. Each directory move instead carries a deterministic recursive source-tree manifest covering every relative path, directory/file/symlink entry type, file digest, and symlink target without following links, plus the required source and destination existence states; reject sockets, devices, FIFOs, escaping links, or any other unsupported entry. Also carry unchanged detail files that participate only as final-fingerprint inputs. Reject duplicate or overlapping targets, directory/file aliasing, partial move pairs, and any action not permitted by the selected concept-publication intent. These primitives are closed to the known create, detail, and scope-out bundles; they are not a general transaction API.

- **Validate before dispatch side effects.** Complete discriminator, field-shape, reference, transition, and target-consistency checks before calculating publication operations. A rejected request must leave every supplied `Plan`, `ConceptTree`, nested `ConceptNode`, ownership list, and deferral list unchanged.

- **Keep concept validation reusable in `plan_tool/concept_tree.py`.** Place concept-ID, ownership, and structured deferral reference checks beside `ConceptTree` and `_validate_tree`, where `plan_tool/concept_sync.py` and later callers can share them. Keep these types transient: `_decode_tree`, `load_concepts`, `save_concepts`, `CONCEPTS_SCHEMA_VERSION`, and the serialized field sets must not include publication-intent data.

- **Leave the legacy synchronizer structurally unchanged in this feature step.** Add and test the new typed intent preparation contract beside `plan_tool/concept_sync.py:synchronize_concepts`; do not route the legacy synchronizer through it or restructure the legacy control flow here. `synchronize_concepts` retains its current use of `_mapped_scopes`, `render_scope_decisions`, `_fingerprint`, original-sidecar comparison, publication rollback, public signature, and result mapping. Caller migration happens only in the owning later feature steps, avoiding a behavior-preserving refactor mixed into this typed-contract feature.

- **Keep intent validation separate from the transaction coordinator.** Do not add journal records, filesystem staging, replacement ordering, directory durability, mutation-lock tokens, rollback verification, or uncertain-path statuses here. Step 3 consumes the prepared contract and owns those behaviors.

## Tests

- `tests/test_concept_sync.py:test_signed_decision_intent_prepares_reviewed_scope` — a signed request maps approved decisions, renders owned scope sections, and preserves the original tree as its source snapshot.
- `tests/test_concept_sync.py:test_unsigned_proposal_intent_preserves_scope_prose` — an unsigned request keeps existing deferred and out-of-scope Markdown and does not create approval.
- `tests/test_concept_sync.py:test_unsigned_proposal_rejects_signoff_transition` — approval or sign-off metadata cannot be published through the unsigned variant.
- `tests/test_concept_sync.py:test_ownership_intent_requires_target_plan_to_match` — declared owners and target `Step.concept_ids` must describe the same final ownership.
- `tests/test_concept_sync.py:test_detail_deferral_intent_replaces_whole_step_links` — a replacement removes old links before adding the complete new set.
- `tests/test_concept_sync.py:test_detail_deferral_intent_accepts_explicit_empty_replacement` — an empty replacement removes the step’s links without creating an empty metadata value.
- `tests/test_concept_sync.py:test_scope_out_intent_accepts_ownerless_include_to_defer` — the scope-out variant accepts a prepared transition only when the concept loses its final committed owner.
- `tests/test_concept_sync.py:test_scope_out_intent_rejects_surviving_owner_transition` — a concept with a committed surviving owner cannot be deferred by the scope-out variant.
- `tests/test_concept_sync.py:test_scope_out_intent_requires_complete_forward_seed` — seed path without content, or content without a path, is invalid.
- `tests/test_concept_sync.py:test_discriminated_intents_reject_foreign_fields` — fields belonging to another variant are rejected instead of ignored.
- `tests/test_concept_sync.py:test_invalid_intent_does_not_prepare_or_write` — validation failure occurs before preparation dispatch and performs no filesystem operation.
- `tests/test_concept_sync.py:test_prepare_publication_intent_does_not_mutate_inputs` — preparation deep-copies mutable plan, tree, node, ownership, and deferral inputs.
- `tests/test_concept_sync.py:test_prepared_artifact_bundle_rejects_overlapping_targets` — duplicate targets, file/directory aliasing, and incomplete move pairs fail before staging.
- `tests/test_concept_sync.py:test_prepared_artifact_bundle_carries_final_fingerprint_inputs` — replacement detail bytes and unchanged ordered detail inputs are explicit and sufficient to derive the final bundle fingerprint.
- `tests/test_concept_sync.py:test_intents_reject_foreign_artifact_actions` — each intent accepts only its declared create, detail, or scope-out artifact actions.
- `tests/test_concept_sync.py:test_synchronize_concepts_remains_compatible_with_signed_intent` — the existing entry point retains its status, rendering, mapping, fingerprint, and rollback behavior.
- `tests/test_concept_tree.py:test_ownership_references_require_known_concepts_and_steps` — unknown concept or step IDs are rejected.
- `tests/test_concept_tree.py:test_ownership_references_reject_duplicate_entries` — duplicate concepts and duplicate owners are invalid.
- `tests/test_concept_tree.py:test_detail_deferral_references_require_known_ids` — deferral replacements reject unknown steps and concepts.
- `tests/test_concept_tree.py:test_detail_deferral_references_reject_malformed_existing_metadata` — malformed structured metadata is reported instead of treated as no links.
- `tests/test_concept_tree.py:test_publication_types_do_not_change_concept_sidecar_schema` — save/load output retains exactly the existing `ConceptTree` and `ConceptNode` fields.

### Test-creation order (feature step)

1. Add the tagged-union shape tests, including foreign-field and partial-seed rejection.
2. Add independent ownership and detail-deferral reference tests in `tests/test_concept_tree.py`.
3. Add signed, unsigned, ownership, deferral, and scope-out preparation tests in `tests/test_concept_sync.py`.
4. Add input-immutability and no-write failure tests.
5. Run the existing synchronization, round-trip, invalid-tree, and rollback tests unchanged.

Every new test and the step 1 characterization suite must be green before this step is considered finished.

## Acceptance criteria

- A public tagged intent union in `plan_tool/concept_sync.py` represents signed decisions, unsigned proposals, ownership changes, detail-deferral replacement/removal, and scope-out publication inputs as distinct variants.
- Parsing or constructing a variant with fields owned by another variant fails before preparation or filesystem access.
- Unsigned publication preserves existing plan scope prose and cannot publish approval or sign-off metadata.
- Ownership intent validation rejects unknown or duplicate concept and step references and rejects a target plan that disagrees with the declared final ownership.
- Detail-deferral intent validation treats an empty replacement as removal and rejects malformed, unknown, or duplicate references.
- Scope-out intent validation accepts only ownerless approved include-to-defer transitions and requires complete forward-seed input.
- Preparing any valid intent leaves all input plan, tree, node, ownership, and deferral objects unchanged.
- Prepared create, detail, and scope-out intents represent every owned artifact action and every unchanged fingerprint input explicitly, reject overlaps, and cannot accept actions owned by another intent.
- Intent preparation performs no filesystem write, staging, lock acquisition, provenance refresh, or rollback.
- `plan_tool/concept_tree.py:CONCEPTS_SCHEMA_VERSION`, `_decode_tree`, `load_concepts`, and `save_concepts` retain the existing persisted sidecar shape.
- `plan_tool/concept_sync.py:synchronize_concepts` remains compatible with its existing callers and passes its success, divergence, conflict, and rollback tests.
- All new tests in `tests/test_concept_sync.py` and `tests/test_concept_tree.py`, plus the step 1 characterization tests, pass.

## References

- [Pydantic — Unions and discriminated unions](https://pydantic.dev/docs/validation/latest/concepts/unions/#discriminated-unions) — Use explicit discriminator values and strict variant fields so incompatible publication requests fail at the boundary.

## Deferred

- All-or-recoverable publication coordination — step 3 owns staging, durable journaling, replacement ordering, final-byte verification, rollback, and uncertain-path reporting.
- Scope-review migration — step 4 changes `plan_tool/cli/scope_review_cmd.py:cmd_scope_review` to submit the signed intent to the new authority.
- Create resume state and terminal approval behavior — step 5 owns the unsigned resume record and interactive review rules.
- Create artifact-bundle preparation and publication — steps 6 and 7 own bundle assembly and migration to signed and unsigned publication intents.
- Detail-file bundle preparation and publication — steps 8 and 9 own prepared detail writes and their transaction with deferral replacement.
- Scope-out preparation and caller migration — step 10 extracts the write-free bundle; step 11 routes `plan_tool/scope_out.py:apply_narrow` and forward-seed publication through the authority.
- Direct-writer enforcement — step 12 owns the source scan that blocks production decision-bearing calls to `save_concepts`, `write_concepts`, and raw `concepts_path` writes.
- Review and lifecycle policy changes — `plan_tool/concept_review.py:review_concept_scope` and later ownership-accounting plans remain the authorities; this step does not redesign them.
- Persisted concept schema changes — the plan frontmatter does not authorize changes to `ConceptTree`, `ConceptNode`, or `CONCEPTS_SCHEMA_VERSION`.
