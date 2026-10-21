> **Auto-archived**: this plan was swept on 2026-08-18 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 4 — Map immutable-evidence storage results to redacted receipt lifecycle evidence

## Summary

Create `plan_tool/roadmap_escalation_run.py` as the receipt-creation runner that turns one selection result and one opaque storage result into a safe typed command result. Extend `plan_tool/run_log.py` with closed receipt-preflight and terminal-result events, then document and register those persisted shapes. The key decision is that returned `existing` bytes are untrusted until the receipt contract validates them against the candidate. When green, creation has a fixed exit-status map, redacted lifecycle evidence, and a defined recovery result when telemetry cannot be persisted.

## Table of Contents

- [Summary](#summary) — Reviewer-level outcome and affected modules.
- [Table of Contents](#table-of-contents) — Links to each section.
- [Why](#why) — Why opaque storage results need receipt-specific meaning.
- [Input](#input) — Upstream selection, receipt, storage, and logging contracts.
- [Files (creates vs edits)](#files-creates-vs-edits) — New runner files and required contract edits.
- [Implementation](#implementation) — Outcome mapping, telemetry ordering, redaction, and recovery rules.
- [Tests](#tests) — Focused lifecycle and storage-result coverage.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Test-fixture references.
- [Applicable guardrails](#applicable-guardrails) — Scope limits that bind this runner.
- [Deferred](#deferred) — CLI, views, storage internals, and broader routing left outside this step.

## Why

The immutable-evidence prerequisite can create a final or return opaque existing bytes, but it cannot determine whether those bytes are a valid reusable receipt, a hash collision, or invalid evidence. Without this runner, receipt creation has no safe lifecycle result, process status, or recovery path when run-log persistence fails. This step supplies that boundary without giving receipt creation authority to alter canonical roadmap state.

## Input

- **Step 1 selector outcome:** Consume step 1’s typed malformed-syntax or unknown-stage outcome without inspecting exception text, then a selector value only when both checks succeed. The runner maps those outcomes to the redacted rows 2 and 2b before it can start receipt admission.

- **Step 2 selection outcome:** Consume step 2’s outer receipt-safe selector admission, then its total selected-artifact result for a safe selector and only its resolved safe fields. The runner owns the outer creation ordering; do not recreate the selected-artifact selection policy here.

- **Step 3 receipt contract:** Consume step 3’s candidate construction, strict parsing, identity validation, and selector-derived source-path comparison. The runner must not rebuild receipt schema rules.

- **Immutable storage result:** Treat the prerequisite’s `created`, `existing`, `invalid-input`, and `write-failed` outcomes as opaque facts. The runner supplies one namespace, final name, and sealed candidate bytes; it does not inspect storage paths or enumerate finals.

- **Run-log boundary:** `plan_tool/run_log.py:RunLogWriter` can fail from `start()`, `_emit`, or `run_end` while persisting telemetry. Receipt publication must therefore depend on successful startup and preflight logging, and later logging failures need their own fixed command result.

## Files (creates vs edits)

- **New files:**
  - `plan_tool/roadmap_escalation_run.py` — Typed receipt-creation result, preflight-to-storage orchestration, outcome mapping, and telemetry-failure handling.
  - `tests/test_roadmap_escalation_run.py` — Direct runner tests with controlled storage and logging outcomes.

- **Existing files (edits only):**
  - `plan_tool/run_log.py` — Add closed `RoadmapEscalationPreflight` and `RoadmapEscalationResult` event types, typed `RunLogWriter` emitters, and `Event` union membership without changing existing event behavior.
  - `tests/test_run_log.py` — Cover event fields, closed vocabularies, nullability, redaction, and appendability.
  - `DATA_CONTRACT.md` — Document the two event shapes, ordering, allowed values, nullability, and the process-status map.
  - `plan_tool/data_contract.py` — Required footprint addition: register the two new persisted event dataclasses in `persisted_dataclass_contracts()` so the existing contract drift checks cover the new `DATA_CONTRACT.md` sections.

## Implementation

- **Foundational logic:** Map one immutable-evidence publication result to one validated, redacted receipt lifecycle result.

- **Keep receipt creation in one owner.** Add a public runner in `plan_tool/roadmap_escalation_run.py` that owns selection handoff, candidate publication, validation of returned existing bytes, lifecycle logging, and the typed result consumed by step 6. Keep CLI parsing and rendering out of this module.

- **Validate the roadmap root first.** At the runner boundary, validate the supplied roadmap root before opening a log, reading a selected artifact, or calling storage. An invalid slug returns the normal usage result with status `2` and leaves no lifecycle record, run log, source access, or evidence access.

- **Classify the shared selector before receipt admission.** After root validation and redacted startup, consume step 1’s typed selector outcome. Map malformed syntax to row-2 `malformed-selector` and a syntactically valid unknown configured stage to row-2 `unknown-artifact`, with no resolved field and without parsing an exception message. Only after a selector value exists, call step 2’s pure receipt-safe selector admission before validating the reason, obtaining a source snapshot, or invoking the selected-artifact predicate. An unsafe selector emits the redacted row-2b `identifier-rejected` lifecycle with no resolved selector field; the later predicate may return `identifier-rejected` only for an unsafe parsed row target.

- **Use the receipt contract as the only evidence interpreter.** Publish the step 3 candidate through the immutable-evidence prerequisite. For an `existing` response, parse and validate its bytes through step 3, then require its final name, stored identity, recomputed identity, semantic preimage, and selector-derived relative source path to match the candidate before returning `reused`.

- **Classify reusable view freshness in this runner.** Return `fresh`, `resolved`, `source-unavailable`, or `invalid` with a structurally valid receipt only for the first three. A missing or unreadable selected source is `source-unavailable`: keep safe receipt identity/selector/reason metadata visible, suppress its handoff, and keep it distinct from readable stale or selection-ineligible `resolved` evidence and malformed `invalid` evidence.

- **Separate reuse, collision, and invalid evidence.** Return `collision` only for a schema-valid but semantically different receipt under the candidate identity. Return `invalid-existing-receipt` for malformed UTF-8 or JSON, duplicate members, invalid schema or identifier values, identity mismatch, final-name mismatch, or source-path mismatch. Neither outcome receives a receipt identity or handoff.

- **Use one closed process-status map.**

  | command result | status |
  | --- | ---: |
  | `created`, `reused` | 0 |
  | `preflight-rejected` | 2 |
  | `storage-rejected`, `collision`, `invalid-existing-receipt`, `write-failed`, `telemetry-unavailable` | 1 |
  | `interrupted` | 130 |

- **Preserve the storage outcome distinctions and interruption phases.** Map prerequisite `invalid-input` to `storage-rejected` and `write-failed` to `write-failed`. An interruption before `RunLogWriter.start()` returns is status `130`, does not call storage, and promises no receipt preflight/result/run-end lifecycle; a partially persisted generic `run_start` or in-flight record remains the existing writer’s bookkeeping rather than receipt telemetry. After startup returns, catch `KeyboardInterrupt` as `interrupted`: when it arrives between receipt-event appends, emit an all-null `interrupted` preflight before selection resolves or preserve another returned preflight verdict, then emit the `interrupted` terminal result and `run_end` with null identity and handoff. When it arrives inside a receipt preflight or result append, return status `130` with null identity/handoff, do not retry or append a compensating receipt result, make no exact-pair claim because the interrupted append may already have persisted, and complete best-effort generic writer cleanup with `run_end`. When it arrives inside the trailing `run_end` append, the result append already durably logged the real outcome and, for `created` or `reused`, its real identity/handoff; catch that `KeyboardInterrupt` locally and return the already-logged result unchanged rather than status `130`. A preflight- or result-phase interruption after storage may have created a final still has null identity and remains null in that invocation; a later retry either creates or validates and reuses the final. If the sink fails while writing a later interruption record, return the existing fixed redacted `telemetry-unavailable` status-`1` result instead of claiming a lifecycle it cannot persist.

- **Add two receipt-specific event types in `plan_tool/run_log.py`.** `RoadmapEscalationPreflight` records only resolved receipt-safe selector and target identifiers, a closed reason after it validates, the selected-artifact digest after it is available, and one closed preflight verdict, including lifecycle-only `interrupted`. `RoadmapEscalationResult` records one closed terminal outcome plus nullable receipt identity and handoff facts.

- **Make preflight fields monotonic.** Populate a field only after its prerequisite succeeds. A rejected raw selector or reason must never be copied into an event as a substitute value, and every later unresolved field remains `null`. The pre-selection `interrupted` preflight is therefore all-null; it is a lifecycle terminality signal, not an eligibility verdict.

- **Use typed emitters without an extension bag.** Add dedicated `RunLogWriter` methods for the new events. Their signatures must not accept arbitrary `**extra` values, so callers have no route to attach reviewer prose or exception text.

- **Keep the envelope structurally redacted.** Open `RunLogWriter.start` with static argv and flags that name only the receipt mode, not raw selector or reason inputs. Do not place raw input, feedback request text, target prose, artifact bytes, receipt bytes, exception prose, source briefs, or repository content in startup fields, writer context, event fields, or terminal records.

- **Gate publication on telemetry availability.** A `RunLogWriter.start()` failure or preflight-event append failure returns `telemetry-unavailable` with status `1` and must block the storage call. An interruption before `start()` returns is instead status `130`, with no storage call and no promised receipt lifecycle; this step does not clean up generic startup bookkeeping that the writer may have persisted before its return. This prevents a durable receipt from being created before its opening lifecycle facts exist.

- **Contain post-publication telemetry failures.** If the terminal-result append or `run_end` fails after storage may have created a final, or the sink fails while recording an `interrupted` sequence, return `telemetry-unavailable` with status `1`, null receipt identity, null handoff, and no exception prose. Do not invent a persisted `telemetry-unavailable` event when its defining problem is an unreliable sink.

- **Make retry the recovery path.** A repeat of an identical request after a post-publication telemetry failure or an interruption that may follow storage validates the existing immutable final and, when the sink works, records a complete `reused` lifecycle. The exact preflight/result pair invariant applies only when telemetry is available and each receipt-event append returns normally.

- **Preserve the run-log contract shape.** Register the event classes in `plan_tool/run_log.py:Event`; retain `RUN_LOG_SCHEMA_VERSION` unless the implemented JSONL shape proves an incompatible change. Register both classes in `plan_tool/data_contract.py:persisted_dataclass_contracts()` and add matching sections to `DATA_CONTRACT.md`.

- **Keep this runner receipt-only.** It may read the selected artifact through the step 2 boundary and use the immutable-evidence API. It must not invoke a backend, open a canonical roadmap writer, enumerate evidence, or modify feedback, seeds, drafts, or Git state.

## Tests

### Tests for this step

- `tests/test_run_log.py::test_escalation_events_have_closed_fields_and_monotonic_nullability` — Verifies each new event exposes only documented fields and unresolved facts remain `null`.

- `tests/test_run_log.py::test_escalation_writer_methods_reject_unknown_vocabulary_and_reviewer_content` — Rejects invalid verdicts or outcomes and proves the typed methods have no prose-bearing extension parameter.

- `tests/test_run_log.py::test_escalation_events_are_event_union_members` — Confirms both discriminators serialize through `append_event`.

- `tests/test_roadmap_escalation_run.py::test_created_receipt_records_one_redacted_lifecycle` — Maps a created storage result to `created`, status `0`, one preflight/result pair, and no canonical roadmap mutation.

- `tests/test_roadmap_escalation_run.py::test_existing_receipt_is_reused_only_after_exact_validation` — Requires strict receipt validation, identity binding, semantic-preimage equality, and selector-derived path equality before `reused`.

- `tests/cli/test_roadmap_cmd.py::test_escalation_view_keeps_valid_receipt_visible_when_source_is_unavailable` — Proves a removed selected source renders the distinct safe-metadata-only `source-unavailable` view with no handoff.

- `tests/test_roadmap_escalation_run.py::test_valid_different_existing_receipt_is_collision` — Proves a valid but different semantic preimage is not reused.

- `tests/test_roadmap_escalation_run.py::test_invalid_existing_receipt_has_no_handoff` — Covers malformed, duplicate-member, unsafe-identifier, identity-invalid, final-name-mismatched, and path-mismatched bytes.

- `tests/test_roadmap_escalation_run.py::test_storage_failure_outcomes_never_report_created` — Maps `invalid-input` and `write-failed` to separate status-`1` results.

- `tests/test_roadmap_escalation_run.py::test_preflight_rejection_records_only_resolved_safe_fields` — Covers the preflight boundary and status `2` without recording raw rejected input.

- `tests/test_roadmap_escalation_run.py::test_invalid_slug_is_log_free_before_source_or_storage_access` — Proves direct callers cannot bypass root validation.

- `tests/test_roadmap_escalation_run.py::test_unsafe_selector_preflight_precedes_reason_and_source_access` — Verifies row-2b `identifier-rejected` has no resolved selector field and reaches neither reason validation, source access, nor selected-artifact selection.

- `tests/test_roadmap_escalation_run.py::test_typed_selector_outcomes_map_to_distinct_redacted_preflights` — Verifies malformed syntax and unknown configured stage reach rows 2 and 2b without error-text parsing, resolved fields, reason validation, or source access.

- `tests/test_roadmap_escalation_run.py::test_telemetry_setup_or_preflight_failure_blocks_publication` — Returns `telemetry-unavailable` before calling storage.

- `tests/test_roadmap_escalation_run.py::test_post_publication_telemetry_failure_returns_retryable_redacted_result` — Covers terminal-event and `run_end` failures, then verifies a retry records `reused`.

- `tests/test_roadmap_escalation_run.py::test_interruption_before_start_blocks_publication_without_promising_receipt_lifecycle` — Returns status `130` with no storage call or receipt event pair when startup has not returned, without asserting cleanup of generic writer bookkeeping.

- `tests/test_roadmap_escalation_run.py::test_interruption_records_phase_correct_lifecycle_and_null_identity` — Proves the all-null pre-selection `interrupted` preflight, preservation of a resolved preflight after later interruption, the terminal `interrupted` pair, and null identity/handoff.

- `tests/test_roadmap_escalation_run.py::test_interruption_sink_failure_is_redacted_telemetry_unavailable` — Verifies an append or `run_end` failure while recording interruption returns status `1` without inventing a terminal event.

- `tests/test_roadmap_escalation_run.py::test_interruption_inside_receipt_event_append_never_compensates_or_claims_exact_pair` — Injects `KeyboardInterrupt` after a receipt event may persist and verifies status `130`, null identity/handoff, no retry or compensating event in that invocation, and no exact-pair assertion.

- `tests/test_roadmap_escalation_run.py::test_creation_log_never_contains_raw_input_or_reviewer_content` — Uses sentinels across success and failure paths to prove structural redaction.

- `tests/test_data_contract.py::test_every_persisted_field_is_documented_in_own_section` — Verifies the new registered event fields and `DATA_CONTRACT.md` sections remain synchronized.

Every listed test must be green before this step is complete.

## Acceptance criteria

- `plan_tool/roadmap_escalation_run.py` maps every immutable-evidence result to one closed receipt result and process status.

- The runner maps step 1’s typed malformed-syntax and unknown-stage outcomes to distinct redacted selector preflights without parsing exception text or accessing source data.

- After closed selector syntax and fixed-stage recognition, the runner rejects an unsafe selector at row 2b before reason validation, source access, feedback lookup, cardinality, or row state; only a receipt-safe selector reaches the selected-artifact predicate.

- Existing opaque bytes become `reused` only after strict receipt validation and exact candidate comparison; valid semantic collisions and invalid evidence remain distinct no-handoff outcomes.

- After `RunLogWriter.start()` returns, root-valid creation with an available sink emits one redacted preflight event, one terminal result event, and one matching `run_end` record only when each receipt-event append returns normally. An interruption before startup returns is status `130` with no promised receipt lifecycle, not a cleanup guarantee for generic writer bookkeeping; an interruption between lifecycle appends emits an all-null `interrupted` preflight or preserves its resolved preflight before emitting the `interrupted` terminal pair; an interruption inside a preflight or result append returns status `130` with null identity/handoff, no compensating receipt result, no exact-pair claim, and best-effort generic writer cleanup; an interruption inside the trailing `run_end` append instead returns the already-logged terminal result unchanged.

- Startup or preflight telemetry failure prevents publication and returns `telemetry-unavailable`; post-publication telemetry failure, or a sink failure while recording interruption, returns the same redacted status without an identity or handoff.

- Retrying after a durable final lacks complete telemetry produces a complete validated `reused` lifecycle when telemetry is available.

- Receipt identity and handoff are present only for durable `created` or validated `reused` results; every other outcome retains `null`.

- `DATA_CONTRACT.md`, `plan_tool/run_log.py`, and `plan_tool/data_contract.py:persisted_dataclass_contracts()` agree on both new event contracts.

- No normal or failure path invokes a backend or changes canonical roadmap artifacts, feedback state, seed state, drafts, or Git state.

## References

- [pytest: How to monkeypatch/mock modules and environments](https://docs.pytest.org/en/stable/how-to/monkeypatch.html) — Use controlled storage and telemetry failures without depending on filesystem internals.

- [pytest: How to use temporary directories and files](https://docs.pytest.org/en/stable/how-to/tmp_path.html) — Build isolated roadmap, evidence, and run-log fixtures.

## Applicable guardrails

- **The plan’s “## Step intent”, opaque storage mapping:** Consume the prerequisite result API and map its facts; do not add another storage protocol.

- **The plan’s “## Plan intent”, receipt-only record:** Limit this runner to receipt evidence and lifecycle telemetry; do not make impact decisions or alter roadmap-owned state.

- **The plan’s “## Out of scope”, immutable-evidence storage:** Leave publication internals and evidence enumeration with the prerequisite.

- **The plan’s “## Out of scope”, local revision compatibility:** Do not alter the bounded local-revision route or its publication behavior.

- **The plan’s “## Out of scope”, identifier grammar:** Apply receipt-safe admission only at this receipt boundary.

- **The plan’s “## Out of scope”, broad workflow work:** Do not add views, routing, backend calls, or structural patches in this runner.

## Deferred

- CLI argument collection, repeated-option handling, command dispatch, and result rendering — Step 6 owns the public command surface.

- Receipt enumeration and log-free receipt views — Step 6 owns inspection behavior. The step-4 runner owns reusable cached receipt freshness classification for that view; step 6 delegates to it rather than recreating source/selection validation.

- Immutable-evidence storage internals and filesystem interleaving coverage — The storage prerequisite remains the sole owner.

- Shared orchestration with bounded local revision — The two runners have different write and lifecycle contracts and need a separately scoped refactor.

- Broader impact analysis and structural routing — A later roadmap workflow owns those decisions.
