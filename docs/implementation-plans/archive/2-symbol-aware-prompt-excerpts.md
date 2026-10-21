> **Auto-archived**: this plan was swept on 2026-07-07 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

---
title: Symbol Aware Prompt Excerpts
status: completed
priority: medium
enforce_step_tests: true
steps:
- id: 1
  title: Add stdlib-only prompt excerpt helpers
  files:
  - plan_tool/review.py
  - tests/test_review.py
  creates:
  - plan_tool/prompt_excerpt.py
  - tests/test_prompt_excerpt.py
  complexity: high
  change_type: feature
  detail: docs/implementation-plans/plan-details/symbol-aware-prompt-excerpts/01-stdlib-only-prompt-excerpt-helpers.md
  status: done
- id: 2
  title: Use prompt excerpts in review and reconcile prompts
  files:
  - plan_tool/review.py
  - tests/test_review.py
  complexity: medium
  change_type: feature
  depends_on:
  - 1
  detail: docs/implementation-plans/plan-details/symbol-aware-prompt-excerpts/02-use-prompt-excerpts-review-reconcile.md
  status: done
- id: 3
  title: Use prompt excerpts in detail and detail-quality prompts
  files:
  - plan_tool/detail.py
  - tests/test_detail.py
  complexity: medium
  change_type: feature
  depends_on:
  - 1
  detail: docs/implementation-plans/plan-details/symbol-aware-prompt-excerpts/03-use-prompt-excerpts-detail-detail.md
  status: done
- id: 4
  title: Use prompt excerpts in plan-audit bundles
  files:
  - plan_tool/review.py
  - tests/test_review.py
  complexity: medium
  change_type: feature
  depends_on:
  - 1
  detail: docs/implementation-plans/plan-details/symbol-aware-prompt-excerpts/04-use-prompt-excerpts-criteria.md
  status: done
- id: 5
  title: Use conservative prompt excerpts in Jira prompts
  files:
  - plan_tool/jira.py
  - tests/test_jira.py
  complexity: medium
  change_type: feature
  depends_on:
  - 1
  detail: docs/implementation-plans/plan-details/symbol-aware-prompt-excerpts/05-use-conservative-prompt-excerpts-jira.md
  status: done
- id: 6
  title: Use prompt excerpts for annotate grounding
  files:
  - plan_tool/annotate.py
  - tests/test_annotate.py
  complexity: medium
  change_type: feature
  depends_on:
  - 1
  detail: docs/implementation-plans/plan-details/symbol-aware-prompt-excerpts/06-use-prompt-excerpts-annotate-grounding.md
  status: done
- id: 7
  title: Remove old prompt head-slicing helpers and duplicated caps
  files:
  - plan_tool/detail.py
  - plan_tool/review.py
  - plan_tool/jira.py
  - plan_tool/annotate.py
  - tests/test_detail.py
  - tests/test_review.py
  - tests/test_jira.py
  - tests/test_annotate.py
  complexity: medium
  change_type: refactor
  depends_on:
  - 2
  - 3
  - 4
  - 5
  - 6
  detail: docs/implementation-plans/plan-details/symbol-aware-prompt-excerpts/07-remove-old-prompt-head-slicing-helpers.md
  status: done
- id: 8
  title: Document prompt excerpt policy and run-detail asymmetry
  files:
  - RUNBOOK.md
  complexity: low
  change_type: non-code
  depends_on:
  - 2
  - 3
  - 4
  - 5
  - 6
  detail: docs/implementation-plans/plan-details/symbol-aware-prompt-excerpts/08-document-prompt-excerpt-policy-run.md
  status: done
---
# Symbol Aware Prompt Excerpts

## Overview

This plan adds stdlib-only prompt excerpt helpers that pick relevant code windows by symbol instead of copying the start of each file. The helpers keep the current command flow and exit codes while giving review, detail, criteria, Jira, and annotate prompts smaller, more focused file context. The default behavior stays conservative: if a useful symbol window cannot be found, prompts fall back to bounded excerpts rather than failing the command.

## Problem statement

Prompt renderers currently ground agents by reading each declared file and copying only the first bounded bytes into the prompt, as seen in `render_review_prompt`, `render_detail_prompt`, `render_detail_quality_prompt`, `render_criteria_fulfillment_prompt`, `render_plan_audit_prompt`, `render_jira_prompt`, and annotate grounding. Those paths are constrained by local caps such as `_MAX_PROMPT_FILE_BYTES` and `_MAX_GROUND_FILE_BYTES`, but the cap is applied before any symbol-aware relevance selection.

