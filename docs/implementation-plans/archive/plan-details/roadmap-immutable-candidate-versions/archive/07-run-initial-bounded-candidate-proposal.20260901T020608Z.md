> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 7 — Run the initial bounded candidate proposal within the lineage’s one-expansion budget and store only a gate-clean inert version

## Summary

Create `plan_tool/roadmap_candidate_run.py` as the bounded proposal runner and `plan_tool/prompts/roadmap-candidate-delta.md` as its closed model-facing contract. The runner admits one immutable lineage for the selected feedback, compiles its initial context, permits one recorded expansion request, sends no more than two bounded backend requests per entry, and passes a typed delta only to step 6’s materialization boundary. Store a candidate only after that boundary returns a complete gate-clean result, with its immutable identity and predecessor binding intact. Update `TESTING.md` and add `tests/test_roadmap_candidate_run.py` so the backend seam and refusal paths stay hermetic.

## Table of Contents

- [Summary](#summary) — The step’s outcome and narrow footprint.
- [Table of Contents](#table-of-contents) — Links to each section.
- [Why](#why) — Why the new proposal edge cannot reuse the live revision writer.
- [Input](#input) — The immutable context, typed delta, storage, and backend contracts.
- [Files (creates vs edits)](#files-creates-vs-edits) — The new runner, prompt, tests, and testing guidance.
- [Implementation](#implementation) — The bounded proposal flow, expansion rule, persistence boundary, and observability.
- [Tests](#tests) — Coverage for calls, expansion, refusals, persistence, and prompt rendering.
- [Acceptance criteria](#acceptance-criteria) — Observable conditions for a stored inert candidate.
- [References](#references) — Closed-output and strict-decoding guidance.
- [Applicable guardrails](#applicable-guardrails) — Plan fences that limit this proposal route.
- [Deferred](#deferred) — Later review, promotion, CLI, and consolidation work.

## Why

`plan_tool/roadmap_revision_run.py:run_local_feedback_revision()` is a same-artifact live-writer route, and its `render_local_revision_prompt()` deliberately gives the model only a selected artifact. That route cannot turn cross-artifact feedback into an immutable, reviewable proposal without giving a model authority over canonical files. This step introduces a separate bounded runner that uses the immutable context and typed candidate seams from steps 5 and 6, so free-form feedback can produce a stored proposal while accepted-head state remains unchanged.

## Input

- **Accepted predecessor and initial capsule:** Step 3 supplies the selected immutable root and its raw brief binding, and step 5 supplies the initial capsule, compact inventory, receipt, and one-expansion operation. The runner must build from those immutable inputs, never from top-level roadmap artifacts, directory recency, or a live brief.

- **Issued capsule and lineage budget:** Step 5's capsule records either no expansion or one selected initial inventory item. A second expansion request must refuse, and the exact issued capsule is the only context passed to step 6. An unexpanded initial capsule remains eligible for the one answer-driven expansion in step 8; an expanded initial capsule is already the lineage's final capsule.

- **Stable feedback identity:** The selected feedback binding includes its artifact key, stable row id, and exact row digest. Candidate materialization preserves those feedback bytes, so this identity can own one admission across predecessor changes without changing the `FeedbackRow`.

- **Typed delta and materialization result:** Step 6 owns strict delta parsing, authorization, full-roadmap gates, deterministic diffing, and candidate content identity. The runner must treat its result as the only evidence that a proposal is complete and gate-clean.

- **Shared stored-version boundary:** Step 3 owns the single root-and-candidate record, namespace, and resolver. Candidate persistence must use that boundary with a non-null predecessor and must carry the predecessor's exact raw recorded-brief bytes and raw digest unchanged; it must not recreate them from context text or create a private candidate path or resolver.

- **Backend seam:** `plan_tool/roadmap_revision_run.py:shell_local_revision_invoker()` and `run_local_feedback_revision()` show the existing one-shot invoker shape. `plan_tool/shell.py:claude_invoke()` remains the production transport, while tests inject an `invoker=` callback.

- **Prompt loading and run evidence:** Use `plan_tool/renderer.py:prompts_dir()` to find the packaged template. Use `plan_tool/run_log.py:RunLogWriter.start()`, `RunLogWriter.bind_shell_sink()`, and `RunLogWriter.run_end()` so each proposal attempt has bounded, redacted run evidence.

## Files (creates vs edits)

- **New files:**
  - `plan_tool/roadmap_candidate_run.py` — Define the bounded initial-proposal runner, response disposition parsing, backend wrapper, immutable candidate persistence, and result records.
  - `plan_tool/prompts/roadmap-candidate-delta.md` — Define the closed prompt contract for either one typed delta or one initial-inventory expansion request.
  - `tests/test_roadmap_candidate_run.py` — Cover the runner, prompt, persistence, refusal, and backend seams.

- **Existing files (edits only):**
  - `TESTING.md` — Add the new runner’s `invoker=` seam to the backend fallback table, including the production-wrapper assertion that transport recovery stays disabled.

## Implementation

- **Foundational logic:** Turn one initial delta response, or one valid initial expansion followed by one delta response, into one stored gate-clean inert candidate.

- **Keep one narrow orchestration boundary.** Expose a small public runner in `plan_tool/roadmap_candidate_run.py`, such as `run_initial_candidate_proposal()`, with explicit immutable predecessor, feedback selection, and context-budget inputs. Keep CLI parsing with step 11; this module must not add a command surface.

- **Build context before any model call.** Resolve the accepted predecessor through step 3’s accepted-head boundary, then ask step 5 to compile the initial capsule. Invalid selection, missing immutable inputs, malformed context, or an over-budget capsule returns `refused` before prompt rendering, backend access, or candidate storage.

- **Admit one immutable lineage before invocation.** Derive one lineage identity and fixed admission path from the roadmap identity plus the selected feedback's artifact key, stable id, and exact row digest. Before a backend call, persist a closed admission that binds that feedback identity, the current accepted predecessor, and the complete initial capsule and receipt. An identical existing admission is the same lineage; a different predecessor, feedback binding, or initial capsule at that path refuses. Do not add a mutable lineage head, branch list, lease, or general operation registry.

- **Make explicit re-entry single-lineage.** If the admission already binds a visible initial candidate, validate and return that exact candidate as `stored` without a backend call. If no candidate is bound, continue from the admission's exact capsule. A previously persisted expansion member is the only final capsule on re-entry, so the runner asks only for its delta and cannot select or spend another expansion. This is user-triggered continuation through the same proposal action, not an automatic retry or crash-recovery subsystem.

- **Use a closed two-disposition response.** The initial response may contain either a typed delta for the initial capsule or one request naming an entry from that capsule’s compact inventory. It must not contain both dispositions, raw artifact text, source paths, a head-selection instruction, an answer, or a promotion instruction. Reuse step 6’s strict typed-delta contract after the runner has selected the delta disposition; do not add a second loose JSON decoder for delta operations.

- **Spend expansion exactly once.** When the first response selects a valid initial inventory entry, call step 5’s expansion operation and persist that expanded capsule and receipt under the admission before making the one follow-up request for a delta. The second response must contain a delta only. An unknown inventory entry, an expansion from an already-expanded capsule, or a second expansion request is `response-rejected`; an expanded capsule that exceeds its declared budget is `refused`. Neither rejected path makes another request or writes a candidate, and later re-entry cannot choose a different expansion.

- **Keep transport calls bounded.** Provide a production wrapper modeled on `plan_tool/roadmap_revision_run.py:shell_local_revision_invoker()` that calls `plan_tool/shell.py:claude_invoke()` with rate-limit waiting disabled and one transient attempt. Each proposal request gets one physical transport call, so an unexpanded proposal makes one call and an expanded proposal makes two calls at most.

- **Render only supplied authority.** Load `plan_tool/prompts/roadmap-candidate-delta.md` through `plan_tool/renderer.py:prompts_dir()` and render it with the capsule’s exact payload and receipt facts. The template must tell the model to work only from supplied content, treat compact inventory entries as discovery-only, and return the closed response shape without fences or surrounding text. Keep the contract in the template itself; it must not direct the model to open repository documentation or inspect files.

- **Return one closed terminal outcome.** The candidate runner returns exactly `stored`, `response-rejected`, `failed`, or `refused`. `stored` means the complete candidate visibility record exists. `response-rejected` means a backend response arrived but failed the closed response shape, expansion authority, typed-delta authorization, candidate parse, or full-roadmap gates; a later explicit command may produce another response, but this route does not retry it. `failed` means invocation or persistence failed. `refused` means deterministic preflight, context-budget, immutable-binding, lineage, or identity-collision checks rejected the request. A valid expansion is an internal continuation, not a terminal outcome.

- **Apply terminal precedence once.** Deterministic preflight refusal wins before invocation; invocation failure wins when no usable response exists; a returned invalid response is `response-rejected`; a failure while persisting an otherwise accepted result is `failed`; and only a fully visible candidate is `stored`. `KeyboardInterrupt` remains the existing interrupted path outside this domain set. Do not add automatic correction or transport retries.

- **Materialize before persistence.** Pass only the exact issued capsule and parsed typed delta to step 6. A malformed or unauthorized response, candidate parse failure, or gate failure returns `response-rejected`; backend or persistence failure returns `failed`. Every non-`stored` outcome produces no visible candidate. Do not assess the truth, quality, completeness, or semantic equivalence of the model's prose.

- **Store only a complete inert result.** Persist the complete candidate bytes, step 6 content identity, predecessor binding, predecessor's exact raw brief bytes and raw digest, complete canonical issued-capsule bytes, issued-capsule receipt, diff, and gate evidence only after step 6 accepts them. Record whether expansion remains available; an expanded capsule is final immediately, while an unexpanded capsule becomes final only if review closes without spending that budget. Derive the initial candidate-version identity from those facts plus the immutable admission identity and an explicit empty review-lineage binding, then store it through step 3's shared version namespace and record shape with a non-null predecessor. Write an immutable admission-to-candidate result binding last; reject a conflicting binding or version identity rather than overwriting it. Use `plan_tool/fileio.py:durable_write_bytes()` or an equivalent existing durable byte writer for persisted records and bytes.

- **Make capsule reuse loadable and verifiable.** The candidate record must bind the digest of the complete stored capsule bytes and the exact receipt identity. Loading a candidate for review validates both before returning them; a receipt without its capsule, a substituted capsule with the same compact metadata, or any live-context recompilation refuses.

- **Preserve canonical state.** The candidate store must not rewrite a stored predecessor, move the accepted-head selector, alter feedback, or update top-level roadmap artifacts. A failed or interrupted candidate write has no visible candidate record; recovery, retention, and cleanup remain outside this step.

- **Record bounded execution facts.** Open a `RunLogWriter` when no logger is injected, bind its shell sink around each backend call, and close it from one `finally` path. Record attempt count, final capsule identity, expansion use, and the exact terminal outcome without storing model prompt or response bodies in the log.

- **Leave the live revision route alone.** `plan_tool/roadmap_revision_run.py:run_local_feedback_revision()` remains unchanged because its live same-artifact publication contract differs from immutable candidate storage. Do not consolidate the two runners in this step.

## Tests

### Tests for this step

- `test_initial_candidate_proposal_materializes_and_stores_only_a_gate_clean_inert_candidate_version` — A valid first-response delta creates one shared-contract stored version whose predecessor, content identity, empty-lineage version identity, bytes, diff, and gate evidence match step 6's accepted result without changing accepted-head or source bytes.

- `test_initial_candidate_proposal_uses_only_the_accepted_predecessor_and_initial_capsule` — Live source changes, another stored version, and a compact-inventory digest do not alter the prompt authority or candidate input.

- `test_initial_inventory_expansion_rebuilds_the_final_capsule_before_the_second_delta_request` — A valid first expansion request produces one expanded final capsule, makes a second request with that capsule, and materializes only the second response.

- `test_expanded_proposal_refuses_a_second_expansion_without_a_third_backend_call` — An expanded response that requests more context creates no candidate and never invokes the backend again.

- `test_invalid_or_over_budget_expansion_refuses_before_follow_up_or_storage` — An unknown initial inventory entry or an expansion that exceeds its budget returns a refusal, makes no second request, and leaves no candidate record.

- `test_candidate_response_requires_one_closed_delta_or_expansion_disposition` — Extra keys, duplicate JSON keys, surrounding text, mixed dispositions, and raw artifact-write instructions refuse before materialization.

- `test_candidate_materialization_refusal_never_creates_a_stored_candidate` — An unauthorized, malformed, or gate-failing delta leaves accepted-head state, predecessor bytes, and candidate storage unchanged.

- `test_candidate_storage_rejects_version_identity_collision_without_overwrite` — A pre-existing candidate-version identity causes refusal and retains the original stored bytes and record.

- `test_candidate_storage_persists_and_validates_the_complete_issued_capsule_and_receipt` — Review loading returns the exact canonical capsule bytes and receipt stored with the candidate, while a missing or substituted member refuses without recompilation.

- `test_candidate_storage_uses_the_shared_version_contract_and_carries_raw_recorded_brief_bytes` — The accepted-version resolver validates the candidate through step 3's namespace and returns its exact inherited raw brief bytes, including CRLF, after live brief changes.

- `test_candidate_visibility_record_is_written_only_after_complete_gate_clean_members` — A write failure before the final record leaves no readable stored candidate.

- `test_production_candidate_invoker_disables_transport_recovery` — The production wrapper calls `plan_tool/shell.py:claude_invoke()` once per proposal request with rate-limit waiting disabled and one transient attempt.

- `test_candidate_runner_records_bounded_attempts_expansion_and_one_terminal_outcome` — The run log records one or two bounded calls, the final capsule identity, expansion use, and one terminal result without prompt or response content.

- `test_candidate_runner_terminal_outcomes_are_closed_and_precedence_is_total` — Preflight refusal, invocation failure, returned-response rejection, persistence failure, and successful visibility produce only `refused`, `failed`, `response-rejected`, `failed`, and `stored`, respectively; valid expansion remains nonterminal.

- `test_feedback_identity_admits_one_immutable_lineage_before_backend_invocation` — The first proposal persists the exact predecessor and initial capsule under one stable feedback admission, while a conflicting predecessor or capsule cannot create a sibling lineage.

- `test_reentered_proposal_reuses_admission_expansion_and_stored_candidate` — Re-entry after an invocation failure uses the admitted capsule, re-entry after a persisted expansion asks only for its delta, and re-entry after candidate visibility returns the same candidate without another call.

- `test_candidate_delta_prompt_has_only_supplied_placeholders_and_no_unresolved_tokens` — The template exists under `plan_tool/prompts/`, renders with the runner’s variables, and leaves no unresolved `${...}` token.

- `test_candidate_delta_prompt_forbids_repository_browsing_and_compact_inventory_edits` — The prompt limits the model to supplied capsule content and states that inventory entries cannot authorize existing-content changes.

Every named test in `tests/test_roadmap_candidate_run.py` must be green before this step is complete.

## Acceptance criteria

- The new runner accepts one selected accepted predecessor and returns exactly one of `stored`, `response-rejected`, `failed`, or `refused`; only `stored` exposes an inert candidate.

- An initial proposal makes one backend request for a delta, or exactly two requests when the first response spends the lineage’s one expansion.

- One stable feedback identity admits one immutable lineage before invocation; explicit re-entry resumes its exact capsule or returns its bound candidate and never creates a sibling or spends a second expansion.

- A second expansion request, invalid inventory selection, or over-budget final capsule causes no further backend request and no candidate storage.

- Only a complete candidate accepted by step 6’s typed authorization and full-roadmap gates becomes visible in candidate storage.

- Stored candidate records bind the fixed content identity, empty-lineage candidate-version identity, predecessor, exact inherited brief, complete issued capsule and receipt, remaining expansion state, complete bytes, diff, and gate evidence, and an identity collision does not overwrite existing data.

- Candidate proposal processing does not change accepted-head selection, a predecessor version, feedback, or top-level roadmap artifact bytes.

- `TESTING.md` documents the runner’s injected backend seam and production transport-recovery settings.

- `tests/test_roadmap_candidate_run.py` passes.

## References

- [Structured outputs - Claude Platform Docs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs) — Use a closed response contract that deterministic code can reject safely.

- [Configuration | Pydantic Docs](https://docs.pydantic.dev/latest/api/config/) — Use strict, frozen records with forbidden extra fields for response dispositions and stored candidate records.

- [json — JSON encoder and decoder](https://docs.python.org/3.13/library/json.html) — Use strict decoding that rejects malformed, duplicate-key, or trailing response data.

- [hashlib — Secure hashes and message digests](https://docs.python.org/3.13/library/hashlib.html) — Bind stored candidate content/version identities, complete capsule, and member evidence to the accepted result.

## Applicable guardrails

- **The plan’s “## Plan intent” and step intent** — Map one feedback request to an inert proposal only; do not turn this runner into a general roadmap editor.

- **The plan’s “## Scope guardrails”, binary observables** — Make the complete stored issued capsule and receipt, remaining expansion state, candidate content and version identities, stored bytes, and gate result directly inspectable.

- **The plan’s “## Scope guardrails”, model authority** — Treat every model response as inert input. This route must not alter canonical roadmap state or create review or promotion authority.

- **The plan’s “## Scope guardrails”, lifecycle order and distinct bindings** — Stop after materializing and storing the initial candidate. Keep admission, predecessor, feedback, candidate content identity, empty-lineage version identity, later answers, and review seals separate.

- **The plan’s “## Scope guardrails”, context omission and compact inventory authority** — Permit only the recorded expansion and never use compact inventory data as permission to edit omitted existing content.

- **The plan’s “## Scope guardrails”, validation authority** — Validate response shape, bindings, limits, and existing candidate gates without judging model prose quality.

- **The plan’s “## Out of scope”, direct writes and workflow expansion** — Do not add direct model-to-canonical writes, automatic promotion, retrieval, concurrent workflows, or a generic context system.

## Deferred

- **Questions, reviewer answers, replacement proposals, and review seals** — Step 8 owns the review lineage. It loads this candidate's stored capsule, may spend the one still-unused expansion for the first answer-driven replacement, and then stores and reuses the resulting final capsule rather than compiling another lineage context.

- **Accepted-head promotion** — Step 9 owns approval of an immutable review seal and the only accepted-head move.

- **CLI integration and the end-to-end operator workflow** — Step 11 owns command parsing, lifecycle ordering across commands, and CLI-level fake-backend coverage.

- **A request that needs more than one expansion** — Record the final capsule facts and refusal for a separate design decision; do not add a third backend call, retrieval layer, full-roadmap prompt, or silent summary.

- **Shared orchestration with `plan_tool/roadmap_revision_run.py:run_local_feedback_revision()`** — The live writer and immutable candidate routes have different authority and persistence contracts, so consolidation requires separately scoped refactor work.
