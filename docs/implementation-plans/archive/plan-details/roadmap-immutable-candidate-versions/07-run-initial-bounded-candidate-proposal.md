> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 7 — Run the initial bounded candidate proposal within the lineage’s one-expansion budget and store only a gate-clean inert version

## Summary

Create `plan_tool/roadmap_candidate_run.py` as the bounded initial-proposal runner and `plan_tool/prompts/roadmap-candidate-delta.md` as its closed model-facing contract. The runner turns one typed delta, or one valid context-expansion request followed by one typed delta, into an immutable candidate only after step 6 accepts the complete candidate. It records one fixed roadmap admission for the representative feedback so explicit re-entry reuses fixed inputs and a different feedback cannot create a branch. Update `TESTING.md` and add `tests/test_roadmap_candidate_run.py` so the backend seam, prompt contract, storage boundary, and refusal cases remain hermetic.

## Table of Contents

- [Summary](#summary) — The outcome and scoped files.
- [Table of Contents](#table-of-contents) — Links to each section.
- [Why](#why) — Why the live revision runner cannot provide this proposal path.
- [Input](#input) — The immutable predecessor, capsule, materializer, and existing runner seams.
- [Files (creates vs edits)](#files-creates-vs-edits) — The new runner, prompt, tests, and testing guidance.
- [Implementation](#implementation) — The bounded lineage, response handling, storage, and observability rules.
- [Tests](#tests) — Focused coverage for proposal, expansion, refusal, and persistence behavior.
- [Acceptance criteria](#acceptance-criteria) — Observable completion conditions.
- [References](#references) — Closed-response, identity, and durable-write guidance.
- [Applicable guardrails](#applicable-guardrails) — Plan boundaries that constrain this route.
- [Deferred](#deferred) — Lifecycle work that later steps own.

## Why

`plan_tool/roadmap_revision_run.py:run_local_feedback_revision()` accepts a selected live artifact and ends by publishing a same-artifact revision. That route cannot preserve a cross-artifact proposal, its exact context, and its predecessor as immutable review input. This step adds a separate runner that turns bounded model output into inert stored candidate evidence while leaving accepted-head selection and canonical roadmap files untouched.

## Input

- **Immutable predecessor:** Step 3 provides the selected accepted version, complete stored artifact bytes, and recorded-brief byte binding. The runner must use that selected version and must not read top-level roadmap artifacts, a live brief, directory order, or another version to fill context.

- **Writer fence:** Step 4 provides the enrolled-roadmap boundary. Use the existing `plan_tool/roadmap_revision_publish.py:roadmap_writer_guard()` for candidate admission and immutable writes; do not introduce a second lease or concurrency system.

- **Capsule and receipt:** Step 5 provides the initial context capsule, its compact inventory, the fixed recorded 64 KiB payload ceiling, and the one-expansion operation. An unexpanded capsule leaves the one expansion available to step 8; an expanded capsule is the lineage’s final capsule. The runner cannot supply or override a ceiling.

- **Candidate materialization:** Step 6 owns strict typed-delta parsing, full-content authorization, complete gate checks, deterministic diffs, and candidate content identity. The runner must treat its accepted materialization result as the only evidence that a candidate may be stored.

- **Backend and prompt seams:** `plan_tool/roadmap_revision_run.py:shell_local_revision_invoker()` and `run_local_feedback_revision()` establish the injected `invoker=` shape. `plan_tool/renderer.py:prompts_dir()` locates packaged templates, while `plan_tool/run_log.py:RunLogWriter.start()`, `RunLogWriter.claude_call_start()`, `RunLogWriter.bind_shell_sink()`, and `RunLogWriter.run_end()` provide the existing bounded-call evidence seam.

- **Strict response precedent:** `plan_tool/roadmap_revision.py:parse_revision_operations()` and its single-object decoder show the required duplicate-key, non-standard-constant, trailing-content, and unknown-field refusal behavior.

## Files (creates vs edits)

- **New files:**
  - `plan_tool/roadmap_candidate_run.py` — Define the initial candidate-proposal runner, closed response handling, production invoker, lineage admission, candidate persistence, and result record.
  - `plan_tool/prompts/roadmap-candidate-delta.md` — Define the self-contained response contract for a typed delta or one compact-inventory expansion request.
  - `tests/test_roadmap_candidate_run.py` — Cover the runner, prompt, storage, refusal paths, and observability with fake backend replies.

- **Existing files (edits only):**
  - `TESTING.md` — Add `plan_tool/roadmap_candidate_run.py` and its `invoker=` seam to `## Backend fallback seams`, including the production transport settings tests must assert.

## Implementation

- **Foundational logic:** Turn one valid delta, or one valid expansion followed by one valid delta, into one stored gate-clean inert candidate with no third model request.

- **Keep one narrow public boundary.** Add a runner such as `run_initial_candidate_proposal()` in `plan_tool/roadmap_candidate_run.py`. It must accept one roadmap identity, feedback selector, injected invoker, and optional run logger. Keep CLI argument parsing and user-facing command flow with step 11.

- **Admit one immutable lineage first.** Use one fixed admission path for the roadmap. Before any backend call, bind the selected feedback identity, accepted predecessor identity, initial capsule, and receipt into that persisted admission. The feedback identity must include the selected artifact key, stable feedback id, and recorded feedback digest. An existing exact match is the same lineage; a different feedback selector or conflicting predecessor, capsule, or receipt must refuse rather than create a sibling lineage. Promotion does not clear or replace the admission, so this proof does not admit sequential feedback lifecycles.

- **Make re-entry deterministic.** When an admission already binds a visible candidate, validate and return that exact candidate without invoking the backend. When it does not, reuse the admission’s stored capsule and receipt. A persisted expanded capsule is the final capsule for every later attempt in that lineage.

- **Use a closed two-disposition response.** The first model response must contain exactly one of:
  - one typed delta for the issued capsule; or
  - one request naming an exact entry in that capsule’s compact inventory.

  Reject mixed dispositions, extra fields, duplicate keys, non-standard constants, trailing text, raw artifact content, standalone relation or ordering-entry operations, filesystem paths, accepted-head instructions, answers, and promotion instructions. Forward the delta portion to step 6’s parser rather than creating a second delta format.

- **Spend the expansion once.** When the initial response names a valid inventory entry, use step 5’s expansion operation and its module-owned 64 KiB ceiling against the same predecessor, then persist the resulting capsule and receipt before rendering the follow-up request. The follow-up response must contain a delta only. Unknown inventory entries, an already-expanded capsule, a second expansion request, or an over-budget expanded capsule must stop processing without another backend call or candidate write.

- **Keep model calls bounded.** Model calls must occur only after deterministic admission and prompt preparation succeed. An unexpanded lineage makes one runner-level request; a valid initial expansion makes exactly two. Model-response rejection, transport failure, materialization rejection, or persistence failure must not cause an automatic retry.

- **Use the existing transport shape.** Provide a production wrapper modeled on `plan_tool/roadmap_revision_run.py:shell_local_revision_invoker()` and call `plan_tool/shell.py:claude_invoke()` with a dedicated phase, `wait_on_rate_limit=False`, and `max_transient_retries=1`. Tests must inject `invoker=` and must not call a real backend.

- **Render only stored authority.** Load `plan_tool/prompts/roadmap-candidate-delta.md` through `plan_tool/renderer.py:prompts_dir()`. Give the template one closed nullable `review_pair` input beside the issued capsule payload and receipt facts. The initial runner supplies explicit null; step 8 supplies the immutable question id, anchor, exact opaque question text, answer id, and exact answer text. The prompt must say that compact inventory is discovery-only, the model may work only from supplied content, and it must return an unfenced closed response object; it must not direct the model to inspect repository files or root-level documentation.

- **Materialize before storage.** Pass only the exact issued capsule, receipt, predecessor, selected feedback binding, and parsed delta to step 6. A malformed, unauthorized, parse-failing, or gate-failing candidate is `response-rejected` and must not expose candidate storage.

- **Store only complete inert evidence.** Persist the candidate through step 3’s shared version contract with its predecessor binding, raw recorded-brief bytes and digest, complete artifact bytes, content identity, deterministic diff, gate evidence, issued capsule, and receipt. Store whether the expansion remains available. The candidate-version identity must bind the initial empty review position without treating it as approval or accepted-head authority.

- **Make visibility the final write.** Candidate members and records may be prepared first, but the admission-to-candidate binding must become visible only after every stored member validates. A collision or write failure must refuse or fail without overwriting an existing candidate, predecessor, accepted-head selector, feedback row, or top-level roadmap artifact.

- **Return a closed result.** Normal completion must distinguish `stored`, `response-rejected`, `failed`, and `refused`. Preserve the existing interrupted-run handling for `KeyboardInterrupt`. Only `stored` may return a visible candidate.

- **Record metadata, not model content.** Use one `RunLogWriter` lifecycle with `RunLogWriter.run_end()` from a single `finally` path. Record call count, terminal outcome, and expansion use through existing run-log events, but do not write prompt, model-response, capsule, feedback, or artifact text into the log.

- **Leave the live writer separate.** Do not change `plan_tool/roadmap_revision_run.py:run_local_feedback_revision()` or merge it with this runner. Its selected-live-artifact publication contract differs from immutable candidate storage.

## Tests

### Tests for this step

- `tests/test_roadmap_candidate_run.py:test_initial_delta_stores_one_gate_clean_inert_candidate_without_moving_accepted_head` — A valid delta creates one stored candidate whose predecessor, bytes, diff, gate evidence, and identities match step 6’s result while accepted-head and source artifacts remain unchanged.

- `tests/test_roadmap_candidate_run.py:test_fixed_roadmap_admission_refuses_different_feedback_before_a_backend_call` — The fixed admission refuses a conflicting feedback selector before a model call.

- `tests/test_roadmap_candidate_run.py:test_reentry_returns_the_bound_candidate_without_another_backend_call` — A completed admission returns its exact stored candidate rather than creating a branch or reinvoking.

- `tests/test_roadmap_candidate_run.py:test_valid_inventory_expansion_persists_final_capsule_then_requests_one_delta` — A valid initial expansion creates the final capsule and makes exactly one follow-up request with that capsule.

- `tests/test_roadmap_candidate_run.py:test_second_expansion_request_stops_without_a_candidate_or_third_request` — A second expansion request leaves no candidate and makes no third request.

- `tests/test_roadmap_candidate_run.py:test_initial_response_requires_exactly_one_closed_disposition` — Duplicate keys, non-standard constants, trailing text, extra fields, mixed dispositions, and raw-write instructions reject before materialization.

- `tests/test_roadmap_candidate_run.py:test_materialization_rejection_never_exposes_candidate_storage` — A materialization rejection leaves candidate storage and canonical roadmap state unchanged.

- `tests/test_roadmap_candidate_run.py:test_candidate_storage_refuses_missing_or_substituted_stored_members` — Review-facing loading refuses absent stored evidence rather than treating a partial candidate as review authority.

- `tests/test_roadmap_candidate_run.py:test_candidate_storage_refuses_evidence_that_cannot_be_reproduced` — A structurally valid but altered deterministic diff refuses when it does not reproduce from immutable predecessor and candidate bytes.

- `tests/test_roadmap_candidate_run.py:test_candidate_runner_logs_bounded_calls_and_terminal_outcome_without_model_content` — The run log records one or two calls and one terminal result without prompt, response, feedback, capsule, or artifact text.

- `tests/test_roadmap_candidate_run.py:test_candidate_delta_prompt_renders_only_supplied_variables_and_uses_null_review_pair` — The prompt resolves each supplied variable and initial proposal uses the explicit null review pair.

Every named test in `tests/test_roadmap_candidate_run.py` must be green before this step is complete.

## Acceptance criteria

- One proposal returns one stored inert candidate only after step 6 accepts its complete candidate and gate evidence.

- An unexpanded initial proposal makes one runner-level backend request; a valid initial expansion makes exactly two; no path makes a third.

- One fixed persisted roadmap admission owns the representative feedback lineage. A different feedback refuses before a backend call, the admission remains after promotion, and no sequential multi-feedback lifecycle is added.

- Re-entry returns a stored candidate or continues from the admission’s exact stored capsule and receipt without selecting a newer accepted head or compiling new initial context.

- A compact-inventory entry can request the one expansion but cannot authorize an edit by itself.

- Initial and expanded capsule compilation use step 5's fixed 64 KiB ceiling; the runner cannot vary it across entry or replay.

- The shared delta prompt accepts only one nullable stored question-and-answer pair; the initial route supplies explicit null and cannot synthesize review facts.

- A malformed response, invalid expansion, over-budget capsule, unauthorized delta, gate failure, or candidate-storage collision leaves canonical roadmap state and existing stored versions unchanged.

- Stored candidates bind their predecessor, inherited raw brief evidence, complete artifact bytes, content identity, deterministic diff, gate evidence, capsule, receipt, and initial review position.

- Candidate proposal processing does not move the accepted head, modify feedback, or write top-level roadmap artifacts.

- `TESTING.md` documents the runner’s injected backend seam and production transport settings.

- `tests/test_roadmap_candidate_run.py` passes.

## References

- [Structured outputs - Claude Platform Docshttps: — Use a constrained response shape that deterministic code can reject safely.

- [Configuration | Pydantic Docshttps: — Use strict frozen records with forbidden extra fields for response and stored-record boundaries.

- [json — JSON encoder and decoderhttps: — Use strict decoding and deterministic encoding for response and identity inputs.

- [hashlib — Secure hashes and message digestshttps: — Bind candidate, predecessor, capsule, and receipt evidence with SHA-256.

- [os — Miscellaneous operating system interfaceshttps: — Review atomic replacement behavior behind durable record writes.

- [RFC 8785: JSON Canonicalization Schemehttps: — Use stable JSON encoding when deriving immutable identities.

## Applicable guardrails

- **The plan’s “## Plan intent” and step intent** — Build only the bounded proposal route from feedback to inert candidate evidence.

- **The plan’s “## Scope guardrails”, binary observables** — Keep candidate bytes, identities, diffs, capsule facts, gate results, and predecessor bindings inspectable.

- **The plan’s “## Scope guardrails”, allowed behavior changes** — Limit changes to the candidate proposal path and preserve unversioned roadmap behavior.

- **The plan’s “## Scope guardrails”, model authority** — Treat model output only as an inert expansion request or typed delta; it cannot mutate canonical state or authorize later lifecycle actions.

- **The plan’s “## Scope guardrails”, lifecycle order and distinct bindings** — Materialize candidates before review and keep feedback, predecessor, candidate content identity, candidate-version identity, and later review records separate.

- **The plan’s “## Scope guardrails”, fixed roadmap admission** — Use one admission for explicit continuation and prohibit another feedback or replay from changing reviewer input, spending another expansion, or creating a branch.

- **The plan’s “## Scope guardrails”, context omission and compact inventory authority** — Persist and reuse exact capsule evidence, reject silent widening, and keep compact inventory out of edit authority.

- **The plan’s “## Scope guardrails”, validation authority** — Validate shape, count, identity, binding, budget, and existing gates only; do not judge model or roadmap prose quality.

- **The plan’s “## Scope guardrails”, smallest functional happy path** — Implement one initial candidate route without a general workflow or version-management framework.

- **The plan’s “## Out of scope”, workflow and hardening expansion** — Do not add automatic promotion, general retrieval, collaborative branching, or operational recovery beyond the existing durable-write primitives.

## Deferred

- **Reviewer questions, answers, replacements, and seals** — Step 8 owns immutable review records and answer-driven replacement.

- **Accepted-head promotion** — Step 9 owns approval and the selector-only canonical state change.

- **Accepted-head reader routing** — Step 10 owns the downstream view migration.

- **CLI flags and result rendering** — Step 11 owns the operator-facing command surface.

- **Consolidating immutable and live revision runners** — `plan_tool/roadmap_revision_run.py:run_local_feedback_revision()` has a different source and publication contract; any shared orchestration refactor needs separately scoped work.

- **Broader retry, recovery, retention, or branch management** — These exceed the representative bounded lineage proof.

- **Persistence-integrity hardening (2026-09-01, user-confirmed)** — A canonical-but-conflicting persisted admission capsule is outside this happy-path proof because normal lifecycle writers do not create it. [#330 owns pre-invocation revalidation; do not expand this runner for that state.
