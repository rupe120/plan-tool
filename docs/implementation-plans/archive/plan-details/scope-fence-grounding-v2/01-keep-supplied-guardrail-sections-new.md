# Step 1 — Keep supplied guardrail sections in new plans

## Summary

Preserve supplied `Scope guardrails`, `Audit guardrails`, and `Expected placement` sections when `plan-tool create` builds a new plan from seed prose. Update `plan_tool/create.py` plus the distill and synthesis prompt contracts so the three recognized sections remain separate, optional plan-body sections rather than being dropped or folded into generated prose. Give author-supplied guardrail text precedence over distill and synthesis output, while keeping the plan body closed to unknown headings. On green, a seed that contains these sections produces a new plan containing the same sections and text; a seed without them gains none.

## Table of Contents

- [Summary](#summary) — The preservation behavior delivered by this step.
- [Table of Contents](#table-of-contents) — Links to each detail section.
- [Why](#why) — Why supplied scope fences must survive plan creation.
- [Input](#input) — The seed-section contract this step consumes.
- [Files (creates vs edits)](#files-creates-vs-edits) — Existing files changed by the work.
- [Implementation](#implementation) — The guardrail preservation rule and integration points.
- [Tests](#tests) — Focused regression coverage.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [Deferred](#deferred) — Related work owned by later steps.

## Why

`plan_tool/create.py:create_plan` can replace the seed with distilled prose before it renders the final body, while the current closed body-section contracts only recognize `Input` as optional. That leaves supplied guardrails vulnerable to being omitted or rewritten even though they state the boundary later planning and audit work must honor.

## Input

- **Seed H2 sections** — Read the seed through `plan_tool/create.py:extract_h2_sections`, which normalizes heading names and returns their non-empty bodies.
- **Recognized guardrails** — Treat only `Scope guardrails`, `Audit guardrails`, and `Expected placement` as supported conditional sections. Preserve their supplied bodies; do not treat arbitrary seed H2 headings as optional plan sections.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `plan_tool/create.py` — recognize supplied guardrail sections, preserve them across distill and synthesis, and render them separately in the final body.
  - `plan_tool/prompts/distill-seed.md` — describe the recognized optional guardrail keys and their preservation-only rule.
  - `plan_tool/prompts/synthesize-body.md` — describe the same optional keys and prevent generated replacements for supplied guardrails.
  - `tests/test_create.py` — cover parsing, prompt contracts, rendering, and end-to-end creation from guardrail-bearing seeds.

## Implementation

- **Foundational logic: preserve supplied guardrail sections.** Keep the three recognized guardrail headings and their author-supplied bodies available from the original seed before `create_plan` rebinds `seed_body` to a `DistillOutcome.distilled` result.

- **Use one recognized-name rule.** Extend the optional-section handling rooted at `OPTIONAL_PLAN_BODY_SECTION_SHAPES`, `_render_section_shapes_block`, `_parse_body_sections_json`, `_validate_distilled_sections`, `_render_distilled_markdown`, and `_render_plan_body` so the same three names are accepted consistently. A shared collection is preferable to repeating the names across parser and renderer branches.

- **Make supplied text authoritative.** When a recognized guardrail section exists in the original seed, render that supplied body under its own H2 heading even if distillation or `propose_body_sections` returns a different value or omits the key. Preserve normal synthesis precedence for the existing canonical sections; the special precedence is limited to supplied guardrails.

- **Keep optional sections conditional.** Render no guardrail heading when the seed does not supply it. Step 2 owns proposing missing guardrails, so this step must not invent defaults, prompt for approval, or add empty placeholders.

- **Keep the body format closed.** Do not add a general unknown-H2 passthrough. `Steps` and `References` retain their existing ownership, and unknown JSON keys remain shape errors in `_parse_body_sections_json` and `_validate_distilled_sections`.

- **Make both model contracts preservation-aware.** Update `plan_tool/prompts/distill-seed.md` and `plan_tool/prompts/synthesize-body.md` to allow the three recognized optional keys only when the source supplies them. State that these sections must remain separate and that their text is not a place for model-authored scope decisions.

- **Detect dropped headings deterministically.** At the distill and synthesis boundaries, compare the recognized headings supplied by the seed with the headings returned at that boundary before renderer fallback can hide a loss. Report bounded, deterministic findings for missing headings without making another model call; do not attempt to judge whether prose was represented elsewhere.

## Tests

- `test_body_section_parser_accepts_recognized_guardrails` — asserts `_parse_body_sections_json` accepts the three optional guardrail keys while still rejecting unknown keys.
- `test_distill_parser_accepts_recognized_guardrails` — asserts `_parse_distill_json` accepts supplied guardrail keys and `_render_distilled_markdown` retains them as separate H2 sections.
- `test_render_plan_body_keeps_supplied_guardrails_separate` — asserts `_render_plan_body` emits each supplied guardrail under its own heading with its supplied text.
- `test_supplied_guardrails_override_distilled_and_synthesized_rewrites` — asserts generated values cannot replace the original seed’s guardrail bodies.
- `test_seed_without_guardrails_does_not_gain_guardrail_headings` — asserts an ordinary seed renders none of the three optional headings.
- `test_guardrail_heading_loss_is_reported_at_distill_and_synthesis_boundaries` — asserts missing recognized headings produce bounded deterministic findings without another invoker call.
- `test_create_plan_preserves_all_supplied_guardrails` — drives `create_plan` with a seed containing all three headings and asserts the written plan retains each heading and body.

### Test-creation order (feature step)

- Add parser and renderer tests with the shared recognized-heading rule — prove accepted optional keys, rejected unknown keys, and conditional rendering.
- Add boundary-preservation tests — prove supplied text wins over distill and synthesis output and lost headings are detected without another model call.
- Add the `create_plan` regression test — prove the full create path writes the three supplied sections unchanged.

Every new test must be green before this step is considered finished.

## Acceptance criteria

- A seed supplying `Scope guardrails`, `Audit guardrails`, or `Expected placement` produces the same heading and supplied body under a separate H2 in the new plan.
- Distillation and synthesis cannot replace supplied guardrail text with generated prose.
- A seed supplying none of the recognized headings produces none of them in the new plan.
- Only the three recognized guardrail keys are accepted as new conditional body-section keys; unrelated keys remain rejected.
- Missing supplied guardrail headings at a distill or synthesis boundary produce deterministic, bounded findings without an additional model invocation.
- `tests/test_create.py` passes.

## Deferred

- Missing-guardrail suggestions and explicit approval — owned by step 2.
- Excluding guardrails from create and detail deferral buckets — owned by step 3.
- General passthrough for arbitrary seed H2 sections — outside this plan’s closed body-section contract.
