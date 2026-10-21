> **Auto-archived**: this plan was swept on 2026-06-24 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Add a backend batch-output contract for Codex final-message capture

## Summary

Add a narrow backend-level contract for deriving batch assistant text after a subprocess exits. The existing `claude_invoke` public shape stays `(rc, stdout)`, but `_run_once` gains a backend-aware way to convert raw process output and optional side artifacts into the text callers should parse. This prepares Codex batch calls for a reliable final-message source without rewriting every batch caller.

## Table of Contents

- [Why](#why) - raw stdout is not a stable Codex batch contract
- [Files](#files) - backend and shell footprint
- [Implementation](#implementation) - add the minimal hook
- [Tests](#tests) - prove Claude stays unchanged and Codex can differ
- [Acceptance criteria](#acceptance-criteria) - contract behavior
- [References](#references) - local contracts
- [Deferred](#deferred) - larger execution API

## Why

Streaming Codex calls already parse JSON events, but batch calls still assume stdout is the final assistant message. Codex's contract identifies `--output-last-message` or JSON parsing as the stable final-message source. A backend hook keeps the fix localized instead of scattering Codex conditionals across authoring and audit code.

## Files

- edits: `plan_tool/backend.py`
- edits: `plan_tool/shell.py`
- edits: `tests/test_backend.py`
- edits: `tests/test_shell.py`
- references: `docs/CODEX_CLI_CONTRACT.md`
- references: `integrations/codex/backend.json`

## Implementation

Extend `CliBackend` with the smallest useful batch-output capability. One acceptable shape is a callable that receives raw stdout, stderr, and an optional output file path, returning the assistant text to expose to callers. Claude should implement the identity behavior over stdout.

Adjust `_run_once` in `plan_tool/shell.py` to create any backend-requested side artifact before spawn, pass the backend's batch argv, and transform the result after the process exits. Keep timing, `stdin=subprocess.DEVNULL`, cwd scoping, rc handling, and event sink behavior unchanged.

## Tests

Feature step. Add tests before or with the hook:

- Claude batch argv and returned stdout remain byte-identical.
- A fake backend can transform stdout through the new hook.
- `_run_once` still passes `stdin=subprocess.DEVNULL` and active spawn cwd.

Run:

```bash
uv run pytest tests/test_backend.py tests/test_shell.py -q
```

## Acceptance criteria

- Batch output derivation is represented once on the backend descriptor or an immediately adjacent helper.
- Existing callers still receive `(rc, stdout)` from `claude_invoke`.
- Claude behavior is unchanged.
- The hook is sufficient for step 2 to implement Codex final-message capture without per-caller changes.

## References

- `plan_tool/backend.py`
- `plan_tool/shell.py`
- `docs/CODEX_CLI_CONTRACT.md`

## Deferred

- Returning structured batch stats from `claude_invoke` is deferred. This step only prepares correct final text.
