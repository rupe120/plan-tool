> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 1 — Add provider-scoped plan-quota detection and date-only reset context

## Summary

Cursor-specific evidence for monthly plan-quota exhaustion lives in the backend descriptor and manifest. `plan_tool/claude_errors.py:classify` returns `ClaudeFailureKind.PLAN_QUOTA` for that confirmed evidence and preserves the provider’s reset date as date-only context. The terminal category distinguishes the quota message from ordinary rate-limit text without parsing a date into a local instant.

## Table of Contents

- [Summary](#summary) — Reviewer overview of the new detection inputs.
- [Table of Contents](#table-of-contents) — Navigation for this detail file.
- [Why](#why) — The current classification and date-only contract.
- [Input](#input) — Existing backend and failure contracts this step extends.
- [Files (creates vs edits)](#files-creates-vs-edits) — Declared files and their scoped changes.
- [Implementation](#implementation) — Required behavior, boundaries, and recommended approach.
- [Tests](#tests) — Deterministic coverage for the new inputs.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Provider and Python date references.
- [Applicable guardrails](#applicable-guardrails) — Plan boundaries that constrain this step.
- [Deferred](#deferred) — Provider variants deliberately left for future work.

## Why

`plan_tool/claude_errors.py:classify` recognizes Cursor’s confirmed monthly quota message separately from ordinary rate limits, while `parse_reset_epoch` remains limited to time-bearing reset messages. The monthly-cycle date stays date-only operator context and the terminal category gives the recovery layer a reliable distinction from a short limit.

## Input

- **Backend classification contract:** `plan_tool/backend.py:CliBackend`, `load_backend_from_dir`, and `_REQUIRED_CLASSIFICATION_KEYS` load regexes from each backend manifest. The new plan-quota signal must be optional so the existing Claude, Codex, generic, and test backends retain no special quota behavior.
- **Failure result contract:** `plan_tool/claude_errors.py:ClaudeFailure` carries `kind`, `reset_epoch`, `hint`, and plan-quota date-only context. The epoch field retains its time-bearing short-limit meaning.
- **Classification ordering:** `plan_tool/claude_errors.py:classify` combines stdout and stderr, then gives rate-limit copy precedence over auth, context overflow, and transient failures. Preserve that order while attaching the new metadata.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `integrations/cursor/backend.json` — add only Cursor’s confirmed monthly plan-quota detection pattern.
  - `plan_tool/backend.py` — extend `CliBackend`, `CURSOR_BACKEND`, and `load_backend_from_dir` to carry an optional provider-scoped plan-quota pattern.
  - `plan_tool/claude_errors.py` — extract the confirmed monthly-cycle date as date-only context and attach both new inputs during classification.
  - `tests/test_backend.py` — cover Cursor’s manifest-backed pattern and optional-pattern round-trip behavior.
  - `tests/test_claude_errors.py` — cover classification metadata and date-only extraction.

## Implementation

- **Keep plan-quota detection provider-scoped.** Add an optional plan-quota pattern to `plan_tool/backend.py:CliBackend` and populate it only for `CURSOR_BACKEND` and `integrations/cursor/backend.json`. The Cursor pattern must require the confirmed plan-level markers from the observed error, not generic phrases such as `usage limit`.

- **Keep the manifest field optional.** Update `plan_tool/backend.py:load_backend_from_dir` to compile the new classification field when supplied and leave it absent for other manifests. Do not add it to `_REQUIRED_CLASSIFICATION_KEYS`: requiring it would expand this step beyond Cursor and force unrelated manifest edits.

- **Keep literal and manifest descriptors aligned.** `CURSOR_BACKEND` and the descriptor loaded from `integrations/cursor/backend.json` must expose the same plan-quota pattern. Extend the pattern-value checks around `_PATTERN_FIELDS` so they correctly compare both present patterns and absent optional patterns.

- **Classify the confirmed terminal outcome.** `plan_tool/claude_errors.py:classify` identifies the plan-quota signal from combined stdout and stderr, returns `ClaudeFailureKind.PLAN_QUOTA`, and attaches the extracted date-only context. Step 2 consumes its terminal category in the shared recovery callers.

- **Keep the reset date date-only.** Add a narrow helper near `parse_reset_epoch` that recognizes the Cursor monthly-cycle date format and returns a date-only value. Do not convert it to an epoch, add a time, infer a timezone, or feed it into `parse_reset_epoch`; that function remains the contract for time-bearing short-limit resets.

- **Preserve generic rate-limit behavior.** A Cursor error that says only `usage limit`, `rate limit`, or another existing short-limit phrase must stay on the current rate-limit path with no plan-quota evidence. The plan-quota pattern must not broaden the shared `_CLAUDE_RATE_LIMIT_PATTERN` or `_CLAUDE_PROVIDER_LIMIT_PATTERN`.

- **Keep the category boundary shared.** `plan_tool/claude_errors.py:KIND_TO_CATEGORY` maps the confirmed quota to the existing terminal recovery category. The recovery callers consume that category without adding provider-specific branching.

## Tests

### Tests for this step

- `tests/test_backend.py:test_cursor_plan_quota_pattern_matches_confirmed_monthly_quota_copy` — asserts the Cursor-only pattern recognizes the confirmed monthly-quota markers.
- `tests/test_backend.py:test_cursor_manifest_plan_quota_pattern_round_trips` — asserts `load_backend_from_dir` preserves Cursor’s configured plan-quota pattern.
- `tests/test_backend.py:test_non_cursor_backends_have_no_plan_quota_pattern` — asserts the optional field does not create a special case for Claude, Codex, generic, or fake backends.
- `tests/test_claude_errors.py:test_classify_cursor_monthly_plan_quota_returns_plan_quota` — asserts the observed Cursor message produces terminal plan-quota classification and its stated date-only context.
- `tests/test_claude_errors.py:test_classify_cursor_plan_quota_does_not_invent_reset_epoch` — asserts a date-only monthly-cycle message leaves `reset_epoch` unset.
- `tests/test_claude_errors.py:test_classify_generic_usage_limit_is_not_plan_quota` — asserts generic usage-limit copy stays on the existing rate-limit path without plan-quota metadata.
- `tests/test_claude_errors.py:test_plan_quota_reset_date_rejects_invalid_calendar_date` — asserts malformed date text yields no date context and does not raise.

Every listed test must be green before this step is complete, along with `uv run pytest tests/ -q -n auto`.

## Acceptance criteria

- `integrations/cursor/backend.json` supplies a Cursor-only pattern for the confirmed monthly plan-quota message, and `plan_tool/backend.py:load_backend_from_dir` exposes it on the loaded descriptor.
- Under `CURSOR_BACKEND`, `plan_tool/claude_errors.py:classify` returns `ClaudeFailureKind.PLAN_QUOTA` and a date-only reset value for the confirmed monthly-cycle error.
- A date-only monthly-cycle message does not produce or alter `ClaudeFailure.reset_epoch`.
- Generic usage-limit and short-rate-limit messages retain their current `ClaudeFailureKind.RATE_LIMIT` behavior without plan-quota metadata.
- The changed tests in `tests/test_backend.py` and `tests/test_claude_errors.py` pass.

## References

- [Models & Pricing | Cursor Docshttps: — Confirm the monthly usage-pool and billing-cycle terminology behind the provider-specific signal.
- [Output format | Cursor Docshttps: — Confirm how Cursor CLI failures reach stdout and stderr.
- [datetime — Basic date and time typeshttps: — Use a date-only representation without creating a local reset instant.

## Applicable guardrails

- **The plan’s “## Step intent”, date-only reset context:** preserve the provider’s stated date as deterministic context only; this step must not turn it into a wait target.
- **The plan’s “## Out of scope”, unchanged short-rate-limit behavior:** do not alter generic rate-limit, prompt, switch, wait, or transient-retry behavior.
- **The plan’s “## Out of scope”, no shared quota state:** do not add quota caches, account lookups, forecasting, or cross-command coordination.
- **The plan’s “## Out of scope”, no broader policy change:** keep audit scheduling, timeout policy, and external-backend testing outside this plan.

## Deferred

- **Other provider-specific quota messages without the confirmed Cursor markers** — retain the plan’s deferred follow-up route instead of broadening this detector.
