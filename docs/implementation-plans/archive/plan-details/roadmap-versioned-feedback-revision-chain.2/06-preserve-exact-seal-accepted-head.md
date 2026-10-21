> **Withdrawn 2026-09-22** — Superseded 2026-09-22: feedback moves to a roadmap-scoped mutable ledger; artifact versions retain no embedded mutable feedback.
> Preserved here for history; do not edit.

# Step 6 — Preserve exact-seal accepted-head replacement and reject stale or changed batches before promotion

<!-- plan-tool:detail-format-version: 1 -->

## Summary

Update `plan_tool/roadmap_version_promotion.py` so promotion accepts only the exact sealed successor produced for the current accepted predecessor and its admitted feedback batch. Keep `promote_review_seal()` as a selector-only operation, using the existing journal-backed `publish_roadmap_generation()` boundary for the final accepted-head check. Update `tests/test_roadmap_version_promotion.py` to cover batch binding failures alongside current stale-head and changed-selector cases. On green, a valid seal moves only `AcceptedRoadmapHead`; any stale predecessor, altered batch evidence, or changed selector leaves the current head unchanged.

## Table of Contents

- [Summary](#summary) — Reviewer overview of the promotion boundary.
- [Table of Contents](#table-of-contents) — Links to this detail’s sections.
- [Why](#why) — Why promotion must recheck the sealed batch and accepted head.
- [Input](#input) — Immutable candidate, review, and publication contracts this step reads.
- [Files (creates vs edits)](#files-creates-vs-edits) — The scoped promotion and test changes.
- [Implementation](#implementation) — Exact-seal validation and final selector replacement rules.
- [Tests](#tests) — Focused cases for stale and changed promotion inputs.
- [Acceptance criteria](#acceptance-criteria) — Observable conditions for safe promotion.
- [References](#references) — Relevant immutable-version and publication contracts.
- [Applicable guardrails](#applicable-guardrails) — Boundaries that keep promotion narrow.
- [Deferred](#deferred) — Related work outside this focused selector change.

## Why

`plan_tool/roadmap_version_promotion.py:promote_review_seal()` already checks a sealed replacement lineage and rechecks the accepted-head selector before replacement, but its current evidence comparisons bind the singular `feedback` value carried by the existing candidate and review records. After steps 3 and 5 make admission and review batch-scoped, promotion must reject any seal whose stored batch facts no longer match the exact admitted candidate and current predecessor. Otherwise a valid-looking seal could move the canonical selector for a different active-feedback inventory.

## Input

- **Step 3 admission:** Read the accepted-head-generation candidate stored through `plan_tool/roadmap_candidate_run.py:load_candidate_admission()` and `load_stored_candidate_proposal()`. Its predecessor and batch identity are immutable promotion inputs.

- **Step 5 review lineage:** Read the exact review seal, question inventory, answer, replacement binding, replacement state, and stored replacement through the loaders used by `plan_tool/roadmap_version_promotion.py:_load_complete_sealed_candidate()`. The landed batch fields and identities from step 5 win over names proposed in earlier details.

- **Accepted head:** Continue to load `AcceptedRoadmapHead` and its version through `plan_tool/roadmap_versions.py:load_accepted_head()` and `load_accepted_version()`. The selector bytes captured by `_load_current_accepted_version()` are the expected old value for this promotion attempt.

- **Publication boundary:** Reuse `plan_tool/roadmap_revision_publish.py:publish_roadmap_generation()` and its `before_replace` hook. This step does not add another journal, writer guard, or selector-writing path.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `plan_tool/roadmap_version_promotion.py` — Adapt exact review-lineage and candidate-evidence checks from singular feedback to the batch contract from steps 3 and 5, while retaining final accepted-head replacement protection.
  - `tests/test_roadmap_version_promotion.py` — Update fixtures for batch-bound records and add refusal and preservation coverage for altered batch and stale selector inputs.

## Implementation

- **Keep promotion selector-only.** `promote_review_seal()` must publish one `GenerationMember` for `accepted_head_path()` and must not rewrite stored versions, candidate records, review records, or live roadmap artifacts. The existing `PendingGeneration(kind="review-seal-promotion")` shape remains the right narrow publication unit.

- **Require one exact batch-bound lineage.** Adapt `_load_complete_sealed_candidate()`, `_require_replacement_binding()`, `_require_final_capsule_binding()`, and `_require_seal_bindings()` to compare the batch identity and member facts that steps 3 and 5 persist. Every loaded record must describe the same initial candidate, predecessor, review inventory, answer, replacement candidate, capsule, receipt, and feedback batch.

- **Do not rediscover live feedback during promotion.** Promotion must validate stored immutable evidence only. Rebuilding eligibility from roadmap artifacts or selecting a new feedback row at promotion time would permit a changed batch to pass under a stale seal.

- **Retain reproducible candidate validation.** Keep `_recheck_stored_candidate()` responsible for validating stored bytes, predecessor diff, content identity, complete stage gate evidence, and the candidate’s admitted feedback binding. Update its call into `plan_tool/roadmap_candidate.py:_content_identity()` to use the landed batch-aware interface from step 2 rather than preserving a singular-feedback compatibility path.

- **Preserve two accepted-head checks.** `_require_candidate_predecessor_is_current()` must reject a candidate whose predecessor differs from the accepted version loaded for this attempt. `final_recheck()` must run through `publish_roadmap_generation(..., before_replace=...)` and require both the same predecessor version and the same captured selector bytes immediately before replacement.

- **Treat changed selector bytes as stale even when they parse.** The final check must compare the rendered current `AcceptedRoadmapHead` with the bytes captured by `_load_current_accepted_version()`. Version equality alone is insufficient because exact replacement requires the selector state read during validation to remain unchanged.

- **Reuse shared publication ownership unchanged.** `plan_tool/roadmap_revision_publish.py:publish_roadmap_generation()` already supplies journal recovery and invokes `before_replace` at the replacement boundary. `plan_tool/cli/roadmap_cmd.py:_cmd_roadmap_promote_review_seal()` already holds `roadmap_writer_guard()` and maps promotion errors to command results; neither file needs an edit for this batch-binding change.

## Tests

### Tests for this step

- `test_promotion_replaces_only_the_accepted_head_selector_for_the_exact_sealed_batch_candidate` — asserts a valid batch-bound seal promotes its exact replacement and leaves all other stored version and review files unchanged.

- `test_promotion_refuses_review_lineage_with_a_changed_feedback_batch` — alters one persisted batch identity or member fact and asserts `RoadmapVersionPromotionError` with the original accepted head preserved.

- `test_promotion_refuses_seal_or_replacement_evidence_bound_to_a_different_batch` — proves matching candidate ids alone cannot promote when the seal, inventory, replacement evidence, capsule, or receipt disagree on the admitted batch.

- `test_promotion_refuses_candidate_with_a_stale_accepted_predecessor` — moves the selector to another valid version before promotion and asserts `StaleRoadmapVersionPromotionError` without restoring or overwriting that newer head.

- `test_promotion_rechecks_exact_selector_bytes_inside_the_journal_window` — changes the accepted-head selector between validation and `before_replace`, then asserts promotion refuses and creates no pending-generation residue.

- `test_promotion_rechecks_batch_aware_content_identity_and_complete_gates` — tampers with stored candidate bytes, batch-aware identity evidence, or complete gate evidence and asserts no selector movement.

- `test_promotion_writes_only_the_accepted_head_member` — captures the published generation and asserts it contains only the accepted-head replacement member.

- **Green-before-done gate:** every changed and added case in `tests/test_roadmap_version_promotion.py` must pass before this step is complete.

## Acceptance criteria

- `promote_review_seal()` promotes only the replacement version named by a complete, internally consistent, batch-bound review seal.

- Promotion rejects a stale predecessor, changed batch identity, changed batch member facts, or changed response binding before the accepted-head selector changes.

- Promotion rechecks the exact accepted-head selector bytes immediately before journaled replacement and raises `StaleRoadmapVersionPromotionError` when they differ.

- A rejected promotion leaves the accepted head at the state present when the rejection occurs and leaves no pending publication journal.

- A successful promotion writes only the accepted-head selector and preserves immutable candidate, review, and stored-version files.

- `tests/test_roadmap_version_promotion.py` passes with the batch-aware promotion coverage.

## References

- [ROADMAP_FORMAT.md — Read the immutable version, candidate, review-seal, and accepted-head lifecycle contract.](../../../ROADMAP_FORMAT.md)

- [DATA_CONTRACT.md — Read the persisted candidate, review, and publication record rules.](../../../DATA_CONTRACT.md)

- [Roadmap promotion module — Follow the exact sealed-candidate validation and selector-only publication path.](../../../plan_tool/roadmap_version_promotion.py)

- [Roadmap publication module — Reuse the writer guard, pending-generation journal, and final replacement hook.](../../../plan_tool/roadmap_revision_publish.py)

- [Roadmap versions module — Follow `AcceptedRoadmapHead` parsing, rendering, and immutable-version loading rules.](../../../plan_tool/roadmap_versions.py)

## Applicable guardrails

- **The plan’s “## Plan intent” — canonical selection:** This step may make the reviewed successor canonical only by updating `AcceptedRoadmapHead` after its exact seal and predecessor checks pass.

- **The plan’s “## Scope guardrails” — exact candidate identity:** This step must refuse batch, predecessor, source, and response-binding drift before promotion, without treating stored candidate evidence as canonical on its own.

- **The plan’s “## Scope guardrails” — promotion boundary:** This step must not rewrite live top-level roadmap artifacts or create a new feedback state while promoting.

- **The plan’s “## Scope guardrails” — existing authority owners:** This step must reuse the current version, review, writer-guard, and journal owners instead of adding another promotion or recovery mechanism.

- **The plan’s “## Out of scope” — no new review protocol:** This step must not add approval states, candidate branches, operation semantics, or automatic promotion behavior.

## Deferred

- CLI promotion flow changes — `plan_tool/cli/roadmap_cmd.py:_cmd_roadmap_promote_review_seal()` already supplies the writer guard and error mapping; changing command behavior is outside this step.

- Publication-journal consolidation — `plan_tool/roadmap_revision_publish.py:publish_roadmap_generation()` remains the shared owner for promotion and other roadmap writers; refactoring that shared authority requires separate work.
