> **Withdrawn 2026-09-22** — Superseded 2026-09-22: feedback moves to a roadmap-scoped mutable ledger; artifact versions retain no embedded mutable feedback.
> Preserved here for history; do not edit.

# Step 2 — Build one complete successor for the batch while preserving existing typed row removals and untouched feedback

<!-- plan-tool:detail-format-version: 1 -->

## Summary

Update `plan_tool/roadmap_candidate.py` so `materialize_candidate()` builds one complete candidate successor from the ordered feedback batch supplied by step 1. Keep the existing closed typed-row operations, including `CandidateRemoveRow` and its coupled plan-ordering behavior, while changing feedback handling from one selected row to the admitted batch. Preserve every predecessor `awaiting-review` and `deferred` feedback row exactly, and move only admitted `open` rows through the existing response lifecycle. Extend `tests/test_roadmap_candidate.py` to prove complete successor assembly, batch authorization, removal preservation, and unchanged inactive feedback.

## Table of Contents

- [Summary](#summary) — Reviewer overview of the successor-materialization change.
- [Table of Contents](#table-of-contents) — Links to this detail’s sections.
- [Why](#why) — Why a single-feedback candidate cannot represent one accepted-head revision.
- [Input](#input) — Immutable predecessor and batch contracts this step consumes.
- [Files (creates vs edits)](#files-creates-vs-edits) — The two scoped file edits.
- [Implementation](#implementation) — Batch-aware materialization and preservation rules.
- [Tests](#tests) — Focused successor-materialization coverage.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Lifecycle and immutable-version contracts.
- [Applicable guardrails](#applicable-guardrails) — Authority and scope limits for this step.
- [Deferred](#deferred) — Later lifecycle work outside candidate assembly.

## Why

`plan_tool/roadmap_candidate.py:materialize_candidate()` currently binds each candidate outcome, operation, review requirement, and content identity to `CandidateContextFeedback`, so it can only assemble a successor around one selected request. That leaves the accepted head’s other active feedback outside the same immutable revision and risks treating existing reviewer-owned responses as model-editable content. This step makes candidate assembly honor step 1’s complete, reproducible batch while retaining the established typed operation and full-roadmap gate boundaries.

## Input

- **Step 1 batch contract:** Consume the ordered feedback inventory and exact capsule/receipt binding produced by step 1. The batch’s member order and source identity are input facts; candidate materialization must not rebuild eligibility from mutable artifacts or reorder it.

- **Immutable predecessor:** Continue to read and parse only the supplied `ResolvedRoadmapVersion` in `plan_tool/roadmap_candidate.py:_verify_bindings()`. Its artifact bytes remain the source for every carried artifact, typed row, and feedback row.

- **Feedback lifecycle:** Follow `FeedbackState` and the predecessor comparison rule enforced by `plan_tool/roadmap_gates.py:check_feedback_integrity()`. An admitted `open` row can receive its proposed response and enter `awaiting-review`; carried `awaiting-review` and `deferred` rows are reviewer-owned and stay unchanged.

- **Existing typed operations:** Retain `CandidateAddRow`, `CandidateReplaceRow`, `CandidateRemoveRow`, `_validate_operation_authority()`, and `_apply_operation()` as the closed row-edit surface. This step changes batch binding and successor feedback assembly, not the meaning of individual row operations.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `plan_tool/roadmap_candidate.py` — Make candidate materialization, authorization, identities, and candidate/review records bind the batch from step 1; assemble successor feedback state while retaining typed row-operation behavior.
  - `tests/test_roadmap_candidate.py` — Update single-feedback fixtures and assertions, then add complete-batch successor and feedback-preservation cases.

## Implementation

- **Build one full successor from the admitted batch.** Adapt `materialize_candidate()` and its result records so the candidate, review-required result, review requirement, and content identity bind the batch supplied by the issued capsule and receipt rather than a singular selected feedback record. The candidate must still contain all stage artifacts in `STAGES` order and remain an in-memory result with no accepted-head side effect.

- **Keep one closed authority boundary.** Update `_verify_bindings()` to reproduce the batch-aware capsule from the immutable predecessor and reject substitutions, stale members, changed source facts, or receipt mismatches before artifact assembly. Do not add a second context compiler or derive a replacement batch from live roadmap files.

- **Authorize every operation against the batch.** Adapt `_validate_operation_authority()` so an operation’s `feedback_id` must name a member of the admitted batch, rather than require one fixed id. Reject an id outside the batch, and retain the existing checks for full-member authority, inherited decisions, typed row shape, and plan ordering entries.

- **Preserve typed removals unchanged.** Keep `CandidateRemoveRow` and `_apply_operation()` as the owner of row removal. A plan removal must still carry and remove its exact matching predecessor `OrderingEntry`; non-plan removals must not acquire ordering behavior. Do not replace typed removals with a generic artifact rewrite or a feedback-specific removal path.

- **Assemble feedback separately from design-row edits.** Apply the existing typed operations to the predecessor artifacts, then produce successor feedback rows from the predecessor and the batch response bindings. Every admitted `open` row must retain its id, target, and request while entering `awaiting-review` with its response. Every predecessor `awaiting-review` and `deferred` row must remain equal to its predecessor value, including any `proposed_response`.

- **Require complete, unambiguous batch coverage.** The materialization input must bind a response for each admitted batch member exactly once. Reject missing, duplicate, or out-of-batch response bindings rather than silently carrying an admitted `open` row forward or accepting a model-created feedback row. One way is to normalize the response bindings before applying row operations, so the rest of assembly consumes one checked batch-to-response mapping.

- **Keep downstream evidence reproducible.** Update `_content_identity()`, `_build_review_requirement()`, and `_review_impact_identity()` wherever they currently encode `selected_feedback`, so their identities bind the exact batch and assembled successor. Preserve operation normalization in `_prepare_operations()` so equivalent typed operation ordering produces the same candidate evidence.

- **Reuse existing full-roadmap checks.** Continue to pass the complete assembled artifacts through `check_complete_roadmap_gates()`. Do not change `plan_tool/roadmap_gates.py` or relax its predecessor-based `check_feedback_integrity()` rule; this step supplies a successor that satisfies it.

## Tests

### Tests for this step

- `test_candidate_materializes_one_successor_for_every_admitted_open_feedback_row` — asserts every batch member appears once in the successor as `awaiting-review` with its bound response.

- `test_candidate_preserves_awaiting_review_feedback_verbatim` — asserts an existing awaiting-review row retains its state and exact `proposed_response`.

- `test_candidate_preserves_deferred_feedback_verbatim` — asserts a deferred row remains unchanged even when the same artifact contains admitted open feedback.

- `test_candidate_refuses_missing_batch_feedback_response` — asserts a successor cannot leave an admitted open row unanswered.

- `test_candidate_refuses_duplicate_or_out_of_batch_feedback_response_binding` — asserts response bindings are one per batch member and cannot authorize an unrelated feedback id.

- `test_candidate_accepts_typed_operations_from_multiple_batch_members` — asserts operations bearing different admitted feedback ids can contribute to one complete successor.

- `test_candidate_valid_plan_removal_with_its_ordering_remains_gate_clean` — retain or update the existing removal case to prove a batch-aware successor still removes the matching plan ordering entry.

- `test_candidate_refuses_plan_removal_without_exact_predecessor_ordering_entry` — retain the typed-removal failure case so batch work cannot weaken the coupled ordering requirement.

- `test_candidate_content_identity_ignores_typed_operation_order` — update the identity case for batch evidence and assert equivalent normalized operations retain one content identity.

Every listed test must be green before this step is complete.

## Acceptance criteria

- `materialize_candidate()` returns an in-memory complete candidate or review-required candidate whose feedback evidence binds the exact batch issued by step 1.

- Every admitted predecessor `open` feedback row appears exactly once in the successor as `awaiting-review` with one bound proposed response.

- Predecessor `awaiting-review` and `deferred` rows remain unchanged in the successor, including their response values.

- An operation with a feedback id outside the admitted batch returns an authorization refusal before candidate assembly.

- Missing or duplicate response coverage for the admitted batch returns a refusal and exposes no partial candidate.

- `CandidateRemoveRow` continues to remove typed rows, and a plan removal continues to require its exact predecessor ordering entry.

- Complete assembled artifacts still pass through `check_complete_roadmap_gates()` before a candidate outcome is returned.

- `uv run pytest tests/test_roadmap_candidate.py -q` passes.

## References

- [ROADMAP_FORMAT.md](../../../../ROADMAP_FORMAT.md) — Read the feedback lifecycle and predecessor-based feedback-integrity rules.
- [DATA_CONTRACT.md](../../../../DATA_CONTRACT.md) — Read the persisted candidate and immutable-version evidence contracts.
- [plan_tool/roadmap_candidate_context.py](../../../../plan_tool/roadmap_candidate_context.py) — Read the step 1 capsule, receipt, batch, and immutable-predecessor binding surface.
- [plan_tool/roadmap_candidate_run.py](../../../../plan_tool/roadmap_candidate_run.py) — Read the current candidate admission and evidence consumer that later adopts this batch-aware result.
- [plan_tool/roadmap_versions.py](../../../../plan_tool/roadmap_versions.py) — Read the immutable predecessor and accepted-head ownership boundary.

## Applicable guardrails

- **The plan’s “## Scope guardrails”, accepted-head authority** — This step may build inert candidate evidence only. It must not move `AcceptedRoadmapHead` or treat a materialized candidate as canonical.

- **The plan’s “## Scope guardrails”, batch identity** — This step must bind one explicit predecessor and exact batch throughout materialization, refusal, review-required evidence, and identities.

- **The plan’s “## Scope guardrails”, feedback lifecycle ownership** — This step may apply the existing model-owned open-to-awaiting-review transition for admitted rows. It must not add lifecycle states or perform reviewer-owned feedback actions.

- **The plan’s “## Out of scope”, operation and gate semantics** — This step must retain the existing typed operation and roadmap-gate meanings except where batch acceptance requires their binding to cover all admitted feedback.

- **The plan’s “## Out of scope”, lifecycle infrastructure** — This step must reuse the existing candidate, review, promotion, journal, checkpoint, and recovery owners rather than introduce parallel records or writers.

## Deferred

- Candidate admission, prompt rendering, and retry routing — Step 3 consumes this batch-aware materialization contract and changes the model-facing proposal flow.

- Review questions, replacement candidates, and seal binding — Step 5 extends the existing review lifecycle with the batch evidence produced here.

- Accepted-head promotion — Step 6 keeps promotion as the sole canonical writer and verifies batch and predecessor freshness there.
