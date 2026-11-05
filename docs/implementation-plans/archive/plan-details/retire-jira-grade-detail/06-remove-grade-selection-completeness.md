> **Auto-archived**: this plan was swept on 2026-11-05 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 6 — Make completeness audits run-grade-only

<!-- plan-tool:detail-format-version: 1 -->

## Summary

Remove the Jira-grade branch from completeness auditing, reporting, detector selection, convergence diagnostics, and gate-status. The retained path always reads the run-grade detail bundle and uses the run-grade conceptual prompts, deterministic checks, report guidance, history, and qualification flow. Update the completeness, convergence, and gate-status CLIs so their grade selectors are rejected by argparse rather than routed through compatibility logic. On green, audit markdown reports and findings sidecars retain their current replacement-write and qualification behavior, but no audit or diagnostic surface can read, describe, or select Jira-grade detail.

## Table of Contents

- [Summary](#summary) — The retained audit and diagnostic behavior.
- [Table of Contents](#table-of-contents) — Links to each section.
- [Why](#why) — Why audit consumers must stop selecting retired detail.
- [Input](#input) — Run-grade evidence and bundle contracts this step reads.
- [Files (creates vs edits)](#files-creates-vs-edits) — Source and test changes in scope.
- [Implementation](#implementation) — Remove grade branches while preserving run-grade policy.
- [Tests](#tests) — Unit and CLI coverage for retained behavior and removed selectors.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — CLI and parametrization references.
- [Applicable guardrails](#applicable-guardrails) — Scope boundaries for this retirement.
- [Deferred](#deferred) — Work this step deliberately leaves out.

## Why

Completeness-audit currently carries two detail contracts through prompt construction, deterministic detector dispatch, reports, saved-result handling, convergence advice, and gate-status selection. Step 5 makes active audit evidence run-grade-only, so retaining a Jira-grade reader here would either expose an unsupported artifact or preserve special cases that no valid evidence can support. This step makes every audit-facing consumer agree on the one supported run-grade bundle without changing the established run-grade convergence bar.

## Input

- **Step 5 run-grade evidence outcome:** Read the supported audit revisions, fingerprints, freshness checks, and reusable results that step 5 leaves behind. Treat retired or malformed grade evidence as unavailable through the existing evidence rules rather than adding a compatibility path.

- **Run-grade detail bundle:** Use `plan_tool/review.py:_format_audit_detail_bundle`, `plan_tool/review.py:audit_detail_bundle_status`, and `plan_tool/detail_artifacts.py:resolve_detail_artifact` as the single source of audit grounding. Preserve `Step.detail` pointer resolution and canonical-path fallback.

- **Saved report lifecycle:** Preserve `plan_tool/cli/completeness_phases.py:_persist_and_present_report` and `plan_tool/completeness_report.py:write_completeness_report` behavior for timestamped markdown reports, findings sidecars, replacement writes, checkpoints, and qualified final results.

## Files (creates vs edits)

- **New files:** None.

- **Existing files (edits only):**
  - `plan_tool/review.py` — Remove Jira-grade bundle resolution, compact-contract validation, prompt framing, grade parameters, and grade-based audit-loop behavior; retain run-grade bundle formatting, coverage status, prompt construction, and conceptual audit behavior.
  - `plan_tool/completeness_report.py` — Remove grade-aware next-step text, Jira-only remediation commands, hand-edit framing, and report branches; retain run-grade report content and qualification-aware guidance.
  - `plan_tool/cli/completeness_cmd.py` — Remove `completeness-audit --grade`, Jira-grade conflict handling, grounding banners, persistence suppression, and grade plumbing.
  - `plan_tool/cli/completeness_phases.py` — Remove grade-filtered detector dispatch and Jira-only report, JSON, persistence, and convergence branches; keep the run-grade detector registry and report pipeline.
  - `plan_tool/convergence_diagnosis.py` — Remove caller-selected grade dispatch for bare-mechanism advice while retaining the existing requirement for supported run-grade evidence.
  - `plan_tool/gate_status.py` — Make saved-result selection run-grade-only and remove grade output and filtering.
  - `plan_tool/cli/convergence_cmd.py` — Remove `convergence --grade` and make `_current_audit_stage` derive the stage from the run-grade bundle.
  - `plan_tool/cli/gate_status_cmd.py` — Remove `gate-status --grade` and its forwarding.
  - `tests/test_review.py` — Remove Jira-grade audit-bundle and framing cases; preserve run-grade bundle, status, prompt, and audit-loop coverage.
  - `tests/test_completeness_report.py` — Remove grade-specific command and report tests; retain run-grade next-step, report, sidecar, and qualification coverage.
  - `tests/cli/test_completeness_cmd.py` — Remove Jira-grade audit scenarios and add retained-path and parser-rejection coverage.
  - `tests/test_convergence_diagnosis.py` — Remove caller-grade selection cases and pin run-grade evidence requirements for the bare-mechanism advisory.
  - `tests/test_gate_status.py` — Remove foreign-grade selection tests and pin newest qualified run-grade result selection.
  - `tests/cli/test_convergence_cmd.py` — Cover run-grade current-stage agreement and argparse rejection of `--grade`.
  - `tests/cli/test_gate_status_cmd.py` — Update the versioned JSON contract and cover argparse rejection of `--grade`.

## Implementation

- **Keep one audit bundle.** Make `plan_tool/review.py:_format_audit_detail_bundle` and `plan_tool/review.py:audit_detail_bundle_status` run-grade-only. They must continue to agree about which steps are detailed or bare, including pointer-versus-canonical resolution and captured audit-input behavior.

- **Remove Jira-only prompt behavior.** Delete `_is_jira_grade_bundle`, `_JIRA_GRADE_BUNDLE_FRAMING`, and grade selection in `plan_tool/review.py:_format_bundle_framing_block`, `plan_tool/review.py:render_plan_audit_prompt`, `plan_tool/review.py:check_plan_audit`, and `plan_tool/review.py:audit_plan_until_stable`. Preserve the run-grade framing and existing bare-plan instructions unchanged in meaning.

- **Keep detector coverage run-grade-only.** Simplify `plan_tool/cli/completeness_phases.py:deterministic_detector_registry`, `_battery_detectors`, and `_run_deterministic_checks` so all retained detectors run through one registry without grade filtering. Remove Jira-bundle detector results and related bucket adaptation; do not change the order or blocking meaning of the retained run-grade checks.

- **Remove grade plumbing end to end.** Remove detail-grade parameters and forwarding from `plan_tool/cli/completeness_cmd.py:cmd_completeness`, `plan_tool/cli/completeness_phases.py:_sample_conceptual_audit`, `_render_completeness_json`, `_render_grouped_report`, `_persist_and_present_report`, and their direct readers. One way is to make the helpers rely on the existing run-grade defaults after removing the selector, but the resulting public and internal contracts must not imply a selectable grade remains.

- **Preserve report and sidecar durability.** Keep markdown report replacement writes and findings-sidecar replacement writes on their existing paths. Preserve the qualification guards that decide whether a final sidecar is written, including checkpoint versus final-result behavior. Removing Jira-grade suppression must not weaken malformed-evidence, stale-revision, or unqualified-result handling established by step 5.

- **Keep run-grade remediation guidance.** Simplify `plan_tool/completeness_report.py:_reaudit_command`, `next_stage_command`, `suggested_next_steps`, `suggested_next_step_commands`, and `build_report_md` to emit only valid run-grade commands and the existing session-directed conceptual-finding guidance. Do not retain commands that name a retired selector or an unavailable Jira-detail authoring route.

- **Keep convergence policy unchanged.** Remove `mechanism_advisory_grade` selection from `plan_tool/convergence_diagnosis.py:classify_bare_mechanism_advisory` and `diagnose_convergence`. The advisory must still require current, completed, run-grade evidence; this is evidence eligibility, not a new convergence rule.

- **Make diagnostics agree with audit grounding.** Update `plan_tool/cli/convergence_cmd.py:_current_audit_stage` to call `plan_tool/review.py:audit_detail_bundle_status` without a selector. Update `plan_tool/gate_status.py:build_gate_status` to select the newest qualified, reusable run-grade result per stage without accepting a requested grade. Keep current-stage failure behavior best-effort and read-only.

- **Remove selectors at argparse registration.** Remove `--grade` from `plan_tool/cli/completeness_cmd.py:register`, `plan_tool/cli/convergence_cmd.py:register`, and `plan_tool/cli/gate_status_cmd.py:register`. Argparse must reject the option before command execution; do not add a separate legacy-refusal branch.

- **Do not broaden the retirement.** This step removes only audit and diagnostic consumers named in the declared file list. Reuse the run-grade evidence and detail contracts established by step 5 rather than changing their schema, rewriting archived records, or changing the run-grade convergence policy.

## Tests

### Tests for this step

- `tests/test_review.py:test_audit_detail_bundle_reads_declared_run_grade_detail` — Assert the audit bundle uses the declared run-grade detail pointer and preserves canonical fallback when no pointer exists.

- `tests/test_review.py:test_audit_detail_bundle_status_matches_run_grade_bundle_resolution` — Assert bare and detailed step IDs are computed from the same run-grade resolution rule used by prompt grounding.

- `tests/test_review.py:test_plan_audit_prompt_uses_run_grade_bundle_framing` — Assert the conceptual prompt contains retained run-grade framing and no Jira-grade contract language.

- `tests/test_completeness_report.py:test_reaudit_command_keeps_iterate_for_the_only_supported_bundle` — Assert re-audit guidance uses the existing run-grade convergence command.

- `tests/test_completeness_report.py:test_report_next_steps_never_emit_retired_grade_commands` — Assert bare and detailed report guidance contains only supported detail, audit, run, and export commands.

- `tests/test_completeness_report.py:test_write_report_preserves_markdown_and_qualified_sidecar_replacement_guards` — Assert markdown and final sidecar writes retain their existing qualification and replacement behavior.

- `tests/cli/test_completeness_cmd.py:test_deterministic_detector_registry_dispatches_retained_run_grade_checks` — Assert the retained registry reaches the normal deterministic checks without grade filtering.

- `tests/cli/test_completeness_cmd.py:test_completeness_audit_persists_run_grade_report_and_qualified_sidecar` — Assert a successful audit writes the normal report and eligible sidecar.

- `tests/cli/test_completeness_cmd.py:test_completeness_audit_rejects_removed_grade_selector` — Assert `main()` returns an argparse error for `completeness-audit ... --grade jira`.

- `tests/test_convergence_diagnosis.py:test_bare_mechanism_advisory_requires_completed_run_grade_evidence` — Assert legacy, malformed, and retired-grade provenance cannot produce the advisory, while valid run-grade evidence can.

- `tests/cli/test_convergence_cmd.py:test_convergence_current_stage_uses_run_grade_bundle` — Assert convergence derives the same bare/detail stage as completeness-audit.

- `tests/cli/test_convergence_cmd.py:test_convergence_rejects_removed_grade_selector` — Assert `convergence ... --grade jira` is rejected by argparse.

- `tests/test_gate_status.py:test_gate_status_selects_newest_qualified_run_grade_result_per_stage` — Assert gate status keeps one newest current qualified result for each stage without a grade selector.

- `tests/test_gate_status.py:test_gate_status_does_not_replace_final_result_with_unqualified_or_unusable_evidence` — Assert checkpoint, malformed, report-only, and unqualified artifacts cannot replace a final gate result.

- `tests/cli/test_gate_status_cmd.py:test_gate_status_emits_run_grade_versioned_json_without_creating_state` — Assert the read-only JSON document omits grade selection while retaining plan, stage, and result fields.

- `tests/cli/test_gate_status_cmd.py:test_gate_status_rejects_removed_grade_selector` — Assert `gate-status ... --grade jira` is rejected by argparse.

Every listed test must be green before this step is finished.

## Acceptance criteria

- `completeness-audit`, `convergence`, and `gate-status` reject `--grade` through argparse.

- `plan_tool/review.py` has one audit detail-bundle resolution path based on run-grade `Step.detail` resolution.

- Conceptual audit prompts, bare/detail coverage, deterministic detector dispatch, JSON output, reports, convergence diagnostics, and gate-status all use the same run-grade bundle.

- Completeness reports never emit Jira-grade framing, remediation commands, export commands with a grade selector, or hand-edit exceptions that existed only for the retired lane.

- Markdown reports and eligible findings sidecars continue to use the current replacement-write paths, and qualification guards continue to prevent unqualified results from becoming final evidence.

- Bare-mechanism convergence advice remains limited to valid completed run-grade evidence.

- Gate-status selects the newest qualified current run-grade result per stage and remains read-only.

- The unit tests and class-marked CLI integration tests in the declared test files pass.

## References

- [argparse — Parser for command-line options, arguments and subcommands](https://docs.python.org/3.13/library/argparse.html) — Use for removing option registration so retired selectors fail during parsing.

- [pytest parametrization — How to parametrize fixtures and test functions](https://docs.pytest.org/en/stable/how-to/parametrize.html) — Use for compact coverage of retained evidence and rejected selector cases.

## Applicable guardrails

- **The plan’s “## Step intent”** — Make audits and diagnostics agree on the supported detail bundle; do not leave a second reader or selector behind.

- **The plan’s “## Scope guardrails”** — Remove retired-grade dependencies only where they block the audit and diagnostic lane; do not add a compatibility reader or replacement artifact.

- **The plan’s “## Out of scope”** — Do not change run-grade authoring, Jira export output, or archived historical records while removing these readers.

## Deferred

- `plan_tool/review_persistence.py` schema evolution or archival-record rewriting — Step 5 owns active audit-evidence validation, and this step must consume its run-grade-only rules without changing stored historical artifacts.
