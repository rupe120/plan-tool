> **Auto-archived**: this plan was swept on 2026-06-24 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Re-capture the Codex CLI contract against the installed binary

## Summary

Refresh the Codex contract and fixture set from the installed CLI version. This is a non-code evidence step: run the existing probe procedure, update the version stamp, and replace only fixture lines that reflect real schema or flag behavior. The output should make later parser changes evidence-driven rather than speculative.

## Table of Contents

- [Why](#why) - stale fixtures weaken MVP confidence
- [Files](#files) - contract and fixture footprint
- [Implementation](#implementation) - recapture and sanitize the evidence
- [Tests](#tests) - validate JSONL fixtures and contract consistency
- [Acceptance criteria](#acceptance-criteria) - checkable completion points
- [References](#references) - local source documents
- [Deferred](#deferred) - future automation left out

## Why

The checked-in contract is version-pinned. Local `codex --version` has already moved beyond the pinned version, so a real MVP run may encounter changed flags or event shapes that the current tests do not cover. Recapturing first keeps any code edits in step 2 grounded in observed CLI behavior.

## Files

- edits: `docs/CODEX_CLI_CONTRACT.md`
- edits: `tests/fixtures/codex/exec-stream-sample.jsonl`
- edits: `tests/fixtures/codex/exec-result-envelope.jsonl`
- edits: `tests/fixtures/codex/exec-command-execution.jsonl`
- edits: `tests/fixtures/codex/exec-turn-failed.jsonl`

## Implementation

Run the probe commands from `docs/CODEX_CLI_CONTRACT.md` in a disposable scratch directory. Capture `codex --version`, `codex exec --help`, a simple successful JSON stream, a command-execution stream, a file-change stream, and the invalid-model failure stream. Preserve JSONL line order and do not pretty-print fixture lines.

Before writing fixtures, sanitize absolute home paths, cwd paths, auth material, account identifiers, and any values that could identify the local environment. Keep schema-bearing keys, event types, status values, token fields, and terminal envelopes intact. Update the contract text to describe changed behavior only when the refreshed transcript proves it.

## Tests

Non-code step. Verify with shell checks rather than adding tests in this step:

- each touched `tests/fixtures/codex/*.jsonl` parses as line-delimited JSON
- the contract version stamp matches the binary used for capture
- `git diff` contains no real home path, token, account id, or unrelated fixture churn

## Acceptance criteria

- `docs/CODEX_CLI_CONTRACT.md` records the refreshed `codex --version` and capture date.
- The committed Codex fixtures reflect the refreshed contract and remain sanitized.
- Every refreshed JSONL fixture parses one standalone JSON object per non-empty line.
- The diff changes only contract and fixture evidence needed for the current installed CLI.

## References

- `docs/CODEX_CLI_CONTRACT.md`
- `tests/fixtures/codex/`
- `integrations/codex/backend.json`

## Deferred

- Automated scheduled contract recapture is deferred. This step is a manual refresh for the MVP support baseline.
