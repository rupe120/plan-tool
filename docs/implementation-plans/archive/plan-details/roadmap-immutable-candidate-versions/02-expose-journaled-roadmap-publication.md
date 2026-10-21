> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 2 — Expose journaled roadmap publication while preserving every overwrite, rollback delete, and journal cleanup

## Summary

Expose the existing journaled generation boundary in `plan_tool/roadmap_revision_publish.py` for future accepted-head writers, without changing current roadmap publication behavior. Keep every existing stage, revision, reopen, baseline, and structural publication path on that one boundary. On green, a guarded publication records exact old and new member bytes before any replacement, recovers only recorded partial work, and removes the journal only when it is safe.

## Table of Contents

- [Summary](#summary) — The step’s outcome and narrow footprint.
- [Table of Contents](#table-of-contents) — Links to each section.
- [Why](#why) — Why accepted-head writers need the existing journal protocol as a shared API.
- [Input](#input) — The journal and writer-lease contracts this step consumes.
- [Files (creates vs edits)](#files-creates-vs-edits) — The two scoped files and their roles.
- [Implementation](#implementation) — The public journal boundary and recovery rules it must preserve.
- [Tests](#tests) — Direct coverage for publication, rollback, refusal, and cleanup.
- [Acceptance criteria](#acceptance-criteria) — Observable completion conditions.
- [References](#references) — Atomic replacement guidance for the durable write boundary.
- [Applicable guardrails](#applicable-guardrails) — Plan fences that keep this a narrow refactor.

## Why

`plan_tool/roadmap_revision_publish.py:_publish_generation()` already owns the exact journal-before-write, verify-after-write, and recover-or-refuse behavior that accepted-head enrollment and promotion need. Keeping it private would invite later version writers to copy a recovery protocol that already handles absent members, partial writes, and stale final checks. Make that boundary reusable while keeping current publication wrappers and recovery entry points on the same behavior.

## Input

- **Generation record:** `plan_tool/roadmap_source_identity.py:PendingGeneration` contains one non-empty ordered tuple of `GenerationMember` records. Each member binds a relative path plus its previous and replacement bytes, including `None` for an absent file.

- **Journal encoding:** `plan_tool/roadmap_source_identity.py:render_pending_generation()` and `load_pending_generation()` validate the existing journal format. This step must consume that format unchanged; it must not add version-storage fields or alter journal schema.

- **Writer lease:** `plan_tool/roadmap_revision_publish.py:RoadmapWriterToken`, `roadmap_writer_guard()`, and `require_roadmap_writer_token()` define who may mutate one roadmap. The exposed boundary must retain that active, matching lease requirement.

- **Durable writes:** `plan_tool/fileio.py:durable_write_bytes()` is the write primitive for both the journal and present generation members. It preserves exact supplied bytes and syncs the completed replacement.

## Files (creates vs edits)

- **New files:** None.

- **Existing files (edits only):**
  - `plan_tool/roadmap_revision_publish.py` — Expose the existing `_publish_generation()` protocol behind a guarded public boundary, and route each current publication wrapper through it without changing its semantic checks or output.
  - `tests/test_roadmap_revision_publish.py` — Add direct tests for the exposed boundary’s journal ordering, write and delete behavior, recovery, refusal, and cleanup rules.

## Implementation

- **Expose one guarded byte-publication boundary.** Promote the protocol now held by `plan_tool/roadmap_revision_publish.py:_publish_generation()` into a public API that accepts an already-built `PendingGeneration`, the roadmap identity, and its active `RoadmapWriterToken`. Keep semantic validation outside this boundary: it publishes recorded member states and must not parse artifacts, run gates, or infer accepted-head policy.

- **Keep the active lease mandatory.** The exposed API must verify its token through `plan_tool/roadmap_revision_publish.py:require_roadmap_writer_token()` before creating a journal or touching a member. Do not expose a root-path-only writer that lets callers bypass the roadmap writer guard.

- **Preserve the publication order.** Reject an existing pending journal, durably write the complete journal through `plan_tool/roadmap_source_identity.py:render_pending_generation()`, run any final recheck callback, then apply each member’s recorded replacement state. The final recheck must still see the journal, because structural publication uses that state to admit its exact in-flight generation.

- **Preserve exact member operations.** Keep `plan_tool/roadmap_revision_publish.py:_replace_generation_members()` as the byte-level operation: present replacement bytes go through `plan_tool/fileio.py:durable_write_bytes()`, while `None` deletes the member. Do not normalize, re-render, or skip a member because its content looks unchanged.

- **Keep cleanup conditional.** After all writes, read every member back and remove the journal only when every observed state equals its recorded replacement state. If a replacement or verification fails after journaling, leave the journal for `recover_roadmap_publication()`.

- **Keep refusal cleanup separate from recovery.** If the final recheck callback raises before any member replacement, remove the just-written journal and leave every member unchanged. This is a safe pre-write refusal, not an interrupted generation.

- **Preserve conservative recovery.** `plan_tool/roadmap_revision_publish.py:recover_roadmap_publication()` must remove only the journal when all members match either the recorded old state or the recorded new state. For a mixed state containing only recorded old/new bytes, restore every old state and verify it before cleanup; restoring an old `None` must delete a newly created member. If any member contains unrecorded bytes, raise `RoadmapPublicationRecoveryError` without overwriting members or removing the journal.

- **Route existing wrappers through the exposed boundary.** Keep `publish_stage_artifact()`, `enroll_stage_baselines()`, `publish_revision_candidate()`, `publish_feedback_reopen_candidate()`, and `publish_structural_revision_proof()` responsible for their existing artifact, gate, source, feedback, and seed-state checks. Their final mutation must use the shared exposed publisher rather than retaining a second journal flow.

- **Keep current recovery consumers unchanged.** `plan_tool/roadmap.py:run_roadmap()`, `plan_tool/roadmap_revision_run.py`’s local-revision entry, `plan_tool/roadmap_structural_revision_run.py:run_structural_revision()`, `plan_tool/roadmap_feedback_reopen.py:run_confirmed_feedback_reopen()`, and `plan_tool/roadmap_impact_run.py:run_roadmap_impact_analysis()` remain callers of `recover_roadmap_publication()`. This step changes neither their control flow nor their result contracts.

- **Reject duplicated recovery logic.** Do not have the future version modules copy the journal writer or recovery rules. A shared public boundary is the narrow alternative to a second transaction implementation.

## Tests

### Tests for this step

- `test_exposed_generation_publication_requires_an_active_matching_writer_token` — A missing, inactive, or foreign token raises before a journal or member is created.

- `test_exposed_generation_publication_journals_before_final_recheck_and_cleans_up_after_success` — The callback observes the complete journal, every member reaches its recorded replacement bytes, and the journal is absent after verified success.

- `test_exposed_generation_publication_preserves_exact_member_bytes_and_absent_replacements` — Present members retain the supplied bytes while a replacement `None` deletes only its recorded member.

- `test_exposed_generation_publication_recheck_refusal_keeps_members_and_cleans_journal` — A final recheck failure leaves all members unchanged and removes the pre-write journal.

- `test_exposed_generation_publication_failure_leaves_journal_for_guarded_recovery` — A failure after a partial recorded write leaves the journal so `recover_roadmap_publication()` can restore the prior generation.

- `test_recovery_restores_mixed_members_and_deletes_new_members` — Recovery restores every recorded old state, including deleting a member whose old state is absent.

- `test_recovery_cleans_only_the_journal_for_wholly_old_or_wholly_new_generations` — Recovery does not rewrite members when the generation is entirely unstarted or entirely committed.

- `test_recovery_refuses_unknown_member_bytes_without_cleanup` — Unrecorded bytes cause `RoadmapPublicationRecoveryError` while both the changed member and journal remain in place.

Every test in `tests/test_roadmap_revision_publish.py` must be green before this step is complete.

## Acceptance criteria

- The shared public publication boundary requires a matching active `RoadmapWriterToken` and accepts a validated `PendingGeneration` without interpreting roadmap semantics.

- Every current publication wrapper in `plan_tool/roadmap_revision_publish.py` reaches the same shared journal boundary.

- A successful publication records the journal before its final recheck, applies every recorded replacement state, verifies all resulting bytes, and then removes the journal.

- A replacement `None` deletes its recorded member, and recovery of an interrupted creation restores an absent old state by deleting that new member.

- A failed final recheck removes its journal without changing any generation member.

- A write or verification failure after journaling leaves the journal for guarded recovery.

- Recovery removes the journal without changing members only for wholly old or wholly new recorded states; unknown bytes cause refusal without an overwrite or journal cleanup.

- `tests/test_roadmap_revision_publish.py` passes.

## References

- [os — Miscellaneous operating system interfaceshttps: — Review atomic replacement semantics that underpin durable member publication.

## Applicable guardrails

- **The plan’s “## Scope guardrails”, binary observables** — Preserve the exact recorded member bytes and state transitions; this refactor must not introduce semantic equivalence checks.

- **The plan’s “## Scope guardrails”, allowed reorganization** — Limit the change to one shared publication boundary. Do not reorganize roadmap artifact models or unrelated pipeline control flow.

- **The plan’s “## Scope guardrails”, allowed behavior changes** — Keep existing unversioned publication behavior unchanged; version enrollment and accepted-head selection remain later work.

- **The plan’s “## Out of scope”, recovery and operational hardening** — Reuse the existing durable recovery primitive without expanding it into broader crash handling, concurrent workflows, retention, or migration work.
