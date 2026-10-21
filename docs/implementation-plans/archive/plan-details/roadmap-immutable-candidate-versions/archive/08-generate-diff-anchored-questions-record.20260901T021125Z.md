> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 8 — Generate diff-anchored questions, record reviewer answers, and request replacements from the same predecessor

## Summary

Create `plan_tool/roadmap_candidate_review.py` and `plan_tool/prompts/roadmap-candidate-questions.md` as the immutable review boundary for one admitted candidate lineage. The module generates one candidate-bound anchored question, records the reviewer's answer as a separate immutable record, and requests one replacement from the same predecessor and stored lineage capsule. The replacement may spend the still-unused expansion once and then persists the final capsule. Exact answer replay continues or returns that same replacement without changing the answer. On green, the original candidate remains unchanged and a review seal binds the replacement version to its complete question-and-answer lineage.

## Table of Contents

- [Summary](#summary) — The step’s outcome and narrow footprint.
- [Table of Contents](#table-of-contents) — Links to each section.
- [Why](#why) — Why the live revision path cannot supply immutable candidate review.
- [Input](#input) — The candidate, diff, capsule, storage, and backend contracts this step reads.
- [Files (creates vs edits)](#files-creates-vs-edits) — The new review module, prompt, tests, and testing guidance.
- [Implementation](#implementation) — The question, answer, replacement, and seal lifecycle.
- [Tests](#tests) — Hermetic coverage for bindings, refusals, and immutable records.
- [Acceptance criteria](#acceptance-criteria) — Observable conditions for a complete review lineage.
- [References](#references) — Closed-record, JSON, and identity guidance.
- [Applicable guardrails](#applicable-guardrails) — Plan fences that constrain the review route.
- [Deferred](#deferred) — Later CLI, promotion, and broader workflow work.

## Why

`plan_tool/roadmap_revision_run.py:run_local_feedback_revision()` publishes a selected live artifact, and `render_local_revision_prompt()` supplies only that artifact’s bounded context. It cannot show a reviewer a cross-artifact candidate diff, preserve a prior proposal after an answer arrives, or bind approval to the exact replacement the reviewer caused. This step adds that missing immutable review lineage without changing the live revision route.

## Input

- **Initial candidate:** Step 6 supplies a complete gate-clean candidate with one fixed content identity, while step 7 supplies its stored candidate-version identity, selected feedback binding, predecessor identity, complete bytes, raw brief binding, and deterministic diff. Treat that stored candidate version as the only source for question facts.

- **Stored proposal context:** Step 7 supplies the candidate's complete stored capsule and receipt plus its immutable predecessor binding. If that capsule records no expansion, the first answer-driven replacement may spend the lineage's one expansion through step 5 and persist the resulting final capsule. If it already records an expansion, or after answer-driven expansion establishes the final capsule, replacements must reuse that exact stored pair. No replacement may compile a new initial capsule or select the current accepted head.

- **Candidate storage:** Steps 3 and 7 own the shared stored-version namespace and candidate visibility records. Reuse that read and write boundary for replacements rather than creating a second candidate namespace or latest-candidate rule.

- **Strict response precedent:** `plan_tool/roadmap_revision.py:parse_revision_operations()` shows the required single-object JSON handling, including duplicate-key, non-standard-constant, trailing-content, and unknown-field refusal. Mirror that contract shape for questions without extending or importing the live revision types.

- **Prompt and run evidence:** `plan_tool/renderer.py:prompts_dir()` locates packaged prompts. `plan_tool/run_log.py:RunLogWriter.start()`, `RunLogWriter.bind_shell_sink()`, and `RunLogWriter.run_end()` provide the bounded backend evidence seam.

- **What tests prove:** Canned replies can prove that question and replacement contracts bind the intended immutable inputs. They cannot prove that a generated question is useful to a reviewer.

## Files (creates vs edits)

- **New files:**
  - `plan_tool/roadmap_candidate_review.py` — Define immutable question, answer, replacement-lineage, and review-seal records; question and replacement orchestration; strict response handling; and refusal results.
  - `plan_tool/prompts/roadmap-candidate-questions.md` — Define the closed model-facing contracts for generating one anchored question and requesting one answer-informed replacement delta.
  - `tests/test_roadmap_candidate_review.py` — Cover the review lineage, immutable storage, prompt rendering, backend seams, and refusal paths.

- **Existing files (edits only):**
  - `TESTING.md` — Add the candidate-review `invoker=` seam and state how tests keep question and replacement requests hermetic.

## Implementation

- **Foundational logic:** Bind one generated question and one reviewer answer to an immutable candidate lineage, then materialize one replacement from the same predecessor.

- **Keep one narrow review boundary.** Expose small public operations in `plan_tool/roadmap_candidate_review.py`, such as question generation, answer recording, replacement request, and review sealing. Keep CLI parsing and human interaction with step 11; this module accepts already-supplied reviewer text and must not call `input()`.

- **Reuse one closed model-route result contract.** Question generation and replacement return the same four terminal outcomes as the initial proposal: `stored` only after the requested immutable question inventory or replacement candidate is visible; `response-rejected` for a returned response that fails its closed shape, anchor, expansion authority, typed-delta authorization, parse, or gates; `failed` for invocation or persistence failure; and `refused` for deterministic preflight, budget, binding, lineage, or identity-collision rejection. A valid replacement expansion remains an internal continuation rather than a fifth outcome.

- **Keep the same precedence.** Refuse invalid immutable inputs before invoking; report invocation failure when no usable response exists; classify a returned invalid response as `response-rejected`; classify persistence failure as `failed`; and return `stored` only after visibility. `KeyboardInterrupt` remains the existing interrupted path outside this set. Neither question nor replacement processing automatically retries a rejected response.

- **Generate from the fixed candidate, not live state.** Build the question request from the initial candidate's selected feedback, fixed diff, content and version identities, relevant gate facts, and compact identity inventory. Include changed row before/after values and changed relation facts, but do not add unrelated roadmap bytes merely because the candidate is complete.

- **Require one resolvable anchor.** For this plan’s one-question happy path, accept exactly one question object with one typed anchor. The anchor must match the selected feedback identity, a recorded diff item, or an identity already present in the candidate’s immutable facts. Assign the stable question id in deterministic code; do not accept a model-chosen id or a vague prose reference. A malformed or unanchored returned question is `response-rejected`, not `refused`.

- **Keep question text opaque.** Validate the response shape and anchor only. Do not score, trim, require a minimum length for, or otherwise judge whether the question is useful.

- **Write one immutable question inventory.** Store the candidate content and version identities, exact question record, anchor binding, and deterministic inventory identity at one fixed location owned by the admission and initial candidate. Re-entry validates and returns that inventory without another model call; a conflicting inventory or question id refuses rather than creating a sibling question path.

- **Return the persisted comparison as review data.** The review result must carry the stored candidate-version identity, predecessor identity, and persisted deterministic diff beside the question inventory. Step 11 renders those domain-provided facts; neither layer reconstructs a diff from current source artifacts.

- **Record reviewer answers separately and replay exactly.** Bind each answer to the exact question id and question-inventory identity, preserving the supplied string exactly. An answer must not rewrite the question, initial candidate, candidate identities, feedback, or accepted-head state. The first submission creates the answer record. Replaying the same question and byte-identical answer reuses that record and continues or returns its one replacement; different answer bytes, an unknown question, or a mismatched inventory refuse.

- **Use opaque answers, not quality rules.** Require a string and exact lineage binding, but do not use answer length, nonblank content, or wording as a quality check. The answer record is evidence of reviewer input, not a claim that the candidate has interpreted it correctly.

- **Request one replacement from the same lineage.** Send the original feedback, initial candidate diff, question inventory, accumulated reviewer answer records, and the exact stored capsule to the replacement request. Its response may be a typed delta, or—only when the stored capsule is still unexpanded—one request naming an entry from that capsule's compact inventory. A valid answer-driven expansion rebuilds closure through step 5 and persists the expanded capsule and receipt as the lineage's final pair before the one follow-up delta request. An already-expanded lineage, invalid entry, second expansion request, or over-budget expanded capsule refuses without another write. Bind the first visible replacement and seal to the answer identity at a fixed immutable result location; exact answer replay returns them without invoking again. If no result exists after a failed call, exact replay continues from the stored answer and any stored final capsule. Materialize through steps 6 and 7 using the same stored predecessor and selected feedback; do not reread top-level roadmap artifacts, resolve a newer accepted head, or compile a new initial capsule.

- **Preserve the prior candidate and separate content from review identity.** Store an accepted replacement as a new candidate version through step 7's shared storage boundary. Carry the predecessor's exact raw recorded-brief bytes and raw digest into that record unchanged; never derive them from decoded prompt context. Derive its immutable version identity from its materialized content identity, predecessor, selected feedback, exact final capsule and receipt, question inventory, and answer identities. This version identity remains distinct even when the answer-informed delta yields the same candidate bytes and diff as the initial proposal. The initial candidate's bytes, content/version identities, diff, and question inventory remain unchanged, and it must not receive the replacement's review seal.

- **Make answer incorporation mechanical.** Record the answer identities supplied to the replacement request beside the resulting replacement content and version identities. Sealing checks that every recorded question has one immutable answer and that the replacement record binds every answer identity; it must not infer incorporation from wording or compare prose.

- **Seal only the exact completed lineage.** Derive an immutable review-seal identity from the initial candidate version and question inventory, all answer identities, the replacement's answer-bound version identity and content identity, the exact final capsule binding, and the replacement's answer-incorporation record. Refuse missing, substituted, or changed members. Step 9 owns approval and accepted-head movement.

- **Keep model calls bounded and observable.** Use one physical model call to generate the question. The replacement uses one call for a delta, or exactly two when its first response spends the still-unused expansion and the second returns the delta. Provide an injected `invoker=` seam; the production wrapper may follow `plan_tool/roadmap_revision_run.py:shell_local_revision_invoker()` by using `plan_tool/shell.py:claude_invoke()` with transport recovery disabled. Record ids, call counts, expansion use, and terminal outcomes in the run log without recording prompt, question, answer, or response text.

- **Keep the prompt self-contained.** Load `plan_tool/prompts/roadmap-candidate-questions.md` through `plan_tool/renderer.py:prompts_dir()`. State both closed response shapes in the template, including the anchor vocabulary and typed-delta handoff. Do not direct the model to inspect repository files or root-level format documents.

- **Leave live writers separate.** `plan_tool/roadmap_revision_run.py:run_local_feedback_revision()` and `plan_tool/roadmap_revision_patch.py:merge_feedback_revision()` retain their same-artifact live-writer contracts. Do not merge them into this immutable review route.

## Tests

### Tests for this step

- `test_question_generation_uses_only_the_fixed_candidate_diff_feedback_and_identity_inventory` — The prompt includes the selected candidate facts and excludes unrelated roadmap bytes, live artifact changes, and another candidate’s facts.

- `test_question_response_requires_exactly_one_resolvable_feedback_diff_or_identity_anchor` — Missing, unknown, mixed, or unresolvable anchors refuse before a question inventory is stored.

- `test_question_text_is_opaque_to_deterministic_validation` — A structurally valid question record is not rejected because of its wording or length.

- `test_question_inventory_assigns_stable_ids_and_never_overwrites_a_conflict` — Identical immutable inputs yield the same inventory identity, while a conflicting stored record remains unchanged and causes refusal.

- `test_reviewer_answer_is_immutable_and_bound_to_one_exact_question_inventory` — The stored answer retains its supplied bytes and rejects unknown, substituted, or duplicate question bindings.

- `test_reviewer_answer_text_is_not_subject_to_quality_or_length_checks` — A string answer is recorded without content-based validation.

- `test_exact_answer_replay_continues_one_replacement_without_changing_the_answer` — After replacement invocation failure, the same question and byte-identical answer reuse the stored answer and exact lineage inputs; changed answer bytes refuse before invocation.

- `test_replacement_reuses_the_initial_candidate_predecessor_feedback_and_stored_capsule` — The replacement request uses the original immutable inputs even when the accepted head or live roadmap files have changed.

- `test_answer_driven_replacement_may_spend_the_unused_lineage_expansion_once` — An unexpanded stored capsule accepts one valid inventory request, persists the expanded final capsule and receipt, and makes exactly one follow-up delta request.

- `test_replacement_reuses_an_already_final_capsule_and_refuses_another_expansion` — An initially or answer-expanded lineage reuses its exact stored final pair; a later expansion request refuses without another backend call or write.

- `test_reentered_question_and_completed_replacement_return_existing_records` — Re-entering question generation returns the candidate-bound inventory, and replaying an answer after replacement visibility returns the same replacement and seal without another model call.

- `test_answer_informed_replacement_materializes_a_new_gate_clean_candidate_version_without_mutating_the_initial_candidate` — A valid typed delta produces a separate stored replacement while the prior candidate bytes and identities stay unchanged.

- `test_answer_informed_replacement_preserves_the_predecessor_raw_brief_binding` — A replacement inherits the predecessor's byte-identical CRLF brief and raw digest without reading a live brief or re-encoding prompt text.

- `test_unchanged_answer_informed_content_gets_a_distinct_answer_bound_version_identity` — A confirming or otherwise opaque answer may yield the same content identity and diff, but its replacement version remains distinct because it binds the exact question and answer lineage.

- `test_replacement_records_every_answer_identity_passed_to_the_model` — The replacement lineage records all accumulated answer identities as supplied input without inferring prose meaning.

- `test_review_seal_requires_answered_questions_and_exact_answer_incorporation_binding` — A seal is created only for a replacement that binds the complete immutable question-and-answer inventory.

- `test_review_seal_refuses_the_initial_candidate_and_any_substituted_lineage_member` — The prior candidate, changed answer, changed question, or different replacement candidate cannot receive the seal.

- `test_review_result_returns_the_persisted_candidate_identity_and_predecessor_diff` — The domain handoff exposes the stored comparison for step 11 without rereading or reconstructing from live artifacts.

- `test_candidate_review_prompt_has_only_supplied_placeholders_and_no_unresolved_tokens` — The template renders from the review variable map with no unresolved `${...}` values.

- `test_candidate_review_prompt_forbids_repository_browsing_and_canonical_mutation` — The prompt limits model output to an anchored question or typed inert replacement delta.

- `test_candidate_review_invoker_and_run_log_are_bounded_and_redacted` — The injected invoker sees one call per review phase, while the log contains lifecycle facts but no prompt, question, answer, or model-response text.

- `test_question_and_replacement_outcomes_are_closed_and_use_shared_precedence` — Each model-facing review phase covers deterministic refusal, invocation failure, response rejection, persistence failure, and stored success through the shared four-value contract, with valid expansion nonterminal and no automatic retry.

Every named test in `tests/test_roadmap_candidate_review.py` must be green before this step is complete.

## Acceptance criteria

- A stored initial candidate produces one immutable question inventory whose question anchor resolves against its selected feedback, deterministic diff, or recorded identity facts.

- Malformed model output, an unknown anchor, or an inventory collision refuses without changing a candidate, accepted-head selection, or prior review record.

- A reviewer answer creates a separate immutable record bound to one exact question inventory and does not alter candidate, feedback, or question bytes.

- A byte-identical answer replay continues or returns the one answer-bound replacement; different answer bytes refuse, and no new command, automatic retry, or sibling replacement is introduced.

- A replacement request uses the same predecessor, selected feedback, and stored capsule as the initial candidate. It may spend only the lineage's still-unused expansion, stores the resulting final capsule and receipt, and never compiles a new initial context.

- A gate-clean replacement becomes a new answer-bound stored candidate version with the predecessor's exact raw brief binding while every prior candidate remains unchanged; identical candidate content does not collapse distinct answer lineage.

- The review seal binds the exact replacement candidate, initial question inventory, and answer records; an unanswered question, missing incorporation binding, or substituted identity refuses sealing.

- Candidate review processing does not move the accepted head or write canonical roadmap artifacts.

- Question generation and replacement each return exactly `stored`, `response-rejected`, `failed`, or `refused` under the shared precedence, and only `stored` exposes the requested immutable record.

- `TESTING.md` documents the review module’s injected backend seam.

- `tests/test_roadmap_candidate_review.py` passes.

## References

- [Structured outputs - Claude Platform Docs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs) — Use a closed response contract for anchored questions and typed replacement deltas.

- [Configuration | Pydantic Docs](https://docs.pydantic.dev/latest/api/config/) — Use strict, frozen models with forbidden extra fields for review records.

- [json — JSON encoder and decoder](https://docs.python.org/3.13/library/json.html) — Use strict decoding and deterministic JSON rendering for stored review bindings.

- [hashlib — Secure hashes and message digests](https://docs.python.org/3.13/library/hashlib.html) — Bind question inventories, answers, replacements, and seals to exact immutable inputs.

- [RFC 8785: JSON Canonicalization Scheme (JCS)](https://datatracker.ietf.org/doc/html/rfc8785) — Review canonical JSON rules before fixing review-seal identity inputs.

## Applicable guardrails

- **The plan’s “## Plan intent” and step intent** — Build the reviewer-owned clarification path only; do not broaden it into general roadmap editing.

- **The plan’s “## Scope guardrails”, binary observables** — Make question anchors, answer records, candidate identities, replacement bindings, and seals directly inspectable.

- **The plan’s “## Scope guardrails”, allowed behavior changes** — Limit changes to the new candidate-review and answer route; leave existing unversioned behavior alone.

- **The plan’s “## Scope guardrails”, model authority** — Keep model output inert. It may propose a question or delta but cannot answer, seal, promote, or mutate a stored version.

- **The plan’s “## Scope guardrails”, lifecycle order and distinct bindings** — Preserve the ordered review lineage and keep feedback, answers, predecessor, candidate content/version identities, and seal as separate records.

- **The plan’s “## Scope guardrails”, context omission and compact inventory authority** — Permit only the lineage's still-unused recorded expansion, persist the resulting final capsule, reuse that exact pair thereafter, and do not treat compact identity data as edit permission.

- **The plan’s “## Scope guardrails”, validation authority** — Check shapes, counts, ids, anchors, and bindings only; do not judge question, answer, delta, or roadmap prose quality.

- **The plan’s “## Scope guardrails”, smallest functional happy path** — Implement the one-question, one-answer, one-replacement proof without a generic review workflow.

- **The plan’s “## Out of scope”, promotion and workflow expansion** — Do not add automatic promotion, concurrent reviewers, retrieval, or a general document editor.

## Deferred

- **CLI interaction and presentation of review questions** — Step 11 owns command parsing, human-facing output, and the operator workflow.

- **Approval and accepted-head movement** — Step 9 owns approving one immutable review seal and changing canonical version selection.

- **Additional questions, reviewers, branches, or merge handling** — The plan’s representative happy path covers one reviewer answer and one replacement only.

- **More context after the lineage expansion is spent** — A replacement must reuse the stored final capsule; broader context needs a separate design decision.

- **Live same-artifact revision consolidation** — `plan_tool/roadmap_revision_run.py:run_local_feedback_revision()` has a different publication contract, so shared orchestration requires separately scoped refactor work.

- **Question usefulness measurement with a real backend** — This needs real reviewer inputs and a durable observation process outside the hermetic suite.
