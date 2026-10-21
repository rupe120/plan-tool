> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 1 — Extend combined and split create guidance to classify reach from the focused property and leave required shared work out, with focused prompt tests

## Summary

Add the same three-route mechanism-reach decision to create’s inline proposal, body-synthesis, and split foundational-sweep guidance. Update `plan_tool/create.py`, `plan_tool/prompts/synthesize-body.md`, and `plan_tool/prompts/foundational-logic-sweep.md` without changing create’s CLI flow, response schemas, or sweep merge behavior. The split sweep receives the original focused description alongside the proposed-step boundary before it recommends a shared-location action. On green, focused create runs preserve suitable reuse, allow compatible local work, and leave required shared semantic changes out of the plan.

## Table of Contents

- [Summary](#summary) — The change and its observable result.
- [Table of Contents](#table-of-contents) — Links to each detail section.
- [Why](#why) — The current authoring gap this step closes.
- [Input](#input) — Existing prompt and sweep contracts that remain stable.
- [Files (creates vs edits)](#files-creates-vs-edits) — Files edited by this step.
- [Implementation](#implementation) — Required prompt and context changes.
- [Tests](#tests) — Focused prompt-contract coverage.
- [Acceptance criteria](#acceptance-criteria) — Reviewable completion checks.
- [References](#references) — Prompt and pytest documentation.
- [Applicable guardrails](#applicable-guardrails) — Scope limits that bind this work.
- [Deferred](#deferred) — Follow-up work outside this step.

## Why

`plan_tool/create.py:_render_from_prompt` currently treats shared logic as a candidate for adding files or a consolidation step, while `plan_tool/create.py:_render_sweep_context` gives split mode only the proposed steps. `plan_tool/prompts/synthesize-body.md` also has proportionality guidance but no explicit way to distinguish ordinary use of a common owner from a required change to that owner’s semantics. The prompts need one clear decision rule so file sharing, caller count, or duplicate-looking code does not widen a focused plan or cause a local copy of a suitable shared structure.

## Input

- **Initial-step proposal contract:** `plan_tool/create.py:_render_from_prompt` and `_STEP_PROPOSAL_RESPONSE_CONTRACT` continue to use the existing step-list shape. This step must not add a route field or another response key.
- **Split-sweep contract:** `plan_tool/create.py:propose_steps_from_claude` calls `_render_sweep_context` before `plan_tool/foundational_logic.py:run_foundational_logic_sweep`. The context must include the original description and the proposed steps, while `plan_tool/foundational_logic.py:_SWEEP_RESPONSE_CONTRACT` remains unchanged.
- **Body-synthesis contract:** `plan_tool/create.py:_render_synthesis_prompt` supplies the seed, confirmed project context, repository evidence, and canonical section catalog to `plan_tool/prompts/synthesize-body.md`. Add guidance within that existing context; do not add a decision section or persisted route state.
- **Fail-closed merge behavior:** `plan_tool/foundational_logic.py:merge_sweep_into_steps` already mutates only `update-in-place` locations and consolidation suggestions. A `defer` result must remain a no-op for the focused plan.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `plan_tool/create.py` — update `_PROPOSAL_FOUNDATIONAL_ITEM`, `_render_from_prompt`, and `_render_sweep_context`; pass the focused description from `propose_steps_from_claude` into split-sweep context.
  - `plan_tool/prompts/synthesize-body.md` — add the mechanism-reach decision to the synthesis rules.
  - `plan_tool/prompts/foundational-logic-sweep.md` — require sweep recommendations to classify semantic reach from the focused property and supplied boundary.
  - `tests/test_create.py` — add prompt and split-context assertions.
  - `tests/test_foundational_logic.py` — add sweep-prompt and fail-closed `defer` assertions.

## Implementation

- **Classify reach by the focused property.** In the combined proposal guidance at `plan_tool/create.py:_PROPOSAL_FOUNDATIONAL_ITEM`, the body-synthesis rules in `plan_tool/prompts/synthesize-body.md`, and the split-sweep instructions in `plan_tool/prompts/foundational-logic-sweep.md`, require the same ordered decision:
  1. Reuse a current common owner unchanged when its existing contract already makes the focused property true.
  2. Otherwise, allow the smallest local adapter or bounded additive extension when existing consumer behavior and schema interpretation stay unchanged.
  3. Otherwise, treat the necessary shared semantic change as separate work and leave it out of the focused plan.

- **Keep both compatible focused routes available.** An available local adapter must not rule out a bounded additive extension that preserves the existing contract. Likewise, common ownership must not force a local duplicate when unchanged reuse already satisfies the property.

- **Reject structural proxies as reach evidence.** A shared path, duplicate, parallel caller, relation label, or number of consumers must trigger inspection of the owner, not prove that the focused plan needs a shared update or consolidation.

- **Give split mode the property it must classify.** Extend `plan_tool/create.py:_render_sweep_context` so the context rendered by `plan_tool/create.py:propose_steps_from_claude` includes the original description plus each proposed step’s declared boundary. The context must let `plan_tool/prompts/foundational-logic-sweep.md` compare a find with the requested property and enforcement boundary instead of inferring reach from titles and file lists.

- **Keep split-create deferral fail-closed.** The sweep prompt must direct a required shared semantic change to `defer`. That recommendation must not add a step, file, consolidation suggestion, plan-body entry, or durable handoff. Preserve `plan_tool/foundational_logic.py:merge_sweep_into_steps` and prove its existing no-op behavior for a `defer` finding.

- **Keep this as prompt guidance only.** Do not change CLI mode selection, `_STEP_PROPOSAL_RESPONSE_CONTRACT`, `plan_tool/foundational_logic.py:_SWEEP_RESPONSE_CONTRACT`, `SharedLocation`, `SweepResult`, or merge mechanics. Do not add a numeric threshold, schema field, automatic rewrite, or generic scope-control layer.

- **Use focused contract tests.** Place assertions beside `TestRenderFromPromptABMode` and `TestRefactorBoundaryProposalGuidance` in `tests/test_create.py`, and beside the prompt and merge tests in `tests/test_foundational_logic.py`. One way is to parameterize the combined and split create arms where the expected text is identical.

## Tests

### Tests for this step

- `test_create_prompt_states_all_three_mechanism_reach_routes` — both `_render_from_prompt` arms permit unchanged common-owner reuse and compatible focused local work, while routing a required shared semantic change out of the focused plan.
- `test_synthesis_prompt_states_all_three_mechanism_reach_routes` — the prompt from `plan_tool/create.py:_render_synthesis_prompt` applies the same routes without inventing a body section or route field.
- `test_split_sweep_context_includes_focused_description_and_step_boundary` — `plan_tool/create.py:_render_sweep_context` includes the original focused description and proposed-step files and creates.
- `test_split_sweep_prompt_classifies_semantic_reach_not_file_count` — `plan_tool/foundational_logic.py:render_foundational_logic_prompt` treats a shared-location relation as inspection evidence and retains all three reach routes.
- `test_split_create_defer_does_not_expand_steps_or_files` — `plan_tool/foundational_logic.py:merge_sweep_into_steps` leaves the proposed steps unchanged for a `defer` location with no consolidation suggestion.

Every listed test must be green before this step is complete.

## Acceptance criteria

- Both rendered `_render_from_prompt` modes contain the three mechanism-reach routes and do not treat shared files or caller count as proof of shared semantic reach.
- The rendered synthesis prompt applies the same three routes without adding a new canonical body key or a route carrier.
- Split-sweep context contains the focused description and proposed-step boundary before `render_foundational_logic_prompt` classifies shared locations.
- The sweep prompt permits `update-in-place` only for compatible focused local work and directs required shared semantic changes to `defer`.
- A `defer` sweep result adds no step, file, consolidation, plan-body entry, or durable handoff.
- `tests/test_create.py` and `tests/test_foundational_logic.py` pass with the new focused coverage.

## References

- [Prompt engineering overviewhttps: — Use for clear task framing and measurable prompt outcomes.
- [Prompting best practiceshttps: — Use for explicit scope rules and constrained model instructions.
- [Define success criteria and build evaluationshttps: — Use for prompt-contract test design.
- [How to parametrize fixtures and test functionshttps: — Use for shared assertions across combined and split create routes.
- [How to write and report assertions in testshttps: — Use for concise failure messages in prompt tests.

## Applicable guardrails

- **The plan’s “## Scope guardrails,” semantic-reach rule** — these prompts may distinguish reuse, compatible focused work, and separate shared work, but they must not make shared placement itself a widening signal.
- **The plan’s “## Scope guardrails,” split-create boundary** — preserve the existing sweep schema and merge mechanics; `defer` must leave no durable record or focused-plan mutation.
- **The plan’s “## Out of scope,” mechanism limits** — restrict implementation to authoring guidance and its tests; do not add a runtime mechanism, automatic split, or broader control framework.

## Deferred

- `plan_tool/detail.py`, `plan_tool/prompts/detail.md`, and `tests/test_detail.py` — step 2 applies the same rule to combined and split detail authoring.
- BACKLOG #336 manual split-create handoff — owns durable operator-visible follow-up for a correctly deferred shared semantic change.
- BACKLOG #335 mechanism-reach audit lens — owns the later manual audit surface for explicit unjustified shared commitments.
