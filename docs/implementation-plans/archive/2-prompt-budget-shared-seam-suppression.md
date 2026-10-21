> **Auto-archived**: this plan was swept on 2026-07-08 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

---
title: Prompt Budget Shared Seam Suppression
status: completed
priority: medium
enforce_step_tests: true
steps:
- id: 1
  title: Extract the shell prompt-budget backstop helper
  files:
  - plan_tool/shell.py
  - tests/test_shell.py
  complexity: low
  change_type: refactor
  enforce_test_authoring: false
  detail: docs/implementation-plans/plan-details/prompt-budget-shared-seam-suppression/01-extract-shell-prompt-budget-backstop.md
  status: done
- id: 2
  title: Add scoped shell backstop suppression for named prompt-budget sends
  files:
  - plan_tool/shell.py
  - plan_tool/create.py
  - plan_tool/detail.py
  - plan_tool/review.py
  - tests/test_shell.py
  - tests/test_create.py
  - tests/test_detail.py
  - tests/test_review.py
  complexity: medium
  change_type: feature
  depends_on:
  - 1
  detail: docs/implementation-plans/plan-details/prompt-budget-shared-seam-suppression/02-scoped-shell-backstop-suppression-named.md
  status: done
- id: 3
  title: Add prompt-budget telemetry regression coverage
  files:
  - tests/test_telemetry.py
  - tests/test_shell.py
  - tests/test_create.py
  - tests/test_detail.py
  - tests/test_review.py
  complexity: low
  change_type: non-code
  depends_on:
  - 2
  detail: docs/implementation-plans/plan-details/prompt-budget-shared-seam-suppression/03-prompt-budget-telemetry-regression.md
  status: done
- id: 4
  title: 'Remove the completed #99 backlog entry and references'
  files:
  - BACKLOG.md
  complexity: low
  change_type: non-code
  depends_on:
  - 3
  detail: docs/implementation-plans/plan-details/prompt-budget-shared-seam-suppression/04-remove-completed-99-backlog-entry.md
  status: done
---
# Prompt Budget Shared Seam Suppression

## Overview

Implement the smallest robust fix for duplicate prompt-budget advisories and telemetry on named-block sends. Named create, detail, and plan-audit sends should warn once and record one prompt-budget telemetry event, while `shell.claude_invoke` keeps its generic total-bytes backstop for callers without a named-block check such as `jira`, `lessons`, and `annotate`. The fix must handle `audit_plan_until_stable` across its N-pass loop and keep advisory behavior best-effort and non-blocking.

## Problem statement

