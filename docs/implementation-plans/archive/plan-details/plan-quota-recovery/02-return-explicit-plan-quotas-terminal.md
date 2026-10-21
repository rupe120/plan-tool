> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 2 — Return explicit plan quotas as terminal outcomes in batch and streaming recovery

## Summary

Turn the provider-scoped plan-quota evidence from step 1 into a distinct terminal `ClaudeFailureKind` in `plan_tool/claude_errors.py`. Route that outcome through the existing terminal branch of `plan_tool/rate_limit_loop.py:run_with_rate_limit_recovery` so neither `plan_tool/shell.py:claude_invoke` nor `plan_tool/launcher.py:shell_invoker` waits, prompts, switches backend, or retries it. Keep those ordinary callers’ `(rc, stdout)` contract and short-rate-limit behavior unchanged, while adding one review-only batch outcome that retains the final classified failure for step 3. On green, both recovery lanes return the failed attempt after a clear date-only quota message.

## Table of Contents

- [Summary](#summary) — Reviewer overview of the terminal quota behavior.
- [Table of Contents](#table-of-contents) — Navigation for this detail file.
- [Why](#why) — The recovery loop currently treats monthly quotas like short limits.
- [Input](#input) — The step 1 classifier evidence and shared recovery contracts this step consumes.
- [Files (creates vs edits)](#files-creates-vs-edits) — Scoped source and test updates.
- [Implementation](#implementation) — Terminal-outcome rules for both recovery lanes.
- [Tests](#tests) — Deterministic coverage for classification and recovery bypasses.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Provider and protocol guidance relevant to recovery behavior.
- [Applicable guardrails](#applicable-guardrails) — Plan boundaries that keep this change narrow.
- [Deferred](#deferred) — Provider variants outside the confirmed evidence.

## Why

`plan_tool/claude_errors.py:classify` currently supplies `RATE_LIMIT` to `plan_tool/rate_limit_loop.py:run_with_rate_limit_recovery`, whose rate-limit branch can wait, prompt, switch backend, and retry. Step 1 makes a confirmed monthly quota distinguishable, so this step must stop that signal before it reaches any of those recovery actions while leaving ordinary short limits on their current path.

## Input

- **Step 1 outcome:** step 1 adds provider-scoped plan-quota evidence and date-only reset context to `plan_tool/claude_errors.py:ClaudeFailure`. This step consumes that evidence; it does not redefine the provider pattern or convert the date into an epoch.
- **Shared classification contract:** `plan_tool/claude_errors.py:build_classification`, `KIND_TO_CATEGORY`, and `plan_tool/rate_limit_loop.py:AttemptClassification` carry a caller-owned failure into the shared leaf.
- **Caller contract:** `plan_tool/shell.py:claude_invoke` and `plan_tool/launcher.py:shell_invoker` return `(rc, stdout)`. Keep that public shape unchanged. `plan_tool/shell.py` will additionally expose a review-only outcome carrying the final `ClaudeFailure`; only step 3's adapter consumes it.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `plan_tool/claude_errors.py` — add the explicit plan-quota failure kind, classify step 1 evidence into it, and map it to the existing terminal recovery category with a date-only user hint.
  - `plan_tool/rate_limit_loop.py` — keep `AttemptCategory.TERMINAL` as the shared, caller-neutral terminal path and make its contract clear for the new outcome.
  - `plan_tool/launcher.py` — keep `shell_invoker` on the shared streaming classification path; add coverage that no streaming recovery action starts for a plan quota.
  - `plan_tool/shell.py` — keep `claude_invoke` on the shared batch classification path and add an additive `ClaudeInvokeOutcome` helper for review-only consumers; add coverage that no batch recovery action starts for a plan quota.
  - `tests/test_claude_errors.py` — update classifier and mapping expectations for the new failure kind.
  - `tests/test_rate_limit_loop.py` — cover the terminal branch’s no-recovery behavior.
  - `tests/test_launcher.py` — cover terminal plan-quota handling through `shell_invoker`.
  - `tests/test_shell.py` — cover terminal plan-quota handling through `claude_invoke`.

## Implementation

- **Use an explicit failure kind.** Have `plan_tool/claude_errors.py:classify` return `ClaudeFailureKind.PLAN_QUOTA` only when it receives step 1’s confirmed plan-quota evidence. Generic `usage limit` and ordinary short-limit messages must remain `ClaudeFailureKind.RATE_LIMIT`.

- **Keep the shared leaf neutral.** Let `plan_tool/claude_errors.py:KIND_TO_CATEGORY` and `build_classification` route `PLAN_QUOTA` to the existing `AttemptCategory.TERMINAL` result. Do not add provider-specific logic or a plan-quota-specific category to `plan_tool/rate_limit_loop.py`.

- **Make terminal mean no recovery action.** In `plan_tool/rate_limit_loop.py:run_with_rate_limit_recovery`, a plan-quota classification must return the original failed `(rc, payload)` after surfacing its hint. It must not call the wait seam, prompt seam, backend-selection seam, sleep seam, retry guard, or a second `run_once`.

- **Preserve the operator context.** Build the terminal hint through `plan_tool/claude_errors.py:format_user_hint` so it identifies a plan quota and retains step 1’s reset date as date-only context. Do not populate `reset_epoch`, display an invented reset time, or direct the shared wait path to that date.

- **Keep both callers aligned through the shared seam.** `plan_tool/shell.py:claude_invoke` must continue using `build_classification_from_outcome`, and `plan_tool/launcher.py:shell_invoker` must continue using `build_streaming_classification_from_outcome`. One way to keep this safe is to test each caller with the same confirmed plan-quota fixture and distinct policy settings rather than adding caller-specific detection.

- **Expose the final batch classification without changing the tuple API.** Factor the batch path through an additive `ClaudeInvokeOutcome` with `rc`, `stdout`, and the final classified `ClaudeFailure` (or no failure on success). `claude_invoke` projects that outcome back to its existing tuple, while the review adapter in step 3 uses the richer helper. The final classification comes from the recovery loop's existing classifier at the completed attempt; do not re-parse output or preserve an earlier recoverable failure after a successful retry.

- **Preserve normal policy behavior.** Existing `RATE_LIMIT` handling must still honor `WAIT`, `ASK`, `SWITCH`, fallback waiting, and the one-retry limit. Keep `TRANSIENT`, timeout, auth, context-overflow, and unknown-nonzero behavior unchanged.

- **Leave audit-loop control to step 3.** This step produces the typed terminal recovery outcome. It must not alter `plan_tool/review.py`, conceptual-pass counts, persistent state, or audit scheduling.

## Tests

### Tests for this step

- `tests/test_claude_errors.py:test_classify_cursor_monthly_plan_quota_returns_plan_quota` — asserts confirmed step 1 evidence produces `ClaudeFailureKind.PLAN_QUOTA`, not `RATE_LIMIT`.
- `tests/test_claude_errors.py:test_plan_quota_maps_to_terminal_recovery_category` — asserts batch and streaming classification builders produce `AttemptCategory.TERMINAL` while retaining the failure object.
- `tests/test_claude_errors.py:test_plan_quota_hint_preserves_date_only_context` — asserts the terminal hint includes the stated monthly date without an epoch or invented time.
- `tests/test_claude_errors.py:test_generic_usage_limit_remains_rate_limit` — asserts generic usage-limit copy remains recoverable and carries no plan-quota outcome.
- `tests/test_rate_limit_loop.py:test_terminal_plan_quota_bypasses_wait_prompt_switch_retry_and_guard` — asserts the terminal branch performs one attempt and calls none of the recovery seams.
- `tests/test_shell.py:test_claude_invoke_plan_quota_bypasses_every_rate_limit_policy_action` — parametrizes wait, ask, and switch policy settings and asserts batch invocation does not sleep, prompt, select a backend, or spawn a retry.
- `tests/test_shell.py:test_claude_invoke_outcome_retains_final_plan_quota_failure` — asserts the additive batch helper exposes `PLAN_QUOTA` from the final classification while `claude_invoke` still returns the identical two-item tuple.
- `tests/test_launcher.py:test_shell_invoker_plan_quota_bypasses_every_rate_limit_policy_action` — parametrizes the same policies and asserts streaming invocation does not wait, prompt, switch, or make a second backend call.
- `tests/test_shell.py:test_claude_invoke_waits_then_retries_on_rate_limit` and `tests/test_launcher.py:test_shell_invoker_waits_then_retries_on_rate_limit` — retain the ordinary short-rate-limit regression path.

Every listed test must be green before this step is complete, along with `uv run pytest tests/ -q -n auto`.

## Acceptance criteria

- A confirmed plan-quota failure returns `ClaudeFailureKind.PLAN_QUOTA` and an `AttemptCategory.TERMINAL` classification.
- A plan quota returns the original failed result after one backend attempt in both batch and streaming recovery.
- Under wait, ask, and switch policies, a plan quota does not wait, prompt, select a fallback backend, sleep for backoff, consult the retry guard, or retry.
- The terminal message identifies the quota and preserves any monthly reset date as date-only context.
- The review-only batch outcome carries the final classified plan quota without changing `claude_invoke`'s `(rc, stdout)` API or reclassifying output text.
- Generic usage-limit and short-rate-limit fixtures remain `RATE_LIMIT` and retain their existing recovery-policy behavior.
- The changed tests in `tests/test_claude_errors.py`, `tests/test_rate_limit_loop.py`, `tests/test_launcher.py`, and `tests/test_shell.py` pass.

## References

- [Models & Pricing | Cursor Docshttps: — Confirm that the detected provider condition is a monthly usage-pool limit rather than a short retry window.
- [Output format | Cursor Docshttps: — Check where nonzero CLI failure text is delivered for both caller paths.
- [Cursor Python SDK — Errorshttps: — Review retryability guidance for usage-limit and rate-limit failures.
- [RFC 6585 — HTTP 429https: — Distinguish ordinary rate-limit semantics from the terminal provider-specific quota outcome.

## Applicable guardrails

- **The plan’s “## Step intent”, terminal recovery bypass:** apply the terminal result before the shared loop can enter wait, prompt, switch, or retry behavior in either caller.
- **The plan’s “## Out of scope”, unchanged short-rate-limit behavior:** leave ordinary rate-limit and transient policy behavior unchanged.
- **The plan’s “## Out of scope”, no shared quota state:** do not add a quota cache, account lookup, forecast, or cross-command coordination.
- **The plan’s “## Out of scope”, audit scheduling:** the terminal outcome has audit-local handling in `plan_tool/review.py`; do not expand it into scheduler or timeout policy.

## Deferred

- **Unconfirmed provider quota wording** — keep it outside this step until it has explicit provider-scoped evidence.
