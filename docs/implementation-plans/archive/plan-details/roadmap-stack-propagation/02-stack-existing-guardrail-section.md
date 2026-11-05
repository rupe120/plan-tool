> **Auto-archived**: this plan was swept on 2026-11-05 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 2 — Add `Stack` to the guardrail-section mechanism

<!-- plan-tool:detail-format-version: 1 -->

## Summary

`Stack` is added as the fourth, last entry of `GUARDRAIL_BODY_SECTIONS` in `plan_tool/scope_fence.py`. It is also added to `OPTIONAL_PLAN_BODY_SECTION_SHAPES` in `plan_tool/create.py`, and both prompts list it as a recognized optional key. `create` then treats `## Stack` like `## Scope guardrails`. The seed's body is captured before distillation, replaces model output in the rendered plan, and reaches detail prompts through `extract_plan_guardrails` and `render_scope_fence`. A seed with no `## Stack` produces a plan with no stack section and no fence entry. On green, a seed's `## Stack` text appears verbatim in the plan and in the detail fence, after `Expected placement` and before `Out of scope`. Tests that pinned the three-heading set are updated, and one test pins the new order.

## Table of Contents

- [Why](#why) — what is lost between seed and plan today
- [Input](#input) — the seed section this step reads
- [Files (creates vs edits)](#files-creates-vs-edits) — the footprint
- [Implementation](#implementation) — the sweep, the order, and the gotchas
- [Tests](#tests) — the roster and the green-before-done gate
- [Acceptance criteria](#acceptance-criteria) — observable checks
- [Applicable guardrails](#applicable-guardrails) — the plan fence as it binds this step
- [Deferred](#deferred) — items left out

## Why

Step 1 puts a tool-rendered `## Stack` section in each draft seed. `create` only preserves headings listed in `GUARDRAIL_BODY_SECTIONS`. Without `Stack` in that list, distillation or synthesis can drop or reword the section, and the derived plan can pick its own store (SQLite instead of the roadmap's PostgreSQL). Detail prompts read the plan body through `extract_plan_guardrails`, so a stack the plan lost never reaches them. Reusing the existing mechanism is the smallest change that carries the stack from the seed to detail.

## Input

- **Seed section (step 1):** step 1 writes one `## Stack` H2 per draft seed, rendered from the accepted hosting and store rows. This step reads that section as opaque text. It does not parse its rows or compare them to anything.
- **Existing readers:** `plan_tool/create.py:_extract_supplied_guardrails` reads recognized headings from the original seed through `extract_h2_sections(..., ignore_fenced_code=True)`. It keys on `GUARDRAIL_BODY_SECTIONS`.
- **Absent section:** drafts and promoted seeds written before step 1 have no `## Stack`. The helper then returns nothing for `Stack`, and nothing is rendered.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/scope_fence.py` — append `"Stack"` as the last entry of `GUARDRAIL_BODY_SECTIONS`. Update the module docstring and the comment above the tuple, which both say "three".
  - `plan_tool/create.py` — add a `"Stack"` entry to `OPTIONAL_PLAN_BODY_SECTION_SHAPES`, after `"Expected placement"`. Write it like the three existing shapes: conditional, source-backed, preserve the supplied body verbatim, do not invent or revise stack decisions. Sweep any other site that spells out the three headings.
  - `plan_tool/prompts/synthesize-body.md` — add `Stack` to both lists of recognized optional keys.
  - `plan_tool/prompts/distill-seed.md` — add `Stack` to its list of recognized optional keys.
  - `tests/test_scope_fence.py` — add the `Stack` cases and update the tests that pin the three-heading set.
  - `tests/test_create.py` — add the `Stack` cases and update the tests that pin the three-heading set.

## Implementation

**Intended behavior**

- **Same path as the other guardrails.** `Stack` is not a new mechanism. Adding it to `GUARDRAIL_BODY_SECTIONS` and `OPTIONAL_PLAN_BODY_SECTION_SHAPES` is the main change. These sites already loop over the tuple:
  - `_extract_supplied_guardrails`, which captures the seed bodies before distillation.
  - The two helpers that report guardrail headings dropped or invented by a lossy stage: `_find_dropped_guardrail_headings` and `_find_uncarried_guardrail_headings`. Confirm the first name against HEAD.
  - The plan-body renderer's guardrail loop, which emits each supplied body after `Architecture` and `Input`.
  - The synthesis step that collects `synthesized_guardrail_bodies`.
  - `plan_tool/scope_fence.py:extract_plan_guardrails`, which iterates `(*GUARDRAIL_BODY_SECTIONS, *_DETAIL_FENCE_SECTIONS)`.
- **Order.** `Stack` goes last in `GUARDRAIL_BODY_SECTIONS`. The `create.py` render order and the fence order follow the tuple. The fence order must be Scope guardrails, Audit guardrails, Expected placement, Stack, Out of scope. Do not add a second ordering list.
- **Override, not merge.** The seed body replaces any model-authored `Stack` text in the rendered plan, as it does for the other three. Keep that behavior and do not special-case `Stack`.
- **Placeholder rule.** A `Stack` body that is only `_(TODO)_` stays out of the fence, through the existing `_is_placeholder_section` check. No new code is needed.
- **Prompts.** Add `Stack` to the recognized optional keys in both prompts. Say that it is preserved verbatim when the seed has the heading, and that the model must not author one. Reword the two prompt lists so the counts and enumerations stay accurate.
- **Sweep first.** Before editing, run two searches and write down what they return:
  - By identifier: `GUARDRAIL_BODY_SECTIONS`, `OPTIONAL_PLAN_BODY_SECTION_SHAPES`, and `_OPTIONAL_PLAN_BODY_SECTIONS` across `plan_tool/` and `tests/`.
  - By vocabulary: `Scope guardrails`, `Audit guardrails`, and `Expected placement` spelled out together, in `plan_tool/*.py`, `plan_tool/prompts/*.md`, and the tests.

  Edit every site that belongs to the create-to-fence path. Say per remaining site why it stays. The known leftover sites are in Deferred.
- **Rejected alternative:** a separate `Stack` field on `Plan`, or a dedicated parser in `create.py`. The guardrail path already preserves a verbatim body and threads it to detail. A new field would need a schema change the plan does not authorize.
- **Not free to vary:**
  - `plan_tool/scope_fence.py` stays a leaf that imports only the stdlib.
  - `plan_tool.create` and `plan_tool.detail` keep re-exporting `GUARDRAIL_BODY_SECTIONS` as the same object. `tests/test_scope_fence.py` already asserts this identity.
  - `_load_roadmap_research_targets` keeps supplying product research only. This step does not touch it.

## Tests

Tests are in `tests/test_scope_fence.py` and `tests/test_create.py`.

### Tests for this step

New tests:

- `test_stack_is_the_fourth_guardrail_heading_in_contract_order` — `GUARDRAIL_BODY_SECTIONS` ends with `Stack`, after `Expected placement`.
- `test_fence_renders_stack_after_expected_placement_and_before_out_of_scope` — a plan carrying all five sections renders them in fence order whatever order the plan body holds them in. This is the one order-pinning test.
- `test_stack_section_is_threaded_into_the_detail_fence` — `extract_plan_guardrails` and `render_scope_fence` include a non-empty `## Stack` body.
- `test_placeholder_stack_is_omitted_from_the_fence` — a `_(TODO)_` `Stack` body adds nothing to the fence.
- `test_plan_without_stack_section_carries_no_stack_in_the_fence` — the absent-section case: output has no `Stack` text and the other three guardrails are unaffected.
- `test_stack_body_is_preserved_verbatim_through_create` — a seed `## Stack` body appears unchanged in the written plan, even when the model response supplies a different `Stack` body.
- `test_seed_without_stack_produces_no_stack_section_in_the_plan` — the absent-section case through `create`: no `## Stack` heading and no `_(TODO)_` stub is written.
- `test_stack_is_captured_before_distillation_and_not_invented_by_it` — a stage output that adds a `Stack` the seed lacks is reported through the existing uncarried-guardrail path, and a seed `Stack` the stage drops is reported through the dropped path.
- `test_stack_is_a_recognized_optional_key_in_both_prompts` — `synthesize-body.md` and `distill-seed.md` name `Stack` as a recognized optional key, asserted by key, not by a loose substring.

Updated tests: every test that pins the three-heading set must include `Stack`, or the sibling case it governs must be rewritten. The known ones in `tests/test_create.py` are the guardrail-order case near the `"Scope guardrails", "Audit guardrails", "Expected placement"` tuples and the optional-key assertions in the preparation-prompt tests. The `GUARDRAIL_BODY_SECTIONS` identity test in `tests/test_scope_fence.py` should still pass unchanged. A sibling test that turns red is expected. Read each one and decide whether it is a missed site or a real carve-out. Do not narrow the change to keep it green.

**Green-before-done gate:** every test above, plus the existing `tests/test_scope_fence.py` and `tests/test_create.py`, must be green before this step is finished. Run `uv run pytest tests/test_scope_fence.py tests/test_create.py -q`. Check the new tests by mutation: drop `"Stack"` from the tuple and watch the order, fence, and preservation tests go red.

## Acceptance criteria

- `GUARDRAIL_BODY_SECTIONS` equals `("Scope guardrails", "Audit guardrails", "Expected placement", "Stack")`.
- A seed with `## Stack` yields a plan whose `## Stack` body is the seed's text, unchanged, even when the model supplies different text.
- `extract_plan_guardrails` on that plan includes `## Stack`, positioned after `## Expected placement` and before `## Out of scope`.
- A seed with no `## Stack` yields a plan with no `Stack` heading and no `Stack` text in the fence.
- Both prompts name `Stack` as a recognized optional key. Neither tells the model to author one.
- `rg -n "Scope guardrails.*Audit guardrails.*Expected placement" plan_tool/scope_fence.py plan_tool/create.py plan_tool/prompts/synthesize-body.md plan_tool/prompts/distill-seed.md` returns no list that omits `Stack`.
- `plan_tool/scope_fence.py` still imports only the stdlib.
- `uv run pytest tests/test_scope_fence.py tests/test_create.py -q` passes.

## Applicable guardrails

- **The plan's "## Out of scope" (conflict surfacing, notes, or technology-name comparison):** this step only carries the `Stack` text. It must not parse rows, compare technology names, or warn about conflicts in `create` or `detail`.
- **The plan's "## Out of scope" (Jira handoff):** this step must not edit the Jira handoff's section whitelist in `plan_tool/jira_handoff.py`.
- **The plan's "## Out of scope" (plan audit and cross-plan audit):** this step must not change `plan_tool/prompts/plan-audit.md` or add an audit check. The plan audit as the contradiction check is a separate piece of the plan.
- **Plan-level proportionality:** the step reuses the guardrail path. It adds no new field, parser, config knob, or parallel section mechanism.

## Deferred

- `plan_tool/prompts/plan-audit.md` guardrail wording — it names the three headings and sits outside this step's file list. It belongs to the plan's audit-side work, not the create-to-fence path.
- `plan_tool/jira_handoff.py` section whitelist — carrying `## Stack` into the Jira handoff is out of scope in the plan's fence, and the whitelist omits it on purpose.
- Fence content for existing plans — correcting plans or drafts written before this change is out of scope in the plan's fence. They carry no stack commitment.
