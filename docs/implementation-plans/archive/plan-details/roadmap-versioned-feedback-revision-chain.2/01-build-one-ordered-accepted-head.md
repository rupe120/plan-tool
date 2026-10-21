> **Withdrawn 2026-09-22** — Superseded 2026-09-22: feedback moves to a roadmap-scoped mutable ledger; artifact versions retain no embedded mutable feedback.
> Preserved here for history; do not edit.

# Step 1 — Build one ordered accepted-head feedback batch and exact batch identity

<!-- plan-tool:detail-format-version: 1 -->

## Summary

Replace single-selector context binding with one ordered batch of every `open` feedback row from an immutable accepted predecessor. Update `plan_tool/roadmap_candidate_context.py` to carry the batch through the capsule, receipt, payload, and identity calculation. Extend `tests/test_roadmap_candidate_context.py` to prove stable ordering, complete membership, and identity changes when the batch’s source changes. On green, later steps can use one reproducible context and identity for an accepted head’s active feedback inventory.

## Table of Contents

- [Summary](#summary) — Reviewer overview of the batch context change.
- [Table of Contents](#table-of-contents) — Links to this detail’s sections.
- [Why](#why) — Why selector-based context cannot support an accepted-head revision.
- [Input](#input) — Immutable predecessor and feedback-lifecycle contracts this step reads.
- [Files (creates vs edits)](#files-creates-vs-edits) — The two scoped file changes.
- [Implementation](#implementation) — Batch ordering, identity, and compatibility rules.
- [Tests](#tests) — Focused test coverage for the new batch contract.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Contracts that define the lifecycle boundary.
- [Applicable guardrails](#applicable-guardrails) — Scope and authority limits for this step.
- [Deferred](#deferred) — Later lifecycle work that consumes this batch contract.

## Why

`plan_tool/roadmap_candidate_context.py:build_candidate_context()` currently binds one parsed `ARTIFACT:FEEDBACK_ID` selector through `CandidateContextFeedback`, so it cannot represent the accepted head’s complete active feedback set. A revision needs one stable, immutable view of every currently `open` request so retries and downstream candidate, review, and promotion checks can prove they acted on the same inputs rather than on a live or partially selected inventory.

## Input

- **Accepted predecessor:** Read only the supplied `ResolvedRoadmapVersion` through `_verify_predecessor`; its immutable artifact bytes remain the only source for batch membership and request facts.
- **Feedback lifecycle:** Treat `FeedbackState.OPEN` as eligible guidance. Keep `awaiting-review` and `deferred` rows outside the active batch; their preservation belongs to successor construction in step 2.
- **Existing context contract:** Replace the one-row binding represented by `CandidateContextFeedback`, `CandidateContextCapsule`, and `CandidateContextReceipt` without weakening their frozen, closed-record validation or their payload-integrity checks.
- **Ordering source:** Use `plan_tool/roadmap.py:STAGES` for artifact order and each parsed artifact’s feedback-row sequence for within-artifact order. Do not sort by request text, digest, or identifier.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `plan_tool/roadmap_candidate_context.py` — Replace selector-based active-feedback selection with an ordered batch value, render it into the context payload and receipt, and derive an exact batch identity.
  - `tests/test_roadmap_candidate_context.py` — Update single-feedback fixtures and assertions, then add batch membership, ordering, empty-batch, and identity-drift coverage.

## Implementation

- **Build one ordered batch from immutable artifacts.** Adapt `build_candidate_context()` and the selection path around `_select_feedback` so context construction derives every eligible `FeedbackState.OPEN` row from the verified predecessor. Preserve artifact order from `STAGES` and authored row order within each artifact.

- **Make membership exact and inspectable.** Replace the singular `CandidateContextFeedback` binding with a frozen, closed batch representation that records each eligible row’s artifact key, feedback id, target, request, state, and source digest. Reuse `_feedback_facts` as a starting point if useful, but make the batch’s public shape clear enough for later candidate, review, and promotion code to compare the full inventory.

- **Bind batch identity to the complete input.** Include the ordered batch facts in `_render_payload`, `CandidateContextCapsule`, and `CandidateContextReceipt`, and compute a deterministic batch identity from the accepted predecessor plus that ordered inventory. A changed request, target, state, artifact placement, membership, or order must produce a different identity; rebuilding from unchanged immutable bytes must produce the same identity.

- **Keep the predecessor as the authority.** `_verify_predecessor` and the existing digest checks remain the boundary before batch construction. The batch builder must not inspect live top-level roadmap artifacts or accepted-head files, and it must not move an accepted head, change feedback state, or write candidate state.

- **Represent an empty batch deterministically.** Return an intact context result for an accepted predecessor with no eligible `open` rows, with an empty ordered batch and stable identity. Do not add no-work, model-call, admission, or publication behavior here; step 3 owns the lifecycle result for that case.

- **Retire selector policy from this context surface.** `parse_feedback_selector`, `matching_feedback_rows`, and the selector-specific refusal outcomes support the current one-row contract but must not remain on the normal batch-building path. Do not add a compatibility selector branch that can silently omit eligible rows.

- **Preserve context safety properties.** Keep the module-owned context ceiling, canonical wire values, immutable records, closure behavior, and expansion integrity checks. Expansion, if retained for the batch context, must reproduce the same complete initial batch before accepting an inventory expansion; it must not substitute a different active-feedback inventory.

- **Leave consumer migration to its owning steps.** `plan_tool/roadmap_candidate.py` currently validates and serializes `selected_feedback`, while `plan_tool/roadmap_candidate_run.py`, `plan_tool/roadmap_candidate_review.py`, and `plan_tool/roadmap_version_promotion.py` consume that singular binding. Do not edit those files in this step; steps 2, 3, 5, and 6 migrate their respective candidate, admission, review, and promotion contracts to the batch value.

## Tests

### Tests for this step

- `test_context_uses_only_the_selected_accepted_predecessor` — Update the assertion to prove every batch member comes from the supplied immutable predecessor and no other version’s bytes enter the payload.
- `test_context_collects_every_open_feedback_in_stage_and_authored_row_order` — Assert that open rows across multiple artifacts form one ordered batch using `STAGES` order and source row order.
- `test_context_excludes_awaiting_review_and_deferred_feedback_from_active_batch` — Assert that non-open rows do not become batch members, including an awaiting-review row with a proposed response.
- `test_context_empty_open_feedback_batch_is_repeatable` — Assert that no eligible rows yields an intact empty batch with repeatable payload and batch identity.
- `test_context_batch_identity_changes_for_membership_or_source_drift` — Assert that adding, removing, reordering, or changing an eligible row’s request, target, or state changes the batch identity.
- `test_context_receipt_payload_and_identity_are_repeatable` — Update the existing repeatability check to cover the ordered batch and its exact identity.
- `test_context_requires_exactly_one_open_selected_feedback_row` — Replace selector-specific expectations with batch eligibility and predecessor-validation cases, retaining refusal coverage only for failures the batch builder still owns.
- `test_expansion_requires_the_same_initial_feedback_batch` — Assert that expansion refuses a capsule whose batch no longer reproduces from the same immutable predecessor.

Every listed test must be green before this step is complete.

## Acceptance criteria

- `build_candidate_context()` derives each active-feedback batch only from the supplied verified `ResolvedRoadmapVersion`.
- Every `open` feedback row in the predecessor appears exactly once in the batch, in `STAGES` order and authored row order.
- `awaiting-review` and `deferred` feedback rows do not appear in the active batch.
- An unchanged predecessor rebuilds the same payload, ordered batch, receipt, and batch identity.
- Any change to the accepted predecessor’s eligible feedback membership, source facts, or order changes the batch identity.
- A predecessor with no open feedback returns a deterministic empty batch without writing or changing state.
- `uv run pytest tests/test_roadmap_candidate_context.py -q` passes.

## References

- [ROADMAP_FORMAT.md](../../../../ROADMAP_FORMAT.md) — Read the feedback lifecycle and immutable candidate-authority contracts.
- [DATA_CONTRACT.md](../../../../DATA_CONTRACT.md) — Read persisted candidate and review bindings that later steps migrate to batch identity.
- [docs/how-to/roadmap.md](../../../../docs/how-to/roadmap.md) — Read the current operator workflow and selector-based behavior being replaced.
- [plan_tool/roadmap_versions.py](../../../../plan_tool/roadmap_versions.py) — Read `ResolvedRoadmapVersion`, `AcceptedRoadmapHead`, and accepted-version loading boundaries.
- [plan_tool/roadmap_candidate_context.py](../../../../plan_tool/roadmap_candidate_context.py) — Read the current capsule, receipt, payload, and context-integrity implementation.

## Applicable guardrails

- **The plan’s “## Scope guardrails”, accepted-head authority:** This step must treat the immutable accepted predecessor as input only and must not introduce a canonical-content selector or accepted-head writer.
- **The plan’s “## Scope guardrails”, exact batch binding:** This step must make predecessor and batch identity exact enough for later stages to refuse drift before any accepted-head movement.
- **The plan’s “## Scope guardrails”, no parallel lifecycle authority:** This step must extend the existing context owner only; it must not create candidate, review, seal, journal, checkpoint, recovery, or promotion ownership.
- **The plan’s “## Out of scope”, feedback lifecycle changes:** This step must classify only existing `open` rows as batch guidance and must not add states or alter reviewer-controlled transitions.
- **The plan’s “## Out of scope”, operation semantics:** This step must not change stage operation authority, roadmap gates, structural proposal formats, or review protocol.

## Deferred

- Batch-aware successor materialization — Step 2 migrates candidate operations and full-successor validation from a single selected row to the batch.
- Accepted-head generation admission and no-work handling — Step 3 owns stored admission, retry, model-call, and inert-candidate outcomes.
- Batch-bound reviewer and promotion checks — Steps 5 and 6 own review-seal and accepted-head verification against the exact batch.
