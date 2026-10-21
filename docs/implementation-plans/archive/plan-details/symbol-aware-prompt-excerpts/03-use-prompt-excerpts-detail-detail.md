> **Auto-archived**: this plan was swept on 2026-07-07 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 3 — Use Prompt Excerpts in Detail and Detail-Quality Prompts

## Summary

This step changes `plan_tool/detail.py` so both `render_detail_prompt` and `render_detail_quality_prompt` show symbol-aware excerpts for declared step files instead of blind leading slices. The scoped production edit is the shared `plan_tool/detail.py:_format_files_contents_block`, because both prompt renderers already call it. The main design decision is to keep filesystem error handling and prompt block shape in `plan_tool/detail.py`, while delegating only successful text excerpt selection to the step 1 prompt excerpt helper. On green, `tests/test_detail.py` proves detail authoring and detail-quality prompts include the relevant symbol window past the byte cap while preserving existing missing-file, unreadable-file, no-files, and truncation-marker contracts.

## Table of Contents

- [Summary](#summary) — Quick review of the shared prompt excerpt wiring and expected result.
- [Why](#why) — Why detail prompts need the same source-context behavior as review prompts.
- [Files (creates vs edits)](#files-creates-vs-edits) — The scoped files and the exact kind of changes in each.
- [Implementation](#implementation) — Required behavior, likely call sites, and constraints to preserve.
- [Tests](#tests) — Focused unit coverage to add in `tests/test_detail.py`.
- [Acceptance criteria](#acceptance-criteria) — Observable checks for completion.
- [References](#references) — Official Python references behind the upstream excerpt helper.
- [Deferred](#deferred) — Related prompt surfaces left out of this step.

## Why

`plan_tool/detail.py:_format_files_contents_block` currently clips each declared file from the beginning, so both the authoring prompt and the detail-quality prompt can show imports or module headers while hiding the function or class named by the step title. Step 1 supplies a reusable prompt excerpt helper for this exact source-preview problem; this step applies it to detail authoring and detail-quality prompts without changing the surrounding prompt contract.

## Files (creates vs edits)

- **New files:**
  - None. This step depends on step 1 for `plan_tool/prompt_excerpt.py`.

- **Existing files (edits only):**
  - `plan_tool/detail.py` — Update `_format_files_contents_block` to use the step 1 prompt excerpt helper after a declared file is successfully read, and derive candidate symbols from the step title plus the rendered file's declared path before rendering each excerpt.
  - `tests/test_detail.py` — Add prompt-rendering tests under the existing `TestRenderDetailPrompt` and `TestRenderDetailQualityPrompt` surfaces, plus any narrow helper-level assertions needed for `_format_files_contents_block`.

## Implementation

- **Foundational logic:** caller-owned source excerpt rendering.

- **Use the shared formatter as the integration point.**
  - Change `plan_tool/detail.py:_format_files_contents_block`, not both prompt renderers separately. `plan_tool/detail.py:render_detail_prompt` and `plan_tool/detail.py:render_detail_quality_prompt` already share that formatter, so one integration keeps the authoring prompt and quality prompt aligned.
  - Keep `plan_tool/detail.py:_MAX_PROMPT_FILE_BYTES` as the budget passed through from both prompt renderers. Do not introduce a second cap for detail prompts.

- **Delegate excerpt selection only after a successful read.**
  - Preserve the current `step.all_files` behavior in `plan_tool/detail.py:_format_files_contents_block`; this includes both `files:` and `creates:` through the `Step.all_files` property.
  - Keep `_no files declared_`, `### \`path\` _(not on disk)_`, and `### \`path\` _(unreadable: ...)_` in `plan_tool/detail.py`. The prompt excerpt helper should receive already-read text, not own filesystem error semantics.
  - For readable files, call the step 1 helper from `plan_tool/prompt_excerpt.py` with the repo-root-relative path string, full file text, candidate symbols, and `max_file_bytes`. The exact helper name depends on step 1, but the integration should consume its rendered excerpt or result object rather than re-implementing symbol windows in `plan_tool/detail.py`.

- **Reuse existing symbol derivation.**
  - Use `plan_tool/review.py:_derive_symbols` as the title-to-candidate source for `step.title`, then append bounded candidates from the rendered file's repo-relative stem and meaningful path components; do not add another tokenizer in `plan_tool/detail.py`.
  - `plan_tool/detail.py` already imports `plan_tool/review.py:heuristic_already_done`, so extending that import is likely enough. If import-order tests expose a cycle, use a body-local import inside `_format_files_contents_block` rather than duplicating the logic.

- **Preserve prompt shape.**
  - Keep the outer block header as `### \`path\`` and keep fenced code blocks for readable files. Existing tests in `tests/test_detail.py:TestRenderDetailPrompt` and `tests/test_detail.py:TestRenderDetailQualityPrompt` expect those markers.
  - Preserve the step 1 fallback metadata vocabulary when embedding helper output: `excerpt_kind`, `fallback_reason`, `truncated`, the visible "fallback preview" cue, and the literal `_(truncated)_` marker. The excerpt may come from the middle of the file, but the prompt still needs a visible marker when the full file exceeded the prompt budget.
  - Leave `plan_tool/detail.py:_format_sibling_details_block`, `plan_tool/detail.py:_format_prior_body_block`, and detail-body rendering alone. This step is about source-code excerpts for declared files, not prose-detail references.

- **Respect the step 1 boundary.**
  - Do not edit `plan_tool/prompt_excerpt.py` in this step unless step 1’s public contract is missing and the plan is being repaired. The declared files for this step are `plan_tool/detail.py` and `tests/test_detail.py`.
  - Do not change `plan_tool/review.py:render_review_prompt` or `plan_tool/review.py:_collect_done_step_file_contents`; those are owned by steps 1 and 2.

## Tests

- `test_detail_prompt_uses_symbol_excerpt_for_declared_python_file` — Builds a file with a large leading prelude and a later function/class matching the step title or declared file path; asserts `render_detail_prompt` includes the matching symbol and omits enough leading filler to prove it did not use a blind leading slice.
- `test_detail_quality_prompt_uses_same_symbol_excerpt_for_declared_python_file` — Uses the same oversized-file shape through `render_detail_quality_prompt`; asserts the relevant symbol appears before the detail body block.
- `test_detail_prompt_preserves_missing_unreadable_and_no_files_contracts` — Keeps the existing missing-file, unreadable-file, and no-files markers intact while readable files use the excerpt helper.
- `test_detail_prompt_renders_no_match_bounded_fallback_preview` — Uses a readable file with no title-derived or path-derived candidate match and asserts the detail prompt renders a bounded fallback preview with the shared fallback metadata vocabulary.
- `test_detail_prompt_preserves_truncation_marker_for_excerpted_large_file` — Asserts an oversized readable file still renders `_(truncated)_` when the helper chooses a non-leading excerpt.
- `test_detail_prompt_uses_step_title_and_path_symbols_for_each_file` — Uses a step title or declared file path that points to one symbol in a multi-symbol file and asserts the chosen excerpt follows the combined candidate list.

### Test-creation order (feature step)

This is a **feature** step — new behavior. Add the prompt-rendering tests with the implementation and keep every new test green before the step is considered finished.

## Acceptance criteria

- `plan_tool/detail.py:render_detail_prompt` includes a matching symbol window from a readable declared file even when that symbol appears after `max_file_bytes`.
- `plan_tool/detail.py:render_detail_quality_prompt` uses the same excerpt behavior through `plan_tool/detail.py:_format_files_contents_block`.
- Missing files still render `### \`path\` _(not on disk)_`.
- Unreadable files still render `### \`path\` _(unreadable: ...)_`.
- Steps with no declared files still render `_no files declared_`.
- A readable file with no title-derived or path-derived candidate match renders a bounded fallback preview with the shared `excerpt_kind`, `fallback_reason`, and `truncated` metadata.
- Oversized readable files still include the literal `_(truncated)_` marker.
- `tests/test_detail.py` covers both authoring and detail-quality prompt paths, and the full `tests/test_detail.py` suite passes.

## References

- [Python ast - Abstract Syntax Trees](https://docs.python.org/3/library/ast.html) — Read for the upstream helper’s Python symbol detection contract from step 1.
- [Python re - Regular Expression Operations](https://docs.python.org/3/library/re.html) — Read for the title-token and fallback matching behavior used around symbol candidates.
- [Python pathlib - Object-Oriented Filesystem Paths](https://docs.python.org/3/library/pathlib.html) — Read for the path handling style used by the prompt renderers and helper inputs.
- [Python textwrap - Text Wrapping and Filling](https://docs.python.org/3/library/textwrap.html) — Read for formatting excerpt blocks and markers without changing prompt shape.

## Deferred

- `plan_tool/review.py` prompt surfaces — Steps 1 and 2 own review and reconcile prompt excerpt wiring.
- `plan_tool/detail.py:_format_sibling_details_block` — Sibling detail files are tone and structure references, not declared source files, so they stay as leading clipped prose in this step.
- `plan_tool/detail.py:_format_prior_body_block` — Prior merged detail bodies must remain faithful full prose context, not symbol-selected source excerpts.
- Extending the prompt excerpt helper contract — Step 1 owns helper behavior; this step should consume it rather than redesign it.