That head-slicing misses the code most likely to matter when a step touches functions, classes, constants, or helpers located below the file header. The user-visible symptom is review, detail, criteria, Jira, and annotate prompts that spend their limited context on imports or unrelated top-of-file scaffolding while omitting the symbol the plan step is actually about. This makes findings noisier, detail files less grounded, and audit/application loops more likely to ask for follow-up corrections even when the relevant implementation is present later in the same declared file.

## Architecture

The plan introduces a leaf `plan_tool.prompt_excerpt` module that owns symbol-aware excerpt selection without depending on review, detail, Jira, or annotate command code. Prompt renderers pass repo-relative declared file paths, already-read file text, caller-derived candidate symbols, and prompt-specific byte budgets into this helper, and receive formatted excerpt blocks plus fallback metadata that can be embedded in existing prompt strings. Keeping the helper at this dependency edge lets every prompt path share one relevance contract while preserving the current command flow and exit behavior.

Symbol selection stays stdlib-only and deterministic. Callers derive bounded candidate symbols from plan step prose and declared file references, using the existing title-derived symbols plus repo-relative path stems and meaningful path components for the file being rendered, while the helper owns matching, ranking, fallback, and rendering for those already-supplied candidates. It inspects Python files with `ast` and lightweight token or regex support, and ranks windows around matching functions, classes, assignments, and nearby imports. For Python symbol excerpts, the helper preserves the contiguous module import block when it fits within the per-file budget; when the budget forces that context out, it keeps the symbol window authoritative and marks the omitted context with the shared truncation marker. Markdown detail files get explicit heading/section matching so plan-audit bundles can start near the section named by the owning step instead of falling back to the file header. When parsing fails, no candidate matches, or a file type has no structured reader, the helper returns the existing conservative bounded excerpt shape instead of turning prompt rendering into a hard failure.

The excerpt contract separates policy from call-site wiring. Step 1 defines the shared dataclasses, selection semantics, truncation markers, and fallback metadata vocabulary; steps 2 through 6 adapt each prompt renderer to call the helper with budgets that match its existing risk profile. The minimal metadata contract is `excerpt_kind` (`symbol` or `fallback`), `fallback_reason` (`parse-error`, `no-symbol-match`, or `unsupported-file-type` when `excerpt_kind` is `fallback`), and `truncated`; migrated prompt renderers preserve that vocabulary when embedding helper output, including the visible "fallback preview" cue and the existing `_(truncated)_` marker when content is omitted. Jira prompts use the same helper conservatively because they may include broader issue context, while annotate grounding can bias toward the symbols it is about to label.

The final refactor removes duplicated head-slicing helpers and repeated cap literals only after all prompt paths have adopted the shared helper, while preserving the named prompt-specific budgets that keep each command's existing effective cap. That sequencing keeps reviewable behavior changes isolated by command family, makes tests pin both symbol-hit and fallback paths, and avoids leaving competing excerpt-selection policies in the dependency graph.

## References

