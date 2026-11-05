> **Auto-archived**: this plan was swept on 2026-11-05 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 6 — Add explicit idempotent legacy migration and guarded mutable reviewer edits in predecessor-grouped ledger sections

<!-- plan-tool:detail-format-version: 1 -->

## Summary

Create `plan_tool/roadmap_feedback_ledger_run.py` as the guarded runtime owner for ledger migration, reviewer edits, and predecessor-grouped rendering. Create `tests/test_roadmap_feedback_ledger_run.py` to prove migration is explicit and idempotent, reviewer edits preserve immutable roadmap and candidate state, and retargeting moves an item to the right rendered group. The key design decision is that this module changes only the mutable ledger under the existing roadmap writer guard; it must not publish versions, alter the accepted head, or create a second lifecycle store. On green, ledger-native roadmaps accept validated reviewer changes, migration-pending roadmaps refuse ledger processing until one completed import, and legacy embedded feedback remains read-only history.

## Table of Contents

- [Summary](#summary) — Reviewer-level outcome for migration and mutable edits.
- [Table of Contents](#table-of-contents) — Links to every section in this file.
- [Why](#why) — Why legacy feedback needs an explicit one-way boundary.
- [Input](#input) — Ledger, version, and active-candidate contracts this step consumes.
- [Files (creates vs edits)](#files-creates-vs-edits) — New module and focused test footprint.
- [Implementation](#implementation) — Guarded migration, edits, grouping, and refusal behavior.
- [Tests](#tests) — Focused runtime contract coverage.
- [Acceptance criteria](#acceptance-criteria) — Observable completion conditions.
- [References](#references) — Primary sources for validation and durable writes.
- [Applicable guardrails](#applicable-guardrails) — Plan boundaries that constrain this runtime owner.
- [Deferred](#deferred) — Related lifecycle and interface work left to later steps.

## Why

Embedded `FeedbackRow` values in `plan_tool/roadmap_artifacts.py:FeedbackRow` remain part of legacy artifact content, while step 1’s ledger becomes the sole mutable reviewer authority for enrolled roadmaps. Without one guarded, recorded import and one owner for reviewer edits, a roadmap can silently read two writable sources, lose a response during migration, or let an ordinary edit change immutable candidate or accepted-head state.

## Input

- **Step 1 ledger contract:** Consume the landed `plan_tool/roadmap_feedback_ledger.py` loader, renderer, ledger-state records, reviewer-item records, target fingerprint checks, and ledger path helper. The landed step 1 names and schema win over this detail.

- **Step 5 processing-pair contract:** Read the landed root-and-active-candidate state from `plan_tool/roadmap_candidate_run.py`, including its active-pointer loader and immutable candidate evidence. Use it to identify the current root/source pair and to prove reviewer edits do not change it.

- **Immutable versions:** Use `plan_tool/roadmap_versions.py:load_accepted_version` and `plan_tool/roadmap_versions.py:load_stored_version` only to read predecessor content and legacy history. `AcceptedRoadmapHead` remains the artifact selector.

- **Legacy artifact vocabulary:** Read legacy embedded rows through `plan_tool/roadmap_artifacts.py:FeedbackRow`, `FeedbackState`, `FeedbackTarget`, and `REVIEW_ROW_KEYS`. Do not treat these rows as mutable after migration.

- **Publication boundary:** Use `plan_tool/roadmap_revision_publish.py:roadmap_writer_guard` and `plan_tool/roadmap_revision_publish.py:publish_roadmap_generation` for coordinated ledger-state changes. Preserve its recovery and final-recheck behavior.

## Files (creates vs edits)

- **New files:**
  - `plan_tool/roadmap_feedback_ledger_run.py` — Guarded runtime operations for explicit legacy import, reviewer-ledger validation and mutation, processing readiness, and predecessor-grouped display data.
  - `tests/test_roadmap_feedback_ledger_run.py` — Focused migration, edit, grouping, refusal, and preservation tests.

- **Existing files (edits only):**
  - `plan_tool/roadmap_feedback_ledger.py` — `LegacyFeedbackSource` and the item's `legacy_source` field, the `LEGACY_BLANK_REQUEST_MARKER` constant and the reopen/edit guard that keeps it off an `open` item, `unresolved_target_fingerprint`, and the public `is_valid_item_id` predicate that migration normalizes against.
  - `tests/test_roadmap_feedback_ledger.py` — Leaf tests for the `legacy_source` render, the snapshot exclusion, and the unresolved fingerprint.
  - `ROADMAP_FEEDBACK_FORMAT.md` — The `legacy_source` field in the worked ledger and the legacy-migration mapping.

## Implementation

- **Make this module the runtime owner of mutable ledger actions.** Provide public operations with clear result or refusal records for explicit migration, loading a processing-ready ledger, validating/submitting reviewer edits, and rendering or returning predecessor-grouped sections. Keep the module narrow: callers choose commands later, while this module owns the guarded domain behavior.

- **Require explicit legacy migration.** Admit import only for the step 2 migration-pending state. Read embedded feedback directly from the current legacy working artifacts on disk — step 2 blocks every old write route (stage regeneration and feedback processing alike) for the entire migration-pending window, so these bytes are the frozen source, not a separately preserved immutable version. Convert every preserved row through the step 1 ledger contract, record migration completion, and publish the ledger and completion record together under `roadmap_writer_guard`.

- **Normalize legacy rows the ledger represents differently; never abort on them.** Keep a legacy feedback id verbatim when it matches the ledger's item-id syntax and is unique across all four artifacts (legacy ids are unique per artifact only). Otherwise mint `legacy-<artifact_key>-<first 12 hex digits of SHA-256 over artifact key, row position, and legacy id>`, so re-running over the frozen source yields identical ids. Record every migrated item's origin in `legacy_source` (`artifact_key`, `feedback_id`); a reviewer-created item renders an explicit `legacy_source: null`. Import a row target that no longer names one live design row (a removed row, a `hosting` or `store` row, an unknown id) unchanged and bound to the accepted root, with a fingerprint over `selected: null` that no live target can equal, so the item stays ineligible until a reviewer retargets, defers, or closes it. Import an empty `proposed_response` on an `open` or `deferred` row as no proposal. Import a row whose `request` is empty or whitespace only as a `closed` item with no proposal, whatever the row's state, carrying the fixed marker `(legacy feedback row had no request text)` as its `request`: the ledger requires reviewer text, a closed item is never eligible, and so the marker never reaches a candidate as an instruction; `legacy_source` records that the text is a marker, and the reopen and edit actions refuse to open an item that carries the marker with a `legacy_source`, so reopening it or editing only its target is refused with a named error until an edit supplies non-blank request text, using migration's own no-request-text predicate (`not request.strip()`), so an edit that supplies only blank text is refused on any migrated item, not only a marker item. The guard sits at those actions, not in the item schema, so migration never refuses a legacy row whose own words equal the sentence and a ledger hand-edited to `open` still loads. A refusal from any ledger validator names the artifact and feedback id and never carries the row's text or a raw validation input. Deliberately not imported: removal records and `feedback_reopen` records, which remain in the frozen artifacts as non-authoritative history.

- **Parse each artifact once per migration pass.** Fingerprint every row's target through one per-call parse cache (the optional `parsed` argument of `target_fingerprint`), so migration parses each artifact once per pass rather than once per row.

- **Recheck the working-artifact bytes as defense-in-depth.** Immediately before publishing the import, re-verify under `roadmap_writer_guard` that the read legacy working artifacts still match what enrollment classified as migration-pending (e.g. by recomputing the same content check step 2 used to classify the roadmap). Refuse the import — without publishing a partial or wrong ledger — if that content changed, rather than trusting step 2's block was never bypassed (a manual file edit outside the tool, or a future code path that forgets the block, must not corrupt migration).

- **Make repeated migration safe.** A second request after a successful import must return the recorded completion outcome without duplicating items, replacing ledger fields, or rewriting immutable versions. A malformed legacy source, conflicting completion record, or interrupted publication must refuse or recover through the existing publication path rather than guessing.

- **Keep one mutable authority.** After successful migration, read and mutate only the ledger. Embedded legacy feedback remains available only as frozen historical content. Before migration completes, ledger-based candidate, review, promotion, and ordinary-feedback callers refuse with the deterministic `migration-required` result — steps 1, 3, and 5 own that refusal via `check_ledger_processing_ready`, not this module; do not silently import or fall back to embedded rows.

- **Validate reviewer edits against the current processing source.** For submit, retarget, and request changes, resolve the selected accepted-root/active-candidate source and use step 1’s target fingerprint rules before publishing canonical ledger bytes. Preserve an item whose target is stale or absent; only a reviewer may retarget, defer, or close it.

- **Preserve stable identity and define state effects.** Adding feedback creates a reviewer-owned stable-id item. Retargeting keeps that id but updates its submitted-against predecessor and moves it to the new predecessor group. Editing a request or target, or reopening an `awaiting-review`, `deferred`, or `closed` item, must clear live proposal fields and set the item to `open`. Closing any item must clear live proposal fields and set it to retained `closed`.

- **Leave stale proposals visible only when lifecycle actions leave them untouched.** Rejection and discard are not reviewer-edit operations here: they retain the existing ledger proposal as stale evidence and do not change the candidate review or active pointer. A later reviewer reopen, retarget, request edit, or close applies the state rules above while immutable candidate evidence remains unchanged.

- **Render predecessor groups deterministically.** Build human-facing groups from each item’s submitted-against predecessor. Render the current accepted-root/active-candidate pair before historical predecessor groups, then use a stable order for the remaining groups and their items. A retargeted item must appear only in its new group.

- **Reuse existing authority instead of copying it.** Use `plan_tool/roadmap_revision_publish.py:roadmap_writer_guard` for serialization and the landed step 1 serializer for canonical ledger bytes. Do not duplicate the legacy selector rules in `plan_tool/roadmap_feedback.py:parse_feedback_selector` or the existing artifact reopen mutation in `plan_tool/roadmap_feedback_reopen.py:reopen_feedback`; those operate on embedded artifact feedback and must remain outside the ledger path.

- **Do not widen this module into candidate orchestration.** `plan_tool/roadmap_candidate_run.py:CandidateProposalAdmission` is the current candidate-storage boundary and step 5 changes its shape. This module may read the landed processing-pair contract and recheck it under the guard, but it must not create candidates, modify reviews, replace active pointers, or write accepted-head state.

## Tests

### Tests for this step

- `test_ledger_native_state_is_ready_without_migration` — asserts a feedback-free enrolled roadmap loads as ledger-ready without an import.

- `test_migration_pending_state_refuses_ledger_processing` — asserts every processing-facing load returns `migration-required` before explicit import and does not write ledger or candidate state.

- `test_explicit_legacy_migration_imports_every_embedded_row_once` — asserts import preserves every embedded row's target, request, state, and proposal fields in the canonical ledger and keeps a representable unique legacy id verbatim.

- `test_a_row_target_naming_no_live_design_row_imports_unchanged_and_never_becomes_eligible` — asserts a removed-row, mistyped-id, `hosting`, and `store` target each import unchanged with the unresolved fingerprint and are never returned by `eligible_reviewer_items`, beside an eligible control item.

- `test_repeated_legacy_ids_import_under_ids_minted_from_artifact_position_and_legacy_id` — asserts a legacy id repeated across artifacts or within one imports under literal, documented minted ids that each name their `legacy_source`.

- `test_a_legacy_id_the_ledger_cannot_carry_imports_under_a_minted_id_that_names_it_as_the_source` — asserts unsafe ids (space, non-ASCII, leading dash, over-length) import under minted ids.

- `test_a_verbatim_legacy_id_that_equals_a_minted_id_refuses_the_import_and_keeps_the_ledger_pending` — asserts a collision after normalization refuses and leaves the pending ledger bytes unchanged.

- `test_an_empty_proposed_response_on_an_open_or_deferred_row_imports_as_no_proposal` — asserts both blank-response spellings import with no proposal.

- `test_a_blank_legacy_request_imports_as_one_closed_item_carrying_the_marker_and_its_source` — asserts an empty, space-only, and mixed-whitespace request each import as one closed item with the marker request, no proposal, and its `legacy_source`, and the ledger reaches `ledger-native`.

- `test_a_blank_request_row_ends_closed_whatever_its_legacy_state_and_drops_a_live_proposal` — asserts the stated carve-out: an `open`, `deferred`, or `awaiting-review` row with a blank request ends `closed` with no proposal, while a non-blank row keeps its state.
- `test_a_blank_request_marker_item_cannot_leave_closed_without_new_request_text` — asserts reopen, a target-only edit, and a retarget each refuse on a marker item with a named ledger error that carries no validation dump, and the ledger bytes unchanged.
- `test_an_edit_that_supplies_only_whitespace_cannot_open_a_blank_request_marker_item` — asserts an edit whose request is only whitespace refuses on a marker item with the ledger bytes unchanged.
- `test_a_blank_edit_cannot_open_any_migrated_item_and_refuses_with_the_named_error` — asserts an empty or whitespace-only edit refuses with the named error on a marker item and on a migrated item with real text, leaving the ledger bytes unchanged.
- `test_a_blank_request_marker_item_becomes_eligible_once_a_reviewer_supplies_request_text` — asserts an edit that supplies text replaces the marker, keeps `legacy_source`, and makes the item eligible.
- `test_a_native_item_whose_own_words_equal_the_marker_text_can_still_be_reopened` — asserts the carve-out: the refusal keys on the marker and a `legacy_source`, so a reviewer-written item with the same sentence reopens normally.
- `test_a_legacy_row_whose_own_words_are_the_marker_sentence_migrates_as_an_ordinary_open_item` — asserts migration imports a non-blank legacy row carrying the sentence as an open, eligible item.
- `test_a_marker_item_hand_edited_to_open_still_loads_and_the_named_exit_still_runs` — asserts the ledger still parses after a hand edit to `open` and an edit that supplies request text still runs.

- `test_a_blank_request_item_is_never_eligible_and_its_marker_never_reaches_a_batch_context` — asserts the marker item is not returned by `eligible_reviewer_items`, not among a batch's reviewer items, and absent from every byte of the capsule, beside an eligible control item.

- `test_a_ledger_holding_only_a_blank_request_item_has_no_batch_work` — asserts a ledger whose only item is a blank-request import yields the no-work outcome.

- `test_a_migrated_item_keeps_its_source_through_every_reviewer_action_and_a_native_item_has_none` — asserts `legacy_source` survives defer, edit, retarget, and close, and a reviewer-created item renders `legacy_source: null`.
- `test_migration_parses_each_target_artifact_once_however_many_legacy_rows_target_it` — asserts the parse count is the same for one legacy row as for five.

- `test_a_legacy_row_the_ledger_rejects_refuses_by_naming_the_row_and_never_echoes_its_input` — asserts a validator refusal names the artifact and feedback id, carries no raw validation input or row text, and leaves migration pending.

- `test_removal_and_reopen_records_are_deliberately_not_imported_and_the_frozen_artifacts_never_change` — asserts the stated carve-out: removal rationales and reopen nonces never reach the ledger, and the working artifacts' bytes are unchanged.

- `test_completed_legacy_migration_is_idempotent` — asserts a repeated migration request returns the recorded completion without duplicate items or changed ledger bytes.

- `test_migration_keeps_embedded_feedback_as_read_only_history` — asserts migration does not rewrite the legacy working artifacts' embedded feedback and later mutable edits affect only the ledger.

- `test_migration_refuses_when_legacy_working_artifacts_changed_since_classification` — asserts the publication-window recheck detects legacy working-artifact bytes that no longer match enrollment's migration-pending classification and refuses the import without publishing a partial ledger.

- `test_migration_failure_preserves_no_partial_second_authority` — asserts malformed input or a refused publication leaves no partly imported writable ledger.

- `test_submit_new_feedback_updates_only_the_ledger` — asserts a valid new item is persisted without changing accepted-version content, active candidate, or immutable candidate evidence.

- `test_retarget_keeps_item_id_and_moves_predecessor_group` — asserts retargeting retains the item id, records the new predecessor and fingerprint, and renders the item only under its new group.

- `test_request_or_target_edit_reopens_and_clears_live_proposal` — asserts edits to either field set `open` and clear the response and candidate-provenance fields.

- `test_reopen_every_retained_ineligible_state_clears_live_proposal` — asserts `awaiting-review`, `deferred`, and `closed` items reopen as `open` with proposal fields cleared.

- `test_close_retains_identity_and_clears_live_proposal` — asserts close retains the item and its current reviewer fields, makes it ineligible, and clears only live proposal fields.

- `test_rejection_and_discard_leave_ledger_proposal_unchanged` — asserts lifecycle resolution leaves the stale ledger proposal visible and does not modify the active pointer or candidate review.

- `test_grouped_render_lists_current_processing_pair_before_history` — asserts the current root/active group precedes historical predecessor groups with stable item ordering.

Every test in `tests/test_roadmap_feedback_ledger_run.py` must be green before this step is complete.

## Acceptance criteria

- A ledger-native enrollment is ready for ledger operations without a migration record.

- A migration-pending roadmap returns `migration-required` for ledger processing until explicit migration completes.

- Explicit migration imports every legacy embedded feedback row exactly once and records completion atomically with the ledger state.

- A legacy row the ledger cannot carry verbatim — an unsafe or repeated id, a row target that names no live design row, an empty proposed response, a blank request — imports normalized and names its source in `legacy_source` instead of aborting migration.

- Repeating a completed migration does not duplicate, rewrite, or remove ledger items.

- A publication-window recheck refuses the import — with no partial ledger written — if the legacy working artifacts changed since enrollment classified the roadmap as migration-pending.

- Migration and later ledger edits never rewrite immutable roadmap versions, advance `AcceptedRoadmapHead`, create a candidate, alter active-candidate state, or modify immutable candidate evidence.

- A reviewer can create, retarget, defer, close, and reopen a retained item through validated ledger operations.

- Retargeting preserves a reviewer item’s stable id and places it under the new predecessor group.

- Editing a request or target, reopening an ineligible item, and closing an item apply the defined proposal-field clearing and lifecycle state changes.

- Rejection and discard retain an existing ledger proposal as stale evidence until a reviewer changes that item.

- The predecessor-grouped ledger places the current root/active pair before historical groups.

- `tests/test_roadmap_feedback_ledger_run.py` passes.

## References

- [Models — Pydantic Documentation](https://docs.pydantic.dev/latest/concepts/models/) — Read strict-model and frozen-record guidance for the persisted migration and mutation results.

- [PyYAML Documentation](https://pyyaml.org/wiki/PyYAMLDocumentation) — Read safe loading and controlled dumping guidance for reviewer-edited ledger text.

- [hashlib — Secure Hashes and Message Digests](https://docs.python.org/3.13/library/hashlib.html) — Read SHA-256 APIs used by target and ledger evidence.

- [os.replace — Miscellaneous Operating System Interfaces](https://docs.python.org/3.13/library/os.html#os.replace) — Read atomic replacement behavior used by the existing publication path.

- [fcntl — The fcntl and ioctl System Calls](https://docs.python.org/3.13/library/fcntl.html) — Read advisory locking behavior behind the existing roadmap writer guard.

## Applicable guardrails

- **The plan’s “## Scope guardrails”, mutable ledger authority** — Keep reviewer input outside canonical artifacts. This module may change only the ledger and its migration state.

- **The plan’s “## Scope guardrails”, immutable batch evidence** — Do not recompute, replace, or consume candidate batch evidence from a later ledger edit.

- **The plan’s “## Scope guardrails”, existing publication ownership** — Reuse the existing writer guard and durable publication path. Do not add another transaction, version chain, candidate store, review store, or accepted-head writer.

- **The plan’s “## Out of scope”, automatic feedback changes** — Require explicit reviewer actions for retargeting, deferral, closing, and reopening; do not infer any of them from changed roadmap content.

- **The plan’s “## Out of scope”, interface limits** — Keep the surface to ledger-file validation and focused mutation operations. Do not add a general editing interface.

## Deferred

- CLI registration and command argument handling — Step 9 owns user-facing routing to these ledger operations.

- Candidate review rejection and discard lifecycle changes — Step 8 owns the candidate-review boundary; this step only preserves their ledger effects.

- Compatibility documentation and retirement of ordinary embedded-feedback processing — Step 10 owns the operator-facing compatibility boundary.
