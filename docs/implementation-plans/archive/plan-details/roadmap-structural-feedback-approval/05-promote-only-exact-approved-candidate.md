> **Auto-archived**: this plan was swept on 2026-11-05 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 5 — Promote only an exact approved structural candidate while atomically advancing the accepted head, releasing the active pointer, and invalidating enrolled seeds

<!-- plan-tool:detail-format-version: 1 -->

## Summary

Update `plan_tool/roadmap_version_promotion.py` so promotion accepts only the exact structural candidate named by step 3’s direct approval seal, whether it is an initial proposal or an edited replacement. Build one publication generation containing the accepted-head overwrite, active-pointer release, and step 4’s enrolled seed-state invalidation member. Keep `AcceptedRoadmapHead` as the sole canonical selector and retain the final stale-state recheck. On green, focused tests prove that approval advances exactly the displayed, sealed candidate and that all promotion effects commit together or none do.

## Table of Contents

- [Summary](#summary) — Reviewer overview of the promotion boundary and result.
- [Table of Contents](#table-of-contents) — Quick links to this detail file.
- [Why](#why) — Why sealing alone is not enough for structural promotion.
- [Input](#input) — Persisted candidate, approval, pointer, and seed-state contracts this step consumes.
- [Files (creates vs edits)](#files-creates-vs-edits) — The two existing files changed by this step.
- [Implementation](#implementation) — Exact approval binding, atomic generation, and freshness rules.
- [Tests](#tests) — Focused promotion, stale-state, and publication-membership coverage.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Contracts governing candidate approval and immutable publication.
- [Applicable guardrails](#applicable-guardrails) — Boundaries on accepted-head authority and lifecycle writes.
- [Deferred](#deferred) — Work intentionally outside this promotion step.

## Why

`plan_tool/roadmap_version_promotion.py:promote_review_seal` currently loads only answered replacement seals. Structural approval must also promote a directly sealed initial candidate without creating a question or replacement first. The same accepted-root, stored-byte, gate, and publication checks must govern both structural cases.

## Input

- **Step 3 approval outcome:** Consume the direct structural approval form of `CandidateReviewSeal`, which names the exact active candidate. Preserve the existing answered-replacement seal branch for its current callers.
- **Stored candidate bytes:** Retain `plan_tool/roadmap_version_promotion.py:_load_complete_sealed_candidate`, `_require_seal_bindings`, and `_recheck_stored_candidate` as the exact-byte and complete-gate boundary. Promotion must select the stored candidate version; it must not regenerate a candidate, invoke a model, or rebuild candidate content from the live ledger.
- **Accepted-head and active-pointer state:** Use `plan_tool/roadmap_versions.py:AcceptedRoadmapHead`, `load_accepted_head`, and `render_accepted_head` for the selector binding. Reuse `plan_tool/roadmap_candidate_run.py:build_active_candidate_pointer_release_generation` when the admitted batch candidate owns an active pointer.
- **Step 4 seed member:** Consume step 4’s enrolled-promotion seed-state member as already-rendered journal evidence. Promotion must not pre-write seed state or edit draft or promoted seed files directly.

## Files (creates vs edits)

- **New files:** None.

- **Existing files (edits only):**
  - `plan_tool/roadmap_version_promotion.py` — Require the explicit structural approval binding, compose the complete promotion generation, and retain final currentness checks.
  - `tests/test_roadmap_version_promotion.py` — Update selector-only expectations and add approval, atomic-generation, seed-state, and stale-state coverage.

## Implementation

- **Promote only the directly approved identity.** Extend `promote_review_seal` to load the candidate named by a direct structural approval seal, including an initial candidate with no replacement evidence. Match the seal to the current active pointer, that candidate's persisted structural route and validated operations, stored content identity, accepted root, and validated candidate bytes. Keep the answered-replacement loader and legacy seal interpretation unchanged. Refuse a missing, malformed, stale, rejected, edited, or differently bound approval before creating a publication generation.

- **Keep stored bytes authoritative.** Apply the existing replay and gate checks to the sealed active candidate, including an initial proposal. The promoted `AcceptedRoadmapHead.version_id` must name that already-stored version. Do not add a model call, candidate materialization call, live-ledger eligibility check, or top-level roadmap-artifact rewrite to promotion.

- **Publish all lifecycle effects as one generation.** Build the `PendingGeneration` in `plan_tool/roadmap_version_promotion.py:promote_review_seal` from:
  - the accepted-head member rendered from the approved candidate version;
  - `build_active_candidate_pointer_release_generation(...).members` when the batch admission has an active pointer; and
  - step 4’s seed-state member for the enrolled structural promotion.

  Retain the existing `review-seal-promotion` generation kind unless the landed step 4 recovery contract requires a compatible shared identifier. The journal must record each member’s old and new bytes so `plan_tool/roadmap_revision_publish.py:publish_roadmap_generation` and `recover_roadmap_publication` can recognize only a complete publication.

- **Preserve final freshness checks.** Keep `final_recheck` as the last check passed to `publish_roadmap_generation`. It must still confirm that the accepted-head bytes name the predecessor observed during validation and, when applicable, that `load_candidate_admission` still equals the admitted active-pointer record. Add the approval binding to this final check if it can change after initial validation; no member may be replaced after any required currentness check fails.

- **Invalidate lifecycle state without rewriting seeds.** Include only the seed-state sidecar member supplied by step 4. The promotion path must mark enrolled tracked seeds invalidated through that member while leaving seed bodies, immutable candidate records, review records, and unselected ledger rows unchanged.

- **Keep selector-era behavior bounded.** Preserve the existing selector-only release shape where no active batch pointer exists, while applying the approved structural route’s required seed member. Do not create terminal-resolution history during approval promotion; `plan_tool/roadmap_candidate_run.py:build_terminal_resolution_generation` remains the rejection and discard path.

## Tests

- `test_promotion_requires_the_exact_structural_approval_for_the_active_candidate` — promotion refuses when approval is absent, rejected, edited, malformed, or names a different candidate, and the accepted head stays unchanged.
- `test_promotion_promotes_the_directly_approved_initial_candidate_without_a_replacement` — a valid direct approval advances `AcceptedRoadmapHead` to the displayed initial version without question or replacement records.
- `test_promotion_promotes_only_the_exact_approved_edited_candidate_bytes` — a valid approval of an edited replacement advances to that replacement without regenerating content or reading the live ledger.
- `test_promotion_publishes_selector_pointer_release_and_seed_invalidation_in_one_generation` — an enrolled batch promotion journals the accepted-head member, active-pointer release, and seed-state member together.
- `test_promotion_invalidates_enrolled_seed_state_without_rewriting_seed_files` — promotion changes only the tracked seed lifecycle state and leaves seed bodies unchanged.
- `test_promotion_refuses_stale_head_pointer_or_approval_before_replacing_any_member` — a changed accepted head, active pointer, or approval binding during the final journal window leaves no promotion member replaced and clears the refused journal.
- `test_promotion_preserves_immutable_candidate_review_and_unselected_ledger_bytes` — promotion leaves immutable history and later live-ledger edits unchanged.
- `test_promotion_generation_contains_no_terminal_resolution_member` — approval releases an active pointer without creating rejection or discard history.

Every listed test must be green before this step is complete.

## Acceptance criteria

- `plan_tool/roadmap_version_promotion.py:promote_review_seal` returns an `AcceptedRoadmapHead` naming only the exact stored candidate authorized by the matching structural approval.
- Missing, stale, rejected, edited, malformed, or differently bound approval refuses without changing the accepted-head selector, active pointer, seed state, or canonical roadmap artifacts.
- A successful enrolled structural promotion publishes the accepted-head overwrite, active-pointer release when present, and seed invalidation in one `PendingGeneration`.
- The final `before_replace` check rejects a changed accepted head or active pointer before any recorded member is replaced.
- Promotion does not invoke a model, materialize a new candidate, rewrite top-level roadmap artifacts, or rewrite live feedback ledger bytes.
- `tests/test_roadmap_version_promotion.py` is green.

## References

- [ROADMAP_FORMAT.md — Read the structural feedback and accepted-artifact authority contracts.](../../../../../ROADMAP_FORMAT.md)
- [DATA_CONTRACT.md — Read persisted candidate, review, accepted-head, and publication-record contracts.](../../../../../DATA_CONTRACT.md)
- [ROADMAP_FEEDBACK_FORMAT.md — Read mutable ledger ownership and the boundary between feedback progress and canonical promotion.](../../../../../ROADMAP_FEEDBACK_FORMAT.md)
- [plan_tool/roadmap_version_promotion.py — Read the existing exact-seal, stored-byte, and final-currentness checks.](../../../../../plan_tool/roadmap_version_promotion.py)
- [plan_tool/roadmap_candidate_review.py — Read the review seal and structural decision lineage.](../../../../../plan_tool/roadmap_candidate_review.py)
- [plan_tool/roadmap_revision_publish.py — Read journaled generation publication and recovery rules.](../../../../../plan_tool/roadmap_revision_publish.py)

## Applicable guardrails

- **The plan’s “## Plan intent”, approval-only acceptance boundary:** This step may advance `AcceptedRoadmapHead` only after the exact structural approval and may not treat sealing, editing, rejection, staleness, or failed validation as acceptance.
- **The plan’s “## Scope guardrails”, canonical selector boundary:** Keep `AcceptedRoadmapHead` as the only accepted-roadmap selector and keep promotion as its only writer.
- **The plan’s “## Scope guardrails”, immutable candidate boundary:** Reuse candidate, review, publication, pointer, and seed-invalidation contracts rather than adding a second store, selector, or transaction system.
- **The plan’s “## Scope guardrails”, failed-proposal boundary:** A failed or interrupted promotion may retain its immutable history but must not rewrite canonical artifacts, seed bodies, or unselected feedback.
- **The plan’s “## Out of scope”, lifecycle and authority limits:** Do not add automatic promotion, user route selection, broader feedback grouping, or structural operations beyond the already validated candidate route.

## Deferred

- CLI presentation of structural approval and promotion outcomes — step 3 and later user-facing workflow work own any command-surface changes.
- Publication-recovery recognition for the complete seed-aware generation — step 4 owns the recovery contract and its focused tests.
- Generalizing publication generations or candidate lifecycle storage — the plan’s scope fence keeps this step on the existing promotion path.
