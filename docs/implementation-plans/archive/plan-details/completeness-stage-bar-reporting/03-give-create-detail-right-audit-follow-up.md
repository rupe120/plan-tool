> **Auto-archived**: this plan was swept on 2026-08-18 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 3 — Give create and detail the right audit follow-up

## Summary

Make authoring follow-ups use Step 2’s qualified audit outcome instead of treating any earlier completeness sidecar as current. Update `plan_tool/cli/authoring.py` to give newly created plans, run-grade detail flows, and Jira-grade detail flows a clear safe audit route when no current qualified result with matching audited plan/detail artifacts exists. Update `plan_tool/cli/completeness_phases.py` to hand the final outcome back to an authoring parent without exposing recovery checkpoints. On green, each authoring command prints one coherent `Next steps:` block that preserves qualified audit guidance or leads with the correct fresh audit command.

## Table of Contents

- [Summary](#summary) — Completed authoring-handoff behavior.
- [Table of Contents](#table-of-contents) — Links to this detail’s sections.
- [Why](#why) — The current gap between authoring and audit qualification.
- [Input](#input) — Step 2’s outcome contract and the existing tail seam.
- [Files (creates vs edits)](#files-creates-vs-edits) — Files changed by this step.
- [Implementation](#implementation) — Follow-up selection and result transport rules.
- [Tests](#tests) — Focused command and phase coverage.
- [Acceptance criteria](#acceptance-criteria) — Observable authoring outcomes.
- [References](#references) — CLI-output and test-capture references.
- [Applicable guardrails](#applicable-guardrails) — Boundaries that keep this a reporting change.
- [Deferred](#deferred) — Related work left to other steps.

## Why

`plan_tool/cli/authoring.py:cmd_create()` and the post-authoring paths in `cmd_detail()`, `cmd_split()`, and `cmd_merge()` currently print generic next commands, while `_run_completeness_tail()` returns only disposition commands. After authoring changes a plan or selected detail bundle, an older sidecar is historical evidence, not proof of a current audit result. This step makes the authoring handoff use Step 2’s final qualification so an operator is directed to a fresh grade-compatible audit whenever the tail did not produce current qualified evidence.

## Input

- **Step 2 final result:** Consume Step 2’s qualified audit-result output as data. Its headline, coverage qualification, plan/detail revision qualification, and final-versus-checkpoint role decide whether authoring may retain tail guidance.
- **Existing parent handoff:** `plan_tool/cli/authoring.py:_run_completeness_tail()` already passes `args._next_steps_sink` to `plan_tool/cli/completeness_phases.py:_persist_and_present_report()`. Preserve the single-parent, single-`Next steps:` behavior.
- **Grade selection:** Use `plan_tool/cli/authoring.py:_detail_grade()` and `GRADE_JIRA` for the selected detail-grade route. Jira-grade detail does not run the run-grade completeness tail.
- **Standalone audit guidance:** `plan_tool/completeness_report.py:suggested_next_step_commands()` remains the standalone completeness-audit route from Step 2. Do not duplicate or change that report policy in this step.

## Files (creates vs edits)

- **New files:** None.

- **Existing files (edits only):**
  - `plan_tool/cli/authoring.py` — Update `cmd_create()`, `cmd_detail()`, `cmd_split()`, `cmd_merge()`, and `_run_completeness_tail()` to choose follow-up commands from final audit qualification.
  - `plan_tool/cli/completeness_phases.py` — Provide the final qualified-result payload to a parent tail and keep `write_pre_apply_audit_checkpoint()` out of that handoff.
  - `tests/cli/test_authoring_cmds.py` — Cover create, detail, split, merge, skipped, and Jira-grade follow-up text.
  - `tests/cli/test_completeness_cmd.py` — Cover final-only result transport at the completeness presentation phase.

## Implementation

- **Foundational logic: qualified-audit-aware authoring follow-up selection.** Centralize the no-current-result follow-up in `plan_tool/cli/authoring.py` so `cmd_create()`, `cmd_detail()`, `cmd_split()`, and `cmd_merge()` do not each rebuild status wording or grade-specific commands.

- **Treat a new plan as unaudited.** After `cmd_create()` writes and registers a plan, state plainly that no current qualified completeness result exists and include `plan-tool completeness-audit <slug>` as a fresh bare-plan audit route. Keep the existing detail, status, gate, and run suggestions as applicable, but do not inspect or reuse a sidecar from before creation.

- **Keep split proposals audit-free.** `cmd_create()`’s `CreateResult.split_proposal` branch and `_emit_split_proposal()` must retain their carve/create guidance without offering a completeness command, because no plan was written.

- **Accept tail guidance only from final current evidence.** Let `_run_completeness_tail()` retain the tail’s disposition commands only when Step 2 supplied an ordinary final result with confirmed coverage, matching audited plan/detail artifacts, and a headline other than `no-qualified-current-evidence`. A qualified `awaiting-human-action`, `advisory-only`, or `clean` result may keep the existing tail commands.

- **Fail closed for missing or unqualified tail output.** When the tail is disabled, produces no final result, fails before revision capture, has `not-sampled` coverage/stage/revision, has unconfirmed coverage, has a stale or unknown revision, has missing/incomplete/nonmatching plan/detail revision data, or reports `no-qualified-current-evidence`, replace tail disposition commands with a clear no-current-result notice and a fresh run-grade `plan-tool completeness-audit <slug>` route. Do not offer apply, reuse, or an older saved audit as a substitute for the fresh audit.

- **Cover skipped authoring and structural edits.** Apply the same no-current-result route when `cmd_detail()` writes no detail, and when `cmd_split()` or `cmd_merge()` skips their tail through `--no-completeness` or `--no-detail`. Keep the immediate detail-authoring command where it is needed, then make the required fresh audit visible in the same next-step block.

- **Keep Jira grade separate.** The Jira branch in `cmd_detail()` must say that no current qualified Jira-grade result exists and direct the operator to `plan-tool completeness-audit <slug> --grade jira`. It must not run the run-grade tail or treat a run-grade sidecar as Jira-grade evidence.

- **Transport the exact final result once.** Extend `plan_tool/cli/completeness_phases.py:_persist_and_present_report()` or its final-result boundary to publish the Step 2 result through an optional parent-owned transport alongside `_next_steps_sink`. One suitable approach is a second private sink on `args`; the exact shape is up to the implementer. Publish the final object unchanged, including an unqualified final object, so `authoring.py` can decide safely.

- **Exclude checkpoints from the transport.** `write_pre_apply_audit_checkpoint()` must not publish recovery evidence to an authoring parent. An iterative tail may create a checkpoint and then a final report, but the parent must receive at most one final result, never the checkpoint’s null result.

- **Preserve command structure.** Keep `_run_completeness_tail()`’s lazy `from plan_tool.cli import app` import, its suppressed child run log, and its merged next-step behavior. The parent must still print one `Next steps:` header, with a fresh-audit route ahead of pipeline actions that would otherwise imply current audit evidence.

## Tests

### Tests for this step

- `tests/cli/test_authoring_cmds.py:TestCreateNextStepsGatesHint.test_created_plan_routes_to_fresh_bare_audit` — A created plan names the absence of current qualified evidence and offers a fresh bare-plan audit without losing applicable existing suggestions.
- `tests/cli/test_authoring_cmds.py:TestEmitSplitProposal.test_split_proposal_has_no_audit_follow_up` — A create split proposal offers no completeness-audit command.
- `tests/cli/test_authoring_cmds.py:TestDetailTailAuditFollowUp.test_qualified_run_tail_keeps_disposition_commands` — Confirmed, current final tail evidence with matching audited plan/detail artifacts preserves the tail’s disposition commands in the single merged block.
- `tests/cli/test_authoring_cmds.py:TestDetailTailAuditFollowUp.test_unqualified_or_missing_run_tail_routes_to_fresh_audit` — Missing, not-sampled, unconfirmed, stale, unknown, missing/incomplete plan/detail revision, and no-qualified-current-evidence tail states suppress unsafe tail commands and show a fresh run-grade audit.
- `tests/cli/test_authoring_cmds.py:TestDetailSkippedOnlyHint.test_all_skipped_names_missing_current_audit` — A skipped-only detail run retains its force/split guidance and also states the fresh audit route.
- `tests/cli/test_authoring_cmds.py:TestDetailGradeRouting.test_grade_jira_names_fresh_jira_audit` — Jira-grade detail skips the run-grade tail and names only the Jira-grade audit command as its audit follow-up.
- `tests/cli/test_authoring_cmds.py:TestSplitCmd.test_no_completeness_routes_to_fresh_audit` — A split that skips the tail reports no current result and a fresh audit route.
- `tests/cli/test_authoring_cmds.py:TestMergeCmd.test_no_completeness_routes_to_fresh_audit` — A merge that skips the tail reports the same safe audit route.
- `tests/cli/test_completeness_cmd.py:TestPersistAndPresentReport.test_final_qualified_result_reaches_parent_sink` — The presentation phase sends the exact final result to a parent-owned transport once.
- `tests/cli/test_completeness_cmd.py:TestPersistAndPresentReport.test_pre_apply_checkpoint_does_not_reach_parent_sink` — Recovery checkpoint persistence never appears as an authoring-tail result.

- **Green gate:** Every test above and the existing affected CLI suites must pass before this step is complete.

## Acceptance criteria

- A successful `create` of a real plan states that no current qualified audit result exists and includes `plan-tool completeness-audit <slug>`.
- A create split proposal contains no completeness-audit follow-up.
- Run-grade detail, split, and merge retain tail disposition commands only for confirmed, current, ordinary-final evidence with matching audited plan/detail artifacts whose headline is not `no-qualified-current-evidence`.
- A disabled, pre-capture-failed, missing, not-sampled, unconfirmed, stale, unknown, or missing/incomplete plan/detail-revision tail result states that no current qualified result exists and leads with a fresh run-grade audit command.
- Jira-grade detail never uses the run-grade tail or sidecar and directs operators to `plan-tool completeness-audit <slug> --grade jira`.
- An iterative tail that writes a pre-apply checkpoint sends its parent only the later final result, if one exists.
- Each affected authoring path prints one merged `Next steps:` block and does not change completeness blocking, apply, or exit-code policy.

## References

- [sys — System-specific parameters and functions](https://docs.python.org/3.13/library/sys.html) — Preserve the existing stderr-oriented CLI handoff behavior.
- [How to capture stdout/stderr output](https://docs.pytest.org/en/stable/how-to/capture-stdout-stderr.html) — Pin the human-facing follow-up output independently from command results.

## Applicable guardrails

- **The plan’s “## Plan intent”** — Use the shared qualification contract to explain the next action; do not create a second audit-result policy in authoring.
- **The plan’s “## Step intent”** — Limit changes to create and detail-family follow-up wording and safe audit routing.
- **The plan’s “## Out of scope”, audit policy** — Do not alter stage bars, finding thresholds, pass policy, or automatic-apply eligibility while selecting follow-up commands.
- **The plan’s “## Out of scope”, process behavior** — Do not add scoring, new exit semantics, automated disposition choices, or broad report redesign.

## Deferred

- **Standalone completeness-report next-step policy** — `plan_tool/completeness_report.py:suggested_next_steps()` and `plan_tool/completeness_report.py:suggested_next_step_commands()` remain Step 2’s report-consumer surface.
- **Operator reference documentation** — Step 4 documents the settled create, run-grade detail, and Jira-grade handoff language.
