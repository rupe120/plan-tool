# Step 1 — Read project backend defaults and command models

<!-- plan-tool:detail-format-version: 1 -->

## Summary

Expose the two opt-in settings through the existing backend configuration reader. Keep command registration knowledge in the CLI and preserve the legacy reader APIs.

## Table of Contents

- [Why](#why) — Purpose.
- [Files](#files) — Edit footprint.
- [Implementation](#implementation) — Smallest delivery path.
- [Tests](#tests) — Evidence.
- [Acceptance criteria](#acceptance-criteria) — Completion checks.

## Why

The existing reader supports only backend-wide tuning. Project defaults and command models need parsing before CLI selection can consume them.

## Files

Edit `plan_tool/backend_config.py`, `plan_tool/cli/parser.py`, and `tests/test_backend_config.py`. Create no files.

## Implementation

Use the current `.plan-tool/backends.json` reader and error type. Add `default_backend` and `backends.<name>.commands.<command>.model`; keep base model and extra-argv parsing in their existing owner. Expose the expanded settings to the CLI with one small result, not a settings registry. Existing `load_backend_overrides` and `backend_override_for` signatures and projection behavior remain usable without CLI context.

Derive a plain canonical-name/alias map from the assembled top-level parsers in `plan_tool/cli/parser.py`, without changing `assemble`'s return shape. CLI callers supply this map to the expanded reader for command-key validation and normalization. Backend leaves never assemble or import the CLI. Legacy projection reads retain base tuning and do not require command-name validation.

Validate the new shapes: absent `default_backend` inherits, but present null/empty/non-string fails; a missing `commands` block is empty, while present blocks and entries must be objects. Missing/null command models inherit; non-empty strings are trimmed and other values fail. Errors identify the file and field. Reject unknown command keys with supported choices, and reject two keys that normalize to the same command. Model names remain free-form.

Keep `default`, `aspects`, `failover`, and unrelated backend definition keys inert. Reads never write. Use shared parsing within this module rather than duplicating legacy model/argv validation.

## Tests

Use unmarked tests with temporary files and small fake parser registrations. Prefer parameterized cases:

| Property | Cases |
| --- | --- |
| New fields | absent, valid, null, empty, wrong types; inherited command model |
| Command identity | primary, alias, unknown, alias collision; distinct commands sharing a handler |
| Compatibility | legacy signatures/path override, base tuning/extras, arbitrary backend names, inert sibling keys |
| Read-only behavior | missing file and invalid file leave filesystem unchanged |

Run `uv run pytest tests/test_backend_config.py tests/cli/test_cli_parser.py -q`. Confirm a tightened validation or alias assertion fails when its corresponding branch is temporarily broken; restore the code before finishing.

## Acceptance criteria

- The expanded reader returns a project default and normalized backend-scoped command models.
- Validation follows the plan contract and errors identify the offending field.
- Legacy projection APIs retain base tuning without CLI imports or registration context.
- Focused tests pass, and reading configuration performs no writes.
