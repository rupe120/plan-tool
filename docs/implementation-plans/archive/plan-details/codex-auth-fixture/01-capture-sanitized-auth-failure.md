> **Auto-archived**: this plan was swept on 2026-06-24 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Capture a sanitized Codex unauthenticated failure transcript

## Summary

Capture Codex's real unauthenticated failure shape without touching the user's actual credentials. Use an isolated temporary `CODEX_HOME`, closed stdin, and a disposable working directory. Record the observed stdout, stderr, or JSONL shape in the contract and fixture set so auth classification is grounded in real CLI output.

## Table of Contents

- [Why](#why) - broad regexes need captured evidence
- [Files](#files) - contract and fixture output
- [Implementation](#implementation) - safe isolated auth probe
- [Tests](#tests) - fixture sanity checks
- [Acceptance criteria](#acceptance-criteria) - captured auth behavior
- [References](#references) - contract and Codex docs
- [Deferred](#deferred) - credential preflight command

## Why

The current auth regex is intentionally broad because the first probe avoided corrupting live credentials. The safe way to capture auth failure is to point Codex at an empty temporary home, not to edit `~/.codex`. The MVP then has an exact failure string to test.

## Files

- edits: `docs/CODEX_CLI_CONTRACT.md`
- creates: `tests/fixtures/codex/exec-auth-failed.jsonl`

## Implementation

Create a temporary directory and run Codex with `CODEX_HOME` set to that path. Use closed stdin and a disposable cwd. Prefer the same `codex exec --json` shape used by the other fixtures; if Codex fails before emitting JSON, record the raw stderr/stdout text in the contract and either commit a representative fixture file or document why no JSONL fixture exists.

Sanitize any absolute paths or identifiers. Do not copy tokens or real account data. The fixture should contain only the auth-failure schema and message needed for parser and classifier tests.

## Tests

Non-code step. Verify manually:

- the probe did not read or modify the user's real `~/.codex`
- any committed JSONL parses line by line
- the contract explains whether auth failure is JSONL, stderr-only, or both

## Acceptance criteria

- A real Codex unauthenticated failure shape is captured and documented.
- The capture procedure uses isolated `CODEX_HOME` and closed stdin.
- The committed artifact contains no real credential, account, or home-path data.
- The contract is explicit about which stream carries the auth message.

## References

- `docs/CODEX_CLI_CONTRACT.md`
- `tests/fixtures/codex/`
- `integrations/codex/backend.json`

## Deferred

- A dedicated backend-auth doctor command is deferred.
