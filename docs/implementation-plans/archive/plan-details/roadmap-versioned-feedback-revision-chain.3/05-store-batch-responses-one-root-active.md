> **Auto-archived**: this plan was swept on 2026-11-05 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 5 — Store batch responses with one root-and-active-candidate pointer while retaining superseded candidate history

<!-- plan-tool:detail-format-version: 1 -->

## Summary

Update `plan_tool/roadmap_candidate_run.py` to persist a successful batch response as an immutable candidate plus one root-bound active-candidate pointer. Store the exact batch evidence in the same guarded publication that writes the admitted reviewer responses and the successor-derived context to the mutable ledger. A successful successor replaces only the active pointer; the former candidate remains readable immutable history marked as superseded. On green, retries and failures before storage leave the ledger and pointer unchanged, while storage refuses a changed processing pair or changed admitted item without losing unrelated reviewer edits.

## Table of Contents

- [Summary](#summary) — Reviewer-level outcome of candidate storage.
- [Table of Contents](#table-of-contents) — Links to each section.
- [Why](#why) — Why the existing one-candidate admission cannot represent a revision chain.
- [Input](#input) — Upstream batch and materialization contracts this step consumes.
- [Files (creates vs edits)](#files-creates-vs-edits) — Production and test changes in scope.
- [Implementation](#implementation) — Root pointer, atomic storage, evidence, and refusal rules.
- [Tests](#tests) — Focused lifecycle and failure-preservation coverage.
- [Acceptance criteria](#acceptance-criteria) — Observable completion conditions.
- [References](#references) — Serialization, validation, hashing, and publication references.
- [Applicable guardrails](#applicable-guardrails) — Plan boundaries that constrain this storage path.
- [Deferred](#deferred) — Later lifecycle owners outside this step.

## Why

`plan_tool/roadmap_candidate_run.py:CandidateProposalAdmission` currently binds one feedback selector, one predecessor, and one stored candidate for the roadmap lifetime. That shape cannot represent an accepted root plus a replaceable active candidate, nor can it retain a successful predecessor candidate while ordinary batch work creates its successor. This step makes candidate storage the single place where a validated batch becomes a root-bound active proposal without allowing mutable reviewer input or the accepted head to become an accidental source of truth.

## Input

- **Step 3 batch contract:** Consume step 3’s accepted-root identity, direct-source identity, ordered immutable reviewer-item snapshots, whole-ledger digest, and source-derived context. The landed `plan_tool/roadmap_candidate_context.py` records and names win over this detail.
- **Step 1 migration-readiness helper:** Consume `check_ledger_processing_ready` for the publication-window recheck below. Step 3 already refuses batch construction for a `migration-pending` roadmap; this step rechecks the same state under the writer guard as defense-in-depth, matching the existing recheck-under-guard pattern for the processing pair and admitted items.
- **Step 4 materialization contract:** Consume step 4’s feedback-free successor artifacts, admitted-item response patch, and fresh successor-derived set. `plan_tool/roadmap_candidate.py:materialize_candidate` remains the authority for validating model output before storage.
- **Immutable version contract:** Retain `plan_tool/roadmap_versions.py:create_candidate_version`, `PreparedRoadmapVersion`, `StoredRoadmapVersion`, and `load_stored_version` for immutable candidate identity and stored-member validation.
- **Publication contract:** Reuse `plan_tool/roadmap_revision_publish.py:roadmap_writer_guard` and `publish_roadmap_generation` for every state change that must become visible together. Do not create a parallel candidate transaction or pointer writer.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `plan_tool/roadmap_candidate_run.py` — Replace selector-bound admission behavior with root-and-active-candidate state, batch-aware candidate evidence, guarded storage, and immutable supersession history.
  - `tests/test_roadmap_candidate_run.py` — Replace selector-focused storage coverage and add root/source, pointer, supersession, atomicity, and refusal tests.

## Implementation

- **Store one explicit processing pair.** Evolve the state represented by `CandidateProposalAdmission`, `candidate_admission_path`, and `load_candidate_admission` so it identifies the accepted root and, when present, exactly one active candidate for that root. The active candidate is a pointer, not a second accepted-head selector.

- **Keep the ledger route selector-free.** `run_initial_candidate_proposal` takes no selector on a roadmap that has a ledger: the caller passes `None`, the batch route never records one, and the run log’s argv carries no selector argument. The parameter stays, typed optional, only for the ledger-less selector-era route, which refuses a proposal that supplies none.

- **Bind candidate evidence to the root and direct source.** Update `CandidateProposalEvidence`, `render_candidate_evidence`, `parse_candidate_evidence`, `load_stored_candidate_proposal`, and `_validate_candidate_evidence` to retain and reproduce the exact step 3 batch, including its root identity, source identity, immutable reviewer snapshots, and source-derived context. Validate that the source ancestry reaches the declared root before publication or later reuse. `source_ancestry_to_root` walks the stored predecessor records from a candidate’s source up to the root; every intermediate version must be a stored candidate, and an unrelated, missing, or cyclic chain refuses. The walked chain is passed to `build_candidate_context`, so a batch can start from a source more than one hop from the root, and a candidate’s evidence is validated against that chain each time it is loaded. A batch candidate’s reload also recomputes `predecessor_diff` from its source and stored artifacts and refuses a difference, because that diff is the one stored field the batch flow reads (the question prompt and `diff-row` anchors). Deliberately not recomputed for batch evidence: `gate_evidence`, `review_requirement`, `content_identity`, and capsule reproduction. Nothing in the batch flow reads the first two; the identity is bound by the stored version record and `_capsule_is_intact`, because batch evidence persists no response patch from which it could be recomputed.

- **Key reentry on step 3's batch identity, not on the processing pair alone.** `run_initial_candidate_proposal` must build step 3's batch fresh on every invocation — building a batch is deterministic and calls no backend, so this costs nothing when nothing changed. When an active candidate already exists, compare the freshly-built batch's identity (root, source, whole-ledger digest, ordered reviewer snapshots, and derived context — the same digest step 3 already guarantees changes when any bound input changes) against the active candidate's stored batch identity. An exact match is the reentry case: return the stored active candidate with no model call. Any difference — new eligible reviewer items, changed derived context, or anything else step 3's digest is sensitive to — is not reentry, even though the accepted root and direct source (the active candidate) are unchanged; proceed through step 4 and storage to create a superseding successor, per Architecture's "an ordinary batch may use the active candidate as its direct source to create a superseding successor." Only an entirely empty fresh batch is step 3's separate no-work case.

- **Make a successful candidate active atomically.** Adapt `run_initial_candidate_proposal` and `_store_candidate` so a valid step 4 result publishes, in one `publish_roadmap_generation` call:
  - the immutable candidate version and adjacent evidence;
  - the root-bound active-candidate pointer;
  - the admitted reviewer-item response changes supplied by step 4; and
  - the candidate’s fresh derived set.

  The accepted head must remain unchanged. A candidate is active only after the complete generation publishes.

- **Replace the pointer without deleting history.** When the direct source is an active candidate, a successful successor must replace that pointer only after successor storage succeeds. Persist enough immutable status or relation evidence beside the former candidate to identify it as superseded by the successor while retaining its original batch, response, artifacts, and derived set. Do not make superseded history another candidate-selection path. The relation is one immutable `CandidateSupersession` record per superseded candidate (`candidate-supersessions/<superseded candidate id>.json`, naming the root, the superseded candidate, and its successor), written by `build_supersession_member` in the same generation as the pointer replacement; a sealed review replacement writes the same record in the seal’s generation. It is history only, and a record that already exists for that candidate fails the whole generation.

- **Expose one bare pointer-release helper, and one terminal-resolution record built on it.** Add a guarded-publication helper that clears the root's active-candidate pointer as a `PendingGeneration` member on its own — this is the one primitive every releasing step needs, including promotion (step 9), which clears the pointer without marking the candidate as terminal history. Separately, define a typed, canonically rendered `CandidateTerminalResolution` record — identifying the exact released candidate, its root/source/batch binding, and a closed `reason` (`rejected`, `discarded`, or `settled`) — that pairs the bare release with a terminal-history entry for the three outcomes where the candidate does not become the new root. This step owns both the helper and the record's shape; it does not itself trigger a release. Steps 7 and 8 each supply their own trigger and `reason` value and must consume this record (not define a second one); step 9 consumes only the bare release. A released pointer names no candidate and keeps the root it was released under, so the batch runner judges only a pointer that names an active candidate against the current accepted root.

- **Recheck only storage-relevant mutable state.** Under `roadmap_writer_guard`, re-read the current root/active processing pair, the ledger's migration-readiness state via `check_ledger_processing_ready`, and each admitted reviewer-item snapshot before `_store_candidate` publishes. Refuse with the deterministic `migration-required` result if the roadmap became `migration-pending` since step 3's batch was built, and refuse if the processing pair or an admitted snapshot changed. Treat the recorded whole-ledger digest as immutable model-input evidence only: an unrelated ledger edit must survive unchanged and must not block storage of the admitted batch. `publish_roadmap_generation` never compares a member’s recorded old bytes with the file on disk, so the recheck runs again inside the publication window (`require_batch_state_unchanged`: the exact pointer and the exact ledger bytes), not only before it. Every deterministic storage-window refusal — `migration-required`, a changed pair, a changed admitted item, an identity collision, an existing supersession record — is a `CandidateStorageRefusal`, which the batch runner reports as `refused` (exit 2) rather than `failed`; the selector-era storage path keeps `failed`.

- **Preserve state on attempts that do not store.** Keep `CandidateProposalResult`, `_result`, and the existing run-log behavior aligned with the new lifecycle. Backend failures, rejected responses, interrupts, materialization refusal, and any failure before publication must leave the active pointer, ledger, accepted head, and existing candidate history unchanged. The batch route records the same terminal diagnostics as the selector route: a rejected reply, whether it fails to parse or is refused at materialization, writes a parse-failure receipt holding the exact bytes and the attempt that produced them, while a storage failure after an accepted reply writes none. The call is counted before it is made, so an error raised by the model call still reports one call.

- **Keep immutable storage collision-safe.** Retain the no-overwrite checks in `_store_candidate` for stored version members and `candidate_evidence_path`. A collision or failed evidence replay must refuse before `publish_roadmap_generation`, leaving the prior pointer and all existing bytes intact.

- **Keep every selector-era identity and byte string.** A field added for the batch route never moves a value stored before it, because stored selector-era records are recomputed from their bytes on every review, replacement, and promotion. `_content_identity` hashes `response_patch` and `derived_feedback` only for a candidate that carries a response patch. `CandidateProposalAdmission` renders `root_version_id` and `active_candidate_version_id` only when at least one is set; a batch admission always states both, with an explicit null for a released pointer. Golden values captured from the selector-era flow pin the candidate id, the content identity, the admission bytes, and the review seal.
- **Refuse a batch over an unpromoted selector-era candidate.** Before any model call, the batch runner refuses `unpromoted-candidate-lineage` when the current admission has no `root_version_id`, names a stored candidate, and that candidate's predecessor is still the accepted head, because the batch pointer would replace the admission and orphan the candidate's review lineage. An admission that names no stored candidate does not block, and neither does a lineage whose head has advanced past it. This is narrower than settlement's guard on purpose: the selector route has no release command, so refusing an admission with nothing to orphan would strand the roadmap.
- **Do not widen review or promotion here.** `plan_tool/roadmap_candidate_review.py` and `plan_tool/roadmap_version_promotion.py` consume the current admission and candidate evidence, but their replacement, rejection, discard, and promotion behavior belongs to later lifecycle steps. This step establishes the persisted root/active contract they will consume.

## Tests

### Tests for this step

- `test_initial_batch_storage_publishes_root_bound_active_candidate_without_moving_accepted_head` — asserts first successful storage records the accepted root, uses it as the direct source, and publishes an active candidate without changing `AcceptedRoadmapHead`.
- `test_successor_storage_uses_active_candidate_as_direct_source_and_replaces_only_the_pointer` — asserts a later valid batch stores a successor, points the same root to it, and does not create a second active branch.
- `test_successor_records_the_former_active_candidate_as_superseded_and_leaves_it_unmodified` and `test_first_batch_candidate_writes_no_supersession_record` — assert supersession writes one immutable record for the former candidate, leaves its stored bytes and evidence unchanged, and that a first candidate writes none.
- `test_existing_supersession_record_refuses_the_successor_and_leaves_the_pointer` and `test_supersession_record_requires_digest_identities_and_a_supported_schema` — assert an existing record fails the whole generation with the pointer unchanged, and that the record validates its identities.
- `test_third_batch_from_a_two_hop_active_candidate_stores_and_supersedes_it`, `test_source_ancestry_walk_lists_predecessors_up_to_and_including_the_root`, and `test_active_candidate_with_a_missing_ancestor_is_refused_on_reload_not_trusted` — assert a source that traces to its root through more than one hop is accepted, and a broken chain is refused on reload rather than trusted.
- `test_storage_updates_candidate_pointer_ledger_patch_and_derived_set_in_one_generation` — captures `publish_roadmap_generation` and asserts the visible state changes belong to one guarded generation.
- `test_storage_refuses_migration_pending_state_discovered_inside_the_publication_window`, `test_changed_admitted_item_refuses_storage_but_unrelated_ledger_edit_does_not`, `test_changed_active_pointer_refuses_storage_without_overwriting_ledger_or_history`, `test_identity_collision_with_existing_storage_refuses_without_publishing`, and `test_batch_storage_refuses_a_ledger_edit_that_lands_inside_the_publication_window` — assert every storage-window refusal is a deterministic `refused` result that writes nothing.
- `test_a_rejected_batch_reply_records_its_exact_response_receipt_and_failure_attempt`, `test_a_batch_materialization_refusal_records_the_reply_it_refused`, `test_batch_storage_failure_after_a_valid_reply_is_not_recorded_as_a_parse_failure`, and `test_a_backend_error_raised_during_the_batch_call_still_counts_the_call` — assert the batch route's terminal diagnostics: receipts for both kinds of rejected reply, none for a storage failure after an accepted reply, and a call count that survives an error in the model call.
- `test_batch_candidate_evidence_with_an_edited_predecessor_diff_is_refused_on_reload` and `test_batch_candidate_evidence_content_identity_is_bound_by_the_stored_record_not_recomputed` — assert an edited diff refuses on reload, and pin the carve-out that an edited content identity is refused by the stored record's binding rather than by recomputation.
- `test_a_released_pointer_naming_an_older_root_does_not_block_a_batch_for_the_current_root` and `test_an_active_pointer_naming_another_root_still_refuses_a_batch` — assert only a pointer that names an active candidate is judged against the current root.
- `test_selector_era_identity_and_admission_bytes_are_the_values_stored_before_the_batch_route` and `test_batch_admission_keeps_both_pointer_keys_including_a_null_for_a_released_pointer` — assert the selector-era candidate id, content identity, and admission bytes equal the values stored before the batch route, and that a batch admission still states both pointer keys.
- `test_a_ledger_batch_refuses_an_unpromoted_selector_era_candidate_and_changes_nothing`, `test_a_selector_era_admission_that_names_no_stored_candidate_does_not_block_a_ledger_batch`, and `test_a_ledger_batch_can_follow_a_promoted_selector_era_lineage` — assert the batch runner refuses only an unpromoted selector-era candidate, before any model call and without touching a byte.
- `test_changed_active_pointer_refuses_storage_without_overwriting_ledger_or_history` — asserts a processing-pair change prevents publication and preserves the later state.
- `test_storage_refuses_migration_pending_state_discovered_inside_the_publication_window` — asserts a roadmap that became `migration-pending` after step 3 built the batch but before publication refuses with the deterministic `migration-required` result and leaves the pointer, ledger, and history unchanged.
- `test_changed_admitted_item_refuses_storage_but_unrelated_ledger_edit_does_not` — distinguishes an edited admitted snapshot from an unrelated reviewer edit and proves the unrelated edit survives.
- `test_failed_or_interrupted_pre_storage_attempt_preserves_root_active_pointer_and_ledger` — asserts no pointer or mutable-state change occurs before successful storage.
- `test_candidate_storage_collision_or_unreproducible_evidence_preserves_existing_pointer` — asserts collision and evidence failures occur before publication.
- `test_reentry_loads_the_current_active_candidate_without_backend_call` — asserts an unchanged fresh batch identity (not merely an unchanged processing pair) returns the stored active candidate and makes no model call.
- `test_new_eligible_feedback_supersedes_active_candidate_despite_unchanged_processing_pair` — asserts new eligible reviewer items or changed derived context, with the accepted root and direct source otherwise unchanged, changes the fresh batch identity and proceeds to create a superseding successor rather than replaying reentry.
- `test_terminal_resolution_record_rejects_an_unclosed_reason` — asserts `CandidateTerminalResolution` accepts only `rejected`, `discarded`, or `settled` and refuses any other value.
- `test_bare_pointer_release_helper_clears_the_pointer_without_a_terminal_resolution` — asserts the bare release helper clears the active-candidate pointer as its own `PendingGeneration` member without requiring or writing a `CandidateTerminalResolution`.

Every listed test must pass before this step is complete.

## Acceptance criteria

- A successful first batch stores immutable candidate evidence that names its accepted root and direct source, then makes that candidate the root’s only active candidate without changing the accepted head.
- A successful batch from an active candidate stores a successor and replaces only the active pointer after the entire guarded generation succeeds.
- Reentry is decided by comparing the freshly-built batch identity to the active candidate's stored batch identity, not by comparing only the accepted root and direct source; new eligible input with an otherwise-unchanged processing pair still produces a superseding successor.
- The former active candidate remains readable immutable history with its original artifacts and batch evidence. The response text it proposed lives on the ledger item, not in its evidence.
- Candidate evidence refuses a source that does not trace back to its declared root, and batch evidence whose `predecessor_diff` differs from its stored bytes.
- A batch can start from an active candidate more than one hop from the root, and a released pointer that keeps an older root does not block it.
- A selector-era candidate stored before the batch route keeps recomputing to the identity and bytes it was stored with, and a ledger batch refuses to replace one that is still awaiting promotion.
- Candidate storage atomically publishes candidate bytes, evidence, active-pointer update, admitted response patch, and fresh derived set through `plan_tool/roadmap_revision_publish.py:publish_roadmap_generation`.
- A changed processing pair or admitted reviewer snapshot refuses storage with no candidate, pointer, or ledger overwrite.
- A roadmap that becomes `migration-pending` inside the publication window refuses storage with the deterministic `migration-required` result and no candidate, pointer, or ledger overwrite.
- An unrelated ledger edit remains unchanged and does not block storage of the exact admitted batch.
- Failed, rejected, interrupted, and pre-publication validation paths leave the accepted head, active pointer, ledger, and existing candidate history unchanged.
- A rejected batch reply leaves a parse-failure receipt with its exact bytes; a storage failure after an accepted reply does not.
- `CandidateTerminalResolution` records exactly one of `rejected`, `discarded`, or `settled` and is the one record shape steps 7 and 8 consume when they release an active candidate outside promotion.
- A bare pointer-release helper clears the active-candidate pointer as its own `PendingGeneration` member independent of `CandidateTerminalResolution`, so promotion (step 9) can reuse it without writing terminal-history evidence.
- `tests/test_roadmap_candidate_run.py` passes with the root/active lifecycle and failure-preservation coverage.

## References

- [Models — Pydantic Documentation](https://docs.pydantic.dev/latest/concepts/models/) — Read strict, frozen model validation for persisted admission and evidence records.
- [json — JSON Encoder and Decoder](https://docs.python.org/3.13/library/json.html) — Read canonical JSON serialization controls for exact persisted evidence bytes.
- [RFC 8785: JSON Canonicalization Scheme](https://www.rfc-editor.org/rfc/rfc8785.html) — Read reproducible JSON rules for batch and candidate identities.
- [hashlib — Secure Hashes and Message Digests](https://docs.python.org/3.13/library/hashlib.html) — Read SHA-256 byte digest behavior used by immutable evidence.
- [os — Miscellaneous Operating System Interfaces](https://docs.python.org/3.13/library/os.html#os.replace) — Read atomic replacement behavior relevant to durable publication.
- [fcntl — The fcntl and ioctl System Calls](https://docs.python.org/3.13/library/fcntl.html) — Read advisory locking behavior used by the roadmap writer guard.

## Applicable guardrails

- **The plan’s “## Scope guardrails”, immutable artifact authority** — Keep `AcceptedRoadmapHead` as the sole canonical-artifact selector; this step may publish an active-candidate pointer but must not advance or replace the accepted head.
- **The plan’s “## Scope guardrails”, exact batch binding** — Store and validate the exact root, direct source, reviewer snapshots, and source-derived context from the admitted batch; later ledger edits must not substitute any of them. The proposed response text is a ledger fact, not stored evidence.
- **The plan’s “## Scope guardrails”, failure preservation** — Refuse changed processing pairs or admitted items before publication while preserving reviewer edits and pointer state.
- **The plan’s “## Out of scope”, candidate branching** — Represent one active candidate for each accepted root and retain superseded candidates as history, not as concurrent processing branches.
- **The plan’s “## Out of scope”, candidate operation authority** — Consume step 4’s validated materialization output without changing stage operations or roadmap gate authority.

## Deferred

- Candidate review replacement, rejection, discard, and settlement resolution — Later lifecycle steps (7 and 8) supply the release trigger and `reason`; they consume this step's shared `CandidateTerminalResolution` record rather than defining their own.
- Accepted-head promotion and its active-pointer release — `plan_tool/roadmap_version_promotion.py` remains a later owner so this step does not change promotion behavior.
- Ledger command validation and reviewer-edit operations — Step 6 owns mutable reviewer workflows and their guarded persistence.
