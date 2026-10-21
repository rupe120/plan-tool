# Step 5 — Review and approve non-delivery records explicitly

## Summary

This step extends scoped concept review to cover the full non-delivery records introduced by step 2, including their disposition, evidence, immutable origin, artifact reference, and step routing. `plan_tool/concept_review.py` owns the copy-on-write review rules, while `plan_tool/cli/scope_review_cmd.py:cmd_scope_review()` gathers an explicit operator decision and `plan_tool/concept_sync.py:synchronize_concepts()` publishes the resulting plan and sidecar together. The key design decision is to treat disposition, evidence, and immutable origin as approval-sensitive semantics while allowing `artifact_ref` and `linked_step_ids` to change without clearing an existing approval. On green, only a TTY-confirmed review can approve a new or changed non-delivery record, rejected or unattended requests write nothing, and approved records participate in deterministic plan synchronization.

## Table of Contents

- [Summary](#summary) — Overview of explicit record review and publication.
- [Why](#why) — Why concept-level sign-off is not enough for durable non-delivery accounting.
- [Input](#input) — Persisted record and publication contracts supplied by earlier steps.
- [Files (creates vs edits)](#files-creates-vs-edits) — Production, documentation, and test files changed.
- [Implementation](#implementation) — Review semantics, operator confirmation, and synchronization rules.
- [Tests](#tests) — Unit, synchronization, CLI, and generated-reference coverage.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Testing guidance used by this step.
- [Deferred](#deferred) — Include regeneration, completeness, and lifecycle work left to later steps.

## Why

`plan_tool/concept_review.py:review_concept_scope()` currently approves only a `ConceptNode` decision and stores sign-off markers in `ConceptNode.source_metadata`; it does not review the durable occurrence records added by step 2. That leaves a parked concept able to look signed while its evidence, origin, or disposition remains unreviewed, and `plan_tool/cli/scope_review_cmd.py:cmd_scope_review()` currently calls `sign_off=True` without a TTY confirmation. This step makes approval belong to the exact non-delivery record semantics and prevents unattended execution from creating that approval.

## Input

- **Step 2 output:** Use step 2's planned `NonDeliveryRecord` collection and identity helper, including the established persisted fields, without changing the schema or identity framing.
- **Step 3 output:** Treat migrated records as ordinary durable records. Preserve their deterministic origins and do not restore or reinterpret `ConceptNode.source_metadata["detail_deferral_step_ids"]`.
- **Step 4 output:** Run review candidates through the semantic publication validator before either artifact is written. This step does not duplicate plan-aware ownership, route, or artifact validation.
- **Current review contract:** Preserve the stale-source, exact-scope, complete-payload, and copy-on-write behavior of `plan_tool/concept_review.py:_validate_request()` and `review_concept_scope()`.
- **Current publication contract:** Preserve the original-versus-reviewed snapshot roles, compare-and-swap checks, plan fingerprinting, publication order, and rollback behavior in `plan_tool/concept_sync.py:synchronize_concepts()`.
- **Approval-sensitive fields:** A record’s `concept_id`, `disposition`, rationale/evidence, and `origin_ref` define what the operator approved. `artifact_ref` and `linked_step_ids` are current routing and do not by themselves invalidate approval.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `plan_tool/concept_tree.py` — Add a shared, pure way to compare approval-sensitive record semantics separately from routing fields.
  - `plan_tool/concept_review.py` — Add exact record-scope validation, copy-on-write record authoring or editing, explicit approve/reject handling, and approval invalidation.
  - `plan_tool/concept_sync.py` — Consume approved non-delivery records when applying parked plan effects while preserving synchronization and rollback rules.
  - `plan_tool/cli/scope_review_cmd.py` — Present complete record facts, require an interactive confirmation before approval, and pass the reviewed candidate to synchronization.
  - `docs/cli/scope-review.md` — Regenerate the command reference from `plan_tool/cli/scope_review_cmd.py:register()` after its description, usage, or options change.
  - `tests/test_concept_tree.py` — Cover the semantic-versus-routing comparison contract.
  - `tests/test_concept_review.py` — Cover record scope, approval, rejection, invalidation, and atomic failure.
  - `tests/test_concept_sync.py` — Cover approved-record plan effects and unchanged transaction behavior.
  - `tests/cli/test_scope_review_cmd.py` — Cover interactive approval, non-TTY refusal, displayed facts, exits, and no-write paths.
  - `tests/cli/test_cli_reference.py` — Assert the generated `scope-review` reference exposes the record-review and interactive-approval contract.

## Implementation

The foundational logic is: **approve a parked concept only after an operator confirms the exact non-delivery record semantics; clear approval after semantic changes but preserve it after routing-only changes.**

- **Define one semantic comparison rule.** Keep the field classification beside `plan_tool/concept_tree.py:NonDeliveryRecord`. A helper such as `non_delivery_review_semantics()` may return the approval-sensitive values for comparison:
  - `concept_id`;
  - `disposition`;
  - rationale/evidence;
  - `origin_ref`.

  Exclude `record_id`, `review_state`, `artifact_ref`, and `linked_step_ids` from this comparison. Identity integrity remains owned by `non_delivery_record_id()` and structural validation; routing changes must not force repeated operator approval.

- **Keep record review separate from concept-only callers.** Extend `plan_tool/concept_review.py` with a record-aware operation rather than making existing calls to `review_concept_scope()` silently approve records. The existing callers in `plan_tool/create.py` and `plan_tool/scope_out.py:_prepare_concept_narrow_update()` must continue to receive the same concept-level behavior without gaining authority to approve durable records.

- **Accept complete record facts.** The record-aware review operation should receive fully formed record proposals or updates plus explicit record outcomes. It must not derive missing evidence, invent an immutable origin, guess an artifact, or infer a likely route from titles. One workable approach is a typed record payload collected interactively by the CLI, but the exact prompt and argument shape may follow existing command conventions.

- **Validate the whole request before copying.**
  - Require a non-empty concept scope and reject duplicate or unknown concept IDs.
  - Require every reviewed record ID to be unique and either already present or backed by a complete new-record payload.
  - Require every reviewed record to belong to a concept in the requested scope.
  - Require `defer` records to accompany `defer` decisions and `wont_do` records to accompany `wont_do` decisions.
  - Reject records or decisions outside the requested scope.
  - Reject an approval request that leaves a newly parked scoped concept without at least one approved matching record.
  - Reject a direct `include` transition while the concept retains non-delivery records. Step 6 owns that pending-transition state.

- **Preserve atomic review behavior.** Finish stale-source, scope, payload, and record validation before mutating a deep copy. Any `InvalidConceptScopeError`, `IncompleteConceptReviewError`, or `StaleConceptReviewError` must leave the supplied `ConceptTree`, its records, and every review state unchanged.

- **Apply approval invalidation consistently.**
  - A change to rationale/evidence clears the old approval before any new operator decision is applied.
  - A change that produces a new `concept_id`, `disposition`, or `origin_ref` is a new record identity and starts unreviewed unless the same interactive operation explicitly approves it.
  - A change only to `artifact_ref` or `linked_step_ids` retains the prior `review_state`.
  - Reapplying identical semantics does not refresh, clear, or otherwise rewrite an existing approval.
  - Explicit rejection sets the selected record to `rejected` without changing unrelated records.

- **Keep concept and record state coherent.** When an operator approves a parked decision, update the scoped `ConceptNode` and the selected matching records in the same copied candidate. Do not treat concept-level `review_state == "approved"` alone as durable non-delivery approval. Unselected concepts and records must remain exactly unchanged.

- **Require a real operator confirmation.** In `plan_tool/cli/scope_review_cmd.py:cmd_scope_review()`, display each selected record’s concept, disposition, evidence, `origin_ref`, `artifact_ref`, and `linked_step_ids` before confirmation. Only a positive response read from a TTY may authorize record approval. A non-TTY invocation, EOF, interrupt, or declined confirmation must perform no synchronization and must not clear existing approvals.

- **Persist what was reviewed.** On positive TTY confirmation, compute and store step 2's semantic review digest from the exact displayed `concept_id`, disposition, rationale/evidence, and `origin_ref`. Any semantic edit clears both approval and the digest; routing-only edits preserve both. Loaded `approved` state without a matching digest is stale, not approval.

- **Keep confirmation testable.** Use a small injected input or confirmation seam rather than placing untestable input calls throughout `cmd_scope_review()`. Check TTY status before prompting. Do not add a `--yes` path that can set a record to `approved`; unattended approval is forbidden by the plan contract.

- **Prepare before publishing.** The CLI may build and validate an unsigned candidate before confirmation, but it must call the approval path only after confirmation. Pass the final reviewed candidate to `plan_tool/concept_sync.py:synchronize_concepts()` once. Do not save the sidecar directly from the review helper or CLI.

- **Use approved records for new parked routing.** Update `plan_tool/concept_sync.py:_accepted_decisions()`, `_mapped_scopes()`, or an equivalent single internal boundary so `defer` and `wont_do` routing supplied by `NonDeliveryRecord.linked_step_ids` is applied only from approved records whose disposition matches the reviewed concept. Ignore unreviewed and rejected records. Preserve deterministic ordering and avoid rendering the same concept more than once when several approved occurrence records support it.

- **Preserve existing concept-only compatibility.** Existing concept decisions and their current plan-section rendering must not be silently reinterpreted as approved durable accounting. Where legacy concept mapping remains necessary for callers outside this step, keep it clearly separate from approved-record routing so step 8 can report the missing record without this step breaking current authoring and scope-out flows.

- **Keep publication guards in order.** In `plan_tool/concept_sync.py:synchronize_concepts()`, apply record-aware mapping and step 4’s candidate validation before fingerprinting, serialization, or either publisher call. Invalid record review or mapping returns `SyncStatus.INVALID_STATE`; concurrent source changes retain the current conflict status and no-write behavior.

- **Regenerate CLI documentation.** Update `plan_tool/cli/scope_review_cmd.py:register()` so help explains that parked decisions review complete records and require interactive confirmation. Regenerate `docs/cli/scope-review.md` through `plan_tool.cli_reference`; do not hand-edit generated usage or option tables.

## Tests

- `tests/test_concept_tree.py:test_non_delivery_review_semantics_include_only_approval_sensitive_fields` — concept, disposition, evidence, and origin affect the semantic comparison.
- `tests/test_concept_tree.py:test_non_delivery_review_semantics_ignore_routing_fields` — changing only `artifact_ref` or `linked_step_ids` leaves the semantic comparison unchanged.
- `tests/test_concept_review.py:test_record_review_approves_complete_parked_scope` — a complete defer or `wont_do` request approves the scoped concept and matching records.
- `tests/test_concept_review.py:test_record_review_can_reject_selected_record` — rejection changes only the selected record and does not approve the concept from that record.
- `tests/test_concept_review.py:test_record_review_rejects_unknown_or_out_of_scope_record` — record IDs must belong to the exact requested concept scope.
- `tests/test_concept_review.py:test_record_review_rejects_duplicate_record_ids` — repeated record outcomes are invalid.
- `tests/test_concept_review.py:test_record_review_rejects_incomplete_new_record` — missing evidence, origin, artifact, or other required facts cannot be invented.
- `tests/test_concept_review.py:test_record_disposition_must_match_concept_decision` — defer and `wont_do` state cannot disagree between concept and record.
- `tests/test_concept_review.py:test_parked_approval_requires_matching_approved_record` — concept-level sign-off alone cannot complete record-aware review.
- `tests/test_concept_review.py:test_semantic_record_change_invalidates_approval` — changed evidence clears prior approval.
- `tests/test_concept_review.py:test_semantic_record_change_can_be_reapproved_explicitly` — the same interactive review operation may approve the changed semantics.
- `tests/test_concept_review.py:test_routing_only_record_change_preserves_approval` — artifact relocation or linked-step fan-out does not clear approval.
- `tests/test_concept_review.py:test_unchanged_record_does_not_refresh_approval` — an identical payload preserves the stored record exactly.
- `tests/test_concept_review.py:test_record_review_failure_is_atomic` — stale, incomplete, or invalid input does not mutate the source tree.
- `tests/test_concept_review.py:test_include_with_retained_non_delivery_record_is_rejected` — step 5 cannot create the pending include state owned by step 6.
- `tests/test_concept_sync.py:test_sync_uses_only_approved_non_delivery_record_routes` — unreviewed and rejected records do not change mapped step scopes.
- `tests/test_concept_sync.py:test_sync_deduplicates_plan_rendering_for_multiple_approved_records` — several occurrence records for one concept render one deterministic parked entry.
- `tests/test_concept_sync.py:test_sync_rejects_invalid_reviewed_record_without_writes` — semantic validation fails before either publisher call.
- `tests/test_concept_sync.py:test_sync_record_publication_failure_rolls_back` — record-aware synchronization retains the existing two-artifact rollback behavior.
- `tests/cli/test_scope_review_cmd.py:test_scope_review_tty_confirmation_approves_and_publishes_records` — a positive TTY confirmation writes the approved records and synchronized plan.
- `tests/cli/test_scope_review_cmd.py:test_scope_review_displays_all_record_facts_before_confirmation` — the operator sees disposition, evidence, origin, artifact, and step routing.
- `tests/cli/test_scope_review_cmd.py:test_scope_review_non_tty_cannot_approve_or_write` — redirected or unattended execution preserves both files.
- `tests/cli/test_scope_review_cmd.py:test_scope_review_decline_eof_and_interrupt_write_nothing` — every cancelled confirmation path leaves both artifacts unchanged.
- `tests/cli/test_scope_review_cmd.py:test_scope_review_invalid_record_payload_has_invalid_state_exit` — malformed or incomplete record input returns exit 4 without publication.
- `tests/cli/test_scope_review_cmd.py:test_scope_review_conflict_still_has_conflict_exit` — re-derivation or source conflicts remain exit 3 and write nothing.
- `tests/cli/test_cli_reference.py:test_scope_review_reference_documents_explicit_record_approval` — generated help documents record review and the interactive approval restriction.

### Test-creation order (feature step)

1. Add semantic-versus-routing comparison tests in `tests/test_concept_tree.py` with the shared field-classification helper.
2. Add valid approval, rejection, scope, mismatch, and copy-on-write tests in `tests/test_concept_review.py` with the record-aware review operation.
3. Add semantic invalidation, routing preservation, unchanged-record, and include-transition tests in `tests/test_concept_review.py`.
4. Add approved-route, deterministic rendering, invalid-state, and rollback tests in `tests/test_concept_sync.py`.
5. Add TTY confirmation, displayed-record, cancellation, non-TTY, and exit-code tests in `tests/cli/test_scope_review_cmd.py`.
6. Regenerate `docs/cli/scope-review.md` and add the focused drift assertion in `tests/cli/test_cli_reference.py`.

Every new test must be green before this step is considered finished.

## Acceptance criteria

- `plan_tool/concept_review.py` can approve or reject an exact set of non-delivery records without changing records outside the requested scope.
- Approval covers the record’s concept, disposition, rationale/evidence, and immutable origin.
- Changing an approval-sensitive field clears prior approval unless a TTY-confirmed review explicitly approves the new value.
- Changing only `artifact_ref` or `linked_step_ids` preserves existing approval.
- A parked concept cannot complete record-aware approval without at least one approved matching non-delivery record.
- A retained non-delivery record cannot transition directly to `include` in this step.
- Non-TTY execution, declined confirmation, EOF, and interruption create no approval and write neither the plan nor `concepts.json`.
- Approved record routes synchronize deterministically; unreviewed and rejected record routes do not change plan scopes.
- Invalid review state returns exit 4, conflicts return exit 3, and both paths leave durable state unchanged.
- `docs/cli/scope-review.md` matches `plan_tool.cli_reference.render_reference()`.
- All new tests in `tests/test_concept_tree.py`, `tests/test_concept_review.py`, `tests/test_concept_sync.py`, `tests/cli/test_scope_review_cmd.py`, and `tests/cli/test_cli_reference.py` pass.

## References

- [pytest API and Built-in Fixtures](https://docs.pytest.org/en/stable/builtin.html) — Use fixtures, monkeypatching, captured streams, and temporary paths to test TTY gates and no-write publication paths.

## Deferred

- Pending `defer|wont_do -> include` transitions — step 6 persists the regeneration request, and step 7 resumes and publishes replacement delivery.
- Missing, unsigned, stale, or contradictory accounting findings — step 8 updates `plan_tool/review.py:check_concept_coverage()` and the completeness reports.
- Create-time and scope-out production of durable records — existing calls in `plan_tool/create.py` and `plan_tool/scope_out.py:_prepare_concept_narrow_update()` remain concept-level callers; later lifecycle and seed-restoration plans own durable record production in those flows.
- Split, merge, artifact-move, and scope-out routing transforms — `concept-remediation-3b-lifecycle-publication` applies the routing-only approval-preservation rule during transactional lifecycle changes.
- Create-time seed restoration — `concept-remediation-3c-seed-restoration` consumes the approved record contract after lifecycle publication is in place.
