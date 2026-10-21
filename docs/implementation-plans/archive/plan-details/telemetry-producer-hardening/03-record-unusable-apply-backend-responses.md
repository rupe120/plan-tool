> **Auto-archived**: this plan was swept on 2026-07-16 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 3 — Record unusable apply backend responses

## Summary

Add `INVOCATION-FAILED` to the existing `apply-verdict` telemetry vocabulary and attempt it when `plan_tool/launcher.py:apply_finding` cannot use either its primary or auto-fix follow-up backend response. Keep `plan_tool/telemetry.py:record_apply_verdict` as the single recorder and preserve the existing plan slug, step id, anchor, plan fingerprint, and ambient run binding. Map the new token explicitly to `still-open` in `plan_tool/telemetry_analysis.py:resolve_decision_inline` without adding a derived outcome. On green, each failed invocation makes at most one best-effort joinable recording attempt while the original return or exception behavior remains unchanged.

## Table of Contents

- [Summary](#summary) — Reviewer-level overview of the new apply failure signal.
- [Table of Contents](#table-of-contents) — Links to every section in this detail.
- [Why](#why) — Why failed backend calls are missing from apply telemetry.
- [Input](#input) — Existing recorder, launcher, and step 1 contracts this step uses.
- [Files (creates vs edits)](#files-creates-vs-edits) — Scoped source, test, and contract changes.
- [Implementation](#implementation) — Failure classification, event emission, and analysis rules.
- [Tests](#tests) — Focused cases for recording, control flow, mapping, and documentation.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Primary JSON persistence reference.
- [Deferred](#deferred) — Parallel ownership and internal retry work left to later steps.

## Why

`plan_tool/launcher.py:apply_finding` records exit-0 responses after `parse_apply_verdict`, but its non-zero branch returns before `record_apply_verdict`, and a raised invoker exception also leaves without a decision event. A successful response with no recognized token becomes `UNKNOWN`, so reusing that token for backend failure would mix a response-contract violation with an invocation that did not provide a usable response. The missing rows make the `apply-verdict` distribution undercount failed applies even though the same plan, finding, and run join keys are available.

## Input

- **Step 1 output** — step 1 provides the compact telemetry schema and keeps historical rows readable. This step adds a value to an existing context-key vocabulary; it does not change `DecisionEvent` fields or the compact code-state contract.
- **Apply recorder contract** — `plan_tool/telemetry.py:record_apply_verdict` writes `kind=APPLY_VERDICT_KIND`, `decision=APPLY_VERDICT_DECISION`, and `context["verdict"]`, with optional `context["step_id"]` plus base-event `anchor` and `plan_fingerprint`.
- **Primary apply boundary** — `plan_tool/launcher.py:apply_finding` calls its injected `Invoker`, returns an `ApplyFindingResult` for returned backend failures, and lets invocation exceptions propagate.
- **Backend metadata** — `plan_tool.backend.ClaudeRunStats.is_error` can mark a returned response even when the process return code is zero, but `apply_finding` currently accepts and parses that response. Do not classify it as invocation failure unless this step also changes host behavior; preserving host behavior means telemetry follows the accepted parsed verdict.
- **Run association** — `plan_tool/telemetry.py:record_decision` reads the active run id from its existing context binding. Do not add a `run_id` parameter to `apply_finding` or `record_apply_verdict`.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `plan_tool/telemetry.py` — define the `INVOCATION-FAILED` apply-verdict constant and include it in `record_apply_verdict` documentation.
  - `plan_tool/launcher.py` — emit the new verdict once for an unusable primary invocation while preserving `apply_finding` return, restore, reporting, and exception behavior.
  - `plan_tool/telemetry_analysis.py` — map the new apply token explicitly to `OUTCOME_STILL_OPEN`.
  - `tests/test_telemetry.py` — cover the constant and persisted recorder shape.
  - `tests/test_launcher.py` — cover non-zero, raised, and self-reported backend failures, join keys, non-duplication, and best-effort behavior.
  - `tests/test_telemetry_analysis.py` — cover the inline outcome mapping.
  - `tests/test_data_contract.py` — guard the documented apply-verdict vocabulary.
  - `DATA_CONTRACT.md` — document the new token, its meaning, and the paths that emit it.

## Implementation

The foundational logic is: **classify an unusable primary `apply_finding` invocation as `INVOCATION-FAILED` without changing the host result**.

- **Add one stable token.** Define a self-describing constant such as `APPLY_VERDICT_INVOCATION_FAILED = "INVOCATION-FAILED"` beside `APPLY_VERDICT_KIND` and `APPLY_VERDICT_DECISION` in `plan_tool/telemetry.py`. Keep the existing kind, decision, context keys, and schema version; extending an enumerated context value is compatible with older rows.

- **Keep `UNKNOWN` narrow.** Continue using `UNKNOWN` only when `plan_tool/launcher.py:parse_apply_verdict` cannot find a recognized token in an otherwise usable response. Do not reclassify missing verdict text as `INVOCATION-FAILED`.

- **Classify the primary invocation in one place.** In `plan_tool/launcher.py:apply_finding`, treat these primary-call outcomes as unusable for telemetry:
  - the invoker returns a non-zero exit code;
  - the invoker raises before returning a usable response.

  One way to avoid drifting kwargs across these branches is a small local best-effort emitter that always supplies the resolved plan slug, `str(step.id)`, `anchor`, and caller-provided `plan_fingerprint`.

- **Preserve returned-failure behavior.** In the `exit_code != 0` branch of `plan_tool/launcher.py:apply_finding`, make one best-effort `INVOCATION-FAILED` recording attempt, then retain the existing snapshot restoration and `ApplyFindingResult` fields. The result may continue to use its existing `verdict="UNKNOWN"` sentinel; this step changes observational telemetry, not the public result contract.

- **Preserve the raised exception and restore tracked files.** Wrap each direct `invoker(prompt)` boundary closely enough to emit the event and preserve its existing host disposition. For a raised primary invocation, attempt restoration of every tracked path, retaining the original backend exception as the one propagated even if individual restore operations fail. Expose restoration success to step 4's deferred observer: a fully restored invocation failure can be packaged as a selected failure result, while incomplete restoration must propagate as a batch-level abort so canonical replay cannot continue on uncertain state. Do not convert the serial exception into an `ApplyFindingResult` or change reporter behavior.

- **Cover the auto-fix follow-up.** A non-zero or raised follow-up invocation makes its own `INVOCATION-FAILED` attempt with the same finding join keys. Preserve the primary edit and the existing returned-result behavior on a non-zero follow-up. On a raised follow-up, restore only to the snapshot taken immediately before that follow-up, preserving the accepted primary edit, then propagate the original exception. This is a second failed attempt, not a duplicate primary event, and needs no new public verdict or attempt-id field.

- **Keep telemetry aligned with accepted zero-exit responses.** A zero-exit response remains on the ordinary parse/apply path even when `_last_stats.is_error` is set, because the host currently accepts that response. Record the parsed verdict (`APPLIED`, `UNKNOWN`, etc.), not `INVOCATION-FAILED`. Changing that host decision is a separate correctness change and must not be smuggled in as observational telemetry.

- **Guarantee one row from the primary call.** The unusable-response path and the ordinary `parse_apply_verdict` path must be mutually exclusive. A returned `is_error` response must not also emit `UNKNOWN`, `APPLIED`, or another parsed verdict, and a recorder error must not trigger a second recording attempt.

- **Keep joins unchanged.** Send failure events through `plan_tool/telemetry.py:record_apply_verdict`, so `step_id` still participates in `decision_id`, the finding anchor remains a base-event field, `plan_fingerprint` remains caller-supplied, and the active run id is read by `record_decision`. Do not add exit codes, exception text, or backend output to the context bag; run logs remain the detailed failure source.

- **Resolve failure as open work.** Import the new token into `plan_tool/telemetry_analysis.py` and handle it explicitly in `resolve_decision_inline` as `OUTCOME_STILL_OPEN`. A failed invocation neither acted on the finding nor proved it unnecessary, and this plan forbids a fifth derived verdict.

- **Document the distinction.** Update `DATA_CONTRACT.md:Apply verdict` so its vocabulary includes `INVOCATION-FAILED`, `UNKNOWN` remains the exit-0 parse-contract failure, and `INVOCATION-FAILED` covers an unusable primary or auto-fix follow-up backend response. Replace the current claim that non-zero applies emit nothing.

## Tests

- `tests/test_telemetry.py:test_apply_verdict_constants_have_expected_values` — pins `APPLY_VERDICT_INVOCATION_FAILED` to `"INVOCATION-FAILED"`.
- `tests/test_telemetry.py:test_record_invocation_failed_apply_verdict_roundtrips` — records and reads the new token with the existing step and base-event join fields.
- `tests/test_launcher.py:test_apply_finding_nonzero_exit_records_invocation_failed_once` — asserts one failure event while preserving exit code, `ApplyFindingResult`, and snapshot restoration.
- `tests/test_launcher.py:test_apply_finding_invoker_exception_records_once_then_reraises` — asserts the original exception object propagates after one failure event.
- `tests/test_launcher.py:test_apply_finding_invoker_exception_restores_partial_edits` — mutates a tracked plan/detail file before raising and proves the original snapshot is restored before the same exception propagates.
- `tests/test_launcher.py:test_apply_finding_restore_failure_preserves_original_exception` — forces one restore operation to fail, proves every path is attempted, preserves the backend exception, and exposes unsafe restoration to deferred callers.
- `tests/test_launcher.py:test_apply_finding_followup_nonzero_records_invocation_failed_once` — preserves the primary edit/result while recording the failed second invocation.
- `tests/test_launcher.py:test_apply_finding_followup_exception_restores_followup_snapshot_and_reraises` — restores partial follow-up edits without discarding the primary edit and propagates the original follow-up exception.
- `tests/test_launcher.py:test_apply_finding_failure_event_carries_join_keys` — checks plan slug, step id, anchor, plan fingerprint, and active run id.
- `tests/test_launcher.py:test_apply_finding_zero_exit_is_error_matches_accepted_host_verdict` — checks a zero-exit self-reported backend error records the same parsed verdict the host accepts, never a contradictory failure token.
- `tests/test_launcher.py:test_apply_finding_failure_recorder_error_preserves_host_failure` — forces `record_apply_verdict` to raise on both returned and raised failure paths without changing either outcome.
- `tests/test_launcher.py:test_apply_finding_missing_verdict_remains_unknown` — proves an exit-0 response without a token is still `UNKNOWN`, not `INVOCATION-FAILED`.
- `tests/test_launcher.py:test_apply_finding_dry_run_records_nothing` — preserves the no-invocation, no-event rule.
- `tests/test_telemetry_analysis.py:test_apply_verdict_mapping` — adds `INVOCATION-FAILED → OUTCOME_STILL_OPEN` to the existing parameterized mapping.
- `tests/test_data_contract.py:test_apply_verdict_context_keys_documented` — guards the new token within `DATA_CONTRACT.md:Apply verdict` without adding a new context key.

### Test-creation order (feature step)

Add the recorder vocabulary and round-trip test with the new constant, then add launcher tests for each unusable-response path while implementing the producer change. Add the analysis mapping and data-contract drift cases in the same change. Every new test and the existing scoped suites must be green before this step is considered finished.

## Acceptance criteria

- `plan_tool.telemetry.APPLY_VERDICT_INVOCATION_FAILED` equals `"INVOCATION-FAILED"`.
- A primary `apply_finding` invocation that returns non-zero makes at most one best-effort `apply-verdict` attempt with `context["verdict"] == "INVOCATION-FAILED"`.
- Each unusable primary or follow-up invocation makes at most one failure recording attempt.
- A primary invoker exception attempts every tracked restoration and propagates the original exception unchanged; deferred replay may continue only when restoration fully succeeded.
- A raised follow-up restores to its immediate pre-follow-up snapshot, retaining the primary edit, before propagating the original exception.
- A zero-exit primary response, including one with `ClaudeRunStats.is_error`, records the verdict actually accepted by existing `apply_finding` control flow; only non-zero returns and raised invocations use `INVOCATION-FAILED`.
- A usable exit-0 response without a recognized verdict still records `UNKNOWN`.
- Failure events carry the ordinary plan slug, resolved step id, anchor, plan fingerprint, and ambient run id.
- A raising telemetry recorder does not change the returned exit code, snapshot restoration, returned result, or propagated invocation exception.
- `resolve_decision_inline` maps `INVOCATION-FAILED` to `OUTCOME_STILL_OPEN`.
- `DATA_CONTRACT.md:Apply verdict` documents `UNKNOWN`, `INVOCATION-FAILED`, and the zero-exit accepted-response rule without changing the event field schema. This is the declared `DATA_CONTRACT.md` deliverable for step 3.
- The scoped tests in `tests/test_telemetry.py`, `tests/test_launcher.py`, `tests/test_telemetry_analysis.py`, and `tests/test_data_contract.py` pass.

## References

- [Python json — JSON encoder and decoder](https://docs.python.org/3/library/json.html) — Defines the JSON string encoding used when the new verdict token is persisted in decision JSONL.

## Deferred

- **Canonical parallel apply ownership** — step 4 moves durable recording to canonical replay and prevents disposable-worker duplicates.
- **Cross-caller forwarding sweep** — step 5 verifies the apply-loop callers and best-effort wrappers outside this step’s producer change.
- **Retries inside `plan_tool/launcher.py:shell_invoker`** — the recovery loop returns one final primary result to `apply_finding`; recording each internal retry would require attempt-level telemetry and is outside this step.
