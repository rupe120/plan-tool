> **Auto-archived**: this plan was swept on 2026-06-24 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

---
title: Codex Auth Failure Fixture
status: completed
priority: medium
enforce_step_tests: true
steps:
- id: 1
  title: Capture a sanitized Codex unauthenticated failure transcript
  files:
  - docs/CODEX_CLI_CONTRACT.md
  creates:
  - tests/fixtures/codex/exec-auth-failed.jsonl
  complexity: low
  change_type: non-code
  detail: docs/implementation-plans/plan-details/codex-auth-fixture/01-capture-sanitized-auth-failure.md
  status: done
- id: 2
  title: Pin Codex auth classification against the captured transcript
  files:
  - plan_tool/backend.py
  - tests/test_backend.py
  allowed_mentions:
  - tests/fixtures/codex/exec-auth-failed.jsonl
  complexity: low
  change_type: feature
  depends_on:
  - 1
  detail: docs/implementation-plans/plan-details/codex-auth-fixture/02-pin-auth-classification.md
  gate:
  - uv run pytest tests/test_backend.py -q
  status: done
- id: 3
  title: Document the safe auth probe procedure for future recaptures
  files:
  - docs/CODEX_CLI_CONTRACT.md
  - RUNBOOK.md
  allowed_mentions:
  - README.md
  complexity: low
  change_type: non-code
  depends_on:
  - 2
  detail: docs/implementation-plans/plan-details/codex-auth-fixture/03-document-safe-auth-probe.md
  status: done
---
# Codex Auth Failure Fixture

## Overview

Turn Codex auth-failure handling from broad best-effort regex coverage into fixture-backed behavior. The MVP should be able to tell an operator "Codex is not authenticated; run `codex login` or fix `CODEX_HOME`" without waiting, retrying, or misclassifying it as an unknown backend failure.

## Problem statement

The current Codex auth pattern is intentionally broad because the original probe avoided corrupting a live `~/.codex/auth.json`. That is reasonable for a first pass, but README now promises clean auth-failure UX. Without a captured unauthenticated transcript, a CLI wording change can silently degrade to `UNKNOWN_NONZERO`, and tests only prove that invented sample strings match the regex.

## Architecture

Capture auth failure safely by setting `CODEX_HOME` to an empty temporary directory for the subprocess, not by editing the user's real `~/.codex`. Save the resulting `codex exec --json` output as a sanitized JSONL fixture if Codex emits JSON, or document the stderr/stdout shape if it fails before JSON starts. Then drive that captured payload through `CODEX_BACKEND.parse_stream_line` and `classify` in `tests/test_backend.py`.

If the real transcript exposes a narrower and more accurate auth phrase, update `CODEX_BACKEND.auth_pattern` and `integrations/codex/backend.json` together. If Codex exits before JSON, the classifier test should still feed the captured text as stdout/stderr and assert `ClaudeFailureKind.AUTH`.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

- Changing Codex login or credential storage.
- Retrying auth failures.
- Adding a credential preflight before every read-only command.

## Risks

- The auth probe must not read or mutate the operator's real Codex credentials. Use an isolated `CODEX_HOME` and closed stdin.
- The failure may be emitted on stderr rather than stdout. Tests should classify the combined text path, not assume a stream event exists.

## Testing

- `uv run pytest tests/test_backend.py -q`
- Manual probe with `CODEX_HOME=$(mktemp -d)` confirms the fixture is reproducible without touching `~/.codex`.
- Fixture sanitization review confirms no real paths, tokens, or account identifiers are committed.

## Acceptance criteria

- A captured unauthenticated Codex failure is recorded in the contract or fixture set.
- `classify` returns `AUTH` for that exact captured failure under the Codex backend.
- The user hint remains no-wait/no-retry and points at re-authentication.
- The runbook documents the safe auth probe procedure.

## Deferred

- A dedicated `plan-tool doctor` command for backend auth preflight is deferred. MVP only needs classification once a backend call reaches auth failure.
