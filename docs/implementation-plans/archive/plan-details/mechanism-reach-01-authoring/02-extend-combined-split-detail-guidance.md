> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 2 — Extend combined and split detail guidance to apply unchanged reuse, bounded local changes, or separate shared work, with focused prompt tests

## Summary

Extend detail authoring prompts with one mechanism-reach rule for both combined and split modes. Update the mode-specific guidance in `plan_tool/detail.py`, the shared authoring instructions in `plan_tool/prompts/detail.md`, and focused prompt-contract tests in `tests/test_detail.py`. The key decision is based on whether the focused property needs a shared semantic change, not on a shared file’s presence or a sweep relation. On green, detail drafts preserve suitable reuse, allow bounded compatible local work, and leave required shared semantic work outside the focused plan.

## Table of Contents

- [Summary](#summary) — The change and its reviewable result.
- [Table of Contents](#table-of-contents) — Links to the detail sections.
- [Why](#why) — The authoring gap this step closes.
- [Input](#input) — Existing mode and sweep contracts this step reads.
- [Files (creates vs edits)](#files-creates-vs-edits) — Files changed by this step.
- [Implementation](#implementation) — The mechanism-reach guidance and compatibility limits.
- [Tests](#tests) — Focused prompt-contract coverage.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Prompt and pytest references.
- [Applicable guardrails](#applicable-guardrails) — Plan boundaries that constrain this work.
- [Deferred](#deferred) — Work this prompt-only step leaves out.

## Why

`plan_tool/detail.py:_DETAIL_FOUNDATIONAL_COMBINED_DIRECTIVE` tells combined authoring how to find related logic, while `_DETAIL_FOUNDATIONAL_SPLIT_DIRECTIVE` tells split authoring how to place sweep results, but neither gives both paths the same clear rule for deciding whether a shared location is already suitable, safely extendable locally, or a separate shared concern. Without that rule, a shared path or sweep finding can make a focused detail draft widen itself or duplicate a usable owner.

## Input

- **Step 1 outcome:** Step 1 establishes the same mechanism-reach decision for create authoring. This step carries that decision into detail authoring without changing create behavior.
- **Mode contract:** `plan_tool/detail.py:render_detail_prompt` keeps combined mode’s inline search and split mode’s injected `foundational_logic_block`; this step does not add prompt variables, CLI flags, or response fields.
- **Sweep context:** `plan_tool/detail.py:_render_step_sweep_context` currently supplies a split sweep only the step title, files, and creates. Before `run_foundational_logic_sweep`, both detail paths will render the existing per-step `render_scope_fence` block and include it in that context. `plan_tool/foundational_logic.py:format_foundational_logic_block` can then provide shared locations tagged with existing recommendations; treat those tags as evidence to consider, not proof that a focused detail must edit a shared owner.
- **Test limit:** Rendered-prompt tests prove that the authoring contract contains the required rule. They cannot prove a model follows the rule for real briefs.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `plan_tool/detail.py` — extend `_DETAIL_FOUNDATIONAL_COMBINED_DIRECTIVE` and `_DETAIL_FOUNDATIONAL_SPLIT_DIRECTIVE` so both modes state the same three reach routes. Extend `_render_step_sweep_context` to render the supplied scope-fence block, and in `_generate_detail_concurrent` and the serial `generate_detail` loop render that block before `run_foundational_logic_sweep`, then pass the same block into the authoring prompt.
  - `plan_tool/prompts/detail.md` — reinforce the route rule at the existing `${foundational_audit_directive}` and scope guidance seams without changing the produced-detail structure.
  - `tests/test_detail.py` — extend `TestRenderDetailPromptABMode` with focused combined and split prompt assertions.

## Implementation

- **Classify reach from the focused property.** Update the authoring guidance so a shared path, helper, caller count, or sweep relation does not alone make work shared.

- **Reuse a suitable owner unchanged.** Tell detail authors to retain an existing shared structure when it already makes the focused property true. Do not recommend a local copy merely to make the plan appear self-contained.

- **Allow only bounded local work.** Permit a local adapter or additive extension when it preserves existing consumer behavior and current schema interpretation. Keep the resulting detail within the step’s declared scope; do not turn compatibility into a reason to revise unrelated consumers.

- **Separate required shared semantic work.** When the focused property requires changing shared authority or other existing shared semantics, require the detail draft to leave that work out of the focused implementation and identify it as separate intentional work in its existing `## Deferred` channel. Do not add a plan step, durable handoff, or shared-work mechanism in this step.

- **Apply the same decision in both modes.** `plan_tool/detail.py:render_detail_prompt` must give combined mode the rule while it searches and split mode the same rule while it places `Foundational-logic finds`. Split mode must not re-run the search, and combined mode must retain its existing purity self-check.

- **Ground the split sweep before classification.** In `_generate_detail_concurrent` and the serial `generate_detail` loop, render the per-step scope fence before the optional split sweep. Pass that block to `_render_step_sweep_context`, which appends it as the focused property and enforcement boundary alongside the step’s title, files, and creates. Reuse the same rendered block later in `render_detail_prompt`; do not add a prompt field, result field, route carrier, or second fence rendering contract.

- **Preserve the authoring contract.** Keep `render_detail_prompt`’s signature, the split-mode selection, the foundational sweep response shape, required detail headings, and deferral envelope unchanged. The prompt text is the appropriate change surface; do not change merge behavior or create a route field.

- **Keep one clear wording source.** Use the existing mode directives for mode-specific behavior and use `plan_tool/prompts/detail.md` only for shared authoring and scope framing, so the two modes cannot drift into different route rules.

## Tests

- `TestRenderDetailPromptABMode.test_combined_guidance_names_reuse_local_and_separate_routes` — asserts combined rendering names unchanged reuse, bounded local work, and separate shared semantic work while retaining the inline search instruction.
- `TestRenderDetailPromptABMode.test_split_guidance_names_reuse_local_and_separate_routes` — asserts split rendering carries the same route rule alongside injected findings.
- `TestRenderDetailPromptABMode.test_split_guidance_does_not_repeat_the_foundational_search` — asserts split rendering still places prior findings without telling the author to search again or restoring the purity self-check.
- `TestRenderDetailPromptABMode.test_shared_location_alone_does_not_require_shared_work` — asserts the rendered guidance rejects file sharing and sweep classification as sufficient reasons to widen a focused detail.
- `TestRenderDetailPromptABMode.test_existing_prompt_structure_remains_unchanged` — keeps the existing required-heading and unresolved-placeholder checks green after the wording changes.
- `TestGenerateDetailHappyPath.test_foundational_invoker_receives_per_step_scope_fence` — captures the serial split-sweep prompt and proves it contains the plan intent and current step intent before classification.
- `TestGenerateDetailConcurrent.test_foundational_invoker_receives_per_step_scope_fence` — runs the existing concurrent lifecycle with a sweep invoker and proves each captured split-sweep prompt contains its own step intent rather than a title-and-path-only context or a sibling’s fence.

### Tests for this step

Every listed test in `tests/test_detail.py` must be green before this step is done. Run the focused class during development and the affected `tests/test_detail.py` coverage before handoff.

## Acceptance criteria

- Combined detail prompts direct authors to choose unchanged reuse, bounded compatible local work, or separate shared work based on semantic reach.
- Split detail prompts apply the same rule to `Foundational-logic finds` without repeating the foundational search.
- Before a split-detail sweep classifies a shared-location find, both serial and concurrent paths supply the rendered per-step scope fence containing the focused property and enforcement boundary.
- A shared file, helper, or sweep relation alone does not instruct authors to widen the focused detail.
- Required shared semantic changes remain outside the focused detail and use the existing reconcile-only deferred path.
- `plan_tool/detail.py:render_detail_prompt` keeps its current signature and mode behavior.
- The focused `TestRenderDetailPromptABMode` cases in `tests/test_detail.py` pass.

## References

- [Prompt engineering overviewhttps: — Use it to keep prompt changes tied to clear success criteria.
- [Prompting best practiceshttps: — Use it for concise scope and decision guidance.
- [How to write and report assertions in testshttps: — Use it for precise rendered-prompt assertions.

## Applicable guardrails

- **The plan’s “## Plan intent”, smallest owner rule:** Limit this step to authoring guidance that selects the smallest suitable owner; do not add runtime ownership behavior.
- **The plan’s “## Scope guardrails”, shared semantic reach:** Keep a required shared semantic change out of the focused detail rather than hiding it behind a local prompt recommendation.
- **The plan’s “## Scope guardrails”, authoring-mode boundary:** Preserve mode selection, sweep schema, and merge mechanics; the prompt guidance makes the reach decision from existing context.
- **The plan’s “## Out of scope”, audit and automation work:** Do not add an audit finding, automatic rewrite, automatic split, or durable handoff surface.

## Deferred

- **Durable split-create handoff:** BACKLOG #336 owns a record or follow-up-plan capability; this step only teaches detail authors how to leave required shared work outside the focused detail.
- **Measured real-model adherence:** Prompt-contract tests cannot measure first-attempt route selection across real briefs, so model-quality measurement remains outside this hermetic test step.