The shipped prompt-budget-advisory plan (#95) added named-block pre-send budget checks in create/detail/plan-audit and a generic total-bytes backstop in `shell.claude_invoke`. Because `create.shell_claude_invoker`, `detail.shell_detail_invoker`, and `review.shell_review_invoker` all delegate to `shell.claude_invoke`, a named-block send currently emits both its named advisory/telemetry event and a second shell-backstop advisory/telemetry event. This creates duplicate warnings and duplicate prompt-budget telemetry for one real send, making user output noisy and telemetry misleading.

## Architecture

Preserve `plan_tool/shell.py` `claude_invoke` as the generic backstop while preventing it from firing for sends that already completed a named-block prompt-budget check in `plan_tool/create.py`, `plan_tool/detail.py`, or `plan_tool/review.py`.

The implementation should explicitly choose between scoped backstop suppression around named sends and per-invoke correlation-id telemetry dedupe. A scoped suppression approach should be tied to each logical named send and must work across every pass of `audit_plan_until_stable`, not through a fragile one-shot global mark that only suppresses pass 1. If the implementation uses Python context-local state for suppression, define the `ContextVar` at module scope and reset it with the token returned by `set()` so the suppression does not bleed into unrelated calls; `contextvars` are designed for context-local state and avoid the cross-context leakage risks of globals.

A correlation-id approach should dedupe telemetry per invoke while preserving the warning behavior and should update `DATA_CONTRACT.md` only if the prompt-budget event schema changes. `plan_tool/telemetry.py` `record_prompt_budget` remains the telemetry sink. Advisory and recorder failures must continue to be swallowed so prompt sending is not blocked by budget warning failures.

## References

- [contextvars — Context Variables](https://docs.python.org/3/library/contextvars.html) — Covers ContextVar tokens, reset semantics, and context-local state useful for scoped shell-backstop suppression.
- [contextlib — Utilities for with-statement contexts](https://docs.python.org/3/library/contextlib.html) — Documents contextmanager patterns for implementing best-effort scoped suppression with reliable cleanup.
- [subprocess — Subprocess management](https://docs.python.org/3/library/subprocess.html) — Defines subprocess invocation behavior relevant to preserving shell.claude_invoke as the generic backstop.
- [unittest.mock — mock object library](https://docs.python.org/3/library/unittest.mock.html) — Covers Mock, patch, side_effect, and call assertions needed to pin telemetry and advisory behavior in unit tests.
- [pytest monkeypatch](https://docs.pytest.org/en/stable/how-to/monkeypatch.html) — Explains pytest's monkeypatch fixture for isolating advisory, recorder, cwd, and subprocess dependencies in tests.
- [pytest stdout/stderr capture](https://docs.pytest.org/en/stable/how-to/capture-stdout-stderr.html) — Covers capsys and capture behavior needed to assert duplicate prompt-budget warnings are not emitted.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

- Changing `DATA_CONTRACT.md` when the prompt-budget event schema does not change; the seed only calls for documentation updates if the schema changes.
- Removing the `shell.claude_invoke` backstop for unnamed callers; callers such as `jira`, `lessons`, and `annotate` still need the generic warning and record path.

## Risks

- A fragile one-shot global suppression marker could suppress only pass 1 of `audit_plan_until_stable`; severity is high because later audit passes would still duplicate warnings and telemetry, and mitigation is to scope suppression or dedupe per logical invoke across every pass.
- Over-suppressing the shell backstop could hide budget warnings for unnamed direct `shell.claude_invoke` callers; severity is high, and mitigation is to prove unnamed callers still emit shell-backstop warning/record when spawn cwd is scoped.
- Recorder or advisory failures could become blocking if error handling changes; severity is medium, and mitigation is to keep failures swallowed and pin that behavior in tests.

## Testing

Unit tests should cover the chosen mechanism in `tests/test_shell.py`, `tests/test_create.py`, `tests/test_detail.py`, `tests/test_review.py`, and `tests/test_telemetry.py`.

Test coverage must prove that named create/detail/plan-audit sends produce exactly one named-phase prompt-budget record and no shell-backstop duplicate; unnamed direct `shell.claude_invoke` callers still produce the shell-backstop warning/record when spawn cwd is scoped; retry behavior remains one budget check per logical send; recorder failures and advisory failures remain swallowed; and the `audit_plan_until_stable` loop suppresses the backstop for every pass. Use `unittest.mock` assertions to prove call counts and arguments on patched advisory/telemetry collaborators, patching objects in the namespace where the code under test looks them up.

Existing suites that must still pass include `tests/test_shell.py`, `tests/test_create.py`, `tests/test_detail.py`, `tests/test_review.py`, and `tests/test_telemetry.py`.

**Per-step test strategy** (derived from each step's `change_type`):

- step 1 (refactor) — characterization tests pinned before the change; pass unchanged after.
- step 2 (feature) — unit tests added with the implementation; green before completion.
- step 3 (non-code) — verification appropriate to the artifacts; no test-ordering directive.
- step 4 (non-code) — verification appropriate to the artifacts; no test-ordering directive.

## Acceptance criteria

- Named create sends through `create.shell_claude_invoker` produce exactly one named-phase prompt-budget telemetry record and no shell-backstop duplicate.
- Named detail sends through `detail.shell_detail_invoker` produce exactly one named-phase prompt-budget telemetry record and no shell-backstop duplicate.
- Named plan-audit sends through `review.shell_review_invoker` and `audit_plan_until_stable` produce exactly one named-phase prompt-budget telemetry record per logical send and no shell-backstop duplicate.
- Unnamed direct `shell.claude_invoke` callers still produce the shell-backstop warning and prompt-budget telemetry record when spawn cwd is scoped.
- Retry behavior performs one budget check per logical send.
- Recorder failures and advisory failures remain swallowed and do not block sending.
- Tests pin the chosen suppression or dedupe mechanism and prove the audit loop suppresses the backstop for every pass.
- The backlog reconciliation step removes #99 or marks the completed resolution per `BACKLOG.md` rules.

## Deferred

- Further prompt-budget schema changes are deferred unless implementation changes the event contract, because this plan only needs to suppress duplicate advisories and telemetry for existing named sends.
