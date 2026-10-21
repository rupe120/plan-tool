> **Auto-archived**: this plan was swept on 2026-08-18 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 4 — Map immutable-evidence storage results to redacted receipt lifecycle evidence

## Summary

Add `plan_tool/roadmap_escalation_run.py` as the receipt-creation runner that turns one accepted selection and the immutable-evidence storage result into a typed, process-ready outcome. Extend `plan_tool/run_log.py` with a closed redacted preflight event and terminal result event, and document both in `DATA_CONTRACT.md`. The key decision is that `existing` storage bytes are untrusted until the receipt contract validates their identity, semantic content, and selector-derived path. After the runner validates its roadmap root, creation produces exactly one redacted preflight record, one terminal receipt result, and one matching process status without changing a canonical roadmap artifact.

## Table of Contents

- [Summary](#summary) — Reviewer-level outcome and affected modules.
- [Table of Contents](#table-of-contents) — Links to each section.
- [Why](#why) — Why storage outcomes need receipt-specific meaning.
- [Input](#input) — Upstream receipt, selection, storage, and lifecycle contracts.
- [Files (creates vs edits)](#files-creates-vs-edits) — New runner files and lifecycle-contract edits.
- [Implementation](#implementation) — Outcome mapping, validation, redaction, and process status rules.
- [Tests](#tests) — Focused storage-result and telemetry coverage.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Primary test-fixture references.
- [Applicable guardrails](#applicable-guardrails) — Scope limits that bind this runner.
- [Deferred](#deferred) — CLI, views, storage internals, and impact work left outside this step.

## Why

`plan_tool/roadmap_evidence_store.py:publish_evidence` correctly publishes or returns opaque bytes, but it cannot decide whether returned bytes are a reusable receipt, a semantic collision, or invalid evidence. Without a receipt runner, the storage outcomes have no safe command result, process status, or redacted lifecycle record. This step supplies that domain boundary while keeping the storage helper opaque and the receipt-only workflow free of canonical roadmap writes.

## Input

- **Step 2 selection outcome:** Use step 2’s public receipt-selection boundary in `plan_tool/roadmap_escalation_selection.py` as the sole source of accepted selector, target, reason, and selected-artifact facts. Do not repeat its ordered admission checks in the runner.

- **Step 3 receipt contract:** Consume step 3’s closed receipt construction, parsing, rendering, semantic-id, and final-name validation boundary in `plan_tool/roadmap_escalation.py`. The runner validates returned storage bytes through that contract; it does not recreate the schema.

- **Configured roadmap facts:** Accept injected `plan_tool/roadmap.py:RoadmapStage` data, following `plan_tool/roadmap.py:STAGES` for production, and use `plan_tool/roadmap_artifacts.py:roadmap_dir` for the storage root. The runner calls that pure helper at entry to validate `slug` before it constructs a logger, reads a selected source, or calls storage.

- **Immutable storage API:** Call only `plan_tool/roadmap_evidence_store.py:publish_evidence` with `EvidenceNamespace.ESCALATIONS`, the candidate final name, and rendered receipt bytes. Interpret `EvidencePublishResult` and its `EVIDENCE_CREATED`, `EVIDENCE_EXISTING`, `EVIDENCE_INVALID_INPUT`, and `EVIDENCE_WRITE_FAILED` values without inspecting storage paths.

- **Run-log lifecycle:** Use `plan_tool/run_log.py:RunLogWriter` for one owned creation lifecycle, calling its `start()` and `run_end()` methods. The runner must create a redacted startup record rather than passing through the CLI’s original arguments.

## Files (creates vs edits)

- **New files:**
  - `plan_tool/roadmap_escalation_run.py` — Receipt-creation runner, typed safe result, storage-result mapping, and lifecycle ownership.
  - `tests/test_roadmap_escalation_run.py` — Direct runner tests using controlled storage results and roadmap fixtures.

- **Existing files (edits only):**
  - `plan_tool/run_log.py` — Add closed `RoadmapEscalationPreflight` and `RoadmapEscalationResult` events, writer methods, and `Event` union membership.
  - `tests/test_run_log.py` — Cover event fields, vocabularies, nullability, appendability, and structural redaction.
  - `DATA_CONTRACT.md` — Document both new event shapes, their closed values, field nullability, event ordering, and process-status map.
  - `plan_tool/data_contract.py` — Required footprint addition: register the two persisted event dataclasses so the existing `DATA_CONTRACT.md` drift guard covers their fields.

## Implementation

- **Foundational logic:** Map one opaque immutable-evidence publication result to one validated receipt lifecycle outcome.

- **Keep creation in one runner.** Make `plan_tool/roadmap_escalation_run.py` own receipt creation, its typed result, and its run-log lifetime. Model its ownership boundary on `plan_tool/roadmap_revision_run.py:run_local_feedback_revision`, but do not reuse local-revision verdicts or change that runner.

- **Establish the roadmap root before any lifecycle side effect.** At the public runner entry, call `plan_tool/roadmap_artifacts.py:roadmap_dir(plans_dir, slug)` before `RunLogWriter.start`, selected-artifact access, or `publish_evidence`. Surface its invalid-slug failure through the command's standard usage path with status `2`, no lifecycle event pair, and no run log. The CLI performs the same pure check for its rendering path, but this runner check is authoritative for direct callers.

- **Treat storage bytes as untrusted.** Build a candidate only after step 2 accepts the request, then pass its final name and rendered bytes to `plan_tool/roadmap_evidence_store.py:publish_evidence`. A `created` result is successful only because the prerequisite has completed its durability contract.

- **Validate `existing` before reuse.** Parse returned bytes through step 3’s strict receipt contract, then require the requested final name, stored semantic id, recomputed semantic id, selector-derived relative stage path, and complete semantic preimage to agree with the candidate. Return `reused` only for that exact match.

- **Keep collision and invalid evidence separate.** A schema-valid existing receipt with a different semantic preimage under the candidate identity is `collision`. Malformed UTF-8, duplicate-member JSON, closed-schema failures, unsafe identifiers, invalid identity, final-name mismatch, or selector-derived path mismatch are `invalid-existing-receipt`. Neither outcome receives a handoff.

- **Map every prerequisite result explicitly.** Map `invalid-input` to `storage-rejected` and `write-failed` to `write-failed`; never report `created` after either. Catch `KeyboardInterrupt` separately as runner-owned `interrupted`, with no durable receipt identity claimed.

- **Return one process-ready result.** Expose a typed result for step 5 that carries only safe receipt facts. Its process status must remain fixed:

  | lifecycle outcome | process status |
  |---|---:|
  | `created`, `reused` | `0` |
  | `preflight-rejected` | `2` |
  | `storage-rejected`, `collision`, `invalid-existing-receipt`, `write-failed` | `1` |
  | `interrupted` | `130` |

- **Emit an exact redacted event pair.** Every root-valid creation path emits one `RoadmapEscalationPreflight` followed by one `RoadmapEscalationResult`; `RunLogWriter.run_end` records the same terminal lifecycle outcome and mapped status. Preflight rejection therefore still emits a terminal `preflight-rejected` result.

- **Make preflight evidence monotonic.** `RoadmapEscalationPreflight` records only nullable safe fields: resolved artifact key, feedback id, closed reason, selected target kind and id, raw artifact digest, and one closed verdict. Populate a field only after its prerequisite succeeds; rejected raw selector or reason input never becomes a replacement value in the event.

- **Use the plan’s closed preflight vocabulary.** The event supports only `mode-rejected`, `malformed-selector`, `unknown-artifact`, `identifier-rejected`, `reason-rejected`, `artifact-unreadable`, `artifact-unparsable`, `artifact-not-canonical`, `missing-feedback`, `duplicate-feedback`, `not-open`, `already-responded`, `missing-or-ambiguous-target`, `target-not-live-in-selected-artifact`, and `accepted`.

- **Keep terminal evidence minimal.** `RoadmapEscalationResult` records its closed outcome, nullable semantic receipt identity, and nullable handoff. The semantic identity is present only for durable `created` or validated `reused` results; all other outcomes, including interruption, retain `null`.

- **Make redaction structural.** Add typed `RunLogWriter` methods with no arbitrary extension bag for these events. Do not place raw selector text, raw reason text, feedback request text, target prose, artifact bytes, rendered receipt bytes, exception prose, or repository content in event fields, writer context, flags, or startup `argv`.

- **Start the log safely.** Only after root validation succeeds, use `RunLogWriter.start` with `command: "roadmap"` and a static receipt-creation mode. Build a redacted `argv` representation instead of forwarding user input, since `run_start` is persisted before selection can establish which values are safe.

- **Keep the runner read-only except for declared evidence and telemetry.** Do not call `plan_tool/roadmap_revision_publish.py:roadmap_writer_guard`, any roadmap writer, `plan_tool/roadmap_evidence_store.py:scan_evidence`, or a backend. The runner may read the selected artifact through the step 2 boundary and publish only through the prerequisite API.

- **Document and register the contract together.** Add `RoadmapEscalationPreflight` and `RoadmapEscalationResult` sections under `DATA_CONTRACT.md`’s run-log event catalog, then register their dataclasses in `plan_tool/data_contract.py`. This keeps field-table drift detectable by `tests/test_data_contract.py`.

## Tests

### Tests for this step

- `tests/test_run_log.py::test_escalation_lifecycle_events_have_closed_fields_and_nullability` — Verifies both event dataclasses expose only their documented safe fields and preserve nullable unresolved values.

- `tests/test_run_log.py::test_escalation_writer_methods_reject_unknown_vocabulary_and_extra_reviewer_content` — Rejects invalid preflight or terminal values and proves typed writer methods cannot accept a prose-bearing extension argument.

- `tests/test_run_log.py::test_escalation_lifecycle_events_are_appendable_event_union_members` — Confirms the new events are valid `Event` members and serialize with their fixed discriminators.

- `tests/test_roadmap_escalation_run.py::test_created_receipt_publishes_once_and_records_one_safe_event_pair` — Maps a created storage result to `created`, status `0`, one preflight/result pair, and an unchanged canonical artifact.

- `tests/test_roadmap_escalation_run.py::test_matching_existing_receipt_is_validated_before_reuse` — Returns `reused` only when the opaque bytes satisfy every receipt identity and selector-derived path check.

- `tests/test_roadmap_escalation_run.py::test_valid_different_semantic_preimage_is_a_collision` — Uses a controlled identity seam to prove a valid nonidentical existing receipt is `collision`, not reuse.

- `tests/test_roadmap_escalation_run.py::test_invalid_existing_receipt_never_receives_a_handoff` — Covers malformed, duplicate-member, identity-invalid, unsafe-identifier, final-name-mismatched, and path-mismatched existing bytes.

- `tests/test_roadmap_escalation_run.py::test_storage_rejections_and_failures_never_report_created` — Maps `invalid-input` and `write-failed` to their distinct terminal outcomes and status `1`.

- `tests/test_roadmap_escalation_run.py::test_preflight_rejection_emits_terminal_result_with_only_resolved_safe_fields` — Covers each preflight evidence boundary and confirms every rejection ends with `preflight-rejected` and status `2`.

- `tests/test_roadmap_escalation_run.py::test_invalid_slug_returns_usage_without_lifecycle_or_path_access` — Calls the public runner with separator and parent-component slugs and proves status `2`, no `RunLogWriter.start`, selected-source read, or storage call.

- `tests/test_roadmap_escalation_run.py::test_interruption_keeps_receipt_identity_null_and_returns_130` — Interrupts at the storage boundary and verifies `interrupted` is distinct from storage failure.

- `tests/test_roadmap_escalation_run.py::test_creation_log_never_contains_raw_input_or_reviewer_content` — Uses sentinel selector, reason, feedback, target prose, artifact body, receipt bytes, and exception text across success and failure paths.

- `tests/test_roadmap_escalation_run.py::test_runner_uses_only_the_opaque_storage_api_and_never_invokes_a_backend` — Confirms the runner supplies only namespace, final name, and bytes to storage and reaches no backend or canonical writer.

- `tests/test_data_contract.py` — Runs unchanged as the field-level drift gate for the two registered event sections.

Every listed test must be green before this step is complete.

## Acceptance criteria

- `plan_tool/roadmap_escalation_run.py` maps each `publish_evidence` outcome to exactly one closed receipt lifecycle result and process status.

- An existing opaque payload becomes `reused` only after strict receipt validation, exact semantic-preimage comparison, final-name binding, and selector-derived source-path validation.

- A valid nonidentical existing payload is `collision`; malformed or invalid existing payload is `invalid-existing-receipt`; neither result exposes a handoff.

- Every root-valid creation invocation writes exactly one redacted preflight event, one terminal result event, and one matching `run_end` record. An invalid slug is instead a log-free usage result before every lifecycle, source, or storage action.

- Receipt identity is present only on durable `created` or validated `reused` results and is `null` for every other terminal outcome.

- Run-log bytes omit raw selector and reason input, reviewer content, artifact content, receipt bytes, and exception prose on success, rejection, storage failure, and interruption paths.

- `plan_tool/data_contract.py` registers both new event dataclasses, and their `DATA_CONTRACT.md` sections document every persisted field and closed vocabulary.

- The runner invokes no backend and changes no canonical roadmap artifact, feedback state, seed state, draft, or Git state.

- The runner validates `roadmap_dir(plans_dir, slug)` at its public boundary, so a direct caller cannot create telemetry or evidence outside the roadmap namespace by bypassing CLI validation.

## References

- [pytest: How to monkeypatch/mock modules and environments](https://docs.pytest.org/en/stable/how-to/monkeypatch.html) — Use controlled storage outcomes and interruption seams without exercising filesystem internals.

- [pytest: How to use temporary directories and files](https://docs.pytest.org/en/stable/how-to/tmp_path.html) — Use isolated roadmap, evidence, and run-log fixtures.

## Applicable guardrails

- **The plan’s “## Step intent”, opaque storage mapping:** Consume the prerequisite’s result API and convert it to receipt facts; do not add a second storage protocol.

- **The plan’s “## Plan intent”, receipt-only record:** Limit this runner to receipt evidence and lifecycle telemetry. It must not make an impact decision or mutate roadmap-owned state.

- **The plan’s “## Out of scope”, immutable-evidence storage:** Do not edit `plan_tool/roadmap_evidence_store.py` or reproduce its namespace, temporary-file, enumeration, or durability work.

- **The plan’s “## Out of scope”, local revision compatibility:** Do not change `plan_tool/roadmap_revision.py`, `plan_tool/roadmap_revision_run.py`, or local revision publication behavior.

- **The plan’s “## Out of scope”, identifier grammar:** Enforce receipt-safe values only at the receipt and lifecycle boundary; do not narrow artifact parsing or the shared selector contract.

- **The plan’s “## Out of scope”, broad workflow work:** Do not add views, routing, backend calls, seed actions, or structural patches in this runner.

## Deferred

- CLI argument collection, repeated-option handling, rendering, and command dispatch — Step 5 owns `plan_tool/cli/roadmap_cmd.py` integration and passes its typed preflight state to this runner.

- Receipt enumeration, freshness checks, and log-free receipt views — Step 5 consumes `plan_tool/roadmap_evidence_store.py:scan_evidence` and owns inspection behavior.

- Immutable-evidence storage internals — The prerequisite and `tests/test_roadmap_evidence_store.py` remain the owner of durable publication, matching-final enumeration, and filesystem failure coverage.

- Shared runner consolidation — `plan_tool/roadmap_revision_run.py:run_local_feedback_revision` and this runner have different write and outcome contracts; any common orchestration extraction needs a separately scoped refactor.

- Impact analysis and structural revision — `roadmap-escalation-impact-routing` owns broader scope decisions after a receipt’s `requires-scope-review` handoff.