- [Python ast - Abstract Syntax Trees](https://docs.python.org/3/library/ast.html) — Covers Python's stdlib AST APIs for finding function, class, import, and assignment nodes when deriving symbol windows.
- [Python tokenize - Tokenizer for Python Source](https://docs.python.org/3/library/tokenize.html) — Documents token-level parsing of Python source, useful for deterministic import/header detection without third-party parsers.
- [Python re - Regular Expression Operations](https://docs.python.org/3/library/re.html) — Defines Python's stdlib regex behavior for matching candidate symbols and locating excerpt windows.
- [Python dataclasses - Data Classes](https://docs.python.org/3/library/dataclasses.html) — Documents dataclass construction for small contracts such as ExcerptResult and PromptExcerptContext.
- [Python pathlib - Object-Oriented Filesystem Paths](https://docs.python.org/3/library/pathlib.html) — Covers Path APIs used by a leaf excerpt helper that accepts declared source file paths.
- [Python textwrap - Text Wrapping and Filling](https://docs.python.org/3/library/textwrap.html) — Documents stdlib helpers for indenting and formatting excerpt blocks and truncation markers in rendered prompts.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

- Cross-file semantic analysis — excerpt selection stays local to each declared file so prompt rendering remains deterministic and stdlib-only.
- Non-Python structured parsing beyond markdown heading/section matching — files without a Python AST reader or markdown heading reader continue to use bounded fallback excerpts rather than adding language-specific parsers.
- Prompt budget redesign — each call site keeps its existing risk profile and byte budget while changing how the excerpt content is selected.
- Command behavior changes — review, detail, criteria, Jira, and annotate flows keep their current exits and failure handling.

## Risks

- Incorrect symbol matching can select a plausible but irrelevant window instead of the code a step actually changes; severity: medium; mitigation: keep deterministic scoring, include the shared fallback metadata vocabulary in rendered prompts, and pin symbol-hit plus fallback cases in tests; unresolved gap: prompt quality can still depend on ambiguous step prose.
- AST or token parsing can fail on partially edited Python files, generated files, or syntax that the local interpreter cannot parse; severity: low; mitigation: treat parse failures as bounded excerpt fallbacks rather than command failures; unresolved gap: fallback prompts retain the old head-slicing blind spot for that file.
- Shared helper adoption can diverge across review, detail, criteria, Jira, and annotate prompts if call sites pass inconsistent budgets or omit fallback metadata vocabulary; severity: medium; mitigation: centralize the excerpt contract in `plan_tool.prompt_excerpt` and verify each migrated prompt's symbol-hit and fallback rendering; unresolved gap: command-specific prompt text can still make equivalent metadata look different.
- Removing old head-slicing helpers can accidentally drop a prompt-specific cap or failure behavior that downstream tests did not cover; severity: medium; mitigation: sequence removal after all migrations and keep characterization coverage for existing caps before step 7; unresolved gap: untested prompt variants may still need manual review.
- Smaller excerpts can omit broader context that a human or model needs to interpret a selected symbol, especially for tightly coupled helpers or constants outside the selected window; severity: medium; mitigation: include the contiguous module import block when it fits, otherwise mark omitted context with the shared truncation marker while preserving bounded budgets; unresolved gap: cross-file semantic context remains out of scope.

## Testing

**Per-step test strategy** (derived from each step's `change_type`):

- step 1 (feature) — unit tests added with the implementation; green before completion.
- step 2 (feature) — unit tests added with the implementation; green before completion.
- step 3 (feature) — unit tests added with the implementation; green before completion.
- step 4 (feature) — unit tests added with the implementation; green before completion.
- step 5 (feature) — unit tests added with the implementation; green before completion.
- step 6 (feature) — unit tests added with the implementation; green before completion.
- step 7 (refactor) — characterization tests pinned before the change; pass unchanged after.
- step 8 (non-code) — verification appropriate to the artifacts; no test-ordering directive.

## Acceptance criteria

- `plan_tool.prompt_excerpt` exists with stdlib-only helpers that expose a stable excerpt result contract, select symbol-centered windows for Python functions, classes, assignments, and constants, select markdown heading/section windows for plan detail files, and return bounded fallback excerpts with the shared `excerpt_kind`, `fallback_reason`, and `truncated` metadata when parsing or matching fails.
- `tests/test_prompt_excerpt.py` proves symbol-hit selection, deterministic module import block preservation when budget allows, markdown heading/section selection, truncation markers when import context is omitted, byte-budget enforcement, syntax-error fallback, no-match fallback, and non-Python fallback behavior without requiring third-party packages.
- `render_review_prompt`, criteria-fulfillment DONE-step evidence rendering as the scoped reconcile surface, `render_detail_prompt`, `render_detail_quality_prompt`, `render_criteria_fulfillment_prompt`, `render_plan_audit_prompt`, `render_jira_prompt`, and annotate grounding all call the shared excerpt helper for declared-file context while preserving their existing command exit behavior; `detail-reconcile` and `run-reconcile` templates rendered through `plan_tool.renderer:render_prompt` remain out of scope because they do not embed declared-file excerpts.
- The migrated prompt tests in `tests/test_review.py`, `tests/test_detail.py`, `tests/test_jira.py`, and `tests/test_annotate.py` assert both symbol-hit rendering and bounded fallback rendering with the shared fallback metadata vocabulary for the prompt paths each file owns.
- Step 7 removes superseded head-slicing helpers and duplicated prompt cap literals from `plan_tool/detail.py`, `plan_tool/review.py`, `plan_tool/jira.py`, and `plan_tool/annotate.py` only after steps 2 through 6 have adopted the shared helper and their tests pass, while preserving named prompt-specific budget ownership and existing effective caps.
- `RUNBOOK.md` documents the shared prompt excerpt policy, fallback semantics, prompt-specific budget ownership, and the run-detail asymmetry introduced by this plan.

## Deferred

- Rich symbol inference from previous implementation diffs — postpone until the shared excerpt contract proves stable across the first migrated prompt paths.
- Language-specific structured readers beyond Python and markdown headings — revisit only if bounded fallbacks create recurring prompt-quality issues for declared non-Python files.
