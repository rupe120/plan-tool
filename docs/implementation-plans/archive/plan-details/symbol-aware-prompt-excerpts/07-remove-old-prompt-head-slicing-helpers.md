> **Auto-archived**: this plan was swept on 2026-07-07 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 7 — Remove Old Prompt Head-Slicing Helpers and Duplicated Caps

## Summary

This step is a cleanup pass after steps 2 through 6 have wired symbol-aware excerpts into the prompt surfaces. It removes leftover leading-slice source preview code and duplicated prompt byte-cap literals from `plan_tool/detail.py`, `plan_tool/review.py`, `plan_tool/jira.py`, and `plan_tool/annotate.py`. The main design decision is to keep each prompt caller's existing wrapper and named budget ownership while making the shared excerpt helper from step 1 the only owner of readable-file excerpt selection. On green, the same prompts still render the same headers, missing/unreadable notes, fenced blocks, truncation markers, and effective caps, but no scoped module still carries its own `body[:max_file_bytes]` source-preview path for readable implementation files.

## Table of Contents

- [Summary](#summary) — Quick review of the cleanup scope and expected green state.
- [Why](#why) — Why the old slicing code and duplicated caps need to go after the excerpt rollout.
- [Files creates vs edits](#files-creates-vs-edits) — The scoped production and test files.
- [Implementation](#implementation) — Required cleanup, boundaries, and call sites to verify.
- [Tests](#tests) — Characterization and regression coverage for the behavior-preserving refactor.
- [Acceptance criteria](#acceptance-criteria) — Observable checks for the finished step.
- [References](#references) — Stdlib references relevant to validating the cleanup.
- [Deferred](#deferred) — Helper redesign and unrelated prompt surfaces left out of this step.

## Why

Steps 2 through 6 replace blind prompt head-slicing with symbol-aware excerpts across review, detail, Jira, and annotate prompts. Once those call sites use the step 1 helper, leaving local `body[:max_file_bytes]` snippets, local truncation-note builders, and copied cap literals around creates two sources of truth: future edits can accidentally revive head-slicing in one prompt while the others keep symbol-aware behavior. This step makes the rollout durable by deleting the old local source-preview paths and keeping the remaining per-caller code focused on filesystem handling, prompt-specific budget ownership, and prompt wrapper text.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `plan_tool/detail.py` — Remove any remaining local readable-file head slicing from `_format_files_contents_block` after step 3's excerpt wiring, while preserving `_MAX_PROMPT_FILE_BYTES` as the detail prompt budget owner unless it is only a duplicate literal alias.
  - `plan_tool/review.py` — Remove any remaining local readable-file head slicing from `render_review_prompt`, `_collect_done_step_file_contents`, and `_format_audit_detail_bundle` after steps 2 and 4, while preserving `_MAX_DETAIL_PARSE_BYTES` for deterministic body parsing.
  - `plan_tool/jira.py` — Remove any remaining local readable-file head slicing from `_render_step_files_contents` after step 5, while preserving `_MAX_PROMPT_FILE_BYTES` as the Jira prompt budget owner unless it is only a duplicate literal alias.
  - `plan_tool/annotate.py` — Remove the old code-grounding head-slice helper path from `_ground_source` after step 6, while keeping `_bound_for_block` only if `_load_step_specs` still needs it for spec/detail text.
  - `tests/test_detail.py` — Add or adjust characterization tests for `render_detail_prompt`, `render_detail_quality_prompt`, and `_format_files_contents_block` contracts.
  - `tests/test_review.py` — Add or adjust characterization tests for `TestRenderReviewPrompt`, `TestCheckCriteriaFulfillment`, and `TestCheckPlanAudit`.
  - `tests/test_jira.py` — Add or adjust characterization tests under `TestRenderJiraPrompt`, including append/covered-step mode if step 5 added that route.
  - `tests/test_annotate.py` — Add or adjust prompt-capture tests for `_ground_source` through `classify_plan_implementation` and keep `_load_step_specs` behavior pinned.

## Implementation

- **Foundational logic:** single source for prompt source excerpts.

- **Treat this as a refactor, not a new excerpt feature.**
  - Depend on step 1 for the shared excerpt helper and on steps 2 through 6 for the prompt call-site wiring.
  - Do not add new symbol selection behavior in this step. If a prompt still cannot call the helper because the helper contract is missing something, record that as a follow-up rather than expanding this cleanup into `plan_tool/prompt_excerpt.py`.

- **Keep caller-owned filesystem behavior unchanged.**
  - In `plan_tool/detail.py:_format_files_contents_block`, keep `Step.all_files`, `_no files declared_`, `### \`path\` _(not on disk)_`, unreadable notes, and the fenced block wrapper.
  - In `plan_tool/review.py:render_review_prompt`, keep files plus creates, `(new)` creates annotations, `step_filter`, first-owner rendered-block `seen_paths`, missing/unreadable notes, and fenced blocks.
  - In `plan_tool/review.py:_collect_done_step_file_contents`, keep DONE-only filtering, `step.files` only, first-owner rendered-block `seen_paths`, `### \`path\` (from step N)` headers, and empty-string return when there is no source context.
  - In `plan_tool/review.py:_format_audit_detail_bundle`, keep `step.detail` path resolution, the body-local `plan_tool.detail:derive_detail_path` fallback, missing/unreadable notes, and the `### Step NN — title` wrapper; keep `DetailBundleStatus` behavior anchored in `audit_detail_bundle_status` and `_format_detail_bundle_status_block`, with `render_plan_audit_prompt` composing them.
  - In `plan_tool/jira.py:_render_step_files_contents`, keep `Step.all_files`, per-step rendering without `seen_paths`, missing/unreadable notes, and `#### \`path\`` fenced blocks.
  - In `plan_tool/annotate.py:_ground_source`, keep `extract_file_path_candidates`, `find_umbrella_root`, duplicate skips, detail-file exclusion, binary/unreadable skip reasons, `GroundedSource.files`, and grounding counts.

- **Delete local readable-file head slicing where the helper now owns excerpt selection.**
  - Search the scoped production files for `body[:max_file_bytes]`, `text[:max_file_bytes]`, and local `_(truncated)_` assembly.
  - For readable implementation/source file previews, the caller should pass already-read text to the step 1 helper and render the returned excerpt inside the existing wrapper.
  - Leave non-source/spec truncation alone when it is intentionally separate. `plan_tool/annotate.py:_load_step_specs` can still use `_bound_for_block` for detail/spec bodies unless a prior step already moved that surface too. `plan_tool/jira.py:_render_step_detail`, `plan_tool/review.py:_render_step_detail_block`, and `plan_tool/detail.py:_format_sibling_details_block` are prose-detail renderers, not implementation source excerpt surfaces.

- **Remove duplicated source-preview literals without breaking prompt-specific budget ownership.**
  - Keep named caller-owned budgets such as `plan_tool/detail.py:_MAX_PROMPT_FILE_BYTES`, `plan_tool/review.py:_MAX_PROMPT_FILE_BYTES`, `plan_tool/jira.py:_MAX_PROMPT_FILE_BYTES`, and `plan_tool/annotate.py:_MAX_GROUND_FILE_BYTES` when prior steps use them to preserve a prompt's existing effective cap.
  - Replace only repeated raw byte literals or local aliases that no longer own a distinct prompt budget after the caller passes its named budget into the shared helper.
  - Do not centralize budget defaults in this cleanup unless the central contract preserves each migrated prompt's existing effective cap unchanged.
  - Keep caps that have a different job. `plan_tool/review.py:_MAX_DETAIL_PARSE_BYTES` is for deterministic detail-body parsing and must not be collapsed into the prompt excerpt budget. `plan_tool/review.py:_AUDIT_DETAIL_FILE_BYTES` should disappear only if `_format_audit_detail_bundle` now uses the shared excerpt budget for detail-bundle prompt context; do not delete it if prior steps kept that bundle on a separate, intentional cap.

- **Preserve candidate-symbol ownership.**
  - Keep `plan_tool/review.py:_derive_symbols` as the title-to-symbol owner for detail, review, Jira, and annotate callers that need title-derived candidates.
  - Do not add another tokenizer to `plan_tool/detail.py`, `plan_tool/jira.py`, or `plan_tool/annotate.py`.
  - Preserve each caller's rendered-block owner rule: review and criteria prompts use first-owner-wins `seen_paths` only for the block/header they render; duplicate-path candidate symbols still remain merged or preserved from all relevant steps before that single block is rendered. Jira renders the same file separately per step; annotate uses a bounded shared candidate set because arbitrary notes do not have a reliable per-file owner.

- **Update comments and docstrings that still describe head slicing.**
  - Replace stale wording such as "truncated file bodies", "truncated to first bytes", or "shows only its first bytes" where it now describes symbol-aware excerpts.
  - Keep wording that still applies to non-source detail/spec bodies.
  - Do not edit prompt templates unless the rendered marker vocabulary changed in an earlier step.

## Tests

- `tests/test_detail.py::TestRenderDetailPrompt::test_source_excerpt_contract_survives_cleanup` — Pins that `render_detail_prompt` still renders detail source file headers, missing/unreadable notes, fenced blocks, and a symbol-aware excerpt past a small cap.
- `tests/test_detail.py::TestRenderDetailQualityPrompt::test_source_excerpt_contract_survives_cleanup` — Pins the same readable-file excerpt contract through `render_detail_quality_prompt`.
- `tests/test_review.py::TestRenderReviewPrompt::test_source_excerpt_contract_survives_cleanup` — Pins review prompt files plus creates, first-owner rendered-block de-duplication, duplicate-path candidate preservation, missing/unreadable markers, and symbol-aware content.
- `tests/test_review.py::TestCheckCriteriaFulfillment::test_done_step_source_excerpt_contract_survives_cleanup` — Pins DONE-step source blocks, first-owner rendered-block behavior, and duplicate-path candidate preservation for `render_criteria_fulfillment_prompt`.
- `tests/test_review.py::TestCheckPlanAudit::test_audit_detail_bundle_contract_survives_cleanup` — Pins `_format_audit_detail_bundle` wrapper behavior, `audit_detail_bundle_status` and `_format_detail_bundle_status_block` status behavior as composed by `render_plan_audit_prompt`, and whatever excerpt or cap contract steps 4 and 7 leave in place.
- `tests/test_jira.py::TestRenderJiraPrompt::test_source_excerpt_contract_survives_cleanup` — Pins Jira per-step file rendering, including repeated file ownership by current step title and existing append/covered-step annotations.
- `tests/test_annotate.py::test_ground_source_excerpt_contract_survives_cleanup` — Captures the annotate prompt through `classify_plan_implementation` and proves grounded code still uses the shared excerpt path while skip counts and `grounded_files` stay based on resolved files.
- `tests/test_annotate.py::test_load_step_specs_still_bounds_specs_after_cleanup` — Pins that detail/spec text remains bounded independently if `_bound_for_block` stays for `_load_step_specs`.

### Test-creation order (refactor step)

This is a behavior-preserving refactor. Write the characterization tests first, before deleting constants or local slicing helpers:

- `tests/test_detail.py::TestRenderDetailPrompt::test_source_excerpt_contract_survives_cleanup` — Pins the detail authoring prompt's current post-step-3 behavior.
- `tests/test_detail.py::TestRenderDetailQualityPrompt::test_source_excerpt_contract_survives_cleanup` — Pins the detail-quality prompt's current post-step-3 behavior.
- `tests/test_review.py::TestRenderReviewPrompt::test_source_excerpt_contract_survives_cleanup` — Pins the review prompt's current post-step-2 behavior.
- `tests/test_review.py::TestCheckCriteriaFulfillment::test_done_step_source_excerpt_contract_survives_cleanup` — Pins the criteria prompt's current post-step-4 behavior.
- `tests/test_review.py::TestCheckPlanAudit::test_audit_detail_bundle_contract_survives_cleanup` — Pins the plan-audit bundle's current post-step-4 behavior.
- `tests/test_jira.py::TestRenderJiraPrompt::test_source_excerpt_contract_survives_cleanup` — Pins the Jira prompt's current post-step-5 behavior.
- `tests/test_annotate.py::test_ground_source_excerpt_contract_survives_cleanup` — Pins annotate grounding's current post-step-6 behavior.
- Pass-unchanged-after gate — The same characterization tests must stay green, without changing their assertions, after removing duplicated cap literals and old head-slicing code.

## Acceptance criteria

- Readable implementation/source prompt excerpt paths in `render_review_prompt`, `_collect_done_step_file_contents`, `_format_audit_detail_bundle`, `_format_files_contents_block`, `_render_step_files_contents`, and `_ground_source` no longer use direct `body[:max_file_bytes]` or `text[:max_file_bytes]` slicing; any remaining matches are limited to intentionally separate prose/detail/spec truncation paths such as `_format_sibling_details_block`, `_render_step_detail_block`, `_render_step_detail`, or `_load_step_specs`.
- Local prompt-preview byte literals are not repeated across `plan_tool/detail.py`, `plan_tool/review.py`, `plan_tool/jira.py`, and `plan_tool/annotate.py` when they do not own a distinct prompt-specific budget.
- Named prompt-specific budgets keep the existing effective caps for detail, review, Jira, and annotate prompt surfaces.
- `plan_tool/review.py:_MAX_DETAIL_PARSE_BYTES` remains separate from the prompt excerpt budget.
- `plan_tool/annotate.py:_bound_for_block` is removed if unused, or remains used only for `_load_step_specs` detail/spec text.
- Existing missing-file, unreadable-file, no-files, creates/new, first-owner rendered-block, duplicate-path candidate preservation, per-step Jira ownership, and annotate skip-count behaviors remain unchanged.
- `pytest tests/test_detail.py tests/test_review.py tests/test_jira.py tests/test_annotate.py` passes.

## References

- [Python re - Regular Expression Operations](https://docs.python.org/3/library/re.html) — Use for the grep-style cleanup checks and any existing symbol-candidate validation that remains in tests.
- [Python pathlib - Object-Oriented Filesystem Paths](https://docs.python.org/3/library/pathlib.html) — Use for preserving caller-owned path handling while removing only local excerpt selection.
- [Python dataclasses - Data Classes](https://docs.python.org/3/library/dataclasses.html) — Use as background for the shared excerpt result contract from step 1 if tests need to assert fields rather than rendered text.

## Deferred

- `plan_tool/prompt_excerpt.py` helper redesign — This step consumes the helper produced by step 1; changing its public API belongs in a separate reconcile item unless the existing API cannot support the cleanup.
- Prompt template wording in `plan_tool/prompts/*.md` — Leave templates alone unless an earlier step changed the rendered marker vocabulary.
- Prose detail/spec truncation in `plan_tool/detail.py:_format_sibling_details_block`, `plan_tool/jira.py:_render_step_detail`, `plan_tool/review.py:_render_step_detail_block`, and `plan_tool/annotate.py:_load_step_specs` — These are not readable implementation source previews, so they should stay separate unless a later plan explicitly moves them to a shared prose excerpt helper.
- New prompt excerpt behavior — This step should not add new parsing, ranking, or symbol-candidate rules; it only removes leftover duplicate local code after steps 2 through 6.
