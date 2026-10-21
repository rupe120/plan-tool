> **Withdrawn 2026-08-19** — 2026-08-19 plan-level review rejected the premise: no demonstrated problem shows that a provenance advisory changes an operator decision.
> Preserved here for history; do not edit.

# Step 1 — Add immutable ordered remedy-event history to annotations, migrate legacy sidecars, and preserve serialized sidecar updates

## Summary

Extend saved-review annotations with an immutable, ordered remedy-event history in `plan_tool/review_persistence.py`. Update `save_review`, `load_review`, and `update_annotation` so a new event preserves its source report, source finding snapshot, disposition, writer attempt identity, and deterministic order while retaining the walk’s latest annotation state. Document the new sidecar contract in `DATA_CONTRACT.md` and cover it through persistence, walk, and contract tests. On green, repeated remedy records no longer erase earlier evidence, legacy sidecars remain readable without invented evidence, and serialized updates retain every sidecar field.

## Table of Contents

- [Summary](#summary) — Reviewer overview of the persistence change and its green result.
- [Table of Contents](#table-of-contents) — Links to every section in this detail.
- [Why](#why) — The missing provenance evidence in overwritten annotations.
- [Input](#input) — Existing sidecar, finding, walk, and write contracts this step extends.
- [Files (creates vs edits)](#files-creates-vs-edits) — The files this step changes.
- [Implementation](#implementation) — Event lifecycle, ordering, migration, and serialized-write rules.
- [Tests](#tests) — Persistence, walk, and contract coverage required before completion.
- [Acceptance criteria](#acceptance-criteria) — Observable conditions for a finished step.
- [References](#references) — Standard-library and pytest references for the persisted contract.
- [Applicable guardrails](#applicable-guardrails) — Plan boundaries that keep this work diagnostic-only.

## Why

`plan_tool/review_persistence.py:Annotation` stores one mutable value per recommendation id, and `plan_tool/review_persistence.py:update_annotation` replaces that value on every write. That loses the earlier remedy and the finding evidence needed to tell a later recurrence apart from a new structural problem. This step makes the sidecar retain the evidence and order required by later diagnostic steps without treating legacy marks or storage timestamps as proof of causation.

## Input

- **Saved-review contract:** Extend `plan_tool/review_persistence.py:SavedReview`, its `annotations` map, and the schema-version handling owned by `save_review` and `load_review`. Preserve all existing role, fingerprint, audit-result, and optional-payload semantics during an annotation rewrite.

- **Finding snapshot:** Read the selected `plan_tool/review.py:Recommendation` from the source sidecar when recording an event. Preserve its full persisted evidence rather than relying only on its content-addressed `id`.

- **Walk persistence seam:** `plan_tool/review_walk.py:walk_recommendations` sends each completed response through its `persist_fn`, which defaults to `plan_tool/review_persistence.py:update_annotation`. The new history must keep the walk’s status, note, and halt behavior intact.

- **Durable write primitive:** Continue using `plan_tool/fileio.py:durable_write_text` for sidecar replacement. Its atomic replacement does not itself serialize a load-modify-write sequence.

## Files (creates vs edits)

- **New files:** None.

- **Existing files (edits only):**
  - `plan_tool/review_persistence.py` — add the immutable event model, source-report ordering, legacy-safe loading, shared serialized write boundary, and complete sidecar rendering.
  - `DATA_CONTRACT.md` — document the new schema version, source-report ordering, annotation history, event fields, migration policy, and malformed-data behavior.
  - `tests/test_review_persistence.py` — cover event retention, ordering, retry idempotency, legacy migration, malformed payloads, and serialized updates.
  - `tests/test_review_walk.py` — prove normal walk responses and accepted rewalks record the expected distinct event history.
  - `tests/test_data_contract.py` — extend drift checks for the documented persisted fields and full-payload preservation.

## Implementation

- **Foundational logic: append an immutable remedy event for each distinct writer attempt.** Extend `plan_tool/review_persistence.py:Annotation` with an ordered immutable history. A recommended shape is a frozen nested record, but its serialized fields must identify the source sidecar, preserve the selected `Recommendation` snapshot, record the disposition, carry a writer-attempt identity, and retain the event’s per-report sequence.

- **Keep the latest annotation and the event history separate.** `Annotation.status`, `Annotation.note`, and `Annotation.halt_reason` remain the walk’s latest state, so `carried_resolution_from_annotations` and `walk_recommendations` keep their existing behavior. The history is append-only: a later accepted rewalk may replace the latest state but must not replace or rewrite an earlier event.

- **Treat writer attempts as the idempotency boundary.** A retry carrying the same source report, selected finding, disposition, and writer-attempt identity must retain the original event and sequence without adding another event. A later accepted rewalk receives a new writer-attempt identity and appends a distinct event even when it selects the same recommendation id.

- **Persist a real total-order key.** Assign a source-report order when a new sidecar is created and assign an event sequence while its update is serialized. Later readers compare `(source report order, event sequence)`; they must not infer occurrence order from `SavedReview.created_at`, the timestamp filename, or filesystem enumeration. Equal wall-clock times therefore remain deterministic.

- **Preserve source evidence at recording time.** Copy the selected recommendation’s persisted fields into the event. Do not have later history readers join the event back to a possibly collapsed or changed `SavedReview.recommendations` list, and do not reduce the event to a finding id.

- **Record every disposition without granting it causal meaning here.** Keep applied, deliberate-decline, failed, halted, and other walk outcomes visible in the event history. This step does not choose which events qualify for a bad-fix advisory; later steps consume the preserved disposition under their own eligibility rules.

- **Migrate safely on read and rewrite.** Keep versions already accepted by `load_review` readable. A legacy annotation loads with no invented remedy event, including an annotation whose legacy `"done"` status normalizes to `"applied"`; normalizing a status is not evidence of a historical remedy. When a legacy sidecar is rewritten, emit the new schema form while preserving its existing role semantics and keeping unavailable historical ordering unavailable.

- **Reject malformed new provenance rather than guessing.** Validate the new event history and ordering data during `load_review`. Malformed or future-schema data must fail as a sidecar read error, not silently become qualifying evidence or an empty clean history.

- **Serialize the whole read-modify-write transaction.** Put source-report order allocation, event-sequence allocation, annotation replacement, event append or deduplication, full payload serialization, and durable replacement behind one shared serialization boundary. Locking only `os.replace` is insufficient because two writers could otherwise load the same old payload and lose one event.

- **Render complete payloads through one shared path where practical.** `save_review` and `update_annotation` must preserve every existing serialized field, including optional audit metadata and checkpoint-role fields, while adding the new event data. Keep `update_annotation`’s existing role-preservation behavior; an annotation write must not downgrade, promote, strip, or reinterpret a saved review.

- **Keep producer-specific recording out of this step.** The parallel replay callback in `plan_tool/cli/completeness_apply_parallel.py:replay_results` and its `plan_tool/cli/completeness_phases.py` persistence bridge become qualified producers in step 2. The explicit hand-recording surface belongs to step 3. This step supplies their shared persistence contract without editing those modules.

## Tests

### Tests for this step

- `tests/test_review_persistence.py:TestRemedyEventHistory.test_event_preserves_source_report_and_full_recommendation_snapshot` — records a remedy, changes the annotation summary, and proves the original source report identity and complete finding evidence remain in the first event.

- `tests/test_review_persistence.py:TestRemedyEventHistory.test_same_writer_attempt_is_idempotent` — repeats one writer attempt and proves it leaves one unchanged event with its original sequence.

- `tests/test_review_persistence.py:TestRemedyEventHistory.test_new_accepted_rewalk_appends_distinct_event` — records the same recommendation through a later accepted rewalk and proves both events survive in sequence order.

- `tests/test_review_persistence.py:TestRemedyEventHistory.test_event_order_does_not_use_timestamp_or_filename_order` — creates colliding or misleading wall-clock and filename conditions and proves the persisted report-order and sequence tuple controls history order.

- `tests/test_review_persistence.py:TestRemedyEventHistory.test_legacy_annotation_migrates_without_inventing_remedy_evidence` — loads and rewrites a legacy applied or `"done"` annotation while keeping its event history empty and its legacy ordering unavailable.

- `tests/test_review_persistence.py:TestRemedyEventHistory.test_malformed_event_history_refuses_to_load` — supplies invalid event fields, duplicate or invalid ordering, and an unsupported schema version, then asserts `ReviewLoadError`.

- `tests/test_review_persistence.py:TestSerializedAnnotationUpdates.test_serialized_updates_keep_both_distinct_events` — drives contending annotation updates and proves neither load-modify-write loses the other event.

- `tests/test_review_persistence.py:TestUpdateAnnotation.test_update_annotation_preserves_full_saved_review_payload` — updates an annotation on a sidecar carrying optional audit fields and proves every non-annotation field, role marker, and qualified-result payload remains intact.

- `tests/test_review_walk.py:TestWalkRecommendationsSkipsAnnotated.test_rewalk_records_a_new_remedy_event_without_erasing_the_first` — walks an already annotated recommendation with `rewalk=True` and proves the latest status changes while both event records remain.

- `tests/test_review_walk.py:TestApplySkipDowngradesAnnotation.test_walk_records_decline_and_drift_dispositions_as_distinct_nonapplied_events` — proves skip and drift-halt outcomes remain visible in history with their existing annotation semantics.

- `tests/test_data_contract.py:test_annotation_remedy_event_fields_are_documented_and_registered` — verifies the runtime persisted model and `DATA_CONTRACT.md` agree on the annotation-history fields and schema alias.

- `tests/test_data_contract.py:test_update_annotation_preserves_saved_review_contract_keys` — expands the existing preservation guard to include the new order and history contract.

Every listed test must be green before this step is considered finished.

## Acceptance criteria

- A newly written sidecar persists a source-report ordering key, and each distinct remedy event persists a stable per-report sequence.

- Each remedy event retains the source sidecar identity, selected recommendation snapshot, disposition, writer-attempt identity, and order data after later annotations update the same recommendation.

- Retrying one writer attempt creates no duplicate event, while a later accepted rewalk creates a distinct event.

- Event order remains deterministic when timestamps collide or storage naming does not reflect occurrence order.

- Legacy sidecars load and may be rewritten without fabricating remedy events or historical order from their annotation state.

- Malformed event history and unsupported future versions fail to load rather than becoming usable provenance.

- Serialized concurrent updates retain both distinct events, and an annotation rewrite preserves every unrelated saved-review field and role state.

- `DATA_CONTRACT.md` documents the new sidecar and annotation fields, and all tests listed in `## Tests` pass.

## References

- [Python 3.13 — dataclasses](https://docs.python.org/3.13/library/dataclasses.html) — Use frozen records and defaulted collections for immutable event history.

- [Python 3.13 — json](https://docs.python.org/3.13/library/json.html) — Review compatible encoding and strict decoding of saved sidecars.

- [Python 3.13 — os.replace](https://docs.python.org/3.13/library/os.html#os.replace) — Review the replacement primitive beneath the durable writer and its atomicity boundary.

- [Python 3.13 — datetime](https://docs.python.org/3.13/library/datetime.html) — Review UTC timestamp handling while keeping timestamps separate from provenance order.

- [pytest API Reference](https://docs.pytest.org/en/stable/reference/reference.html) — Use fixtures and monkeypatching for legacy payload, replacement-failure, and serialized-update cases.

## Applicable guardrails

- **The plan’s “## Plan intent”, advisory-only boundary** — persist evidence only; do not add diagnostic rendering, change convergence behavior, or alter command outcomes.

- **The plan’s “## Step intent”, attribution and ordering boundary** — retain a source-attributable event for every distinct remedy attempt and preserve the total order through repeated annotations and legacy reads.

- **The plan’s “## Out of scope”, persistence boundary** — keep saved audit annotations as the durable record and do not add a separate provenance store.

- **The plan’s “## Out of scope”, mutation boundary** — do not mutate plan files or introduce automatic remediation while recording annotation history.
