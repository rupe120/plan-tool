# Step 1 — Add completed-step context to selected code reconciliations

## Summary

Harden the existing completed-sibling context for fresh `reconcile-code --step N`. The path uses one verified plan snapshot, requires a selected `DONE` step with readable detail, and sends only normalized sibling-declared paths through the existing prompt seam. It refuses before a backend call when this grounding is unreliable. The model receives explicit ownership context before it writes findings; the saved record retains its existing classifications and states when sibling context informed them.

## Table of Contents

- [Summary](#summary) — The completed behavior and main design choice.
- [Table of Contents](#table-of-contents) — Quick links to each section.
- [Why](#why) — The selected-step ownership problem this fixes.
- [Input](#input) — Plan and saved-report contracts the path reads.
- [Files (creates vs edits)](#files-creates-vs-edits) — The scoped file changes.
- [Implementation](#implementation) — Required preflight, ownership, prompt, and report behavior.
- [Tests](#tests) — Focused prompt, CLI, and saved-report coverage.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Primary documentation for templating, models, and tests.
- [Applicable guardrails](#applicable-guardrails) — Plan boundaries that constrain this step.

## Why

`plan_tool/cli/reconcile.py:_run_run_reconcile_step` already sends completed-sibling context with raw declared paths to `plan_tool/prompts/run-reconcile.md`. Later completed work can still be mistaken for removable selected-step drift when equivalent paths use different spellings or prompt priorities conflict. The path needs targeted hardening, and it must refuse rather than guess when its selected target or input snapshot is unreliable.

## Input

- **Plan step records:** Parse `Plan.steps` once. Use `plan_tool/schema.py:StepStatus` to require the selected and sibling candidates to be `DONE`, and `plan_tool/schema.py:Step`’s `all_files` property so `creates:` entries receive the same ownership treatment as `files:`.
- **Selected-step contract:** Read the selected detail successfully from that snapshot before prompt assembly. A current or pending target, unreadable selected detail, or changed plan snapshot is a deterministic pre-backend error, not a model question.
- **Ownership identity:** Normalize each declared path with the existing `plan_tool/scope_guard.py` rule before set comparison, so equivalent raw, dotted, and creation-annotated spellings identify one path.
- **Saved result contract:** Keep the final `## Findings` block compatible with `plan_tool/launcher.py:summarize_findings` and `plan_tool/review.py:extract_run_reconcile_recommendations`; `plan_tool/cli/reconcile.py:_save_and_walk_run_reconcile` persists both the report text and extracted recommendations.
- **Sibling context:** Use sibling normalized declared paths only. Do not load sibling detail; absent sibling paths provide no ownership claim and never prove code removable.

## Files (creates vs edits)

- **New files:** None.

- **Existing files (edits only):**
  - `plan_tool/cli/reconcile.py` — Harden existing completed-sibling context for the fresh selected run-reconcile path and state when it informed the existing report classification.
  - `plan_tool/launcher.py` — Preserve the existing opt-in context rendering and budget breakdown while refusing a high-budget selected reconciliation before invocation.
  - `plan_tool/prompts/run-reconcile.md` — Render the context and state the ownership rule the audit must follow.
  - `plan_tool/scope_guard.py` — Expose the existing declared-path normalization rule for the selected reconciliation ownership comparison.
  - `tests/test_launcher.py` — Cover prompt injection, default isolation, and prompt-budget accounting.
  - `tests/test_cli.py` — Cover selected-step preflight, context selection, outcomes, and persisted report wording.
  - `tests/test_scope_guard.py` — Cover the shared normalization spelling contract.

## Implementation

- **Build one verified selected-run snapshot.** In `plan_tool/cli/reconcile.py:_cmd_run_reconcile`, parse and select from one plan snapshot. Require the target to be `DONE`, read its detail, and revalidate the plan fingerprint immediately before backend invocation. If the snapshot changes, refuse and require a retry; do not combine selected grounding from one read with sibling context from another.

- **Use declared normalized paths for sibling ownership.** Derive context from every other `DONE` step, including earlier and later siblings. Reuse a small shared scope-guard normalizer rather than comparing raw `Step.all_files` strings. Include only sibling paths outside the selected normalized footprint. Do not read sibling details or invent a sibling-data protocol.

- **Keep ownership narrow.** A path shared with the selected step remains subject to selected-step reconciliation. Sibling context has higher priority than broad cross-cutting prompt language, but only for an otherwise out-of-footprint sibling path; it cannot hide a selected-footprint mismatch.

- **Reuse the existing rendering seam.** Keep the keyword-only `plan_tool/launcher.py:run_step` context input and its `plan_tool/renderer.py:render_prompt` `extra_vars` path. Ordinary `run`, review modes, `detail-reconcile`, and all existing `run_step` callers retain their current prompts.

- **Render a dedicated, higher-priority context block.** In `plan_tool/prompts/run-reconcile.md`, place the completed-sibling block near `## Step context`. State that an otherwise out-of-footprint path listed as sibling-owned is context only: it cannot produce a removal recommendation or be called selected-step drift. This rule takes precedence over the prompt's general cross-cutting-drift instruction.

- **Preserve selected-step findings.** The prompt must still compare the selected step’s own detail and footprint against code on disk. A genuine selected-step gap, including one in a shared file, must remain a normal code-side finding with the existing severity, remediation, and redirect rules.

- **Prefer prompt-time classification over text filtering.** Do not try to infer sibling ownership by deleting parsed natural-language recommendations after `plan_tool/review.py:extract_run_reconcile_recommendations` runs. That would risk hiding genuine selected-step drift. Require the model to classify using the supplied ownership context, then preserve the resulting parseable findings.

- **Keep report classification and ownership separate.** Keep `plan_tool/launcher.py:format_findings_verdict` generic. The run-reconcile-specific report passed to `_save_and_walk_run_reconcile` keeps the existing clean, scoped, or selected-step-drift classification and adds a sibling-context note when applicable. Do not create a third outcome, synthetic finding, or `## Redirect`: the redirect protocol remains solely for plan-rooted findings. `## Findings` remains real findings or the existing `_(none)_` clean sentinel.

- **Keep dry-run and budget behavior honest.** `run_step` renders the same context under `--dry-run`, before any invoker call. Add it as a named existing budget block so displayed and actual prompt size agree. For this selected run-reconcile preflight only, a `high` `estimate_prompt_budget` result refuses before invocation. Do not change generic budget thresholds or behavior.

- **Leave reuse semantics unchanged.** `_prompt_reuse_saved_run_reconcile` bypasses a fresh prompt and should continue to replay a fresh saved result without rebuilding or mutating its context. The new behavior applies to fresh selected run-reconcile calls, shared by `reconcile-code` and legacy `run --reconcile`.

## Tests

Every test below must be green before this step is complete.

### Tests for this step

- `test_run_reconcile_prompt_includes_completed_sibling_context` — `tests/test_launcher.py` verifies an opt-in run-reconcile prompt contains sibling identity and ownership context while retaining the selected step detail.
- `test_run_step_without_completed_context_keeps_existing_prompt_shape` — `tests/test_launcher.py` verifies the new `run_step` input is optional and does not alter normal modes or callers.
- `test_run_reconcile_context_is_in_prompt_budget_blocks` — `tests/test_launcher.py` verifies the context appears in the prompt-budget breakdown and contributes nonzero bytes when present.
- `test_reconcile_code_selected_step_excludes_itself_and_includes_other_done_steps` — `tests/test_cli.py` uses a multi-step completed plan and captures the fresh run-reconcile input, including a later completed sibling but not the selected step.
- `test_reconcile_code_context_normalizes_and_excludes_shared_selected_paths` — `tests/test_cli.py` verifies equivalent spellings normalize and sibling context does not claim a selected path.
- `test_reconcile_code_later_sibling_work_is_clean_context` — `tests/test_cli.py` uses canned clean output to verify later-step-only work creates no removal recommendation for an earlier selected step.
- `test_reconcile_code_selected_step_mismatch_is_saved` — `tests/test_cli.py` verifies a canned selected-step finding remains an extracted and persisted run-reconcile recommendation.
- `test_reconcile_code_saved_report_labels_completed_sibling_context` — `tests/test_cli.py` verifies the saved run-reconcile report states when sibling context informed the existing classification without emitting a redirect.
- `test_reconcile_code_rejects_non_done_or_unreadable_selected_target` — `tests/test_cli.py` verifies current/pending targets and unreadable selected detail refuse before a backend call.
- `test_reconcile_code_rejects_changed_snapshot_or_high_selected_budget` — `tests/test_cli.py` verifies snapshot drift and high selected prompt budget refuse before a backend call.
- `test_scope_guard_normalizes_declared_path_spellings` — `tests/test_scope_guard.py` pins the shared `foo.py`/`./foo.py`/`foo.py (new)` identity rule.

## Acceptance criteria

- `reconcile-code <plan> --step N` accepts only a selected `DONE` step with readable detail from one verified plan snapshot.
- It renders selected detail and normalized-path context for every other completed sibling that owns paths outside the selected footprint.
- A later completed sibling’s code does not produce a removal recommendation when an earlier completed step is selected.
- A deliberate mismatch in the selected step still produces a normal run-reconcile finding and remains in the saved recommendations.
- Shared paths remain eligible for selected-step reconciliation; sibling context does not suppress their real mismatches.
- The saved run-reconcile report retains its parseable clean, scoped, or selected-step-drift classification and states when sibling context informed it without emitting a redirect.
- `--dry-run` shows the context without invoking the backend, and prompt-budget blocks include the context when it is rendered.
- A changed snapshot or high selected prompt budget refuses before any backend call.
- Existing non-run-reconcile `run_step` callers keep their current prompt behavior.

## References

- [Template strings — Python documentation](https://docs.python.org/3/library/string.html#template-strings) — Use `Template.safe_substitute` behavior when adding the prompt context variable.
- [Models — Pydantic Documentation](https://pydantic.dev/docs/validation/latest/concepts/models/) — Reference for safe field access while filtering completed `Step` records.
- [Prompt engineering overview — Claude Platform Docs](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/overview) — Guide for separating sibling context from selected-step instructions.
- [How to monkeypatch/mock modules and environments — pytest documentation](https://docs.pytest.org/en/stable/how-to/monkeypatch.html) — Use for focused CLI and prompt-composition seams without a backend call.
- [How to use temporary directories and files in tests — pytest documentation](https://docs.pytest.org/en/stable/how-to/tmp_path.html) — Use for multi-step plan fixtures and saved-report assertions.

## Applicable guardrails

- **The plan’s “## Plan intent”, selected-step ownership boundary:** Treat sibling-delivered work as context only when reconciling the selected step; do not turn that work into selected-step scope.
- **The plan’s “## Step intent”, real-mismatch boundary:** Keep findings for clear mismatches in the selected step even when sibling context is present.
- **The plan’s “## Out of scope”, contained behavior boundary:** Limit changes to the selected run-reconcile path. Do not alter plan/detail content, generic review-walk routing, or unrelated reconciliation behavior.
