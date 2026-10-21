> **Auto-archived**: this plan was swept on 2026-07-07 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 8 — Document Prompt Excerpt Policy and Run-Detail Asymmetry

## Summary

This step updates `RUNBOOK.md` so operators know that embedded file contents are now symbol-aware excerpts, not guaranteed leading slices or complete files. The edit should land in existing runbook sections rather than creating a new command workflow: `RUNBOOK.md:Workflow: author detail files for developer hand-off`, `RUNBOOK.md:Inspecting prompts before they run`, and the per-subcommand reconcile sections are the main anchors. The key design decision is to document policy and operator expectations, not restate the helper implementation owned by steps 1 through 7. On green, `RUNBOOK.md` explains excerpt fallback behavior, prompt-specific budget ownership, and why `run --reconcile` and `detail --reconcile` may embed different context even when they discuss the same plan step.

## Table of Contents

- [Summary](#summary) — Quick review of the runbook documentation change and expected result.
- [Why](#why) — Why operators need prompt excerpt and run/detail guidance after the rollout.
- [Files (creates vs edits)](#files-creates-vs-edits) — The single scoped documentation file and where to edit it.
- [Implementation](#implementation) — Required documentation points, recommended runbook anchors, and wording constraints.
- [Tests](#tests) — Non-code verification checks for this documentation-only step.
- [Acceptance criteria](#acceptance-criteria) — Observable checks for the completed runbook update.
- [Deferred](#deferred) — Related docs and implementation work left out of this step.

## Why

Steps 1 through 7 change prompt file context from simple head slices to symbol-aware excerpts across review, detail, Jira, audit, and annotate prompt surfaces. Without a runbook update, an operator inspecting a `--dry-run` prompt can mistake a focused excerpt for a full file, assume missing top-of-file content is a bug, or miss that fallback excerpts are expected when no symbol can be found. The runbook also needs to make the reconcile split plain: `detail --reconcile` fixes plan/detail truth, while `run --reconcile` fixes code truth, so their prompts can carry different detail and source context by design.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `RUNBOOK.md` — Add concise operator guidance for symbol-aware prompt excerpts, fallback semantics, prompt-specific budgets, `--dry-run` inspection, and the `detail --reconcile` / `run --reconcile` context split.

## Implementation

- **Foundational logic:** prompt excerpt policy documentation.

- **Add policy where operators already inspect prompts.**
  - Update `RUNBOOK.md:Inspecting prompts before they run` to say that the "Current file contents" block is a bounded preview and may start near a matching function, class, constant, markdown section, or other title-derived symbol.
  - Keep the existing `--dry-run` command examples. Add `plan-tool detail my-feature --step 3 --dry-run` if the section still lists only run/reconcile/verify/Jira examples, because `RUNBOOK.md:Workflow: author detail files for developer hand-off` already documents that detail dry-run path and this section is the cross-command inspection checklist.
  - Tell operators what to verify: the right paths are present, missing/unreadable markers are accurate, `_(truncated)_` still means a bounded preview, and a symbol-centered excerpt does not prove the rest of the file is absent.

- **Document fallback behavior without restating helper internals.**
  - Refer to the outcome of steps 1 through 7: readable source and markdown detail previews use the shared prompt excerpt policy; if no useful symbol or markdown section match exists, prompts keep a bounded fallback preview instead of failing.
  - Do not explain AST ranking, token parsing, stopwords, candidate scoring, or helper dataclasses in `RUNBOOK.md`. Those details belong in `plan_tool/prompt_excerpt.py` and its tests, not in the operator runbook.
  - Use plain wording such as "focused excerpt" and "fallback preview." Avoid promising exact placement, exact byte counts, or a complete-file view.

- **Call out prompt-specific budget ownership.**
  - In `RUNBOOK.md:Inspecting prompts before they run`, state that each prompt family still owns its own context budget. The shared policy changes which part of a readable file is shown, not whether a command can exceed its prompt budget.
  - Keep this as operator guidance, not a constant map. Do not list implementation constants such as `plan_tool/detail.py:_MAX_PROMPT_FILE_BYTES`, `plan_tool/review.py:_MAX_PROMPT_FILE_BYTES`, `plan_tool/jira.py:_MAX_PROMPT_FILE_BYTES`, or `plan_tool/annotate.py:_MAX_GROUND_FILE_BYTES`, because step 7 may remove or consolidate those names.

- **Explain the run/detail asymmetry in the reconcile section.**
  - Update `RUNBOOK.md:detail --reconcile — fix the plan to match the code` and `RUNBOOK.md:reconcile-code — fix the code to match the plan` with a short note that the two prompts are intentionally asymmetric.
  - `detail --reconcile` should be described as plan/detail-edit guidance: it may emphasize plan frontmatter, detail body, and declared-file evidence needed to repair the spec.
  - `run --reconcile` / `reconcile-code` should be described as code-edit guidance: it may emphasize the implementation excerpt and redirect to `detail --reconcile` when the plan is wrong.
  - Preserve the existing rule in `RUNBOOK.md:## Redirect and the [REDIRECT] signal`: a plan-side root cause under `run --reconcile` should be acted on by switching to `detail --reconcile`, not by retrying the code path.

- **Connect detail files to excerpt behavior without overloading detail authoring.**
  - In `RUNBOOK.md:Workflow: author detail files for developer hand-off`, keep the existing point that `run`, `reconcile-plan`, and `jira` embed detail files when present.
  - Add one sentence that detail prompts can include focused current-file excerpts as grounding, while detail files themselves remain developer hand-off specs and should not be treated as generated source excerpts.
  - Do not edit the seven-section template beyond this clarification. The template is already the right operator contract for detail files.

- **Keep the step within `RUNBOOK.md`.**
  - Do not edit `README.md`, `PLAN_FORMAT.md`, `SKILL.md`, `plan_tool/prompts/review.md`, `plan_tool/prompts/detail.md`, `plan_tool/prompts/jira.md`, or `plan_tool/prompts/annotate.md` in this step.
  - Do not add tests or generated docs. `RUNBOOK.md` is hand-maintained and is not covered by the generated CLI reference drift guard.

## Tests

This is a non-code step. No unit tests are required.

### Verification (non-code step)

- `rg -n "focused excerpt|symbol-aware|fallback preview|Current file contents|detail --reconcile|run --reconcile|reconcile-code" RUNBOOK.md` — Confirms the new policy and asymmetry wording exists in the expected operator sections.
- `rg -n "full file|complete file|always starts|leading slice|head slice" RUNBOOK.md` — Confirms the runbook does not keep stale wording that implies prompt previews are complete files or always leading slices.
- `rg -n "plan-tool detail my-feature --step 3 --dry-run" RUNBOOK.md` — Confirms detail prompt inspection is documented alongside the other dry-run examples if added to `RUNBOOK.md:Inspecting prompts before they run`.
- `python -m pytest` — Optional sanity check only; no test should be added or changed for this documentation-only step.

## Acceptance criteria

- `RUNBOOK.md:Inspecting prompts before they run` explains that embedded file contents are bounded, symbol-aware excerpts and can fall back to bounded previews.
- `RUNBOOK.md:Inspecting prompts before they run` tells operators that `_(truncated)_` still marks an incomplete preview and that a focused excerpt does not mean the rest of the file is absent.
- `RUNBOOK.md` documents that prompt families keep their own budgets while sharing the same readable-file excerpt policy.
- `RUNBOOK.md:detail --reconcile — fix the plan to match the code` and `RUNBOOK.md:reconcile-code — fix the code to match the plan` describe the intentional prompt-context asymmetry between plan/detail edits and code edits.
- `RUNBOOK.md` keeps the existing redirect guidance: a plan-side issue found under `run --reconcile` points the operator to `detail --reconcile`.
- No files other than `RUNBOOK.md` are edited for this step.

## Deferred

- `README.md`, `PLAN_FORMAT.md`, and `integrations/claude/SKILL.md` policy wording — This step is scoped to the operator runbook; broader conceptual docs can follow only if the rollout changes their existing contracts.
- Prompt template wording in `plan_tool/prompts/*.md` — Steps 1 through 7 change rendered context; this step documents operator behavior and does not change model instructions.
- Helper API or excerpt marker changes in `plan_tool/prompt_excerpt.py` — Steps 1 and 7 own helper behavior and cleanup; this step only documents the shipped policy.
- Generated CLI docs under `docs/cli/` — The excerpt policy is not an argparse flag or command help change, so no CLI reference regeneration belongs here.
