> **Auto-archived**: this plan was swept on 2026-08-18 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 7 — Add closed redacted rewrite preflight and terminal events while preserving atomic run-log replacement and guarded temporary and in-flight cleanup

## Summary

Add two structural-rewrite lifecycle event types to `plan_tool/run_log.py`, with writer methods that admit only safe identifiers, digests, counts, and closed status values. Document the events and their exact preflight and terminal matrices in `DATA_CONTRACT.md`, then register them with the contract-drift registry. Preserve the existing JSONL append behavior, atomic `in-flight.json` replacement, temporary-file cleanup, and newer-run ownership check during `RunLogWriter.run_end`. On green, step 8 can report every structural rewrite outcome without storing reviewer or artifact content.

## Table of Contents

- [Summary](#summary) — Reviewer-level outcome and affected surfaces.
- [Table of Contents](#table-of-contents) — Links to each section in this detail.
- [Why](#why) — Why structural rewrites need their own closed lifecycle records.
- [Input](#input) — Upstream evidence and operation facts this contract summarizes.
- [Files (creates vs edits)](#files-creates-vs-edits) — Exact file footprint, including one required correction.
- [Implementation](#implementation) — Event shapes, validation matrices, and preserved I/O rules.
- [Tests](#tests) — Focused lifecycle, redaction, documentation, and cleanup coverage.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Primary references for atomic replacement and digests.
- [Applicable guardrails](#applicable-guardrails) — Plan boundaries that limit these records.
- [Deferred](#deferred) — Work owned by later steps or separate refactors.

## Why

`plan_tool/run_log.py:RunLogWriter` records closed lifecycle facts for local revisions, escalation receipts, and impact analyses, but structural rewrites have no equivalent contract. Step 8 needs a durable way to distinguish rejected evidence, rejected operations, stale final checks, publication failure, success, and interruption without turning logs into a copy of the feedback request, roadmap artifact, prompt, or backend reply.

## Input

- **Exact evidence context:** Step 2 supplies the accepted receipt-analysis pair, selected artifact and feedback facts, target-row identity, canonicality result, and current binding facts. This step records only safe identifiers and a digest of the complete binding; it does not recreate step 2’s preflight.

- **Operation boundary:** Step 3 supplies the closed operation and rejection vocabulary. Attempt telemetry records only whether that boundary accepted or rejected work, never its JSON envelope or response text.

- **Existing lifecycle precedent:** `plan_tool/run_log.py:RoadmapLocalRevisionPreflight`, `RoadmapLocalRevisionAttempt`, `RoadmapImpactPreflight`, and their `RunLogWriter` methods establish the existing frozen-event, validated-vocabulary, and redacted-prefix pattern. Keep their persisted contracts unchanged.

- **I/O lifecycle:** `plan_tool/run_log.py:write_in_flight` and `RunLogWriter.run_end` own atomic snapshot replacement and guarded cleanup. New event emission must remain append-only and must not refresh or delete an in-flight snapshot.

## Files (creates vs edits)

- **New files:** None.

- **Existing files (edits only):**
  - `plan_tool/run_log.py` — Add structural-rewrite preflight and terminal event dataclasses, their closed validators, `Event` union members, and fixed-argument `RunLogWriter` emitters without changing snapshot I/O behavior.
  - `tests/test_run_log.py` — Add lifecycle matrix, redaction, union, append-only, atomic replacement, temporary-file cleanup, and guarded in-flight cleanup coverage.
  - `DATA_CONTRACT.md` — Document both new event schemas, their allowed fact groups, terminal outcome matrix, ordering, and redaction rule.
  - `plan_tool/data_contract.py` — **Required footprint addition:** add this file to the step’s `files:` list before implementation, then register both new persisted dataclasses in `persisted_dataclass_contracts`.
  - `tests/test_data_contract.py` — Assert registration and documentation of both event contracts.

## Implementation

- **Foundational logic:** Add a closed, redacted structural-rewrite lifecycle matrix.

- **Add a separate structural event pair.** In `plan_tool/run_log.py`, add frozen `RoadmapStructuralRevisionPreflight` and `RoadmapStructuralRevisionAttempt` dataclasses beside the existing roadmap lifecycle events. Add both to the `Event` union so `append_event` accepts them without a special path.

- **Keep the preflight record small and safe.** `RoadmapStructuralRevisionPreflight` should carry only `receipt_final`, `analysis_final`, `artifact_key`, `feedback_id`, `target_row_id`, `binding_digest`, `render_canonical`, and `verdict`, in addition to the base timestamp, run id, and event discriminator. Validate final names and binding digests as SHA-256 identities, and validate selected identifiers with the existing receipt-safe identifier rule.

- **Use one closed preflight fact matrix.** Add a validator, such as `_validate_roadmap_structural_revision_preflight_facts`, that permits only these verdict-specific fact groups:
  - `mode-rejected`, `evaluator-rejected`, and `interrupted` carry no evidence,
    selection, binding, or canonicality facts. `mode-rejected` covers malformed
    final identities and mixed or incomplete command forms without retaining
    their raw values. `evaluator-rejected` covers a missing, malformed, or
    version-mismatched fixed evaluator, unavailable host-isolation provider, or
    failed workspace-read denial without retaining a version, path,
    configuration, or error string.
  - `evidence-rejected` carries only the fully admitted receipt-analysis final pair.
  - `feedback-rejected` additionally carries the selected artifact and feedback identifiers, but no target, binding, or canonicality fact.
  - `render-canonical-rejected` additionally carries the resolved target row and `render_canonical=False`, but no binding digest.
  - `accepted` requires the complete set and `render_canonical=True`.
  
  Do not accept a partial pair, an unsafe identifier, a digest before its complete binding, or a later-stage fact on an earlier rejection.

- **Make accepted preflight the attempt boundary.** Step 8 validates final-name
  shape, then the captured fixed-evaluator runtime contract, before evidence
  loading. It emits `mode-rejected` for malformed or mixed command forms and
  fact-free `evaluator-rejected` for a missing, malformed, or version-mismatched
  evaluator, unavailable isolation provider, or failed no-workspace-read probe.
  It uses the fixed evaluator without consulting active backend selection or
  project argv. Document and enforce that every rejected or
  interrupted preflight has no structural attempt event. An accepted preflight
  is followed by exactly one `RoadmapStructuralRevisionAttempt` with
  `attempt=1`; step 8 owns emitting that sequence.

- **Define the terminal record around completed boundaries.** `RoadmapStructuralRevisionAttempt` should carry a required complete `binding_digest`, nullable nonnegative `invalidated_seed_count`, and closed `operation_verdict`, `merge_verdict`, `proof_verdict`, `final_snapshot_verdict`, `publication_outcome`, and `outcome` fields. Use the plan’s vocabulary: operation and merge are `not-reached`/`accepted`/`rejected`; proof is `not-reached`/`structural-rejected`/`gate-rejected`/`accepted`; final snapshot is `not-reached`/`current`/`stale`; publication is `not-reached`/`published`/`failed`/`unknown-after-interrupt`.

- **Validate the full outcome-to-phase table, not each field alone.** Add a dedicated attempt validator and document this exact matrix in `DATA_CONTRACT.md`:
  
  | Outcome | Operation | Merge | Proof | Final snapshot | Publication |
  |---|---|---|---|---|---|
  | `seed-invalidation-failed` | `not-reached` | `not-reached` | `not-reached` | `not-reached` | `not-reached` |
  | `invoke-failed` / `empty-reply` | `not-reached` | `not-reached` | `not-reached` | `not-reached` | `not-reached` |
  | `envelope-rejected` | `rejected` | `not-reached` | `not-reached` | `not-reached` | `not-reached` |
  | `merge-rejected` | `accepted` | `rejected` | `not-reached` | `not-reached` | `not-reached` |
  | `proof-rejected` | `accepted` | `accepted` | `structural-rejected` or `gate-rejected` | `not-reached` | `not-reached` |
  | `final-snapshot-stale` | `accepted` | `accepted` | `accepted` | `stale` | `not-reached` |
  | `publication-failed` | `accepted` | `accepted` | `accepted` | `current` | `failed` |
  | `published` | `accepted` | `accepted` | `accepted` | `current` | `published` |
  
  `invalidated_seed_count` is `null` only when invalidation did not finish; all non-invalidation terminal rows require its nonnegative count. `interrupted` permits only an incomplete prefix of the successful path, with `unknown-after-interrupt` allowed only after the final snapshot is `current` and replacement may have started. Reject every tuple outside these rows and permitted interruption prefixes.

- **Expose fixed writer methods.** Add `RunLogWriter.roadmap_structural_revision_preflight` and `RunLogWriter.roadmap_structural_revision_attempt` with explicit keyword-only arguments. Do not give either method `**extra`, raw-error, prompt, reply, feedback, artifact, or path parameters. This keeps the event API closed and helps keep records below `_MAX_LINE_BYTES`.

- **Keep event emission append-only.** The new writer methods should follow the existing roadmap event methods and call `_emit` only. They must not call `_refresh_in_flight`, alter `RUN_LOG_SCHEMA_VERSION`, or change `read_run_events` behavior.

- **Preserve replacement and cleanup behavior.** Leave `write_in_flight` as the same-directory temporary-file plus `os.replace` path, including cleanup when replacement raises. Leave `RunLogWriter.run_end`’s run-id check intact so an older same-slug writer cannot remove a newer writer’s `in-flight.json`.

- **Register and document the persisted schema.** Add both owners to `plan_tool/data_contract.py:persisted_dataclass_contracts`, then add matching `DATA_CONTRACT.md` sections with every dataclass field, the preflight fact matrix, the terminal outcome matrix, and the rule that these events contain no feedback text, roadmap prose, prompt, backend reply, or exception detail. Keep `plan_tool/data_contract.py` as the source used by `tests/test_data_contract.py`; do not create a parallel documentation check.

## Tests

### Tests for this step

- `test_structural_revision_events_have_closed_fields_and_nullability` — asserts both dataclasses expose exactly their documented base and lifecycle fields.
- `test_structural_revision_preflight_requires_the_closed_fact_matrix` — accepts each permitted verdict row and rejects partial final pairs, unsafe ids, out-of-order facts, and a binding digest before accepted preflight.
- `test_structural_revision_preflight_rejections_keep_raw_inputs_out_of_events` —
  covers malformed names and an unsupported evaluator with one fact-free
  preflight event and no attempt event; it proves evaluator rejection retains
  no version, path, configuration, or error content.
- `test_structural_revision_attempt_requires_exact_outcome_phase_tuples` — accepts every documented terminal row and permitted interruption prefix, while rejecting impossible combinations such as accepted proof with a stale earlier phase or published outcome without published replacement.
- `test_structural_revision_attempt_requires_seed_count_after_successful_invalidation` — distinguishes a failed or interrupted invalidation from every later outcome that must retain the nonnegative invalidated count.
- `test_structural_revision_writer_methods_reject_unlisted_vocabulary_and_content` — rejects unknown closed values and extra feedback, artifact, prompt, reply, path, or error arguments without serializing them.
- `test_structural_revision_events_are_event_union_members` — appends each new dataclass through `append_event`.
- `test_structural_revision_events_append_without_refreshing_active_snapshot` — proves lifecycle events do not change the active in-flight snapshot.
- `test_write_in_flight_preserves_previous_snapshot_and_removes_tempfile_when_replace_fails` — proves a failed replacement leaves the prior snapshot readable and no sibling temporary file behind.
- `test_run_end_skips_unlink_when_a_newer_run_owns_the_snapshot` — remains green, proving an older writer preserves a newer same-slug snapshot.
- `test_run_end_still_unlinks_own_snapshot` — remains green, proving the normal writer still cleans up its own snapshot.
- `test_structural_revision_event_contracts_are_registered_and_documented` — verifies `plan_tool/data_contract.py:persisted_dataclass_contracts` names both event owners and `DATA_CONTRACT.md` documents their fields and closed vocabulary.

Every test above must be green before this step is considered finished.

## Acceptance criteria

- `plan_tool/run_log.py:Event` includes `RoadmapStructuralRevisionPreflight` and `RoadmapStructuralRevisionAttempt`, each with a fixed discriminator and no free-form content field.

- `RunLogWriter` rejects every structural preflight fact combination outside the documented verdict matrix.

- `RunLogWriter` rejects every structural terminal tuple outside the documented outcome-to-phase matrix, including invalid interruption and seed-invalidation combinations.

- New structural lifecycle records contain only allowed identifiers, SHA-256 digests, booleans, counts, and closed status values; callers cannot add reviewer text, roadmap prose, prompts, backend replies, paths, or error text through the public event methods.

- `DATA_CONTRACT.md` and `plan_tool/data_contract.py:persisted_dataclass_contracts` describe and register the same fields as the runtime dataclasses.

- `write_in_flight` still replaces a snapshot atomically, cleans its sibling temporary file after a failed replacement, and `RunLogWriter.run_end` still preserves a newer same-slug in-flight snapshot.

## References

- [Python `os.replace`](https://docs.python.org/3.13/library/os.html#os.replace) — Read the replacement semantics that keep `in-flight.json` from becoming partially written.

- [Python `hashlib` secure hashes](https://docs.python.org/3.13/library/hashlib.html#hashlib.file_digest) — Use the digest contract for safe binding identities without retaining source content.

## Applicable guardrails

- **The plan intent, one-artifact rewrite boundary:** Keep lifecycle events observational only. They must not become publication authority or imply a write set beyond the selected artifact.

- **The plan’s step intent, redacted lifecycle evidence:** Limit new records to closed status facts and safe identities. Do not add content-bearing diagnostic fields.

- **The plan’s “## Out of scope”, unrelated revision modes:** Keep `RoadmapLocalRevisionPreflight` and `RoadmapLocalRevisionAttempt` unchanged. Structural lifecycle support must not alter local revision behavior or become a shared generic patch contract.

- **The plan’s “## Out of scope”, recovery scope:** Preserve the existing single-snapshot and guarded cleanup behavior; do not add multi-file journals or recovery state.

## Deferred

- `plan_tool/roadmap_structural_revision_run.py` emission order and redacted console diagnostics — Step 8 owns the runner that opens the writer, emits the accepted-preflight attempt, and avoids passing content through generic run boundaries.

- `plan_tool/cli/roadmap_cmd.py` command parsing and operator-facing outcome rendering — Step 9 owns the exclusive command surface and its summary.

- Consolidating local, escalation, impact, and structural lifecycle validators — the event contracts have different facts and compatibility requirements; treat any shared abstraction as a separate refactor.
