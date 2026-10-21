> **Auto-archived**: this plan was swept on 2026-07-16 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 2 — Move plan body section parsing into the parser

## Summary

Move the shared H2 plan-body parser from `plan_tool/review.py:split_body_sections` to `plan_tool/parser.py`, making plan-body sections available without depending on review code. Preserve the current heading normalization, section-boundary, and whitespace behavior exactly. Update `plan_tool/review.py` to consume the parser-owned function while keeping review findings unchanged. On green, parser characterization tests own the section-parsing contract and the existing review completeness tests still pass without behavioral changes.

## Table of Contents

- [Summary](#summary) — The parser ownership change and expected result.
- [Why](#why) — Why plan-body parsing must be shared infrastructure.
- [Input](#input) — The Markdown body shape and parsing contract that must remain stable.
- [Files (creates vs edits)](#files-creates-vs-edits) — The four existing files changed by this refactor.
- [Implementation](#implementation) — The ownership move, caller updates, and invariants.
- [Tests](#tests) — Characterization and integration coverage for the refactor.
- [Acceptance criteria](#acceptance-criteria) — Observable checks that prove behavior stayed the same.
- [Deferred](#deferred) — Related parsing work intentionally left outside this step.

## Why

`plan_tool/review.py:split_body_sections` implements general plan-Markdown parsing even though review is only one consumer. Later concept bootstrap and synchronization steps need the same section boundaries and normalized keys, and importing review code would couple those domain paths to review policy. Moving the foundational H2 section parse routine into `plan_tool/parser.py` gives those callers one neutral authority while preserving the existing review behavior. The heuristic matches in `plan_tool/review.py` and `tests/test_review.py` do not show this refactor is already implemented: the actual section parser still lives in review.

## Input

- **Plan Markdown body:** Parse only the prose returned as `plan_tool/parser.py:_Split.body`; frontmatter remains owned by `plan_tool/parser.py:_split_frontmatter`.
- **Recognized headings:** Treat Markdown H2 headings beginning with `##` and whitespace as sections.
- **Section boundaries:** A section ends at the next H1, H2, closing fence-shaped heading boundary already recognized by the current routine, or end of input. H3 and deeper headings remain part of the current H2 body.
- **Normalized keys:** Lowercase the full H2 name, trim surrounding whitespace, and remove trailing `:` or `.` punctuation.
- **Duplicate headings:** Preserve the current dictionary behavior, where a later normalized heading replaces an earlier entry with the same key.
- **Body values:** Exclude the heading line and trim surrounding newline characters as `plan_tool/review.py:split_body_sections` does at HEAD.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `plan_tool/parser.py` — Add the parser-owned public plan-body section routine near `_split_frontmatter`, and update the module contract to acknowledge that plan prose can be structurally parsed while write-back still preserves it unchanged.
  - `plan_tool/review.py` — Remove the local `split_body_sections` implementation, import the parser-owned routine, and keep all review callers using the shared behavior.
  - `tests/test_parser.py` — Add the characterization tests that define the shared section parser’s public behavior.
  - `tests/test_review.py` — Stop treating `split_body_sections` as review-owned and retain integration tests for review checks that consume parsed sections.

## Implementation

The foundational logic is: **split a plan’s Markdown body into normalized H2-name-to-body mappings without changing the body itself**.

- **Move ownership to `plan_tool/parser.py`.** Expose a public routine with the current `split_body_sections(body: str) -> dict[str, str]` contract. Keeping the existing name is the lowest-risk approach because it describes the operation clearly and reduces caller churn.
- **Preserve parsing behavior.** Move the logic from `plan_tool/review.py:split_body_sections` without changing its regular-expression rules, key normalization, section termination, duplicate handling, or newline trimming. This step is a refactor, not an opportunity to adopt a full Markdown parser or tighten accepted syntax.
- **Keep frontmatter and body concerns separate.** `plan_tool/parser.py:_split_frontmatter` should continue returning the untouched body used by `write_plan`. The section routine should derive a mapping from a body string and must not rewrite, cache, or attach normalized prose to the `Plan` schema.
- **Update the parser module description.** Remove the claim that prose is “never parsed.” State the narrower invariant: the body is not schema-validated or reserialized, and `plan_tool/parser.py:write_plan` preserves its current on-disk bytes while structural readers may inspect its H2 sections.
- **Make review a consumer.** Change `plan_tool/review.py` to import `split_body_sections` from `plan_tool.parser` beside `_split_frontmatter` and `parse_plan`, then delete its local implementation.
- **Cover every review call site.** Confirm the imported function continues to serve `plan_tool/review.py:check_body_completeness`, `_plan_body_sections`, `_summary_and_why_text`, `_extract_acceptance_criteria`, and the other direct `split_body_sections` calls. Helpers that first read `_Split.body`, such as `_collect_plan_body`, should retain their current error and empty-body behavior.
- **Keep review policy in review.** Placeholder detection, completeness skip markers, required-section selection, acceptance-name aliases, file-read failure handling, and issue construction remain in `plan_tool/review.py`. The parser routine should only identify sections.
- **Move contract tests with the function.** Transfer the direct section-splitting cases from `tests/test_review.py:TestSplitBodySections` to a parser-focused class in `tests/test_parser.py`. Leave `tests/test_review.py:TestCheckBodyCompleteness` and other review-level cases in place so they prove the import move did not change findings.
- **Do not merge detail parsing.** `plan_tool/detail.py:parse_detail_file_sections` deliberately uses first-significant-word tokens for a fixed detail-file schema. Its output contract differs from full normalized plan-section names, so sharing this routine would change behavior and mix two formats.

## Tests

- `tests/test_parser.py:test_split_body_sections_simple_two_sections` — returns normalized keys and bodies for two H2 sections.
- `tests/test_parser.py:test_split_body_sections_trailing_punctuation_normalized` — treats trailing `:` and `.` as equivalent to the unpunctuated heading.
- `tests/test_parser.py:test_split_body_sections_h1_terminates_section` — excludes a following H1 and its content from the preceding H2 body.
- `tests/test_parser.py:test_split_body_sections_h3_remains_in_parent_body` — keeps deeper headings inside the enclosing H2 section.
- `tests/test_parser.py:test_split_body_sections_empty_body_returns_empty` — returns an empty mapping for an empty body.
- `tests/test_parser.py:test_split_body_sections_duplicate_normalized_heading_uses_last` — pins the current overwrite behavior for duplicate normalized keys.
- `tests/test_parser.py:test_split_body_sections_preserves_internal_markdown` — leaves internal paragraphs, lists, and deeper headings unchanged apart from surrounding newline trimming.
- `tests/test_review.py:TestCheckBodyCompleteness.test_all_required_sections_present_no_issues` — proves review still recognizes a complete plan through the parser-owned routine.
- `tests/test_review.py:TestCheckBodyCompleteness.test_missing_three_sections` — proves missing-section findings remain unchanged.
- `tests/test_review.py:TestCheckBodyCompleteness.test_todo_placeholder_flagged` — proves section extraction still feeds placeholder policy correctly.
- `tests/test_review.py:TestCheckBodyCompleteness.test_none_answer_is_not_a_placeholder` — proves real empty-state prose is still retained and accepted.

### Test-creation order (refactor step)

1. Add or relocate the direct characterization cases into `tests/test_parser.py` while `plan_tool/review.py:split_body_sections` still owns the implementation; temporarily import or call the existing function as needed to pin HEAD behavior.
2. Add the duplicate-heading, H3, and internal-Markdown cases before moving code so any unclear edge behavior is settled against the current implementation.
3. Run the parser characterization tests and the existing `tests/test_review.py:TestCheckBodyCompleteness` tests before restructuring.
4. Move the routine and update imports.
5. Run the same characterization tests unchanged. They must pass without editing expected values after the restructuring.
6. Run all of `tests/test_parser.py` and `tests/test_review.py` to catch parser round-trip or review integration regressions.

## Acceptance criteria

- `plan_tool/parser.py` publicly owns `split_body_sections(body: str) -> dict[str, str]`.
- `plan_tool/review.py` contains no local `split_body_sections` implementation and consumes the parser-owned function.
- Existing H2 key normalization, section boundaries, duplicate handling, and body trimming produce the same mappings as before the move.
- `plan_tool/parser.py:write_plan` continues to preserve the current on-disk prose body unchanged.
- `plan_tool/review.py:check_body_completeness` produces the same missing, empty, placeholder, and skipped-section results as before the refactor.
- The direct section-parsing characterization tests live in `tests/test_parser.py` and pass unchanged before and after the move.
- The complete `tests/test_parser.py` and `tests/test_review.py` suites pass.

## Deferred

- `plan_tool/detail.py:parse_detail_file_sections` consolidation — its token-based detail schema differs from the plan-body mapping contract, so combining them needs a separate compatibility decision.
- Returning sections from `parse_plan` or storing them on `plan_tool.schema.Plan` — that would change the parser or schema API and belongs to a feature step, not this behavior-preserving move.
- Markdown syntax expansion — setext headings, H3-as-top-level sections, fenced-code awareness, and a third-party Markdown parser would change accepted behavior and require plan-level scope.
