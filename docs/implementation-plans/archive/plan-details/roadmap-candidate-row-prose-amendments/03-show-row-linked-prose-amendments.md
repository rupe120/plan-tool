> **Auto-archived**: this plan was swept on 2026-11-05 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 3 — Show row-linked prose amendments in structural review without changing approval or promotion writes

<!-- plan-tool:detail-format-version: 1 -->

## Summary

Expose each admitted candidate prose amendment in the structural review output. Add a deterministic amendment-diff record in `plan_tool/roadmap_candidate.py`, then render it through the existing structural disclosure and stack views in `plan_tool/cli/roadmap_cmd.py`. Keep approval confirmation, seal creation, and promotion on their existing paths. On green, an approver sees every amendment’s artifact key, row id, and exact fragment before confirming the stack, and the stack digest changes when that disclosure data changes.

## Table of Contents

- [Summary](#summary) — Reviewer overview of the structural review change.
- [Table of Contents](#table-of-contents) — Quick links to each section.
- [Why](#why) — Why row additions alone do not make prose reviewable.
- [Input](#input) — The persisted amendment contract from step 2 and current review surfaces.
- [Files (creates vs edits)](#files-creates-vs-edits) — The scoped production and test edits.
- [Implementation](#implementation) — Amendment-diff derivation, disclosure, and digest rules.
- [Tests](#tests) — Focused review and CLI regression coverage.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Candidate, diff, review, and gate contracts.
- [Applicable guardrails](#applicable-guardrails) — Scope and lifecycle boundaries for this step.
- [Deferred](#deferred) — Adjacent work owned by later steps.

## Why

Step 2 makes a fragment part of an immutable candidate artifact, but a structural approver must also be able to inspect that exact fragment before approval. Existing `RoadmapDiff` output identifies changed artifacts and typed rows, while `plan_tool/cli/roadmap_cmd.py:_render_structural_candidate_stack()` and `_render_structural_candidate_disclosure()` present the approval surface. Add a narrow, deterministic prose-amendment disclosure instead of treating changed artifact bytes or the raw operation payload as a human review substitute.

## Input

- **Step 2 normalized operations:** Step 2 stores `CandidateAddRow.prose_amendment` beside the admitted addition in normalized candidate operations. Read that persisted operation data; do not infer narrative from an artifact body.
- **Existing stack identity:** `plan_tool/roadmap_candidate_review.py:CandidateStackView._stack_view_identity_input()` already binds each hop’s normalized operations into the stack digest. Keep that binding so an amendment changes the digest without changing approval logic.
- **Existing disclosure paths:** `plan_tool/cli/roadmap_cmd.py:_render_structural_candidate_disclosure()`, `_render_structural_candidate_stack()`, and `_print_diff_lines()` render the top candidate, lower hops, and cumulative comparison.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `plan_tool/roadmap_candidate.py` — derive a deterministic row-linked amendment-diff record from normalized candidate add-row operations.
  - `plan_tool/cli/roadmap_cmd.py` — render amendment records in structural candidate disclosure and per-hop stack output without changing decision dispatch.
  - `tests/test_roadmap_candidate_review.py` — verify amendment data participates in the stored-record review and stack-digest contract.
  - `tests/cli/test_roadmap_cmd.py` — verify structural output shows exact amendment records and retains existing no-write and promotion behavior.

## Implementation

- **Derive review data from admitted operations.** Add a small immutable amendment-diff record in `plan_tool/roadmap_candidate.py` that contains only the artifact key, added row id, and fragment. Derive records from `CandidateAddRow` normalized operations that carry the step-2 amendment field.

- **Keep the record deterministic.** Preserve normalized operation order when producing amendment records. Do not read current artifacts, mutable feedback, or generated prose to reconstruct the records; the stored operation is the authority for what the candidate proposed.

- **Expose the same data at every structural review level.** Extend `plan_tool/cli/roadmap_cmd.py:_render_structural_candidate_disclosure()` for the top candidate and `_render_structural_candidate_stack()` for lower hops so an approver can identify each amendment before the existing choices or confirmation line. Keep cumulative output focused on its current root-to-tip comparison unless it can truthfully show the same deterministic amendment records.

- **Bind display facts to confirmation.** Keep `CandidateStackView._stack_view_identity_input()`’s normalized-operation binding intact. The amendment record must therefore affect the digest used by `_cmd_roadmap_structural_candidate_decision()` and `plan_tool/roadmap_candidate_review.py:decide_structural_candidate()` without adding a second digest or a display-only value outside the existing identity input.

- **Preserve approval and promotion writes.** Do not change `decide_structural_candidate()`, structural approval seals, or `_cmd_roadmap_promote_review_seal_id()` to write amendment-specific state. The review output remains read-only; unconfirmed approval still writes nothing, and confirmed approval promotes through the existing seal path.

- **Keep non-amendment candidates readable.** Candidates whose normalized operations contain no prose amendment must retain their current structural review output apart from an empty or omitted amendment disclosure chosen consistently with existing optional structural facts. Do not add absent amendment fields to legacy evidence.

- **Do not widen candidate prose authority.** This step only displays step 2’s admitted add-row data. It must not add prose handling for replacements or removals, alter reviewer binding, or weaken `check_inventory_has_prose()`.

## Tests

### Tests for this step

- `test_candidate_prose_amendment_diff_lists_artifact_row_and_exact_fragment_in_normalized_order` — asserts multiple admitted additions produce ordered records containing only their artifact key, row id, and exact fragment.
- `test_candidate_prose_amendment_diff_ignores_operations_without_an_admitted_add_row_amendment` — asserts replace, remove, and legacy operations do not invent disclosure records.
- `test_stack_view_digest_changes_when_an_amended_operations_fragment_changes` — extends the stack identity coverage so changing only an admitted fragment changes the digest rebuilt from stored records.
- `test_stack_view_rebuilds_amendment_disclosure_from_stored_operations` — asserts an in-memory alteration cannot change the review data or digest.
- `test_structural_disclosure_prints_row_linked_prose_amendment_records` — asserts the top-candidate disclosure includes artifact key, row id, and exact fragment.
- `test_stack_printout_lists_amendment_records_for_each_hop` — asserts lower-hop amendments remain attached to their own hop and retain stored order.
- `test_unconfirmed_structural_approve_discloses_amendments_and_writes_nothing` — asserts the first approval invocation shows amendments and leaves all roadmap state unchanged.
- `test_confirmed_structural_approve_promotes_the_same_seal_after_amendment_disclosure` — asserts confirmation still uses the displayed stack digest and follows the existing promotion path.

Every listed test must be green before this step is complete.

## Acceptance criteria

- A normalized add-row operation with an admitted prose amendment produces one deterministic record containing its artifact key, row id, and exact fragment.
- Structural disclosure and stack output show every amendment record before an approver confirms the stack.
- Amendment records retain normalized operation order and remain associated with their originating stack hop.
- Changing only a stored amendment fragment changes the candidate stack digest.
- A structural candidate without amendments remains reviewable without invented amendment data.
- Unconfirmed approval still writes nothing.
- Confirmed approval still creates and promotes only through the existing structural seal path.
- `tests/test_roadmap_candidate_review.py` and `tests/cli/test_roadmap_cmd.py` pass.

## References

- [BUG_BACKLOG.md — Read “Structural candidates cannot satisfy described-row gates for newly added rows” for the required review-visible amendment record.](BUG_BACKLOG.md)
- [plan_tool/roadmap_candidate.py — Read `CandidateAddRow`, `CandidatePredecessorDiff`, and candidate operation normalization for immutable amendment inputs.](plan_tool/roadmap_candidate.py)
- [plan_tool/roadmap_diff.py — Read `RoadmapDiff` and `RoadmapRowDiff` for the existing structural-diff model.](plan_tool/roadmap_diff.py)
- [plan_tool/roadmap_candidate_review.py — Read `CandidateStackView`, `_stack_view_identity_input()`, and `build_candidate_stack_view()` for stored-record stack identity.](plan_tool/roadmap_candidate_review.py)
- [plan_tool/cli/roadmap_cmd.py — Read `_render_structural_candidate_disclosure()`, `_render_structural_candidate_stack()`, and `_cmd_roadmap_structural_candidate_decision()` for the review and confirmation surface.](plan_tool/cli/roadmap_cmd.py)
- [plan_tool/roadmap_gates.py — Read `check_inventory_has_prose()` for the unchanged described-row rule.](plan_tool/roadmap_gates.py)

## Applicable guardrails

- **The plan’s “## Out of scope”, prose amendment boundary:** Limit this step to showing admitted addition amendments; do not add prose behavior to other candidate operations.
- **The plan’s “## Out of scope”, prose-gate enforcement:** Keep the gate unchanged; review disclosure does not become an alternate way to satisfy it.
- **The plan’s “## Out of scope”, candidate authority and lifecycle:** Keep approval, ledger, accepted-head, seed, and promotion ownership on their existing paths.
- **The plan’s “## Architecture”, immutable review contract:** Derive review data from persisted normalized operations so the displayed facts and confirmation digest refer to the same candidate content.

## Deferred

- Candidate proposal and correction prompt instructions — step 4 owns model-facing amendment guidance.
- Replacement-span and removal-prose review semantics — remain outside the plan’s candidate-addition boundary.
