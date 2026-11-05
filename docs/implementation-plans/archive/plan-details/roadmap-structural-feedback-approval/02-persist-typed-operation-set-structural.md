> **Auto-archived**: this plan was swept on 2026-11-05 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 2 — Persist the typed operation set and structural route while preserving atomic ledger overwrite and active-candidate replacement

<!-- plan-tool:detail-format-version: 1 -->

## Summary

Extend batch-candidate evidence in `plan_tool/roadmap_candidate_run.py` so each stored candidate retains the validated normalized operation set and its bounded or structural route. Consume step 1’s classification result rather than deriving a route from mutable ledger state, prose, or a relation diff at read time. Keep candidate bytes, evidence, active-candidate pointer replacement, supersession history, and selected ledger updates in the existing single publication generation. On green, `tests/test_roadmap_candidate_run.py` proves later readers receive exact, validated route facts while all existing storage conflicts remain fail-closed.

## Table of Contents

- [Summary](#summary) — Reviewer overview of the persisted candidate facts.
- [Table of Contents](#table-of-contents) — Quick links to each section.
- [Why](#why) — Why later lifecycle stages need stored route facts.
- [Input](#input) — The validated operation classification and batch storage contracts this step consumes.
- [Files (creates vs edits)](#files-creates-vs-edits) — The two files changed by this step.
- [Implementation](#implementation) — Evidence binding, replay checks, and atomic publication rules.
- [Tests](#tests) — Focused storage and stale-state coverage.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Candidate, ledger, and immutable-version contracts.
- [Applicable guardrails](#applicable-guardrails) — Boundaries on routing and canonical state.
- [Deferred](#deferred) — Decision and promotion work owned by later steps.

## Why

`plan_tool/roadmap_candidate_run.py:_store_batch_candidate` stores candidate bytes, gate evidence, batch receipt, ledger updates, and the active pointer, but it does not retain the validated operations that produced the candidate or the broader structural classification from step 1. A later review or promotion path would otherwise need to infer its route from mutable input or reconstruct it from a diff, which can disagree with the validated candidate boundary. Persisting and validating these facts beside the immutable candidate gives later steps one exact source without changing the current storage authority.

## Input

- **Step 1 classification:** Consume the normalized validated operation evidence and deterministic bounded-versus-structural result produced by step 1 in `plan_tool/roadmap_candidate.py:materialize_candidate`. Do not reclassify raw model text or a mutable ledger.
- **Batch candidate contract:** Read the batch result returned through `plan_tool/roadmap_candidate.py:BatchGateCleanCandidate`, including its source binding, complete artifact set, gate outcomes, response patch, and derived feedback.
- **Storage contract:** Extend `plan_tool/roadmap_candidate_run.py:CandidateProposalEvidence` and its `_requires_exact_bindings` validation without making selector-era evidence claim batch-only route facts it cannot prove.
- **Publication contract:** Retain `plan_tool/roadmap_revision_publish.py:publish_roadmap_generation` and `plan_tool/roadmap_candidate_run.py:require_batch_state_unchanged` as the write and final currentness boundary.

## Files (creates vs edits)

- **New files:** None.

- **Existing files (edits only):**
  - `plan_tool/roadmap_candidate_run.py` — Persist and validate the batch operation evidence and route in `CandidateProposalEvidence`, then carry them through batch storage and stored-candidate validation.
  - `tests/test_roadmap_candidate_run.py` — Add focused evidence, reload, route, and atomic-publication tests.

## Implementation

- **Persist the validated facts with the candidate.** Extend `CandidateProposalEvidence` with the complete normalized typed operation set and the route selected by step 1. The fields must come from the materialized batch candidate accepted by `plan_tool/roadmap_candidate.py:materialize_candidate`, not from the raw response, a ledger reread, or `predecessor_diff`.

- **Keep route selection closed and deterministic.** Store the step 1 bounded or structural result as a typed closed value. The route must agree with the stored normalized operations when `plan_tool/roadmap_candidate_run.py:_validate_candidate_evidence` checks a batch candidate. A relation-only change remains structural, but relation impact must not become a substitute classifier for additions, removals, ordering effects, or semantic replacements.

- **Bind evidence to immutable bytes.** Update `plan_tool/roadmap_candidate_run.py:_store_batch_candidate` so the persisted operation set and route are included in the evidence written beside the candidate version. On reload, validate them against the stored source version, stored candidate artifacts, and stored batch capsule. Do not consult the live ledger during this evidence check.

- **Preserve compatibility deliberately.** Batch evidence must require a complete operation-and-route pair. Selector-era evidence that predates the batch route must remain readable without invented route facts; reject incomplete or contradictory new batch metadata rather than treating absence as bounded.

- **Keep the batch ledger patch narrow.** Preserve `plan_tool/roadmap_candidate_run.py:_apply_batch_ledger_patch` as the owner of selected-item updates. It must update only the exact admitted snapshots and leave unrelated reviewer items and derived context intact under the existing rules.

- **Keep one atomic generation.** `plan_tool/roadmap_candidate_run.py:_store_batch_candidate` must continue to publish immutable candidate members, evidence, any `CandidateSupersession`, the active-candidate admission pointer, and the rendered ledger replacement through one `PendingGeneration`. Do not add a second writer or a follow-up route write.

- **Keep stale-state refusal at the publication boundary.** Retain `require_batch_state_unchanged` as the final check of both admission-pointer and ledger bytes. A changed pointer, changed selected item, or changed ledger during publication must refuse without replacing the ledger, pointer, or candidate history.

- **Keep active-candidate replacement intact.** When a new batch candidate replaces an active one, retain `build_supersession_member` and `build_active_candidate_pointer_member` in the same generation. The former active candidate remains immutable, the pointer names only the successor, and the stored route facts belong to each candidate independently.

- **Leave decision behavior to step 3.** This step records eligibility facts only. It must not add approve, edit, reject, review prompting, promotion, seed invalidation, or an accepted-head write.

## Tests

### Tests for this step

- `test_batch_candidate_evidence_persists_normalized_operations_and_bounded_route` — A presentation-only batch candidate reloads with the exact validated normalized operations and bounded route.
- `test_batch_candidate_evidence_persists_normalized_operations_and_structural_route` — A batch candidate containing a structural operation reloads with the exact operations and structural route.
- `test_batch_candidate_route_is_not_inferred_from_relation_diff` — A structural semantic change without a declared relation change remains structural after storage and reload.
- `test_batch_candidate_evidence_rejects_incomplete_operation_route_pair` — Batch evidence missing either operations or route is rejected rather than silently treated as bounded.
- `test_batch_candidate_evidence_rejects_route_that_disagrees_with_stored_operations` — Tampered route metadata that conflicts with the stored typed operation set refuses on validation.
- `test_selector_era_candidate_evidence_remains_readable_without_batch_route_facts` — Existing non-batch evidence remains readable without claiming a structural route.
- `test_batch_storage_keeps_unselected_ledger_items_unchanged` — `_apply_batch_ledger_patch` changes only admitted reviewer items while preserving unrelated items.
- `test_batch_storage_refuses_pointer_or_ledger_change_without_partial_publication` — A final-window state change leaves the admission pointer, ledger, and stored candidate set unchanged.
- `test_structural_successor_supersedes_active_candidate_in_the_same_generation` — A replacement candidate records its route, supersedes the former active candidate, and moves the active pointer together.

Every listed test must be green before this step is complete.

## Acceptance criteria

- A stored batch candidate contains the exact normalized validated operation set and a closed bounded or structural route.
- Reload validation rejects a batch candidate whose persisted route does not agree with its stored operations and immutable candidate facts.
- Selector-era candidate evidence remains readable without fabricated batch route metadata.
- Route selection does not read live ledger state, model prose, or only the predecessor diff.
- A successful batch store still publishes candidate bytes, evidence, ledger update, active pointer, and any supersession record as one generation.
- A changed ledger or admission pointer during the final publication window refuses without a partial overwrite.
- Unselected reviewer feedback remains unchanged after batch candidate storage.
- `tests/test_roadmap_candidate_run.py` passes with the focused route and atomicity coverage.

## References

- [Roadmap Structural Feedback Approval handoff — approved work order and prerequisite boundaries](../../../../../handoffs/2026-09-22-roadmap-feedback-revision-approval.md)
- [ROADMAP_FORMAT.md — immutable candidate authority and structural-route constraints](../../../../../ROADMAP_FORMAT.md)
- [DATA_CONTRACT.md — persisted candidate, review, and publication contracts](../../../../../DATA_CONTRACT.md)
- [ROADMAP_FEEDBACK_FORMAT.md — mutable ledger ownership and feedback lifecycle](../../../../../ROADMAP_FEEDBACK_FORMAT.md)
- [plan_tool/roadmap_candidate.py — validated operations and complete candidate materialization](../../../../../plan_tool/roadmap_candidate.py)
- [plan_tool/roadmap_candidate_run.py — candidate evidence, batch storage, and atomic state checks](../../../../../plan_tool/roadmap_candidate_run.py)
- [plan_tool/roadmap_revision_publish.py — journaled immutable generation publication](../../../../../plan_tool/roadmap_revision_publish.py)

## Applicable guardrails

- **Plan intent, explicit approval gate:** This step may record structural eligibility but must not treat storage as approval or promotion.
- **Plan scope guardrails, validated typed operations:** Persist only the operation facts already validated by the candidate boundary; do not introduce user route selection or new operation authority.
- **Plan scope guardrails, canonical selector:** Candidate storage and route persistence must not advance `AcceptedRoadmapHead` or rewrite live roadmap artifacts.
- **Plan scope guardrails, reuse existing contracts:** Extend the existing evidence, candidate store, ledger patch, pointer, and publication generation rather than creating parallel storage or transaction paths.
- **Plan scope guardrails, failure preservation:** Failed or stale storage must preserve canonical state and unrelated feedback through the existing refusal boundary.
- **Plan out of scope, structural operations:** Do not widen the candidate operation vocabulary or accept operations the current full-roadmap gates cannot validate.

## Deferred

- **Structural approve, edit, and reject decisions** — Step 3 consumes the stored route and typed operation evidence to create the single decision surface.
- **Promotion and accepted-head changes** — Step 5 owns approval-gated promotion and remains the sole accepted-head writer.
- **Documentation of the persisted metadata** — Step 7 updates the contract and operator references after the complete lifecycle lands.
