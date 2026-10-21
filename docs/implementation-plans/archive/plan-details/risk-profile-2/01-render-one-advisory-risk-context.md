> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 1 — Render one advisory risk context for explicit declarations

## Summary

Add one small renderer for the plan’s explicit risk-profile declaration and placeholders for that renderer in the run-grade detail authoring and quality-review prompts. The renderer returns a concise advisory block for a declared tier and rationale, or an empty string for legacy plans with no declaration. Keep the prompt-rendering hooks optional and empty by default so this step creates the reusable seam without changing current prompt output. On green, the next step can supply one tested context block to both prompt routes.

## Table of Contents

- [Summary](#summary) — Reviewer overview of the renderer and prompt hooks.
- [Why](#why) — Why explicit risk declarations need visible authoring context.
- [Input](#input) — Parsed plan fields and legacy-plan behavior.
- [Files (creates vs edits)](#files-creates-vs-edits) — Existing files changed by this step.
- [Implementation](#implementation) — Required renderer behavior and template seam.
- [Tests](#tests) — Focused renderer and prompt-rendering coverage.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Plan and detail-flow contracts.
- [Applicable guardrails](#applicable-guardrails) — Scope boundaries for this local change.
- [Deferred](#deferred) — Prompt-route wiring owned by the next step.

## Why

`plan_tool/schema.py:Plan` already preserves an explicit `risk_profile`–`risk_profile_rationale` declaration, but neither run-grade detail prompt has a place to show it. A single local renderer gives later prompt routes consistent wording while keeping the declaration advisory: it helps authors judge how much procedure is appropriate without weakening grounding, test, or safety duties.

## Input

- **Parsed plan declaration:** Read the `risk_profile` and `risk_profile_rationale` fields of `plan_tool/schema.py:Plan` as the paired input. The parser admits either a complete explicit pair or an omitted legacy pair.
- **Legacy distinction:** Do not use the `Plan.effective_risk_profile` fallback for this context. Its `standard` fallback is policy behavior for a legacy omission, while this renderer must emit nothing unless the plan explicitly declared both fields.
- **Validation boundary:** Treat the parsed `Plan` as valid input. This step renders context only; it does not classify risk, validate frontmatter, or edit the declaration.

## Files (creates vs edits)

- **New files:** None.

- **Existing files (edits only):**
  - `plan_tool/detail.py` — Add the declared-risk context renderer and optional empty context slots to `render_detail_prompt` and `render_detail_quality_prompt`.
  - `plan_tool/prompts/detail.md` — Add the authoring-prompt insertion point for an optional rendered context block.
  - `plan_tool/prompts/detail-quality.md` — Add the quality-review insertion point for the same optional block.
  - `tests/test_detail.py` — Cover explicit declarations, legacy omission, prompt insertion, and empty-default behavior.

## Implementation

- **Render one advisory block:** Add a small local renderer in `plan_tool/detail.py`—for example, `render_declared_risk_context(plan)`—that returns a self-contained context block when both stored declaration fields are present.

  - Show the declared tier and its rationale.
  - State that the context is advisory.
  - Ask the reader to keep the procedure proportionate to the declaration.
  - Keep current grounding requirements, test duties, and safety review in force.
  - Ask the reader to explain a material mismatch rather than silently treating the declaration as controlling policy.

- **Return an exact empty context for a legacy plan:** When either stored declaration field is absent, return `""`. Do not render an inferred `standard` tier, a legacy notice, an empty heading, or a fallback rationale.

- **Keep the renderer policy-free:** Do not add tier-specific branches, a closed vocabulary, findings, validation, or a frontmatter mutation path. The renderer produces prompt prose only.

- **Prepare both run-grade renderers without supplying context yet:** Extend `plan_tool/detail.py:render_detail_prompt` and `plan_tool/detail.py:render_detail_quality_prompt` with an optional keyword-only context-block input that defaults to `""`. Substitute that value into their existing `Template.safe_substitute` maps. Step 2 owns computing the context and passing it to every route.

- **Place the insertion points consistently:** In `plan_tool/prompts/detail.md` and `plan_tool/prompts/detail-quality.md`, place the optional block after the confirmed project context and before the prompt’s first main section. The block supplies its own spacing when non-empty, so the default empty value preserves the current rendered prompt text.

- **Keep authoring budget reporting honest:** When `render_detail_prompt` receives a non-empty context block, include its embedded size in the existing `collect_blocks` breakdown. The block must be measured from the text that enters the prompt.

- **Leave adjacent lanes alone:** Do not change `plan_tool/detail.py:render_jira_detail_prompt`, completeness-audit prompts, or any caller behavior in this step. The new default must keep existing callers valid until step 2 opts into the context.

## Tests

### Tests for this step

- `test_render_declared_risk_context_for_explicit_profiles` — Parameterize low, standard, and high explicit declarations; assert each rendered block includes the stored tier, rationale, advisory status, proportionate-procedure guidance, grounding, tests, safety review, and mismatch explanation.
- `test_render_declared_risk_context_omits_legacy_plan` — Assert a plan with no stored declaration returns `""` and does not render the effective `standard` fallback.
- `test_detail_prompt_renders_supplied_risk_context_block` — Assert `plan_tool/detail.py:render_detail_prompt` includes a supplied marker block before `## Step` and records its embedded byte count in `collect_blocks`.
- `test_detail_quality_prompt_renders_supplied_risk_context_block` — Assert `plan_tool/detail.py:render_detail_quality_prompt` includes the same supplied marker before `## Step files`.
- `test_empty_risk_context_keeps_detail_prompts_renderable` — Assert omitted and explicitly empty context inputs produce the same prompt text and leave no unresolved `${risk_context_block}` marker.
- `test_jira_detail_prompt_does_not_render_declared_risk_context` — Assert an explicitly declared plan does not add the advisory block to `plan_tool/detail.py:render_jira_detail_prompt`.

Every listed test must be green before this step is complete.

## Acceptance criteria

- A complete explicit declaration renders one concise advisory context containing its stored tier and rationale.
- The advisory context tells readers to retain grounding, tests, and safety review and to explain a material mismatch.
- A legacy plan with no stored declaration produces an empty context rather than an inferred `standard` context.
- `render_detail_prompt` and `render_detail_quality_prompt` accept an empty optional context without unresolved template markers or changed default prompt text.
- A supplied authoring context is included in the prompt-budget block accounting.
- Jira-grade detail rendering remains free of the advisory context.
- `uv run pytest tests/test_detail.py -q` passes.

## References

- [Plan frontmatter contract — Read the paired declaration and legacy-omission rules for `risk_profile` and `risk_profile_rationale`.
- [Detail flow](../../../how-to/pipeline/detail.md) — Read the authoring and detail-quality prompt roles this step prepares.

## Applicable guardrails

- **The plan’s “## Plan intent,” advisory context:** Keep the renderer informational; it must not make a declaration into a gate or policy decision.
- **The plan’s “## Step intent,” concise shared statement:** Produce one reusable context shape for detail authors and reviewers while retaining their normal review duties.
- **The plan’s “## Scope contract,” allowed behavior changes:** Limit this step to the local renderer and prompt hooks; leave route-wide wiring to the owning next step.
- **The plan’s “## Out of scope,” unaffected pipeline surfaces:** Do not extend this change into classification, validation, audit behavior, Jira detail, or unrelated commands.

## Deferred

- **Run-grade route wiring** — Step 2 supplies this renderer’s output to initial authoring, quality review, and detail-loop rewrite calls.
