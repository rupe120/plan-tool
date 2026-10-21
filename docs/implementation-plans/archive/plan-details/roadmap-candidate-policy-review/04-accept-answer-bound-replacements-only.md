> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 4 — Accept answer-bound replacements only when their recomputed impact is contained by the initial disclosure and the admitted capsule

## Summary

Update `plan_tool/roadmap_candidate.py` and `plan_tool/roadmap_candidate_review.py` so every review-required-lineage replacement, including a `GateCleanCandidate` that eliminates the typed reason, carries a newly computed candidate-impact atom stream contained by the initial disclosure. Keep containment as a multiplicity-preserving atom comparison owned by candidate logic, not an equality check on impact identities or an interpretation of the reviewer’s answer. Review-required replacements must reuse the initially admitted capsule and cannot use the existing expansion path. On green, a contained replacement can be stored and sealed, while a wider, stale, or expansion-seeking replacement creates no candidate or seal.

## Table of Contents

- [Summary](#summary) — The step’s result and main design choice.
- [Table of Contents](#table-of-contents) — Links to each section.
- [Why](#why) — The missing boundary around answer-bound replacements.
- [Input](#input) — The initial requirement, inventory, materializer, and stored-record contracts.
- [Files (creates vs edits)](#files-creates-vs-edits) — The declared implementation and test files.
- [Implementation](#implementation) — Containment, capsule reuse, storage, and replay rules.
- [Tests](#tests) — Focused counterexamples and regression coverage.
- [Acceptance criteria](#acceptance-criteria) — Observable completion conditions.
- [References](#references) — Immutable-record and deterministic-identity references.
- [Applicable guardrails](#applicable-guardrails) — Plan boundaries that constrain this step.
- [Deferred](#deferred) — Related work left outside this focused change.

## Why

`plan_tool/roadmap_candidate_review.py:request_replacement` currently lets every replacement use the normal expansion path and accepts any gate-clean `materialize_candidate` result for storage. After steps 1–3 make an initial review-required impact visible in immutable evidence and the question inventory, that behavior could let an opaque answer produce a replacement with new authority or a different policy impact. This step keeps the existing one-question lifecycle while making the initial disclosure and capsule the hard boundary for the replacement that may later be sealed.

## Input

- **Step 3 inventory:** step 3 produces one immutable `plan_tool/roadmap_candidate_review.py:CandidateQuestionInventory` that binds the stored initial review requirement to the exact question and answer lineage.
- **Initial candidate evidence:** step 2 extends `plan_tool/roadmap_candidate_run.py:CandidateProposalEvidence` with the validated review-required state. Its predecessor, selected feedback, capsule, receipt, and requirement are the fixed baseline for this comparison.
- **Materializer result:** `plan_tool/roadmap_candidate.py:materialize_candidate`, `CandidateMaterializationResult`, and `GateCleanCandidate` provide the candidate-derived result. The candidate-owned atom helper must run for both review-required and gate-clean results so reason elimination never bypasses disclosure containment.
- **Replacement lifecycle:** `plan_tool/roadmap_candidate_review.py:request_replacement`, `_store_replacement`, `_validate_replacement`, and `CandidateReviewReplacement` own answer-bound storage and replay.
- **Promotion reader:** `plan_tool/roadmap_version_promotion.py:_load_complete_sealed_candidate` already calls `_validate_replacement`; retain that single validation path rather than adding a promotion-only comparison.

## Files (creates vs edits)

- **New files:** none.

- **Existing files (edits only):**
  - `plan_tool/roadmap_candidate.py` — add the narrow deterministic recomputation and containment check for the review requirement produced by step 1.
  - `plan_tool/roadmap_candidate_review.py` — select the initial-capsule-only route for review-required lineages, persist the recomputed replacement-impact state, and validate containment before replay, sealing, or promotion can consume it.
  - `tests/test_roadmap_candidate.py` — cover fact-based containment and counterexamples without relying on impact-identity equality.
  - `tests/test_roadmap_candidate_review.py` — cover review-required replacement storage, refusal, capsule reuse, and gate-clean expansion compatibility.
  - `tests/test_roadmap_version_promotion.py` — cover promotion of an exact sealed, contained review-required replacement and refusal that preserves the accepted head.

## Implementation

- **Foundational logic:** accept a review-required replacement only when its complete, newly derived candidate-impact atom stream is a multiplicity-preserving subset of the initial disclosed stream, whether or not the typed reason remains.

- **Compare independent atoms, not identities or enclosing snapshots.** Keep the initial disclosed-impact identity and a replacement impact identity as separate immutable evidence. In `plan_tool/roadmap_candidate.py`, place one small deterministic containment check beside the step 1 atom helper. It must compare the complete typed replacement candidate-impact atom stream with the initial stream; it must not compare counts, row IDs alone, whole normalized operations, whole `CandidateRowDiff` values, or artifact after-digests, and it must not require the two impact identities to match. Treat repeated equal relation atoms as an ordered multiset: retained evidence and identities preserve source order, while containment requires each atom's replacement count to be no greater than its initial count.

- **Contain every result arm.** A `GateCleanCandidate` replacement represents elimination of the initial typed requirement, not automatic containment. Derive and persist its current atom stream, then require it to be contained by the initial stream before storage or sealing. A replacement that still carries the typed review-required state must additionally retain the same policy reason. In either arm, every remaining relation-independent row atom or directional-relation occurrence must be contained at no greater multiplicity. Removing atoms is valid; adding, changing, or substituting one is not. This admits a smaller relation removal on a surviving row while the unchanged row-base atom remains equal, but rejects a changed non-relation field, a new row, a repeated relation occurrence beyond initial multiplicity, or a gate-clean candidate with an unrelated authorized change. The full normalized operation sequence and display diff remain identity-bound disclosure for the reviewer; they are not directly comparable containment values.

- **Keep the materializer authoritative.** Use `materialize_candidate` to derive the replacement’s state from the replacement candidate, then use the candidate-owned containment check from the prior bullet. Do not let `CandidateReviewAnswer.answer_text`, a model-supplied impact identity, or hand-written replacement evidence decide whether the impact is contained.

- **Bind the fixed lineage before storage.** In `plan_tool/roadmap_candidate_review.py:request_replacement`, require the stored initial requirement in both `CandidateProposalEvidence` and the step 3 inventory to agree before invoking the replacement model. The replacement must bind the same predecessor version, selected feedback, initial candidate, inventory, answer, capsule, and receipt.

- **Refuse stale review-required writes.** Before invoking or storing a review-required replacement, require its predecessor to remain the current accepted head and repeat that check at the storage writer boundary. `seal_review` must make the same check before it writes a seal. Preserve `promote_review_seal`'s existing final current-head check and do not change gate-clean lineage behavior.

- **Use the admitted capsule for review-required replacements.** When the initial candidate carries a review requirement, invoke the replacement only with `initial.evidence.capsule` and its matching receipt. Pass `allow_expansion=False` to `plan_tool/roadmap_candidate_run.py:parse_candidate_proposal_response`; an `expand` response must be rejected before context expansion or a second model call.

- **Refuse replacement state on that lineage.** Update `_replacement_capsule` or a narrow caller-owned selector so a review-required initial candidate refuses an existing `replacement_state_path`, including a symlink. Do not read, create, or publish `CandidateReviewReplacementState` for that lineage. Preserve the current state-loading and one-expansion behavior when the initial candidate is gate-clean.

- **Persist the computed result for every result arm.** Extend `CandidateReviewReplacement`, its canonical identity checks, and `_store_replacement` to retain the replacement’s computed atom stream. A remaining requirement must carry its own recomputed identity and facts; an eliminated requirement must remain an unambiguous no-requirement state while still retaining the atom stream that proves it did not add a non-disclosed candidate change. Do not copy the initial identity into replacement evidence.

- **Revalidate on every later read.** `_validate_replacement` must verify the stored replacement against the exact initial evidence and inventory, the admitted capsule and receipt, the replacement candidate version, and the candidate-owned containment rule. An identity by itself is not enough proof. A missing, changed, widened, duplicated, gate-clean-but-uncontained, or otherwise uncontained replacement state must refuse before `seal_review` or `plan_tool/roadmap_version_promotion.py:_load_complete_sealed_candidate` can promote it.

- **Keep outcomes and approval boundaries unchanged.** Reuse the current `stored` and fail-closed result behavior in `request_replacement`; do not add an exit-code branch. `answer_candidate_question` may still request and seal one valid replacement, but only `promote_review_seal` changes the accepted head.

- **Leave other relation editors unchanged.** `plan_tool/roadmap_revision.py:_validate_unchanged_relations` and `plan_tool/roadmap_revision_patch.py:_verify_stage_edit` share relation-comparison vocabulary but enforce separate revision contracts. Do not extend this answer-bound exception to either path.

## Tests

### Tests for this step

- `test_review_requirement_containment_allows_eliminated_or_subset_impact` — asserts candidate logic accepts no remaining requirement and a complete remaining candidate-impact atom subset.
- `test_review_requirement_containment_does_not_require_equal_impact_identities` — asserts containment is based on independently derived atoms rather than equality of initial and replacement identities.
- `test_review_requirement_containment_allows_narrower_relation_removal_on_one_surviving_row` — asserts a replacement that retains one initially disclosed relation removal but restores another has a contained relation atom set even though its enclosing row, operation, diff, and artifact digest differ.
- `test_review_requirement_containment_counts_repeated_relation_occurrences` — asserts a replacement cannot retain more equal relation occurrences than the initial disclosure.
- `test_gate_clean_review_required_replacement_refuses_undisclosed_authorized_change` — asserts restoring the reviewed relation does not let an otherwise gate-clean replacement add an unrelated authorized row or non-relation edit.
- `test_gate_clean_review_required_replacement_accepts_contained_atom_stream` — asserts an eliminated reason can store and seal only when its independently derived atom stream remains contained.
- `test_review_requirement_containment_refuses_added_or_changed_atom` — asserts a new affected member, non-relation row change, relation occurrence, or policy reason is not contained.
- `test_review_required_replacement_accepts_eliminated_impact_with_initial_capsule` — asserts a valid answer-bound replacement that removes the requirement stores and seals using the original capsule and receipt.
- `test_review_required_replacement_accepts_contained_recomputed_impact` — asserts a remaining review-required impact with only initial-disclosure facts stores its recomputed replacement identity and can seal.
- `test_review_required_replacement_refuses_uncontained_impact_without_candidate_or_seal` — asserts a wider or different impact returns the existing fail-closed result and leaves no replacement binding or seal.
- `test_review_required_replacement_rejects_expansion_without_replacement_state_write` — asserts an `expand` response is rejected after one call and does not create `CandidateReviewReplacementState`.
- `test_review_required_replacement_refuses_preexisting_regular_or_symlinked_state_before_invocation` — asserts pre-existing normal and symlinked replacement-state paths refuse before a model call, state read, or any artifact write.
- `test_review_required_replacement_revalidates_persisted_containment_before_seal` — asserts substituted or mismatched replacement evidence refuses during replay or sealing.
- `test_stale_review_required_lineage_refuses_before_replacement_or_seal_write` — advances the accepted head after initial review and proves answer/replacement and sealing leave no new artifacts; promotion retains its race check.
- `test_pre_change_gate_clean_lineage_replays_and_spends_its_existing_expansion` — proves old no-requirement inventory, replacement, and seal records retain their identity and clean-path behavior.
- `test_answer_driven_replacement_spends_the_recorded_expansion_once` — retain and clarify the gate-clean regression case: its existing expansion route remains available and writes its normal replacement state.
- `test_review_required_contained_replacement_promotes_only_after_exact_seal` — asserts the accepted head changes only through promotion of the exact contained replacement.
- `test_promotion_refuses_uncontained_review_required_replacement_and_preserves_head` — asserts promotion reaches replacement validation, refuses invalid containment evidence, and leaves the accepted head unchanged.

Green-before-done gate: every listed case, `uv run pytest tests/test_roadmap_candidate.py tests/test_roadmap_candidate_review.py tests/test_roadmap_version_promotion.py -q`, and `uv run pytest tests/ -q -n auto` must pass.

## Acceptance criteria

- Every review-required-lineage replacement, including a gate-clean result that eliminates the initial requirement, proves every candidate-impact atom is contained by the initial disclosure at no greater relation-occurrence multiplicity.
- Initial and replacement impact identities remain separate; containment does not require identity equality.
- A new, changed, repeated, wider, stale, gate-clean-but-uncontained, or otherwise uncontained replacement exposes no stored replacement or review seal.
- A review-required replacement uses only the initially admitted capsule and receipt, rejects expansion and pre-existing regular or symlinked replacement state, and leaves no replacement-expansion state.
- Existing gate-clean replacements retain their current one-expansion behavior.
- `CandidateReviewReplacement` and `_validate_replacement` retain and verify the computed replacement-impact state before sealing or promotion.
- Only exact review-seal promotion changes the accepted head.
- `tests/test_roadmap_candidate.py`, `tests/test_roadmap_candidate_review.py`, `tests/test_roadmap_version_promotion.py`, and the full plan test command pass.

## References

- [Configuration | Pydantic Docshttps: — Use frozen, strict, extra-forbid records for replacement evidence.
- [Validators | Pydantic Docshttps: — Use model validators for lineage, state, and identity bindings.
- [Serialization | Pydantic Docshttps: — Review deterministic model serialization for persisted review records.
- [json — JSON encoder and decoderhttps: — Review canonical JSON options for impact-identity inputs.
- [hashlib — Secure hashes and message digestshttps: — Review SHA-256 identities for immutable impact evidence.
- [RFC 8785: JSON Canonicalization Schemehttps: — Use as the reference model for stable structured identity inputs.
- [How to parametrize fixtures and test functionshttps: — Use focused contained and non-contained counterexample matrices.

## Applicable guardrails

- **The plan’s “## Scope guardrails”, single selected-feedback request:** keep the answer-bound route inside the existing candidate, question, answer, replacement, and seal lifecycle.
- **The plan’s “## Scope guardrails”, binary observable:** reject a replacement that lacks complete authority or has facts outside the disclosure without storing a candidate.
- **The plan’s “## Scope guardrails”, validator limits:** compare deterministic typed facts only; do not judge prose quality, desirability, or the meaning of answer text.
- **The plan’s “## Scope guardrails”, no new outcome policy:** retain existing replacement outcomes and exit behavior.
- **The plan’s “## Scope guardrails”, no generic approval framework:** keep one direct containment check for the typed requirement rather than adding a policy registry.
- **The plan’s “## Scope guardrails”, initial capsule reuse:** make the review-required branch reject expansion and replacement state while preserving the gate-clean branch.
- **The plan’s “## Scope guardrails”, accepted-head authority:** keep all candidate and review records inert until the existing exact promotion path runs.
- **The plan’s “## Out of scope”, broader relation authority:** do not add standalone relation operations or make this narrow replacement rule available to other revision flows.

## Deferred

- `plan_tool/roadmap_revision.py:_validate_unchanged_relations` and `plan_tool/roadmap_revision_patch.py:_verify_stage_edit` — retain their strict relation-preservation rules because they do not participate in the candidate-review lineage.
- Additional review-required reasons or a reusable policy framework — require separate evidence and plan scope.
- Multiple reviewer questions, answer interpretation, and alternate approval transport — remain outside the single-review lifecycle.
