# Step 3 — Make `annotate` write all three guardrail headings into its carryover seed

<!-- plan-tool:detail-format-version: 1 -->

## Summary

This step makes the carryover seed from `annotate` carry `## Scope guardrails`, `## Audit guardrails` and `## Expected placement`. When the source has a heading that step 1's check accepts, `plan_tool/annotate_render.py:render_create_seed` copies its body verbatim through step 2's block helper. When it has none, the existing single `annotate` response also returns the missing bodies. That takes an additive extension of `_ANNOTATE_RESPONSE_CONTRACT` and `PlanAnnotation` in `plan_tool/annotate.py`, and `plan_tool/prompts/annotate.md` gets one proportionality line. A response without guardrail bodies renders `_(TODO)_` and does not fail the annotation. `plan_tool/cli/annotate_cmd.py` names each inherited or model-written heading in its printed output. On green, every seed `annotate` writes can pass step 1's check unless a heading is `_(TODO)_`, and no new model call exists.

## Table of Contents

- [Why](#why) — why annotate seeds need the three headings
- [Input](#input) — what steps 1 and 2 provide and how the response is shaped today
- [Files (creates vs edits)](#files-creates-vs-edits) — the seven files touched
- [Implementation](#implementation) — response extension, rendering, prompt line, printed output
- [Tests](#tests) — cases per test file
- [Acceptance criteria](#acceptance-criteria) — observable results
- [References](#references) — code and docs to read
- [Applicable guardrails](#applicable-guardrails) — plan fences that bind this step
- [Deferred](#deferred) — work left to other steps

## Why

`render_create_seed` writes `## References` and the carryover sections, but no guardrail headings. Once `create --from-existing` refuses a seed missing any of them, every `annotate` seed would be refused. The source plan is the only real place a fence can come from. Copying it keeps the fence. When the source has none, `annotate` already makes one model call that reads the source and the code, so that call is the right place to ask for a fence the source implies. `_(TODO)_` is the fallback when the model returns nothing. That way nobody mistakes an invented fence for an inherited one.

## Input

- **Step 1.** Adds the three-heading constant and a pure function in `plan_tool/scope_fence.py` that reports headings that are missing, duplicated, empty or placeholders. Read the landed names off the module at implementation time. The landed names win over any spelling here. At HEAD of this drafting, neither the constant nor the function exists yet.
- **Step 2.** Adds the block helper beside `source_references_block` in `plan_tool/scope_fence.py`. It takes the source body, copies each accepted heading verbatim and writes `_(TODO)_` otherwise. It also has a companion that reports which headings were inherited. This step calls both and does not re-implement the accept rule. If step 2's helper cannot accept a model-written body for the "no accepted heading" case, extend it additively. Do not make a second copy of the rule in `plan_tool/annotate_render.py`.
- **Source text.** `PlanAnnotation.source_text` already carries the source verbatim. `render_create_seed` already reads `## References` from it through `extract_h2_sections(_strip_frontmatter(...), ignore_fenced_code=True)`. The guardrail read uses the same text and step 2's helper.
- **Response today.** `_ANNOTATE_RESPONSE_CONTRACT` is a `JsonResponseContract` with `root=JSON_ROOT_ARRAY`. `_parse_annotation_response` raises `AnnotateError` on any element that has no non-blank `heading` or has an unknown `status`. A new element shape therefore needs separate handling before that loop.
- **Limit on verification.** Canned-response tests show the contract can be satisfied. They do not show a real model usually obeys the "only fences the source implies" line. That needs real runs.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/annotate.py`:
    - extend `_ANNOTATE_RESPONSE_CONTRACT` with one example guardrail element
    - add an optional field to `PlanAnnotation`
    - have `_parse_annotation_response`, or a helper it calls, split the guardrail element out before the per-section loop
  - `plan_tool/annotate_render.py`: `render_create_seed` writes the three headings through step 2's helper.
  - `plan_tool/prompts/annotate.md`: add one rule line.
  - `plan_tool/cli/annotate_cmd.py`: `_annotate_one` prints one line per heading naming whether it is inherited, model-written or unfilled.
  - `tests/test_annotate.py`, `tests/test_annotate_render.py`, `tests/cli/test_annotate_cmd.py`: new cases, listed under Tests.

## Implementation

- **Carrying the bodies in the response (recommended).**
  - Keep the array root. Add one reserved element that has a `guardrails` object and no `heading`. For example: `{"guardrails": {"scope": "...", "audit": "None", "placement": "None"}}`.
  - Key names are the implementer's choice. They must map one to one onto the three headings.
  - Rejected alternative: change the root to an object with `sections` and `guardrails`. It breaks every existing response and every existing test that passes a bare array, which contradicts "the existing response stays valid unchanged".
- **Parsing.**
  - Pull out any element that has `guardrails` and no `heading` before the per-section loop. Remove it from the list the loop sees, so the missing-heading error does not fire for it.
  - An empty list after the removal must still raise the existing "empty" error. A response containing only a guardrails element is not a valid annotation.
  - Keep each body as a stripped string. A missing key, a non-string value or a blank value means "no body for that heading", not an error. This rule is what makes older responses and partial responses work.
  - Store the result on `PlanAnnotation` as an optional field with a default (an empty mapping or `None`), the same way `grounding_candidate_count` and `low_grounding` default. That keeps every existing `PlanAnnotation(...)` call, including `_annotation(...)` in `tests/test_annotate_render.py`, valid.
  - A response with more than one guardrails element is not an error. Merge them, or keep the first. Pick one and pin it with a test.
- **Rendering order of authority.**
  - **Inherited first.** If the source has a heading step 1's rule accepts, copy it verbatim and ignore any model body for that heading.
  - **Model-written next.** Otherwise use the model's body for that heading only if step 1's `is_acceptable_guardrail_body` accepts it, through step 2's helper. This step passes the bodies to the helper and does not re-check them. The decision is per heading, so a source with some accepted headings has those inherited and the model is consulted only for the rest.
  - **`_(TODO)_` last.** Otherwise write `_(TODO)_`.
  - The inherited case must win over the model even when the model body differs. The source is the authority, and the model must not overwrite a fence the operator wrote.
- **A model body of `None`.** `None` is a valid body. It must pass through unchanged and must not be treated as a placeholder or as missing. Do not add `None` or `N/A` to any placeholder pattern.
- **Placement in the seed.** Put the three headings in the seed after `## Already implemented` and before `## References`. One fixed order is the only constraint. They are H2 headings at the top level of the seed, outside any fence.
- **Prompt line.** Add one line to `plan_tool/prompts/annotate.md`, in the Rules list:
  - Write a guardrail only when the source already implies the fence, use `None` when it implies none, and add no scope, mechanism or requirement.
  - It carries the proportionality rule from `plan_tool/prompts/synthesize-body.md`. Read that file and match its meaning. Do not copy its text.
  - The placeholder `${response_format_block}` already renders the extended contract. Do not add a new `${...}` key. If you add one anyway, it must be a key `render_annotate_prompt` supplies.
  - Write any literal `$` as `$$`, since rendering uses `string.Template.safe_substitute`.
- **Printed result.**
  - In `plan_tool/cli/annotate_cmd.py:_annotate_one`, after the existing `detail(f"seed ...")` line, print one line per heading using `detail(...)`. Use three states: inherited from the source, model-written (review before `create`), or unfilled (fill in by hand).
  - Derive the states from the same decision `render_create_seed` made. Do not run a second classification in the command. One way: have the render step or step 2's companion return the per-heading state, and print it here. Keep the command thin.
- **Destructive operations stay as they are.**
  - The default-seed existence check in `_annotate_one` and its refusal message stay.
  - Replacement is still only through an explicit `--seed`.
  - `--archive` stays opt-in.
  - Do not touch `_derive_annotate_paths`, `_archive_source` or the batch summary, except where a new printed line must fit.
- **No new model call.** `classify_plan_implementation` still makes one invoker call. A test must pin the call count.
- **Mirror, do not widen.** Do not add `## Stack`, `## Outcome` or `## In scope`. Do not touch `--iterate` handling, which stays rejected.

## Tests

All tests use canned responses through the `invoker=` seam. None spawns a real backend.

### Tests for this step

- `tests/test_annotate_render.py`
  - `test_inherited_guardrail_heading_is_copied_verbatim` — a source with an accepted `## Scope guardrails` body appears unchanged in the seed.
  - `test_inherited_guardrail_beats_model_written_body_for_the_same_heading` — when both exist, the source body is the only one in the seed. This pins "the source is the authority".
  - `test_model_written_guardrail_fills_a_heading_the_source_lacks` — a heading with no accepted source body takes the model body.
  - `test_model_body_none_is_rendered_as_none_not_todo` — an explicit `None` body survives as `None`.
  - `test_missing_guardrail_bodies_render_todo_for_all_three_headings` — an annotation with no guardrail data writes `_(TODO)_` under each heading.
  - `test_seed_carries_all_three_headings_exactly_once` — each heading appears once, in the fixed order, outside any fence.
  - `test_duplicated_or_placeholder_source_heading_is_not_inherited` — a source heading step 1 rejects falls back to the model body or `_(TODO)_`, so the seed does not copy a bad heading.
  - `test_mixed_source_inherits_its_accepted_heading_and_takes_model_bodies_for_the_rest` — a source carrying only `## Scope guardrails` keeps that body verbatim, and the other two take model bodies or `_(TODO)_`.
  - `test_partial_model_response_fills_only_the_headings_it_supplies` — a response with one or two bodies fills those headings and writes `_(TODO)_` under the rest.
  - `test_unusable_model_body_is_not_written` — an empty, `TODO`-form, or `## `-containing model body gives `_(TODO)_` for that heading, and the seed still carries each heading exactly once.
  - `test_existing_seed_sections_unchanged_by_guardrail_headings` — carryover scope, done-context, references and provenance render as before.
- `tests/test_annotate.py`
  - `test_response_with_guardrails_element_populates_the_annotation` — the reserved element is split out and stored.
  - `test_guardrails_element_does_not_count_as_a_section` — `sections` contains only real headings, and no missing-heading error is raised.
  - `test_older_response_shape_without_guardrails_still_parses` — a bare section array parses, and the guardrail field is empty.
  - `test_response_with_only_a_guardrails_element_still_raises_empty` — the existing empty-array error is kept.
  - `test_blank_or_non_string_guardrail_value_is_treated_as_absent` — no error, and the heading is treated as unfilled.
  - `test_classify_makes_one_invoker_call_with_guardrails_requested` — the call count is 1.
  - `test_annotate_prompt_contains_the_guardrail_fence_instruction` — the rendered prompt contains the "only fences the source already implies / `None` / no scope, mechanism or requirement" line, and the response-format block names the guardrails element.
- `tests/cli/test_annotate_cmd.py`
  - `test_printed_result_names_inherited_model_written_and_unfilled_headings` — output lists each heading with its state.
  - `test_older_response_without_guardrails_exits_zero_and_prints_unfilled` — exit code 0, seed has `_(TODO)_`, output says unfilled.
  - `test_existing_default_seed_still_refuses_overwrite` — carve-out pin: the refusal still fires, and nothing is written.
  - `test_explicit_seed_path_still_permits_replacement` — carve-out pin: an explicit `--seed` still replaces.
  - `test_archive_flag_still_opt_in` — carve-out pin: no archive move without `--archive`.

Every test above must be green before this step is finished. Verify the new assertions by mutation: for example, make the model body win over an accepted source heading and watch the precedence test go red.

## Acceptance criteria

- A seed from `annotate` contains each of the three headings exactly once, in all of these cases: source has accepted headings, source has none and the model supplies bodies, response has no guardrail data.
- An accepted source heading is copied verbatim. A model body never replaces it.
- A response with no guardrail bodies produces `_(TODO)_` under the missing headings, and `annotate` exits 0.
- A partial response fills only the headings it supplies a usable body for; a missing, empty, `TODO`-form or `## `-containing body gives `_(TODO)_`, and the printed result lists that heading as unfilled.
- A body of `None` is rendered as `None` and is not replaced by `_(TODO)_`.
- A response in the old shape (a bare array of sections) parses to the same sections as before.
- The rendered prompt contains the guardrail instruction line.
- The printed result names each heading as inherited, model-written or unfilled.
- `classify_plan_implementation` makes exactly one invoker call.
- The default-seed refusal, the explicit `--seed` replacement and the opt-in `--archive` move behave as before.
- `rg 'None' plan_tool/scope_fence.py` shows no new `None` or `N/A` entry in `_SECTION_PLACEHOLDER_RE`.
- `uv run pytest tests/test_annotate.py tests/test_annotate_render.py tests/cli/test_annotate_cmd.py -q` passes.

## References

- `plan_tool/annotate.py` (`_ANNOTATE_RESPONSE_CONTRACT`, `_parse_annotation_response`, `PlanAnnotation`) — the response contract and parser this step extends.
- `plan_tool/annotate_render.py` (`render_create_seed`) — where the three headings are written.
- `plan_tool/scope_fence.py` (`source_references_block`, `_is_placeholder_section`, plus the names steps 1 and 2 add) — the accept rule and the block helper to reuse.
- `plan_tool/prompts/annotate.md` and `plan_tool/prompts/synthesize-body.md` — the prompt to edit and the proportionality rule to carry.
- `plan_tool/cli/annotate_cmd.py` (`_annotate_one`) — where the printed result and the unchanged destructive checks live.
- `SEED_FORMAT.md`; `docs/how-to/pipeline/create-from-existing.md` — seed contract and intake.

## Applicable guardrails

- **The plan's "## Scope guardrails", presence-only check.** This step adds no judgment of guardrail content. It copies a source body or writes a model or `_(TODO)_` body, and judges none of them.
- **The plan's "## Scope guardrails", `None` must pass.** The `None` body path above must not touch the placeholder pattern. A test pins that `None` is rendered as written.
- **The plan's "## Scope guardrails", no required `## Stack`, `## Outcome` or `## In scope`.** The seed writer adds only the three headings. The tempting spot is the seed layout in `render_create_seed`, where adding "just one more" heading looks cheap.
- **The plan's "## Scope guardrails", no new model call.** The guardrail bodies ride on the existing single `annotate` call. The tempting spot is `classify_plan_implementation`, where a second invoker call for guardrails would look simpler than extending the response. A call-count test guards it.
- **The plan's "## Out of scope", no quality judgment, agreement check, length cap or exit-code change.** `annotate` must not compare a guardrail to `Out of scope`, cap its length, or exit non-zero because a heading is `_(TODO)_`.

## Deferred

- Refusing a seed with a bad heading — step 1's check is wired into the `create --from-existing` intake and the roadmap draft gate by other steps, not here.
- Carrying guardrails in `scope-out` and `reground` seeds — step 2 owns them; this step only calls the helper step 2 adds.
- Documentation of the extended response and the seed headings (`SEED_FORMAT.md`, `docs/how-to/pipeline/create-from-existing.md`) — owned by the plan's docs step, not this step's files.
- Measuring how often a real model writes only fences the source implies — needs real runs the canned-response suite cannot supply.
- Merging duplicated heading-extraction code across `annotate_render.py` and other seed writers — a consolidation entry for `BACKLOG.md`, not part of this step.
