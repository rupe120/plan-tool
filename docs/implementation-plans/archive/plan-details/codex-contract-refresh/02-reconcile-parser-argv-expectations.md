> **Auto-archived**: this plan was swept on 2026-06-24 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Reconcile Codex parser and argv expectations with the refreshed contract

## Summary

Update Codex parser or manifest behavior only where the refreshed contract requires it. The target is compatibility with the current supported Codex CLI while preserving the existing backend abstraction. If the refreshed fixture set still matches the current code, this step should be a no-op implementation with tests proving that fact.

## Table of Contents

- [Why](#why) - parser behavior must follow captured evidence
- [Files](#files) - backend and test footprint
- [Implementation](#implementation) - compare fixtures to parser and manifest
- [Tests](#tests) - targeted backend test run
- [Acceptance criteria](#acceptance-criteria) - parser and argv checks
- [References](#references) - relevant code and fixtures
- [Deferred](#deferred) - non-MVP backend work

## Why

Codex event schema drift should not be handled by broad guesses. The code already has a focused parser, manifest loader, and fixture-backed tests; this step keeps that shape and updates only the parts that are stale after recapture.

## Files

- edits: `plan_tool/backend.py`
- edits: `integrations/codex/backend.json`
- edits: `tests/test_backend.py`
- edits: `tests/test_launcher.py`
- references: `docs/CODEX_CLI_CONTRACT.md`

## Implementation

Drive the refreshed JSONL fixtures through `CODEX_BACKEND.parse_stream_line`. Check every event family the contract names: agent messages, command execution, file changes, terminal success, terminal failure, usage fields, cached input tokens, and request-id correlation. If a field path changed, update `_codex_parse_stream_line` and the tests together.

Compare `codex exec --help` from the refreshed contract to `integrations/codex/backend.json`. Keep `stdin=subprocess.DEVNULL` behavior in the spawn sites untouched. Update manifest flags only if the supported invocation changed; avoid adding project-local workarounds to the manifest.

## Tests

Feature step. Add or update tests with the implementation, then run:

```bash
uv run pytest tests/test_backend.py tests/test_launcher.py -q
```

If no code change is needed, run the same test command and record that the refreshed fixtures are compatible.

## Acceptance criteria

- Codex parser tests pass against the refreshed fixtures.
- `CODEX_BACKEND` still extracts final text, token input/output, cached input tokens, and terminal error state correctly.
- `integrations/codex/backend.json` matches the refreshed supported invocation.
- Unknown or extra Codex events continue to degrade through the generic event path rather than breaking parsing.

## References

- `plan_tool/backend.py`
- `integrations/codex/backend.json`
- `tests/test_backend.py`
- `tests/test_launcher.py`
- `docs/CODEX_CLI_CONTRACT.md`

## Deferred

- Quality benchmarking and backend recommendations are deferred to the benchmark workflow, not this compatibility step.
