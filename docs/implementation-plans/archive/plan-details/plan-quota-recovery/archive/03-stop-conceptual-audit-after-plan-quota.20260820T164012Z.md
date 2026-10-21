> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 3 — Stop the conceptual audit after a plan-quota outcome and keep coverage unconfirmed

## Summary

Stop `plan_tool/review.py:audit_plan_until_stable` after the first terminal plan-quota result from step 2, before it starts another conceptual pass. Carry that incomplete outcome through `plan_tool/cli/completeness_cmd.py:finalize_completeness_run` and the presentation helpers in `plan_tool/cli/completeness_phases.py`. Keep the actual pass count visible, mark the audit incomplete, and avoid saving it as a normal reusable completeness sidecar. On green, a quota ends this audit’s conceptual sampling once; a separate invocation has no remembered quota state.

## Table of Contents

- [Summary](#summary) — Reviewer overview of the quota-stop behavior.
- [Table of Contents](#table-of-contents) — Navigation for this detail file.
- [Why](#why) — The repeated-pass recovery cost this step removes.
- [Input](#input) — The terminal quota result supplied by step 2.
- [Files (creates vs edits)](#files-creates-vs-edits) — Scoped source, documentation, and test updates.
- [Implementation](#implementation) — Required stop, coverage, and persistence behavior.
- [Tests](#tests) — Deterministic coverage for the pass boundary and reported result.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Provider output guidance relevant to the audit adapter.
- [Applicable guardrails](#applicable-guardrails) — Plan boundaries that keep the change narrow.
- [Deferred](#deferred) — Quota work outside this audit-local stop rule.

## Why

`plan_tool/review.py:audit_plan_until_stable` treats a nonzero conceptual pass as neutral and can start another pass up to its configured cap. After step 2 identifies a monthly plan quota as terminal, repeating those passes cannot recover and can reopen the same provider recovery path. The audit must stop at that first known terminal outcome while making clear that its conceptual coverage is incomplete rather than converged.

## Input

- **Step 2 outcome:** step 2 supplies an additive batch outcome containing the final `ClaudeFailure`, while ordinary callers keep their `(rc, stdout)` result. Convert only `ClaudeFailureKind.PLAN_QUOTA` into the typed audit signal; do not infer quota status again from a rendered hint or raw output text.

- **Audit-pass contract:** `plan_tool/review.py:check_plan_audit` remains the per-pass parser and `plan_tool/review.py:audit_plan_until_stable` owns repeated conceptual passes, carried findings, and coverage facts.

- **Coverage and persistence contract:** `plan_tool/cli/completeness_cmd.py:finalize_completeness_run` passes coverage into `plan_tool/cli/completeness_phases.py:_render_completeness_json` and `_persist_and_present_report`. The coverage contract will carry an explicit early-stop reason so a quota stop is unconfirmed without being mislabeled budget-limited; it is presentation-only because the stopped run writes no reusable sidecar.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `DATA_CONTRACT.md` — document the JSON coverage early-stop reason, its unconfirmed/incomplete meaning, and the absence of a reusable sidecar for quota-stopped sampling.
  - `docs/cli/completeness-audit.md` — document that a terminal plan quota stops conceptual passes early and leaves coverage unconfirmed.
  - `plan_tool/cli/completeness_cmd.py` — preserve the quota-stopped coverage result through `finalize_completeness_run`, JSON output, and final report selection.
  - `plan_tool/cli/completeness_phases.py` — render an accurate unconfirmed-coverage message and persist the Markdown report without treating the stopped audit as reusable evidence.
  - `plan_tool/review.py` — carry step 2’s terminal outcome into `check_plan_audit` and stop `audit_plan_until_stable` before another provider pass starts.
  - `plan_tool/review_persistence.py` — own the additive coverage state, backward-compatible normalization/projection, and the reuse rejection for a quota-stopped audit.
  - `tests/cli/test_completeness_cmd.py` — cover command-level reporting, JSON, and report persistence for a quota-stopped audit.
  - `tests/test_convergence.py` — prove a quota-stopped coverage payload cannot qualify as a reusable audit sample.
  - `tests/test_data_contract.py` — pin the documented coverage field, valid quota-stop shape, and legacy shape compatibility.
  - `tests/test_review.py` — cover the audit-pass stop condition, normal error behavior, and invocation isolation.
  - `tests/test_review_persistence.py` — cover normalization and public projection of the explicit quota-stop state.

## Implementation

- **Stop the conceptual pass loop on the first terminal quota.** Update `plan_tool/review.py:audit_plan_until_stable` so a plan-quota result from step 2 ends its current loop immediately after the failed pass. Do not classify it as an ordinary neutral nonzero result that consumes one slot and permits a later pass.

- **Keep the signal typed through one compatibility boundary.** Add a frozen `ReviewInvocationOutcome` with `rc`, `stdout`, and nullable `failure_kind`, and let `Invoker` accept either it or the existing `(rc, stdout)` tuple. `shell_review_invoker` maps step 2's final classified failure into this outcome; injected test invokers remain tuples and normalize to no failure kind. `_make_reporting_invoker` preserves the original outcome after reading its `rc` and `stdout` for progress, while `check_plan_audit` normalizes once and recognizes only `ClaudeFailureKind.PLAN_QUOTA`. Do not add a second provider classifier or inspect rendered text.

- **Make persistence own the coverage state.** Extend `plan_tool/review_persistence.py`'s coverage keys, `normalize_audit_coverage`, `project_audit_coverage`, and `audit_coverage_qualifies_sample` with `early_stop_reason: "plan_quota" | null`. On the quota path record the passes actually attempted and configured cap, set `early_stop_reason` to `plan_quota`, leave `budget_limited` false, and leave `confirmation_kind` null. The normalizer accepts the legacy closed shape as an implicit null early-stop reason, but `audit_coverage_qualifies_sample` rejects the explicit quota-stop state even if its sole pass conformed. Mark the result incomplete and unconfirmed, with no clean confirmation or conceptual-bar blocker set. Quota-stopped runs do not persist a reusable sidecar. Do not invent skipped passes, relabel the stop as convergence, or claim the audit reached its normal pass cap.

- **Keep terminal quota separate from ordinary failures.** A non-quota invoker exception or nonzero result must retain `audit_plan_until_stable`’s current neutral-pass behavior. The new early stop applies only to the explicit terminal quota outcome from step 2.

- **Do not save a quota stop as reusable audit evidence.** `plan_tool/cli/completeness_cmd.py:finalize_completeness_run` and `plan_tool/cli/completeness_phases.py:_persist_and_present_report` must still produce the human-readable report, but must withhold the normal completeness findings sidecar and its data-contract payload for an early quota outcome. That prevents later reuse or apply from treating stopped sampling as qualified.

- **Make presentation state the real reason.** Update `plan_tool/cli/completeness_phases.py:emit_coverage_unconfirmed`, `_render_coverage_confidence_markdown`, `_render_completeness_json`, and the qualified-result calculation so terminal quota output says coverage is unconfirmed because sampling stopped early, not because it kept discovering findings at a cap. `audit_coverage_qualifies_sample` must reject the explicit early-stop state. Preserve `audit_incomplete=True`, null conceptual-bar blocker ids, and the existing `--fail-on-findings` incomplete-audit gate.

- **Keep the boundary local to conceptual sampling.** Do not change the configured pass counts, general retry policy, purity pass behavior, or deterministic `--iterate` finding loop. The rule only prevents later calls in the conceptual-pass sequence.

- **Avoid cross-invocation state.** Keep any terminal marker scoped to one call of `audit_plan_until_stable`. Do not add a quota cache, comparison logic, or replay behavior; the next invocation evaluates its own first conceptual pass under its normal settings.

## Tests

### Tests for this step

- `tests/test_review.py:test_plan_quota_stops_conceptual_audit_after_first_pass` — injects a terminal plan-quota outcome with multiple passes configured and asserts no second provider call occurs.
- `tests/test_review.py:test_shell_review_invoker_preserves_typed_plan_quota_outcome` — asserts the production review adapter carries the final classified failure while tuple test invokers remain supported.
- `tests/test_review.py:test_plan_quota_reports_actual_pass_count_and_unconfirmed_coverage` — asserts the early stop records the attempted pass count, retains the configured cap, and has no convergence confirmation.
- `tests/test_review.py:test_non_quota_nonzero_pass_remains_neutral` — asserts ordinary failed passes retain the current retry-through-the-pass-budget behavior.
- `tests/test_review.py:test_plan_quota_state_does_not_leak_to_next_audit` — runs two audit invocations and asserts the second receives its own provider call.
- `tests/test_review_persistence.py:test_plan_quota_coverage_projects_and_rejects_reuse` — asserts the additive state projects publicly, legacy coverage stays readable, and explicit plan-quota coverage cannot qualify for reuse.
- `tests/test_data_contract.py:test_plan_quota_early_stop_coverage_contract_is_documented` — asserts the data-contract documentation names the field, unconfirmed state, and no-sidecar rule.
- `tests/test_convergence.py:test_audit_coverage_qualifies_sample_rejects_plan_quota_stop` — asserts the reused-audit predicate rejects the terminal state even when the attempted pass parsed successfully.
- `tests/cli/test_completeness_cmd.py:test_plan_quota_audit_renders_coverage_unconfirmed` — asserts the command reports the terminal quota and visibly incomplete coverage without claiming cap-based convergence.
- `tests/cli/test_completeness_cmd.py:test_plan_quota_audit_json_marks_result_incomplete` — asserts JSON exposes `audit_incomplete`, omits conceptual-bar blocker ids, and preserves the early-stop coverage facts.
- `tests/cli/test_completeness_cmd.py:test_plan_quota_audit_json_names_early_stop_reason` — asserts `early_stop_reason` is `plan_quota`, `budget_limited` is false, and the output is still unconfirmed.
- `tests/cli/test_completeness_cmd.py:test_plan_quota_audit_writes_markdown_without_reusable_sidecar` — asserts the report remains available to the operator while no normal `-completeness.json` findings sidecar is created.
- `tests/cli/test_completeness_cmd.py:test_iterate_plan_quota_keeps_conceptual_bar_unconfirmed` — asserts the iterate path carries the same incomplete conceptual result without starting another conceptual pass.

Every listed test must be green before this step is complete, along with `uv run pytest tests/ -q -n auto`.

## Acceptance criteria

- A terminal plan quota on the first conceptual pass prevents every later conceptual-pass provider call in that invocation.
- The audit result reports coverage as unconfirmed, `audit_incomplete` is true, and no clean or converged result is emitted.
- The early quota result exposes `early_stop_reason: "plan_quota"`, not a cap-based `budget_limited` verdict, and tuple-based injected invokers remain compatible.
- The reported pass count reflects calls actually made; it does not fabricate skipped passes or claim the configured cap was reached.
- A quota-stopped audit writes an operator-readable report but no normal reusable completeness findings sidecar.
- The persistence contract projects `early_stop_reason: "plan_quota"`, keeps earlier coverage sidecars readable, and rejects the explicit quota-stop state for reuse.
- Ordinary non-quota failures retain their current multi-pass behavior.
- A separate audit invocation has no remembered quota outcome from an earlier invocation.
- The changed tests in `tests/test_review.py` and `tests/cli/test_completeness_cmd.py` pass.

## References

- [Output format | Cursor Docs](https://cursor.com/docs/cli/reference/output-format) — Confirm how terminal CLI failures reach the review invoker before adapting the typed outcome handoff.
- [Models & Pricing | Cursor Docs](https://cursor.com/docs/models-and-pricing#usage-pools) — Confirm the provider condition remains a monthly usage-pool exhaustion, not a short retry window.

## Applicable guardrails

- **The plan’s “## Step intent”, conceptual-pass boundary:** stop only later conceptual-pass calls and leave the failed audit visibly incomplete.

- **The plan’s “## Out of scope”, unchanged audit policy:** do not change general audit scheduling, configured pass counts, purity behavior, timeout budgets, or ordinary short-rate-limit recovery.

- **The plan’s “## Risks”, state leak:** keep the quota result local to one audit invocation and do not add persistent quota state or cross-command coordination.

## Deferred

- Provider-specific quota wording without step 1’s confirmed markers — route through the plan’s `## Deferred` process rather than broadening this terminal audit rule.
- Cross-command quota coordination or persistent quota state — remains outside the plan’s audit-local recovery boundary.
