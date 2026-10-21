> **Auto-archived**: this plan was swept on 2026-07-07 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 2 — Use Prompt Excerpts in Review and Reconcile Prompts

## Summary

This step extends the step 1 review-prompt wiring to the criteria-fulfillment DONE-step evidence path, which is the scoped reconcile surface for this plan, by using the prompt excerpt helper in `plan_tool/review.py:_collect_done_step_file_contents`. `plan_tool/review.py:render_review_prompt` is already owned by step 1, so this step treats that surface as verification coverage rather than a new implementation target. The key design decision is to keep DONE-step filesystem handling and prompt-section wording owned by `plan_tool/review.py`, while delegating only successful text excerpt selection to the step 1 helper. On green, existing prompt contracts still hold, and criteria-fulfillment prompts include the relevant DONE-step function/class window when the step title points to one.

## Table of Contents

- [Summary](#summary) — Quick review of the prompt excerpt wiring and test target.
- [Why](#why) — Why source previews need symbol-aware excerpts in these prompt paths.
- [Files (creates vs edits)](#files-creates-vs-edits) — The scoped files and what changes in each.
- [Implementation](#implementation) — Required behavior, call sites, constraints, and out-of-scope prompt readers.
- [Tests](#tests) — Test cases to add or adjust in `tests/test_review.py`.
- [Acceptance criteria](#acceptance-criteria) — Observable checks for the completed step.
- [References](#references) — Relevant stdlib docs from the helper design.
- [Deferred](#deferred) — Related prompt readers and helper changes left out of this step.

## Why

`plan_tool/review.py` currently gives Claude source context by reading each declared file and clipping from the start. That often hides the symbol named by a step title behind imports, constants, or unrelated helpers. Step 1 supplies a stdlib-only excerpt helper and wires it into `render_review_prompt`; this step applies the same contract to the criteria-fulfillment path without changing its DONE-step discovery, missing-file, unreadable-file, de-duplication, or truncation-marker contracts.

## Files (creates vs edits)

- **New files:**
  - None. `plan_tool/prompt_excerpt.py` is owned by step 1 and is consumed here once that dependency has landed.

- **Existing files (edits only):**
  - `plan_tool/review.py` — Reuse the step 1 prompt excerpt helper in `_collect_done_step_file_contents` for DONE-step source blocks that feed `render_criteria_fulfillment_prompt`.
  - `tests/test_review.py` — Add focused tests under `TestCheckCriteriaFulfillment` that prove relevant DONE-step symbols past the byte cap appear while existing prompt contract markers remain unchanged; keep the step 1 `TestRenderReviewPrompt` coverage passing as a guardrail.

## Implementation

- **Foundational logic:** caller-owned source excerpt rendering.

- **Use the step 1 helper only after a file is successfully read.**
  - Leave `plan_tool/review.py:render_review_prompt` wiring to step 1, including its duplicate-path contract that merges or preserves candidate symbols before rendering each path once. This step may touch nearby shared imports or test fixtures only as needed to keep the step 1 `## Current file contents` behavior green.
  - In `plan_tool/review.py:_collect_done_step_file_contents`, keep the DONE-step-only filter, `step.files`-only behavior, `seen_paths`, and `### \`path\` (from step N)` header. Replace only the successful-read leading slice.

- **Derive symbols in `plan_tool/review.py`, not in the helper.**
  - Use `plan_tool/review.py:_derive_symbols` as the title-to-candidate source for the criteria-fulfillment DONE-step evidence call site, then append bounded candidates from each rendered file's repo-relative stem and meaningful path components.
  - For `_collect_done_step_file_contents`, preserve candidate symbols from every DONE step that references the same file before the `seen_paths` render keeps one block per path.

- **Preserve prompt output shape.**
  - Keep fenced code blocks, headings, file paths, creates paths, and the literal `_(truncated)_` marker behavior that `tests/test_review.py:TestRenderReviewPrompt` already pins.
  - The excerpt text may come from the middle of a file, but the outer block format should still look like the current `### \`path\`` and `### \`path\` (from step N)` blocks.
  - Preserve the step 1 fallback metadata vocabulary when embedding helper output: `excerpt_kind`, `fallback_reason`, `truncated`, the visible "fallback preview" cue, and the literal `_(truncated)_` marker. Do not invent new prompt prose in `plan_tool/prompts/review.md` or `plan_tool/prompts/criteria-fulfillment.md` in this step.

- **Keep prompt purposes separate.**
  - Treat criteria-fulfillment DONE-step evidence as the only reconcile-named prompt surface in this rollout. Do not change `detail-reconcile` or `run-reconcile` templates rendered through `plan_tool.renderer:render_prompt`; they do not embed declared-file excerpts.
  - Do not change `plan_tool/review.py:_render_step_detail_block`; it renders prose detail files, not source snippets.
  - Do not change `plan_tool/review.py:_format_audit_detail_bundle`; it renders implementation detail files for `plan_tool/prompts/plan-audit.md`, not step source files.
  - Do not change `heuristic_already_done` or `_scan_for_heuristic_hit`; those are detection logic, not prompt rendering.

- **Avoid duplicating excerpt logic.**
  - Do not add AST, regex-windowing, or truncation heuristics directly in `plan_tool/review.py`.
  - Treat the helper from step 1 as the single source for choosing the excerpt from already-read text. `plan_tool/review.py` should decide which file and which candidate symbols apply.

## Tests

- Keep the step 1 `tests/test_review.py:TestRenderReviewPrompt` coverage green for `## Current file contents`, missing/unreadable branches, `creates:` handling, and `step_filter` behavior; add only follow-up assertions needed to protect interactions with the criteria-fulfillment wiring.
- `test_criteria_fulfillment_done_files_use_symbol_excerpt` — In `tests/test_review.py:TestCheckCriteriaFulfillment`, build a DONE-step file with the acceptance-relevant symbol past the byte cap; assert `check_criteria_fulfillment` sends a prompt containing that symbol.
- `test_criteria_fulfillment_keeps_done_file_headers_and_truncation_marker` — In `tests/test_review.py:TestCheckCriteriaFulfillment`, assert the `### \`foo.py\` (from step 1)` header and `_(truncated)_` marker remain in the captured prompt.

### Test-creation order (feature step)

Add the `TestCheckCriteriaFulfillment` cases before or alongside the `_collect_done_step_file_contents` change. This is a feature step: every new test above must be green, and the existing `tests/test_review.py:TestRenderReviewPrompt` and `tests/test_review.py:TestCheckCriteriaFulfillment` coverage must still pass before the step is done.

## Acceptance criteria

- `plan_tool/review.py:_collect_done_step_file_contents` uses the step 1 excerpt helper for successfully-read DONE-step source files.
- `plan_tool/review.py:_derive_symbols` remains the source of title-derived candidate symbols passed from DONE steps into criteria-fulfillment excerpt selection, with declared file path candidates appended per rendered file.
- Missing and unreadable files still render with the existing `(not on disk)` and `(unreadable: ...)` markers.
- Existing `render_review_prompt` excerpt behavior from step 1, including `creates:` handling, `step_filter` behavior, duplicate-path candidate-symbol preservation, and `seen_paths` de-duplication, stays intact.
- Existing DONE-step filtering and `### \`path\` (from step N)` headers in `_collect_done_step_file_contents` stay intact.
- `tests/test_review.py::TestRenderReviewPrompt` passes.
- `tests/test_review.py::TestCheckCriteriaFulfillment` passes.

## References

- [Python ast - Abstract Syntax Trees](https://docs.python.org/3/library/ast.html) — Read for the helper behavior step 1 owns when matching Python functions and classes.
- [Python re - Regular Expression Operations](https://docs.python.org/3/library/re.html) — Read for the title-symbol derivation and non-Python matching behavior that the helper may use.
- [Python pathlib - Object-Oriented Filesystem Paths](https://docs.python.org/3/library/pathlib.html) — Read for the caller-owned file path handling that stays in `plan_tool/review.py`.

## Deferred

- `plan_tool/review.py:_render_step_detail_block` — Leave unchanged because it renders step detail prose, not source-code excerpts.
- `plan_tool/review.py:_format_audit_detail_bundle` — Leave unchanged because plan-audit detail files need prose context, not title-symbol source windows.
- `plan_tool/prompts/review.md` and `plan_tool/prompts/criteria-fulfillment.md` — Leave unchanged unless the step 1 helper already established new marker text that these templates must explain.
- `plan_tool/prompt_excerpt.py` behavior changes — Leave helper parsing, window ranking, and fallback rules to step 1 or a follow-up helper-specific step.
