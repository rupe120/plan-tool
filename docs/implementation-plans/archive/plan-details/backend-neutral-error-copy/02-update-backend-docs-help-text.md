> **Auto-archived**: this plan was swept on 2026-06-24 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Update backend docs and help text where generic surfaces still imply Claude-only behavior

## Summary

Bring docs in line with the backend-neutral error copy. This is a small documentation pass that removes stale Claude-only phrasing from generic backend sections while preserving Claude-specific instructions where they truly apply. It should not introduce new behavior or policy.

## Table of Contents

- [Why](#why) - docs should match terminal behavior
- [Files](#files) - documentation surfaces
- [Implementation](#implementation) - targeted wording cleanup
- [Tests](#tests) - doc and help verification
- [Acceptance criteria](#acceptance-criteria) - copy alignment
- [References](#references) - docs to inspect
- [Deferred](#deferred) - large rename work

## Why

After step 1, terminal messages become backend-aware. The docs should teach the same model: plan-tool has a generic backend seam, with Claude as the default and Codex as an alternative. Leaving generic docs in Claude-only language makes Codex support look accidental.

## Files

- edits: `README.md`
- edits: `RUNBOOK.md`
- edits: `TESTING.md`
- edits: `integrations/codex/SKILL.md`
- edits: `integrations/claude/SKILL.md`

## Implementation

Search these documentation surfaces for generic use of `claude` where the text really means "active backend" or "backend subprocess." Update wording narrowly. Keep explicitly Claude-only material intact, such as Claude backend prerequisites, Claude-specific flags, and historical test names that refer to current code identifiers.

If help text from `plan_tool/cli/parser.py` contains stale user-facing wording, route that change back to step 1 only if code must change; otherwise keep this step docs-only.

## Tests

Non-code step. Verify with:

```bash
plan-tool validate backend-neutral-error-copy
```

Optionally run the package-surface help test if parser help text changes:

```bash
uv run pytest tests/cli/test_package_surface.py -q
```

## Acceptance criteria

- Generic docs describe the active backend rather than Claude-only execution.
- Codex-specific docs still name Codex prerequisites and auth behavior.
- Claude-specific docs still name Claude where the statement is truly Claude-only.
- No behavior or parser change is bundled into this docs step.

## References

- `README.md`
- `RUNBOOK.md`
- `TESTING.md`
- `integrations/codex/SKILL.md`
- `integrations/claude/SKILL.md`

## Deferred

- Renaming files, tests, or schema objects that include `claude` is deferred.
