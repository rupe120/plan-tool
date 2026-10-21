> **Auto-archived**: this plan was swept on 2026-06-24 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Replace hardcoded claude wording in backend-generic failure hints

## Summary

Make backend-generic failure messages name the active backend instead of always saying Claude. This preserves retry and classification behavior while reducing operator confusion when `--backend codex` is selected. Internal class names and run-log schema stay unchanged.

## Table of Contents

- [Why](#why) - misleading error copy slows MVP rollout
- [Files](#files) - shell, classifier, and tests
- [Implementation](#implementation) - use active backend display names
- [Tests](#tests) - Codex-active copy assertions
- [Acceptance criteria](#acceptance-criteria) - user-facing wording
- [References](#references) - affected modules
- [Deferred](#deferred) - schema renames

## Why

The subprocess seam is now backend-generic, but some messages still say "claude rate limit" or "`claude` executable not found." During a Codex run that copy is false and points the operator at the wrong tool. The fix is low-risk because it changes display strings, not classification.

## Files

- edits: `plan_tool/shell.py`
- edits: `plan_tool/claude_errors.py`
- edits: `tests/test_shell.py`
- edits: `tests/test_backend.py`

## Implementation

Audit user-facing strings in `shell.py` and `claude_errors.py` that describe the active subprocess. Replace hardcoded `claude` only when the message is backend-generic. Use `get_active_backend().name` or a small helper so rate-limit, context-overflow, transient, unknown-nonzero, missing-binary, and wait-copy messages name the selected backend.

Leave internal identifiers such as `ClaudeFailureKind`, `ClaudeRunStats`, and `claude_call_end` untouched. Also leave Claude-specific historical comments alone unless they appear in terminal output.

## Tests

Feature step. Update existing tests and add one Codex-active assertion for each changed class of message where practical. Run:

```bash
uv run pytest tests/test_shell.py tests/test_backend.py -q
```

## Acceptance criteria

- Missing executable output names the active backend binary.
- Rate-limit, context-overflow, transient, and unknown-nonzero hints name the active backend.
- Codex auth failure remains specific and actionable.
- No run-log schema, enum, or public Python API is renamed.

## References

- `plan_tool/shell.py`
- `plan_tool/claude_errors.py`
- `tests/test_shell.py`
- `tests/test_backend.py`

## Deferred

- Backend-neutral schema renames are deferred until there is a planned run-log migration.
