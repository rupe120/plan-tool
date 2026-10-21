> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 8 — Generate diff-anchored questions, record reviewer answers, and request replacements from the same predecessor

## Summary

Create `plan_tool/roadmap_candidate_review.py` as the immutable review boundary for one stored candidate lineage, and add `plan_tool/prompts/roadmap-candidate-questions.md` for its closed question response. The module must generate one anchored question from the admitted initial candidate's stored facts, preserve reviewer answers as separate immutable records, and request an answer-informed replacement from the same predecessor and stored capsule. Reuse step 7’s closed candidate-delta contract for replacement responses rather than creating a second delta format. On green, the initial candidate remains unchanged, and a review seal binds only the exact answer-informed replacement and its complete review history.

## Table of Contents

- [Summary](#summary) — The review lifecycle this step adds.
- [Table of Contents](#table-of-contents) — Links to each section.
- [Why](#why) — Why the live revision route cannot support immutable review.
- [Input](#input) — The stored candidate, capsule, and runner contracts this step consumes.
- [Files (creates vs edits)](#files-creates-vs-edits) — New review files and testing guidance update.
- [Implementation](#implementation) — Question, answer, replacement, and seal rules.
- [Tests](#tests) — Focused hermetic coverage for immutable review behavior.
- [Acceptance criteria](#acceptance-criteria) — Observable completion conditions.
- [References](#references) — Closed-response and identity guidance.
- [Applicable guardrails](#applicable-guardrails) — Plan boundaries for this review route.
- [Deferred](#deferred) — Related work left outside this step.

## Why

`plan_tool/roadmap_revision_run.py:run_local_feedback_revision()` and `plan_tool/roadmap_revision_patch.py:merge_feedback_revision()` operate on one live artifact and end at canonical publication. They cannot show a reviewer an immutable cross-artifact diff, preserve the candidate that prompted a question, or bind a replacement to the exact answer that caused it. This step adds that missing review record without changing the existing same-artifact writer.

## Input

- **Stored initial candidate:** Step 6 supplies the complete gate-clean candidate, deterministic predecessor diff, and fixed content identity. Step 7 stores that evidence with its candidate-version identity, selected feedback, predecessor, capsule, and receipt. Read these stored facts rather than current roadmap files.

- **Lineage capsule:** Step 7 persists the issued capsule and receipt for the fixed admitted feedback lineage, including step 5's 64 KiB ceiling. An unexpanded capsule leaves the recorded expansion available to this route; a final capsule must be reused exactly. Review and replacement callers cannot select another ceiling.

- **Candidate storage:** Steps 3 and 7 own immutable candidate records and their shared storage boundary. Store review records and replacements through that boundary; do not introduce a second candidate namespace or a newest-candidate rule.

- **Strict JSON precedent:** `plan_tool/roadmap_revision.py:parse_revision_operations()` and its private single-object decoder show the required duplicate-key, non-standard-constant, trailing-content, and unknown-field refusals. Mirror that strict parsing shape for questions without importing the live revision types.

- **Prompt and observability seams:** Use `plan_tool/renderer.py:prompts_dir()` to locate templates. Follow `plan_tool/roadmap_revision_run.py:shell_local_revision_invoker()` for the injected backend seam, and use `plan_tool/run_log.py:RunLogWriter.start()`, `RunLogWriter.claude_call_start()`, `RunLogWriter.bind_shell_sink()`, and `RunLogWriter.run_end()` for bounded-call evidence.

- **Test limit:** Canned replies prove binding, refusal, and storage behavior. They cannot prove that a model-generated question is useful.

## Files (creates vs edits)

- **New files:**
  - `plan_tool/roadmap_candidate_review.py` — Define immutable question, answer, replacement, and review-seal records; strict response handling; stored-lineage orchestration; and closed terminal results.
  - `plan_tool/prompts/roadmap-candidate-questions.md` — Define the self-contained closed response contract for one anchored question.
  - `tests/test_roadmap_candidate_review.py` — Cover question generation, answer replay, replacement storage, sealing, prompts, and backend isolation.

- **Existing files (edits only):**
  - `TESTING.md` — Add the candidate-review `invoker=` seam to `## Backend fallback seams`, including the fake-response pattern that keeps question and replacement tests hermetic.

## Implementation

- **Foundational logic:** Bind one generated question and one reviewer answer to a stored candidate lineage, then materialize one separate replacement from the same predecessor.

- **Keep one review boundary.** Give `plan_tool/roadmap_candidate_review.py` narrow public operations for generating questions, recording an already-supplied answer, requesting a replacement, and sealing a completed review. Step 11 owns CLI parsing and presentation. This module must not call `input()` or inspect terminal state.

- **Use stored authority only.** Build the question request from the admitted initial candidate version, its persisted diff, original feedback, and stored capsule; build the replacement request from those same facts plus the one stored question-and-answer pair. The question prompt must include the capsule receipt's ordered closure-member identities, inclusion reasons, and declared-relation evidence; it must not substitute live closure or gate results. Do not read top-level artifacts, a live brief, a newer accepted head, directory order, or another candidate to fill missing facts.

- **Accept review entry only for the initial candidate.** Resolve the supplied candidate-version identity through the feedback admission and require its empty initial-review position. Re-entry with that exact initial identity returns or continues its one inventory. A replacement or unrelated candidate identity must return `refused` before a model call or review-record write rather than create or redirect to another inventory.

- **Generate one anchored question.** Accept exactly one closed question object. Its deterministic anchor must identify the selected feedback, an item in the persisted diff, or a resolvable identity supplied in the immutable candidate facts. An inventory identity may anchor a question, but it must not grant edit authority. Assign the question identifier in deterministic code; do not accept a model-selected identifier or positional anchor.

- **Keep question text opaque.** Validate only the closed response shape and anchor binding. Do not score, trim, compare, or use length as a proxy for question quality.

- **Persist one immutable inventory.** Bind the question inventory to the initial candidate version and content identity, predecessor, selected feedback, question record, and anchor facts. Re-entry must validate and return that inventory without another model call. A missing, changed, or conflicting stored inventory must refuse rather than create a sibling question path.

- **Record answers separately and exactly.** Store the supplied answer string unchanged with the exact question identifier and question-inventory identity. The first valid submission creates the immutable answer record. Replaying the same bytes must reuse that record; different bytes, an unknown question, or a mismatched inventory must refuse before a model call. Do not impose nonblank or wording rules.

- **Request the replacement through the existing delta contract.** Resolve the answer through its immutable question inventory, then render step 7's `review_pair` input with the stored question id, anchor, exact opaque question text, answer id, and exact answer text. A missing, changed, or substituted pair member refuses before a model call; do not reconstruct a question from CLI input, current candidate output, or live files. Pass accepted typed deltas to step 6’s materialization boundary. Existing-row replacements must preserve declared relations, and relation-set changes remain limited to consequences of admitted row additions or removals; an answer cannot widen that authority. Do not duplicate the delta response schema in `plan_tool/prompts/roadmap-candidate-questions.md`.

- **Preserve the lineage’s fixed inputs.** A replacement must retain the initial candidate’s accepted predecessor, selected feedback, stored capsule, and its fixed 64 KiB ceiling. When the recorded expansion remains available, a valid inventory request may create and persist the final expanded capsule and receipt under that same module-owned ceiling before one follow-up delta request. Once a final capsule exists, every replay and later replacement attempt must reuse it; no route may compile a new initial capsule or select another limit.

- **Bound calls and retries.** Question generation makes one model call. A replacement makes one call, or two only when a valid first response uses the recorded expansion route and the second returns the delta. Invalid responses, transport failures, materialization failures, and persistence failures must not trigger automatic retries. Exact answer replay may resume only from immutable records already stored for that answer.

- **Store a distinct replacement candidate.** Persist an accepted replacement through the shared version boundary with its predecessor binding, inherited raw brief bytes and digest, complete candidate bytes, content identity, persisted predecessor diff, final capsule and receipt, question inventory, answer identities, and answer-incorporation record. Its candidate-version identity must remain distinct from the initial version even when the materialized content and diff are unchanged.

- **Make incorporation mechanical.** A review seal must verify that the stored question has an answer and that the replacement record binds the exact question-and-answer pair passed to the replacement request. Do not infer incorporation by comparing question or answer prose with candidate prose.

- **Seal only the exact completed replacement.** Load the initial candidate’s replacement binding and require the supplied replacement identity to match it before sealing. Bind the seal to the initial candidate version, question inventory, answer records, replacement content and version identities, answer-incorporation record, and final capsule binding. Refuse missing, changed, or substituted members. Step 9 owns approval and accepted-head movement.

- **Keep logs redacted and reusable.** Use one `RunLogWriter` lifecycle with `run_end()` from a single `finally` path. Record phases, call counts, expansion use, and terminal outcomes through existing generic events, but never log prompt, question, answer, capsule, artifact, or model-response text.

- **Keep prompts self-contained.** `plan_tool/prompts/roadmap-candidate-questions.md` must state its closed question schema, allowed anchor forms, and no-repository-browsing rule. Every `${...}` placeholder must have a supplied value, and literal dollar signs must follow `string.Template` escaping rules.

- **Leave live writers unchanged.** `plan_tool/roadmap_revision_run.py:run_local_feedback_revision()` and `plan_tool/roadmap_revision_patch.py:merge_feedback_revision()` remain separate because their live-artifact publication contract differs from immutable candidate review.

## Tests

### Tests for this step

- `tests/test_roadmap_candidate_review.py:test_question_request_uses_only_stored_candidate_diff_feedback_closure_and_identity_inventory` — The question prompt contains the persisted diff, feedback, ordered closure-member identities, inclusion reasons, declared-relation evidence, and compact inventory while excluding unrelated candidate, live-roadmap, live-brief, and live-gate content.

- `tests/test_roadmap_candidate_review.py:test_question_response_requires_one_closed_resolvable_anchor` — Duplicate keys, extra fields, invalid anchor kinds, mixed anchors, and unresolvable anchors reject before inventory storage.

- `tests/test_roadmap_candidate_review.py:test_question_inventory_is_candidate_bound_reusable_and_replacement_is_refused_before_invocation` — Re-entry returns the candidate-bound inventory while a replacement identity refuses before invocation.

- `tests/test_roadmap_candidate_review.py:test_reviewer_answer_is_immutable_and_bound_to_one_question_inventory` — The answer keeps its exact supplied bytes and rejects unknown question and substituted-inventory bindings.

- `tests/test_roadmap_candidate_review.py:test_answer_replacement_creates_distinct_candidate_and_exact_review_seal` — The representative answer path creates and seals one distinct replacement while preserving the initial candidate.

- `tests/test_roadmap_candidate_review.py:test_review_seal_refuses_a_replacement_not_bound_to_the_initial_candidate` — A supplied replacement identity that differs from the initial candidate’s stored replacement binding refuses sealing.

- `tests/test_roadmap_candidate_review.py:test_answer_driven_replacement_spends_the_recorded_expansion_once` — A valid answer-driven expansion spends the recorded capacity once.

- `tests/test_roadmap_candidate_review.py:test_candidate_review_invoker_and_run_log_are_bounded_and_redacted` — Fake invokers observe only the permitted call count, and logs contain lifecycle metadata but no model or reviewer content.


**Green-before-done gate:** Every listed test in `tests/test_roadmap_candidate_review.py` must pass before this step is complete.

## Acceptance criteria

- One stored initial candidate produces one immutable question inventory whose anchor points to its selected feedback, persisted diff, or recorded identity facts.
- The question prompt carries the stored capsule receipt's ordered closure-member identities, inclusion reasons, and declared-relation evidence without reading live closure or gate state.
- Review entry accepts only the admitted initial candidate identity; replacement and unrelated candidate identities refuse before invocation or review-record writes.

- Invalid question output or an inventory collision leaves candidate bytes, accepted-head state, and prior review records unchanged.

- A reviewer answer creates a separate immutable record bound to one exact question inventory and does not modify the candidate, feedback, question, or accepted head.

- An exact stored question-and-answer replay continues or returns the same replacement; changed pair members refuse without creating a branch.

- The replacement prompt carries the exact immutable question-and-answer pair that gives answer text its meaning; answer text alone, CLI-supplied question prose, and live reconstruction are not accepted inputs.

- A replacement always uses the same predecessor, selected feedback, and stored capsule as the initial candidate, and it never compiles a new initial context.

- An answer-driven replacement preserves relations on retained existing rows; only admitted row additions or removals may change the relation set.

- A replacement may use only the recorded expansion route, persists any resulting final capsule and receipt, and cannot spend another expansion later.

- Initial, expanded, and answer-driven capsule compilation share step 5's fixed 64 KiB ceiling without a review-time override.

- A gate-clean replacement becomes a distinct answer-bound candidate version while the initial candidate remains unchanged, including when both versions have the same materialized content.

- A review seal binds the exact replacement, question inventory, question-and-answer pair, answer-incorporation record, and final capsule binding; missing or substituted members refuse sealing.

- Candidate review does not move the accepted head or write canonical roadmap artifacts.

- `TESTING.md` documents the injected candidate-review backend seam.

- `tests/test_roadmap_candidate_review.py` passes.

## References

- [Structured outputs - Claude Platform Docshttps: — Use a constrained response shape that deterministic code can reject safely.

- [Configuration | Pydantic Docshttps: — Use strict frozen models with forbidden extra fields for review records and response envelopes.

- [json — JSON encoder and decoderhttps: — Use strict decoding hooks and deterministic serialization for closed records.

- [hashlib — Secure hashes and message digestshttps: — Bind candidate, question, answer, and seal identities with SHA-256.

- [RFC 8785: JSON Canonicalization Schemehttps: — Review stable JSON rules before fixing review-record identity inputs.

## Applicable guardrails

- **The plan’s “## Plan intent” and step intent** — Keep reviewer clarification tied to one inert candidate lineage; do not create a general document-review system.

- **The plan’s “## Scope guardrails”, model authority** — Treat model output as proposed questions or deltas only. This step must leave authority for answers, approval, and canonical selection outside the model.

- **The plan’s “## Scope guardrails”, lifecycle ordering** — Form question, answer, replacement, and seal records only in the plan-defined order. This step must not promote or alter the accepted head.

- **The plan’s “## Scope guardrails”, distinct immutable bindings** — Preserve separate identities for feedback, predecessor, content, candidate version, answer, and seal so later output cannot substitute for review evidence.

- **The plan’s “## Scope guardrails”, fixed roadmap admission and replay** — Re-entry must reuse recorded inputs and results instead of accepting changed reviewer input or creating a sibling branch.

- **The plan’s “## Scope guardrails”, inspectable context and edit authority** — Keep context expansion bounded and visible. Question anchors may identify compact inventory entries but cannot convert them into edit authority.

- **The plan’s “## Scope guardrails”, validation limits** — Validate record shape, identity, binding, and the fixed capsule ceiling only. Do not make deterministic claims about question, answer, or roadmap-prose quality.

- **The plan’s “## Out of scope”** — Keep this to the smallest single-reviewer happy path; leave broader review workflows, branch management, and operational hardening out of these files.

## Deferred

- **More context after the lineage’s recorded expansion is spent** — This needs a separate plan-level decision about context authority and storage.

- **CLI answer entry and review presentation** — Step 11 owns the operator-facing lifecycle surface.

- **Promotion and accepted-head replacement** — Step 9 owns approval of the sealed candidate and the selector-only publication.

- **Consolidating immutable review with live same-artifact revision** — `plan_tool/roadmap_revision_run.py:run_local_feedback_revision()` has a different authority and publication contract.

- **Question usefulness measurement with a real backend** — This needs real reviewer inputs and a durable observation process outside the hermetic suite.
