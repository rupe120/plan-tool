# Step 4 — Persist and resume reviewed include regeneration requests

## Summary

This step turns each reviewed pending `include` transition from step 3 into durable, resumable regeneration work. `plan_tool/concept_tree.py` owns the persisted request shape, `plan_tool/concept_sync.py` validates and records requests with the reviewed transition, and `plan_tool/detail.py:generate_detail()` discovers and resumes the affected steps through its existing checkpoint flow. The key design decision is to keep the reviewed transition, the regeneration request, and the cached authoring response distinct: the concept sidecar records what must be regenerated, while the checkpoint records reusable model output. On green, an interrupted `plan-tool detail` run can continue the same reviewed transition without losing intent, using an unrelated cached response, or clearing the prior non-delivery accounting.

## Table of Contents

- [Summary](#summary) — Overview of the durable regeneration request and resume behavior.
- [Why](#why) — The gap between reviewed include intent and resumable detail work.
- [Input](#input) — Dependency-owned records and existing checkpoint contracts consumed here.
- [Files (creates vs edits)](#files-creates-vs-edits) — Source, contract, and test files changed by this step.
- [Implementation](#implementation) — Request persistence, validation, scheduling, and resume rules.
- [Tests](#tests) — Unit and command cases for durable and stale-safe resumption.
- [Acceptance criteria](#acceptance-criteria) — Observable requirements for completion.
- [References](#references) — Primary validation, canonicalization, and test guidance.
- [Deferred](#deferred) — Publication and later lifecycle transformations outside this step.

## Why

Step 3 makes a reviewed `defer|wont_do → include` request durable while retaining the approved non-delivery record, but detail regeneration still needs an exact, recoverable mapping from that request to the affected step and artifact. At HEAD, `plan_tool/detail.py:_included_deferral_step_ids()` partially demonstrates automatic regeneration through legacy `ConceptNode.source_metadata["detail_deferral_step_ids"]`, and `_detail_step_input_hash()` supports ordinary response resumption, but the checkpoint key does not identify the reviewed transition. A stopped run can therefore lose the work selection or reuse a response prepared for different accounting. Persisting the exact regeneration request and including it in the resume key closes that gap without removing the prior accounting before step 5 can publish the replacement safely.

## Input

- **Step 3 pending transition:** Consume the reviewed pending-include state produced by step 3. It contains an approved concept-level `include` request while the prior approved structured non-delivery record remains effective.
- **Step 2 non-delivery records:** Use their stable concept, record, artifact, and step-routing references. Do not recover targets from titles, Markdown, or `ConceptNode.source_metadata`.
- **Concept sidecar:** Extend the strict boundary at `plan_tool/concept_tree.py:ConceptTree`, `_decode_tree()`, `_validate_tree()`, `load_concepts()`, and `save_concepts()`. Preserve duplicate-key rejection, complete-shape validation, stale-fingerprint handling, and atomic replacement.
- **Synchronization:** Keep `plan_tool/concept_sync.py:synchronize_concepts()` as the guarded writer for the reviewed transition and its regeneration request. `original_tree` remains the compare-and-swap snapshot.
- **Detail resume:** Reuse `plan_tool/detail.py:_DETAIL_CHECKPOINT_NAME`, `_detail_step_input_hash()`, `_author_step_detail()`, and `generate_detail()`. The existing checkpoint payload remains the cached authoring response; it is not the durable transition request.
- **Target selection:** A full detail run may process every queued step. An explicit `step_id` processes only matching requests and leaves other requests pending.
- **Publication limit:** This step schedules and resumes regeneration but does not declare the replacement detail and accounting committed together. Step 5 owns verified publication, rollback, result finalization, and request completion.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `plan_tool/concept_tree.py` — add the persisted include-regeneration request shape and pure validation, grouping, and lookup helpers.
  - `plan_tool/concept_sync.py` — derive and persist exact regeneration requests from reviewed pending includes and reject inconsistent requests before publication.
  - `plan_tool/detail.py` — replace legacy metadata-based scheduling with request discovery, bind checkpoints to the selected requests, and retain recovery state until completion.
  - `plan_tool/data_contract.py` — register the new nested persisted request contract and its schema constant or compatibility rule.
  - `DATA_CONTRACT.md` — document the request fields, uniqueness rules, lifecycle, compatibility behavior, and checkpoint relationship.
  - `tests/test_concept_tree.py` — cover request round trips, validation, deterministic grouping, and compatibility.
  - `tests/test_concept_sync.py` — cover request creation with pending transitions and no-write rejection cases.
  - `tests/test_detail.py` — cover selection, interruption, checkpoint resumption, stale checkpoint refusal, concurrency, and dry-run behavior.
  - `tests/test_data_contract.py` — extend the drift guard to the request record and updated concept schema.
  - `tests/cli/test_authoring_cmds.py` — verify the existing detail command resumes queued work and reports work that remains pending.

## Implementation

The foundational logic is an **exact pending-transition-to-regeneration mapping with a transition-bound resume key**.

- **Persist the work, not the authoring response.** Add a small record under `plan_tool/concept_tree.py:ConceptTree` for each pending include regeneration. A name such as `IncludeRegenerationRequest` is suitable. It should carry enough stable references to identify the concept, retained non-delivery record, destination step, and intended detail artifact without copying mutable prose.

- **Keep one authority for intent.** Treat step 3’s reviewed pending include as the reason the request exists. The request supplies scheduling and resume routing; it must not become a second decision or approval record.

- **Use exact dependency-owned links.** Build requests only from stable concept and structured non-delivery references. Reject a pending include when its retained records do not identify a valid target, identify conflicting targets, or point outside the current plan.

- **Group work by destination step.** Several pending concepts may require the same detail to be regenerated. `plan_tool/concept_tree.py` should expose a deterministic, write-free projection that groups requests by step in plan order so `generate_detail()` invokes authoring once for that step.

- **Define strict request validity.** `plan_tool/concept_tree.py:_validate_tree()` should reject:
  - duplicate requests for the same transition and target;
  - requests whose concept or retained record is absent;
  - requests not backed by a reviewed pending include;
  - unknown or invalid step references;
  - conflicting artifact targets for one regeneration job;
  - completed or ordinary include decisions that have no retained non-delivery state.

- **Handle compatibility deliberately.** Sidecars with no pending includes should load with an empty request collection under the selected schema compatibility rule. If a step-3 sidecar contains a pending include but no request, derive one only when its exact structured links produce an unambiguous target; otherwise return an invalid-state result that tells the operator to review the transition again.

- **Persist request and transition together.** In `plan_tool/concept_sync.py:synchronize_concepts()`, prepare and validate regeneration requests before `_mapped_scopes()`, `render_scope_decisions()`, `_fingerprint()`, or either `Publisher` call. Publish the reviewed pending transition and its request in the same candidate sidecar while leaving the effective parked plan scope unchanged.

- **Preserve compare-and-swap roles.** Compare current durable state with `original_tree`. Use `reviewed_tree` only to prepare the intended transition and request candidate.

- **Replace legacy scheduling.** In `plan_tool/detail.py:generate_detail()`, replace `_included_deferral_step_ids()` and its `source_metadata` parsing with the shared request projection. Do not keep two regeneration selectors after step 2 removes `detail_deferral_step_ids`.

- **Respect explicit step selection.** With no `step_id`, add all requested destination steps to the normal work set in deterministic plan order. With `step_id=N`, process only step N’s requests; unrelated pending requests remain unchanged and visible on the next run.

- **Make requested regeneration bypass the ordinary existing-detail skip.** A matching pending request must cause the selected detail to be regenerated even when `Step.detail` is set and the current file exists. Preserve the old artifact as the current durable generation until step 5 completes publication.

- **Bind checkpoints to reviewed intent.** Extend `plan_tool/detail.py:_detail_step_input_hash()` to accept the selected request descriptors or an equivalent deterministic projection. Include their stable IDs and target references in the value passed to `compute_input_hash()`, sorted independently of sidecar list order. Do not invalidate one step’s checkpoint because an unrelated concept request changed.

- **Reject stale cached responses.** A checkpoint created before the include request, for a replaced request, or for a different request set must miss and invoke authoring again. A checkpoint with the same step inputs and exact request set may resume without another model call.

- **Keep transition checkpoints until completion.** `plan_tool/detail.py:_author_step_detail()` may continue saving a parsed response through `save_checkpoint()`. For include-triggered work, do not discard that checkpoint merely because detail bytes or a plan pointer were prepared; retain it until step 5 reports verified publication or the operator explicitly declines or disables resume.

- **Keep workers write-free for shared state.** `_generate_detail_concurrent()` may prepare per-step responses in parallel, but it must not update regeneration requests or `concepts.json`. Request validation, deterministic grouping, and later completion stay in the shared serial tail.

- **Keep dry-run read-only.** Dry-run should show which pending request caused each regeneration and render the corresponding prompt, but it must not alter concept, checkpoint, plan, detail, or archive files.

- **Expose honest command outcomes through existing results.** `DetailResult` should let `plan_tool/cli/authoring.py:cmd_detail` distinguish prepared or resumed include work from an ordinary idempotent skip. A failed attempt must produce a non-idempotent failure reason that says the reviewed request remains pending and can be resumed.

- **Do not add a second checkpoint store.** The rejected alternative is embedding cached detail bodies in `concepts.json`. That would mix tracked review intent with local, expiring authoring output and duplicate `plan_tool/checkpoint.py:Checkpoint`.

## Tests

- `test_include_regeneration_request_round_trips` in `tests/test_concept_tree.py` — the request survives `save_concepts()` and `load_concepts()` with all stable references unchanged.
- `test_include_regeneration_requests_group_by_step_deterministically` in `tests/test_concept_tree.py` — several concepts targeting one step form one ordered job.
- `test_include_regeneration_request_requires_pending_include` in `tests/test_concept_tree.py` — a request without the matching reviewed pending transition is invalid.
- `test_include_regeneration_request_rejects_unknown_links` in `tests/test_concept_tree.py` — unknown concepts, records, steps, and conflicting artifacts fail validation.
- `test_concept_sidecar_without_requests_loads_empty` in `tests/test_concept_tree.py` — a compatible non-pending sidecar loads without fabricated work.
- `test_pending_include_without_unambiguous_target_is_invalid` in `tests/test_concept_tree.py` — compatibility handling never guesses a routing link.
- `test_sync_persists_pending_include_and_regeneration_request_together` in `tests/test_concept_sync.py` — one successful synchronization writes both while preserving the parked plan effect.
- `test_sync_rejects_inconsistent_regeneration_request_without_writes` in `tests/test_concept_sync.py` — invalid routing leaves plan and sidecar unchanged.
- `test_sync_publication_failure_restores_request_and_transition` in `tests/test_concept_sync.py` — rollback retains the original pair and reports failure.
- `test_full_detail_run_discovers_all_pending_regenerations` in `tests/test_detail.py` — an unfiltered run schedules every requested destination step in plan order.
- `test_explicit_step_resumes_only_matching_regeneration` in `tests/test_detail.py` — `step_id=N` processes N and leaves unrelated requests pending.
- `test_multiple_requests_for_one_step_invoke_once` in `tests/test_detail.py` — one regenerated detail covers the complete request group for its step.
- `test_pending_request_bypasses_existing_detail_skip` in `tests/test_detail.py` — an existing detail does not suppress reviewed include regeneration.
- `test_include_checkpoint_hash_contains_exact_request_set` in `tests/test_detail.py` — changing request identity or routing changes the cache key while unrelated requests do not.
- `test_interrupted_include_regeneration_resumes_without_reinvoke` in `tests/test_detail.py` — a matching saved response is reused after restart.
- `test_stale_include_checkpoint_is_not_reused` in `tests/test_detail.py` — a checkpoint from before or from another transition causes a fresh invocation.
- `test_failed_include_regeneration_retains_request_and_checkpoint` in `tests/test_detail.py` — failed preparation leaves reviewed intent and reusable recovery state intact.
- `test_concurrent_include_regeneration_keeps_request_order` in `tests/test_detail.py` — worker completion order does not affect grouped results or shared state.
- `test_include_regeneration_dry_run_changes_nothing` in `tests/test_detail.py` — dry-run reports the cause and changes no persisted artifact.
- `test_cmd_detail_resumes_pending_include_request` in `tests/cli/test_authoring_cmds.py` — the existing command reaches queued regeneration without a new CLI flag.
- `test_cmd_detail_failed_include_reports_resumable_pending_work` in `tests/cli/test_authoring_cmds.py` — failure output is nonzero and states that the reviewed request remains pending.
- `test_include_regeneration_contract_is_registered_and_documented` in `tests/test_data_contract.py` — runtime fields, schema rules, and the `DATA_CONTRACT.md` section remain in sync.

### Test-creation order (feature step)

1. Add the persisted request round-trip, grouping, and invalid-link tests with the `plan_tool/concept_tree.py` contract.
2. Add synchronization success, invalid-state, and rollback tests with the `plan_tool/concept_sync.py` integration.
3. Add detail selection, existing-detail bypass, and one-invocation-per-step tests.
4. Add exact checkpoint-key, interrupted-resume, stale-cache, and failed-attempt retention tests.
5. Add concurrent-order and dry-run tests.
6. Add command result-routing tests in `tests/cli/test_authoring_cmds.py`.
7. Add registry and documentation drift tests in `tests/test_data_contract.py`.

Every new test must be green before this step is considered finished.

## Acceptance criteria

- A reviewed pending include is persisted with an exact regeneration request while its approved non-delivery record remains effective.
- Reloading `concepts.json` recovers the same pending requests without title or prose matching.
- Invalid, duplicate, ambiguous, or dangling regeneration requests are rejected before plan or sidecar publication.
- A full `generate_detail()` run schedules every requested destination step once in deterministic plan order.
- An explicit `step_id` processes only matching requests and leaves all other requests pending.
- A matching request regenerates its step even when the current detail file and pointer exist.
- The detail checkpoint key changes when the selected transition request changes and remains unchanged for unrelated requests.
- Restarting with a valid matching checkpoint resumes without another model call.
- Failed or interrupted regeneration retains the pending request, prior non-delivery accounting, and usable checkpoint.
- Concurrent workers do not write shared concept state, and their completion order does not change request ordering.
- Dry-run changes no plan, detail, concept, checkpoint, or archive file.
- `DATA_CONTRACT.md`, `plan_tool/data_contract.py:persisted_dataclass_contracts()`, and the runtime concept dataclasses describe the same persisted fields and schema rules.
- Focused tests in `tests/test_concept_tree.py`, `tests/test_concept_sync.py`, `tests/test_detail.py`, `tests/test_data_contract.py`, and `tests/cli/test_authoring_cmds.py` pass.

## References

- [JSON Schema Validation Draft 2020-12](https://json-schema.org/draft/2020-12/json-schema-validation) — Use its required-field, enum, uniqueness, and conditional-validation concepts when defining request validity.
- [RFC 8785: JSON Canonicalization Scheme](https://www.rfc-editor.org/rfc/rfc8785.html) — Use deterministic JSON ordering principles for the transition-bound checkpoint input.
- [pytest: How to Parametrize Fixtures and Test Functions](https://docs.pytest.org/en/stable/how-to/parametrize.html) — Use parametrized cases for invalid links, interruption points, and stale checkpoint variants.

## Deferred

- Verified detail and accounting publication — step 5 commits the replacement detail, plan pointer, request completion, and non-delivery removal as one recoverable generation.
- Split and merge request remapping — steps 7 and 8 update pending request routing alongside their structural accounting transformations.
- Scope-out creation of new non-delivery records — step 9 owns review and publication when delivery loses its final committed owner.
- Lifecycle-wide integration coverage — step 13 carries one accounting state through restoration, split, merge, scope-out, regeneration, and completeness.
