> **Withdrawn 2026-08-11** — Withdrawn after the detail-stage audit exposed an unresolved high-severity provenance-ordering defect and non-convergent correctness contracts; re-seed the capability from the audited invariants before implementation.
> Preserved here for history; do not edit.

# Step 2 — Persist qualified remedy provenance on annotations

## Summary

Extend `Annotation` with timestamped note provenance and source-report identity, and persist those fields through saved-review reads and rewrites. Update `plan_tool/review_walk.py` and the serial/parallel completeness-apply paths so only explicit operator-entered text is marked as operator evidence; generated verdict and status text remains non-operator evidence. Update `plan_tool/convergence_diagnosis.py` so reuse-collapse retains every source annotation event alongside its existing terminal-status view. On green, each newly recorded annotation is ordered and attributable without yet emitting a bad-fix advisory.

## Table of Contents

- [Summary](#summary) — Reviewer overview of the persisted provenance and collapse behavior.
- [Table of Contents](#table-of-contents) — Quick links to each section.
- [Why](#why) — Why saved annotations need qualified remedy evidence.
- [Input](#input) — Existing sidecar, writer, and collapse contracts this step extends.
- [Files (creates vs edits)](#files-creates-vs-edits) — In-scope code and test changes.
- [Implementation](#implementation) — Provenance rules, producer classification, and event retention.
- [Tests](#tests) — Focused coverage for persistence, producers, and collapse.
- [Acceptance criteria](#acceptance-criteria) — Observable completion conditions.
- [References](#references) — Primary references for dataclass and JSON persistence.
- [Applicable guardrails](#applicable-guardrails) — Plan boundaries that limit this feature.
- [Deferred](#deferred) — Work intentionally left to later plan steps.

## Why

`plan_tool/review_persistence.py:Annotation` can currently record an applied status and free-form note, but it cannot distinguish an operator’s remedy statement from automated apply output or establish when and in which report the note was recorded. `plan_tool/convergence_diagnosis.py:build_collapsed_completeness_passes` also reduces merged annotations to one current value, which loses the earlier evidence a later diagnostic needs. Step 1 supplies the common annotation writer; this step makes that writer produce trustworthy, ordered evidence while keeping unqualified and legacy records non-causal.

## Input

- **Step 1 writer boundary:** Step 1 supplies the shared durable annotation-write path rooted at `plan_tool/review_persistence.py:update_annotation`. All new provenance must enter through that outcome, not through a second sidecar store.
- **Saved-review contract:** `plan_tool/review_persistence.py:Annotation`, `SavedReview`, `save_review`, and `load_review` define the JSON representation. `SavedReview.created_at` and the selected sidecar path provide the immutable report identity a new annotation must record.
- **Producer contract:** `plan_tool/review_walk.py:_auto_apply` and `_prompt_for_annotation` construct interactive dispositions, while `plan_tool/cli/completeness_apply_parallel.py:annotation_status` derives parallel final dispositions.
- **Collapse contract:** `plan_tool/convergence_diagnosis.py:RunSnapshot.annotations` and `CompatiblePass.annotations` remain the terminal-state view used by existing convergence helpers. The new event view must supplement, not replace, that map.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `plan_tool/review_persistence.py` — add persisted annotation provenance, safe legacy handling, and a provenance-aware sidecar version path.
  - `plan_tool/review_walk.py` — classify manually entered feedback separately from generated action output when constructing annotations.
  - `plan_tool/cli/completeness_cmd.py` — bind the parallel completeness-apply persistence callback to the shared writer without reclassifying generated output as operator text.
  - `plan_tool/cli/completeness_apply_parallel.py` — pass final generated dispositions to persistence with non-operator note provenance.
  - `plan_tool/convergence_diagnosis.py` — retain complete source annotation events through completeness-pass collapse while preserving existing terminal-state behavior.
  - `tests/test_review_persistence.py` — cover stamped provenance, legacy reads, schema-role preservation, and rewrite round trips.
  - `tests/test_review_walk.py` — cover operator feedback, generated action messages, empty notes, and drift outcomes.
  - `tests/cli/test_completeness_cmd.py` — cover serial and command-bound parallel provenance classification.
  - `tests/cli/test_completeness_apply_parallel.py` — cover generated parallel annotations and final replay callback timing.
  - `tests/test_convergence_diagnosis.py` — cover source-event retention, ordering, and checkpoint exclusion during collapse.

## Implementation

- **Foundational logic: provenance-stamped annotation events.** Treat every newly persisted annotation as one event with its disposition plus the information needed to decide later whether it could be an intervening remedy.

- **Keep provenance in `Annotation`.** Extend `plan_tool/review_persistence.py:Annotation` with a valid UTC `recorded_at`, a closed `note_source` vocabulary, and source-report identity containing the selected report filename or stem plus that report’s immutable `created_at`. Use `operator`, `generated`, and `none` as the source values.

- **Make the writer authoritative for time and report identity.** At the Step 1 writer seam rooted at `plan_tool/review_persistence.py:update_annotation`, assign the recording time once and derive the source report from the loaded sidecar. Do not copy the report creation time into `recorded_at`, and do not let a producer invent or overwrite the report identity.

- **Fail closed for old or malformed provenance.** `plan_tool/review_persistence.py:load_review` must continue to load v1–v3 sidecars whose annotations lack the new fields. Represent absent, malformed, or unrecognized provenance as unknown/non-qualifying; never infer `operator` from a non-empty legacy note.

- **Version provenance-bearing payloads safely.** Update the schema-version handling around `SCHEMA_VERSION`, `_SUPPORTED_SCHEMA_VERSIONS`, and `_normalize_checkpoint_role` so a sidecar rewritten with provenance is recognized by new readers and rejected by readers that cannot parse it. Preserve the established final, checkpoint, and unknown-role behavior when a v1–v3 sidecar is upgraded by an annotation write.

- **Classify interactive notes by origin, not by content alone.** In `plan_tool/review_walk.py:_prompt_for_annotation` and `_auto_apply`, mark a stripped, explicitly entered feedback/note as `operator`. Mark an action handler’s returned message as `generated`, and use `none` when no text was entered or produced. Whitespace-only input is not operator evidence.

- **Keep disposition semantics unchanged.** `status`, `note`, and `halt_reason` from `plan_tool/review_walk.py:walk_recommendations` must retain their current meaning. A user note still wins over an action message as note text, but its source must remain `operator`; failed, skipped, and drift-halt records are still persisted even though they cannot later qualify as remedies.

- **Keep completeness apply output non-operator by default.** The serial `plan_tool/cli/completeness_cmd.py:cmd_completeness_apply` path inherits interactive classification through `walk_recommendations`. In the parallel path, update `plan_tool/cli/completeness_apply_parallel.py:annotation_status`, `replay_results`, and `run_parallel_apply` so verdict tokens such as `APPLIED` and `NOT-APPLICABLE` are recorded as `generated` after the final replay result is known. `plan_tool/cli/completeness_cmd.py:_apply_walk_recs_parallel` should only persist that final annotation through the shared writer.

- **Preserve event history during collapse.** Add an ordered in-memory source-event collection alongside `plan_tool/convergence_diagnosis.py:CompatiblePass.annotations`. Each event must keep the source recommendation id and the complete `Annotation` payload. Seed it from `RunSnapshot` and append events in report order when `build_collapsed_completeness_passes` merges adjacent compatible reports.

- **Retain the current terminal-status map.** Keep `_merge_collapse_annotations` and `CompatiblePass.annotations` as the winner map for `_is_resolved_in_run`, `classify_edit_drift`, and `classify_impact_recurrence`. The event collection exists for later provenance lookup and must not change those consumers’ current results.

- **Keep checkpoint filtering intact.** `load_report_history` already excludes non-final sidecars. Do not add a checkpoint scan; annotations found only in checkpoint sidecars remain unavailable to the later advisory.

- **Cover indirect walker consumers without widening scope.** `plan_tool/cli/review_cmd.py`, `plan_tool/cli/reconcile.py`, and `plan_tool/cli/data_contract_cmd.py` reach the shared classification through `walk_recommendations`; do not edit those callers. Do not change `plan_tool/convergence_diagnosis.py:_matches` or add advisory evaluation here; later steps own identity matching and rendering.

## Tests

### Tests for this step

- `tests/test_review_persistence.py:TestUpdateAnnotation.test_writes_only_annotations` — extend it to assert one writer call stamps a valid UTC time, source category, and immutable source-report identity while preserving the rest of the sidecar.
- `tests/test_review_persistence.py:TestLoadReview.test_legacy_annotation_without_provenance_is_unknown` — verify a v1–v3 annotation without provenance loads and cannot acquire an inferred operator source.
- `tests/test_review_persistence.py:TestCheckpointRole.test_update_annotation_preserves_checkpoint_role_and_v3_matrix` — update the role matrix coverage for a provenance-bearing rewrite and confirm final, checkpoint, and unknown roles keep their meanings.
- `tests/test_review_persistence.py:TestUpdateAnnotation.test_provenance_round_trips_without_restamping` — verify persisted provenance survives load and a later full-sidecar rewrite unchanged.
- `tests/test_review_walk.py:TestWalkRecommendationsNote.test_note_then_done` — verify explicit feedback followed by apply persists `note_source="operator"`.
- `tests/test_review_walk.py:TestWalkApplyDispatchesAction.test_apply_preserves_user_note_over_action_message` — verify the operator note remains both the stored text and operator source when an action returns generated text.
- `tests/test_review_walk.py:TestWalkApplyDispatchesAction.test_generated_action_message_is_not_operator_provenance` — verify an action-only message is stored as generated evidence.
- `tests/test_review_walk.py:TestWalkApplyDispatchesAction.test_pre_apply_drift_halt_records_drift_halt_reason` — verify drift disposition and generated source remain distinct from an operator remedy.
- `tests/cli/test_completeness_cmd.py:TestCarriedFindingsWiring.test_serial_completeness_apply_generated_verdict_is_non_operator` — drive a serial apply through the real walk and assert its generated disposition has source-report provenance but is not operator evidence.
- `tests/cli/test_completeness_cmd.py:TestCompletenessApplyParallel.test_parallel_applies_and_persists_annotations` — update the command-level callback fixture to assert applied and failed parallel outcomes are persisted as generated annotations.
- `tests/cli/test_completeness_apply_parallel.py:TestAnnotationStatus.test_applied_maps_to_generated_annotation` — verify each verdict mapping keeps its current status while marking its note as generated.
- `tests/cli/test_completeness_apply_parallel.py:TestReplayPersistCallback.test_persist_fires_per_finding_incrementally` — verify the callback receives each final, fully classified annotation only after replay has decided its disposition.
- `tests/test_convergence_diagnosis.py:test_annotations_carried_through_verbatim` — extend the history assertion to retain complete provenance-bearing annotations.
- `tests/test_convergence_diagnosis.py:test_adjacent_collapse_retains_all_source_annotation_events` — verify collapsed compatible reports retain both source events, their recommendation ids, outcomes, timestamps, and original report identities.
- `tests/test_convergence_diagnosis.py:test_load_report_history_excludes_marked_pre_apply_checkpoint` — keep proving checkpoint-only annotations do not enter the event history.

Every listed test must be green before this step is considered finished.

## Acceptance criteria

- Every annotation newly committed through `plan_tool/review_persistence.py:update_annotation` has a valid UTC `recorded_at`, a `note_source`, and the selected sidecar’s immutable identity.
- Explicit non-empty interactive feedback records `note_source="operator"`; action output and parallel verdict text record `note_source="generated"`; absent or whitespace-only text records `note_source="none"`.
- Existing applied, skipped, failed, and drift-halt statuses retain their current behavior and stored note text.
- V1–v3 sidecars remain readable, but annotations missing, malformed, or unrecognized provenance do not become operator evidence.
- A provenance-bearing rewrite preserves checkpoint-role semantics and does not let an older reader silently accept an annotation shape it cannot interpret.
- `build_collapsed_completeness_passes` preserves every source annotation event from collapsed reports while leaving `CompatiblePass.annotations` usable as the existing terminal-status map.
- `load_report_history` continues to exclude checkpoint and unknown-role sidecars from convergence history.
- The tests listed in `## Tests` are green.

## References

- [Python dataclasses — Data Classes](https://docs.python.org/3/library/dataclasses.html) — Review frozen record defaults and `asdict` behavior for the extended `Annotation` shape.
- [Python json — JSON encoder and decoder](https://docs.python.org/3/library/json.html) — Review saved-sidecar encoding, decoding, and compatibility handling.
- [Python os — `os.replace`](https://docs.python.org/3/library/os.html#os.replace) — Review the atomic replacement behavior used by the durable annotation writer.

## Applicable guardrails

- **The plan’s “## Plan intent”, recommend-only evidence boundary** — persist qualified evidence only; do not add a convergence advisory, stop reason, or exit-code effect.
- **The plan’s “## Step intent”, operator-evidence boundary** — classify source honestly and never treat generated output or legacy notes as causal remedy evidence.
- **The plan’s “## Out of scope”, identity-matcher boundary** — do not change `plan_tool/convergence_diagnosis.py:_matches` or add same-issue matching behavior.
- **The plan’s “## Out of scope”, storage and mutation boundary** — keep provenance in annotations and do not expand plan mutation or create another provenance store.

## Deferred

- **Documentation and the contract drift guard** — Step 6 owns `DATA_CONTRACT.md` and `tests/test_data_contract.py` after every producer and consumer rule is settled; do not update them in this step.
