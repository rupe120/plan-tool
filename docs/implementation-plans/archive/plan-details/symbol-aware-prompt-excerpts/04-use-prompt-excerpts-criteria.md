> **Auto-archived**: this plan was swept on 2026-07-07 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 4 — Use Prompt Excerpts in Plan-Audit Bundles

## Summary

This step updates `plan_tool/review.py` so the plan-audit implementation bundle uses the prompt excerpt helper from step 1 instead of slicing readable detail files from the start. The production work lives in `plan_tool/review.py:_format_audit_detail_bundle`; `tests/test_review.py` gets focused coverage under `TestCheckPlanAudit`. The key design decision is to keep file discovery, missing-file notes, unreadable-file notes, headers, and prompt-template wiring in `plan_tool/review.py`, while delegating only successful text excerpt selection to `plan_tool/prompt_excerpt.py`. On green, plan-audit detail bundles can surface the relevant step-detail section without changing their outer prompt contract.

## Table of Contents

- [Summary](#summary) — Quick review of the review-prompt bundle changes and expected result.
- [Why](#why) — Why the plan-audit bundle needs the same excerpt behavior as the main review prompt.
- [Files creates vs edits](#files-creates-vs-edits) — The scoped production and test files.
- [Implementation](#implementation) — Required behavior, likely call sites, and constraints to preserve.
- [Tests](#tests) — Focused test cases to add in `tests/test_review.py`.
- [Acceptance criteria](#acceptance-criteria) — Observable checks for completion.
- [References](#references) — Stdlib references behind the upstream excerpt helper.
- [Deferred](#deferred) — Related prompt surfaces left outside this step.

## Why

`plan_tool/review.py` still has a plan-audit prompt bundle that reads a detail file and takes `text[:max_file_bytes]`: `_format_audit_detail_bundle` for `render_plan_audit_prompt`. That can hide the markdown section named by the owning step title behind setup prose or earlier unrelated sections. Step 1 supplies a reusable prompt excerpt helper for this exact problem, so this step applies it to the plan-audit detail bundle without changing skip behavior, path resolution, prompt headings, or finding parsing. Criteria-fulfillment DONE-step source excerpts are owned by step 2.

## Files (creates vs edits)

- **New files:**
  - None. `plan_tool/prompt_excerpt.py` is owned by step 1 and is consumed here.

- **Existing files (edits only):**
  - `plan_tool/review.py` — Use the step 1 prompt excerpt helper in `_format_audit_detail_bundle` after each detail file is successfully read. Keep `render_plan_audit_prompt`, `audit_detail_bundle_status`, and prompt-template substitution behavior unchanged except for the excerpt text they receive.
  - `tests/test_review.py` — Add coverage under `TestCheckPlanAudit` proving the bundle includes relevant excerpt windows past a small byte cap while preserving existing headers, missing/unreadable markers, and truncation markers.

## Implementation

- **Foundational logic:** caller-owned prompt excerpt rendering.

- **Use the step 1 helper only on readable text.**
  - Import the helper from `plan_tool/prompt_excerpt.py` in `plan_tool/review.py` once step 1 has landed.
  - Keep filesystem handling in `plan_tool/review.py`. The helper should receive a repo-root-relative path string, already-read text, candidate symbols, and the existing byte budget.
  - Do not move `(not on disk)`, `(unreadable: ...)`, detail-path fallback, or skip decisions into the helper.

- **Update plan audit at `_format_audit_detail_bundle`.**
  - Keep the path rules exactly where they are: use `step.detail` when set, otherwise call `plan_tool/detail.py:derive_detail_path` through the existing body-local import.
  - Keep the status and prompt wrappers that `render_plan_audit_prompt` already relies on: `audit_detail_bundle_status`, `_format_detail_bundle_status_block`, the `### Step NN — <title>` header, the missing-detail note, and unreadable-detail note.
  - For a readable detail file, use the step 1 helper with the detail file path and candidates from `_derive_symbols(step.title)` plus the detail file's repo-relative stem and meaningful path components. This depends on step 1's markdown heading/section support so detail files can show the section most related to the step instead of only the opening slice.
  - Keep `_AUDIT_DETAIL_FILE_BYTES` as the budget for the plan-audit bundle. Do not introduce a second cap.

- **Preserve prompt output shape.**
  - Plan audit still renders through `render_plan_audit_prompt` and `plan_tool/prompts/plan-audit.md` with `${detail_files_block}` and `${carried_findings_block}`.
  - Keep plain markdown detail body output for plan-audit detail bundles unless the upstream helper contract already returns text that matches the caller’s expected block style.
  - Preserve the step 1 fallback metadata vocabulary when embedding helper output: `excerpt_kind`, `fallback_reason`, `truncated`, the visible "fallback preview" cue, and the literal `_(truncated)_` marker pinned by `tests/test_review.py`.

- **Do not change unrelated review readers.**
  - `plan_tool/review.py:render_review_prompt` is owned by step 1. Keep its existing `TestRenderReviewPrompt` expectations green, but do not make it a new implementation target here unless step 1 left a small import or call-shape adjustment needed by this step.
  - `plan_tool/review.py:_collect_done_step_file_contents` is owned by step 2. Keep its existing `TestCheckCriteriaFulfillment` expectations green, but do not make it an implementation target here.
  - `plan_tool/review.py:_render_step_detail_block` is the main review prompt’s per-step detail renderer, not the plan-audit bundle. Leave it out of this step.
  - Heuristic detection in `heuristic_already_done`, `_derive_symbols`, and `_scan_for_heuristic_hit` stays unchanged. This step consumes `_derive_symbols`; it does not redesign title parsing.

## Tests

- `test_plan_audit_detail_bundle_uses_markdown_section_excerpt_for_step_detail` — A step detail markdown file has the relevant section after a small `_AUDIT_DETAIL_FILE_BYTES`-style cap; `render_plan_audit_prompt` includes that section under `### Step 01 — <title>`.
- `test_plan_audit_detail_bundle_preserves_missing_and_unreadable_notes` — Missing detail files still render `_(no detail file on disk)_`, unreadable files still render `_(unreadable: ...)_`, and no helper call is required for those branches.
- `test_plan_audit_detail_bundle_preserves_derived_path_fallback` — A detail file at the derived `plan-details/<plan-slug>/NN-*.md` path still appears when `step.detail` is unset.

### Test-creation order (feature step)

Add the plan-audit detail-bundle tests, including the derived-path fallback because `_format_audit_detail_bundle` owns path logic. Every new test in `tests/test_review.py` must be green, and the existing `TestRenderReviewPrompt`, `TestCheckCriteriaFulfillment`, and `TestCheckPlanAudit` tests must stay green before this step is done.

## Acceptance criteria

- `plan_tool/review.py:_format_audit_detail_bundle` uses the step 1 prompt excerpt helper for readable per-step detail files.
- Candidate symbols for `_format_audit_detail_bundle` come from `plan_tool/review.py:_derive_symbols(step.title)` plus the detail file's repo-relative stem and meaningful path components.
- Missing and unreadable branches in `_format_audit_detail_bundle` keep their current caller-owned wording.
- `render_plan_audit_prompt` still returns `None` only for a bodyless plan and still includes the plan body, detail status block, detail bundle, and carried findings block.
- `tests/test_review.py` includes focused coverage for markdown heading/section excerpts in plan-audit bundles.
- `pytest tests/test_review.py` passes.

## References

- [Python ast - Abstract Syntax Trees](https://docs.python.org/3/library/ast.html) — Read for the upstream step 1 helper’s Python symbol detection contract.
- [Python re - Regular Expression Operations](https://docs.python.org/3/library/re.html) — Read for matching candidate symbols and markdown headings in helper-level excerpt selection.
- [Python pathlib - Object-Oriented Filesystem Paths](https://docs.python.org/3/library/pathlib.html) — Read for the path handling style used by `plan_tool/review.py` and the helper API.
- [Python textwrap - Text Wrapping and Filling](https://docs.python.org/3/library/textwrap.html) — Read for safe formatting of excerpt text and truncation markers if the helper exposes rendered text.

## Deferred

- `plan_tool/review.py:render_review_prompt` — Owned by step 1; this step keeps it green but does not redesign that prompt path.
- `plan_tool/review.py:_collect_done_step_file_contents` — Owned by step 2; this step keeps it green but does not redesign the criteria-fulfillment prompt path.
- `plan_tool/review.py:_render_step_detail_block` — It feeds the main review prompt’s declared step-detail preview, not the plan-audit bundle named by this step.
- `plan_tool/prompt_excerpt.py` API redesign — Step 1 owns the helper contract. If the helper cannot support readable source and markdown detail text, reconcile that upstream instead of expanding this step’s file list.
- Prompt template wording in `plan_tool/prompts/plan-audit.md` — The existing template already accepts embedded preview blocks; this step changes the selected excerpt content, not the instructions.
