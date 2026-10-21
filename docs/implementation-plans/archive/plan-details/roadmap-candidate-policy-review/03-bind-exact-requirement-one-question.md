> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 3 — Bind the exact requirement into the one question inventory while keeping question records create-only

## Summary

Extend `plan_tool/roadmap_candidate_review.py` so `CandidateQuestionInventory` binds the exact review requirement that step 2 stores with an initial candidate. Update `plan_tool/prompts/roadmap-candidate-questions.md` to give the model that immutable context, while `plan_tool/cli/roadmap_cmd.py:_render_candidate_review_result` deterministically shows the same facts to the reviewer beside the one question. Keep question and answer text opaque, and preserve gate-clean records that have no requirement. On green, a review-required candidate creates or replays one immutable inventory whose identity proves the exact disclosed impact.

## Table of Contents

- [Summary](#summary) — The step’s result and main design choice.
- [Table of Contents](#table-of-contents) — Links to each section.
- [Why](#why) — The missing review-requirement binding.
- [Input](#input) — Stored candidate and question-lifecycle contracts.
- [Files (creates vs edits)](#files-creates-vs-edits) — The declared implementation files.
- [Implementation](#implementation) — Binding, compatibility, rendering, and immutability rules.
- [Tests](#tests) — Focused coverage for the one-question boundary.
- [Acceptance criteria](#acceptance-criteria) — Observable completion conditions.
- [References](#references) — Immutable-record and canonical-serialization sources.
- [Applicable guardrails](#applicable-guardrails) — Plan boundaries that constrain this work.
- [Deferred](#deferred) — Later replacement-policy work.

## Why

Step 2 makes a validated review requirement available on stored initial-candidate evidence, but `plan_tool/roadmap_candidate_review.py:CandidateQuestionInventory`, `_new_question_inventory`, and `render_candidate_question_prompt` bind only the existing candidate facts. The review contact must prove the exact policy impact it covers and show that impact without letting model-written question text or opaque answer text act as approval.

## Input

- **Step 2 stored result:** step 2 extends `plan_tool/roadmap_candidate_run.py:CandidateProposalEvidence`; the loaded `StoredCandidateProposal` carries either the exact immutable review requirement or the existing no-requirement gate-clean state.
- **Inventory contract:** `plan_tool/roadmap_candidate_review.py:CandidateQuestionInventory`, `_inventory_preimage`, `render_question_inventory`, and `parse_question_inventory` define the canonical stored inventory.
- **Question lifecycle:** `plan_tool/roadmap_candidate_review.py:generate_candidate_question`, `_load_question_inventory_if_present`, `_validate_inventory`, and `_publish_new_record` own replay, validation, and one-time publication.
- **Answer boundary:** `plan_tool/roadmap_candidate_review.py:CandidateReviewAnswer`, `_new_answer`, and `record_reviewer_answer` bind answer bytes to inventory and question identities without interpreting their meaning.
- **Review display:** `plan_tool/roadmap_candidate_review.py:render_candidate_question_prompt` renders `plan_tool/prompts/roadmap-candidate-questions.md`, while `plan_tool/cli/roadmap_cmd.py:_render_candidate_review_result` prints the stored review contact.

## Files (creates vs edits)

- **New files:** none.

- **Existing files (edits only):**
  - `plan_tool/roadmap_candidate_review.py` — bind and validate the requirement in question inventories, preserve canonical gate-clean records, and provide the stored requirement to the prompt.
  - `plan_tool/cli/roadmap_cmd.py` — render the stored requirement beside the existing question.
  - `plan_tool/prompts/roadmap-candidate-questions.md` — present the complete stored requirement and restate that it grants no edit authority.
  - `tests/test_roadmap_candidate_review.py` — cover review-required inventories, gate-clean compatibility, prompt context, replay, tampering, and opaque answers.
  - `tests/cli/test_roadmap_cmd.py` — cover deterministic requirement display and the compatible CLI lifecycle.

## Implementation

- **Foundational logic:** bind the validated initial review requirement into the one immutable question inventory and its canonical identity.

- **Mirror the stored state exactly.** Extend `plan_tool/roadmap_candidate_review.py:CandidateQuestionInventory` and `_new_question_inventory` with the requirement state that step 2 stores. A review-required candidate must carry its exact requirement; a gate-clean candidate must carry no synthetic requirement.

- **Bind the requirement to the inventory, not the question.** `CandidateQuestion.question_id` must remain a function of its existing anchor and opaque question text. Include a review-required inventory’s complete requirement in `_inventory_preimage` so a changed requirement changes `inventory_id`.

- **Preserve no-requirement records.** `render_question_inventory`, `parse_question_inventory`, and `_inventory_preimage` must omit the requirement from gate-clean inventories. Existing gate-clean evidence and inventory bytes must remain parseable with their existing identities; adding a `null` field is not compatible.

- **Validate every reader path.** `_validate_inventory` must compare requirement presence and exact facts with the stored initial candidate, alongside its existing content, predecessor, feedback, diff, capsule, and anchor checks. Missing, substituted, or mismatched requirement facts must refuse before an answer, replacement, seal, or promotion can consume the inventory.

- **Keep inventories create-only.** Preserve `generate_candidate_question`’s load-before-invoke order and `_publish_new_record` collision behavior. A valid existing inventory must replay with no backend call or write. An invalid existing inventory must refuse rather than regenerate or replace it.

- **Provide complete immutable context to the prompt.** Update `render_candidate_question_prompt` and `plan_tool/prompts/roadmap-candidate-questions.md` together. The template must receive the complete stored requirement, including its identity and disclosed facts, using only persisted candidate evidence. Keep the closed response shape in `parse_candidate_question_response`: one anchor and one opaque question.

- **Show the same facts to the human reviewer.** Update `plan_tool/cli/roadmap_cmd.py:_render_candidate_review_result` to render the stored requirement’s identity, reason, affected facts, normalized operations, display diff, and ordered candidate-impact atom stream alongside the one question. Render repeated relation occurrences separately in their stored order. Model-written question text must not be the only disclosure path.

- **Keep answers opaque and inert.** Do not add approval fields, requirement selectors, or semantic parsing to `CandidateReviewAnswer`, `_new_answer`, or `record_reviewer_answer`. Blank and arbitrary answer text remain valid guidance bound through the requirement-bearing inventory identity.

- **Reuse promotion validation unchanged.** `plan_tool/roadmap_version_promotion.py:_load_complete_sealed_candidate` already parses the inventory and calls `plan_tool/roadmap_candidate_review.py:_validate_inventory`. Keep that single validation path rather than adding promotion-only requirement checks.

## Tests

### Tests for this step

- `test_review_required_question_inventory_binds_exact_stored_requirement` — asserts a review-required candidate inventory carries the exact requirement from its stored evidence.
- `test_review_required_requirement_changes_inventory_identity` — asserts changing any bound requirement fact invalidates the inventory identity.
- `test_gate_clean_question_inventory_omits_requirement_and_replays_legacy_bytes` — asserts no-requirement inventories retain their canonical serialized shape and existing identity.
- `test_review_required_question_prompt_contains_complete_stored_requirement` — asserts the prompt contains the stored requirement and no live brief or repository data.
- `test_question_response_stays_anchor_and_question_only_with_requirement_context` — asserts requirement context does not widen the closed model response schema.
- `test_requirement_mismatch_refuses_before_question_invocation_or_rewrite` — asserts a malformed or substituted stored inventory refuses without a backend call or replacement write.
- `test_review_required_inventory_replay_does_not_invoke_or_rewrite` — asserts a valid stored inventory replays unchanged with zero model calls.
- `test_reviewer_answer_remains_opaque_with_bound_requirement` — asserts blank and arbitrary answer text remain valid and bind only through the inventory and question identities.
- `test_review_result_renders_complete_stored_requirement_beside_one_question` — asserts CLI output includes every required stored disclosure fact beside the question.
- `test_review_result_renders_repeated_relation_occurrences_in_stored_order` — asserts the deterministic CLI disclosure does not collapse repeated relation atoms.
- `test_cli_gate_clean_inventory_remains_promotable` — asserts the existing gate-clean CLI lifecycle remains compatible through review, answer, seal, and promotion.

Green-before-done gate: every listed case, `uv run pytest tests/test_roadmap_candidate_review.py -q`, `uv run pytest tests/cli/test_roadmap_cmd.py -q`, and `uv run pytest tests/ -q -n auto` must pass.

## Acceptance criteria

- A review-required stored initial candidate creates one `CandidateQuestionInventory` bound to its exact stored requirement.
- Requirement substitution, removal, or mutation makes the inventory invalid.
- Gate-clean inventories omit the requirement and retain their existing canonical bytes and identities.
- The prompt receives the complete stored requirement while model output remains limited to one anchor and opaque question text.
- `_render_candidate_review_result` deterministically renders the complete stored requirement, including repeated relation occurrences, beside that question.
- Replaying a valid inventory makes no backend call and does not rewrite the record.
- An invalid inventory refuses without regeneration or replacement.
- Opaque reviewer answers and existing gate-clean promotion behavior remain compatible.
- The focused and full test commands pass.

## References

- [Configuration | Pydantic Docshttps: — Use frozen, strict, extra-forbid models for immutable records.
- [Validators | Pydantic Docshttps: — Review cross-field validation for inventory and stored-evidence bindings.
- [Serialization | Pydantic Docshttps: — Review deterministic model serialization and round-tripping.
- [json — JSON encoder and decoderhttps: — Review canonical JSON inputs for persisted identities.
- [hashlib — Secure hashes and message digestshttps: — Review SHA-256 identity binding.
- [RFC 8785: JSON Canonicalization Schemehttps: — Reference stable structured encodings for content-addressed evidence.
- [How to parametrize fixtures and test functionshttps: — Build focused valid, compatibility, and tamper matrices.

## Applicable guardrails

- **The plan’s “## Scope guardrails”, single selected-feedback request:** keep the requirement inside the existing inventory and question exchange; do not add another feedback, question, command, or transport.
- **The plan’s “## Scope guardrails”, binary observable:** expose an inventory only when stored initial evidence carries a valid bounded requirement.
- **The plan’s “## Scope guardrails”, validator limits:** validate typed bindings only; do not judge prose quality, desirability, or answer meaning.
- **The plan’s “## Scope guardrails”, existing outcome policy:** retain current question outcomes and exit-code behavior.
- **The plan’s “## Scope guardrails”, no approval framework:** retain one typed requirement record without a registry or extension mechanism.
- **The plan’s “## Scope guardrails”, accepted-head authority:** keep inventories and answers inert; this step must not change promotion or accepted roadmap artifacts.

## Deferred

- `plan_tool/roadmap_candidate_review.py:request_replacement`, `_replacement_capsule`, and `_store_replacement` — step 4 owns replacement containment, staleness, and the review-required initial-capsule boundary.
- Additional review-required reasons or a general policy framework — require separate evidence and plan scope.
