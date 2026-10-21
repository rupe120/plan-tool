# Step 6 — Persist pending include regeneration requests

## Summary

This step adds a durable `IncludeRegenerationRequest` collection to `plan_tool/concept_tree.py:ConceptTree` and allows scoped review to create the exact pending state for a reviewed `defer|wont_do -> include` transition. `plan_tool/concept_review.py` validates the transition intent, while `plan_tool/concept_sync.py:synchronize_concepts()` persists the request and retains the approved non-delivery record and parked plan effect. The key design decision is to store regeneration intent separately from both the reviewed concept decision and the retained non-delivery record. On green, interruption after review cannot lose the requested destination, and no parked accounting is removed before step 7 publishes replacement delivery.

## Table of Contents

- [Summary](#summary) — Overview of durable pending-include intent and preserved parked accounting.
- [Why](#why) — Why an approved include decision cannot immediately remove non-delivery state.
- [Input](#input) — Dependency-owned records and validation rules consumed by this step.
- [Files (creates vs edits)](#files-creates-vs-edits) — Production, contract, documentation, and test files changed.
- [Implementation](#implementation) — Request shape, transition rules, validation, and publication behavior.
- [Tests](#tests) — Structural, review, synchronization, CLI, and contract cases.
- [Acceptance criteria](#acceptance-criteria) — Observable conditions that define completion.
- [References](#references) — Primary JSON, filesystem, and testing guidance.
- [Deferred](#deferred) — Regeneration execution, completion, and completeness reporting left to later steps.

## Why

A reviewed change from `defer` or `wont_do` to `include` cannot remove its approved non-delivery record until replacement detail is durable, but retaining that record without a separate request makes the state look contradictory and loses the exact destination after interruption. Step 5 deliberately rejects this transition because `plan_tool/concept_review.py` and `plan_tool/concept_sync.py` cannot yet distinguish effective parked accounting from reviewed include intent. This step adds that distinction and persists the exact regeneration target while keeping the prior record and plan effect in force.

## Input

- **Step 2 output:** Use step 2's planned `NonDeliveryRecord` collection and stable `record_id`. The pending request refers to a retained record; it does not copy or replace its approved evidence and origin.
- **Step 4 output:** Extend `plan_tool/concept_tree.py:validate_concept_accounting_candidate()` with one narrow valid-pending exception. Keep structural loading separate from plan-aware publication validation.
- **Step 5 output:** Use the record-aware review operation, approval-sensitive comparison, TTY confirmation, approved-record routing, and original-versus-reviewed snapshot roles supplied by step 5.
- **Concept sidecar:** Extend `plan_tool/concept_tree.py:ConceptTree`, `_decode_tree()`, `_validate_tree()`, `load_concepts()`, and `save_concepts()` without weakening duplicate-key rejection or atomic replacement.
- **Synchronization:** `plan_tool/concept_sync.py:synchronize_concepts()` remains the only writer used by `plan_tool/cli/scope_review_cmd.py:cmd_scope_review()`.
- **Publication limit:** This step persists pending work but does not regenerate detail, remove requests, remove retained records, or claim committed delivery. Step 7 owns those operations.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `plan_tool/concept_tree.py` — Add the persisted include-regeneration request type and collection, schema compatibility, structural checks, deterministic request ordering, and plan-aware pending-state validation.
  - `plan_tool/concept_review.py` — Allow an explicitly reviewed include transition only when it carries a complete request set for the retained approved records.
  - `plan_tool/concept_sync.py` — Preserve the retained record’s parked effect, validate request routing against the candidate plan, and persist the pending state without removing accounting.
  - `plan_tool/data_contract.py` — Register the nested request dataclass in `persisted_dataclass_contracts()`.
  - `plan_tool/cli/scope_review_cmd.py` — Collect and display exact record-to-destination mappings before the existing TTY confirmation.
  - `DATA_CONTRACT.md` — Extend the `Concept sidecar` contract with the request collection, fields, uniqueness, compatibility, and lifecycle rules.
  - `docs/cli/scope-review.md` — Regenerate the command reference after changing the pending-include help or options.
  - `tests/test_concept_tree.py` — Cover request persistence, strict decoding, compatibility, ordering, and semantic validation.
  - `tests/test_concept_review.py` — Cover complete pending transitions, bare-include rejection, request scope, and copy-on-write failure.
  - `tests/test_concept_sync.py` — Cover parked-effect preservation, invalid-state refusal, persistence, and rollback.
  - `tests/test_data_contract.py` — Extend runtime-field and documentation drift checks to the request type.
  - `tests/cli/test_scope_review_cmd.py` — Cover target collection, confirmation display, cancellation, exits, and durable results.
  - `tests/cli/test_cli_reference.py` — Assert the generated reference documents pending include regeneration.

## Implementation

The foundational logic is: **an approved include intent may coexist with approved non-delivery only when complete, exact regeneration requests retain that non-delivery as the effective state until replacement delivery commits.**

- **Add one explicit request type.** Add a dataclass such as `plan_tool/concept_tree.py:IncludeRegenerationRequest` and an ordered `include_regeneration_requests` collection on `ConceptTree`. Each request should contain:
  - the exact `concept_id`;
  - the retained `record_id`;
  - one positive destination step ID;
  - the intended current detail `artifact_ref`;
  - `reviewed_mapping_digest`, a domain-tagged digest binding the exact concept,
    retained record, destination step, and artifact shown at confirmation.

  Keep the request small. It schedules work and does not repeat rationale, origin, disposition, approval, or generated detail content.

- **Use a composite request key and a separate review binding.** Treat `(concept_id, record_id, destination_step_id)` as the request’s logical key. Reject repeated keys, including rows that disagree only on `artifact_ref`. The request key schedules work; `reviewed_mapping_digest` proves that the exact target mapping was confirmed and must match recomputation before publication or resume.

- **Pin mapping-digest bytes.** Compute the mapping digest with ASCII domain tag `plan-tool/include-regeneration-review/v1` plus NUL, followed in order by `concept_id`, `record_id`, the destination step ID rendered as canonical ASCII decimal, and `artifact_ref`. Frame every value using the same ASCII byte-length, NUL, UTF-8 bytes, NUL rule as the record and semantic-review digests, then return lowercase SHA-256. For concept `"a" * 64`, record `"b" * 64`, destination `7`, and artifact `docs/implementation-plans/plan-details/sample/07-example.md`, pin `0cad375d646b9dd125060b74f10c05df583565da387681ffe9c0b1dc59aeb047` as the golden digest.

- **Keep stale mappings diagnosable.** Structural decoding validates digest shape but permits a missing or mismatched mapping digest. Candidate publication and resume reject it, while completeness reports its exact request identity instead of collapsing the sidecar into a generic parse failure.

- **Bump and decode the sidecar schema deliberately.** Advance `plan_tool/concept_tree.py:CONCEPTS_SCHEMA_VERSION` because `ConceptTree` gains a persisted field. Current-schema JSON must contain the complete request collection. Preserve the earlier compatibility paths supplied by step 2:
  - version-1 sidecars normalize with empty non-delivery and request collections;
  - the step-2 schema normalizes with its records intact and an empty request collection;
  - `save_concepts()` always emits the new complete shape.

  Compatibility loading must not invent requests from decisions, record routes, titles, or prose.

- **Keep structural validation diagnostic-friendly.** Extend `plan_tool/concept_tree.py:_decode_tree()` and `_validate_tree()` to enforce exact fields, valid identifier syntax, positive non-boolean step IDs, bounded artifact references, and unique composite keys. Allow structurally valid requests with unknown concepts, records, steps, or artifacts to load so step 8 can diagnose durable corruption.

- **Validate the pending combination at publication.** Extend `plan_tool/concept_tree.py:validate_concept_accounting_candidate()` so a valid pending concept has all of these properties:
  - its reviewed intent is approved `include`;
  - it still has one or more approved retained `defer` or `wont_do` records;
  - every retained approved record for that concept has at least one request;
  - every request names that concept and one of its retained records;
  - every destination names a current step;
  - every `artifact_ref` is the exact intended detail artifact for that destination under the existing artifact-reference contract;
  - no committed owner already claims replacement delivery.

  Reject missing, extra, duplicate, ambiguous, or dangling mappings before publication. Continue rejecting an include decision with retained non-delivery when this exact request-backed exception is not satisfied.

- **Bind target approval explicitly.** The operator approves the include transition through step 5’s record-aware review path, and that same positive TTY confirmation stores the mapping digest for every displayed request. The request needs no free-form rationale or separate state machine, but an absent or mismatched mapping digest is unreviewed/stale and cannot be published or resumed.

- **Require destination closure.** Before confirmation, reject a target step shared with any other effectively parked concept unless that concept has a complete include request in the same closed reviewed batch. This prevents committing a destination from creating delivery/non-delivery contradictions for an unrelated parked concept.

- **Support reviewed cancellation and replacement.** The same TTY-only review command can withdraw a pending include by restoring the node's effective retained disposition and atomically removing its requests while keeping the approved records, or replace its targets by displaying and approving a complete new mapping set and digest. Declined, unattended, partial, or stale cancellation/replacement writes nothing.

- **Require complete transition input.** Extend the record-aware operation in `plan_tool/concept_review.py` to accept request proposals with an include decision. Validate the complete concept, record, and request scope before changing a deep copy:
  - requests may name only concepts in the requested scope;
  - each request must name an approved retained record for the same concept;
  - every included concept’s retained approved records must be covered;
  - parked decisions without an include transition must not gain requests;
  - repeated or incomplete mappings reject the whole operation.

  Preserve step 5’s rule that failures leave concepts, records, requests, and review states unchanged.

- **Keep exact target selection explicit.** `plan_tool/cli/scope_review_cmd.py:cmd_scope_review()` has the current `Plan`, so it should collect a record-to-destination mapping instead of asking the review layer to guess. One suitable CLI shape is a repeatable typed option modeled on `_decision()`, such as `--regenerate RECORD_ID=STEP_ID`; the implementer may choose an equally explicit spelling. Derive the intended artifact only from the selected current step and the established artifact contract, never from a title or likely filename.

- **Show the transition before confirmation.** Add each concept ID, retained record ID and disposition, destination step, and intended artifact to the facts displayed by `cmd_scope_review()`. Only the existing positive TTY confirmation may approve and publish the include intent. Non-TTY input, EOF, interruption, or decline must write neither the plan nor `concepts.json`.

- **Persist intent and request together.** Pass one reviewed candidate containing both the approved include intent and complete requests to `plan_tool/concept_sync.py:synchronize_concepts()`. Do not save requests separately from the concept tree.

- **Keep parked accounting effective.** Update the approved-record selection used by `plan_tool/concept_sync.py:render_scope_decisions()` and `_mapped_scopes()` so a valid pending include still renders and applies the retained record’s `defer` or `wont_do` disposition. The node’s `include` value is reviewed future intent, not current delivery, until step 7 completes the request.

- **Keep the exception narrow.** A concept decision and record disposition may disagree only for a valid request-backed pending include. Ordinary mismatches, requests attached to `defer` or `wont_do`, requests without retained approved records, and committed ownership during the pending state remain invalid.

- **Preserve synchronization ordering.** In `plan_tool/concept_sync.py:synchronize_concepts()`, compare durable state with `original_tree`, prepare the effective parked mapping, build the candidate plan, validate the full pending state, then fingerprint and serialize. Invalid pending state returns `SyncStatus.INVALID_STATE` before either publisher call; source divergence and mapping conflicts keep their existing statuses.

- **Preserve failure state.** If synchronized publication fails and restoration succeeds, the original decision, records, requests, plan sections, and step scopes remain durable. Do not report that a request was queued unless the sidecar and parked plan generation were successfully published.

- **Regenerate CLI documentation.** Update `plan_tool/cli/scope_review_cmd.py:register()` to explain that include transitions require exact regeneration targets and remain parked until detail regeneration completes. Regenerate `docs/cli/scope-review.md` through `plan_tool.cli_reference`; do not hand-edit generated usage or option tables.

## Tests

- `tests/test_concept_tree.py:test_include_regeneration_request_round_trips_exactly` — save and load preserve every request field and collection order.
- `tests/test_concept_tree.py:test_prior_schema_defaults_include_requests_to_empty` — supported older sidecars load without fabricated pending work.
- `tests/test_concept_tree.py:test_current_schema_requires_include_request_collection` — the new schema rejects a missing top-level request field.
- `tests/test_concept_tree.py:test_include_request_rejects_unknown_fields_and_invalid_types` — strict decoding rejects extra keys, malformed IDs, booleans, non-positive steps, and invalid references.
- `tests/test_concept_tree.py:test_include_request_rejects_duplicate_composite_key` — repeated concept, record, and destination keys are invalid even when artifacts differ.
- `tests/test_concept_tree.py:test_structurally_dangling_include_request_loads` — unknown cross-record references remain available for diagnostics.
- `tests/test_concept_tree.py:test_publication_validation_accepts_complete_pending_include` — approved intent, retained approved records, and exact requests form the one valid mismatch exception.
- `tests/test_concept_tree.py:test_publication_validation_rejects_bare_include_with_retained_record` — an include intent without requests remains invalid.
- `tests/test_concept_tree.py:test_publication_validation_rejects_request_without_retained_record` — a request cannot stand in for approved parked accounting.
- `tests/test_concept_tree.py:test_publication_validation_rejects_incomplete_retained_record_coverage` — every retained approved record for the concept has at least one target.
- `tests/test_concept_tree.py:test_publication_validation_rejects_unknown_destination_or_artifact` — dangling or mismatched plan routing cannot be published.
- `tests/test_concept_tree.py:test_publication_validation_rejects_pending_include_with_committed_owner` — pending regeneration cannot also claim completed delivery.
- `tests/test_concept_review.py:test_record_review_creates_complete_pending_include` — explicit include plus complete target mappings updates one copied candidate.
- `tests/test_concept_review.py:test_record_review_rejects_include_without_regeneration_mapping` — a bare include cannot bypass pending-state creation.
- `tests/test_concept_review.py:test_record_review_rejects_request_outside_scope` — requests may name only scoped concepts and their retained records.
- `tests/test_concept_review.py:test_record_review_rejects_partial_request_set_atomically` — incomplete target input leaves concepts, records, requests, and approvals unchanged.
- `tests/test_concept_review.py:test_parked_review_does_not_create_include_request` — ordinary defer and `wont_do` review remains request-free.
- `tests/test_concept_sync.py:test_sync_persists_include_intent_request_and_retained_record` — successful synchronization writes the complete pending state together.
- `tests/test_concept_sync.py:test_sync_pending_include_preserves_parked_plan_effect` — sections and step scopes continue to reflect the retained disposition.
- `tests/test_concept_sync.py:test_sync_rejects_invalid_pending_request_without_writes` — invalid request state returns `SyncStatus.INVALID_STATE` before publication.
- `tests/test_concept_sync.py:test_sync_pending_publication_failure_restores_original_generation` — restored failure leaves the original plan and sidecar state durable.
- `tests/test_concept_sync.py:test_sync_deduplicates_pending_parked_rendering` — several requests or retained occurrences do not duplicate one concept’s parked section entry.
- `tests/test_data_contract.py:test_include_regeneration_contract_discovers_runtime_fields` — the registered contract matches the request dataclass fields.
- `tests/test_data_contract.py:test_include_regeneration_contract_is_documented` — the request fields, uniqueness, compatibility, and lifecycle rules appear in `DATA_CONTRACT.md`.
- `tests/cli/test_scope_review_cmd.py:test_scope_review_include_collects_exact_regeneration_target` — the CLI maps a retained record to a current step and intended artifact.
- `tests/cli/test_scope_review_cmd.py:test_scope_review_displays_pending_transition_before_confirmation` — confirmation shows the concept, record, disposition, destination, and artifact.
- `tests/cli/test_scope_review_cmd.py:test_scope_review_include_without_target_returns_invalid_state` — missing target input returns exit 4 with no writes.
- `tests/cli/test_scope_review_cmd.py:test_scope_review_pending_include_tty_confirmation_persists_request` — positive TTY confirmation publishes the pending state and preserves parked plan effects.
- `tests/cli/test_scope_review_cmd.py:test_scope_review_pending_include_cancel_paths_write_nothing` — decline, EOF, interruption, and non-TTY input preserve both artifacts.
- `tests/cli/test_cli_reference.py:test_scope_review_reference_documents_pending_include_regeneration` — generated help explains exact targets and the still-parked state.

### Test-creation order (feature step)

1. Add request-shape, strict-decoding, compatibility, round-trip, and duplicate-key tests with `plan_tool/concept_tree.py:IncludeRegenerationRequest`.
2. Add direct publication-validation tests for the complete pending state and every invalid combination.
3. Add copy-on-write review tests for complete, missing, partial, duplicate, and out-of-scope request payloads.
4. Add synchronization tests for request persistence, effective parked routing, invalid-state refusal, and restored publication failure.
5. Add CLI target collection, displayed-facts, TTY confirmation, cancellation, and exit-code tests.
6. Register and document the request contract, then regenerate `docs/cli/scope-review.md` and run the drift assertions.

Every new test must be green before this step is considered finished.

## Acceptance criteria

- `plan_tool/concept_tree.py:ConceptTree` persists an ordered `include_regeneration_requests` collection.
- Each request stores an exact concept ID, retained non-delivery record ID, positive destination step ID, and intended detail artifact reference.
- Supported older sidecars load with an empty request collection and never infer pending work.
- Structurally valid dangling requests load for diagnostics, while new publication rejects their unknown or inconsistent references.
- An approved include intent may retain approved non-delivery only when a complete request set covers every retained approved record for that concept.
- A bare include, missing retained record, partial request set, unknown destination, mismatched artifact, or committed owner makes the candidate invalid.
- `plan_tool/concept_review.py` prepares pending transitions on a copy and leaves its input unchanged after any rejected request.
- `plan_tool/cli/scope_review_cmd.py:cmd_scope_review()` requires exact regeneration targets and displays them before TTY confirmation.
- Non-TTY execution, decline, EOF, and interruption publish no include intent or request.
- `plan_tool/concept_sync.py:synchronize_concepts()` persists the include intent, requests, and retained records together while keeping the plan’s parked sections and scopes effective.
- Invalid pending state returns `SyncStatus.INVALID_STATE` before either publisher call.
- A restored publication failure preserves the original plan and concept sidecar generation.
- `plan_tool/data_contract.py:persisted_dataclass_contracts()`, `DATA_CONTRACT.md`, and the runtime request dataclass describe the same persisted fields.
- `docs/cli/scope-review.md` matches `plan_tool.cli_reference.render_reference()`.
- All new tests in `tests/test_concept_tree.py`, `tests/test_concept_review.py`, `tests/test_concept_sync.py`, `tests/test_data_contract.py`, `tests/cli/test_scope_review_cmd.py`, and `tests/cli/test_cli_reference.py` pass.

## References

- [RFC 8259: The JavaScript Object Notation Data Interchange Format](https://www.rfc-editor.org/rfc/rfc8259.html) — Apply strict object-member and interoperability rules to the expanded sidecar.
- [Python json — JSON encoder and decoder](https://docs.python.org/3.13/library/json.html) — Preserve duplicate-key detection and controlled decoding across schema versions.
- [Python os — Miscellaneous operating system interfaces](https://docs.python.org/3.13/library/os.html) — Preserve the existing atomic replacement and restoration behavior during synchronized publication.
- [Pydantic Validators](https://docs.pydantic.dev/latest/concepts/validators/) — Follow cross-field validation principles when checking requests against the candidate plan.
- [pytest API and Built-in Fixtures](https://docs.pytest.org/en/stable/builtin.html) — Use temporary paths, monkeypatching, and stream fixtures for no-write and TTY cases.

## Deferred

- Regeneration scheduling and resume — step 7 reads pending requests, groups them by destination step, and resumes detail authoring.
- Transactional completion — step 7 publishes regenerated detail, committed plan accounting, request removal, and retained-record removal as one recoverable generation.
- Pending-state completeness findings — step 8 validates durable pending combinations during `check_concept_coverage()` and reports malformed or stale requests.
- Split, merge, scope-out, and artifact-move request transforms — `concept-remediation-3b-lifecycle-publication` updates pending routing during later lifecycle operations.
- Create-time restoration of pending accounting — `concept-remediation-3c-seed-restoration` owns restoration from machine-readable seeds.
