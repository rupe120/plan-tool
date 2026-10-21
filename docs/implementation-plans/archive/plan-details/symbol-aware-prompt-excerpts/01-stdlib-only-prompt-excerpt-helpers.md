> **Auto-archived**: this plan was swept on 2026-07-07 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 1 — Add Stdlib-Only Prompt Excerpt Helpers

## Summary

This step creates `plan_tool/prompt_excerpt.py` as a small leaf module for building source excerpts that favor relevant symbols over a blind leading slice. `plan_tool/review.py:render_review_prompt` should use it when rendering the `## Current file contents` block for declared step files, while preserving the existing missing/unreadable path behavior. The main design choice is to use only Python stdlib parsing and text tools, with best-effort symbol windows for Python, markdown heading/section windows for detail files, and safe bounded fallbacks for other files. On green, `tests/test_prompt_excerpt.py` covers the helper contract directly, and the existing `tests/test_review.py:TestRenderReviewPrompt` expectations still pass with the new excerpt output.

## Table of Contents

- [Summary](#summary) — Quick review of the new helper and the review prompt wiring.
- [Why](#why) — The problem with blind leading file slices and why a leaf helper is the right first step.
- [Files creates vs edits](#files-creates-vs-edits) — The new files and the narrow edit to the existing renderer.
- [Implementation](#implementation) — Required behavior, suggested helper shape, call sites, and constraints.
- [Tests](#tests) — Unit coverage for symbol windows, fallbacks, formatting, and review integration.
- [Acceptance criteria](#acceptance-criteria) — Observable conditions for considering the step done.
- [References](#references) — Stdlib docs relevant to this helper.
- [Deferred](#deferred) — Related prompt and parser work that stays out of this step.

## Why

`plan_tool/review.py:render_review_prompt` currently includes each declared file by reading the whole file and clipping from the start. That is cheap, but it often gives the reviewer imports, constants, or module headers while the symbol named by the step title sits past the cap. This step adds a reusable, stdlib-only helper that can put the most relevant class/function/assignment window into the prompt without adding parser dependencies or moving review orchestration into a heavier module.

## Files (creates vs edits)

- **New files:**
  - `plan_tool/prompt_excerpt.py` — Add the leaf helper API, small dataclasses, source parsing, window selection, and markdown rendering helpers.
  - `tests/test_prompt_excerpt.py` — Add direct unit tests for the helper without going through the full review pipeline.

- **Existing files (edits only):**
  - `plan_tool/review.py` — Import the new helper and use it in `render_review_prompt` for the declared-file contents block. Consider using the same helper in `plan_tool/review.py:_collect_done_step_file_contents` if doing so keeps its current header and missing/unreadable behavior unchanged.

## Implementation

- **Foundational logic:** symbol-aware prompt excerpt selection.

- **Create a leaf helper in `plan_tool/prompt_excerpt.py`.**
  - Keep it stdlib-only. Expected imports are in the `ast`, `dataclasses`, `pathlib`, `re`, `tokenize`, and `textwrap` family.
  - Do not import `plan_tool/review.py`, `plan_tool/schema.py`, `plan_tool/detail.py`, or CLI modules. The helper should accept plain values such as a repo-relative path string, file text, and candidate symbols.
  - A practical public shape is a small result dataclass such as `ExcerptResult` plus a function such as `build_prompt_excerpt(...)` or `render_prompt_excerpt(...)`. The exact names can vary, but the public contract should be obvious from `tests/test_prompt_excerpt.py`.
  - Define the minimal fallback metadata contract on the result: `excerpt_kind` is `symbol` or `fallback`; `fallback_reason` is `parse-error`, `no-symbol-match`, or `unsupported-file-type` when `excerpt_kind` is `fallback`; and `truncated` records whether content was omitted to honor the prompt budget.

- **Prefer real symbol windows for Python files.**
  - For `.py` text, use `ast.parse` to find top-level and nested `FunctionDef`, `AsyncFunctionDef`, `ClassDef`, and useful assignment nodes when their names match the supplied candidate symbols.
  - Use `lineno` / `end_lineno` when present to slice full source lines. Include a small amount of surrounding context so decorators and adjacent comments are not lost. For Python symbol excerpts, preserve the contiguous module import block when it fits within the per-file byte budget; when it does not fit, keep the selected symbol window authoritative and mark the omitted context with the shared `_(truncated)_` marker.
  - If AST parsing fails, do not raise. Return a bounded fallback excerpt with `excerpt_kind=fallback`, `fallback_reason=parse-error`, and a rendered "fallback preview" cue that makes it clear the output is not a symbol match.

- **Handle non-Python files safely.**
  - For `.md` text, support markdown heading/section matching with stdlib line or regex logic. A candidate that matches a heading should return a bounded window for that section so plan-audit detail bundles can surface relevant step-detail sections.
  - For `.ts`, `.tsx`, `.js`, `.jsx`, `.mjs`, `.cjs`, `.go`, `.rs`, `.java`, `.kt`, `.rb`, `.swift`, `.md`, `.toml`, and `.json`, use conservative regex or line matching only. Do not try to implement language parsers.
  - For files where no candidate symbol is found, keep the current bounded leading excerpt behavior so the prompt still gives orientation, and set `fallback_reason=no-symbol-match`.
  - For unsupported file types that use a bounded leading excerpt, set `fallback_reason=unsupported-file-type`.
  - Keep binary-ish or unreadable text handling in `plan_tool/review.py:render_review_prompt`; the helper should work on text it is given rather than owning filesystem error messages.

- **Preserve the review prompt contract.**
  - `plan_tool/review.py:render_review_prompt` currently renders missing files as ``### `<path>` _(not on disk)_`` and unreadable files as ``### `<path>` _(unreadable: ...)``. Keep those branches in `plan_tool/review.py`.
  - Replace only the successful-file branch that now builds `snippet = body[:max_file_bytes]`.
  - Keep the markdown shape under `## Current file contents`: a `###` path heading followed by a fenced block. Existing tests in `tests/test_review.py:TestRenderReviewPrompt` assert this section contains file contents and `(new)` creates paths; add focused coverage for current-file truncation if this branch needs a new assertion.
  - Preserve `step_filter` and `seen_paths` behavior in `plan_tool/review.py:render_review_prompt`; excerpt selection must not cause duplicate file blocks or leak other steps into a filtered prompt.

- **Feed the helper candidate symbols from `plan_tool/review.py`.**
  - Reuse `plan_tool/review.py:_derive_symbols` to turn each step title into candidate symbols for that step, then append bounded candidates from the rendered file's repo-relative stem and meaningful path components. Do not duplicate that stopword logic in `plan_tool/prompt_excerpt.py`.
  - Keep file-reference candidate derivation in the caller layer with the same conservative token rules as title symbols: derive it from declared file paths, ignore extension-only and generic directory noise, preserve ordering after title-derived candidates, and pass the resulting list as plain candidate strings.
  - When a file appears in more than one reviewed step, merge or preserve candidate symbols before rendering so the first seen path does not discard later step intent. One way: build a `dict[str, list[str]]` while walking the filtered steps, then render each path once.
  - Include `creates:` paths as well as `files:` paths, matching the existing `render_review_prompt` behavior.

- **Keep size limits honest.**
  - Honor `max_file_bytes` as the main prompt budget for each file block. A symbol match should choose better lines, not grow the prompt without bound.
  - Mark omitted content in a stable, human-readable way. The existing `_(truncated)_` string should still appear when the helper omits file content because of the byte cap, and fallback excerpts should use the same "fallback preview" vocabulary across prompt renderers; `tests/test_review.py:TestRenderReviewPrompt.test_oversized_detail_truncated` covers the same marker for step-detail excerpts, not the `## Current file contents` block.
  - Prefer line-based clipping, then enforce the byte or character budget after rendering. Avoid splitting multi-byte text in a way that raises.

- **Keep parallel prompt readers in mind.**
  - `plan_tool/review.py:_collect_done_step_file_contents` repeats the same successful-file leading-slice logic for the criteria fulfillment prompt. It is in scope because `plan_tool/review.py` is in the file list. If the helper can be used there without changing that prompt’s headings or DONE-step filtering, use it to avoid two excerpt rules in one module.
  - `plan_tool/review.py:_render_step_detail_block` renders step detail prose, not source code. Leave it as a bounded leading excerpt unless the implementation naturally supports prose without changing the current detail prompt contract.
  - `plan_tool/review.py:heuristic_already_done` and `_scan_for_heuristic_hit` are detection logic, not prompt rendering. Do not fold them into `plan_tool/prompt_excerpt.py`.

## Tests

- `test_python_function_symbol_window_beats_file_header` — A Python file with a long header section and a matching function later in the file returns an excerpt containing the function, not only the file start.
- `test_python_symbol_window_preserves_module_import_block_when_budget_allows` — A Python symbol match includes the contiguous top-of-file import block when that block fits inside the per-file byte budget.
- `test_python_symbol_window_marks_omitted_import_context_when_budget_excludes_it` — A Python symbol match keeps the selected symbol window when the import block cannot fit and uses the shared truncation marker for the omitted context.
- `test_python_class_symbol_window_includes_decorator_context` — A decorated class match includes the decorator or nearby context needed to understand the class.
- `test_python_assignment_symbol_window` — A top-level assignment matching a candidate symbol can be selected when no function or class owns the name.
- `test_multiple_symbols_prefers_first_real_match` — Candidate symbols are tried in order and the first real symbol match wins deterministically.
- `test_invalid_python_uses_bounded_fallback` — Syntax errors do not raise and still produce a capped excerpt.
- `test_fallback_metadata_uses_stable_vocabulary` — Parse-error, no-match, and unsupported-file fallbacks expose the shared `excerpt_kind`, `fallback_reason`, and `truncated` fields and render the "fallback preview" cue.
- `test_markdown_heading_symbol_window_uses_matching_section` — A Markdown detail file with a matching heading past the file header returns a bounded section excerpt instead of the leading slice.
- `test_non_python_regex_match_uses_symbol_line_window` — A TypeScript or Markdown sample with a matching symbol returns a small window around that line.
- `test_no_symbol_match_returns_leading_excerpt` — A file with no matching symbols keeps the current orientation behavior.
- `test_excerpt_marks_truncation_when_content_omitted` — Large input produces the agreed truncation marker.
- `test_render_review_prompt_uses_symbol_excerpt_for_declared_file` — `plan_tool/review.py:render_review_prompt` includes the late matching symbol for a step title or declared file path under `## Current file contents`.
- `test_render_review_prompt_keeps_missing_and_unreadable_branches` — Review rendering still reports missing/unreadable files without calling the helper on absent content.

### Test-creation order (feature step)

This is a feature step. Add the direct `tests/test_prompt_excerpt.py` cases alongside `plan_tool/prompt_excerpt.py`, then update the focused review integration tests in `tests/test_review.py:TestRenderReviewPrompt`. Every new test must be green before this step is considered finished.

## Acceptance criteria

- `plan_tool/prompt_excerpt.py` imports only stdlib modules.
- `plan_tool/prompt_excerpt.py` exposes a small public helper contract covered by `tests/test_prompt_excerpt.py`.
- A Python file with a matching late `def`, `async def`, `class`, or top-level assignment renders the matching symbol window instead of only the start of the file.
- A Markdown file with a matching heading renders the matching section window instead of only the start of the file.
- Invalid Python, unsupported extensions, and no-match files return bounded fallback excerpts without raising and expose the shared `excerpt_kind`, `fallback_reason`, and `truncated` metadata.
- `plan_tool/review.py:render_review_prompt` still includes `files:` and `creates:` entries, respects `step_filter`, and renders each repo-relative path once.
- `plan_tool/review.py:render_review_prompt` keeps the existing not-on-disk and unreadable messages.
- Existing `tests/test_review.py:TestRenderReviewPrompt` tests pass.
- New `tests/test_prompt_excerpt.py` tests pass.

## References

- [Python ast - Abstract Syntax Trees](https://docs.python.org/3/library/ast.html) — Use this for `lineno`, `end_lineno`, and node types when finding Python symbol ranges.
- [Python tokenize - Tokenizer for Python Source](https://docs.python.org/3/library/tokenize.html) — Use this if import/header detection needs token-level handling without a third-party parser.
- [Python re - Regular Expression Operations](https://docs.python.org/3/library/re.html) — Use this for conservative non-Python symbol line matching.
- [Python dataclasses - Data Classes](https://docs.python.org/3/library/dataclasses.html) — Use this for the helper result object and any small input context object.
- [Python pathlib - Object-Oriented Filesystem Paths](https://docs.python.org/3/library/pathlib.html) — Use this for suffix and path handling at the review/helper boundary.
- [Python textwrap - Text Wrapping and Filling](https://docs.python.org/3/library/textwrap.html) — Use this for stable indentation or formatting of excerpt markers.

## Deferred

- Full multi-language parsing — This step uses conservative stdlib matching outside Python; richer TypeScript/Rust/Go parsing would need a separate dependency and plan decision.
- Semantic symbol discovery from step detail bodies — This step can pass title-derived symbols from `plan_tool/review.py:_derive_symbols` plus declared file path candidates; mining detail prose for more symbols is a later prompt-quality improvement.
- Changing `plan_tool/prompts/review.md` instructions — The prompt already says embedded file contents are a truncated preview and tells reviewers to Read/Grep HEAD. This step can keep that wording unless the final marker text changes materially.
- Reworking `plan_tool/review.py:heuristic_already_done` — The existing already-done heuristic remains separate detection logic and should not be merged with prompt excerpt rendering in this step.
