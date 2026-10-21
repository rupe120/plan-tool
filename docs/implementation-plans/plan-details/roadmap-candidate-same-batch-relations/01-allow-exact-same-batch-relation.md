# Step 1 — Allow exact same-batch relation endpoints while preserving row replacement and removal

<!-- plan-tool:detail-format-version: 1 -->

## Summary

Allow a validated candidate batch to use an exact row added by that same batch as a declared-relation endpoint. Update `plan_tool/roadmap_candidate.py:_validate_relation_authority` while retaining operation admission in `_validate_operation_authority` and the existing candidate assembly flow in `materialize_candidate`. Add focused materialization coverage in `tests/test_roadmap_candidate.py` and a batch-run regression in `tests/test_roadmap_candidate_run.py`. On green, coherent multi-feedback batches reach the existing inert structural-candidate route without publishing canonical roadmap state.

## Table of Contents

- [Summary](#summary) — Reviewer-level outcome and affected surfaces.
- [Table of Contents](#table-of-contents) — Routes to each section.
- [Why](#why) — The current authority gap and its impact.
- [Input](#input) — Candidate operation and context contracts this step reads.
- [Files (creates vs edits)](#files-creates-vs-edits) — The limited implementation footprint.
- [Implementation](#implementation) — Required authority boundary and recommended approach.
- [Tests](#tests) — Focused regression coverage and green gate.
- [Acceptance criteria](#acceptance-criteria) — Observable completion conditions.
- [References](#references) — Source bug and unchanged lifecycle contract.
- [Applicable guardrails](#applicable-guardrails) — Scope limits for this change.

## Why

`plan_tool/roadmap_candidate.py:_validate_relation_authority` currently requires changed relation endpoints to be predecessor members, so an admitted batch cannot connect an existing changed row to a valid row that the same batch adds. That blocks the normal multi-feedback structural case even after every operation has passed typed validation and feedback binding. The fix must allow only the exact added identity in a `CandidateContextBatchCapsule`, while keeping selector-era predecessor-membership and reached-context rules fail-closed for everything else.

## Input

- **Normalized operations:** `materialize_candidate` prepares the parsed `CandidateDelta.operations` before authority validation. This step depends on the exact `CandidateAddRow`, `CandidateReplaceRow`, and `CandidateRemoveRow` identities and their admitted `feedback_id` values.
- **Candidate artifacts:** `_validate_relation_authority` compares `extract_declared_relations` over immutable predecessor artifacts and the fully applied candidate artifacts. The candidate artifacts are the source for confirming that an allowed added endpoint actually exists after application.
- **Capsule authority:** `_full_member_authority`, `CandidateContextCapsule.full_members`, and `CandidateContextCapsule.relation_evidence` remain the authority source for predecessor rows and reached anchors. Same-batch additions must not expand this context.
- **Candidate route:** `CandidateContextBatchCapsule` is the only route that may use an exact same-candidate addition. Selector-era capsules continue to require predecessor endpoints.

## Files (creates vs edits)

- **New files:** None.

- **Existing files (edits only):**
  - `plan_tool/roadmap_candidate.py` — extend `_validate_relation_authority` so exact same-candidate additions can satisfy relation endpoint and added-owner anchor checks without weakening operation authority.
  - `tests/test_roadmap_candidate.py` — replace the predecessor-only sibling regression with exact-linkage, rejection, and operation-order materialization cases.
  - `tests/test_roadmap_candidate_run.py` — cover the batch proposal route reaching the existing structural candidate surface without publication.

## Implementation

- **Keep typed-operation authority first.** Leave `materialize_candidate` ordering intact: `_prepare_operations` and `_validate_operation_authority` must reject malformed, colliding, wrongly typed, or unbound operations before relation authority considers a same-batch endpoint.

- **Bind the exception to an exact addition.** In `plan_tool/roadmap_candidate.py:_validate_relation_authority`, treat a missing predecessor endpoint as available only when a distinct `CandidateAddRow` in the same prepared operation set creates its exact artifact key, typed row identity, and row id. Do not use a row-id-only match.

- **Keep the exception batch-only.** Permit the exact-addition path only for `CandidateContextBatchCapsule`. Selector-era candidates that pass through the shared relation validator must keep the predecessor-only endpoint rule.

- **Preserve independent feedback traceability.** The relation-owning operation and endpoint-addition operation may carry different admitted `feedback_id` values. Their existing operation-level bindings are the authority record; do not add a relation-level feedback protocol.

- **Update both relation guards together.** The predecessor-membership branch and the added-row reached-anchor branch must both recognize the same exact same-batch endpoint rule. A partial change leaves added-owner-to-added-endpoint relations rejected even when existing-owner-to-added-endpoint relations work.

- **Keep predecessor authority unchanged.** When an endpoint is found in predecessor artifacts, retain the existing full-content capsule-membership requirement through `_predecessor_relation_members`. A same-batch addition must not become a general context anchor for unrelated added rows.

- **Retain removal and replacement behavior.** Keep the incident-relation removal check for `CandidateRemoveRow`, and keep relation ownership tied to an owning add, replace, or remove operation as `_validate_relation_authority` already requires. The new endpoint allowance must not authorize a relation whose owner lacks its own valid operation.

- **Keep validation and lifecycle ownership unchanged.** Let `_assemble_candidate_artifacts`, `check_complete_roadmap_gates`, `_classify_validated_operations`, and the existing batch-candidate path decide validity and structural routing after authority succeeds. Do not alter review, promotion, accepted-head, feedback-state, seed, or canonical-artifact behavior.

- **Use materialization-level cases for the core rule.** Helper-only tests are not enough because correctness depends on prepared operations, candidate application, relation extraction, complete gates, and structural classification working together.

## Tests

### Tests for this step

- `test_candidate_existing_owner_can_relate_to_exact_same_batch_added_endpoint` — materializes a gate-clean structural candidate where an admitted replacement points to an endpoint created by another admitted `add-row`, including distinct feedback bindings.
- `test_candidate_added_owner_can_relate_to_exact_same_batch_added_endpoint` — materializes a gate-clean structural candidate where an added owner declares a relation to an exact same-batch added endpoint.
- `test_candidate_same_batch_relation_endpoint_is_operation_order_independent` — verifies both operation orders produce the same successful candidate result.
- `test_candidate_same_batch_relation_endpoint_requires_exact_added_artifact_and_row_type` — refuses a colliding or wrongly typed addition instead of accepting a matching row id from another artifact or collection.
- `test_candidate_same_batch_relation_endpoint_without_valid_addition_is_refused` — preserves refusal when the endpoint exists in neither the predecessor nor a valid admitted addition.
- `test_candidate_predecessor_relation_endpoint_still_requires_full_membership` — preserves the existing predecessor full-membership refusal.
- `test_candidate_added_endpoint_is_not_a_general_context_anchor` — proves an exact permitted endpoint does not authorize an unrelated addition.
- `test_selector_candidate_same_batch_endpoint_remains_refused` — proves the shared relation validator does not widen selector-era candidates beyond predecessor endpoints.
- `test_batch_candidate_same_batch_relation_reaches_structural_candidate_with_existing_ledger_transition` — drives `plan_tool/roadmap_candidate_run.py:run_initial_candidate_proposal` with the Integration-shaped multi-feedback batch and asserts the structural candidate reaches the existing route, selected items move to `awaiting-review` with their proposals, and no canonical artifact, accepted head, or seed is published.

Every listed test must be green before this step is complete.

## Acceptance criteria

- A valid admitted batch can relate an existing changed row to an endpoint created by an exact same-batch `add-row`.
- A valid admitted batch can relate an added owner to an endpoint created by another exact same-batch `add-row`.
- Both relation forms work regardless of operation order and preserve each operation’s admitted feedback binding.
- An endpoint absent from both predecessor artifacts and exact valid candidate additions remains refused.
- A predecessor endpoint without full capsule membership remains refused.
- A matching row id in the wrong artifact or row type does not authorize a relation.
- A selector-era candidate cannot use the same-candidate endpoint exception.
- Batch candidate storage keeps its existing selected-item `awaiting-review` transition and proposal record while publishing no canonical artifact, accepted head, or seed.
- Row replacement, row removal, complete roadmap gates, structural classification, and existing review/promotion behavior remain unchanged.
- `tests/test_roadmap_candidate.py` and `tests/test_roadmap_candidate_run.py` pass with the new focused coverage.

## References

- [BUG_BACKLOG.md — Read the “Candidate relation authority rejects endpoints added by the same admitted batch” entry for the source case, settled traceability decision, and refusal cases that must remain closed.](../../../BUG_BACKLOG.md)
- [Roadmap Candidate Same Batch Relations plan — Read the Architecture, Risks, and Testing sections for the step’s exact authority boundary.](../../2-roadmap-candidate-same-batch-relations.md)
- [Roadmap Structural Feedback Approval — Read the structural candidate classification and approval lifecycle that this step must leave unchanged.](../../2-roadmap-structural-feedback-approval.md)

## Applicable guardrails

- **The plan’s “## Out of scope”, authority boundary:** Limit changes to exact same-batch relation endpoints. Do not broaden a feedback item’s authority beyond its own admitted operation.
- **The plan’s “## Out of scope”, endpoint creation boundary:** Accept only endpoints already created by a valid operation in the candidate. This step must not infer or add rows.
- **The plan’s “## Out of scope”, lifecycle boundary:** Keep roadmap gates and candidate review, promotion, accepted-head, and seed behavior outside this step.
- **The plan’s “## Out of scope”, design boundary:** Do not introduce a generic candidate-context expansion or separate relation-feedback mechanism.
