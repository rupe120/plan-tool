> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 3 — Bind the exact requirement into the one question inventory while keeping question records create-only

## Summary

Extend `plan_tool/roadmap_candidate_review.py` so the existing `CandidateQuestionInventory` retains the exact review requirement stored by step 2. Update the question prompt in `plan_tool/prompts/roadmap-candidate-questions.md` to show that complete stored requirement without changing the closed model response shape. Keep the question identity and opaque answer contract unchanged; bind the requirement through the inventory identity instead. On green, a review-required initial candidate creates or replays one immutable inventory that proves which requirement its question covers.

## Table of Contents

- [Summary](#summary) — The step’s result and main design choice.
- [Table of Contents](#table-of-contents) — Links to each section.
- [Why](#why) — The missing binding between stored requirement and review.
- [Input](#input) — Stored candidate and question-record contracts.
- [Files (creates vs edits)](#files-creates-vs-edits) — The three files this step edits.
- [Implementation](#implementation) — Requirement binding, prompt, and create-only rules.
- [Tests](#tests) — Focused coverage for the one-question boundary.
- [Acceptance criteria](#acceptance-criteria) — Observable completion conditions.
- [References](#references) — Immutable-record and canonical-serialization references.
- [Applicable guardrails](#applicable-guardrails) — Plan boundaries for this review change.
- [Deferred](#deferred) — Replacement containment and broader policy work left later.

## Why

Step 2 makes an exact review requirement available on validated stored initial-candidate evidence, but `plan_tool/roadmap_candidate_review.py:CandidateQuestionInventory`, `_new_question_inventory`, and `render_candidate_question_prompt` currently bind and show only the candidate’s existing facts. Without adding the requirement to the immutable inventory, the one question can be replayed without proving the policy impact it covers. The requirement must become part of the existing inventory at creation time so a later answer remains bound through `inventory_id` without giving opaque answer text approval meaning.

## Input

- **Step 2 stored result:** step 2 extends `plan_tool/roadmap_candidate_run.py:CandidateProposalEvidence` so a validated `StoredCandidateProposal` carries either the exact immutable review requirement or the existing gate-clean state with none.
- **Question record contract:** `plan_tool/roadmap_candidate_review.py:CandidateQuestionInventory`, `_inventory_preimage`, `render_question_inventory`, and `parse_question_inventory` define the canonical immutable inventory record.
- **Question lifecycle:** `plan_tool/roadmap_candidate_review.py:generate_candidate_question`, `_load_question_inventory_if_present`, `_validate_inventory`, and `_publish_new_record` own replay, validation, and one-time publication.
- **Answer boundary:** `plan_tool/roadmap_candidate_review.py:CandidateReviewAnswer`, `_new_answer`, and `record_reviewer_answer` bind an answer to the inventory and question IDs while leaving answer text opaque.
- **Prompt contract:** `plan_tool/roadmap_candidate_review.py:render_candidate_question_prompt` supplies stored facts to `plan_tool/prompts/roadmap-candidate-questions.md`; `parse_candidate_question_response` continues to accept only an anchor and question.

## Files (creates vs edits)

- **New files:** none.

- **Existing files (edits only):**
  - `plan_tool/roadmap_candidate_review.py` — bind the stored requirement into the inventory, its identity validation, replay validation, and prompt variables.
  - `plan_tool/cli/roadmap_cmd.py` — render the stored requirement facts beside the one stored question.
  - `plan_tool/prompts/roadmap-candidate-questions.md` — show the complete stored requirement and restate its non-authorizing role.
  - `tests/test_roadmap_candidate_review.py` — add review-required inventory, prompt, replay, tamper, and opaque-answer coverage.
  - `tests/cli/test_roadmap_cmd.py` — cover deterministic review-result rendering.

## Implementation

- **Foundational logic:** bind the validated initial review requirement into the one immutable question inventory and its canonical identity.

- **Mirror the stored candidate state exactly.** Extend `CandidateQuestionInventory` and `_new_question_inventory` to retain the requirement supplied by the stored initial candidate. A review-required candidate must carry its exact requirement; a gate-clean candidate must not gain a synthetic requirement.

- **Include the requirement in the inventory identity.** Update `_inventory_preimage` and `CandidateQuestionInventory._requires_exact_identity` so the inventory ID changes when any bound requirement fact changes. Keep `CandidateQuestion.question_id` bound only to its existing anchor and opaque question text.

- **Preserve old gate-clean inventories exactly.** An absent requirement in a pre-change gate-clean inventory remains valid and its preimage omits that field; a new gate-clean inventory uses the same omission. Only a review-required inventory includes the requirement in its preimage and identity.

- **Validate on every read.** Update `_validate_inventory` to compare the inventory’s requirement state with `initial.evidence` as well as its existing predecessor, feedback, diff, capsule, and anchor bindings. A missing, substituted, or mismatched requirement must fail closed before an answer or replacement can consume the inventory.

- **Keep records create-only.** Preserve `generate_candidate_question`’s load-before-invoke order and `_publish_new_record`’s collision refusal. If an inventory already exists, validate and replay it with no model call; if it is malformed or no longer binds the stored candidate, refuse without regenerating or replacing its bytes.

- **Show the full stored requirement in the existing prompt.** Update `render_candidate_question_prompt` and `plan_tool/prompts/roadmap-candidate-questions.md` together so the template receives canonical structured requirement facts, not only an impact identity. The prompt must continue to use stored candidate evidence only.

- **Render the same facts deterministically to the reviewer.** Update `plan_tool/cli/roadmap_cmd.py:_render_candidate_review_result` to print the stored requirement's reason, affected facts, normalized operations, complete diff, and identity alongside the existing one question. Treat model-written question text as opaque; it cannot be the sole disclosure channel.

- **Keep the response and answer contracts closed.** `parse_candidate_question_response` must continue to accept exactly `anchor` and `question`. Do not add a requirement selector, approval field, or semantic interpretation to `CandidateReviewAnswer`, `_new_answer`, or `record_reviewer_answer`; blank and arbitrary answer text remain valid opaque guidance.

- **Reuse downstream readers unchanged.** `plan_tool/roadmap_version_promotion.py:_load_question_inventory` already consumes the canonical inventory through `parse_question_inventory`; this step does not change promotion behavior or add a second validation path there.

## Tests

### Tests for this step

- `test_review_required_question_inventory_binds_the_exact_stored_requirement` — a stored review-required candidate creates one inventory containing the same requirement facts and immutable identity as its evidence.
- `test_review_required_question_prompt_contains_complete_stored_requirement` — the captured prompt contains the complete stored requirement while excluding live repository and brief data.
- `test_question_response_schema_stays_anchor_and_question_only_with_requirement_context` — a requirement-bearing prompt still accepts only one resolvable anchor and opaque question text.
- `test_gate_clean_question_inventory_has_no_review_requirement` — the existing gate-clean path creates an inventory without a review-required state.
- `test_pre_change_gate_clean_inventory_replays_with_existing_identity` — an inventory fixture without a requirement field remains valid through answer, replacement, seal, and promotion.
- `test_review_required_question_inventory_replay_does_not_invoke_or_rewrite` — a valid existing inventory returns with zero backend calls and unchanged stored bytes.
- `test_question_inventory_requirement_tampering_refuses_without_invocation_or_rewrite` — missing or changed requirement evidence rejects before invocation and preserves the existing inventory file.
- `test_reviewer_answer_remains_opaque_with_a_bound_review_requirement` — blank and arbitrary answer text stay valid while the answer remains bound through the requirement-bearing inventory ID.
- `test_review_result_renders_complete_stored_requirement_beside_one_question` — CLI output deterministically includes every stored disclosure fact even when the model question omits them.

Green-before-done gate: every listed case, `uv run pytest tests/test_roadmap_candidate_review.py -q`, and `uv run pytest tests/ -q -n auto` must pass.

## Acceptance criteria

- A review-required stored initial candidate creates one `CandidateQuestionInventory` that binds its exact stored requirement.
- The inventory identity rejects a changed, missing, or substituted requirement.
- Existing gate-clean inventories without the new field retain their identity and replay behavior.
- The question prompt contains the complete stored requirement while its model response remains limited to an anchor and opaque question.
- The existing review result deterministically renders the complete stored requirement beside that one question.
- Replaying a valid inventory makes no backend call and does not rewrite its record.
- A malformed or mismatched existing inventory refuses without replacement or regeneration.
- Gate-clean question generation and opaque reviewer answers remain compatible.
- `tests/test_roadmap_candidate_review.py` and the plan test command pass.

## References

- [Configuration | Pydantic Docs](https://docs.pydantic.dev/latest/api/config/) — Use frozen, strict, extra-forbid settings for immutable question records.
- [Validators | Pydantic Docs](https://docs.pydantic.dev/latest/concepts/validators/) — Use model validation for inventory and stored-evidence bindings.
- [Serialization | Pydantic Docs](https://docs.pydantic.dev/latest/concepts/serialization/) — Review deterministic model serialization and round-tripping.
- [json — JSON encoder and decoder](https://docs.python.org/3.13/library/json.html) — Review canonical JSON inputs for immutable record identities.
- [hashlib — Secure hashes and message digests](https://docs.python.org/3.13/library/hashlib.html) — Review SHA-256 identity binding.
- [RFC 8785: JSON Canonicalization Scheme](https://www.rfc-editor.org/rfc/rfc8785.html) — Use as the reference model for stable structured identity inputs.
- [How to parametrize fixtures and test functions](https://docs.pytest.org/en/stable/how-to/parametrize.html) — Use focused valid, replay, and tamper matrices.

## Applicable guardrails

- **The plan’s “## Scope guardrails”, single selected-feedback request:** keep the requirement inside the existing inventory and question flow; do not add another feedback, question, command, or transport surface.
- **The plan’s “## Scope guardrails”, binary observable:** bind only a requirement that step 2 validated from stored initial-candidate evidence; invalid evidence must expose no usable inventory.
- **The plan’s “## Scope guardrails”, validator limits:** validate typed identities and bindings only; do not judge prose quality, desirability, or answer meaning.
- **The plan’s “## Scope guardrails”, no new outcome policy:** preserve current question outcomes and exit behavior.
- **The plan’s “## Scope guardrails”, no generic approval framework:** retain one typed stored requirement rather than adding policy registration or extensibility.
- **The plan’s “## Scope guardrails”, accepted-head authority:** keep question and answer records inert; this step must not alter promotion or accepted roadmap artifacts.

## Deferred

- `plan_tool/roadmap_candidate_review.py:request_replacement`, `_replacement_capsule`, and `_store_replacement` — step 4 owns replacement-impact containment and the review-required initial-capsule boundary.
- Additional review-required reasons or a general policy framework — require separate evidence and plan scope.
