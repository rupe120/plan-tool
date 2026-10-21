> **Auto-archived**: this plan was swept on 2026-06-24 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

---
title: Codex Batch Final Message Capture
status: completed
priority: high
enforce_step_tests: true
steps:
- id: 1
  title: Add a backend batch-output contract for Codex final-message capture
  files:
  - plan_tool/backend.py
  - plan_tool/shell.py
  - tests/test_backend.py
  - tests/test_shell.py
  allowed_mentions:
  - docs/CODEX_CLI_CONTRACT.md
  - integrations/codex/backend.json
  complexity: medium
  change_type: feature
  detail: docs/implementation-plans/plan-details/codex-batch-final-message/01-add-backend-batch-output-contract.md
  status: done
  gate:
  - uv run pytest tests/test_backend.py tests/test_shell.py -q
- id: 2
  title: Route Codex batch invocations through a reliable final-message path
  files:
  - plan_tool/backend.py
  - plan_tool/shell.py
  - tests/test_backend.py
  - tests/test_shell.py
  allowed_mentions:
  - plan_tool/launcher.py
  - docs/CODEX_CLI_CONTRACT.md
  complexity: medium
  change_type: feature
  depends_on:
  - 1
  detail: docs/implementation-plans/plan-details/codex-batch-final-message/02-route-codex-batch-final-message.md
  gate:
  - uv run pytest tests/test_backend.py tests/test_shell.py tests/cli/test_package_surface.py::TestBackendSelection -q
  status: done
- id: 3
  title: Document the MVP guarantee for Codex batch authoring and audit commands
  files:
  - README.md
  - RUNBOOK.md
  - docs/CODEX_CLI_CONTRACT.md
  allowed_mentions:
  - integrations/codex/SKILL.md
  complexity: low
  change_type: non-code
  depends_on:
  - 2
  detail: docs/implementation-plans/plan-details/codex-batch-final-message/03-document-mvp-batch-guarantee.md
  status: done
---
# Codex Batch Final Message Capture

## Overview

Make Codex batch subprocess calls use a reliable final-message capture path before claiming Codex works across all plan-tool authoring and audit commands. The streaming `run` path already parses `codex exec --json`; the batch path still assumes plain stdout is the final assistant answer, while the captured contract names `--output-last-message` or JSON parsing as the stable source.

## Problem statement

Plan-tool has two backend invocation surfaces: streaming calls in `launcher.py` and batch calls in `shell.py`. Codex's streaming path is normalized against fixtures, but batch authoring and audit calls use `get_active_backend().batch_argv(prompt)` with `subprocess.run(..., capture_output=True)`. If modern Codex prints progress or diagnostics on stdout, or if final response behavior changes, batch consumers may parse the wrong text or see an empty response. That is an MVP correctness risk because `create`, `detail`, `review`, `jira`, and apply-style calls depend on batch stdout.

## Architecture

Introduce a narrow batch-output contract on `CliBackend` rather than special-casing Codex throughout call sites. Keep the public `claude_invoke(prompt) -> (rc, stdout)` shape unchanged: `_run_once` remains the single subprocess runner, but after the process exits it asks the active backend how to derive the assistant text from stdout, stderr, and any backend-specific side artifact.

The Codex implementation should prefer the contract-supported final-message path. The least invasive MVP shape is a temp file passed via `-o/--output-last-message` for Codex batch argv, read after the subprocess exits, and cleaned up. Claude keeps raw stdout. If the refreshed contract proves `--json` is better for batch, use the same parser path as streaming instead, but keep the abstraction local to `backend.py`/`shell.py`.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

- Reworking prompt transport off argv.
- Changing the streaming launcher protocol.
- Adding cross-backend optimization or quality benchmarking.

## Risks

- A temp-file based path must be cleaned up on both success and failure. Tests should cover non-zero Codex exits and missing output files.
- `CliBackend` is currently intentionally simple; the new hook should stay minimal and avoid turning the backend descriptor into a large class hierarchy.

## Testing

- `uv run pytest tests/test_backend.py tests/test_shell.py -q`
- Add a test that Codex batch argv carries the final-message output mechanism and that `_run_once` returns that final message instead of noisy stdout.
- Add a test that Claude batch behavior remains byte-identical.

## Acceptance criteria

- Codex batch calls return the final assistant message from a contract-supported source.
- Existing batch callers still see `(rc, stdout)` and do not need per-call changes.
- Claude batch argv and stdout behavior remain unchanged.
- The docs no longer overstate plain stdout as Codex's reliable batch response source.

## Deferred

- A larger backend execution API that returns structured batch stats is deferred. MVP only needs correct final-message text.
