> **Auto-archived**: this plan was swept on 2026-11-05 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 8 — Bind candidate questions, answers, rejection, and discard resolution to the exact active-candidate batch

<!-- plan-tool:detail-format-version: 1 -->

## Summary

Update `plan_tool/roadmap_candidate_review.py` and `plan_tool/prompts/roadmap-candidate-questions.md` so review questions and answers bind the exact active candidate, its root/source processing pair, and its immutable batch evidence. Extend `tests/test_roadmap_candidate_review.py` for batch-bound review, replacement, rejection, and explicit discard behavior. The key decision is that review activity reads stored candidate evidence only and releases an active candidate only through the existing guarded publication boundary. On green, a changed pointer, candidate, batch, or answer cannot inherit an earlier review action, while rejected and discarded candidates remain immutable history.

## Table of Contents

- [Summary](#summary) — The completed review and lifecycle outcome.
- [Table of Contents](#table-of-contents) — Links to every section in this file.
- [Why](#why) — Why the single-candidate review records cannot safely review a batch.
- [Input](#input) — Upstream candidate and batch contracts this step consumes.
- [Files (creates vs edits)](#files-creates-vs-edits) — The scoped production, prompt, and test changes.
- [Implementation](#implementation) — Batch binding, replacement, rejection, and discard rules.
- [Tests](#tests) — Focused lifecycle and refusal coverage.
- [Acceptance criteria](#acceptance-criteria) — Observable completion conditions.
- [References](#references) — Validation, canonical JSON, hashing, and durable-publication references.
- [Applicable guardrails](#applicable-guardrails) — Boundaries that constrain review work.
- [Deferred](#deferred) — Adjacent work owned by later steps.

## Why

`plan_tool/roadmap_candidate_review.py` currently stores one question inventory, answer, replacement, and seal around the selector-bound `CandidateProposalAdmission` and `StoredCandidateProposal` contracts. Step 5 instead supplies one root-bound active candidate with immutable batch evidence, so review must prove that every question, answer, replacement, rejection, and discard action targets that exact current candidate rather than later ledger state or a changed processing pair.

## Input

- **Only the seal, which rewrites the ledger, rechecks migration readiness.** Question generation, answers, replacement storage, rejection, and discard call no `check_ledger_processing_ready`: an active candidate can exist only after step 5's storage path admits one, and step 5 (via step 3) already refuses that admission for a `migration-pending` roadmap. The ledger is nevertheless reviewer-editable, so a hand-set `migration-pending` state is reachable while a candidate is active. `_publish_batch_seal` therefore keeps one `check_ledger_processing_ready` call and refuses `migration-required` before writing, as every other ledger-writing publication does; the other review actions never write the ledger.

- **Step 4 batch response:** Consume the landed batch-aware candidate materialization and response-patch evidence from `plan_tool/roadmap_candidate.py`. Step 4 owns the closed response contract and feedback-free successor semantics.

- **Step 5 active-candidate state:** Consume the landed root/source-bound active pointer, immutable candidate evidence, batch identity, supersession facts, the shared `CandidateTerminalResolution` record, and guarded publication helpers from `plan_tool/roadmap_candidate_run.py`. The landed record names and fields win over names suggested in this detail.

- **Existing review boundary:** Evolve `plan_tool/roadmap_candidate_review.py:CandidateQuestionInventory`, `CandidateReviewAnswer`, `CandidateReviewReplacement`, `CandidateReviewSeal`, `generate_candidate_question`, `record_reviewer_answer`, `request_replacement`, and `seal_review` rather than retaining a parallel review store.

- **Prompt inputs:** Continue loading `plan_tool/prompts/roadmap-candidate-questions.md` through `plan_tool/renderer.py:prompts_dir` in `plan_tool/roadmap_candidate_review.py:render_candidate_question_prompt`. The prompt receives stored evidence only; tests with canned responses prove the contract is satisfiable, not real-model hit rate.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `plan_tool/roadmap_candidate_review.py` — Replace initial-candidate and single-feedback review bindings with active-candidate batch bindings; add terminal rejection and discard resolution through guarded publication.
  - `plan_tool/prompts/roadmap-candidate-questions.md` — Ask for one closed question against supplied immutable active-candidate batch facts.
  - `tests/test_roadmap_candidate_review.py` — Replace selector-bound fixtures and add batch, replacement, rejection, discard, stale-pointer, and no-write coverage.

## Implementation

- **Bind every review record to the active candidate’s immutable evidence.** Extend the record validation around `CandidateQuestionInventory`, `CandidateReviewAnswer`, `CandidateAnswerIncorporation`, `CandidateReviewReplacement`, and `CandidateReviewSeal` so their identities cover the reviewed candidate and its stored root, original batch source, batch identity, admitted reviewer snapshots, and derived context. Do not rebuild these facts from the live ledger.

- **Make the reviewed candidate’s source the replacement’s predecessor.** A sealed replacement applies its delta to the reviewed candidate’s own source, using the reviewed candidate’s stored batch capsule, and records that source as its direct predecessor. Its review evidence and seal bind the reviewed candidate’s root, source, and batch identity, and its binding record names the reviewed candidate, so neither identity can be substituted. The reviewed candidate cannot be the predecessor: that would need a capsule built from the live ledger, whose admitted items are already `awaiting-review`, and it would put the replacement two records from the root. Decided 2026-09-23 by the user; do not re-open.

- **Select only the current active candidate.** Replace the selector-bound admission loading in `_load_admitted_initial_candidate`, `_load_admitted_initial_candidate_from_admission`, and `_validate_initial_candidate` with validation against step 5’s active pointer and stored candidate evidence. A review request, answer, replacement, seal, rejection, or discard must refuse before a model call or write when the pointer, root, candidate id, source ancestry, or batch binding does not match.

- **Refuse review commands about a sealed candidate.** Review acts only on the active candidate. Once the seal has swapped the pointer to the replacement, a replayed seal, answer, or question command for the reviewed candidate refuses before any model call or write.

- **Keep questions closed and batch-scoped.** Update `render_candidate_question_prompt`, `parse_candidate_question_response`, `_parse_question_anchor`, and `_anchor_resolves` to expose only immutable facts from the reviewed candidate’s stored batch. The prompt may let a question identify an admitted reviewer item, derived-context row, changed row, closure member, or supplied inventory identity only when that target appears in the stored batch. A batch question cannot anchor on a response: the receipt's snapshots are taken at admission and carry no proposal, and the candidate's evidence retains no response text. The prompt therefore does not offer a `response` anchor, and `_parse_question_anchor` refuses one with an explicit reason. Do not grant edit or replacement authority merely by naming an inventory item. A selector-era candidate accepts only `feedback`, `diff-row`, `full-member`, and `inventory` anchors; `reviewer-item`, `response`, and `derived-context` anchors resolve only against a batch receipt and never fall through to an inventory lookup.

- **Keep answers opaque but exact.** Preserve `CandidateReviewAnswer` as reviewer text rather than model-interpreted state. An answer must bind one stored question inventory and question id, and a replay may succeed only when it supplies the same exact stored answer. A different answer, inventory id, or question id must refuse without replacing the earlier answer.

- **Create one focused sealed replacement path in two publications.** `request_replacement` (through `_store_batch_replacement`) stores the replacement immutably in one generation: its version members, its review evidence, its own candidate evidence (so the active pointer can later name it and the next batch, rejection, discard, and settlement can load it), and the binding record under the reviewed candidate. It leaves the active pointer on the reviewed candidate, so `seal_review` still loads that candidate. `seal_review` (through `_publish_batch_seal`) then publishes one generation carrying the seal, the reviewed candidate’s supersession record, the pointer swap to the replacement, and a ledger patch, so a crash cannot leave a seal without an active replacement. The ledger patch changes only items still `awaiting-review` on the reviewed candidate whose reviewer-owned fields still match the admitted snapshot: each takes the replacement’s response text and the replacement’s candidate id as its proposal binding (`ProposalFields.candidate_version_id`, the field that records which stored candidate produced a proposal). It also appends the replacement’s own derived set, keyed by the replacement’s id. An item the reviewer reopened, edited, closed, or deferred keeps exactly what the reviewer left. Do not recheck live ledger eligibility or otherwise mutate reviewer-owned input; the seal publication rechecks the pointer and the exact ledger bytes inside its window. The response-text rule was decided 2026-09-23 by the user: the replacement’s responses replace the text, because the replacement’s identity binds them.

- **Resolve rejection and discard using the shared terminal-resolution record.** Consume step 5's `CandidateTerminalResolution` record for the two permitted release paths this step triggers: review rejection (`reason: rejected`) and explicit discard (`reason: discarded`). Do not define a second terminal-resolution record in `plan_tool/roadmap_candidate_review.py`. Each resolution must identify the exact active candidate and processing pair it releases. Under `roadmap_writer_guard` and `publish_roadmap_generation`, recheck that binding, record the terminal resolution, and clear the active pointer in one publication. Keep the released candidate, its batch, questions, answers, proposals, and prior evidence readable as stale history.

- **Preserve unrelated reviewer state.** Rejection and discard must not alter ledger bytes, reviewer items, proposal text, accepted-head state, or immutable candidate records. The resulting active-source selection must return to the accepted root’s derived set rather than retaining context from the released candidate.

- **Keep model-facing prompt authority narrow.** Update `plan_tool/prompts/roadmap-candidate-questions.md` to name the active candidate and supplied batch facts as the complete authority. It must prohibit repository inspection, live-ledger reads, accepted-head discovery, promotion instructions, and fields outside the closed JSON response. Keep every `${...}` placeholder supplied by `render_candidate_question_prompt`, and escape any literal dollar sign for `string.Template`.

- **Reuse the existing transaction owner.** Use `plan_tool/roadmap_revision_publish.py:roadmap_writer_guard` and `publish_roadmap_generation` for every review record that changes visible lifecycle state. Do not add a review-specific lock, pointer store, version chain, or accepted-head writer.

## Tests

### Tests for this step

- `test_question_inventory_binds_the_exact_active_candidate_batch` — A generated question inventory records the active candidate, root, original source, batch identity, and immutable batch facts.

- `test_question_prompt_exposes_only_stored_active_candidate_batch_facts` — The rendered prompt contains supplied batch evidence and excludes live-ledger, repository, and accepted-head discovery instructions.

- `test_question_anchor_must_resolve_inside_the_stored_batch` — A valid admitted-batch anchor stores, while an anchor from a different candidate, later batch, or unrelated inventory refuses.
- `test_batch_question_prompt_offers_no_response_anchor_and_keeps_the_others`, `test_batch_question_anchored_on_a_response_is_refused_with_the_explicit_reason`, and `test_batch_response_anchor_never_resolves_even_when_a_receipt_snapshot_carries_a_proposal` — assert the batch prompt omits the `response` anchor, a `response` anchor is refused with its own reason, and no receipt snapshot can make one resolve.
- `test_batch_only_anchor_kinds_never_resolve_for_a_selector_era_candidate` — asserts a `reviewer-item`, `response`, or `derived-context` anchor does not resolve on a selector-era candidate even when its row identity matches an inventory entry.

- `test_replayed_question_for_unchanged_active_candidate_does_not_invoke` — An exact stored inventory replays without a backend call or rewrite.

- `test_question_generation_refuses_changed_active_candidate_before_invocation` — A changed root/active pointer or batch binding blocks question generation without invoking the model.

- `test_answer_binds_exact_question_inventory_and_replays_only_exact_text` — The same answer replays, while a changed answer, question id, or inventory id refuses without replacing stored evidence.

- `test_batch_replacement_materializes_from_the_reviewed_source_and_binds_root_source_and_batch` — A stored replacement’s predecessor is the reviewed candidate’s source and its evidence binds the reviewed candidate’s root, source, and batch identity; the pointer and ledger stay untouched until the seal.

- `test_batch_replacement_replays_without_a_model_call_and_refuses_a_different_answer` — An exact stored replacement replays without a backend call; a different answer refuses.

- `test_a_stored_batch_replacement_that_disagrees_with_its_reviewed_candidate_is_refused_on_replay` and `test_a_replacement_whose_own_candidate_evidence_carries_a_different_capsule_is_refused_on_replay` — A stored replacement whose root, batch, initial candidate, response patch, diff, or own candidate evidence disagrees with the reviewed candidate refuses on replay.

- `test_replacement_refuses_when_the_active_pointer_changes_before_storage` and `test_replacement_publish_rechecks_the_pointer_after_the_pre_storage_check` — Pointer drift after the answer is stored, including drift inside the publication window, prevents replacement publication and preserves existing state.

- `test_sealed_batch_replacement_atomically_swaps_the_pointer_and_records_supersession` — The seal, the supersession record, the pointer swap, and the ledger patch become visible in one generation; the reviewed candidate’s stored bytes stay unchanged.

- `test_seal_refuses_when_the_ledger_changes_inside_the_publication_window` — A ledger edit between the seal’s read and its publication refuses without writing.

- `test_seal_refuses_a_ledger_that_became_migration_pending_and_writes_nothing` — A hand-set `migration-pending` ledger refuses the seal with `migration-required` and writes nothing.

- `test_a_sealed_active_replacement_is_loadable_by_the_next_batch_and_by_rejection` — The active replacement can be the source of the next batch and can be rejected.

- `test_review_commands_for_a_sealed_candidate_refuse_once_the_replacement_is_active` — A replayed seal or answer for the reviewed candidate refuses before invoking a model.

- `test_sealing_rebinds_awaiting_review_proposals_to_the_replacement_and_publishes_its_derived_set` — Sealing gives each item still `awaiting-review` on the reviewed candidate the replacement’s response text and candidate id, leaves its request and target unchanged, and appends the replacement’s derived set.

- `test_sealing_leaves_an_item_the_reviewer_reopened_between_replacement_and_seal_untouched` and `test_replacement_ledger_patch_rebinds_only_an_item_still_awaiting_review_on_the_reviewed_candidate` — An item that is not `awaiting-review` on the reviewed candidate with unchanged reviewer-owned fields is left exactly as the reviewer left it.

- `test_review_rejection_and_discard_record_the_exact_resolution_and_release_only_the_matching_pointer` — Rejection and discard each write one terminal record naming the exact candidate, root, source, batch, and reason, and clear only the matching active pointer in one generation; the accepted root is again the processing source.

- `test_explicit_discard_records_exact_resolution_and_releases_active_candidate` — Discard follows the same guarded release rule without requiring question or answer generation.

- `test_rejection_and_discard_refuse_stale_candidate_without_writes` — A supplied candidate that is no longer active cannot release a newer pointer or write a terminal resolution.

- `test_rejection_and_discard_preserve_ledger_and_candidate_history` — Both release paths leave reviewer input, accepted-head state, candidate bytes, and stored proposals unchanged.

- `test_candidate_review_prompt_placeholders_match_renderer_variables` — Every placeholder in `plan_tool/prompts/roadmap-candidate-questions.md` is supplied by the renderer and no unresolved placeholder remains.

Every test in `tests/test_roadmap_candidate_review.py` must be green before this step is complete.

## Acceptance criteria

- A question inventory, answer, replacement, and seal each prove the exact reviewed active candidate and its immutable root/source/batch evidence.

- A batch question can anchor on an admitted reviewer item, a derived-context row, a changed row, a closure member, or an inventory identity, and is refused with its own reason when it anchors on a response.

- A review action refuses before model invocation or publication when the active pointer, root, reviewed candidate, source ancestry, or batch binding differs from its stored evidence.

- A sealed replacement uses the reviewed candidate’s source as its predecessor and binds the reviewed candidate’s root, source, and batch identity.

- A sealed replacement atomically becomes the active candidate, with a supersession record for the reviewed candidate, and stores a fresh derived set for its own revision.

- A sealed replacement gives the reviewed candidate’s `awaiting-review` items the replacement’s response text and candidate id without altering their reviewer-owned request or target fields; an item the reviewer has since changed is left as they left it.

- After the seal, review commands about the sealed candidate refuse.

- Rejection records a terminal rejection resolution and atomically releases only the matching active candidate.

- Explicit discard records a terminal discard resolution and atomically releases only the matching active candidate.

- Rejection and discard leave the accepted head, live ledger, candidate records, proposals, and immutable review evidence unchanged.

- `tests/test_roadmap_candidate_review.py` passes.

## References

- [Pydantic models](https://docs.pydantic.dev/latest/concepts/models/) — Use strict, frozen records and forbidden extra fields for review and resolution evidence.

- [Python json](https://docs.python.org/3.13/library/json.html) — Use stable JSON encoding for exact persisted review identities.

- [RFC 8785: JSON Canonicalization Scheme](https://www.rfc-editor.org/rfc/rfc8785.html) — Read the canonicalization requirements behind reproducible evidence identities.

- [hashlib — Secure hashes and message digests](https://docs.python.org/3.13/library/hashlib.html) — Use SHA-256 over canonical bytes for stored evidence bindings.

- [os.replace](https://docs.python.org/3.13/library/os.html#os.replace) — Read the atomic replacement behavior used by durable publication.

- [fcntl](https://docs.python.org/3/library/fcntl.html) — Read advisory-lock behavior relevant to the existing writer guard.

## Applicable guardrails

- **The plan’s “## Scope guardrails”, immutable batch binding:** `plan_tool/roadmap_candidate_review.py` must use stored candidate evidence and must not substitute later ledger items, responses, target facts, or derived context.

- **The plan’s “## Scope guardrails”, writer ownership:** Review records, replacements, rejection, and discard must use the existing writer guard and publication boundary; this step must not add independent lifecycle or accepted-head authority.

- **The plan’s “## Scope guardrails”, unrelated ledger edits:** A review path must not use the whole-ledger digest as an equality precondition or consume reviewer items outside its admitted batch.

- **The plan’s “## Out of scope”, focused lifecycle extensions:** This step may implement only the focused replacement, rejection, and discard behavior, not a general review workflow or automatic feedback retargeting.

- **The plan’s “## Out of scope”, candidate branching:** The active pointer remains the sole candidate selector for one accepted root; this step must not create concurrent branches.

## Deferred

- CLI flags and command dispatch for review rejection and explicit discard — Step 10 owns the public command surface and its compatibility checks.

- Promotion of a sealed replacement — Step 9 owns accepted-head advancement and must consume this step’s exact seal and active-candidate binding.
