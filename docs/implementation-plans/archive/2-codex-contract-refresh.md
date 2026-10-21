> **Auto-archived**: this plan was swept on 2026-06-24 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

---
title: Codex Contract Refresh
status: completed
priority: high
enforce_step_tests: true
steps:
- id: 1
  title: Re-capture the Codex CLI contract against the installed binary
  files:
  - docs/CODEX_CLI_CONTRACT.md
  - tests/fixtures/codex/exec-stream-sample.jsonl
  - tests/fixtures/codex/exec-result-envelope.jsonl
  - tests/fixtures/codex/exec-command-execution.jsonl
  - tests/fixtures/codex/exec-turn-failed.jsonl
  complexity: medium
  change_type: non-code
  detail: docs/implementation-plans/plan-details/codex-contract-refresh/01-re-capture-codex-cli-contract.md
  status: done
- id: 2
  title: Reconcile Codex parser and argv expectations with the refreshed contract
  files:
  - plan_tool/backend.py
  - integrations/codex/backend.json
  - tests/test_backend.py
  - tests/test_launcher.py
  allowed_mentions:
  - docs/CODEX_CLI_CONTRACT.md
  complexity: medium
  change_type: feature
  depends_on:
  - 1
  detail: docs/implementation-plans/plan-details/codex-contract-refresh/02-reconcile-parser-argv-expectations.md
  gate:
  - uv run pytest tests/test_backend.py tests/test_launcher.py -q
  status: done
---
# Codex Contract Refresh

## Overview

Refresh the version-pinned Codex CLI contract and fixture set so the shipped backend support is grounded in the installed `codex` binary rather than the older captured stream. The current repo contract is pinned to `codex-cli 0.137.0`, while the local installed binary reports `codex-cli 0.142.0`; this plan updates the captured evidence first, then adjusts the parser or manifest only if the new evidence requires it.

## Problem statement

Codex support is fixture-backed, which is the right shape for an MVP, but the fixtures are only as trustworthy as the CLI version they represent. A stale contract can hide stream-schema drift, renamed flags, changed terminal envelopes, or different error-copy shapes until a real operator run fails. The MVP needs the confidence bar to be "works with the installed supported Codex CLI," not "worked with an older captured version."

## Architecture

Step 1 re-runs the existing probe runbook from `docs/CODEX_CLI_CONTRACT.md` in a disposable scratch directory, sanitizes any paths or identifiers, and replaces only the schema-bearing fixture content and version stamp. It should keep the current fixture set unless the new CLI emits a new required event shape; gratuitous recapture churn is out of scope.

Step 2 compares the refreshed fixtures against `plan_tool/backend.py` and `integrations/codex/backend.json`. If the event taxonomy, usage fields, terminal envelope, or argv flags changed, update the Codex parser and manifest with focused tests. If no code change is required, step 2 should make that explicit in the plan status note and still leave the targeted backend tests green.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

- Benchmarking Codex quality or changing backend recommendations.
- Adding new backend-selection policy.
- Optimizing token/cost reporting beyond fields Codex currently emits.

## Risks

- Captured fixtures may accidentally include machine-local paths or account data. Mitigate by following the contract document's sanitization checklist before committing.
- Codex may emit extra informational events that are harmless. The parser should tolerate unknown events instead of overfitting to every line.

## Testing

- `uv run pytest tests/test_backend.py tests/test_launcher.py -q`
- Manual check: `codex --version` in the contract matches the installed binary used to capture the fixtures.
- Manual check: every refreshed `tests/fixtures/codex/*.jsonl` file parses as line-delimited JSON and contains no secrets or real home paths.

## Acceptance criteria

- `docs/CODEX_CLI_CONTRACT.md` records the current captured `codex --version`, capture date, and any changed flag or stream-schema facts.
- Codex fixtures reflect the refreshed contract and remain sanitized.
- Codex stream parser tests pass against the refreshed fixtures.
- `integrations/codex/backend.json` remains byte-faithful to the supported invocation shape.

## Deferred

- A recurring automated contract probe in CI is deferred. MVP only needs a manual recapture procedure and fixtures that match the supported local binary.
