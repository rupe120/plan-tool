> **Auto-archived**: this plan was swept on 2026-07-08 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 2 — Add scoped shell backstop suppression for named prompt-budget sends

## Summary

Add a scoped suppression path so `plan_tool/shell.py:claude_invoke` keeps its generic prompt-budget backstop for uninstrumented batch callers, but skips it when an upstream caller has already emitted a named prompt-budget advisory for the same send. The main edits are in `plan_tool/shell.py`, with caller wiring in `plan_tool/create.py`, `plan_tool/detail.py`, and `plan_tool/review.py`. The key design decision is to make suppression explicit at the already-instrumented send sites, not automatic in the `shell_*_invoker` wrappers. Green means named create/detail/review sends produce one prompt-budget warning/telemetry record, while direct batch callers still get the shell backstop.

## Table of Contents

- [Summary](#summary) — The short version of the suppression behavior and files touched.
- [Why](#why) — Why the shell backstop needs a scoped opt-out now.
- [Input](#input) — The upstream helper and existing prompt-budget contracts this step relies on.
- [Files creates vs edits](#files-creates-vs-edits) — The exact file footprint for this step.
- [Implementation](#implementation) — The intended shell API, caller wiring, and invariants.
- [Tests](#tests) — The regression cases that prove suppression is scoped and non-leaking.
- [Acceptance criteria](#acceptance-criteria) — Observable checks for review and CI.
- [References](#references) — Primary docs for the context manager and test seams.
- [Deferred](#deferred) — Related work this step does not take on.

## Why

`plan_tool/shell.py:claude_invoke` is the shared batch Claude seam and must keep a generic prompt-budget backstop for callers with no named block breakdown, such as `plan_tool/jira.py:shell_jira_invoker`, `plan_tool/lessons.py:default_equivalence_invoker`, and `plan_tool/annotate.py`. Create, detail, and plan-audit already run better named prompt-budget checks before their sends, so the shell backstop currently duplicates warning and telemetry for those paths when they use the production shell invoker. This step adds a narrow opt-out that only those named sends activate, keeping the backstop useful for every uninstrumented caller.

## Input

- **Shell backstop location:** `plan_tool/shell.py:claude_invoke` owns the generic shell backstop before the subprocess retry loop; apply suppression at that backstop site whether it is still inline or has been extracted by step 1.
- **Shell byte measure:** `plan_tool/shell.py:claude_invoke` must keep using `backend.batch_transport(prompt).prompt_bytes` when the backstop is not suppressed.
- **Named create checks:** `plan_tool/create.py:_maybe_warn_create_budget` is already called by `plan_tool/create.py:propose_distilled_seed_from_claude`, `plan_tool/create.py:propose_steps_from_claude`, and `plan_tool/create.py:propose_body_sections`.
- **Named detail check:** `plan_tool/detail.py:_author_step_detail` already checks and records the detail prompt budget once per invoked step before its retry loop.
- **Named review check:** `plan_tool/review.py:audit_plan_until_stable` already checks and records the base plan-audit prompt once before the audit pass loop.
- **Limit:** suppression is only about the shell backstop. It must not skip the named caller checks, subprocess execution, retry handling, `ClaudeCallEnd` sink events, or existing run-log start/end behavior.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/shell.py` — Add a thread-scoped suppression context, skip the shell backstop warn/record work while suppression is active, and keep `claude_invoke` behavior unchanged outside that scope.
  - `plan_tool/create.py` — Wrap only the already-named production sends in `propose_distilled_seed_from_claude`, `propose_steps_from_claude`, and `propose_body_sections` so their next shell call does not run the generic backstop.
  - `plan_tool/detail.py` — Wrap the invoked-step retry loop in `_author_step_detail` after the named detail budget check so both the first attempt and parse-repair retry avoid duplicate shell backstop output.
  - `plan_tool/review.py` — Suppress shell backstop calls during the `audit_plan_until_stable` pass loop only after the once-per-run plan-audit budget check has run.
  - `tests/test_shell.py` — Add shell-level suppression tests and extend the autouse reset fixture to clear the new context state.
  - `tests/test_create.py` — Add create-path tests proving named create checks still fire once and shell backstop telemetry does not double-record when using `shell_claude_invoker`.
  - `tests/test_detail.py` — Add detail-path tests proving `_author_step_detail` keeps one named budget record and no shell-backstop record, including the parse-retry shape.
  - `tests/test_review.py` — Add audit-path tests proving `audit_plan_until_stable` keeps one named budget record while suppressing shell backstop records across multiple passes.

## Implementation

- **Foundational logic:** scoped prompt-budget backstop suppression for already-advised batch sends.

- **Add a scoped shell API.** In `plan_tool/shell.py`, add a small context manager, likely named `suppress_prompt_budget_backstop()`, backed by a `contextvars.ContextVar`. A counter or token-based reset is fine; the required behavior is nested-safe, thread-scoped, and reset in a `finally` path.

- **Check suppression at the shell backstop site.** The generic shell backstop path in `plan_tool/shell.py:claude_invoke`, whether inline or helper-extracted, should be the only place that reads the suppression state. When suppressed, it should skip `maybe_warn_prompt_budget` and `record_prompt_budget` and then continue with the normal invoke path. `plan_tool/shell.py:claude_invoke` should still do the PATH check, retry loop, `_run_once`, `_emit_call_end`, failure classification, and return handling as it does today.

- **Do not suppress in wrapper functions by default.** Avoid putting the context manager inside `plan_tool/create.py:shell_claude_invoker`, `plan_tool/detail.py:shell_detail_invoker`, or `plan_tool/review.py:shell_review_invoker`. Those wrappers are also reachable from callers that do not have named budget checks, so suppressing there would remove the only backstop those callers get.

- **Wire create at the real named sends.** In `plan_tool/create.py`, enter the suppression scope only around the `raw = invoker(prompt)` call that immediately follows `_maybe_warn_create_budget` in:
  - `plan_tool/create.py:propose_distilled_seed_from_claude`
  - `plan_tool/create.py:propose_steps_from_claude`
  - `plan_tool/create.py:propose_body_sections`

- **Gate create suppression to the production shell wrapper when needed.** Tests often inject fake invokers. If the implementation uses a scope around `invoker(prompt)` regardless of invoker identity, ensure a fake invoker cannot leave state behind for a later shell call. One simple approach is to use a proper context manager around the call; another is to apply the scope only when `invoker is shell_claude_invoker`.

- **Handle create repair retries deliberately.** The existing create named checks fire once for the initial send, not the repair prompt. Suppress only the initial send that has just been advised. Leave repair-retry sends to the generic shell backstop unless the implementation also adds an explicit named check for those repair prompts, which is outside this step.

- **Wire detail around the retry loop.** In `plan_tool/detail.py:_author_step_detail`, place the suppression scope after the named detail budget check and around the loop that calls `invoker(attempt_prompt)`. The named detail check already represents the whole invoked-step prompt, and the `_REPROMPT_SUFFIX` retry is intentionally treated as the same budget event.

- **Wire review around the audit pass loop.** In `plan_tool/review.py:audit_plan_until_stable`, enter suppression for the sends driven by the pass loop after the once-per-run plan-audit budget check. This prevents one shell-backstop record per pass while preserving the single named `phase="plan-audit"` record.

- **Preserve uninstrumented batch callers.** Calls through `plan_tool/jira.py:shell_jira_invoker`, `plan_tool/lessons.py:default_equivalence_invoker`, and `plan_tool/annotate.py` should keep the shell backstop because they do not set the suppression context.

- **Preserve telemetry scoping.** When the shell backstop is not suppressed, it still records only under `plan_tool/backend.py:get_active_spawn_cwd`, still uses `phase="shell-backstop"`, and still uses an empty `plan_slug`.

- **Keep the advisory best-effort.** Suppression should never affect `(rc, stdout)`, subprocess count, retry behavior, stderr from non-budget failures, or run-log sink events.

## Tests

- `tests/test_shell.py:test_suppressed_backstop_skips_warn_and_record_but_still_invokes` — Inside the new shell suppression context, `claude_invoke` still returns subprocess output but does not call `maybe_warn_prompt_budget` or `record_prompt_budget`.
- `tests/test_shell.py:test_backstop_runs_again_after_suppression_scope_exits` — A call after the context exits runs the shell backstop normally.
- `tests/test_shell.py:test_backstop_suppression_is_nested_safe` — Nested suppression scopes do not re-enable the backstop until the outer scope exits.
- `tests/test_shell.py:test_backstop_suppression_is_thread_scoped` — Suppression in one thread does not suppress a separate thread's `claude_invoke`.
- `tests/test_create.py:test_shell_create_distill_does_not_double_record_prompt_budget` — `propose_distilled_seed_from_claude` with `shell_claude_invoker` records the named `create-distill` event and no `shell-backstop` event.
- `tests/test_create.py:test_shell_create_steps_does_not_double_record_prompt_budget` — `propose_steps_from_claude` with `shell_claude_invoker` records the named `create-steps` event and no `shell-backstop` event.
- `tests/test_create.py:test_shell_create_synthesis_does_not_double_record_prompt_budget` — `propose_body_sections` with `shell_claude_invoker` records the named `create-synthesis` event and no `shell-backstop` event.
- `tests/test_detail.py:test_shell_detail_does_not_double_record_prompt_budget` — `generate_detail` using `shell_detail_invoker` records one named detail budget event and no shell-backstop event.
- `tests/test_detail.py:test_detail_parse_retry_stays_suppressed_for_shell_backstop` — A detail parse retry still produces one named detail budget event and no shell-backstop event for either attempt.
- `tests/test_review.py:test_shell_plan_audit_does_not_double_record_prompt_budget` — `audit_plan_until_stable` using `shell_review_invoker` records one named plan-audit budget event and no shell-backstop event.
- `tests/test_review.py:test_plan_audit_suppresses_shell_backstop_across_passes` — Multiple audit passes do not produce per-pass shell-backstop telemetry.

### Test-creation order (feature step)

1. Add the shell-only suppression tests in `tests/test_shell.py` first, because they define the new context contract without create/detail/review setup.
2. Add the create wiring tests in `tests/test_create.py`, using the existing prompt-budget spy style around `plan_tool.create.maybe_warn_prompt_budget` and `plan_tool.create.record_prompt_budget`.
3. Add the detail wiring tests in `tests/test_detail.py`, reusing `TestGenerateDetailPromptBudget` helpers where possible.
4. Add the review wiring tests in `tests/test_review.py`, reusing `TestAuditPromptBudgetAdvisory` fixtures and a fake shell subprocess path.
5. The green-before-done gate is all new tests plus the existing prompt-budget suites in `tests/test_shell.py`, `tests/test_create.py`, `tests/test_detail.py`, and `tests/test_review.py`.

## Acceptance criteria

- `plan_tool/shell.py:claude_invoke` still runs the shell backstop by default when the executable exists.
- Inside the new shell suppression context, `plan_tool/shell.py:claude_invoke` skips only the shell prompt-budget warn/record helper.
- Suppression state is thread-scoped, nested-safe, and always restored after the context exits.
- `plan_tool/create.py:propose_distilled_seed_from_claude`, `plan_tool/create.py:propose_steps_from_claude`, and `plan_tool/create.py:propose_body_sections` do not emit `phase="shell-backstop"` telemetry for their already-named initial sends when using `shell_claude_invoker`.
- `plan_tool/detail.py:_author_step_detail` does not emit shell-backstop telemetry for the initial detail attempt or parse-repair retry when using `shell_detail_invoker`.
- `plan_tool/review.py:audit_plan_until_stable` does not emit shell-backstop telemetry across audit passes when using `shell_review_invoker`.
- Uninstrumented direct calls to `plan_tool/shell.py:claude_invoke` still emit shell-backstop telemetry when `get_active_spawn_cwd()` is scoped.
- Existing retry, missing executable, nonzero exit, and run-log sink tests in `tests/test_shell.py` still pass.

## References

- [contextvars — Context Variables](https://docs.python.org/3/library/contextvars.html) — Use this for thread-scoped suppression state and reset semantics.
- [contextlib — Utilities for with-statement contexts](https://docs.python.org/3/library/contextlib.html) — Use this for a small context manager with reliable cleanup.
- [subprocess — Subprocess management](https://docs.python.org/3/library/subprocess.html) — Check this when preserving `claude_invoke` subprocess behavior while changing only the pre-send advisory.
- [unittest.mock — mock object library](https://docs.python.org/3/library/unittest.mock.html) — Useful for call assertions around warn and telemetry spies.
- [pytest monkeypatch](https://docs.pytest.org/en/stable/how-to/monkeypatch.html) — Use this for hermetic shell, recorder, and subprocess test seams.
- [pytest stdout/stderr capture](https://docs.pytest.org/en/stable/how-to/capture-stdout-stderr.html) — Use this to assert duplicate prompt-budget warnings are not printed.

## Deferred

- `plan_tool/jira.py`, `plan_tool/lessons.py`, and `plan_tool/annotate.py` named prompt-budget breakdowns — These callers keep relying on the shell backstop because this step only suppresses callers that already have named checks.
- `plan_tool/launcher.py:run_step` — The streaming run path does not use `plan_tool/shell.py:claude_invoke`, so shell suppression does not apply there.
- Named checks for create repair prompts — This step suppresses duplicate shell backstop output for already-advised initial sends; adding named block breakdowns for repair prompts is separate behavior.
