> **Withdrawn 2026-08-11** — Withdrawn after the detail-stage audit exposed an unresolved high-severity provenance-ordering defect and non-convergent correctness contracts; re-seed the capability from the audited invariants before implementation.
> Preserved here for history; do not edit.

# Step 5 — Add the bad-fix provenance advisory to convergence

## Summary

Add a recommend-only bad-fix advisory to `plan_tool/convergence_diagnosis.py` that joins a newly open recurring finding to qualified, prior remedy evidence. Update `plan_tool/cli/completeness_cmd.py:_convergence_loop_advisory_lines` so the same rendered advisory reaches the existing completeness stderr path after a saved run. Keep identity stricter than `_matches`, and keep the existing edit-drift and impact-recurrence behavior unchanged. On green, operators see the recurring finding and the relevant prior operator remedy without any change to convergence verdicts, stop reasons, or exit codes.

## Table of Contents

- [Summary](#summary) — Reviewer overview of the advisory and its output paths.
- [Table of Contents](#table-of-contents) — Quick links to every section.
- [Why](#why) — Why convergence needs qualified remedy evidence before warning about a bad fix.
- [Input](#input) — Upstream provenance, record-command, and title-matcher contracts this step consumes.
- [Files (creates vs edits)](#files-creates-vs-edits) — In-scope implementation and regression files.
- [Implementation](#implementation) — Same-issue matching, evidence selection, rendering, and non-interference rules.
- [Tests](#tests) — Focused unit and command coverage for the new advisory.
- [Acceptance criteria](#acceptance-criteria) — Observable completion conditions.
- [References](#references) — Standard-library behavior behind the result records and title fallback.
- [Applicable guardrails](#applicable-guardrails) — Plan boundaries that constrain this advisory.
- [Deferred](#deferred) — Related work intentionally left outside this step.

## Why

`plan_tool/convergence_diagnosis.py:classify_edit_drift` can identify a recurrence pattern, but its `_build_prior_apply_set` accepts disappearances and terminal dispositions without proving an operator recorded a remedy. Steps 2 and 3 supply ordered, source-marked annotation evidence, so this step can warn that a particular recurrence followed a real operator remedy while still treating the match as a prompt to re-check work, not proof of causation.

## Input

- **Step 2 provenance contract:** Step 2 supplies provenance-bearing `plan_tool/review_persistence.py:Annotation` values and the source-event collection retained by `plan_tool/convergence_diagnosis.py:build_collapsed_completeness_passes`. Read the landed fields and event shape from code; missing or malformed provenance remains non-qualifying.

- **Step 3 hand-record contract:** Step 3 makes `plan_tool/cli/completeness_cmd.py:cmd_completeness_record` another producer of explicit operator remedy evidence. Treat it the same as a qualifying interactive remedy event; do not add a separate hand-apply history path.

- **Step 4 title contract:** Step 4 supplies `plan_tool/convergence_diagnosis.py:_fuzzy_title_match`. Reuse that title-only fallback without changing `plan_tool/convergence_diagnosis.py:_matches`.

- **History and status contracts:** `plan_tool/convergence_diagnosis.py:CompatiblePass.annotations` remains the terminal-status map for `_is_resolved_in_run`; the separate source-event view supplies provenance selection. `plan_tool/convergence_diagnosis.py:_impact_recurrence_trailing_window` defines the existing same-stage collapsed-pass window.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `plan_tool/convergence_diagnosis.py` — retain the finding data needed for issue-skeleton matching; add the dedicated same-issue predicate, bad-fix classifier and result data, diagnosis wiring, and renderer lines.
  - `plan_tool/cli/completeness_cmd.py` — include the new renderer output in `_convergence_loop_advisory_lines` under the existing post-sidecar advisory conditions.
  - `tests/test_convergence_diagnosis.py` — cover identity tiers, qualified-event selection, window boundaries, classifier silence, diagnosis wiring, and rendering.
  - `tests/cli/test_convergence_cmd.py` — drive saved sidecars through `plan-tool convergence` and assert the advisory remains read-only and exit-zero.
  - `tests/cli/test_completeness_cmd.py` — extend `TestCompletenessStderrConvergenceAdvisories` for the shared stderr hook and its non-interference rules.
  - `tests/test_audit_shapes.py` — make the regression explicit that `self-seeded-finding` remains judgment-only and cannot become an advisory-emitter shape.

## Implementation

- **Foundational logic: evidence-gated same-issue recurrence.** Add a dedicated classifier, such as `classify_bad_fix_provenance`, that returns no advisory unless an unresolved newest-pass finding matches an earlier finding and that earlier finding has qualifying remedy evidence.

- **Carry a usable issue skeleton through history.** Extend `plan_tool/convergence_diagnosis.py:RunFinding` and `_finding_from_recommendation` with `Recommendation.body` or an equivalent normalized skeleton. Keep hand-built `RunFinding` fixtures and existing consumers compatible, and do not store or compare prose beyond the deterministic normalized equality needed here.

- **Use a separate identity predicate.** Add a private helper such as `_same_issue_identity` beside `_matches`. It must not use `step_id` as identity, because `_matches`’ step-focus tier is intentionally broader than this signal.

- **Keep tier ordering strict.** Match equal non-empty anchors first. When anchors are absent, one-sided, or unequal, compare non-empty normalized bodies with `plan_tool/review.py:_normalize_audit_fingerprint`; only then use Step 4’s `_fuzzy_title_match`. Equal finding ids may reduce candidate work, but never establish identity alone.

- **Keep empty evidence from matching.** Empty normalized bodies must not match each other. Continue to the title fallback when no usable body skeleton exists rather than treating two missing bodies as the same issue.

- **Do not alter existing recurrence matchers.** Leave `_matches`, `classify_edit_drift`, `classify_impact_recurrence`, and `plan_tool/telemetry_analysis.py:_strict_finding_match` on their current identity rules. The new helper owns the narrower policy.

- **Use only prior distinct collapsed passes.** Start from `build_collapsed_completeness_passes`, then use the newest same-stage trailing window. Require at least three distinct collapsed passes even when a test supplies a smaller window value; do not read raw `ReportHistory.runs` or reconcile series.

- **Require an open recurrence.** Evaluate only a finding in the newest collapsed pass that `_is_resolved_in_run` considers open. An applied finding or deliberate empty-halt skip in the newest pass cannot produce this advisory.

- **Join identity before provenance.** For each matched prior finding, look up source events using that prior finding’s recommendation id, not the newest finding id. This keeps the join correct when recommendation ids change between audits.

- **Use a fail-closed remedy predicate.** A source event qualifies only when it has the Step 2 applied disposition, empty halt reason, stripped non-empty operator note, recognized operator source, complete source-report identity, and a valid `recorded_at` strictly before the newest pass’s `created_at`. Generated text, failed or declined dispositions, any halt, legacy records, malformed fields, and later timestamps remain silent.

- **Select the closest qualifying evidence.** When more than one matched prior event qualifies, select the latest qualifying `recorded_at` before the recurrence. Preserve and render that event’s own source report identity and report-created time, never the collapsed pass replacement time.

- **Keep collapse boundaries meaningful.** Do not use an event merged into the newest collapsed pass as prior evidence. If an applied note and its identical-id re-audit collapse together with no earlier distinct pass, the classifier stays silent.

- **Make the result renderer-ready.** Add a frozen advisory record that carries the recurring finding and the selected evidence needed by `_bad_fix_lines`: operator-note excerpt, recording time, note source, and original report identity. Follow the existing `EditDriftAdvisory` and `ImpactRecurrenceAdvisory` data-flow shape without forcing either type to carry provenance.

- **Wire both render paths.** Add the result to `ConvergenceDiagnosis`, populate it in `diagnose_convergence`, and render it in `render_diagnosis` beside the existing loop-pattern advisories and before run-readiness lines. `plan_tool/cli/convergence_cmd.py:cmd_convergence` then gains the output through `render_diagnosis` without a handler change.

- **Reuse the completeness hook.** Update `plan_tool/cli/completeness_cmd.py:_convergence_loop_advisory_lines` to import and append `_bad_fix_lines` when the diagnosis has this advisory. Preserve `_emit_convergence_loop_advisories`’ existing grade, sidecar-write, and stderr timing rules.

- **State the limit in the output.** Render a clear warning that names the recurring issue, excerpts the recorded operator remedy, identifies when and where it was recorded, and tells the operator to re-check that edit. Say it is recommend-only and does not change the convergence verdict or run-readiness behavior.

## Tests

### Tests for this step

- `tests/test_convergence_diagnosis.py:test_same_issue_identity_uses_anchor_skeleton_then_title` — verifies anchor priority, one-sided and unequal-anchor skeleton fallback, and final fuzzy-title fallback.

- `tests/test_convergence_diagnosis.py:test_same_issue_identity_rejects_equal_id_or_step_alone` — proves recommendation-id equality and shared step focus cannot create a bad-fix match by themselves.

- `tests/test_convergence_diagnosis.py:TestBadFixProvenanceClassifier.test_qualifying_prior_operator_remedy_fires_for_open_recurring_finding` — verifies a three-pass, same-stage, id-churn recurrence selects a valid earlier operator remedy.

- `tests/test_convergence_diagnosis.py:TestBadFixProvenanceClassifier.test_selects_latest_qualifying_event_and_original_report_identity` — verifies event-time ordering and rendering data come from the selected source event rather than collapse metadata.

- `tests/test_convergence_diagnosis.py:TestBadFixProvenanceClassifier.test_silent_without_three_distinct_same_stage_collapsed_passes` — covers short history, stage changes, reconcile reports, and a reuse-collapsed prior note that is not a distinct pass.

- `tests/test_convergence_diagnosis.py:TestBadFixProvenanceClassifier.test_silent_for_unqualified_or_post_recurrence_annotations` — covers generated, declined, failed, halted, blank, legacy, malformed, and late annotations.

- `tests/test_convergence_diagnosis.py:TestBadFixProvenanceClassifier.test_silent_for_identity_only_or_note_only_history` — proves neither recurrence identity nor a note without a matched issue is causal evidence.

- `tests/test_convergence_diagnosis.py:test_diagnose_and_render_bad_fix_advisory_are_recommend_only` — verifies `diagnose_convergence` populates the field and `render_diagnosis` includes the finding, note excerpt, time, report identity, and non-gating wording.

- `tests/cli/test_convergence_cmd.py:test_convergence_prints_bad_fix_provenance_advisory` — seeds real sidecars, drives `main`, and confirms the CLI prints the advisory while returning zero.

- `tests/cli/test_completeness_cmd.py:TestCompletenessStderrConvergenceAdvisories.test_completeness_stderr_prints_bad_fix_provenance_advisory` — confirms the post-sidecar stderr path renders the same eligible signal.

- `tests/cli/test_completeness_cmd.py:TestCompletenessStderrConvergenceAdvisories.test_bad_fix_advisory_does_not_change_exit_code_or_iterate_stop_reason` — confirms the advisory leaves existing command outcomes unchanged.

- `tests/test_audit_shapes.py:test_self_seeded_finding_remains_judgment_only` — confirms this deterministic provenance advisory does not change audit-shape registry eligibility.

Every listed test must be green before this step is considered finished.

## Acceptance criteria

- A saved history with three distinct same-stage collapsed completeness passes emits a bad-fix advisory only when an open newest finding has both a same-issue prior finding and qualifying intervening remedy evidence.

- Same-issue matching uses equal non-empty anchors, then non-empty normalized body skeletons, then `plan_tool/convergence_diagnosis.py:_fuzzy_title_match`; equal finding ids and step focus never match alone.

- A newest-pass applied finding or deliberate empty-halt skip does not emit the advisory.

- The selected remedy is the latest qualifying prior event before the recurrence and renders its original report identity, report-created time, recording time, source, and operator-note excerpt.

- Generated, legacy, malformed, blank, declined, failed, halted, or post-recurrence annotations do not emit the advisory.

- Fewer than three distinct collapsed same-stage completeness passes, stage-boundary histories, reconcile-only history, and evidence merged into the recurring pass stay silent.

- `plan-tool convergence` and the existing completeness stderr hook expose the same recommend-only advisory.

- The bad-fix signal does not change convergence verdicts, `stop_reason`, `--fail-on-findings`, or command exit codes.

- `self-seeded-finding` remains judgment-only in `plan_tool/audit_shapes.py:AUDIT_SHAPES`.

## References

- [Python dataclasses — Data Classes](https://docs.python.org/3/library/dataclasses.html) — Review frozen advisory records and defaulted history-model fields.

- [Python difflib — SequenceMatcher](https://docs.python.org/3/library/difflib.html#difflib.SequenceMatcher) — Review the title-comparison behavior reused through Step 4’s helper.

## Applicable guardrails

- **The plan’s “## Plan intent”, causal-evidence boundary** — require both issue identity and qualified provenance, then emit an advisory only.

- **The plan’s “## Step intent”, bounded-history boundary** — limit evaluation to open newest findings in the required collapsed same-stage history.

- **The plan’s “## Out of scope”, loop-control and mutation boundaries** — do not change exit behavior, stop reasons, plan contents, or automated remedies.

- **The plan’s “## Out of scope”, matcher and evidence boundaries** — leave `_matches` semantics intact and do not add free-form similarity grading or another provenance store.

- **The plan’s “## Out of scope”, audit-shape boundary** — keep `self-seeded-finding` as a judgment-only shape.

## Deferred

- **Hard failure or iterate-stop policy for a bad-fix signal** — future work after this recommend-only advisory has operator evidence in production.

- **Telemetry matcher consolidation** — `plan_tool/telemetry_analysis.py:_strict_finding_match` has separate consumers and is outside this step’s declared files; assess a shared policy in a reconcile step.

- **Provenance documentation and backlog closure** — Step 6 owns the documentation surfaces and backlog update.
