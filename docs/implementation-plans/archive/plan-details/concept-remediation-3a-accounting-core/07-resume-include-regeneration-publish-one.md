# Step 7 — Resume include regeneration and publish it as one transaction

## Summary

This step makes `plan_tool/detail.py:generate_detail()` resume the durable include requests produced by step 6 and regenerate each exact destination detail. It uses the concept publication authority through `plan_tool/concept_sync.py` to publish the regenerated Markdown, plan ownership and scope, request removal, and retained-record removal as one recoverable generation. The key design decision is to derive completion from the reviewed requests, while treating generated prose as content rather than authority for concept ownership. On green, a successful regeneration leaves committed replacement delivery with no pending or parked accounting, while any recoverable failure leaves the prior detail, parked plan effect, retained records, and requests unchanged.

## Table of Contents

- [Summary](#summary) — Overview of resumable regeneration and transactional completion.
- [Why](#why) — Why the current separate regeneration and accounting writes are unsafe.
- [Input](#input) — Dependency-owned request, accounting, and publication contracts.
- [Files (creates vs edits)](#files-creates-vs-edits) — The production and test files changed.
- [Implementation](#implementation) — Scheduling, completion rules, transaction contents, and failure handling.
- [Tests](#tests) — Focused success, failure, resume, ordering, and rollback coverage.
- [Acceptance criteria](#acceptance-criteria) — Observable proof that regeneration completes safely.
- [References](#references) — Filesystem and testing guidance relevant to the transaction.
- [Deferred](#deferred) — Completeness and later lifecycle work outside this step.

## Why

The current `plan_tool/detail.py:generate_detail()` include-regeneration path finds approved include decisions through legacy deferral links, replaces detail files, and updates concept state afterward. That ordering can leave replacement content paired with old parked accounting when concept publication fails. Step 6 supplies durable requests and deliberately retains the parked state, so this step must resume from those requests and remove that state only in the same verified publication that makes replacement delivery durable.

## Input

- **Step 6 output:** Read the planned persisted include-regeneration request collection. Each `IncludeRegenerationRequest` supplies the exact concept, retained record, destination step, intended detail artifact, and reviewed mapping digest. Do not infer work from a bare include decision, record routing, title, or prose.
- **Step 6 effective state:** Pending concepts remain governed by their approved retained `NonDeliveryRecord` dispositions. Their plan scopes and parked sections stay effective until this step completes the full transition.
- **Step 4 validation:** Validate the completed candidate with `plan_tool/concept_tree.py:validate_concept_accounting_candidate()`. This step must produce ordinary committed delivery, not add another exception to the pending-state rules.
- **Prerequisite publication authority:** Use the typed all-or-recoverable concept publication API delivered by `concept-remediation-1-publication-transactions`. Consume its verified-success, restored-failure, and rollback-failed outcomes without duplicating its journal, staging, locking, durability, or recovery logic.
- **Prerequisite authoring boundary:** Consume write-free prepared detail outcomes from the prerequisite detail-publication work. `plan_tool/detail.py:_author_step_detail()` and worker threads must not publish active files or shared concept state.
- **Existing detail result contract:** Preserve `plan_tool/detail.py:DetailResult`. `written=True` means the complete candidate generation was verified, not merely that model output parsed or a temporary file was prepared.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `plan_tool/concept_sync.py` — Add pending-include completion to the typed concept-publication preparation path, including committed ownership, request and retained-record removal, final validation, and result mapping.
  - `plan_tool/detail.py` — Select exact regeneration destinations from durable requests, author them once per destination, reject contradictory output, and submit the complete transition through the shared publication authority.
  - `tests/test_concept_sync.py` — Cover completed-candidate preparation, exact request consumption, validation refusal, restored failure, and rollback uncertainty.
  - `tests/test_detail.py` — Cover request-driven scheduling, serial and concurrent authoring, dry-run, partial authoring failure, transactional success, checkpoints, and operator-facing results.

## Implementation

The foundational logic is: **remove a pending include request and its retained non-delivery record only in the verified transaction that publishes the requested replacement detail and exact committed ownership.**

- **Schedule from durable requests.** In `plan_tool/detail.py:generate_detail()`, load the current concept tree as it already does and collect destinations from `ConceptTree.include_regeneration_requests`. Group requests by destination step so one detail is authored once even when several requested concepts target it.

- **Honor exact routing.** Require each request’s destination and intended artifact to match the current plan and the canonical output selected through `plan_tool/detail.py:derive_detail_path()`. Treat missing steps, changed pointers, or mismatched artifacts as invalid durable state. Do not choose a nearby step or derive a replacement path from a concept title.

- **Resume requested work regardless of ordinary selection.** Preserve the current behavior in which regeneration work is added to the requested `step_id` or full-plan selection. A pending destination must not be skipped merely because its detail already exists; that file represents the still-parked generation that the request asks to replace.

- **Keep dry-run read-only.** A dry run may render and return prompts for request destinations, but it must not invoke the backend, alter detail files, change plan ownership or scope, remove records or requests, discard checkpoints, or call the publication authority.

- **Keep workers write-free.** Both the serial path and `plan_tool/detail.py:_generate_detail_concurrent()` may prepare regenerated content. Worker completion order must not decide publication order, request consumption, ownership, or shared concept state.

- **Bind resumed checkpoints to current intent.** If regeneration uses the existing checkpoint path, its input hash must cover enough current request and concept state to reject a response prepared for an older destination or request set. A stale or opaque checkpoint must cause normal re-authoring, not completion from uncertain content.

- **Treat reviewed requests as ownership authority.** On accepted regenerated content, add each requested `concept_id` to the exact destination step’s `concept_ids` and make that destination committed as required by the final plan model. Do not require the generated response to restate ownership, and do not infer ownership from prose.

- **Reject contradictory authoring output.** If `plan_tool/detail.py:parse_structured_detail_response()` returns a deferral for a concept whose pending request is being completed in that detail, treat the destination as failed regeneration. Keep its old detail, request, retained record, parked scope, and ownership state. A model response cannot reverse the operator-reviewed include transition.

- **Complete a closed request batch.** Build the publication candidate only when every request included in the pending regeneration batch has a successful prepared destination. This avoids publishing a committed owner while another request or retained record for the same pending transition remains. If requests share concepts or destination steps, keep that connected work in the same completion batch rather than publishing an internally contradictory subset.

- **Revalidate reviewed mapping and destination closure.** Before authoring and again before publication, recompute every request's mapping digest and reject stale substitutions. Expand the closure check over each destination to every effectively parked concept routed through it; completion is allowed only when all such concepts are in the same valid request batch. Never grant delivery to an unrelated parked concept merely because its route shares the destination step.

- **Prepare the final concept state in `plan_tool/concept_sync.py`.** Extend the typed intent preparation used by `synchronize_concepts()` or its prerequisite replacement boundary. For every completed request:
  - remove the exact request;
  - remove its exact retained `NonDeliveryRecord` once no request in the completed transition still needs it;
  - preserve unrelated requests and records;
  - preserve record identity and ordering for everything retained;
  - require the concept’s reviewed decision to remain approved `include`;
  - apply exact committed ownership to the requested destination.

- **Render the final plan from completed accounting.** The candidate must remove the completed concept from the parked sections and change the affected step from the retained parked disposition to committed delivery. Use `plan_tool/concept_sync.py:render_scope_decisions()` and `_mapped_scopes()` through their post-step-6 effective-decision rules; do not edit rendered Markdown separately after building the accounting candidate.

- **Publish one recoverable generation.** Submit the regenerated detail bytes, updated plan pointers and ownership, final plan sections and scopes, request removal, retained-record removal, and final concept tree in one prerequisite transaction. Include existing detail replacement or archive actions in that same request.

- **Fingerprint final bytes.** Preserve the framing represented by `plan_tool/concept_sync.py:_fingerprint()` or the prerequisite transaction equivalent: hash the fully rendered candidate plan with the final ordered detail set, including the regenerated bytes before they become live. Store that fingerprint on the candidate concept tree before semantic validation and serialization.

- **Validate before mutation.** Run the plan-aware accounting validator against the completed candidate. It must now pass as ordinary include delivery: exact committed owner present, completed requests absent, and completed retained non-delivery records absent. Invalid state must stop before any live target changes.

- **Map outcomes honestly.**
  - Verified success marks the regenerated `DetailResult` values as written and permits checkpoint discard and other success-only callbacks.
  - Authoring or validation failure leaves the prior generation unchanged and keeps the requests available for another run.
  - Restored publication failure reports the regeneration as not written and states that the prior generation was restored.
  - Rollback failure reports every uncertain path supplied by the publication authority and does not claim that either generation won.

- **Keep direct writers out of completion.** The concept-backed regeneration path must not call `plan_tool/concept_tree.py:save_concepts()`, perform a separate `update_step_detail_field()` write, or publish regenerated Markdown before the common transaction. Those calls would recreate the mixed-generation window this step closes.

- **Preserve unrelated detail behavior.** Ordinary detail authoring in the same call may use the prerequisite transaction behavior, but it must not consume pending requests or remove records unless the complete request batch satisfies the completion rules above. Plans without a concept tree remain request-free and keep their established detail-only behavior.

## Tests

- `tests/test_detail.py:test_pending_include_schedules_exact_destination` — an exact durable request adds its destination to the authoring set even when another `step_id` was requested.
- `tests/test_detail.py:test_pending_include_groups_requests_by_destination` — several concepts targeting one step cause one authoring call and one prepared detail.
- `tests/test_detail.py:test_pending_include_existing_detail_is_regenerated` — the ordinary already-exists skip does not suppress durable regeneration work.
- `tests/test_detail.py:test_pending_include_rejects_changed_artifact_target` — a destination or artifact mismatch performs no authoring or publication.
- `tests/test_detail.py:test_pending_include_checkpoint_requires_current_request_state` — only a checkpoint bound to the current request set may resume regeneration.
- `tests/test_detail.py:test_pending_include_contradictory_deferral_retains_parked_state` — output that re-defers a requested concept leaves the old generation and request intact.
- `tests/test_detail.py:test_pending_include_partial_authoring_failure_publishes_no_transition` — one failed destination prevents committed ownership or accounting removal for the closed batch.
- `tests/test_detail.py:test_pending_include_serial_and_concurrent_prepare_same_batch` — serial and `jobs > 1` paths produce the same destination order and transaction input.
- `tests/test_detail.py:test_pending_include_dry_run_is_read_only` — dry-run returns prompts while preserving details, plan, concept tree, requests, records, and checkpoints.
- `tests/test_detail.py:test_pending_include_success_side_effects_wait_for_commit` — checkpoint discard and success callbacks occur only after verified publication.
- `tests/test_concept_sync.py:test_complete_include_prepares_committed_owner_and_removes_parked_state` — completion adds exact ownership and removes the matching request and retained record.
- `tests/test_concept_sync.py:test_complete_include_preserves_unrelated_accounting` — unrelated requests, records, concepts, scopes, and sections remain unchanged and ordered.
- `tests/test_concept_sync.py:test_complete_include_rejects_partial_request_batch` — a candidate that leaves a connected request or retained record cannot publish.
- `tests/test_concept_sync.py:test_complete_include_fingerprint_uses_regenerated_detail_bytes` — the stored fingerprint identifies the final plan and ordered candidate details.
- `tests/test_concept_sync.py:test_complete_include_restored_failure_keeps_original_generation` — an injected publication failure with successful restoration preserves every prior path and byte.
- `tests/test_concept_sync.py:test_complete_include_rollback_failure_reports_uncertain_paths` — rollback failure returns the complete uncertain-path set without claiming success.
- `tests/test_concept_sync.py:test_complete_include_uses_no_direct_concept_writer` — completion succeeds through the publication authority when direct sidecar and per-pointer writers are patched to fail.

### Test-creation order (feature step)

1. Add request selection, exact routing, grouping, existing-detail, and checkpoint-resume tests with `plan_tool/detail.py:generate_detail()`.
2. Add pure completed-candidate tests for ownership, scope, request removal, record removal, and unrelated-state preservation in `tests/test_concept_sync.py`.
3. Add contradiction and incomplete-batch tests before enabling publication.
4. Add one-transaction success and final-byte fingerprint tests.
5. Add serial-versus-concurrent ordering and dry-run tests.
6. Add restored-failure and rollback-failed tests at each transaction target.
7. Add success-only callback, checkpoint, and direct-writer exclusion tests.

Every new test must be green before this step is considered finished.

## Acceptance criteria

- `plan_tool/detail.py:generate_detail()` derives include-regeneration work only from durable step-6 requests.
- Several requests for one destination produce one regenerated detail.
- A pending destination regenerates even when its current detail exists.
- A request whose step or intended artifact no longer matches the plan changes no files.
- Generated output that defers a requested include concept cannot complete the transition.
- Successful completion adds each requested concept to the exact destination step’s `concept_ids`.
- Successful completion leaves the destination in `StepScope.COMMITTED` and removes the concept from parked plan sections.
- The matching include requests and retained non-delivery records disappear only in the transaction that publishes replacement detail and committed ownership.
- The completed concept tree passes `validate_concept_accounting_candidate()` without using the pending-include exception.
- The stored plan fingerprint covers the final rendered plan and final ordered detail bytes.
- A failed or incomplete regeneration retains the prior details, parked plan effects, retained records, and requests.
- A restored transaction failure returns not-written results and preserves the original generation.
- A rollback failure returns not-written results with every uncertain path reported by the publication authority.
- Concurrent and serial regeneration produce the same ordered candidate and durable state.
- Dry-run performs no backend call, transaction, checkpoint change, or filesystem mutation.
- The concept-backed completion path performs no direct `save_concepts()` or separate plan-pointer write.
- All new tests in `tests/test_concept_sync.py` and `tests/test_detail.py` pass.

## References

- [Python os — Miscellaneous operating system interfaces](https://docs.python.org/3.13/library/os.html) — Review replacement, synchronization, and durability primitives used by the prerequisite publication transaction.
- [pytest API and Built-in Fixtures](https://docs.pytest.org/en/stable/builtin.html) — Use temporary paths and injected failure seams to verify restoration, uncertainty, and no-write behavior.

## Deferred

- Pending-state completeness findings — step 8 updates `plan_tool/review.py:check_concept_coverage()` and completeness reporting for valid, malformed, and stale requests.
- Split, merge, scope-out, and artifact-move transforms — `concept-remediation-3b-lifecycle-publication` updates requests and non-delivery routing during structural changes.
- Create-time restoration and the full lifecycle sequence — `concept-remediation-3c-seed-restoration` restores machine-readable accounting and proves the end-to-end conservation flow.
- General transaction internals — `concept-remediation-1-publication-transactions` owns staging, journals, locks, durability, recovery, and operator-directed rollback-failure handling.
