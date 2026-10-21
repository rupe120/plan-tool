> **Auto-archived**: this plan was swept on 2026-06-24 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Route Codex batch invocations through a reliable final-message path

## Summary

Make Codex batch calls return the final assistant message from the contract-supported source. The likely MVP path is `codex exec ... --output-last-message <tmpfile>`, with `_run_once` reading that file after exit and exposing it as stdout to existing batch consumers. This closes the main Codex MVP risk for authoring and audit commands.

## Table of Contents

- [Why](#why) - batch callers need parseable final text
- [Files](#files) - Codex backend, shell, and tests
- [Implementation](#implementation) - wire output-last-message or JSON parsing
- [Tests](#tests) - targeted batch behavior
- [Acceptance criteria](#acceptance-criteria) - final-message guarantees
- [References](#references) - contract and adjacent streaming path
- [Deferred](#deferred) - prompt transport changes

## Why

Commands such as `detail`, `create`, `review`, and apply-style flows use batch invocation and parse the returned text. If Codex emits progress, warnings, or no final answer on plain stdout, those commands fail even though streaming `run` works. The MVP support claim depends on batch text being reliable.

## Files

- edits: `plan_tool/backend.py`
- edits: `plan_tool/shell.py`
- edits: `tests/test_backend.py`
- edits: `tests/test_shell.py`
- references: `plan_tool/launcher.py`
- references: `docs/CODEX_CLI_CONTRACT.md`

## Implementation

Use the hook from step 1 to add Codex-specific final-message capture. Prefer `--output-last-message <file>` if the refreshed contract still confirms it. Ensure the output file path is generated per invocation, never stored in the manifest, and removed in a `finally` path.

On successful Codex exits, return the final-message file contents when present. On non-zero exits, preserve enough stdout and stderr for `classify` to work, but do not let progress copy masquerade as a model response. If the final-message file is missing on a zero exit, surface a clear warning or return raw stdout only when tests prove that fallback is safe.

## Tests

Feature step. Add tests covering:

- Codex batch argv includes the final-message capture mechanism before the prompt.
- `_run_once` returns the file content rather than noisy stdout for Codex.
- Missing final-message file on non-zero Codex exit still leaves classifier text available.
- Claude remains unchanged.

Run:

```bash
uv run pytest tests/test_backend.py tests/test_shell.py tests/cli/test_package_surface.py::TestBackendSelection -q
```

## Acceptance criteria

- Codex batch calls expose the final assistant message to existing batch consumers.
- The implementation keeps `stdin=subprocess.DEVNULL` and cwd scoping intact.
- Non-zero Codex failures remain classifiable from combined stdout/stderr.
- No authoring or audit call site needs a Codex-specific branch.

## References

- `docs/CODEX_CLI_CONTRACT.md`
- `plan_tool/backend.py`
- `plan_tool/shell.py`
- `plan_tool/launcher.py`

## Deferred

- Moving the whole prompt off argv is deferred. This step changes response capture only.
