> **Auto-archived**: this plan was swept on 2026-08-18 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 2 — Show the qualified audit result everywhere

## Summary

Render Step 1’s shared audit decision in the CLI, Markdown reports, JSON, and saved completeness sidecars. Update the completeness command, phases, report, persistence, saved-review walk, and data-contract apply paths so every final result shows its headline, qualification, and audited plan/detail revision. Keep the saved result immutable and compute later plan/detail freshness as a separate view-time status. The LLM may continue to use the live project as context to explain an issue; no output or sidecar claims that this context was frozen, sandboxed, or reproducible. On green, operators and machine consumers see one consistent result, while checkpoint, legacy, stale, and unqualified completeness sidecars cannot drive a saved-review walk.

## Table of Contents

- [Summary](#summary) — The completed presentation and persistence outcome.
- [Why](#why) — Why existing output and saved-review readers can disagree.
- [Input](#input) — The Step 1 result and current report-sidecar contracts this step consumes.
- [Files (creates vs edits)](#files-creates-vs-edits) — The existing report, persistence, CLI, and test files to update.
- [Implementation](#implementation) — Result transport, rendering, reader checks, and invariants.
- [Tests](#tests) — Focused coverage for output, persistence, and replay behavior.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — JSON, CLI, and test-output references.
- [Applicable guardrails](#applicable-guardrails) — Policy and scope boundaries that remain fixed.
- [Deferred](#deferred) — Follow-on authoring and documentation work.

## Why

`finalize_completeness_run()` currently sends related facts through separate JSON, Markdown, console, persistence, reuse, and apply paths. A reader can therefore see current-looking findings without one joined explanation of coverage and the audited plan/detail revision, and `cmd_completeness_apply()`, `cmd_data_contract_apply()`, and `cmd_review_walk()` can select a completeness sidecar without proving it is a final, current result. Step 1 supplies the decision; this step makes that same decision visible and safe at every consumer boundary.

## Input

- **Step 1 result:** Step 1 provides the ordered finalization decision and immutable audited plan revision, grade-selected detail-bundle revision, and audit stage. Consume that outcome as data; do not recreate its headline logic in a renderer or command.
- **Saved-review contract:** Use `plan_tool/review_persistence.py:SavedReview`, `save_review()`, `load_review()`, and `update_annotation()` as the persistence boundary. Preserve the existing `audit_coverage`, `audit_stage`, fingerprint fields, and `is_pre_apply_checkpoint` role behavior. Versions 1–3 stay readable as legacy evidence; a completeness sidecar carrying `qualified_result` moves to one new version for both ordinary finals and checkpoints so an older reader rejects it rather than silently dropping the new object.
- **Existing output paths:** Keep `plan_tool/cli/completeness_phases.py:_render_completeness_json`, `_render_grouped_report`, and `_persist_and_present_report` aligned with `plan_tool/completeness_report.py:build_report_md` and `console_summary`.
- **Read-time freshness:** Compare the saved plan and grade-selected detail-bundle revisions to the current selected artifacts. A mismatch makes the saved result noncurrent and leads to a fresh audit suggestion. A missing or malformed saved result/revision is unavailable evidence, not a clean result. Project code, prompts, lessons, configuration, and prior audit history remain live context for explanation and are not freshness inputs.
- **Data-contract sidecar:** Keep `plan_tool/cli/data_contract_cmd.py:_verify_fresh` as the separate registry/document freshness check after the audit-result eligibility check; neither check replaces the other.
- **Generic saved-review walk:** Treat `plan_tool/cli/review_cmd.py:cmd_review_walk()` as a completeness-sidecar consumer whenever its default or explicit `--id` resolution selects `kind="completeness"`; its existing checkpoint-role check is not sufficient evidence eligibility.

## Files (creates vs edits)

- **New files:** None.

- **Existing files (edits only):**
  - `DATA_CONTRACT.md` — Document the `SavedReview.qualified_result` payload, immutable plan/detail audit revision, version-4 transition for final and checkpoint completeness sidecars, checkpoint `null` value, legacy handling, and additive `completeness-audit --json` object.
  - `plan_tool/cli/data_contract_cmd.py` — Make `_newest_saved_completeness_with_contract_payload()` and `cmd_data_contract_apply()` accept only a current final qualified audit before walking data-contract findings.
  - `plan_tool/cli/completeness_cmd.py` — Pass Step 1’s decision through `finalize_completeness_run()`, keep JSON stdout machine-readable, and reject non-final or non-current saved results in `cmd_completeness_apply()`.
  - `plan_tool/cli/completeness_phases.py` — Thread the result through `_render_completeness_json()`, `_render_grouped_report()`, `write_pre_apply_audit_checkpoint()`, and `_persist_and_present_report()`.
  - `plan_tool/cli/review_cmd.py` — Make default and explicit-id saved-review walking apply the same final/current eligibility rule before admitting a completeness sidecar.
  - `plan_tool/completeness_report.py` — Render one compact audit-result/provenance block in `build_report_md()`, `console_summary()`, and next-step helpers without recomputing the headline.
  - `plan_tool/review_persistence.py` — Store, load, and preserve `SavedReview.qualified_result`; expose one fail-closed plan/detail read-time revision projection for saved completeness consumers.
  - `tests/cli/test_data_contract_cmd.py` — Cover current-final selection and refusal paths for the data-contract apply command.
  - `tests/cli/test_completeness_cmd.py` — Cover JSON, finalization, checkpoint, and completeness-apply presentation and eligibility.
  - `tests/cli/test_review_cmds.py` — Cover generic saved-review-walk selection and refusal paths for completeness sidecars.
  - `tests/test_data_contract.py` — Pin the documented SavedReview and JSON contract.
  - `tests/test_completeness_report.py` — Cover Markdown, console, next-step, and read-time freshness presentation.
  - `tests/test_review_persistence.py` — Cover result round trips, legacy/malformed handling, checkpoints, and annotation rewrites.

## Implementation

- **Use one public result object.** Render the Step 1 decision as additive `qualified_result` data with `headline`, `stage`, `coverage`, `revision_status`, and nullable `audit_revision`. The populated audit revision identifies the audited plan revision and grade-selected detail-bundle revision. The allowed headlines are `no-qualified-current-evidence`, `awaiting-human-action`, `advisory-only`, and `clean`; the stage values are `bare`, `detail`, and `not-sampled`, and coverage values are `confirmed`, `unconfirmed`, `unknown-legacy`, and `not-sampled`. An absent, skipped, or pre-capture failed audit has all three qualifiers `not-sampled` and a null audit revision; `unconfirmed` requires a completed audit whose coverage cannot qualify.

- **Keep audit-time and view-time state separate.** Treat `qualified_result.revision_status` and `qualified_result.audit_revision` as immutable facts about the audit that completed. When a command reads a sidecar later, calculate a separate `view_revision_status` by comparing the saved plan/detail revision against the current selected artifacts; never rewrite the saved result or replace its captured values. A result with no audited-revision capture remains explicitly `not-sampled`, never stale or current. Live project context is deliberately not materialized or compared by this status.

- **Do not let renderers classify findings.** `plan_tool/cli/completeness_cmd.py:finalize_completeness_run()` should receive or obtain the Step 1 decision once, then pass it unchanged to `plan_tool/cli/completeness_phases.py:_render_completeness_json`, `_render_grouped_report`, and `_persist_and_present_report`. Reject the alternative of having each renderer infer a headline from finding counts, stops, or coverage fields.

- **Render every final surface.** Add a compact status and provenance block to the audit-only grouped Markdown and the persisted report assembled by `plan_tool/completeness_report.py:build_report_md`. Extend `console_summary()` with the same headline and short qualification, leaving full revision data in the report. Make `_render_completeness_json()` include the additive object while preserving all existing top-level JSON keys and their meanings.

- **Preserve JSON and exit behavior.** For `--json`, keep stdout valid JSON; send any concise status or `--fail-on-findings` guidance to stderr. Use the shared result only to explain the existing finalization outcome—do not change `_completeness_has_blocking_findings()`, `_completeness_finalize_is_clean()`, stage bars, or return-code precedence.

- **Handle checkpoints explicitly.** `plan_tool/cli/completeness_phases.py:write_pre_apply_audit_checkpoint()` must persist `qualified_result: null` and label its Markdown artifact as recovery evidence rather than a final result. A checkpoint must never receive a synthetic headline merely because it has recommendations, coverage, or fingerprints.

- **Persist without a shadow revision or version downgrade.** Thread the final result and captured plan/detail revision through `plan_tool/completeness_report.py:write_completeness_report()` into `plan_tool/review_persistence.py:save_review()`. Any completeness sidecar carrying `qualified_result`, including a checkpoint whose value is `null`, uses schema version 4. `load_review()` leaves versions 1–3 readable as legacy absence and malformed/incomplete revision values loadable but unavailable for final/current use. `update_annotation()` must retain a version-4 result and version, never rewrite it as a v1–3 payload. Keep the audit revision nested in `qualified_result`; do not have persistence or report writing recompute it from post-iteration disk.

- **Document the schema precisely.** In `DATA_CONTRACT.md`, add the `qualified_result` row to the `SavedReview` contract and describe the nested plan/detail revision fields, version-4 write rule, valid status vocabulary, checkpoint `null`, and legacy-unavailable behavior. Versions 1–3 remain loadable legacy records, while a pre-version-4 reader rejects version 4 by its established supported-version check. Existing code fingerprints, if retained, remain historical metadata rather than a claim that all audit context is reproducible. Update the `completeness-audit --json` section to distinguish immutable `revision_status` from unpersisted read-time `view_revision_status`.

- **Make next steps result-aware.** Update `plan_tool/completeness_report.py:suggested_next_steps()` and `suggested_next_step_commands()` so no-qualified evidence leads with a fresh audit route, not an apply/reuse command. Preserve existing human-action and advisory guidance when the result is final and current; do not use this work to choose a user’s apply, defer, split, or carve decision.

- **Fail closed before every completeness-sidecar walk.** In `plan_tool/cli/completeness_cmd.py:cmd_completeness_apply()`, `plan_tool/cli/data_contract_cmd.py:cmd_data_contract_apply()`, and `plan_tool/cli/review_cmd.py:cmd_review_walk()`, admit a completeness sidecar only when it is ordinary-final with a present qualified result, confirmed coverage, and a current plan/detail view. During unpinned selection, skip ineligible completeness candidates and use an older current final one only if it still qualifies; an explicit `--id` for an ineligible sidecar must fail without falling back. The generic walk preserves its existing behavior for non-completeness review kinds. Report the fresh `plan-tool completeness-audit <name>` route before any completeness findings, advisory display, data-contract payload, or mutation is processed.

- **Keep Jira-grade behavior coherent.** The Jira-grade Markdown and JSON paths must render the shared result using the grade-selected audited plan/detail revision. Preserve the current Jira-grade rule that does not write a findings sidecar, so no run-grade replay path can consume Jira-grade findings.

## Tests

### Tests for this step

- `tests/cli/test_completeness_cmd.py:TestRenderCompletenessJson.test_qualified_result_is_additive` — Final JSON contains the required headline, qualification, and nullable plan/detail revision fields without changing existing keys; an absent/skipped/pre-capture-failed audit uses `not-sampled` stage/coverage/revision and null revision.
- `tests/cli/test_completeness_cmd.py:TestFinalizeCompletenessRun.test_final_result_reaches_every_final_renderer` — One finalization decision reaches JSON, grouped Markdown, persisted Markdown, and the concise terminal summary.
- `tests/cli/test_completeness_cmd.py:TestFinalizeCompletenessRun.test_fail_on_findings_explains_without_changing_exit_policy` — Result guidance does not alter established `--fail-on-findings` return behavior or corrupt JSON stdout.
- `tests/cli/test_completeness_cmd.py:TestPersistAndPresentReport.test_pre_apply_checkpoint_has_no_qualified_result` — The checkpoint report and sidecar carry recovery-only status and `qualified_result: null`.
- `tests/cli/test_completeness_cmd.py:TestCompletenessApplyRevisionGate.test_apply_rejects_checkpoint_unqualified_and_stale_results` — Default and explicit completeness-apply paths do not walk findings from an ineligible or plan/detail-noncurrent sidecar.
- `tests/cli/test_data_contract_cmd.py:test_data_contract_apply_skips_ineligible_default_sidecars` — Default data-contract selection skips checkpoints and unavailable results while accepting a current final audit.
- `tests/cli/test_data_contract_cmd.py:test_data_contract_apply_rejects_explicit_noncurrent_result` — An explicit stale, legacy, or checkpoint sidecar returns a fresh-audit route before any contract edit.
- `tests/cli/test_review_cmds.py:test_review_walk_skips_ineligible_completeness_sidecars` — Default generic-walk lookup skips stale, legacy, unconfirmed, malformed, and checkpoint completeness sidecars.
- `tests/cli/test_review_cmds.py:test_review_walk_rejects_explicit_ineligible_completeness_sidecar` — An explicit completeness-sidecar id that is not final/current fails before walking findings, while ordinary review-sidecar behavior remains unchanged.
- `tests/test_completeness_report.py:test_report_renders_qualified_result_and_audit_revision` — The persisted Markdown reports the headline, coverage, revision status, and exact audited plan/detail revision.
- `tests/test_completeness_report.py:test_console_and_next_steps_route_unqualified_result_to_fresh_audit` — Console and report next steps do not offer apply/reuse actions for no-qualified-current-evidence.
- `tests/test_completeness_report.py:test_saved_result_revision_view_status_does_not_mutate_audit_time_status` — Later plan or selected-detail drift is shown as view-time stale without changing the stored historical result, while live project-context changes do not assert staleness.
- `tests/test_review_persistence.py:TestSaveReview.test_qualified_result_round_trips_as_version_four` — A new final sidecar retains the complete result object and audited plan/detail revision through save and load at version 4.
- `tests/test_review_persistence.py:TestCheckpointRole.test_checkpoint_round_trips_null_qualified_result_as_version_four` — A version-4 checkpoint role and null result remain distinct from an ordinary final sidecar.
- `tests/test_review_persistence.py:TestSaveReview.test_version_four_qualified_result_is_rejected_by_pre_version_four_reader` — A fixture using the version-1–3 supported set rejects the new sidecar rather than accepting and dropping `qualified_result`.
- `tests/test_review_persistence.py:TestSaveReview.test_update_annotation_preserves_version_four_qualified_result` — Annotation writes do not drop or rewrite a valid immutable result, or downgrade its schema version.
- `tests/test_review_persistence.py:TestSaveReview.test_missing_or_malformed_qualified_result_is_unavailable` — Legacy, malformed, and incomplete revision payloads remain inspectable but cannot qualify as current final evidence.
- `tests/test_data_contract.py:test_saved_review_qualified_result_contract_documented` — `DATA_CONTRACT.md` documents the persisted result fields, null checkpoint form, and legacy semantics.

- **Green gate:** Every test above and the existing affected suites must pass before this step is complete.

## Acceptance criteria

- Every new final `completeness-audit --json` payload includes `qualified_result` with the four required status fields and the audited plan/detail revision object, or `null` as the contract requires.
- A result with no audited-revision capture renders `not-sampled` for stage, coverage, and revision status with a null audit revision; a completed audit with coverage-unconfirmed result retains the captured bare/detail stage.
- Final run-grade completeness sidecars persist the same `qualified_result` that their reports render at schema version 4; version 1–3 sidecars remain readable legacy evidence without being treated as qualified.
- A pre-apply checkpoint persists `qualified_result: null` at schema version 4 and is never presented as a final or current audit result.
- Markdown reports show the headline, coverage qualification, revision qualification, and exact audited plan/detail revision without recomputing post-audit inputs.
- A later sidecar consumer can show a separate current/stale/unknown `view_revision_status` from a plan/detail comparison without modifying the saved `qualified_result`; live project context stays available for explanation and is not presented as captured input.
- `completeness-apply`, `data-contract-apply`, and the generic saved-review walk refuse an explicit checkpoint, missing/malformed revision, unconfirmed result, or non-current plan/detail revision before presenting or applying findings.
- Unpinned completeness-sidecar lookup in every consumer may select only a current final qualified result with matching plan/detail artifacts; it must route to a fresh audit when none exists.
- A v4 annotation rewrite preserves its `qualified_result` and schema version; a pre-v4 reader rejects the sidecar instead of silently dropping the new contract.
- Existing blocking bars, apply eligibility, convergence, and return-code policy remain unchanged.

## References

- [json — JSON encoder and decoder](https://docs.python.org/3.13/library/json.html) — Use the standard-library JSON model when adding an additive object to CLI output.
- [How to capture stdout/stderr output](https://docs.pytest.org/en/stable/how-to/capture-stdout-stderr.html) — Pin human-facing status text separately from JSON stdout.

## Applicable guardrails

- **The plan’s “## Plan intent”** — Show one qualified audit-result contract across final surfaces; do not treat live project context as a frozen input contract.
- **The plan’s “## Step intent”** — Keep this step to result transport, presentation, persistence, and safe saved-sidecar consumption.
- **The plan’s “## Out of scope”, audit policy** — Do not change finding thresholds, stage bars, pass policy, automatic-apply eligibility, or exit semantics.
- **The plan’s “## Out of scope”, implementation scope** — Do not add background re-audits, a project-context snapshot, or a general report redesign.

## Deferred

- **Authoring follow-up wording** — Step 3 owns create/detail/split/merge next-step selection and parent-tail transport.
- **Operator documentation and plan-gap presentation** — Step 4 documents the settled result and authoring handoff language.
