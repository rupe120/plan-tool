> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 2 — Store review-required initial candidates with immutable evidence

## Summary

Extend candidate storage so the review-required materialization result from step 1 can follow the same inert initial-candidate route as a gate-clean result. Update `plan_tool/roadmap_candidate_run.py` to persist and replay the exact review requirement through candidate evidence, while keeping `CandidateProposalAdmission` as the mutable pointer to the admitted candidate version. Publish the candidate version, immutable evidence, and admission replacement through one pending generation. On green, a review-required initial candidate returns the existing `stored` outcome, replays without another backend call, and leaves the accepted head unchanged.

## Table of Contents

- [Summary](#summary) — The step’s stored-result contract.
- [Table of Contents](#table-of-contents) — Links to each section.
- [Why](#why) — The storage gap after step 1 adds a third materialization outcome.
- [Input](#input) — Materializer, admission, evidence, publication, and test contracts.
- [Files (creates vs edits)](#files-creates-vs-edits) — The two files this step edits.
- [Implementation](#implementation) — Storage, replay, and atomic-publication rules.
- [Tests](#tests) — Focused storage and replay coverage.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Persistence and immutable-record references.
- [Applicable guardrails](#applicable-guardrails) — Plan boundaries for this storage change.
- [Deferred](#deferred) — Review lifecycle work owned by later steps.

## Why

After step 1 adds a distinct review-required materialization result, `plan_tool/roadmap_candidate_run.py:run_initial_candidate_proposal` and `_store_candidate` only accept the current `GateCleanCandidate` arm. Without a stored representation of the requirement, an eligible candidate cannot reach the existing review, and a re-entry could not prove the exact concern the initial materialization found. The runner must store that requirement as immutable candidate evidence without turning the mutable admission pointer into a second source of review authority.

## Input

- **Step 1 result:** `plan_tool/roadmap_candidate.py:materialize_candidate` and `CandidateMaterializationResult` supply the distinct review-required arm, its normalized delta binding, and its initial disclosed-impact identity. Step 1 owns how those facts are computed; this step persists and reproduces them.
- **Existing candidate contract:** `plan_tool/roadmap_candidate_run.py:CandidateProposalEvidence`, `CandidateProposalAdmission`, and `StoredCandidateProposal` bind candidate bytes, predecessor, feedback, capsule, receipt, gates, and the admitted candidate version.
- **Publication contract:** `plan_tool/roadmap_candidate_run.py:_store_candidate` uses `plan_tool/roadmap_source_identity.py:GenerationMember` and `PendingGeneration` with `plan_tool/roadmap_revision_publish.py:publish_roadmap_generation`. Reuse this transaction unchanged.
- **Replay contract:** `plan_tool/roadmap_candidate_run.py:load_stored_candidate_proposal` and `_validate_candidate_evidence` load only persisted bytes and reproduce their stored facts before later review code can consume them.
- **Test seam:** `tests/test_roadmap_candidate_run.py:_enroll`, `_green_gates`, and injected proposal invokers provide deterministic storage coverage without a backend call.

## Files (creates vs edits)

- **New files:** none.

- **Existing files (edits only):**
  - `plan_tool/roadmap_candidate_run.py` — persist the review-required state in candidate evidence, accept both valid materializer candidate arms, and reproduce the stored requirement during load validation.
  - `tests/test_roadmap_candidate_run.py` — add review-required storage, replay, atomic-publication, collision, and tamper coverage while retaining the gate-clean cases.

## Implementation

- **Foundational logic:** persist and reproduce the materializer’s exact disposition and review requirement.

- **Accept both valid candidate arms explicitly.** Update `plan_tool/roadmap_candidate_run.py:run_initial_candidate_proposal` and `_store_candidate` to accept the gate-clean arm and step 1’s review-required arm. A hard refusal must still produce `response-rejected` with no candidate storage.

- **Make candidate evidence the requirement owner.** Extend `CandidateProposalEvidence` with the typed immutable requirement from step 1. A review-required candidate must retain the complete requirement, including its ordered, multiplicity-preserving candidate-impact atom stream, and an ordinary gate-clean candidate must retain no requirement. Validate the state against the materializer disposition so stored evidence cannot describe a review-required candidate as gate-clean.

- **Preserve old gate-clean evidence exactly.** Parse an absent requirement as no requirement, but omit that field from newly serialized no-requirement evidence and its identity preimage. Do not rewrite a pre-change record or change its evidence/content identities merely because the reader now knows about review requirements.

- **Keep admission narrow.** `CandidateProposalAdmission` must continue to bind the selected feedback, predecessor, final initial capsule, receipt, expansion state, and candidate-version pointer. Do not copy the review requirement into admission or create another mutable review pointer.

- **Preserve the current candidate identity shape.** Keep `_store_candidate` on `create_candidate_version` with `INITIAL_EMPTY_REVIEW_LINEAGE_ID`; the new disclosed-impact identity belongs to immutable review evidence, not the candidate content identity or accepted-head selector.

- **Publish one atomic generation.** Keep `_store_candidate`’s `PendingGeneration` as the only publication path. Candidate members and `candidate-evidence.json` must be new `GenerationMember` entries, while the admission member must replace the exact admission bytes read before publication with the version-bound admission. Do not write the candidate evidence or final admission update separately.

- **Keep evidence append-only.** Reject an existing or symlinked candidate evidence path before publication and preserve its bytes on collision. Re-entry may load and validate the evidence, but it must not rewrite, expand, or otherwise amend it.

- **Reproduce review-required evidence from stored authority.** Extend `_validate_candidate_evidence` so review-required evidence is checked against the stored predecessor, capsule, receipt, rendered candidate bytes, and step 1’s normalized delta binding. One suitable approach is to replay the stored normalized delta through `plan_tool/roadmap_candidate.py:materialize_candidate` and require the same review-required requirement, including its disclosed-impact identity and repeated relation-atom occurrences. Keep the existing diff, content-identity, artifact-digest, and gate-evidence checks.

- **Retain gate-clean replay unchanged.** `load_stored_candidate_proposal` must continue to load ordinary candidates with the existing evidence checks. A review requirement attached to a gate-clean candidate, a missing requirement for a review-required candidate, or a substituted requirement must fail closed.

- **Keep initial expansion behavior.** The initial proposal may still use the existing one-time context expansion before materialization. If the final response is review-required, persist the final admitted capsule and receipt with its requirement. Do not add answer-bound expansion handling or replacement state here.

- **Preserve the existing result and logging surface.** A successfully stored review-required candidate must use the existing `stored` outcome and exit-code path. Do not add a new outcome, gate, command, or accepted-head mutation.

## Tests

### Tests for this step

- `test_initial_delta_stores_one_gate_clean_inert_candidate_without_moving_accepted_head` — update the existing clean-path test to assert that ordinary stored evidence carries no review requirement.
- `test_pre_change_gate_clean_candidate_evidence_replays_with_existing_identity` — asserts a persisted evidence fixture with no requirement key loads and completes its existing lineage without rewriting identities.
- `test_review_required_initial_delta_stores_exact_requirement_without_moving_accepted_head` — asserts an eligible step-1 result stores its exact requirement, normalized binding, and disclosed-impact identity while the accepted head remains unchanged.
- `test_review_required_storage_replays_repeated_relation_occurrences_without_deduplication` — asserts a stored requirement preserves repeated relation-atom multiplicity and load validation rejects a dropped or added occurrence.
- `test_review_required_candidate_reentry_replays_persisted_requirement_without_backend_call` — asserts re-entry loads the same candidate and requirement without invoking the proposal backend.
- `test_review_required_candidate_after_initial_expansion_binds_final_admitted_capsule` — asserts a review-required result after the allowed initial expansion retains the final capsule and receipt, not the compact first-call capsule.
- `test_review_required_candidate_evidence_substitution_is_refused_on_load` — asserts altered requirement facts or identity make `load_stored_candidate_proposal` fail before later review can use the candidate.
- `test_review_required_storage_publishes_evidence_and_admission_in_one_generation` — asserts the pending generation creates candidate evidence and replaces the admission pointer together, with no separate final admission write.
- `test_review_required_candidate_evidence_collision_does_not_overwrite_existing_bytes` — asserts an existing evidence path blocks storage, preserves its bytes, and leaves admission without a candidate version.

Green-before-done gate: every listed case, `uv run pytest tests/test_roadmap_candidate_run.py -q`, and `uv run pytest tests/ -q -n auto` must pass.

## Acceptance criteria

- An eligible review-required initial materialization returns the existing `stored` result with one inert stored candidate.
- `CandidateProposalEvidence` binds the exact immutable review requirement, including repeated relation-atom multiplicity, for a review-required candidate and retains no requirement for a gate-clean candidate.
- Pre-change gate-clean evidence without a requirement key remains readable and retains its existing identity.
- Loading a review-required candidate reproduces its requirement from stored authority and rejects missing, changed, or substituted requirement evidence.
- `_store_candidate` publishes new candidate members and evidence with the admission candidate-version replacement in one `PendingGeneration`.
- Candidate evidence collisions or symlinks refuse without overwriting stored bytes or binding the admission to a candidate.
- Initial review-required storage preserves the existing accepted head, result code, run-log outcome, and one-time initial expansion behavior.
- `tests/test_roadmap_candidate_run.py` and the plan test command pass.

## References

- [Configuration | Pydantic Docshttps: — Use frozen, strict, extra-forbid settings for immutable persisted evidence.
- [Validators | Pydantic Docshttps: — Use model validation for disposition and cross-record bindings.
- [Serialization | Pydantic Docshttps: — Review deterministic model serialization and round-tripping.
- [json — JSON encoder and decoderhttps: — Review canonical JSON options used by the persisted records.
- [hashlib — Secure hashes and message digestshttps: — Review SHA-256 handling for immutable identities.
- [RFC 8785: JSON Canonicalization Schemehttps: — Use as the reference model for stable structured identity inputs.
- [How to parametrize fixtures and test functionshttps: — Use deterministic storage and tamper counterexamples.

## Applicable guardrails

- **The plan’s “## Scope guardrails”, one selected-feedback request:** keep the requirement bound to the admitted feedback and evidence; do not add another request, question, command, or transport surface.
- **The plan’s “## Scope guardrails”, binary observable:** store only a fully eligible review-required result. A refused, ungrounded, or incomplete result must expose no candidate.
- **The plan’s “## Scope guardrails”, validator limits:** validate typed materializer facts and stored bindings only; do not infer intent, prose meaning, or answer approval.
- **The plan’s “## Scope guardrails”, existing outcome policy:** preserve the current stored and refusal result paths without adding exit-code rules or roadmap gates.
- **The plan’s “## Scope guardrails”, no generic approval framework:** persist only the typed requirement step 1 supplies; do not add policy registration or extensibility machinery.
- **The plan’s “## Scope guardrails”, initial-capsule boundary:** retain the existing initial expansion behavior but do not add replacement expansion state or new authority.
- **The plan’s “## Scope guardrails”, accepted-head authority:** keep every stored candidate inert and leave accepted-head mutation to the existing promotion lifecycle.
- **The plan’s “## Out of scope”, relation authority:** do not change the materializer’s relation rules or add standalone relation operations in the runner.

## Deferred

- `plan_tool/roadmap_candidate_review.py:generate_candidate_question` and `CandidateQuestionInventory` — step 3 owns reading the stored requirement into the existing single-question inventory.
- `plan_tool/roadmap_candidate_review.py:request_replacement`, `_replacement_capsule`, and `_store_replacement` — step 4 owns answer-bound containment, replacement authority, and review-required replacement storage.
- `ROADMAP_FORMAT.md` and `tests/test_roadmap_format.py` — step 5 owns documentation of the landed candidate evidence contract.
- Additional review-required reasons or a general policy framework — require separate evidence and plan scope.
