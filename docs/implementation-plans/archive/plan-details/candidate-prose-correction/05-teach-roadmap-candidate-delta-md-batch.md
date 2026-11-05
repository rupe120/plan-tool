> **Auto-archived**: this plan was swept on 2026-11-05 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 5 — Teach the batch candidate prompt the `correct-prose` operation

<!-- plan-tool:detail-format-version: 1 -->

## Summary

This step edits `plan_tool/prompts/roadmap-candidate-delta.md` so the batch route tells the model it may emit step 4's `correct-prose` operation. The prompt gets one closed example and the authority rules. `plan_tool/prompts/roadmap-candidate-delta-selector.md` is deliberately left alone, so selector-era runs never see the operation. The key design decision is to restate the operation's keys in the template text, because the template cannot cite a repo doc. A new test pins that restatement against the parser's required-key constant. On green, a batch prompt names `correct-prose` and every required key, and the selector prompt does not mention it.

## Table of Contents

- [Why](#why) — an accepted operation the model is never offered
- [Input](#input) — step 4's output and the prompt machinery this step reads
- [Files (creates vs edits)](#files-creates-vs-edits) — the two files touched
- [Implementation](#implementation) — what the template must say and where it must stay silent
- [Tests](#tests) — the key-coverage test, the selector carve-out, and the test that must change
- [Acceptance criteria](#acceptance-criteria) — checkable outcomes
- [Applicable guardrails](#applicable-guardrails) — plan fences that bind this step
- [Deferred](#deferred) — related work this step does not do

## Why

Step 4 adds the `correct-prose` operation to `plan_tool/roadmap_candidate.py`, and the parser accepts it. The batch prompt, `plan_tool/prompts/roadmap-candidate-delta.md`, still says "Use only `add-row`, `replace-row`, and `remove-row`". A model following it would never emit the operation, and one that guessed it would hit a closed-parser refusal. This step makes the operation reachable from real batch runs.

## Input

- **Step 4 output:** the parser constants and wire shape for `correct-prose` live in `plan_tool/roadmap_candidate.py`, next to `ADD_ROW_REQUIRED_KEYS`, `REPLACE_ROW_REQUIRED_KEYS`, and `REMOVE_ROW_REQUIRED_KEYS`. Read the landed operation name, required-key constant, and any optional-key constant from that module. They did not exist at HEAD when this detail was written. Where this detail and the landed names disagree, the landed names win.
- **Step 3 output:** the capsule carries each issued shared span with its span id, text, and owning set. Read the landed field names from `plan_tool/roadmap_candidate_context.py`. The prompt text must use those names.
- **Template loading:** `plan_tool/roadmap_candidate_run.py:render_candidate_delta_prompt` picks `roadmap-candidate-delta.md` for the batch route and `roadmap-candidate-delta-selector.md` otherwise. It fills `${operation_shapes}` from `_render_batch_operation_shapes`, `${non_addable_collections_notice}`, `${collection_hints}`, `${review_pair}`, `${capsule_payload}`, and `${capsule_receipt}`. Substitution is `string.Template.safe_substitute`, so a literal `$` must be written `$$` and an unsupplied `${name}` ships as literal text.
- **Existing example test:** `test_batch_prompt_renders_parser_owned_operation_shapes` collects every fenced JSON block containing `"op"` from the rendered prompt and asserts the set of operations equals exactly `add-row`, `replace-row`, and `remove-row`. A `correct-prose` example in the template changes that set.
- **Limit on verification:** canned-response tests prove the contract can be satisfied. They do not prove a real model usually emits `correct-prose` correctly. Measuring that needs real briefs this suite cannot supply.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/prompts/roadmap-candidate-delta.md`: add the operation to the allowed list and describe it. Include a closed example and the authority rules.
  - `tests/test_roadmap_candidate_run.py`: add the key-coverage and selector carve-out tests. Update `test_batch_prompt_renders_parser_owned_operation_shapes` for the new operation. Its other assertions stay.
- **Deliberately not edited:** `plan_tool/prompts/roadmap-candidate-delta-selector.md`, `plan_tool/roadmap_candidate_run.py`, `plan_tool/roadmap_candidate.py`.

## Implementation

- **Allowed-operation sentence:** extend "Use only `add-row`, `replace-row`, and `remove-row`" to include the correction operation by its landed name. Keep the "Never use `add`, `replace`, or `remove`" line.
- **Say what it is for, in plain terms:** it replaces the text of one issued shared-narrative span with corrected text, changes no typed row, and is offered only for a span the issued payload lists.
- **State the authority rule:** the operation names an issued span by its span id from the payload and carries the full replacement text. Its `feedback_id` must name one issued reviewer item. A span id the payload did not issue grants nothing, and neither does a reference to a removed row.
- **Restate every required key in the template's own words.** The template cannot cite `ROADMAP_FORMAT.md`, because the installed tool runs in repos that do not have it. Name each key the landed required-key constant lists, and name any optional key.
- **Use a placeholder example:** one closed JSON block with placeholder ids and `<one line>`-style text, so a believable example is not copied wholesale. The block must carry exactly the landed key set. This also makes it visible to the existing example-collecting test.
- **Do not widen the operation's scope in prose.** The template must not offer correction of an arbitrary body region, a span from the compact inventory, or text outside an issued span. Say that replacement text is bounded by the byte ceiling step 1 settles, naming the number only if the landed constant states one.
- **Combined use:** state the combination rule step 1 settles for sharing a delta with typed-row operations. Copy it from the landed doc; do not invent it.
- **Keep the existing prohibitions consistent.** The sentence "Do not attach prose amendments to `replace-row` or `remove-row`, or emit prose as artifact body text or a separate response field" stays. Correction is an `operations` member, not a response field, so add a short clause saying so. Keep "Do not include … artifact text" consistent with it: the replacement text lives only inside the operation.
- **Leave the selector prompt untouched.** The selector route issues no shared spans. It answers `{"delta":...}` or `{"expand":...}`, and `test_selector_prompt_requires_row_owned_prose_only_in_delta_additions` pins that wording. Rejected alternative: share the operation text between both templates through a substituted variable like `${non_addable_collections_notice}`. That would put the operation in front of selector runs and needs `plan_tool/roadmap_candidate_run.py` edits outside this step.
- **Rejected alternative: render the example from the parser's key constant.** `_render_batch_operation_shapes` does that for the three existing operations, but it lives in a file outside this step. A static example plus a key-coverage test delivers the property with a smaller diff. Whether to move it into the renderer is Deferred.
- **Write `$` literally only as `$$`.** The template has no bare `$` today. Any new `${name}` must already be supplied by the caller, and this step adds none.

## Tests

All in `tests/test_roadmap_candidate_run.py`. Follow the style of the neighboring `test_batch_prompt_*` cases, which render through `render_candidate_delta_prompt` with the `_resolved`/`_ledger` helpers.

### Tests for this step

- `test_batch_prompt_names_every_key_the_correct_prose_parser_requires` — renders the batch prompt and asserts each key in the landed required-key constant, and each optional key, appears as a quoted JSON key in the correction example. Reads the keys from `roadmap_candidate`, never a hard-coded list, so a parser key change reddens it.
- `test_batch_prompt_correct_prose_example_has_exactly_the_parser_key_set` — extracts the example block and asserts its key set equals required plus optional. Fails if the prompt leaves a key out or invents one.
- `test_batch_prompt_correct_prose_example_parses_through_the_real_parser` — wraps the example in the batch root shape and runs it through `parse_candidate_delta` with placeholders replaced by ids from a capsule that issues a shared span. It must parse. This pins that the example satisfies the closed parser.
- `test_selector_era_prompt_deliberately_does_not_offer_correct_prose` — renders the selector-route prompt and asserts the operation name appears nowhere in it. It carries the reason in its name and docstring: the selector route issues no shared spans, so offering the operation would invite a refusal. Verify by mutation: paste the operation name into the selector template and watch it go red.
- `test_batch_prompt_states_correct_prose_is_an_operation_not_a_response_field` — asserts the prompt says correction text travels only inside the operation, and that the existing "Do not attach prose amendments to `replace-row` or `remove-row`" line is still present.
- `test_batch_prompt_renders_parser_owned_operation_shapes` (changed) — the expected map gains the correction operation with its landed key set. Add a comment that its example is static in the template, unlike the other three, which come from `_render_batch_operation_shapes`.

**Green-before-done gate:** every test above must be green, and the existing `test_batch_prompt_*`, `test_selector_*`, and `test_batch_and_selector_prompts_share_the_non_addable_collections_notice` cases must stay green. Run `uv run pytest tests/test_roadmap_candidate_run.py -q`.

## Acceptance criteria

- The rendered batch prompt names the correction operation and every key the landed parser requires, each as a quoted JSON key in a closed example.
- The example's key set equals the parser's required plus optional keys, and it parses through `parse_candidate_delta` with valid ids.
- The rendered selector-route prompt does not contain the operation name, and `plan_tool/prompts/roadmap-candidate-delta-selector.md` has no diff.
- `rg -n 'FORMAT\.md' plan_tool/prompts/roadmap-candidate-delta.md` returns nothing, and `rg -P '\$(?!\{|\$)' plan_tool/prompts/roadmap-candidate-delta.md` returns nothing.
- The only code files changed are `plan_tool/prompts/roadmap-candidate-delta.md` and `tests/test_roadmap_candidate_run.py`.
- `uv run pytest tests/test_roadmap_candidate_run.py -q` passes.

## Applicable guardrails

- **The plan's "## Scope guardrails" and "## Out of scope", arbitrary body replacement and marker-based editing:** the prompt must offer correction only of an issued span. It must not hint at replacing other body text or at selecting text by marker.
- **The plan's "## Scope guardrails", stale-row reference:** the prompt must not say a reference to a removed row grants authority over the body. Authority comes only from the issued span.
- **The plan's "## Scope guardrails", weaker described-row gates:** the prompt must not suggest that a correction can skip the complete-roadmap gates. Do not describe the gates as optional.
- **Step intent:** this step makes the operation reachable and does nothing more. It adds no new operation, field, or parser rule.

## Deferred

- Render the correction example from the parser's key constant inside `plan_tool/roadmap_candidate_run.py:_render_batch_operation_shapes` — would remove the static example but needs edits outside this step's files. The key-coverage test already guards drift. Route to BACKLOG.md only if the static example drifts.
- Offer `correct-prose` on the selector route — the selector issues no shared spans, so there is nothing to correct. Needs a plan-level decision.
- Measure how often a real model emits a valid correction on its first attempt — needs real briefs and a place to record them; the suite stays hermetic.
- Review display of before/after text and promotion confirmation — owned by the plan's other steps, not this prompt.
