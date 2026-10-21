> **Auto-archived**: this plan was swept on 2026-06-24 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

---
title: Backend Neutral Error Copy
status: completed
priority: medium
enforce_step_tests: true
steps:
- id: 1
  title: Replace hardcoded claude wording in backend-generic failure hints
  files:
  - plan_tool/shell.py
  - plan_tool/claude_errors.py
  - tests/test_shell.py
  - tests/test_backend.py
  complexity: low
  change_type: feature
  detail: docs/implementation-plans/plan-details/backend-neutral-error-copy/01-replace-hardcoded-claude-wording.md
  status: done
  gate:
  - uv run pytest tests/test_shell.py tests/test_backend.py -q
- id: 2
  title: Update backend docs and help text where generic surfaces still imply Claude-only behavior
  files:
  - README.md
  - RUNBOOK.md
  - TESTING.md
  - integrations/codex/SKILL.md
  - integrations/claude/SKILL.md
  complexity: low
  change_type: non-code
  depends_on:
  - 1
  detail: docs/implementation-plans/plan-details/backend-neutral-error-copy/02-update-backend-docs-help-text.md
  status: done
---
# Backend Neutral Error Copy

## Overview

Clean up backend-generic user-facing copy so a Codex run does not report "claude" for missing executables, rate limits, context overflow, waits, or generic failure hints. This is not a behavior change; it removes misleading diagnostics from the MVP support path.

## Problem statement

The backend seam routes both Claude and Codex through the same subprocess and classifier code, but several messages still hardcode Claude. During a Codex MVP rollout, these messages make real failures harder to diagnose: an operator who selected `--backend codex` may see a "claude rate limit" or "`claude` executable not found" message and chase the wrong fix.

## Architecture

Keep the existing failure taxonomy and recovery behavior. Replace hardcoded display names with the active backend name from `get_active_backend()`. The classifier can continue to use `ClaudeFailureKind` internally for compatibility; only operator-facing strings and tests need to become backend-neutral.

Tests should activate a fake or Codex backend and assert the emitted hints name that backend. Claude-specific tests should still pass, but their assertions should check behavior instead of relying on stale literal wording where possible.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

- Renaming internal `ClaudeFailureKind`, `ClaudeRunStats`, or run-log event names.
- Changing retry policy.
- Changing auth or rate-limit detection patterns.

## Risks

- Some tests intentionally pin old copy. Update them only where the copy is backend-generic; do not churn unrelated output.
- Run-log schema names still contain `claude_*`. Renaming those is a migration and is explicitly out of scope.

## Testing

- `uv run pytest tests/test_shell.py tests/test_backend.py -q`
- A Codex-active classify or invoke test proves hints say `codex`, not `claude`.
- Existing Claude failure tests still pass.

## Acceptance criteria

- Missing-binary, rate-limit, context-overflow, transient, and unknown-nonzero user hints use the active backend display name where they are backend-generic.
- Codex auth failure copy remains specific and actionable.
- No run-log schema or internal enum migration is required.

## Deferred

- Renaming `ClaudeFailureKind`, `ClaudeRunStats`, and `claude_call_*` run-log fields to backend-neutral names is deferred until a schema migration is justified.
