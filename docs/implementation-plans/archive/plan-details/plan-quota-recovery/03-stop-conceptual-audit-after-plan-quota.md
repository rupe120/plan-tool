> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 3 — Stop the conceptual audit after a plan-quota outcome and keep coverage unconfirmed

## Summary

Stop `plan_tool/review.py:audit_plan_until_stable` after the first terminal plan-quota outcome from step 2, before it can begin another conceptual audit pass. Carry the early-stop state through `plan_tool/cli/completeness_cmd.py:finalize_completeness_run` and the reporting paths in `plan_tool/cli/completeness_phases.py`. Record actual sampling facts, mark coverage unconfirmed, and withhold the ordinary final findings sidecar. On green, the current audit stops once while a separate invocation starts with no remembered quota state.

## Table of Contents

- [Summary](#summary) — Reviewer overview of the audit stop and reporting result.
- [Table of Contents](#table-of-contents) — Navigation for this detail file.
- [Why](#why) — Why a terminal quota must end conceptual sampling.
- [Input](#input) — The step 2 outcome and existing audit contracts this step consumes.
- [Files (creates vs edits)](#files-creates-vs-edits) — Scoped source, documentation, and test changes.
- [Implementation](#implementation) — Required stop, coverage, persistence, and compatibility behavior.
- [Tests](#tests) — Deterministic coverage for the pass boundary and published result.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Provider behavior relevant to the audit adapter.
- [Applicable guardrails](#applicable-guardrails) — Plan boundaries that constrain this step.
- [Deferred](#deferred) — Work outside the audit-local quota stop.

## Why

`plan_tool/review.py:audit_plan_until_stable` currently treats a nonzero conceptual pass as neutral and can start another pass up to its configured cap. Once step 2 identifies the provider response as a terminal plan quota, another pass cannot recover and can reopen the same provider path. The audit must stop at that known outcome and clearly report that its conceptual coverage is incomplete.

## Input

- **Step 2 terminal outcome:** consume step 2’s classified batch outcome only at the conceptual-audit boundary. Do not classify provider text again from a hint, stderr tail, or rendered message.

- **Audit-pass contract:** `plan_tool/review.py:check_plan_audit`, `_AuditSampleEvidence`, `_make_reporting_invoker`, and `audit_plan_until_stable` together own per-pass parsing, pass accounting, progress reporting, and repeated sampling.

- **Coverage contract:** `plan_tool/review_persistence.py:normalize_audit_coverage`, `project_audit_coverage`, and `audit_coverage_qualifies_sample` supply the coverage facts read by `plan_tool/cli/completeness_phases.py:_conceptual_bar_from_audit_recs`, `_render_completeness_json`, and `_render_coverage_confidence_markdown`.

- **Persistence contract:** `plan_tool/cli/completeness_phases.py:_persist_and_present_report` writes the human-readable report, while `plan_tool/completeness_report.py:is_reusable_audit_sidecar` already excludes a pre-apply checkpoint from reuse.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `DATA_CONTRACT.md` — document the early quota-stop coverage state, its unconfirmed meaning, and final-sidecar behavior.
  - `docs/cli/completeness-audit.md` — explain that a terminal plan quota ends conceptual sampling early and does not confirm coverage.
  - `plan_tool/cli/completeness_cmd.py` — preserve the early-stop coverage result through `finalize_completeness_run`, qualified-result selection, and JSON output.
  - `plan_tool/cli/completeness_phases.py` — use the quota-specific coverage message, keep the conceptual bar incomplete, and write Markdown without an ordinary final findings sidecar.
  - `plan_tool/review.py` — adapt step 2’s typed terminal result at the conceptual-audit seam and stop `audit_plan_until_stable` before another pass starts.
  - `plan_tool/review_persistence.py` — validate, project, and fail closed on the additive early-stop coverage state while keeping older coverage payloads readable.
  - `tests/cli/test_completeness_cmd.py` — cover command reporting, JSON, checkpoints, and final-sidecar suppression.
  - `tests/test_convergence.py` — cover rejection of an early quota stop as reusable audit evidence.
  - `tests/test_data_contract.py` — pin the documented coverage field and legacy compatibility.
  - `tests/test_review.py` — cover the pass boundary, wrapper compatibility, ordinary failures, and invocation isolation.
  - `tests/test_review_persistence.py` — cover normalization and public projection of quota-stopped coverage.

## Implementation

- **Stop only conceptual sampling.** Update `plan_tool/review.py:audit_plan_until_stable` so the first terminal quota outcome ends the current pass loop immediately after that attempted pass. Do not treat it as the ordinary neutral nonzero path that consumes a slot and permits another conceptual provider call.

- **Keep ordinary review tuple-based.** Leave `plan_tool/review.py:shell_review_invoker`, `review_plan_full`, and `extract_and_append_review_lessons` on their existing `(rc, stdout)` contract. Use an audit-only adapter for step 2’s richer outcome, and ensure `check_plan_audit`, `_make_reporting_invoker`, and the loop’s error-tracking wrapper retain the terminal marker until the pass loop reads it.

- **Recognize only the upstream typed signal.** The audit adapter must convert only step 2’s explicit terminal plan-quota classification into the stop signal. Do not add another regex, inspect raw response text, or broaden ordinary nonzero behavior.

- **Record an explicit early-stop coverage state.** Extend `plan_tool/review_persistence.py:_AUDIT_COVERAGE_KEYS` and its coverage helpers with a documented early-stop reason for a plan quota. The quota case must retain the attempted-pass count and configured cap, report no confirmation, and remain distinct from `budget_limited`: it stopped for a terminal provider result, not because it reached the pass cap.

- **Keep coverage fail-closed.** `audit_coverage_qualifies_sample` must reject the explicit quota-stop state regardless of otherwise plausible counters. `plan_tool/cli/completeness_phases.py:_conceptual_bar_from_audit_recs` and `plan_tool/cli/completeness_cmd.py:classify_qualified_audit_result` must therefore produce unconfirmed coverage, `audit_incomplete=True`, and no conceptual-bar blocker list or clean qualified result.

- **Preserve legacy coverage.** Existing saved coverage payloads without the new field must continue to normalize and project as their current meaning, not become malformed or gain an invented quota reason.

- **Report the real reason.** Update `emit_coverage_unconfirmed`, `_render_coverage_confidence_markdown`, and `_render_completeness_json` so a quota stop says sampling ended early after a terminal plan quota. Do not reuse the pass-cap wording or claim that the conceptual audit converged.

- **Keep the Markdown evidence but withhold the final reusable sidecar.** The non-JSON report must still be written for operators, but its final ordinary `-completeness.json` findings sidecar and associated final findings payload must not be written. Do not reuse `skip_sidecar_write` for this: that path suppresses the Markdown report too.

- **Preserve checkpoint semantics.** Under `--iterate`, retain the existing pre-apply checkpoint behavior if reached; its existing checkpoint role keeps it nonreusable. The quota rule applies to the ordinary final sidecar, not to unrelated deterministic-loop recovery evidence.

- **Keep the scope local.** Do not change audit-pass defaults, timeout budgets, purity behavior, normal short-rate-limit recovery, or the deterministic `--iterate` finding loop. A later command invocation must make its own first conceptual call without a quota cache or replay state.

## Tests

### Tests for this step

- `tests/test_review.py:test_plan_quota_stops_conceptual_sampling_after_terminal_pass` — asserts a terminal quota prevents every later conceptual-pass provider call.
- `tests/test_review.py:test_plan_audit_adapter_preserves_terminal_signal_through_wrappers` — asserts progress and error wrappers do not discard the audit-only terminal marker.
- `tests/test_review.py:test_standard_review_invoker_remains_tuple_based` — asserts ordinary review callers retain their existing invocation contract.
- `tests/test_review.py:test_plan_quota_coverage_uses_actual_pass_count` — asserts coverage records attempted passes, the configured cap, no confirmation, and the terminal stop reason.
- `tests/test_review.py:test_nonquota_failed_pass_remains_neutral` — asserts ordinary nonzero and exception paths retain their current pass-budget behavior.
- `tests/test_review.py:test_plan_quota_state_does_not_cross_audit_invocations` — asserts a later audit starts its own provider call.
- `tests/test_review_persistence.py:test_plan_quota_coverage_normalizes_and_projects` — asserts the explicit early-stop coverage shape is valid and publicly visible.
- `tests/test_review_persistence.py:test_legacy_coverage_without_early_stop_reason_remains_valid` — asserts older saved coverage retains its current meaning.
- `tests/test_convergence.py:test_audit_coverage_qualifies_sample_rejects_plan_quota_stop` — asserts an early quota stop never qualifies as reusable evidence.
- `tests/test_data_contract.py:test_data_contract_documents_plan_quota_coverage_stop` — asserts the documented field, unconfirmed result, and final-sidecar rule remain present.
- `tests/cli/test_completeness_cmd.py:test_plan_quota_json_reports_unconfirmed_early_stop` — asserts JSON distinguishes the quota reason from a budget-limited pass-cap result and omits conceptual-bar blocker ids.
- `tests/cli/test_completeness_cmd.py:test_plan_quota_markdown_report_omits_final_reusable_sidecar` — asserts the operator report is written without an ordinary final findings sidecar.
- `tests/cli/test_completeness_cmd.py:test_iterate_plan_quota_keeps_checkpoint_nonreusable` — asserts an existing pre-apply checkpoint remains marked as recovery-only while no final reusable sidecar is created.

Every listed test must be green before this step is complete, along with `uv run pytest tests/ -q -n auto`.

## Acceptance criteria

- The first terminal plan-quota outcome prevents every later conceptual-pass provider call in that audit invocation.
- The early-stop coverage records the actual attempted-pass count and configured cap, names the terminal quota reason, and does not report a pass-cap stop.
- A quota-stopped audit has unconfirmed coverage, `audit_incomplete=True`, no conceptual-bar blocker ids, and no clean qualified result.
- Ordinary non-quota invoker failures retain their current neutral-pass behavior.
- A non-JSON quota-stopped audit writes a readable Markdown report but no ordinary final reusable findings sidecar.
- An `--iterate` checkpoint, when written, remains explicitly recovery-only and cannot be selected for reuse.
- Older coverage payloads remain readable without an invented early-stop reason.
- A separate completeness-audit invocation does not inherit quota state from an earlier one.

## References

- [Output format | Cursor Docshttps: — Use this to confirm how a terminal CLI failure reaches the batch audit adapter.
- [Models & Pricing | Cursor Docshttps: — Use this to keep the terminal condition tied to monthly usage exhaustion rather than a short retry window.

## Applicable guardrails

- **The plan’s `## Architecture`, audit-local stop:** stop later conceptual passes only; do not cache, compare, or replay quota evidence.

- **The plan’s `## Out of scope`, unchanged recovery and scheduling:** leave ordinary rate-limit behavior, audit-pass configuration, purity behavior, time budgets, and external-backend testing outside this step.

- **The plan’s `## Risks`, false special case and state leak:** trust only step 2’s terminal classification and keep the result scoped to one audit invocation.

## Deferred

- Provider quota wording without step 1’s confirmed markers — route through the plan’s existing deferred-work process rather than broadening this audit rule.
- Persistent quota coordination across commands — remains outside this audit-local stop behavior.
