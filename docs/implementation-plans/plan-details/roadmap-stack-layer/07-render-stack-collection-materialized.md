# Step 7 — Render the stack collection in materialized draft seeds beside #460's hosting and store section

<!-- plan-tool:detail-format-version: 1 -->

## Summary

- Adds the `stack` collection to the deterministic `## Stack` section that #460's seed renderer writes into materialized draft seeds. Chosen concerns, open concerns, and "stack not recorded" each get an explicit line.
- Files: `plan_tool/roadmap.py` (the seed renderer and its draft and promoted-seed overwrites), `plan_tool/prompts/roadmap-seed.md`, `tests/test_roadmap.py`, and `tests/test_roadmap_seed_manifest.py`.
- Key decision: stack lines are rendered by code from the parsed `ConstraintsArtifact.stack`, never authored by the model. The prompt tells the model the section is tool-owned and that it must not invent or "resolve" an open concern.
- On green, a seed materialized from a roadmap with an open deployment platform shows that concern as open next to the hosting and store rows. A plan derived from the seed sees chosen and open concerns, including language/runtime, as settled input.
- The overwrite paths #460 owns are unchanged. They write the stack-bearing text because the text they write now contains it.

## Table of Contents

- [Summary](#summary) — what the step does and the result on green
- [Why](#why) — the gap between the roadmap's stack and the seed
- [Input](#input) — what steps 1 and 2 and #460 hand this step
- [Files (creates vs edits)](#files-creates-vs-edits) — the four files touched
- [Implementation](#implementation) — rendering rules, prompt edit, and what must not change
- [Tests](#tests) — the cases that pin the behavior
- [Acceptance criteria](#acceptance-criteria) — checkable outcomes
- [Applicable guardrails](#applicable-guardrails) — the plan fences that bind this step
- [Deferred](#deferred) — work that belongs elsewhere

## Why

- Hosting and store rows reach a seed through #460's `## Stack` section. Stack concerns (deployment platform, store engine, language/runtime) have no path into a seed. A plan derived from the seed would pick its own language and platform, which is the loss the plan's problem statement describes.
- A concern recorded as `open` must reach `create` as open. If the seed omits it, `create` fills the gap with a vendor the roadmap never chose.
- A version that predates the collection must read "stack not recorded" in the seed, not as an empty stack. Step 1 made that difference exist in the parsed type.

## Input

- **Step 1 output.** `ConstraintsArtifact.stack` is `None` (not recorded), `()` (present, empty), or a source-ordered tuple of stack rows. Each row has an id, a `concern`, and either a `choice` or an `open` marker. Read the landed names in `plan_tool/roadmap_artifacts.py`. They win over any name used here.
- **#460 output (shipped).** `_render_stack_section` in `plan_tool/roadmap.py` renders the tool-owned `## Stack` section from the accepted version: a `### Hosting` sub-part, then a `### Stores` sub-part, with a missing product rendered through `_product_text`. Read it, and how the draft and promoted-seed overwrite paths call it, before editing.
- **Step 4 output.** The constraints stage already authors stack rows, so the constraints text embedded in the seed prompt carries them.
- **Limit.** The tests prove the rendering is deterministic and the prompt carries the instruction. They do not show that a real model leaves the section alone.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/roadmap.py`:
    - extend #460's `## Stack` rendering with the stack lines;
    - keep the draft overwrite and promoted-seed overwrite call paths as they are.
  - `plan_tool/prompts/roadmap-seed.md`: add the rule that the rendered `## Stack` section is tool-owned, and that an open concern stays open.
  - `tests/test_roadmap.py`: add the rendering and prompt cases below, and update only the existing assertions the new lines break.
  - `tests/test_roadmap_seed_manifest.py`: add a case that a seed carrying the stack-bearing section classifies like any other current seed.

## Implementation

**Where the lines go.**
- Add the stack lines inside #460's `## Stack` section, in a `### Technology stack` sub-part after the `### Stores` sub-part. Do not add a second top-level heading.
- Adding a heading would break every site that enumerates guardrail headings. #460's detail owns that list, and the plan fences this step away from it.

**Row rendering rules (the parts that are not free to vary).**
- **Chosen row.** Render the concern and its `choice` verbatim.
- **Open row.** Render the concern with an explicit "open — not decided" marker. Never render an empty value and never a placeholder vendor.
- **`stack` is `None`.** Render one explicit line saying the stack is not recorded for this roadmap version. This matches how #460 renders a missing `product` through `_OPEN_PRODUCT_TEXT` ("product left open by the accepted roadmap").
- **`stack` is `()`.** Render a distinct line saying the collection is present and empty. Steps 1 and 2 keep these two states different, and so must the seed.
- **Order.** Keep source order from the parsed tuple.
- **Same inputs, same bytes.** The output depends only on the parsed constraints artifact. No clock, no model call.

**Source of the constraints artifact.**
- Reuse whatever #460 already uses to reach the parsed constraints, most likely the `_LoadedArtifact` items that `_render_seed_materialize_prompt` and its callers already load.
- Do not add a second read of `02-constraints.md`. One way: pass the parsed artifact into the existing renderer call.

**Prompt edit.**
- In `plan_tool/prompts/roadmap-seed.md`, add a short instruction that the `## Stack` section is rendered by the tool from `02-constraints.md`, that the model must not rewrite it, and that a concern marked open stays open: do not choose a vendor, runtime, or engine for it.
- Use only `${...}` names the variable map already supplies. Write a literal `$` as `$$`.
- Restate the rule in the prompt text. Do not cite `ROADMAP_FORMAT.md`; installed prompts cannot open repo docs.
- Keep the existing roadmap-altitude and scope-contract rules unchanged. The instruction adds no scope.

**Do not change.**
- The draft overwrite and promoted-seed overwrite behavior #460 owns.
- Draft-seed provenance keys and validation, including `roadmap_components` and the `## References` requirement.
- The digest and state logic in `plan_tool/roadmap_seed_state.py` and `plan_tool/roadmap_seed_manifest.py`. A digest of the stack-bearing text is an ordinary digest.

**Rejected alternative.**
- Letting the model copy the stack rows from the constraints artifact in the prompt. That makes the section model-dependent, so an open concern could be silently resolved. A code-rendered section is what makes "an open concern reaches `create` as open" a checkable fact.

## Tests

`tests/test_roadmap.py`:
- `test_seed_stack_section_renders_chosen_stack_rows_verbatim` — a chosen row appears with its concern and choice text.
- `test_seed_stack_section_renders_open_concern_as_open_not_a_vendor` — an open row shows the open marker and no invented value. This pins the Integration case.
- `test_seed_stack_section_says_stack_not_recorded_when_collection_absent` — `stack is None` renders the not-recorded line, not an empty list.
- `test_seed_stack_section_distinguishes_present_empty_from_not_recorded` — `()` and `None` render different lines.
- `test_seed_stack_section_keeps_source_order_and_is_deterministic` — two renders of the same input are equal, in row order.
- `test_seed_stack_lines_sit_inside_the_single_stack_heading` — the output has one `## Stack` heading, with hosting, store, and stack content under it.
- `test_draft_and_promoted_seed_overwrites_write_the_stack_bearing_text` — both overwrite paths write the text that contains the stack lines, with no new branch.
- `test_seed_prompt_says_stack_section_is_tool_owned_and_open_stays_open` — the prompt contains the instruction, asserted by key phrase.
- `test_seed_prompt_placeholders_are_a_subset_of_the_variable_map` — the existing case stays green with the edited prompt.
- `test_seed_prompt_cites_no_repo_document` — the existing case stays green.

`tests/test_roadmap_seed_manifest.py`:
- `test_classify_current_for_seed_text_carrying_the_stack_section` — a seed with the stack-bearing section and a matching digest classifies as current.

### Tests for this step

- Every case above must be green before the step is finished.
- The existing seed-prompt tests and the existing #460 hosting/store rendering tests must stay green. A rewrite is allowed only where a test pinned a rendered section that now legitimately contains stack lines.

## Acceptance criteria

- A seed materialized from a roadmap whose deployment platform is open shows that concern as open under `## Stack`, and shows no vendor for it.
- A seed from a version with no `stack` collection shows the not-recorded line.
- The rendered section has one `## Stack` heading. `rg -n '^## Stack' plan_tool/roadmap.py` finds no second heading definition.
- Rendering the same constraints artifact twice gives the same text.
- `roadmap-seed.md` carries the tool-owned and stays-open instruction and no `FORMAT.md` citation.
- The draft and promoted-seed overwrite paths have no diff other than what #460's renderer call already needs.
- `uv run pytest tests/test_roadmap.py tests/test_roadmap_seed_manifest.py -q` is green.

## Applicable guardrails

- **The plan's "## Out of scope", non-goals.** This step adds no fifth artifact, no concern beyond the three, no closed vendor vocabulary, and no defect class or approval block on stack content. The seed shows the stack and judges nothing.
- **Plan intent and step intent.** The step only makes the stack visible as settled input to a plan derived from the roadmap. Whether a plan contradicts the stack is the plan audit's job, owned by #460.
- **Existing accepted versions.** The step does not regenerate or rewrite them. A seed from an older version reads "stack not recorded" and stays valid.
- **The declared files list.** Changes to `create`, `detail`, or the plan-audit prompt are #460's and not this step's.

## Deferred

- Carrying `## Stack` through `create`, `detail`, the scope fence, and the plan-audit prompt — owned by #460, not this step.
- Comparing a plan against the stack, or flagging a conflict between a hosting row and a stack choice — a semantic judgment the plan keeps out of the tool.
- Format documentation of the seed's stack lines — a later docs step in this plan.
- Rematerializing existing drafts so they gain the stack lines — left to the operator's refresh command; no tool migrates them.
- Measuring what a real model does with an open concern in a Integration seed — recorded as an observation that gates nothing.
