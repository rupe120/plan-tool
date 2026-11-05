> **Auto-archived**: this plan was swept on 2026-11-05 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 1 — Move fenced spans into review.py

<!-- plan-tool:detail-format-version: 1 -->

## Summary

Move the citation-fence span scanner from `plan_tool/jira_grade.py:fenced_spans` into `plan_tool/review.py`, where its callers already live. Update review’s local callers to use the moved function and remove the Jira-grade dependency for this behavior. Keep the scanner’s current citation-specific parsing rules intact, without changing `plan_tool/scope_fence.py:_fenced_code_spans`. On green, review parsing continues to ignore heading-like text inside protected citations while Jira-grade tests no longer own this shared review behavior.

## Table of Contents

- [Summary](#summary) — The move and its observable result.
- [Table of Contents](#table-of-contents) — Links to this detail’s sections.
- [Why](#why) — Why review must own its citation parser before Jira grade is removed.
- [Input](#input) — The existing citation and fence-parsing contract this step preserves.
- [Files (creates vs edits)](#files-creates-vs-edits) — The focused source and test changes.
- [Implementation](#implementation) — Required parser behavior and ownership boundary.
- [Tests](#tests) — Unit coverage for preserved fence behavior.
- [Acceptance criteria](#acceptance-criteria) — Reviewable completion checks.
- [References](#references) — The relevant fence syntax reference.
- [Applicable guardrails](#applicable-guardrails) — Scope limits for the Jira-grade retirement.

## Why

`plan_tool/review.py` uses `fenced_spans` to keep quoted citations from being parsed as real finding boundaries, but the helper currently belongs to the Jira-grade module that this plan retires. Move the helper before deleting that owner so review keeps its established protection and no longer depends on the removed Jira-grade lane.

## Input

- **Citation body text:** `plan_tool/review.py:_split_audit_fix`, `plan_tool/review.py:_split_audit_restated_and_fix`, and `plan_tool/review.py:_find_redirect_heading` pass model-produced text through the span scanner before treating markers or headings as structure.
- **Existing scanner contract:** `plan_tool/jira_grade.py:fenced_spans` currently returns character offsets over the original text, including CRLF bytes, and treats an unclosed opener as spanning through end of text.
- **Separate Markdown scanner:** `plan_tool/scope_fence.py:_fenced_code_spans` has different callers and an inline-backtick exception. This step must not change that function or make review adopt its behavior accidentally.

## Files (creates vs edits)

- **New files:** None.

- **Existing files (edits only):**
  - `plan_tool/review.py` — Define and use the citation-specific `fenced_spans` helper locally; remove its import from `plan_tool/jira_grade.py`.
  - `plan_tool/jira_grade.py` — Remove `fenced_spans` and its citation-only marker support after the review-owned replacement exists.
  - `tests/test_review.py` — Move or add focused coverage for review-owned fence spans and citation-boundary protection.
  - `tests/test_jira_grade.py` — Remove the relocated shared-parser tests while retaining Jira-grade contract coverage that still belongs to this module.

## Implementation

- **Make `plan_tool/review.py` the owner of citation fence spans.** Place `fenced_spans` and any private matcher it needs near review’s other parsing helpers, then update `indent_bullet_body`, `_find_redirect_heading`, `_split_audit_fix`, and `_split_audit_restated_and_fix` to use the local helper.

- **Preserve the existing return contract.** The helper must continue to return `(start, end)` character offsets into the original string. Scan with line endings retained so a CRLF input produces offsets that slice the original CRLF text correctly.

- **Keep citation parsing intentionally broader than rendered Markdown.** A fence indented beyond three spaces must still protect citation text. This is review’s model-output safety rule, so do not narrow it to CommonMark’s rendered-Markdown indentation limit.

- **Keep delimiter matching exact.** A closer must use the same delimiter character as its opener and contain at least as many delimiter characters. Tilde and backtick fences must not close each other, and a shorter nested run must not close a longer opener.

- **Fail safe on an unclosed citation fence.** An unclosed opener must span through end of text, preventing later apparent `### Restated`, `### Fix`, or redirect headings from being treated as live review structure.

- **Preserve review’s current inline-backtick behavior.** A line beginning with an inline backtick span remains subject to the existing `fenced_spans` citation scanner behavior; do not import or copy `plan_tool/scope_fence.py:_fenced_code_spans`’s inline-span exception. The two scanners serve different contracts.

- **Keep the scope-fence scanner unchanged.** `plan_tool/scope_fence.py:_fenced_code_spans` remains the owner for its existing document and frontmatter callers. Do not consolidate these helpers in this focused retirement step.

- **Move test ownership with code ownership.** `tests/test_review.py` should contain direct tests for `plan_tool/review.py:fenced_spans` plus the boundary-level tests that prove protected citations cannot supply false review headings. Keep Jira-grade tests focused on the Jira-grade code that remains after this move.

## Tests

### Tests for this step

- `test_fenced_spans_returns_original_text_offsets_for_closed_fence` — asserts a returned review span slices the full fenced block from the original text.
- `test_fenced_spans_unclosed_fence_spans_to_end_of_text` — asserts an unclosed citation opener protects all remaining text.
- `test_fenced_spans_requires_matching_delimiter_character_and_length` — asserts tilde/backtick mismatch and a shorter same-character run cannot close an opener.
- `test_fenced_spans_preserves_crlf_offsets` — asserts spans identify the correct CRLF-delimited substring.
- `test_fenced_spans_recognizes_fence_indented_beyond_three_spaces` — asserts deeply indented citation fences remain protected.
- `test_fenced_spans_preserves_current_leading_inline_backtick_span_treatment` — asserts review retains the scanner behavior for a line beginning with an inline backtick span.
- `test_indented_citation_fence_protects_the_boundary` — asserts an indented fake `### Restated` stays inside the citation while the real restated and fix blocks are extracted.
- `test_unclosed_citation_fence_degrades_to_none_not_corruption` — asserts review does not invent restated or fix content after an unclosed citation fence.
- `tests/test_jira_grade.py` regression coverage — keeps remaining Jira-grade validation tests green after the shared helper and its tests move.

Every listed test must be green before this step is considered finished.

## Acceptance criteria

- `plan_tool/review.py:fenced_spans` exists and review’s citation-parsing callers use it without importing `fenced_spans` from `plan_tool/jira_grade.py`.
- `plan_tool/jira_grade.py` no longer defines `fenced_spans` or its citation-only fence marker.
- Review identifies fenced spans for backtick and tilde fences, deep indentation, matched delimiter lengths, CRLF text, and unclosed openers with the existing results.
- A line beginning with an inline backtick span has the same citation-parser result before and after the move.
- `test_indented_citation_fence_protects_the_boundary` passes.
- `plan_tool/scope_fence.py:_fenced_code_spans` remains unchanged.
- `tests/test_review.py` and `tests/test_jira_grade.py` pass.

## References

- [CommonMark Specification — Fenced code blocks](https://spec.commonmark.org/0.31.2/#fenced-code-blocks) — Read the delimiter-character and minimum-closing-length rules that the citation scanner preserves while deliberately accepting deeper indentation.
- [CommonMark Specification — Code spans](https://spec.commonmark.org/0.31.2/#code-spans) — Read the distinction between inline backtick spans and fenced blocks when preserving review’s existing behavior.

## Applicable guardrails

- **The plan’s “## Step intent”.** Keep finding-annotation fence protection working after the Jira-grade module disappears; do not expand this move into unrelated review parsing changes.
- **The plan’s “## Scope guardrails”.** Move only the dependency that blocks Jira-grade deletion. Do not add a replacement grade, compatibility reader, migration, or output change.
- **The plan’s “## Out of scope”.** Leave run-grade detail authoring and Jira story and developer-handoff behavior unchanged.
