> **Withdrawn 2026-09-22** — Superseded 2026-09-22: feedback moves to a roadmap-scoped mutable ledger; artifact versions retain no embedded mutable feedback.
> Preserved here for history; do not edit.

# Step 5 — Bind review questions and answers to the exact batch while preserving journaled review-state replacements

<!-- plan-tool:detail-format-version: 1 -->

## Summary

Update `plan_tool/roadmap_candidate_review.py` so its question inventory, stored answer, replacement evidence, binding, and seal carry the complete immutable feedback batch from steps 2 and 3. Update `plan_tool/prompts/roadmap-candidate-questions.md` to present the stored batch, not a singular selected-feedback fact. Keep the existing journal-backed review replacement publication path intact. On green, a question-and-answer lineage cannot be reused for a different predecessor or feedback batch, and replay or recovery retains its exact stored review state.

## Table of Contents

- [Summary](#summary) — Reviewer overview of the batch-bound review change.
- [Table of Contents](#table-of-contents) — Links to this detail’s sections.
- [Why](#why) — Why singular review bindings can drift after batch admission.
- [Input](#input) — Immutable batch, candidate, and publication contracts this step consumes.
- [Files (creates vs edits)](#files-creates-vs-edits) — Scoped review, prompt, and test changes.
- [Implementation](#implementation) — Batch identity propagation and journal-preserving replacement rules.
- [Tests](#tests) — Focused coverage for review lineage and replacement recovery.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Lifecycle and persistence contracts to consult.
- [Applicable guardrails](#applicable-guardrails) — Authority and scope boundaries for review work.
- [Deferred](#deferred) — Work intentionally left to later steps.

## Why

`plan_tool/roadmap_candidate_review.py` currently records `CandidateContextFeedback` through `CandidateQuestionInventory`, `CandidateReviewReplacement`, and `CandidateReviewSeal`, which represents one selected row rather than the generation-wide batch admitted by steps 2 and 3. Without carrying the upstream batch identity through every review record and validation replay, a stored question, answer, or replacement could appear valid while describing a different feedback inventory than the candidate it is meant to review.

## Input

- **Step 2 batch-aware candidate:** Consume the complete successor evidence and its feedback-batch binding from `plan_tool/roadmap_candidate.py:materialize_candidate()`. This step must not rebuild eligibility or redefine typed candidate operations.

- **Step 3 generation-scoped admission:** Resolve the admitted initial candidate through `plan_tool/roadmap_candidate_run.py:load_candidate_admission()` and `plan_tool/roadmap_candidate_run.py:load_stored_candidate_proposal()`. Its accepted predecessor and batch identity are review inputs, not live values to rediscover.

- **Existing review records:** Adapt `CandidateQuestionInventory`, `CandidateReviewAnswer`, `CandidateAnswerIncorporation`, `CandidateReviewReplacementBinding`, `CandidateReviewReplacement`, and `CandidateReviewSeal` together so their closed identities continue to cover every fact their validation helpers require.

- **Publication recovery:** Retain `plan_tool/roadmap_revision_publish.py:publish_roadmap_generation()` as the owner of durable replacement publication and recovery. The review module supplies its replacement members; it must not introduce a parallel journal or direct multi-file write path.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `plan_tool/roadmap_candidate_review.py` — Carry the admitted feedback batch through review records, prompt rendering, replacement materialization, validation, and seal construction while retaining journal-backed replacement publication.
  - `plan_tool/prompts/roadmap-candidate-questions.md` — Describe the complete stored batch as the question authority and remove singular-selector wording.
  - `tests/test_roadmap_candidate_review.py` — Update singular-feedback fixtures and add batch-binding, refusal, replay, and journal-state coverage.

## Implementation

- **Bind every review artifact to the admitted batch.** Replace the singular feedback assumptions in `CandidateQuestionInventory`, `CandidateReviewReplacementState`, `CandidateReviewReplacement`, and their identity preimages with the batch contract supplied by steps 2 and 3. The stored predecessor, candidate identity, batch identity, capsule, receipt, and candidate content facts must remain mutually consistent.

- **Keep the existing review protocol narrow.** Adapt `generate_candidate_question()`, `record_reviewer_answer()`, `request_replacement()`, `answer_candidate_question()`, and `seal_review()` to validate the batch-bound inventory before reuse or publication. Do not turn a complete feedback batch into a new per-row approval, edit, or rejection protocol; opaque reviewer questions and answers remain distinct from promotion authority.

- **Make prompt authority match persisted authority.** Update `render_candidate_question_prompt()` and `plan_tool/prompts/roadmap-candidate-questions.md` so the model receives the complete stored batch and can anchor a question only in facts issued for that candidate. Keep the prompt’s no-live-repository and no-promotion-authority rules. Add a placeholder coverage check so every template variable has a supplied value and rendered output has no unresolved placeholder.

- **Reject drift before model work or state changes.** Update `_validate_initial_candidate()`, `_validate_inventory()`, `_validate_answer()`, `_load_replacement_if_present()`, and `_validate_replacement()` so a changed predecessor, batch membership, member source identity, question inventory, answer, or replacement binding refuses rather than reusing a record from another lineage.

- **Preserve exact replay semantics.** Keep `_new_question_inventory()`, `_new_answer()`, `_review_lineage_identity()`, and `_new_seal()` deterministic over the complete stored facts. Replaying the same question, answer, or replacement must return the matching record; conflicting bytes must refuse and must not create a branch.

- **Keep replacement state journaled.** Retain `_store_replacement()` as the path that assembles version members, replacement evidence, and replacement binding into one `PendingGeneration` for `publish_roadmap_generation()`. Preserve `CandidateReviewReplacementState` as the recorded final-capsule input when the existing expansion route applies; do not overwrite, omit, or bypass it during batch conversion.

- **Retain current-predecessor rechecks.** Keep `_require_review_required_predecessor_is_current()` at the existing write boundaries. Batch binding strengthens lineage evidence but does not replace the current accepted-head check for review-required replacements and seals.

## Tests

- `test_question_inventory_binds_the_complete_admitted_feedback_batch` — A generated inventory records the exact ordered batch and changes identity when a member, source digest, or predecessor changes.

- `test_question_prompt_contains_only_the_stored_batch_authority` — Rendered prompt includes the batch facts and preserves its closed JSON response contract and no-extra-authority wording.

- `test_question_prompt_placeholders_match_render_candidate_question_prompt_variables` — Every placeholder in `plan_tool/prompts/roadmap-candidate-questions.md` is supplied by `render_candidate_question_prompt()`.

- `test_answer_refuses_a_question_inventory_from_a_different_batch` — Recording an answer against a mismatched inventory or question refuses without replacing the stored answer.

- `test_replacement_refuses_before_invocation_when_batch_or_predecessor_drifted` — `request_replacement()` makes no backend call and writes no replacement member when stored review facts do not match the admitted candidate.

- `test_replacement_evidence_and_binding_preserve_the_exact_batch_review_lineage` — A stored replacement, its binding, and its answer incorporation all validate only against the original batch, question, and answer.

- `test_seal_binds_the_exact_batch_bound_replacement` — `seal_review()` refuses a replacement from another batch or predecessor and seals the matching replacement only.

- `test_batch_bound_replacement_replay_returns_the_stored_record` — Exact replay returns the existing replacement and seal without a second model invocation or a new candidate branch.

- `test_batch_bound_replacement_keeps_journaled_replacement_state` — A replacement using the existing final-capsule state retains that state and validates it after journal-backed publication or recovery.

- `test_batch_bound_review_required_recheck_refuses_before_replacement_or_seal_write` — Accepted-head movement leaves prior review records inert and prevents replacement or seal publication.

Every test in `tests/test_roadmap_candidate_review.py` must be green before this step is finished.

## Acceptance criteria

- `CandidateQuestionInventory` and every later review record bind the same admitted predecessor and complete feedback batch as the initial candidate.

- A question prompt identifies the complete stored batch and does not describe one selected feedback row as the review authority.

- A changed batch member, member source identity, predecessor, question inventory, answer, or replacement binding refuses before a replacement or seal is written.

- Exact question, answer, replacement, and seal replay returns the existing immutable record and does not create another review branch.

- Replacement publication continues to use `plan_tool/roadmap_revision_publish.py:publish_roadmap_generation()` with the review-state members required for recovery.

- Existing final-capsule replacement state remains validated when present and is not replaced by a second review-state or journal mechanism.

- `tests/test_roadmap_candidate_review.py` passes.

## References

- [ROADMAP_FORMAT.md](../../../ROADMAP_FORMAT.md) — Read the immutable candidate, review, seal, and accepted-head authority rules.

- [DATA_CONTRACT.md](../../../DATA_CONTRACT.md) — Read persisted-record and durable-publication requirements.

- [docs/how-to/roadmap.md](../../../docs/how-to/roadmap.md) — Read the operator-facing candidate-review workflow.

- [plan_tool/roadmap_candidate_run.py](../../../plan_tool/roadmap_candidate_run.py) — Read generation-scoped admission and stored candidate evidence.

- [plan_tool/roadmap_revision_publish.py](../../../plan_tool/roadmap_revision_publish.py) — Read `publish_roadmap_generation()` and its recovery boundary.

## Applicable guardrails

- **The plan’s “## Scope guardrails”, accepted-head authority** — This step must keep review records inert; it must not move `AcceptedRoadmapHead` or rewrite live roadmap artifacts.

- **The plan’s “## Scope guardrails”, exact batch and predecessor binding** — This step must refuse lineage drift instead of rebuilding a batch from mutable inputs.

- **The plan’s “## Scope guardrails”, reuse existing owners** — Keep the existing version, candidate, review, journal, checkpoint, and recovery owners; do not add another persistence or transaction path.

- **The plan’s “## Out of scope”, review protocol changes** — Do not add feedback states, structural proposal formats, or a new reviewer decision flow while adapting review evidence to the batch.

## Deferred

- Promotion-side validation in `plan_tool/roadmap_version_promotion.py` — Step 6 consumes this step’s batch-bound replacement and seal evidence.

- CLI routing and operator-facing command changes — Step 7 owns selector-free command behavior.

- Reference documentation updates — Step 8 owns the durable workflow and data-contract documentation.
