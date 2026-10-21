> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 1 — Add a review-required result with an immutable initial impact identity for exact relation changes after all hard refusals

## Summary

Add a third materialization disposition for an exact, fully authorized declared-relation impact on a surviving row that needs review. Update `plan_tool/roadmap_candidate.py` to expose a distinct immutable review-required candidate and requirement record while retaining the existing gate-clean arm's no-requirement meaning and the existing refusal records. Keep hard refusals ahead of the new disposition, then compute the review requirement only from fully assembled candidate facts after every ordinary gate passes. On green, an eligible existing-row relation change returns one inert review-required result with a reproducible initial impact identity, while valid added-row and removed-row relation routes remain gate-clean.

## Table of Contents

- [Summary](#summary) — The step’s result and main design choice.
- [Table of Contents](#table-of-contents) — Links to each section in this detail.
- [Why](#why) — The missing materializer outcome this step closes.
- [Input](#input) — Existing candidate, capsule, relation, and diff contracts.
- [Files (creates vs edits)](#files-creates-vs-edits) — The two files this step changes.
- [Implementation](#implementation) — The disposition, eligibility, identity, and refusal rules.
- [Tests](#tests) — Focused coverage for the new materialization boundary.
- [Acceptance criteria](#acceptance-criteria) — Observable completion conditions.
- [References](#references) — Primary references for immutable records and canonical identities.
- [Applicable guardrails](#applicable-guardrails) — Plan boundaries that constrain this work.
- [Deferred](#deferred) — Later lifecycle work and unrelated relation editors left unchanged.

## Why

`plan_tool/roadmap_candidate.py:CandidateMaterializationResult` currently exposes only a `GateCleanCandidate` or `CandidateRefusal`, while `plan_tool/roadmap_candidate.py:_validate_operation_authority` rejects every existing-row relation change as `relation-authority`. That treats an exact impact over fully authorized rows the same as an ungrounded relationship rewrite, leaving no candidate for the existing review lifecycle to inspect. This step creates a precise middle result without weakening the checks that protect capsule authority, candidate rendering, roadmap gates, or accepted-head authority.

## Input

- **Closed delta input:** `plan_tool/roadmap_candidate.py:CandidateDelta` supplies typed operations, and `plan_tool/roadmap_candidate.py:_prepare_operations` supplies their normalized deterministic order. Bind the normalized operations, not the model’s raw JSON order.
- **Authority input:** `plan_tool/roadmap_candidate_context.py:CandidateContextCapsule`, its receipt, and `plan_tool/roadmap_candidate.py:_full_member_authority` establish the only predecessor rows that can support a review-required impact.
- **Relation input:** `plan_tool/roadmap_relations.py:extract_declared_relations` preserves source order and duplicate relation occurrences. Add one candidate-owned ordered multiset difference helper that derives directional relation-occurrence atoms from predecessor and candidate relations. Do not use `_relation_key`, a set, or a dictionary as the authority difference, and do not infer impact from prose or relation counts.
- **Candidate evidence input:** `plan_tool/roadmap_candidate.py:_assemble_candidate_artifacts` and `check_complete_roadmap_gates` provide the rendered, gate-clean bytes required before review eligibility exists. `_build_predecessor_diff` remains the compatible display snapshot; the new multiplicity-preserving atom helper provides exact relation authority and containment evidence.
- **Test fixtures:** `tests/test_roadmap_candidate.py:_resolved`, `_capsule`, and `_green_gates` provide an in-memory predecessor, authorized context, and deterministic gate seam.

## Files (creates vs edits)

- **New files:** none.

- **Existing files (edits only):**
  - `plan_tool/roadmap_candidate.py` — add the closed review-required result and requirement evidence, separate hard relation validation from review-policy classification, and derive the initial disclosed-impact identity.
  - `tests/test_roadmap_candidate.py` — replace the former terminal-relation-change expectation and add focused disposition, identity, precedence, and refusal coverage.

## Implementation

- **Foundational logic:** classify an authorized existing-row declared-relation diff as review-required only after all structural, rendering, and roadmap-gate refusals have passed.

- **Keep three exclusive materialization outcomes.** Extend `plan_tool/roadmap_candidate.py:CandidateMaterializationResult` so exactly one of hard refusal, ordinary `GateCleanCandidate`, or a distinct review-required candidate is present. Keep the existing gate-clean arm free of unresolved requirements; do not add an optional review field to `GateCleanCandidate`.

- **Use a closed immutable requirement record.** Add a frozen, strict, extra-forbid `CandidateReviewRequirement`-style record with one typed initial reason for declared-relation impact, its deterministic affected-row facts, normalized operations, `CandidatePredecessorDiff` display snapshot, independently comparable candidate-impact atoms, and an initial disclosed-impact identity. The review-required candidate must retain the normal candidate evidence needed by later storage work while clearly identifying itself as review-required.

- **Bind the whole initial disclosure, then derive one common atom stream.** The initial impact identity must bind the selected feedback, predecessor version, capsule receipt, normalized operation sequence, predecessor-diff display snapshot, every affected predecessor member, and the ordered containment atoms. Preserve relation and diff source order in the evidence and identity preimage. Derive row atoms from each `CandidateRowDiff` after projecting declared-relation fields out of its typed before and after values, and derive a directional relation atom for every unmatched relation occurrence through the ordered multiset helper. Include row additions, removals, and relation-independent changes as row atoms; include every added or removed relation occurrence as a relation atom. Use this same helper in `_validate_relation_authority`, eligibility classification, review evidence, and later replacement containment. Do not use whole normalized operations, whole rows, `CandidateArtifactDiff.after_digest`, or the lossy relation members of `CandidatePredecessorDiff` as containment atoms because a valid narrower relation change necessarily changes those enclosing values.

- **Keep impact identity separate from content identity.** `plan_tool/roadmap_candidate.py:_content_identity` identifies the candidate bytes and existing evidence, while the new initial disclosed-impact identity identifies the policy concern being reviewed. Do not redefine `_content_identity` to carry the new requirement: `plan_tool/roadmap_candidate_run.py:_validate_candidate_evidence` reproduces its current contract, and later steps must persist the new identity separately.

- **Move only the reviewable surviving-row rule.** Let `plan_tool/roadmap_candidate.py:_validate_operation_authority` continue to reject invalid bindings, invalid targets, missing full-row authority, and invalid plan ordering. It must no longer terminally reject an otherwise eligible `CandidateReplaceRow` solely because `same_declared_row_relations` differs. Do not classify a valid `CandidateRemoveRow` that removes its owner's relations or a valid anchored `CandidateAddRow` relation route as review-required; both retain their existing gate-clean behavior.

- **Preserve hard relation refusals and repeated-relation accounting.** Keep `plan_tool/roadmap_candidate.py:_validate_relation_authority` fail-closed for dangling relations, relation changes not attributable to authorized operations, missing affected endpoint membership, new sibling self-authorization, and unreached addition anchors. Feed it the same ordered multiset relation difference so removing one repeated relation is neither hidden nor deduplicated. A relation effect is reviewable only when the remaining checks prove its complete impact exactly.

- **Classify after complete validation.** One workable approach is to have relation validation retain enough deterministic relation-diff facts for a later policy classifier. Run that classifier only after `_assemble_candidate_artifacts`, `check_complete_roadmap_gates`, and `_build_predecessor_diff` succeed. A gate failure or any earlier refusal must return only `CandidateRefusal`, never a partial review-required candidate.

- **Limit the first reason.** Support the one declared-relation reason required by this plan with a closed typed vocabulary. Do not add a policy registry, generic rule language, semantic approval check, or second user interaction.

- **Make identity reproducible.** Reuse the canonical JSON discipline in `plan_tool/roadmap_candidate.py:_canonical_json_bytes` and SHA-256 hashing, with a separate review-impact preimage and schema marker. Validate the requirement’s identity against that preimage when constructing the immutable record so later persistence can reject substituted evidence.

- **Leave other relation editors unchanged.** `plan_tool/roadmap_revision.py:_validate_unchanged_relations` and `plan_tool/roadmap_revision_patch.py:_verify_stage_edit` share `same_declared_row_relations` but govern separate structural-revision contracts. Do not broaden this candidate-review behavior into those paths.

## Tests

### Tests for this step

- `test_candidate_materialization_requires_exactly_one_disposition` — asserts the result rejects zero, multiple, or ambiguous outcome arms.
- `test_candidate_authorized_existing_relation_change_returns_review_required` — asserts a changed relation on a fully authorized existing row produces only the review-required arm, retains an inert candidate payload, and leaves predecessor bytes unchanged.
- `test_review_requirement_binds_normalized_delta_complete_diff_and_affected_members` — asserts the requirement carries the prepared operations, predecessor-diff display snapshot, exact authorized predecessor members, and ordered candidate-impact atoms derived from the change.
- `test_review_requirement_identity_is_stable_for_normalized_operation_order` — asserts equivalent input operation order produces the same initial disclosed-impact identity.
- `test_review_requirement_identity_changes_with_disclosed_impact` — asserts a changed affected fact or complete candidate diff produces a different review-impact identity.
- `test_review_requirement_impact_atoms_keep_relation_removal_independent_of_its_row_snapshot` — asserts removing one relation from a surviving row produces a relation atom while its whole row and artifact snapshots remain disclosure-only evidence.
- `test_review_requirement_preserves_repeated_relation_occurrences_in_identity_and_atoms` — asserts removing one of repeated declared relations produces one distinct removed-relation occurrence and changes the review identity.
- `test_review_required_relation_difference_counts_repeated_occurrences_for_authority` — asserts a repeated relation difference cannot disappear through `_relation_key` deduplication.
- `test_candidate_ungrounded_relation_impact_remains_relation_authority_refusal` — asserts an impact involving a compact or otherwise unauthorized endpoint exposes no review-required candidate.
- `test_candidate_gate_failure_precedes_review_required_result` — asserts an otherwise eligible relation impact returns `gate-failed` and exposes no candidate when the complete gate bundle fails.
- `test_candidate_relation_free_authorized_replacement_remains_gate_clean` — asserts the existing ordinary replacement path remains gate-clean with no requirement.
- `test_candidate_valid_row_removal_with_incident_relation_removal_stays_gate_clean` — asserts the existing authorized `CandidateRemoveRow` route stays gate-clean.
- `test_candidate_valid_anchored_row_addition_stays_gate_clean` — asserts the existing reached-anchor addition route stays gate-clean.
- `test_candidate_added_relation_anchor_rules_remain_hard_refusals` — updates the current reached-anchor coverage to prove additions without a valid reached anchor do not enter review.

Green-before-done gate: every focused case above and `uv run pytest tests/test_roadmap_candidate.py -q` must pass.

## Acceptance criteria

- `materialize_candidate` exposes exactly one hard-refusal, gate-clean, or review-required disposition.
- A fully authorized existing-row relation change that passes rendering and all roadmap gates returns one immutable review-required candidate rather than `relation-authority`.
- The review requirement binds normalized operations, selected feedback, predecessor, capsule receipt, predecessor-diff display snapshot, affected predecessor members, ordered candidate-impact atoms, and a separately reproducible initial disclosed-impact identity.
- Candidate-impact atoms cover every changed row and every repeated relation occurrence at relation-independent granularity. One ordered multiset helper supplies hard relation validation, review eligibility, evidence, identity, and later containment; whole operations, rows, artifact digests, and lossy legacy diff relation members remain disclosure evidence rather than containment inputs.
- A malformed, unbound, ungrounded, undisclosed, or gate-failing relation impact returns a hard refusal with no review-required candidate.
- Existing relation-free gate-clean materialization and valid added-row and removed-row relation behavior remain compatible.
- `tests/test_roadmap_candidate.py` passes.

## References

- [Configuration | Pydantic Docshttps: — Use frozen, strict, extra-forbid record settings for closed evidence models.
- [Validators | Pydantic Docshttps: — Use model validation to enforce exclusive outcomes and identity bindings.
- [Serialization | Pydantic Docshttps: — Review deterministic serialization of immutable evidence.
- [json — JSON encoder and decoderhttps: — Review sorted keys, compact separators, and non-finite-number rejection for canonical preimages.
- [hashlib — Secure hashes and message digestshttps: — Review SHA-256 generation for the disclosed-impact identity.
- [RFC 8785: JSON Canonicalization Schemehttps: — Use as the reference model for stable structured identity inputs.
- [How to parametrize fixtures and test functionshttps: — Use deterministic counterexample matrices where several hard-refusal shapes share one assertion.

## Applicable guardrails

- **The plan’s “## Scope guardrails”, single selected-feedback request:** keep the requirement as materializer evidence bound to the selected feedback; do not add feedback rows, questions, commands, or transport.
- **The plan’s “## Scope guardrails”, binary observable:** emit review-required only for an exactly proven impact; any missing authority or unbounded fact must leave no candidate.
- **The plan’s “## Scope guardrails”, validator limits:** classify typed structural facts only. Do not judge prose quality, desirability, or opaque-answer meaning.
- **The plan’s “## Scope guardrails”, no new outcome policy:** do not add CLI behavior, exit-code rules, or a new roadmap-content gate in these files.
- **The plan’s “## Scope guardrails”, no generic approval framework:** keep the initial reason closed and local to candidate materialization.
- **The plan’s “## Scope guardrails”, accepted-head authority:** keep this materializer in-memory and inert; do not add promotion, accepted-artifact mutation, or review expansion behavior.
- **The plan’s “## Out of scope”, standalone relation authority:** do not add relation operations or wider model authority while making this narrow classification possible.

## Deferred

- `plan_tool/roadmap_candidate_run.py:run_initial_candidate_proposal`, `_store_candidate`, and `_validate_candidate_evidence` — step 2 owns persistence, replay, and admission replacement for the new review-required evidence.
- `plan_tool/roadmap_candidate_review.py:generate_candidate_question` and `request_replacement` — steps 3 and 4 own question binding, opaque-answer handling, replacement containment, and the initial-capsule-only boundary.
- `plan_tool/roadmap_revision.py:_validate_unchanged_relations` and `plan_tool/roadmap_revision_patch.py:_verify_stage_edit` — retain their existing strict structural-revision contracts because they do not participate in candidate review.
- Additional materializer-policy reasons or a reusable policy framework — require separate evidence and plan scope.
