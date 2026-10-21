> **Auto-archived**: this plan was swept on 2026-06-24 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Document the safe auth probe procedure for future recaptures

## Summary

Document how to reproduce Codex auth failure safely. The procedure should make it clear that operators must not rename, corrupt, or delete their real `~/.codex` files. Future contract refreshes can then recapture auth behavior without risking credentials.

## Table of Contents

- [Why](#why) - auth probes are easy to do unsafely
- [Files](#files) - contract and runbook updates
- [Implementation](#implementation) - add safe procedure
- [Tests](#tests) - doc verification
- [Acceptance criteria](#acceptance-criteria) - clear operator steps
- [References](#references) - existing docs
- [Deferred](#deferred) - doctor command

## Why

The original contract avoided auth capture to protect real credentials. Now that an isolated `CODEX_HOME` procedure exists, it should be written down so future recaptures use the safe path instead of ad hoc credential mutation.

## Files

- edits: `docs/CODEX_CLI_CONTRACT.md`
- edits: `RUNBOOK.md`
- references: `README.md`

## Implementation

Add a short auth-probe subsection to the contract runbook: create a temp `CODEX_HOME`, run `codex exec --json` with closed stdin, capture stdout/stderr, sanitize, and remove the temp directory. Add a runbook recovery note that auth failures should be fixed with `codex login` or a corrected `CODEX_HOME`, not by retrying.

Keep README changes out unless the existing README prerequisites become inaccurate. README already names `~/.codex` and `codex login`; the detailed safe-probe mechanics belong in the contract and runbook.

## Tests

Non-code step. Verify with:

```bash
plan-tool validate codex-auth-fixture
```

Manual review should confirm the procedure never instructs users to edit real `~/.codex/auth.json`.

## Acceptance criteria

- The contract documents a safe isolated auth-failure probe.
- RUNBOOK tells operators auth failures are no-wait/no-retry and require credential repair.
- The docs do not instruct users to corrupt, move, or delete real Codex credentials.
- README remains accurate or is intentionally left unchanged.

## References

- `docs/CODEX_CLI_CONTRACT.md`
- `RUNBOOK.md`
- `README.md`

## Deferred

- A `plan-tool doctor` command for backend credentials is deferred.
