> **Auto-archived**: this plan was swept on 2026-07-08 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 3 — Add prompt-budget telemetry regression coverage

## Summary

Add test-only regression coverage that proves step 2's shell-backstop suppression removes duplicate prompt-budget telemetry for named create, detail, and review sends. The primary edits are in `tests/test_shell.py`, `tests/test_create.py`, `tests/test_detail.py`, and `tests/test_review.py`, with `tests/test_telemetry.py` used only if recorder-level assertions need a small strengthening. The key design choice is to test through the production shell wrapper paths, not only through injected fake invokers, because the duplicate event appears only when a named caller also reaches `plan_tool/shell.py:claude_invoke`. Green means direct uninstrumented shell sends still record `phase="shell-backstop"`, while named create/detail/review sends record exactly one named prompt-budget event and no shell-backstop duplicate.

## Table of Contents

- [Summary](#summary) — The short version of the test-only hardening.
- [Why](#why) — Why the current prompt-budget tests do not catch duplicate shell telemetry.
- [Input](#input) — The upstream suppression and recorder contracts these tests depend on.
- [Files creates vs edits](#files-creates-vs-edits) — The test files this step updates.
- [Implementation](#implementation) — The regression shape and the boundaries to exercise.
- [Tests](#tests) — The focused cases to add or adjust.
- [Acceptance criteria](#acceptance-criteria) — The observable results reviewers and CI can check.
- [References](#references) — Test and stdlib docs relevant to the regression seams.
- [Deferred](#deferred) — Work that stays outside this test-only step.

## Why

The existing prompt-budget tests prove the recorder contract in `tests/test_telemetry.py:test_record_prompt_budget_roundtrips`, the generic shell backstop in `tests/test_shell.py:test_backstop_records_telemetry_on_real_send`, and the named create/detail/review advisory hooks in `tests/test_create.py:TestCreatePromptBudgetAdvisory`, `tests/test_detail.py:TestGenerateDetailPromptBudget`, and `tests/test_review.py:TestAuditPromptBudgetAdvisory`. Those named-caller tests mostly use fake invokers, so they do not exercise the downstream batch seam in `plan_tool/shell.py:claude_invoke`. After step 2 adds suppression for already-advised sends, this step closes that gap by proving telemetry count and `phase` values through the real production shell wrapper paths.

## Input

- **Step 2 output:** step 2 provides scoped shell-backstop suppression for named prompt-budget sends. This step should treat that as the behavior under test, not redesign or widen it.
- **Telemetry recorder contract:** `plan_tool/telemetry.py:record_prompt_budget` records `kind="prompt-budget"` with `context.phase`, `context.total_bytes`, and `context.advisory`, and allows `plan_slug=""` for `phase="shell-backstop"`.
- **Shell backstop contract:** `plan_tool/shell.py:claude_invoke` still records `phase="shell-backstop"` for direct batch sends when a scoped spawn cwd exists.
- **Named caller contracts:** `plan_tool/create.py:_maybe_warn_create_budget`, `plan_tool/detail.py:_author_step_detail`, and `plan_tool/review.py:audit_plan_until_stable` still emit their named events before real sends.
- **Limit:** this step verifies prompt-budget telemetry behavior only. It does not change prompt sizing, advisory thresholds, subprocess retry policy, run-log events, or data-contract documentation.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `tests/test_shell.py` — Add focused regression coverage that suppression skips the shell backstop warn/record path only while active, while direct `claude_invoke` still records `phase="shell-backstop"`.
  - `tests/test_create.py` — Add production-wrapper tests for `propose_distilled_seed_from_claude`, `propose_steps_from_claude`, and `propose_body_sections` using `plan_tool.create:shell_claude_invoker` inside `plan_tool.backend:spawn_cwd`, with named and shell recorders counted together.
  - `tests/test_detail.py` — Add a `generate_detail` test that uses `plan_tool.detail:shell_detail_invoker` and proves the detail send records exactly one named event.
  - `tests/test_review.py` — Add an `audit_plan_until_stable` test that uses `plan_tool.review:shell_review_invoker` inside `plan_tool.backend:spawn_cwd`, or drives `review_plan_full`, and proves the plan-audit run records exactly one named event across multiple passes.
  - `tests/test_telemetry.py` — Keep existing recorder shape tests; add only a small case if the step 2 implementation exposes a new recorder-level edge that is not already covered by `test_record_prompt_budget_empty_slug_ok` and `test_record_prompt_budget_omits_optional_keys`.

## Implementation

- **Foundational logic:** one prompt-budget telemetry event per advised production shell send.
- **Test the real duplicate path.** Add regressions that call the production shell wrapper functions instead of only injected fake invokers:
  - `tests/test_create.py:TestCreatePromptBudgetAdvisory` should gain cases that enter `plan_tool.backend:spawn_cwd` and pass `plan_tool.create:shell_claude_invoker` into the three `propose_*` functions, because those functions are not decorated with `spawn_cwd_from_repo_root` and only exercise shell-backstop telemetry when the test provides the scoped cwd.
  - `tests/test_detail.py:TestGenerateDetailPromptBudget` should gain a case that lets `generate_detail` call `plan_tool.detail:shell_detail_invoker`.
  - `tests/test_review.py:TestAuditPromptBudgetAdvisory` should gain a case that either enters `plan_tool.backend:spawn_cwd` before passing `plan_tool.review:shell_review_invoker` to `audit_plan_until_stable`, or drives `review_plan_full`, because `audit_plan_until_stable` is not decorated with `spawn_cwd_from_repo_root` and only exposes shell-backstop telemetry when the test provides the scoped cwd.
- **Count both recorder seams together.** In caller tests, patch the named module recorder and shell module recorder into one shared capture list:
  - `plan_tool.create.record_prompt_budget` plus `plan_tool.shell.record_prompt_budget`.
  - `plan_tool.detail.record_prompt_budget` plus `plan_tool.shell.record_prompt_budget`.
  - `plan_tool.review.record_prompt_budget` plus `plan_tool.shell.record_prompt_budget`.
  This is the important assertion: the final phases list should contain the named phase only, never an extra `"shell-backstop"` for the same send.
- **Keep subprocess hermetic.** Reuse the style already in `tests/test_shell.py:_fake_run_factory`: patch `plan_tool.shell.shutil.which` to return a fake executable and patch `plan_tool.shell.subprocess.run` to return valid stdout for the caller under test.
- **Return caller-valid stdout.** Each production-wrapper regression needs stdout that the named caller can parse:
  - Create distill: use the existing `_distill_single_json` helper in `tests/test_create.py`.
  - Create steps: return a valid one-step JSON list, matching `tests/test_create.py:TestCreatePromptBudgetAdvisory.test_steps_warns_before_invoke`.
  - Create synthesis: use `_full_body_json` in `tests/test_create.py`.
  - Detail: return `_GOOD_BODY` in `tests/test_detail.py`.
  - Review: return the two-section audit body produced by `tests/test_review.py:TestAuditPromptBudgetAdvisory._sections`.
- **Keep direct shell coverage.** `tests/test_shell.py` should still prove uninstrumented `plan_tool/shell.py:claude_invoke` records `phase="shell-backstop"` under `plan_tool.backend:spawn_cwd`. Add or adjust only the suppression-specific cases needed after step 2; do not weaken existing tests such as `test_backstop_records_telemetry_on_real_send`, `test_backstop_skips_telemetry_without_spawn_cwd`, and `test_backstop_fires_once_per_call_not_per_retry`.
- **Preserve create repair-retry intent.** `tests/test_create.py:TestCreatePromptBudgetAdvisory.test_repair_retry_warns_once` already pins that the named create check fires only for the initial send. If step 2 intentionally leaves repair retries eligible for the shell backstop, do not add a blanket "no shell-backstop ever" assertion for repair prompts.
- **Avoid production edits.** If these tests fail, the fix belongs to step 2's production files. This step should update only the test files listed here.

## Tests

- `tests/test_shell.py:test_backstop_suppression_skips_warn_and_record` — asserts the step 2 suppression scope prevents `maybe_warn_prompt_budget` and `record_prompt_budget` from firing at the shell backstop.
- `tests/test_shell.py:test_backstop_still_records_without_suppression` — asserts a direct `claude_invoke` under `spawn_cwd` still records exactly one `phase="shell-backstop"` event.
- `tests/test_create.py:test_distill_shell_invoker_records_named_budget_only` — asserts `propose_distilled_seed_from_claude` through `shell_claude_invoker` inside `spawn_cwd` records `phase="create-distill"` and no `phase="shell-backstop"`.
- `tests/test_create.py:test_steps_shell_invoker_records_named_budget_only` — asserts `propose_steps_from_claude` through `shell_claude_invoker` inside `spawn_cwd` records `phase="create-steps"` and no duplicate shell event.
- `tests/test_create.py:test_synthesis_shell_invoker_records_named_budget_only` — asserts `propose_body_sections` through `shell_claude_invoker` inside `spawn_cwd` records `phase="create-synthesis"` and no duplicate shell event.
- `tests/test_detail.py:test_shell_detail_invoker_records_named_budget_only` — asserts `generate_detail` through `shell_detail_invoker` records one `phase="detail"` event and no `phase="shell-backstop"`.
- `tests/test_review.py:test_shell_review_invoker_records_named_budget_only` — asserts `audit_plan_until_stable` through `shell_review_invoker` inside `spawn_cwd`, or via `review_plan_full`, records one `phase="plan-audit"` event and no `phase="shell-backstop"`, even when the audit loop runs more than one pass.

### Verification (non-code step)

This is a test-only step and changes no production code. Verify the affected regression set directly with `pytest tests/test_shell.py tests/test_create.py tests/test_detail.py tests/test_review.py tests/test_telemetry.py`. Also run a focused search after editing to confirm no new production files were touched for this step.

## Acceptance criteria

- Direct `plan_tool/shell.py:claude_invoke` with a scoped spawn cwd still records one prompt-budget event with `context.phase == "shell-backstop"`.
- Each named create production-wrapper send runs inside `plan_tool.backend:spawn_cwd`, records exactly one event with phase `create-distill`, `create-steps`, or `create-synthesis`, and records no `shell-backstop` event for that send.
- Detail generation through `plan_tool.detail:shell_detail_invoker` records exactly one `phase="detail"` prompt-budget event and no shell duplicate.
- Plan audit through `plan_tool.review:shell_review_invoker` inside `plan_tool.backend:spawn_cwd`, or through `review_plan_full`, records exactly one `phase="plan-audit"` prompt-budget event and no shell duplicate across the audit pass loop.
- Existing recorder tests in `tests/test_telemetry.py` still pass without a telemetry schema version bump.
- The step changes only `tests/test_telemetry.py`, `tests/test_shell.py`, `tests/test_create.py`, `tests/test_detail.py`, and `tests/test_review.py`.

## References

- [unittest.mock — mock object library](https://docs.python.org/3/library/unittest.mock.html) — Use for patching subprocess and recorder seams without invoking a real Claude binary.
- [pytest monkeypatch](https://docs.pytest.org/en/stable/how-to/monkeypatch.html) — Use for isolating module-level recorder, warning, cwd, and subprocess dependencies in tests.
- [pytest stdout/stderr capture](https://docs.pytest.org/en/stable/how-to/capture-stdout-stderr.html) — Use when a regression also checks that duplicate prompt-budget warnings are not emitted.
- [contextlib — Utilities for with-statement contexts](https://docs.python.org/3/library/contextlib.html) — Relevant if step 2 exposes suppression as a context manager that tests enter directly.
- [contextvars — Context Variables](https://docs.python.org/3/library/contextvars.html) — Relevant for understanding why shell suppression state must not leak between tests or threads.

## Deferred

- Production suppression fixes — belong to step 2 if these regressions fail.
- DATA_CONTRACT.md prompt-budget documentation — already covered by existing data-contract drift tests outside this step's file list.
- Repair-retry prompt-budget naming for create repair prompts — out of scope unless a later plan adds a named budget check for repair sends.
