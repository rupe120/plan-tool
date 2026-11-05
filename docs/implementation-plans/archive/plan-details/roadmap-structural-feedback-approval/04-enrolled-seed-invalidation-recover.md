> **Auto-archived**: this plan was swept on 2026-11-05 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 4 — Add enrolled seed invalidation and recover complete promotion publications

<!-- plan-tool:detail-format-version: 1 -->

## Summary

Extend `plan_tool/roadmap_revision_publish.py` so an enrolled structural promotion can add an invalidated seed-state member to its existing journaled publication generation. Keep recovery strict: it may clear a promotion journal only after every recorded selector, active-pointer, and seed-state member is present with the expected bytes. Preserve the existing un-enrolled pre-invalidation path and immutable version recovery rules. On green, `tests/test_roadmap_revision_publish.py` proves complete promotions recover without changing published bytes while interrupted or malformed promotions remain refused and recoverable.

## Table of Contents

- [Summary](#summary) — Reviewer overview of promotion seed invalidation and recovery.
- [Table of Contents](#table-of-contents) — Quick links to each section.
- [Why](#why) — Why the current promotion recovery shape is incomplete.
- [Input](#input) — Contracts this step reads from structural classification and publication state.
- [Files (creates vs edits)](#files-creates-vs-edits) — The two existing files changed by this step.
- [Implementation](#implementation) — Seed-member construction and strict completed-publication recognition.
- [Tests](#tests) — Focused coverage for complete and interrupted promotion journals.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Publication, version, seed, and feedback contracts.
- [Applicable guardrails](#applicable-guardrails) — Boundaries on canonical state and recovery.
- [Deferred](#deferred) — Promotion wiring and user-facing lifecycle work owned later.

## Why

`plan_tool/roadmap_revision_publish.py:preinvalidate_roadmap_seeds` refuses enrolled roadmaps, while `_is_completed_version_owned_generation` recognizes only the older, selector-only `review-seal-promotion` shape. Step 5 needs a safe seed-state member that can join the promotion generation, and recovery must recognize that complete three-part publication without treating a partial write or unrelated journal as complete.

## Input

- **Step 1 structural classification:** Consume only the structural transition fact established by step 1 when exposing the enrolled promotion seed-state member. Do not derive structural eligibility from user text, mutable ledger state, or a new diff during publication.
- **Publication journal:** Preserve `plan_tool/roadmap_source_identity.py:PendingGeneration` and `GenerationMember` as the durable record of old and new bytes. Recovery must continue to trust only the journaled member list.
- **Seed lifecycle state:** Use `plan_tool/roadmap_seed_state.py:invalidated_seed_state`, `render_seed_state`, and `seed_state_path` to create validated seed-state bytes without editing seed files.
- **Accepted version:** Use `plan_tool/roadmap_versions.py:AcceptedRoadmapHead`, `load_accepted_version`, and stored accepted content only to verify that a completed promotion journal belongs to the selected candidate version.

## Files (creates vs edits)

- **New files:** None.

- **Existing files (edits only):**
  - `plan_tool/roadmap_revision_publish.py` — Add the enrolled-promotion seed-state member builder and extend completed version-owned generation recognition for the complete promotion member set.
  - `tests/test_roadmap_revision_publish.py` — Add focused seed-member, completed-recovery, interrupted-recovery, and malformed-generation cases.

## Implementation

- **Foundational rule: promotion seed invalidation is a journal member, not a pre-write.** Add a narrow helper near `_publication_members` or the existing seed-state helpers that prepares the seed-state `GenerationMember` for an enrolled structural promotion. It must retain the prior sidecar bytes as its old value and render an `invalidated_seed_state` snapshot as its new value.

- **Keep invalidation limited to tracked lifecycle state.** The helper must mark every enrolled tracked seed invalidated and update draft paths from the promoted plans artifact when that artifact supplies them. It must not alter draft seed files, promoted seed files, roadmap artifacts, baselines, candidate records, or the accepted head.

- **Keep the existing writer boundary.** The helper must require the active `RoadmapWriterToken` through the promotion generation’s existing publication path. Do not make `preinvalidate_roadmap_seeds` accept enrolled roadmaps or write enrolled seed state before `publish_roadmap_generation` records its journal.

- **Support the complete promotion shape.** Extend `_is_completed_version_owned_generation` so `review-seal-promotion` recognizes the exact selector update plus the active-candidate release when applicable and the enrolled seed-state invalidation member. Match member paths, old bytes, new bytes, and ordering tightly enough that a completed journal cannot authorize extra records or omit a required effect.

- **Verify seed bytes against the selected promotion.** Completed-generation recognition must confirm that the seed-state member is a valid invalidation of its recorded prior state and, where applicable, carries draft paths from the promoted accepted plans artifact. A journal that merely contains parseable seed JSON is not sufficient.

- **Retain fail-closed recovery.** `recover_roadmap_publication` must delete an enrolled promotion journal only when all recorded members already equal their exact new bytes and the generation passes version-owned recognition. A missing selector swap, missing pointer release, missing seed update, unexpected member change, malformed seed state, or mismatched candidate version must leave the journal and filesystem unchanged and raise `RoadmapPublicationRecoveryError`.

- **Reuse the existing recovery model.** Keep root-enrollment and decision-settlement recovery behavior unchanged. Do not add a second transaction, accepted-head writer, checkpoint, or broad repair path; step 5 consumes the helper to assemble the promotion generation.

## Tests

### Tests for this step

- `test_enrolled_promotion_seed_member_invalidates_tracked_entries_without_touching_seed_files` — asserts the prepared member invalidates every tracked entry, preserves unrelated seed fields, refreshes applicable draft paths, and does not write draft or promoted seed files.
- `test_enrolled_promotion_seed_member_preserves_absent_seed_state_as_a_recorded_absence` — asserts an enrolled roadmap without a sidecar receives a journal member whose old bytes represent absence and whose new bytes are a valid empty lifecycle state.
- `test_completed_review_seal_promotion_with_pointer_release_and_seed_state_journal_is_dropped_without_touching_members` — asserts recovery removes only the completed journal after selector, release, and seed-state bytes are all present.
- `test_review_seal_promotion_recovery_refuses_missing_seed_invalidation` — asserts a promotion with an advanced selector but incomplete seed publication leaves every member and the journal unchanged.
- `test_review_seal_promotion_recovery_refuses_missing_active_pointer_release` — asserts a promotion with seed-state publication but no required active-pointer release remains unrecovered.
- `test_review_seal_promotion_recovery_refuses_seed_state_not_derived_from_promoted_plans_artifact` — asserts parseable but mismatched seed-state bytes cannot make a promotion journal recoverable.
- `test_review_seal_promotion_recovery_refuses_extra_or_reordered_members` — asserts completed-version recognition remains exact rather than accepting a broader journal shape.

Every listed test must be green before this step is complete.

## Acceptance criteria

- An enrolled structural promotion can receive one validated seed-state `GenerationMember` that invalidates tracked seeds without writing seed content files.
- The seed-state member records both old and new sidecar bytes and can join the existing `review-seal-promotion` generation.
- A completed promotion journal with its required selector, active-pointer, and seed-state members is removed by `recover_roadmap_publication` without changing any completed member.
- A partial, malformed, mismatched, reordered, or expanded promotion journal raises `RoadmapPublicationRecoveryError`, preserves the journal, and preserves member bytes.
- Existing root-enrollment, decision-settlement, and un-enrolled publication recovery tests remain green.
- `uv run pytest tests/test_roadmap_revision_publish.py -q` passes.

## References

- [Roadmap Structural Feedback Approval handoff — Read the reuse boundary for immutable candidates, promotion, recovery, and seed invalidation.](../../../../handoffs/2026-09-22-roadmap-feedback-revision-approval.md)
- [ROADMAP_FORMAT.md — Read immutable candidate authority, accepted-head selection, and roadmap seed-state rules.](../../../../ROADMAP_FORMAT.md)
- [ROADMAP_FEEDBACK_FORMAT.md — Read the candidate-review and promotion lifecycle.](../../../../ROADMAP_FEEDBACK_FORMAT.md)
- [DATA_CONTRACT.md — Read persisted publication and recovery contracts.](../../../../DATA_CONTRACT.md)
- [plan_tool/roadmap_revision_publish.py — Read writer guards, seed helpers, generation publication, and recovery recognition.](../../../../plan_tool/roadmap_revision_publish.py)
- [plan_tool/roadmap_version_promotion.py — Read the sole promotion caller that step 5 will update.](../../../../plan_tool/roadmap_version_promotion.py)
- [plan_tool/roadmap_seed_state.py — Read seed-state validation and invalidation rendering.](../../../../plan_tool/roadmap_seed_state.py)
- [plan_tool/roadmap_versions.py — Read accepted-head and immutable version storage contracts.](../../../../plan_tool/roadmap_versions.py)

## Applicable guardrails

- **The plan’s “## Plan intent”, approval-only publication boundary** — This step may prepare publication data and validate recovery, but it must not advance `AcceptedRoadmapHead` or make approval automatic.
- **The plan’s “## Step intent”, atomic promotion effects** — Keep accepted-head, active-pointer, and seed-state effects in one recorded generation so recovery never treats a partial promotion as complete.
- **The plan’s “## Scope guardrails”, canonical selector boundary** — Reuse the existing promotion writer and publication journal; do not create another accepted-head writer, version schema, or transaction system.
- **The plan’s “## Scope guardrails”, failure preservation boundary** — Refused, stale, malformed, or interrupted promotion publications must not rewrite canonical state or seeds.
- **The plan’s “## Out of scope”, lifecycle-system limits** — Do not add user route selection, automatic promotion, new recovery infrastructure, or broader structural authority.

## Deferred

- **Promotion assembly and final freshness checks** — Step 5 updates `plan_tool/roadmap_version_promotion.py:promote_review_seal` to consume this step’s seed-state member with the exact approval seal.
- **CLI decision and promotion wiring** — Step 6 owns the user-facing command surface and outcome reporting.
- **Lifecycle documentation** — Step 7 owns updates to operator and persisted-contract documentation.
