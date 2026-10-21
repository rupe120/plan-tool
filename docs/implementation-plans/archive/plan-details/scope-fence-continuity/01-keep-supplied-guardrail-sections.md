> **Auto-archived**: this plan was swept on 2026-08-03 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 1 — Keep supplied guardrail sections in created plans

## Summary

Preserve supplied `Scope guardrails`, `Audit guardrails`, and `Expected placement` sections when `plan-tool create` builds a plan from seed prose. Update `plan_tool/create.py` and both create prompts so these three known sections are conditional body sections, not unknown keys or prose folded into a canonical section. Keep the seed’s guardrail text authoritative through distillation, synthesis, and final rendering. On green, a seed with any of the three headings creates a plan with the same heading and body; a seed without them gains none.

## Table of Contents

- [Summary](#summary) — The preservation behavior delivered by this step.
- [Table of Contents](#table-of-contents) — Links to each section in this detail.
- [Why](#why) — Why supplied scope fences must survive creation.
- [Input](#input) — The seed and model-output contracts this step consumes.
- [Files (creates vs edits)](#files-creates-vs-edits) — The files changed in this step.
- [Implementation](#implementation) — The recognized-heading and precedence rules.
- [Tests](#tests) — Focused regression coverage.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Heading and test documentation.
- [Deferred](#deferred) — Work left to later steps or follow-up.

## Why

`plan_tool/create.py:create_plan` can replace the original seed with `DistillOutcome.distilled` before final body rendering, while the current optional-section contract recognizes only `Input`. A supplied scope fence can therefore be omitted or rewritten even though it sets boundaries for the plan. The create flow needs a narrow, known-heading preservation rule without accepting arbitrary H2 sections.

## Input

- **Seed H2 contract** — Read source headings through `plan_tool/create.py:extract_h2_sections`, which provides normalized names and non-empty bodies.
- **Recognized guardrails** — Support only `Scope guardrails`, `Audit guardrails`, and `Expected placement` as optional body sections.
- **Model-output contract** — `plan_tool/create.py:_validate_distilled_sections` and `plan_tool/create.py:_parse_body_sections_json` must continue to require every canonical body key while allowing only recognized optional keys.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `plan_tool/create.py` — add the three recognized optional sections, retain their original seed bodies through `create_plan`, and render supplied sections as separate H2s.
  - `plan_tool/prompts/distill-seed.md` — allow and require preservation of the three conditional guardrail keys when the seed supplies them.
  - `plan_tool/prompts/synthesize-body.md` — document the same conditional keys and preservation-only rule.
  - `tests/test_create.py` — cover parser contracts, final rendering, prompt content, and the full create path.

## Implementation

- **Foundational logic: preserve supplied guardrail sections.** Treat `Scope guardrails`, `Audit guardrails`, and `Expected placement` as the only new optional body-section names. Their supplied bodies must remain separate plan H2 sections.

- **Keep the body format closed.** Extend the optional-section handling rooted at `plan_tool/create.py:OPTIONAL_PLAN_BODY_SECTION_SHAPES`, `_render_section_shapes_block`, `_parse_body_sections_json`, `_validate_distilled_sections`, `_render_distilled_markdown`, and `_render_plan_body`. Unknown JSON keys and arbitrary seed H2 headings must remain unsupported.

- **Keep original seed guardrails available.** `plan_tool/create.py:create_plan` currently rebinds seed text after a successful `propose_distilled_seed_from_claude` result. Preserve the recognized guardrail bodies from the original seed before that rebind so a model omission or rewrite cannot erase author-supplied constraints.

- **Make supplied text win only for guardrails.** Render the original supplied body for each recognized guardrail heading, even if distillation or `propose_body_sections` omits it or returns different prose. Keep the existing synthesized-over-seed precedence for canonical body sections unchanged.

- **Render conditionally.** Place each supplied guardrail under its own H2 in `plan_tool/create.py:_render_plan_body`; do not add placeholders, defaults, or model-authored guardrails when the seed lacks that heading. Preserve the existing `Input` placement and the ownership of `Steps` and `References`.

- **Update both prompt contracts together.** In `plan_tool/prompts/distill-seed.md` and `plan_tool/prompts/synthesize-body.md`, describe the three keys as conditional, source-backed sections that must stay separate. The prompts may preserve supplied content but must not invent scope decisions or add a guardrail absent from the seed.

- **Leave generic H2 parsing generic.** `plan_tool/reprocess.py` also consumes `plan_tool/create.py:extract_h2_sections`; do not change that extractor into a guardrail-specific parser. Apply the narrow recognition rule at the create optional-section boundary.

## Tests

- `test_body_section_parser_accepts_recognized_guardrails` — asserts `plan_tool.create._parse_body_sections_json` accepts the three recognized optional keys while rejecting unrelated keys.
- `test_distill_parser_accepts_recognized_guardrails` — asserts the distill validation and rendered distilled markdown retain recognized guardrail sections.
- `test_render_plan_body_keeps_supplied_guardrails_separate` — asserts `plan_tool.create._render_plan_body` emits each supplied guardrail as its own H2 with its original body.
- `test_supplied_guardrails_override_distilled_and_synthesized_text` — asserts model output cannot replace a supplied guardrail body.
- `test_seed_without_guardrails_does_not_render_guardrail_headings` — asserts absent guardrails produce no empty or invented sections.
- `test_guardrail_atx_closing_sequence_is_preserved` — asserts a CommonMark-valid `## Audit guardrails ##` seed heading is normalized to the recognized guardrail name and renders under that canonical H2.
- `test_create_plan_preserves_all_supplied_guardrails` — drives `plan_tool.create.create_plan` with all three headings and checks the written plan.
- `test_guardrail_prompt_contracts_allow_only_recognized_optional_keys` — checks `plan_tool/prompts/distill-seed.md` and `plan_tool/prompts/synthesize-body.md` describe the conditional preservation rule without opening unknown-key acceptance.

### Test-creation order (feature step)

- Add parser and renderer tests with the recognized-heading rule.
- Add precedence tests proving original seed bodies win over model output.
- Add the end-to-end `create_plan` regression and prompt-contract checks.

Every new test must be green before this step is considered finished.

## Acceptance criteria

- A seed supplying any of `Scope guardrails`, `Audit guardrails`, or `Expected placement` produces the same heading and supplied body under a separate H2 in the created plan.
- Distillation and synthesis output cannot replace or remove a supplied guardrail body from the final plan.
- A seed supplying none of the three recognized headings produces none of them.
- The three recognized guardrail keys are accepted as optional sections; unrelated optional keys remain shape errors.
- Existing canonical section order, `Input` behavior, and `Steps` and `References` ownership remain unchanged.
- `tests/test_create.py` passes.

## References

- [Python regular expression operations](https://docs.python.org/3/library/re.html) — Use for the exact heading matching already used by `extract_h2_sections`.
- [pytest monkeypatch guide](https://docs.pytest.org/en/stable/how-to/monkeypatch.html) — Use to simulate distinct distill and synthesis output without invoking a model.
- [CommonMark Specification — ATX headings](https://spec.commonmark.org/current/#atx-headings) — Use for the H2 heading syntax the preserved sections must follow.

## Deferred

- Deterministic warnings when a distill or synthesis stage drops a supplied heading — owned by step 2.
- Missing-guardrail suggestions, approval flows, and model-based detection of content folded into another section — outside this step; material-fold detection remains BACKLOG #163.
- General passthrough for arbitrary seed H2 sections — retain the closed optional-section catalog.
