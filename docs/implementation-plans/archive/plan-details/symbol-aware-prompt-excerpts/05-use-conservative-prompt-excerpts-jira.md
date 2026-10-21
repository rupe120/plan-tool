> **Auto-archived**: this plan was swept on 2026-07-07 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 5 — Use Conservative Prompt Excerpts in Jira Prompts

## Summary

This step updates `plan_tool/jira.py` so Jira story-generation prompts use the step 1 prompt excerpt helper for each readable declared file in the `**Current file contents:**` section. The production change is centered on `plan_tool/jira.py:_render_step_files_contents`, which is called by `plan_tool/jira.py:_render_steps_block` and therefore by `plan_tool/jira.py:render_jira_prompt` in normal, append, and refresh flows. The key design decision is to keep Jira's file discovery, missing-file markers, unreadable-file markers, headings, and fenced blocks in `plan_tool/jira.py`, while delegating only successful text excerpt selection to the shared helper from step 1. On green, `tests/test_jira.py:TestRenderJiraPrompt` proves a symbol named by a step title or declared file path can appear past a small byte cap without changing the existing Jira prompt wrapper contract.

## Table of Contents

- [Summary](#summary) — Quick review of the Jira prompt excerpt change and expected result.
- [Why](#why) — Why Jira story prompts need better source previews.
- [Files (creates vs edits)](#files-creates-vs-edits) — The scoped production and test files.
- [Implementation](#implementation) — Required behavior, likely call sites, and constraints to preserve.
- [Tests](#tests) — Focused unit coverage to add in `tests/test_jira.py`.
- [Acceptance criteria](#acceptance-criteria) — Observable checks for completion.
- [References](#references) — Official Python references behind the upstream excerpt helper.
- [Deferred](#deferred) — Related prompt surfaces left outside this step.

## Why

`plan_tool/jira.py:_render_step_files_contents` currently reads each declared file and slices from the beginning, so the Jira prompt can show imports or module headers while hiding the function or class named by the plan step. Jira story generation uses that prompt to decide how to consolidate, split, and describe plan work, so the source preview should favor the relevant symbol when step 1's helper can find one. This step applies that helper only to Jira's readable source-file previews and keeps the rest of the story export contract unchanged.

## Files (creates vs edits)

- **New files:**
  - None. `plan_tool/prompt_excerpt.py` is owned by step 1 and is consumed here after that dependency has landed.

- **Existing files (edits only):**
  - `plan_tool/jira.py` — Use the step 1 prompt excerpt helper inside `_render_step_files_contents` after a file is successfully read, and derive candidate symbols from the owning Jira step title plus the rendered file's declared path before rendering each readable file block.
  - `tests/test_jira.py` — Add focused coverage under `TestRenderJiraPrompt` for symbol-aware source previews in Jira prompts while keeping existing prompt shape tests green.

## Implementation

- **Foundational logic:** caller-owned Jira source excerpt selection.

- **Use `_render_step_files_contents` as the integration point.**
  - Change `plan_tool/jira.py:_render_step_files_contents`, not `plan_tool/jira.py:render_jira_prompt` or `plan_tool/jira.py:_render_steps_block` directly. `_render_steps_block` already passes each `Step` into `_render_step_files_contents`, so one integration covers the whole Jira prompt.
  - Keep `plan_tool/jira.py:_MAX_PROMPT_FILE_BYTES` as the budget passed from `render_jira_prompt` through `_render_steps_block` into `_render_step_files_contents`.
  - Keep `Step.all_files` as the file source. That preserves the current `files:` plus `creates:` behavior and the existing ordering.

- **Delegate only readable text selection.**
  - Preserve the current `_render_step_files_contents` branches for `_no files declared_`, `#### \`path\` _(not on disk)_`, and `#### \`path\` _(unreadable: ...)_`.
  - After `path.read_text(encoding="utf-8", errors="replace")` succeeds, pass the repo-root-relative file path string, full body text, candidate symbols, and `max_file_bytes` into the helper from `plan_tool/prompt_excerpt.py` that step 1 provides.
  - Keep Jira's outer block format unchanged: `#### \`path\``, a fenced code block, and the step 1 fallback metadata vocabulary when embedding helper output: `excerpt_kind`, `fallback_reason`, `truncated`, the visible "fallback preview" cue, and the literal `_(truncated)_` marker when the rendered excerpt represents a bounded preview of a larger file.

- **Use the existing title-symbol owner.**
  - Derive candidates from the owning step title before rendering that step's file blocks, then append bounded candidates from the rendered file's repo-relative stem and meaningful path components. The existing owner for the title heuristic is `plan_tool/review.py:_derive_symbols`; do not create a second title tokenizer in `plan_tool/jira.py`.
  - Prefer a normal import from `plan_tool.review` only if it does not introduce an import cycle in HEAD. If importing `plan_tool.review._derive_symbols` at module load is awkward, use a body-local import in `_render_step_files_contents`; the important rule is that Jira reuses the existing heuristic rather than copying its stopword list or regex.
  - Pass the symbols from the current `Step` only. Jira renders one file block per step and does not currently de-duplicate file paths across steps, so do not merge symbols across steps in this change.

- **Keep prompt semantics conservative.**
  - Treat the helper as a content selector, not a block renderer, unless step 1's public contract explicitly owns the complete fenced-block rendering. Jira's existing heading and code-fence contract should remain in `plan_tool/jira.py`.
  - Do not change `plan_tool/jira.py:_render_step_detail`. That helper renders the authored step-detail markdown body, not declared source files, and it has different prompt semantics from `**Current file contents:**`.
  - Do not edit `plan_tool/prompts/jira.md`. The template already receives a `steps_block`; this step changes the source excerpt inside that block, not the story-generation instructions.
  - Do not change `parse_jira_response`, `format_markdown`, `format_json`, `export_jira`, existing-ticket reconciliation, or story-id validation. Those surfaces are downstream of prompt rendering and should stay untouched.

- **Respect append and refresh flows.**
  - `plan_tool/jira.py:render_jira_prompt` calls `_render_steps_block` before append-mode handling finishes, so the same `_render_step_files_contents` behavior applies when `existing`, `uncovered_steps`, or `refresh_tickets` are passed.
  - Keep covered-step annotations from `_render_steps_block` unchanged. A covered step may still appear in the prompt as frozen context, and its current file preview should use the same conservative excerpt rule as any other step.

## Tests

- `test_jira_prompt_uses_symbol_excerpt_for_declared_file` — Builds a file whose title-matching function or class appears after enough leading filler to exceed a small `max_file_bytes`; `render_jira_prompt` includes the matching symbol and excludes earlier unrelated filler that only a leading slice would show.
- `test_jira_prompt_preserves_missing_unreadable_and_new_file_markers` — Verifies `_render_step_files_contents` still renders `(not on disk)`, `(unreadable: ...)`, `(new)` from `_render_steps_block`, and `_no files declared_` without routing those branches through the helper.
- `test_jira_prompt_renders_no_match_bounded_fallback_preview` — Uses a readable file with no title-derived or path-derived candidate match and asserts the Jira prompt renders a bounded fallback preview with the shared fallback metadata vocabulary.
- `test_jira_prompt_preserves_truncated_marker_with_excerpt` — Uses a small byte cap and a larger readable file; the rendered Jira prompt still contains the literal `_(truncated)_` marker when the helper returns a bounded preview.
- `test_jira_prompt_uses_current_step_title_symbols` — Uses two steps that reference similar files or similarly named symbols and proves each rendered block is selected from the `Step.title` that owns that block, not from a merged or global symbol set.
- `test_jira_prompt_append_mode_uses_same_file_excerpt_behavior` — Calls `render_jira_prompt` with `existing` and `uncovered_steps` and asserts the symbol-aware file excerpt still appears while already-covered ticket annotations remain unchanged.

### Test-creation order (feature step)

This is a feature step. Add the focused `tests/test_jira.py:TestRenderJiraPrompt` cases with the implementation, using small `max_file_bytes` values so the tests fail against the current leading-slice behavior. The step is not finished until every new test is green and the existing `tests/test_jira.py` Jira prompt tests still pass.

## Acceptance criteria

- `plan_tool/jira.py:_render_step_files_contents` calls the step 1 prompt excerpt helper for readable files and no longer uses `body[:max_file_bytes]` directly for the `**Current file contents:**` source preview.
- `plan_tool/jira.py:_render_step_files_contents` preserves `_no files declared_`, `#### \`path\` _(not on disk)_`, `#### \`path\` _(unreadable: ...)_`, fenced code blocks, and the literal `_(truncated)_` marker behavior.
- `plan_tool/jira.py:_render_steps_block` and `plan_tool/jira.py:render_jira_prompt` keep their public signatures and prompt-section ordering unchanged.
- `tests/test_jira.py:TestRenderJiraPrompt` includes a regression test where a symbol from the step title or declared file path appears past a small byte cap and is still included in the rendered Jira prompt.
- `tests/test_jira.py:TestRenderJiraPrompt` includes a no-match bounded fallback preview test that asserts the shared `excerpt_kind`, `fallback_reason`, and `truncated` metadata appears in the rendered Jira prompt.
- `tests/test_jira.py` passes.

## References

- [Python ast - Abstract Syntax Trees](https://docs.python.org/3/library/ast.html) — Read for the upstream step 1 helper behavior that finds Python function and class windows.
- [Python re - Regular Expression Operations](https://docs.python.org/3/library/re.html) — Read for the title-symbol and fallback matching behavior reused by prompt excerpt selection.
- [Python pathlib - Object-Oriented Filesystem Paths](https://docs.python.org/3/library/pathlib.html) — Read for the path handling style used by `plan_tool/jira.py:_render_step_files_contents`.

## Deferred

- `plan_tool/jira.py:_render_step_detail` — Leave step-detail markdown slicing unchanged because this step targets declared source-file previews under `**Current file contents:**`.
- `plan_tool/prompts/jira.md` — Leave the prompt template unchanged unless a later step changes the visible marker or story-generation contract.
- `plan_tool/prompt_excerpt.py` helper redesign — Step 1 owns the helper API; if its public contract is missing a value Jira needs, reconcile that dependency instead of expanding this step beyond `plan_tool/jira.py` and `tests/test_jira.py`.
