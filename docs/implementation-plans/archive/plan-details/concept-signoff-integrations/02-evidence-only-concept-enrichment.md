> **Auto-archived**: this plan was swept on 2026-07-16 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 2 — Add the evidence-only concept enrichment producer on the shipped core

## Summary

Add an evidence-only concept enrichment round-trip to the concept-record core shipped by the prerequisite plan. Extend `plan_tool/concept_tree.py` with a fail-soft producer that validates structured model output and merges valid candidates through the core’s public enrichment contract, and add its shared default invoker in `plan_tool/shell.py`. Create `plan_tool/prompts/concept-emit.md` and `tests/test_concept_emit.py`, then document the test seam in `TESTING.md:Backend fallback seams`. On green, supported evidence can add unsigned candidate concepts without replacing deterministic seeds, changing reviewed decisions, writing the sidecar, or inventing concepts absent from the evidence.

## Table of Contents

- [Summary](#summary) — The producer, prompt, invoker seam, and expected result.
- [Why](#why) — Why deterministic bootstrap needs bounded model enrichment.
- [Input](#input) — Contracts consumed from step 1 and the shipped concept-record core.
- [Files (creates vs edits)](#files-creates-vs-edits) — New and modified files in this step.
- [Implementation](#implementation) — Required producer, validation, merge, and failure behavior.
- [Tests](#tests) — Unit cases for evidence handling, merge safety, and backend isolation.
- [Acceptance criteria](#acceptance-criteria) — Observable completion conditions.
- [References](#references) — Authoritative structured-output and validation guidance.
- [Deferred](#deferred) — Integration and ownership work assigned to later steps.

## Why

The shipped concept-record core can bootstrap and review concepts deterministically, but deterministic sources cannot surface additional hierarchy or concepts that are stated elsewhere in supplied evidence. Create and detail need one reusable enrichment producer rather than separate model prompts or a second concept-tree implementation. The producer must remain subordinate to the core: model output may add evidence-backed, unsigned candidates, but it must not remove deterministic seeds, overwrite reviewed state, choose a re-derivation conflict, or persist independently.

## Input

- **Shipped concept-record core:** The plan’s execution prerequisite supplies the public `ConceptTree` and concept-node model in `plan_tool/concept_tree.py`, deterministic bootstrap and conflict-aware re-derivation, scoped review, synchronization, and persistence. Confirm the landed symbols and signatures at HEAD before implementing; use those public contracts instead of recreating their models or merge rules.
- **Step 1 ownership field:** Step 1 adds `plan_tool/schema.py:Step.concept_ids`. This producer does not assign those IDs to steps; later integrations consume its stable core concept IDs.
- **Deterministic seed:** Enrichment starts from a caller-supplied tree or candidate set produced by the shipped core. An empty model response or failed round-trip must leave that input unchanged.
- **Evidence envelope:** Callers supply the text to inspect and the small amount of plan context required by the prompt. The producer must not read arbitrary repository files or infer facts from a plan title alone.
- **Core decision state:** Existing IDs, source links, review/sign-off state, and conflict results remain authoritative. Model suggestions are candidates only and must use the core’s safe unreviewed defaults.

## Files (creates vs edits)

- **New files:**

  - `plan_tool/prompts/concept-emit.md` — define the bounded, JSON-only, evidence-only enrichment request and response shape.
  - `tests/test_concept_emit.py` — cover prompt rendering, structured parsing, safe merging, failure behavior, and the injected invoker seam.

- **Existing files (edits only):**

  - `plan_tool/concept_tree.py` — add the prompt renderer and public enrichment producer, using the shipped core types and merge contract.
  - `plan_tool/shell.py` — add the stdout-only default concept invoker that delegates to `claude_invoke`.
  - `TESTING.md` — add the producer to the `Backend fallback seams` neutralization table.

## Implementation

- **Make evidence-only enrichment the foundational logic.** Add a public producer in `plan_tool/concept_tree.py`, with a descriptive name such as `emit_concept_tree`, that follows this flow: render supplied evidence, invoke through an injected callable, validate the response, convert valid entries into core candidates, and merge them through the shipped core’s public enrichment or re-derivation contract. Return the resulting in-memory value; do not save it.

- **Verify the shipped merge surface before coding.** The prerequisite core is not present at the current planning checkout, so names beyond `ConceptTree` cannot be confirmed here. At implementation time, inspect the landed `plan_tool/concept_tree.py` and its bootstrap/re-derivation tests. If the core exposes no public way to add candidates while preserving existing decisions and reporting conflicts, stop and route that missing prerequisite back to the core plan; do not add a second merge algorithm inside this step.

- **Keep the producer fail-soft.** The public return must allow “no enrichment,” preferably `Optional[ConceptTree]` or the equivalent shipped outcome type. Empty stdout, malformed JSON, schema-invalid content, or unusable candidates return the no-enrichment result and never raise as part of normal model-output handling. This matches `plan_tool/create.py:propose_steps_from_claude`, whose invalid model response returns `None` so its caller can keep the deterministic path.

- **Do not persist inside the producer.** `plan_tool/concept_tree.py` may own the core’s save function, but the enrichment producer must not call it. Create, detail, and other orchestrators must remain responsible for coordinated persistence so one failed round-trip cannot publish a partial concept record.

- **Preserve deterministic and reviewed state.** A successful enrichment may add evidence-backed candidates or hierarchy permitted by the shipped merge contract. It must not:

  - remove or replace a deterministic seed omitted from the response;
  - change an existing stable ID;
  - overwrite a reviewed state, sign-off flag, source baseline, or conflict;
  - assign `Step.concept_ids`;
  - manufacture ownership or deferral links.

- **Use safe candidate defaults.** Every newly emitted concept must be unsigned and unreviewed according to the shipped core vocabulary. Treat any state-like model value as a suggestion, not operator sign-off. If the output includes an unknown suggested state, retain the evidence-backed concept under the core’s safe operator-visible default rather than dropping it; silent dropping would recreate the loss this producer is meant to prevent.

- **Validate the complete response shape.** `plan_tool/prompts/concept-emit.md` should request one JSON object containing a bounded concept collection with, at minimum, a title, suggested state, evidence rationale, and optional children or parent linkage compatible with the shipped core. Reject wrong top-level types, missing required fields, non-string titles or rationales, malformed children, and extra shapes that cannot be represented safely. Let the core create or validate stable IDs; never accept a model-supplied ID as authoritative.

- **Require evidence for every addition.** The prompt must state that candidates and rationales come only from `${evidence}`. A plan title may orient the response but is not evidence for adding a concept. Keep each rationale short and tied to supplied text; unsupported entries must be rejected or left out during conversion rather than merged.

- **Bound output size explicitly.** Set concrete depth and breadth limits in `plan_tool/prompts/concept-emit.md`, and enforce the same limits while parsing so prompt compliance is not the only guard. Choose limits that fit the shipped core’s tree shape and expose them as named constants in `plan_tool/concept_tree.py` rather than scattered numbers.

- **Render the prompt beside its owner.** In `plan_tool/concept_tree.py`, load `plan_tool/prompts/concept-emit.md` through `plan_tool/renderer.py:prompts_dir` and render its `${evidence}` and plan-context placeholders with `string.Template.safe_substitute`, following `plan_tool/detail.py:render_detail_prompt`. Do not edit `plan_tool/renderer.py`; it already supplies the shared prompt-directory resolver.

- **Route the default through the shared shell chokepoint.** Add `plan_tool/shell.py:shell_concept_invoker` as a stdout-only wrapper around `claude_invoke`, matching the wrapper contract described in `plan_tool/shell.py`’s `Public surface`. The producer takes a distinct `invoker=` keyword defaulting to that wrapper. Never call `subprocess` from `plan_tool/concept_tree.py`; delegation through `claude_invoke` preserves active-backend selection, retry handling, prompt-budget checks, and run-log events.

- **Keep the new seam independently injectable.** The concept call is separate from create and detail authoring calls, so callers must be able to stub it without also replacing their existing invokers. `TESTING.md:Backend fallback seams` should name the production call, `shell_concept_invoker` default, and a canned-JSON neutralization recipe.

- **Rely on inherited backend-gate coverage.** `tests/conftest.py:_no_real_claude_subprocess` already blocks every binary returned by `plan_tool.backend.py:registered_binaries`. Because `shell_concept_invoker` delegates to `plan_tool/shell.py:claude_invoke`, no conftest change is needed; add a focused regression proving the default path reaches that existing guard.

## Tests

Add these cases to `tests/test_concept_emit.py`:

- `test_render_concept_emit_prompt_includes_supplied_evidence` — the rendered prompt contains the evidence and states the JSON shape and configured depth and breadth limits.
- `test_emit_enriches_deterministic_tree` — valid nested output adds evidence-backed candidates through the shipped core merge contract without removing seed nodes.
- `test_emit_preserves_existing_reviewed_decisions` — a response that repeats or conflicts with a reviewed node does not overwrite its ID, state, sign-off, or source data.
- `test_emit_does_not_trust_model_ids` — a model-supplied identifier is rejected or ignored in favor of the core’s identity contract.
- `test_emit_additions_are_unsigned` — every new candidate uses the shipped core’s unreviewed and unsigned defaults.
- `test_emit_maps_unknown_state_to_safe_visible_default` — an unsupported suggested state retains the concept under the core’s safe default rather than dropping it.
- `test_emit_rejects_unsupported_claim_without_evidence` — an entry without the required evidence rationale is not merged.
- `test_emit_enforces_depth_and_breadth_limits` — oversized output cannot bypass the parser-side bounds.
- `test_emit_returns_none_on_empty_or_invalid_output` — empty stdout, prose, malformed JSON, and schema-invalid JSON produce no enrichment and do not raise.
- `test_emit_failure_leaves_input_unchanged` — a failed round-trip does not mutate the caller’s seed tree.
- `test_emit_does_not_persist` — invoking the producer creates or rewrites no concept sidecar.
- `test_emit_uses_injected_invoker_once` — a canned invoker receives the rendered prompt once and no shell call occurs.
- `test_default_invoker_uses_real_backend_gate` — the unoverridden default reaches the existing registered-backend subprocess guard.
- `test_shell_concept_invoker_returns_stdout` — `plan_tool/shell.py:shell_concept_invoker` discards the exit code and returns the stdout from a stubbed `claude_invoke`.
- `test_same_seed_and_response_are_deterministic` — repeated enrichment from equal inputs produces equal candidate order and stable core IDs.

### Test-creation order (feature step)

Add prompt-rendering and parser-validation tests with the response-shape implementation. Add preservation, no-mutation, and no-persistence tests with the core merge integration, then add injected/default invoker tests with `plan_tool/shell.py:shell_concept_invoker`. Every new test in `tests/test_concept_emit.py` must be green before this step is considered finished, and the shipped core’s concept-tree and bootstrap regression tests must remain green.

## Acceptance criteria

- `plan_tool/concept_tree.py` exposes an evidence-only producer with a distinct injected `invoker=` seam and a fail-soft no-enrichment result.
- `plan_tool/shell.py:shell_concept_invoker` delegates to `claude_invoke` and returns stdout without spawning a backend directly.
- `plan_tool/prompts/concept-emit.md` requests JSON-only, evidence-backed candidates and states concrete depth and breadth limits.
- Valid output enriches the caller’s deterministic seed through the shipped core contract while preserving every existing ID, reviewed decision, sign-off value, and conflict.
- Empty, malformed, unsupported, or over-limit output does not raise, persist, or mutate the supplied tree.
- Every new model-produced concept remains unsigned and unreviewed; an unknown suggested state does not silently drop the concept.
- The producer never writes the concept sidecar and never assigns `Step.concept_ids`.
- `TESTING.md:Backend fallback seams` documents how to replace the concept producer’s default invoker in tests.
- `tests/test_concept_emit.py` passes, along with the shipped core’s concept-tree and bootstrap test suites.

## References

- [Structured outputs — Claude API Docs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs) — Use the response-schema and invalid-output guidance when defining the concept candidate envelope.
- [Structured model outputs — OpenAI API](https://developers.openai.com/api/docs/guides/structured-outputs) — Keep the injected backend compatible with schema-conforming structured responses.
- [JSON Schema Validation: A Vocabulary for Structural Validation of JSON](https://json-schema.org/draft/2020-12/json-schema-validation) — Use its object, array, required-field, type, and uniqueness semantics for local response validation.

## Deferred

- **Create integration and explicit step ownership** — step 3 invokes the producer, reviews the result, and assigns stable concept IDs to steps.
- **Structured detail deferrals and include-time regeneration** — step 4 consumes the signed-off record and ownership links.
- **Missing-owner completeness findings** — step 5 compares signed-off concepts with explicit ownership and structured deferrals.
- **Split, merge, re-ground, and scope-out preservation** — steps 6–9 own those operation-specific transformations.
- **Changing signed-off concept content** — the plan explicitly excludes revising the signed-off concept set; this producer only proposes unsigned enrichment.
- **Automatic conflict resolution** — the shipped core keeps re-derivation conflicts explicit, and this producer must not choose a winner.
