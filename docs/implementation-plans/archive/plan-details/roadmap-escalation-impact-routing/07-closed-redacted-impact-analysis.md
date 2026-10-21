> **Auto-archived**: this plan was swept on 2026-08-18 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 7 — Add closed redacted impact-analysis telemetry while preserving run-log appends, active-snapshot replacement, and guarded cleanup

## Summary

Extend `plan_tool/run_log.py` with typed preflight and terminal events for impact-analysis creation, then document and test their closed redaction and lifecycle rules. Update `tests/test_run_log.py` and `DATA_CONTRACT.md` so the event fields, nullability, vocabulary, append behavior, and cleanup boundaries are explicit. The key design decision is that these methods append lifecycle facts only; they do not refresh, replace, or remove the active snapshot. Green means step 8 can report analysis admission and terminal outcomes without exposing reviewer or artifact content.

## Table of Contents

- [Summary](#summary) — The completed telemetry contract and its observable result.
- [Table of Contents](#table-of-contents) — Links to every section in this detail.
- [Why](#why) — Why impact-analysis lifecycle facts need their own closed events.
- [Input](#input) — Existing run-log and step 5 contracts this step consumes.
- [Files (creates vs edits)](#files-creates-vs-edits) — The three files this step edits.
- [Implementation](#implementation) — Event shape, redaction, lifecycle, and snapshot boundaries.
- [Tests](#tests) — Focused coverage for event validity and unchanged writer behavior.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Primary documentation for JSON, digests, filesystem behavior, and tests.
- [Applicable guardrails](#applicable-guardrails) — Scope limits that bind this telemetry step.
- [Deferred](#deferred) — Runner, storage, and CLI work owned by later steps.

## Why

`plan_tool/run_log.py:RoadmapEscalationPreflight` and `plan_tool/run_log.py:RoadmapEscalationResult` make receipt creation observable, but impact analysis has different admission evidence and must preserve route class separately from immutable publication outcome. Without its own closed event contract, a runner could lose whether a durable scope-review analysis was created or reused, leak prose through an extension field, or accidentally change the active-run snapshot while trying to log an analysis.

## Input

- **Run-log event boundary:** Use `plan_tool/run_log.py:Event`, `RunLogWriter._emit`, `_CONTEXT_RESERVED_KEYS`, `RunLogWriter.start`, `RunLogWriter._refresh_in_flight`, and `RunLogWriter.run_end` as the existing append, context, snapshot, and cleanup contracts.

- **Receipt lifecycle precedent:** Follow the closed-field and monotonic-fact approach in `plan_tool/run_log.py:RoadmapEscalationPreflight`, `RoadmapEscalationResult`, `_validate_roadmap_escalation_preflight_facts`, and their `RunLogWriter` methods. Keep impact telemetry a separate event family.

- **Step 5 analysis outcome:** Consume step 5’s closed analysis identity, route classes, workflow mapping, and transient-invalid result. This step records those facts; it does not recompute, validate, or persist an analysis.

- **Run-log documentation:** Extend `DATA_CONTRACT.md:Run log events` using the existing lifecycle-event table style. Keep `RUN_LOG_SCHEMA_VERSION` unchanged because these are additional JSONL event discriminators, not a snapshot-schema change.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `plan_tool/run_log.py` — Add closed impact preflight and result event dataclasses, register them in `Event`, validate their allowed facts, and expose append-only `RunLogWriter` emitters.
  - `tests/test_run_log.py` — Add focused event-shape, redaction, union, append-only, snapshot, and guarded-cleanup coverage.
  - `DATA_CONTRACT.md` — Document the two event schemas, verdict and outcome vocabulary, nullability, redaction boundary, and lifecycle ordering.

## Implementation

- **Foundational logic — emit only validated redacted lifecycle facts.** Add `RoadmapImpactPreflight` and `RoadmapImpactResult` beside `RoadmapEscalationPreflight` and `RoadmapEscalationResult` in `plan_tool/run_log.py`. Give each event a distinct discriminator and a frozen, closed dataclass shape.

- **Keep preflight facts small and ordered.** `RoadmapImpactPreflight` should contain the safe requested receipt final; resolved safe selector, target, and reason facts when available; the receipt-source digest, SHA-256 digest of exact raw source-record bytes, decoded-text brief digest; snapshot-artifact, closure-node, and closure-relation counts; and one closed admission verdict. Use nullable fields only for facts that have not yet been established, and never serialize a raw command argument, artifact-digest vector, path, source text, or relation identifier that failed the safe-id rule.

- **Define the closed impact-preflight matrix.** Add `mode-rejected`, `final-rejected`, `receipt-missing`, `receipt-unreadable`, `receipt-invalid`, `receipt-rejected`, `snapshot-rejected`, `closure-rejected`, `accepted`, and `interrupted`. `mode-rejected`, `final-rejected`, and early `interrupted` expose no semantic evidence; a safe requested final appears only when the parser established it. Receipt-missing/unreadable/invalid have at most that safe final. Receipt-rejected may additionally contain validated receipt selector, target, reason, and receipt-source digest. Snapshot-rejected may additionally contain raw-source-record/decoded-brief digests and snapshot-artifact count. Closure-rejected may additionally contain closure counts. Accepted contains the same fully resolved safe fact set. No verdict may include a fact from a later phase.

- **Validate monotonic disclosure.** Add an impact-specific validation helper modelled on `plan_tool/run_log.py:_validate_roadmap_escalation_preflight_facts` that enforces this exact matrix. Require digest-shaped values, nonnegative aggregate counts, safe identifiers, and the existing closed reason and target vocabularies.

- **Define one terminal result contract.** Add `RunLogWriter.roadmap_impact_result` with one event outcome: `completed`, `preflight-rejected`, `invalid`, `storage-rejected`, `collision`, `write-failed`, or `interrupted`. `storage-rejected` records a validated candidate that the evidence store rejects before it creates a final; it remains distinct from an I/O `write-failed` outcome. A `completed` result carries exactly one stored route class (`same-artifact`, `cross-artifact`, or `requires-scope-review`) and exactly one immutable publication outcome (`created` or `reused`), plus a safe analysis id. `next_workflow` is present only for `same-artifact` and `cross-artifact`; a completed `requires-scope-review` result carries a null workflow. Failure outcomes carry no route, publication outcome, identity, or workflow. `telemetry-unavailable` is deliberately excluded: it is a return-only command outcome when an event append cannot prove itself durable. This keeps terminal lifecycle, stored route, and immutable publication as three closed, independent facts.

- **Keep the leaf boundary intact.** `plan_tool/run_log.py` must not import step 5’s analysis module or any other first-party module. Hand-copy only the closed literal vocabularies it needs, validate them at the writer boundary, and reject unknown values or additional prose-carrying parameters.

- **Register event fields everywhere the writer derives them.** Add both types to `plan_tool/run_log.py:Event` so `append_event` accepts them and `_CONTEXT_RESERVED_KEYS` prevents writer context from replacing lifecycle facts such as `receipt_final`, `analysis_id`, or `next_workflow`.

- **Append only; do not touch the active snapshot.** Implement the new writer methods through `RunLogWriter._emit` only. Do not call `_refresh_in_flight`, `write_in_flight`, or `unlink`, and do not change `RunLogWriter.start` or `RunLogWriter.run_end`. Starting a later same-slug run must still replace the snapshot, and an earlier run’s `run_end` must still leave that newer snapshot in place.

- **Document the runner-owned sequence.** In `DATA_CONTRACT.md`, state that after `RunLogWriter.start` succeeds, step 8 resolves and appends one preflight before publication. A nonaccepted `mode-rejected`/`final-rejected` preflight is followed by `preflight-rejected`; other nonaccepted verdicts are followed by `invalid`; accepted preflight precedes publication and one of `completed`/`storage-rejected`/`collision`/`write-failed`. Emit a terminal event only after its own append returns. A telemetry failure or interruption during either append returns a redacted process result, performs normal generic cleanup, and adds no compensating event; a successfully appended interruption may have an `interrupted` terminal event. A telemetry failure before publication blocks publication. If the terminal result event is already durable, a later `run_end` interruption or cleanup failure returns that durable result without a compensating event; otherwise a failure or interruption after publication does not make telemetry authority over the immutable final.

- **Leave orchestration to later steps.** Do not add a runner, evidence-store call, writer guard, CLI flag, view behavior, backend call, or canonical-artifact mutation in this step.

## Tests

### Tests for this step

- `tests/test_run_log.py:test_impact_preflight_verdict_matrix_has_closed_fields_and_monotonic_nullability` — Locks the dataclass field sets and proves every verdict exposes exactly its permitted safe facts while accepted facts retain the full resolved set.

- `tests/test_run_log.py:test_impact_preflight_rejects_unsafe_or_out_of_order_facts` — Rejects unsafe identifiers, malformed digests, invalid counts, unknown verdicts, and facts that appear before their prerequisite check succeeds.

- `tests/test_run_log.py:test_impact_result_separates_completed_route_publication_identity_and_workflow` — Requires `completed` results to carry an analysis id, route class, and `created`/`reused` publication outcome; proves each scope-review publication has an id and no workflow.

- `tests/test_run_log.py:test_impact_result_excludes_return_only_telemetry_unavailable` — Rejects `telemetry-unavailable` at the event boundary while preserving it for the runner’s redacted process result.

- `tests/test_run_log.py:test_impact_writer_methods_reject_unknown_vocabulary_and_prose` — Rejects unknown terminal values and attempts to pass reviewer prose, paths, or artifact content through the closed emitter signatures.

- `tests/test_run_log.py:test_impact_event_fields_are_reserved_from_writer_context` — Proves context cannot replace impact event identity, ids, workflow, or outcome fields.

- `tests/test_run_log.py:test_impact_events_are_event_union_members` — Appends each new dataclass through `append_event` and verifies both discriminators are readable JSONL events.

- `tests/test_run_log.py:test_impact_events_append_without_refreshing_active_snapshot` — Emits both events and proves the active in-flight snapshot remains owned and unchanged until normal lifecycle code refreshes or ends it.

- `tests/test_run_log.py:test_impact_events_preserve_newer_snapshot_during_guarded_run_end_cleanup` — Emits impact events from one writer, starts a newer writer for the same slug, and proves the older `run_end` does not remove the newer snapshot.

- **Green-before-done gate:** `uv run pytest tests/test_run_log.py -q` passes.

## Acceptance criteria

- `plan_tool/run_log.py` defines and registers one closed `roadmap_impact_preflight` event and one closed `roadmap_impact_result` event.

- Impact preflight records only receipt-safe identifiers, valid digest and aggregate-count facts, and fields justified by its closed admission-verdict matrix.

- Impact terminal events accept only the documented append-confirmed outcomes; completed results separately carry route and publication facts, while durable analysis ids and workflow values follow the documented nullability rules. Return-only `telemetry-unavailable` is not an event.

- Neither event type accepts or serializes reviewer prose, artifact or brief content, paths, raw selector input, prompts, backend data, or unsafe relation identifiers.

- Both event types append through the existing JSONL path and do not change `RUN_LOG_SCHEMA_VERSION`, replace an active snapshot, or weaken `RunLogWriter.run_end`’s newer-run cleanup guard.

- `DATA_CONTRACT.md` documents both event schemas, redaction rules, lifecycle ordering, and the publication boundary.

- `uv run pytest tests/test_run_log.py -q` passes.

## References

- [json — JSON encoder and decoder](https://docs.python.org/3.13/library/json.html) — Use this for the JSONL serialization and strict value-shape boundary.

- [hashlib — Secure hashes and message digests](https://docs.python.org/3.13/library/hashlib.html) — Use this for the SHA-256-shaped receipt and analysis identity rules.

- [os — Miscellaneous operating system interfaces](https://docs.python.org/3.13/library/os.html) — Use this for the existing append, replacement, and cleanup behavior that these emitters must not alter.

- [How to monkeypatch/mock modules and environments — pytest](https://docs.pytest.org/en/stable/how-to/monkeypatch.html) — Use this for controlled same-slug snapshot and append-boundary tests.

## Applicable guardrails

- **The plan’s “## Step intent,” observable but redacted lifecycle:** Limit these edits to analysis admission and terminal telemetry facts; do not turn the run log into a copy of analysis evidence.

- **The plan’s “## Architecture,” closed telemetry lifecycle:** Keep event vocabulary, field presence, and durable-result handling explicit and reject unlisted data at the `plan_tool/run_log.py:RunLogWriter` boundary.

- **The plan’s “## Architecture,” telemetry is not evidence:** Document observation of durable publication without making the event log a source of route or record validity.

- **The plan’s “## Out of scope,” execution and state changes:** Do not add backend work, canonical writes, feedback changes, seed changes, or follow-on workflow execution.

- **The plan’s “## Out of scope,” existing writer boundary:** Preserve `plan_tool/run_log.py:RunLogWriter.start`, `_refresh_in_flight`, and `run_end` semantics rather than widening or replacing snapshot coordination.

## Deferred

- Impact-run preflight resolution, publication ordering, exact retry behavior, and terminal emission calls — step 8 owns the guarded runner.

- Immutable evidence storage and temporary-file handling — steps 6 and 8 own the analysis namespace and publication protocol.

- Impact-analysis command parsing, result rendering, and log-free inspection — step 9 owns the CLI surfaces.
