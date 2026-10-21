> **Auto-archived**: this plan was swept on 2026-06-24 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Pin Codex auth classification against the captured transcript

## Summary

Use the captured unauthenticated transcript to test Codex auth classification directly. The goal is for `classify` to return `AUTH` for the real failure shape, with no wait and no retry. If the current auth regex is too broad or too narrow, adjust it and the manifest together.

## Table of Contents

- [Why](#why) - invented auth strings are not enough
- [Files](#files) - parser, manifest, and tests
- [Implementation](#implementation) - classify captured text
- [Tests](#tests) - backend unit coverage
- [Acceptance criteria](#acceptance-criteria) - auth classification behavior
- [References](#references) - fixture and backend code
- [Deferred](#deferred) - preflight UX

## Why

Tests currently prove that plausible auth strings match, not that the real Codex unauthenticated output matches. Fixture-backed classification closes that gap and protects the MVP from a silent downgrade to `UNKNOWN_NONZERO`.

## Files

- edits: `plan_tool/backend.py`
- edits: `tests/test_backend.py`
- references: `tests/fixtures/codex/exec-auth-failed.jsonl`

## Implementation

Add a test helper that loads the captured auth fixture. If the fixture is JSONL, parse each line through `CODEX_BACKEND.parse_stream_line` and join text chunks as the launcher does. If auth is stderr-only, load the captured text from the documented fixture format and pass it as stderr to `classify`.

Set the active backend to Codex in the test and assert `ClaudeFailureKind.AUTH`. If the test fails, update `_CODEX_AUTH_PATTERN` and the `classification.auth` field in `integrations/codex/backend.json` to match the captured copy without swallowing unrelated invalid-request failures.

## Tests

Feature step. Add the fixture-backed test, then run:

```bash
uv run pytest tests/test_backend.py -q
```

## Acceptance criteria

- The exact captured unauthenticated Codex failure classifies as `AUTH`.
- Captured invalid-model failures still classify as `UNKNOWN_NONZERO`.
- Auth failure remains no-wait and no-retry.
- `plan_tool/backend.py` and `integrations/codex/backend.json` stay aligned if the regex changes.

## References

- `plan_tool/backend.py`
- `integrations/codex/backend.json`
- `tests/test_backend.py`
- `tests/fixtures/codex/exec-auth-failed.jsonl`

## Deferred

- Credential preflight before spawning Codex is deferred.
