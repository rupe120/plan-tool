> **Auto-archived**: this plan was swept on 2026-07-16 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 3 — Wire concept review and explicit ownership into create

## Summary

Integrate the shipped concept-record core into `plan_tool/create.py:create_plan` before the plan is finalized. Create must retain deterministic concepts when optional enrichment fails, obtain operator decisions when interactive, and place accepted included concept IDs on the committed steps that own them. Add a separate injected concept invoker, keep unattended proposals unsigned, and let the core synchronizer produce the scope prose and final sidecar state. Update `plan_tool/prompts/distill-seed.md` so distillation does not compete with the concept record for scope decisions, and cover the full create flow in `tests/test_create.py`.

## Table of Contents

- [Summary](#summary) — The create integration and its observable result.
- [Why](#why) — Why create needs reviewed concepts and durable ownership before publication.
- [Input](#input) — Contracts supplied by steps 1 and 2 and the shipped concept core.
- [Files (creates vs edits)](#files-creates-vs-edits) — The three existing files changed by this step.
- [Implementation](#implementation) — Gate placement, ownership review, synchronization, and failure rules.
- [Tests](#tests) — Unit and integration cases for create-time concept handling.
- [Acceptance criteria](#acceptance-criteria) — Observable completion conditions.
- [References](#references) — Structured-output validation guidance.
- [Deferred](#deferred) — Later detail, completeness, and structural-remedy work.

## Why

`plan_tool/create.py:create_plan` currently reviews proposed step change types and gates, then builds and writes a plan without a durable link between conceptual commitments and the steps responsible for them. Distillation and body synthesis can also produce scope prose independently of any reviewed concept record. This step makes concept review and explicit `Step.concept_ids` ownership part of create’s pre-publication flow, so deterministic concepts cannot disappear after an enrichment failure and unattended execution cannot be mistaken for operator approval.

## Input

- **Shipped concept-record core:** The execution prerequisite provides deterministic bootstrap, conflict-aware re-derivation, scoped review, persistence, and canonical synchronization in `plan_tool/concept_tree.py`. Confirm the landed public symbols and signatures at implementation time; this step must call those contracts rather than recreate their state machine, navigator, or writer in `plan_tool/create.py`.
- **Step 1 ownership field:** Step 1 adds `plan_tool/schema.py:Step.concept_ids` as the persisted ownership link. This step assigns accepted concept IDs to proposed steps; it does not change the field’s validation or serialization rules.
- **Step 2 enrichment producer:** Step 2 adds the evidence-only concept producer and its default invoker. Create supplies the seed and reviewed step context, but enrichment remains subordinate to deterministic bootstrap and does not persist independently.
- **Distill output:** `plan_tool/create.py:_canonical_body_section_keys` and `plan_tool/create.py:_validate_distilled_sections` require the existing eight-key single-plan section object. Any prompt field that must abstain still appears with a `null` value.
- **Create ordering:** `plan_tool/create.py:create_plan` already runs `_review_step_change_types` and `_review_step_gates` before constructing the final `Plan`, synthesizing its body, checking placeholders, and calling `write_new_plan`.

## Files (creates vs edits)

- **New files:**

  - None.

- **Existing files (edits only):**

  - `plan_tool/create.py` — add the independent concept invoker seam, run deterministic bootstrap and optional enrichment, invoke the shipped review and ownership flow, synchronize the reviewed result into the plan, and persist the final concept record against the completed plan bytes.
  - `plan_tool/prompts/distill-seed.md` — make scope fields abstain where the concept record is authoritative while preserving the exact eight-key response shape.
  - `tests/test_create.py` — cover deterministic fallback, interactive and unattended review, explicit ownership, synchronization, resume, invalid ownership suggestions, and final fingerprint behavior.

## Implementation

- **Make reviewed explicit ownership the foundational logic.** Before create publishes a plan, each accepted included concept must either appear in at least one proposed committed step’s `concept_ids` or remain visibly unresolved for later completeness handling. Title similarity or other heuristics may suggest an owner, but only an explicit accepted ID establishes ownership.

- **Add a distinct concept invoker seam.** Extend `plan_tool/create.py:create_plan` with a parameter dedicated to step 2’s concept producer, using the default invoker shipped by that step. Do not reuse `claude_invoker`: step proposal and concept enrichment have different response and failure contracts, and tests must be able to stub them independently. Because the default routes through `plan_tool/shell.py:claude_invoke`, the existing real-backend test guard applies without changes outside this step’s file list.

- **Place concept review after the existing step gates.** Run the integration after `plan_tool/create.py:_review_step_gates`, when the final proposed step list and source evidence are available, but before the final `Plan` is assembled and before body synthesis or `write_new_plan`. This ordering lets ownership attach to the settled step IDs and ensures every later render and validation sees the reviewed result.

- **Bootstrap before enriching.** Use the shipped core’s deterministic bootstrap or re-derivation entry point first, then pass that result through step 2’s evidence-only enrichment producer. An empty, malformed, or failed enrichment response must leave every deterministic seed intact. It must not skip review by turning the whole tree into `None`.

- **Use the saved record as resume state.** Derive the prospective plan path with `plan_tool/create.py:predict_plan_path`, because create’s priority prefix means `output_dir / f"{slug}.md"` is not the final path. Ask the shipped core to read and validate any existing concept record before producing a new one. Reuse a valid create-time resume record; route stale or conflicting state through the core’s documented re-derivation or conflict-review result instead of silently replacing operator decisions.

- **Keep review and persistence in the core.** Call the shipped scoped-review or navigation contract with create’s existing `input_fn` and `yes` context. Preserve its operator-approval rules:

  - Interactive confirmation may establish approval and accepted ownership.
  - `yes=True` and non-TTY execution retain safe suggested decisions but remain unsigned.
  - Every persisted intermediate decision uses the core’s single-writer seam.
  - A conflict or incomplete review remains visible and cannot be converted into a signed record by create-specific fallback code.

- **Review ownership as part of the concept decision.** Present producer-recommended links, when available, as suggestions against the settled steps. Accept only IDs that exist in the current concept record and step IDs that exist in the reviewed step list. Allow an included concept to have more than one owner when the shipped contract permits it; remove duplicates within each step through step 1’s validation rules.

- **Apply accepted links only to valid owners.** Copy accepted concept IDs onto committed proposed steps through `Step.model_copy` or an equivalent immutable update. Do not count deferred or `wont_do` steps as owners. If the operator defers a concept that had a suggested owner, do not leave that suggestion on a committed step as if delivery were still promised.

- **Do not infer ownership from titles.** A conservative title or identifier match can seed the operator’s choices, but it cannot silently populate authoritative `concept_ids`. The rejected alternative is automatic title-slug ownership: it produces false matches, breaks when titles change, and contradicts the plan’s explicit-link completeness rule.

- **Let the core synchronizer own scope rendering.** After review, call the shipped canonical synchronization contract to align concept decisions, step ownership, and the plan’s scope sections. Do not add a second renderer or sidecar writer in `plan_tool/create.py`. Feed the synchronized section values into the existing highest-precedence `synthesized_sections` path before `plan_tool/create.py:_find_placeholder_body_sections` and `plan_tool/create.py:write_new_plan`, so body synthesis cannot overwrite reviewed scope.

- **Keep fail-soft fallback honest.** If optional enrichment fails, continue with deterministic concepts and review them. If deterministic bootstrap or core synchronization itself cannot produce a valid result, raise an actionable `CreateError` before collision archival, plan writing, or manifest mutation. Do not fabricate an empty concept record or publish a plan through a silent-drop branch.

- **Persist authoritative fingerprints only after final bytes exist.** Intermediate review saves may use the core’s documented prospective or unset fingerprint state. After `plan_tool/create.py:write_new_plan` and the existing `parse_plan` verification succeed, finalize the concept record through the core synchronizer using the actual written plan. Do not fingerprint a stub, the pre-write `Plan`, or a body that differs from the published file.

- **Preserve the existing placeholder behavior.** Apply synchronized section overrides before the candidate body is passed to `plan_tool/create.py:_find_placeholder_body_sections`. The non-iterate path must validate the synchronized body; the `budget.enabled` path keeps its existing placeholder-check bypass.

- **Make distillation abstain without changing its schema.** Update `plan_tool/prompts/distill-seed.md` so fields whose final value belongs to reviewed concept synchronization return `null` unless the prompt is explicitly preserving seed evidence for the later concept flow. Keep all eight keys in the single-plan JSON object because `plan_tool/create.py:_validate_distilled_sections` rejects missing keys.

- **Keep later ownership transformations out of this step.** The same explicit-ID rule also applies to split, merge, re-ground, and scope-out paths, but steps 6 through 9 own those call sites. This step handles only initial ownership established during create.

## Tests

Add the following cases to `tests/test_create.py` using injected step and concept invokers. No test may invoke a real backend.

- `test_create_retains_deterministic_concepts_when_enrichment_fails` — malformed or empty enrichment leaves all deterministic seed concepts available for review and persistence.
- `test_create_reviews_concepts_after_step_gates` — the concept review receives the final post-review step IDs and contents.
- `test_create_uses_independent_concept_invoker` — the concept producer uses `concept_invoker` without consuming the step-proposal `claude_invoker`.
- `test_create_assigns_accepted_concept_ids_to_committed_steps` — accepted links appear in the written plan’s `Step.concept_ids`.
- `test_create_rejects_unknown_concept_ownership_id` — an ownership suggestion outside the current record cannot enter the written plan.
- `test_create_rejects_unknown_owner_step` — an ownership suggestion naming a missing or replaced step cannot be accepted.
- `test_create_does_not_infer_ownership_from_matching_titles` — similar concept and step titles remain unowned unless an explicit link is accepted.
- `test_create_allows_shared_explicit_ownership` — one concept may be explicitly assigned to more than one committed step without duplicate IDs within a step.
- `test_create_does_not_assign_deferred_step_as_owner` — a deferred or `wont_do` step cannot satisfy accepted delivery ownership.
- `test_create_yes_persists_unsigned_proposals` — `yes=True` keeps suggested concept decisions and ownership proposals unsigned.
- `test_create_non_tty_persists_unsigned_proposals` — non-TTY execution does not prompt or claim operator approval.
- `test_create_interactive_confirmation_persists_signed_review` — a scripted interactive confirmation produces the core’s signed result.
- `test_create_resume_reuses_valid_saved_concepts` — a valid saved record seeds review and avoids unnecessary enrichment.
- `test_create_surfaces_saved_concept_conflict` — stale or conflicting saved state follows the core conflict path and is not silently overwritten.
- `test_create_synchronizes_scope_before_placeholder_check` — the candidate body checked for `_(TODO)_` contains the core-synchronized scope sections.
- `test_create_finalizes_concepts_after_plan_write` — the authoritative record fingerprints the final parsed plan, not the pre-write or stub content.
- `test_create_core_sync_failure_writes_nothing` — a synchronization failure occurs before collision archival, plan publication, and manifest mutation.
- `test_distill_prompt_keeps_eight_keys_and_abstains_from_scope_decisions` — the prompt preserves the required JSON shape and directs the model not to become a second scope authority.

### Test-creation order (feature step)

Add each test with the create integration behavior it covers. Keep the existing distillation, body-synthesis, resume, gate-review, placeholder, collision, and post-write parse tests green throughout. Every new test and `uv run pytest tests/test_create.py -q` must pass before this step is considered finished.

## Acceptance criteria

- `plan_tool/create.py:create_plan` exposes an independent injected concept invoker using step 2’s shipped default.
- Create deterministically bootstraps concepts before optional enrichment and retains every deterministic concept when enrichment returns unusable output.
- Concept review runs after `_review_step_gates` and receives the settled proposed steps.
- Accepted included concept IDs are written only to explicit valid committed owners through `Step.concept_ids`.
- Matching prose or titles alone never establish ownership.
- `yes=True` and non-TTY runs persist unsigned proposals and never claim operator sign-off.
- Interactive confirmation follows the shipped core’s approval contract and persists the reviewed result.
- Core-synchronized scope sections reach `_find_placeholder_body_sections` and `write_new_plan` ahead of independently synthesized values.
- A core bootstrap, conflict, or synchronization failure cannot publish a plan through an empty or unreviewed concept record.
- The final concept record is synchronized and fingerprinted from the plan that successfully passes the existing post-write `parse_plan` check.
- `plan_tool/prompts/distill-seed.md` retains all eight single-plan section keys and does not independently decide concept-owned scope.
- `uv run pytest tests/test_create.py -q` passes.

## References

- [Structured outputs — Claude API Docs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs) — Use for the validated enrichment and ownership-suggestion response boundary.
- [Structured model outputs — OpenAI API](https://developers.openai.com/api/docs/guides/structured-outputs) — Use when implementing the equivalent injected backend response contract.
- [JSON Schema Validation: A Vocabulary for Structural Validation of JSON](https://json-schema.org/draft/2020-12/json-schema-validation) — Use for required fields, typed ownership arrays, identifiers, and uniqueness rules.

## Deferred

- **Detail-time concept scope, structured deferrals, and regeneration** — step 4 owns `plan_tool/detail.py` and its prompt and CLI integration.
- **Blocking uncovered, dangling, and invalid-owner findings** — step 5 owns deterministic completeness reporting; create establishes links but does not replace that audit.
- **Split ownership partitioning** — step 6 validates that every source concept ID survives across replacement steps.
- **Merge ownership unions** — step 7 combines source ownership without duplicates.
- **Re-ground ownership preservation** — step 8 carries explicit IDs through re-grounding.
- **Scope-out deferral for concepts with no surviving owner** — step 9 owns the concept-state and ownership changes for carved steps.
- **Automatic creation of covering steps** — excluded by the plan; unresolved concepts stay visible instead of causing create to invent implementation work.
