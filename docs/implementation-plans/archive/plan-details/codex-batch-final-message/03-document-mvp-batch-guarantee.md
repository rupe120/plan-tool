> **Auto-archived**: this plan was swept on 2026-06-24 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Document the MVP guarantee for Codex batch authoring and audit commands

## Summary

Update operator-facing docs so they accurately describe the Codex batch behavior after the final-message fix. The docs should distinguish the stable final-message capture mechanism from raw stdout, and should name the supported MVP scope without promising optimizations.

## Table of Contents

- [Why](#why) - docs must match the support boundary
- [Files](#files) - README, runbook, and contract
- [Implementation](#implementation) - update precise operator copy
- [Tests](#tests) - doc verification
- [Acceptance criteria](#acceptance-criteria) - documented guarantee
- [References](#references) - affected docs
- [Deferred](#deferred) - recommendation refreshes

## Why

The current docs correctly identify the Codex backend but leave batch final-message behavior easy to misread. Once the implementation is fixed, the documentation should say what works and how: batch commands return the final assistant message through the supported capture path, not by trusting arbitrary stdout.

## Files

- edits: `README.md`
- edits: `RUNBOOK.md`
- edits: `docs/CODEX_CLI_CONTRACT.md`
- references: `integrations/codex/SKILL.md`

## Implementation

Update the README Backends section to mention that batch authoring and audit commands use Codex's final-message capture path. Update the runbook only where an operator would diagnose backend behavior or decide whether Codex is safe for a workflow. Keep the contract document as the exact source for flags and version-specific behavior.

Avoid broad claims about performance, quality, or cost. The guarantee is functional: batch calls produce parseable final assistant text and streaming calls continue to parse JSON events.

## Tests

Non-code step. Verify by reading the affected docs and checking named flags against the implementation. Run validation if the plan is updated:

```bash
plan-tool validate codex-batch-final-message
```

## Acceptance criteria

- README no longer implies plain stdout is the reliable Codex batch response source.
- RUNBOOK gives an operator a correct troubleshooting model for Codex batch commands.
- The contract remains the version-pinned location for exact Codex flag spellings.
- No docs promise backend-quality improvements or cost reporting changes.

## References

- `README.md`
- `RUNBOOK.md`
- `docs/CODEX_CLI_CONTRACT.md`
- `integrations/codex/SKILL.md`

## Deferred

- Regenerating backend recommendations is deferred to the benchmark workflow.
