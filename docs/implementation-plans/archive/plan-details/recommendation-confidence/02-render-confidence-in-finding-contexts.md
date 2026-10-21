> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 2 — Render confidence in user and LLM finding contexts

## Summary

Show one evidence-support label for user-facing `Recommendation` output and direct LLM prompts that act on a finding, using the same `supported`, `limited`, or `unknown` wording. The label is display-only in those prompts: it cannot change the supplied remedy or verdict. Add one shared display projection near `plan_tool/review.py:Recommendation`, then use it wherever those contexts format a finding’s severity, title, or body. Preserve the stored confidence through `CarriedFinding` and `RunFinding` rather than deriving it again from source or severity. On green, a legacy `None` value displays as `confidence: unknown`, while existing finding identity, severity, selection, and control flow stay unchanged.

## Table of Contents

- [Summary](#summary) — The reader-facing outcome and shared display rule.
- [Table of Contents](#table-of-contents) — Links to every section in this detail.
- [Why](#why) — Why evidence support must be visible apart from severity.
- [Input](#input) — The upstream classification and persistence contracts this step reads.
- [Files (creates vs edits)](#files-creates-vs-edits) — The reader surfaces and focused tests in scope.
- [Implementation](#implementation) — The required label, projection, and behavior boundaries.
- [Tests](#tests) — Focused coverage for user and prompt contexts.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Primary references for optional values and CLI output tests.
- [Applicable guardrails](#applicable-guardrails) — Plan boundaries that keep confidence informational.
- [Deferred](#deferred) — Related work this reader step does not take on.

## Why

`Recommendation` already carries severity, source, and text, but a user or LLM acting on a finding cannot tell whether it came from a directly checked predicate, a limited heuristic, or a legacy record without opening saved JSON. Step 1 supplies a classified, legacy-safe stored value; this step makes that distinction visible in user output and direct LLM finding prompts. A label must follow the stored value, not a source-name rule, because source names can be shared by findings with different evidence and a legacy record has no new classification to infer.

## Input

- **Step 1 classification and persistence:** `plan_tool/review.py:Recommendation`, `plan_tool/review_persistence.py:_load_recommendations`, and `plan_tool/purity_cache.py:_entry_from_json` supply classified new values or `None` for legacy unknown. This step renders but does not decide or normalize them.
- **Projection types:** `plan_tool/review.py:CarriedFinding` and `plan_tool/convergence_diagnosis.py:RunFinding` currently retain selected finding fields for later prompts and history. They must retain confidence as well so those readers do not lose the stored result.
- **Reader boundary:** Cover human-facing `Recommendation` output and direct LLM prompts that act on a finding. In those prompts, confidence is display-only and cannot alter the supplied remedy or verdict. Keep scope-guard handoffs, split-criteria diagnostics, issue-shaped summaries, and model verdict parsing on their existing derived-record contracts.

## Files (creates vs edits)

- **New files:** None.

- **Existing files (edits only):**
  - `plan_tool/review.py` — Add the canonical confidence display projection near `Recommendation`; preserve confidence in `assemble_carried_findings`, and render it in `assemble_report`, `emit_triage_summary`, `_format_carried_findings_block`, and `_render_extract_lessons_prompt`.
  - `plan_tool/review_walk.py` — Show the label in `_format_recommendation` and already-annotated skip notices without changing walk selection or actions.
  - `plan_tool/create.py` — Show the stored label with the granularity-split hint and carry it through `_converge_create_plan` direct LLM finding prompts.
  - `plan_tool/cli/review_cmd.py` — Add the label to the saved-review summaries emitted when a walk cannot run.
  - `plan_tool/cli/review_actions.py` — Carry the canonical label through `_dispatch_apply_finding` into its direct LLM finding prompt.
  - `plan_tool/completeness_report.py` — Render confidence in `_fmt_finding_line`, `_fmt_pending_line`, and the applied-finding summary paths.
  - `plan_tool/cli/completeness_phases.py` — Add the label to `_finding_progress_label`, the grouped completeness report, public JSON projections, and `_run_iterate_convergence_loop` direct LLM finding prompts.
  - `plan_tool/cli/completeness_apply_parallel.py` — Carry the same label into isolated direct LLM finding prompts.
  - `plan_tool/cli/reconcile.py` — Include the label in direct reconcile notices, including redirect output, while leaving reuse and walk behavior unchanged.
  - `plan_tool/detail.py` — Render the label in `emit_detail_findings_summary` and `_emit_split_recommendations`, and carry it through `_converge_run_grade_step_detail` direct LLM finding prompts.
  - `plan_tool/cli/inspect.py` — Render the label for `cmd_validate` smell and convergence-blocking output.
  - `plan_tool/cli/data_contract_cmd.py` — Include the label in `_finding_label` for skipped and non-interactive data-contract findings.
  - `plan_tool/convergence_diagnosis.py` — Preserve confidence in `RunFinding` and show it when `render_diagnosis` names stored findings.
  - `plan_tool/launcher.py` — Render preserved carried-finding confidence in `_format_carried_context_block`, and preserve the canonical label in `apply_finding` and `_format_findings_as_body` direct LLM prompts.
  - `plan_tool/prompts/apply-finding.md` — State the common direct-apply rule that confidence is display-only and does not alter the supplied remedy or verdict.
  - `plan_tool/prompts/extract-lessons-review.md` — Permit confidence only as an evidence-support qualifier in a synthesized lesson, never as a reason to weaken or reclassify the source finding.
  - `tests/test_review.py` — Cover the canonical label, review output, and carried-finding preservation.
  - `tests/test_review_walk.py` — Cover interactive and already-annotated supported, limited, and legacy-unknown rendering.
  - `tests/test_create.py` — Cover the confidence label in the create-time granularity hint.
  - `tests/test_lessons.py` — Cover the confidence label in the review lesson-extraction prompt.
  - `tests/cli/test_review_actions.py` — Cover a review-walk direct LLM finding prompt without changing apply behavior.
  - `tests/test_completeness_report.py` — Cover persisted report and applied-summary labels.
  - `tests/cli/test_completeness_cmd.py` — Cover progress, grouped output, and JSON labels.
  - `tests/cli/test_completeness_apply_parallel.py` — Cover isolated direct LLM finding prompts.
  - `tests/cli/test_reconcile_engine.py` — Cover reconcile notices that bypass the interactive walk.
  - `tests/cli/test_inspect_cmds.py` — Cover `validate` output labels.
  - `tests/cli/test_data_contract_cmd.py` — Cover data-contract apply labels before the walk starts.
  - `tests/test_convergence_diagnosis.py` — Cover stored-value preservation and history rendering.
  - `tests/test_detail.py` — Cover detail-quality and split recommendation output.
  - `tests/test_launcher.py` — Cover carried context supplied to follow-up prompts.
  - `tests/cli/test_review_cmds.py` — Cover non-interactive saved-review summaries.
  - `tests/test_cli.py` — Cover end-to-end CLI output without changing exit behavior.

## Implementation

- **Use one canonical label.** Add a small shared formatter associated with `plan_tool/review.py:Recommendation` that renders exactly `confidence: supported`, `confidence: limited`, or `confidence: unknown`. Map only stored `None` to `unknown`; valid non-null values keep their existing meaning.

- **Keep display separate from classification.** Do not recompute confidence from `source`, `severity`, `impact`, anchors, or whether the finding is currently applyable. The rejected approach is per-reader source inference: it would misclassify legacy records and source-name collisions, then drift as new producers are added.

- **Keep the formatter pure.** Rendering a legacy value must not mutate a `Recommendation`, a saved review, or a cache entry. Step 1 owns validation and persistence normalization; this step only turns an already-safe stored value into visible text.

- **Render the label beside the existing finding identity.** Update the reader anchors in `plan_tool/review.py:assemble_report`, `plan_tool/review_walk.py:_format_recommendation`, `plan_tool/completeness_report.py:_fmt_finding_line`, and `plan_tool/cli/completeness_phases.py:_finding_progress_label` so a reader sees severity and confidence together without losing the current source, anchor, title, body, or suggested action.

- **Cover all completeness projections.** `plan_tool/cli/completeness_phases.py:_render_grouped_report` has several direct recommendation loops, while `plan_tool/completeness_report.py:build_report_md` has summary and applied paths. Route each through the same display rule, including the public `--json` recommendation projections, so a legacy record is reported as `unknown` rather than JSON `null` on the reader-facing surface.

- **Preserve confidence through later views.** Extend `plan_tool/review.py:CarriedFinding` and `plan_tool/convergence_diagnosis.py:RunFinding` with defaulted optional confidence fields. `assemble_carried_findings`, `plan_tool/review.py:_format_carried_findings_block`, `plan_tool/launcher.py:_format_carried_context_block`, `plan_tool/convergence_diagnosis.py:_finding_from_recommendation`, and the finding-title rendering used by `render_diagnosis` must retain and show the same label. Keep constructor compatibility for existing callers by defaulting the added projection fields.

- **Update non-walk readers.** Add the same label to `plan_tool/cli/review_cmd.py` saved-review reuse summaries, `plan_tool/cli/reconcile.py` redirect notices, `plan_tool/cli/inspect.py:cmd_validate`, `plan_tool/cli/data_contract_cmd.py:_finding_label`, and the two detail emitters. These paths matter because they display findings without passing through `walk_recommendations`.

- **Cover creation and follow-up-prompt readers.** Prefix each line from `plan_tool/create.py:_granularity_split_hints` with the canonical label before `_ask_change_type` prints it. In `plan_tool/review.py:_render_extract_lessons_prompt`, include the same label in every structured finding line passed to `extract-lessons-review.md`. In that template, allow the label only to qualify the evidence support of an extracted lesson; it cannot weaken, reclassify, or suppress its source finding. These contexts steer a human or a later model, so neither may infer or silently drop the stored value.

- **Cover pre-skipped walk findings.** `plan_tool/review_walk.py:walk_recommendations` formats an already-annotated finding directly instead of calling `_format_recommendation`; add the canonical label to that notice as well. Keep the existing skip, rewalk, and failed-annotation decisions unchanged.

- **Treat a direct LLM finding prompt as a reader.** Add one canonical recommendation-to-apply representation that includes the stored confidence label with the existing severity, title, and body. Pass it instead of raw `rec.body` at every `apply_finding` boundary: review-action dispatch, create convergence, run-grade detail convergence, serial completeness convergence, and isolated parallel completeness apply. In the shared `apply-finding.md` template, state that the label is display-only: follow the supplied remedy and verdict regardless of confidence, and never skip, narrow, defer, reprioritize, or otherwise change requested work because of it. Scope-guard handoffs remain raw finding bodies because they record derived out-of-scope work rather than render or act on a `Recommendation`.

- **Preserve retry context.** `plan_tool/launcher.py:_format_findings_as_body` constructs the one automatic follow-up prompt after an apply introduces deterministic findings. Render the same stored label in each single or bundled finding there. These are presentation-only changes: keep targeted fixes, operator feedback, finding ids, scope evaluation, apply dispatch, retry count, and all verdict or exit behavior unchanged.

- **Do not change decision behavior.** Leave `plan_tool/review_walk.py:walk_recommendations`, `plan_tool/review.py:triage_reason`, `plan_tool/cli/completeness_phases.py:_completeness_has_blocking_findings`, and launcher verdict handling dependent on their current fields. Confidence is display-only context: it cannot change filtering, ordering, annotations, apply dispatch, a supplied remedy or verdict, blocking, convergence, or exit codes.

## Tests

### Tests for this step

- `tests/test_review.py::test_confidence_label_renders_stored_values_without_reclassification` — The shared projection emits the three exact labels from stored values rather than severity or source.
- `tests/test_review.py::test_carried_finding_rendering_preserves_stored_confidence` and `tests/test_review.py::TestAssembleReportWalkMode::test_walk_mode_omits_recommendation_lines_but_default_renders_them` — Carried findings retain their value, and the non-walk report renders it without reintroducing the interactive-walk duplicate.
- `tests/test_review_walk.py::TestWalkOutput::test_recommendation_shows_stored_confidence_without_changing_actions` and `tests/test_review_walk.py::TestWalkRecommendationsSkipsAnnotated::test_already_annotated_items_skipped_by_default` — Interactive and already-annotated skip output include the label while actions and annotations remain unchanged.
- `tests/test_create.py::TestGranularitySplitHints::test_split_hints_render_stored_confidence` — The create-time hint carries the stored label without modifying its split recommendation.
- `tests/test_lessons.py::test_review_lesson_prompt_includes_stored_confidence` — The review follow-up prompt carries each finding’s stored label and allows it only as an evidence-support qualifier.
- `tests/cli/test_review_actions.py::TestOperatorFeedbackSteersApply::test_apply_finding_consumes_and_clears_operator_feedback` and `tests/cli/test_review_actions.py::TestInteractiveApplyVerdictOwnership::test_validation_lines_render_stored_confidence` — Review applies carry the display-only label to the model prompt and to the post-apply validation lines without changing the supplied remedy or verdict.
- `tests/test_completeness_report.py::test_finding_lines_render_stored_legacy_confidence` and `tests/test_completeness_report.py::test_report_lists_applied_with_verdicts` — Persisted report lines and applied summaries render legacy values as `unknown`.
- `tests/cli/test_completeness_cmd.py::TestFindingProgressLabel::test_formats_source_severity_and_title`, `tests/cli/test_completeness_cmd.py::TestRenderCompletenessJson::test_json_renders_legacy_confidence_as_unknown`, and `tests/test_cli.py::TestCmdCompletenessConceptWiring::test_iterate_writes_report_and_concise_summary` — Progress text, public JSON, and the saved grouped report retain the reader-facing value.
- `tests/cli/test_completeness_cmd.py::TestCarriedFindingsWiring::test_apply_walks_both_sources_correctness_first` and `tests/cli/test_completeness_apply_parallel.py::TestApplyFindingInTree::test_worker_passes_finding_body_and_step_id` — Serial and isolated parallel completeness apply prompts retain the stored label.
- `tests/cli/test_reconcile_engine.py::TestWalkSavedRunReconcileExitCodes::test_redirect_replay_renders_stored_confidence` — A direct reconcile notice retains the finding’s stored label.
- `tests/cli/test_inspect_cmds.py::TestCmdValidate::test_valid_plan_with_smells_prints_advisory_block_and_exits_0` and `tests/cli/test_data_contract_cmd.py::test_finding_label_renders_stored_legacy_confidence` — Inspection and data-contract readers display the label without changing their control paths.
- `tests/test_convergence_diagnosis.py::test_render_edit_drift_advisory_names_majority_and_matched_findings` and `tests/test_convergence_diagnosis.py::test_capped_confidence_labels_signal_omitted_findings` — Convergence history renders the same canonical label and keeps paired capped lists equally complete.
- `tests/test_detail.py::TestEmitDetailFindingsSummary::test_anchor_tag_only_when_present` and `tests/test_detail.py::TestGenerateDetailIterationLoop::test_dedup_dispatches_each_finding_once` — Detail-quality output and direct detail convergence prompts retain the label.
- `tests/test_create.py::TestCreatePlanIterationLoop::test_iteration_dedups_apply_dispatch_and_keeps_finding_open` — Create convergence passes the stored label without changing its apply lifecycle.
- `tests/test_launcher.py::TestApplyFindingDryRunStructuralOption::test_carried_findings_excerpt_line` and `tests/test_launcher.py::TestFormatFindingsAsBody::test_multi_finding_includes_directive_and_numbering` — Carried context plus single and bundled retry bodies include stored confidence while preserving prompt grammar.
- `tests/cli/test_review_cmds.py::TestPromptReuseSavedReviewFlags::test_review_safe_reuse_dispatch_modes` — A saved review reported without a TTY does not omit the label.

Every listed test must be green before this step is considered finished. Run the focused tests while implementing, then run `uv run pytest tests/ -q -n auto`.

## Acceptance criteria

- User-facing Recommendation output shows one `confidence: supported`, `confidence: limited`, or `confidence: unknown` label beside its existing finding information.
- A stored `None` value renders as `confidence: unknown` in review, completeness, reconcile, detail, inspection, data-contract, creation, lesson-extraction prompt, carried-finding, and convergence-history output.
- Direct LLM finding prompts, including automatic retry prompts, render that same stored label as display-only context and preserve the supplied remedy and verdict regardless of confidence.
- No reader derives confidence from source, severity, anchor, triage metadata, or current apply state.
- `CarriedFinding` and `RunFinding` preserve the stored optional value instead of dropping or reclassifying it.
- Completeness Markdown and public JSON projections render the reader-facing unknown label without changing the persisted sidecar’s legacy-safe value.
- Existing finding IDs, severity, ordering, walk behavior, apply behavior, blocking decisions, convergence decisions, and exit codes remain unchanged; lesson extraction can only describe evidence support, not weaken or reclassify a source finding.
- The focused tests and `uv run pytest tests/ -q -n auto` pass.

## References

- [dataclasses — Data Classes — Python 3.13 documentationhttps: — Use for compatible defaulted fields on carried and history projections.
- [typing — Support for type hints — Python 3.13 documentationhttps: — Use for the distinction between a stored legacy `None` and fresh confidence values.
- [json — JSON encoder and decoder — Python 3.13 documentationhttps: — Use for public completeness JSON rendering without changing persistence semantics.
- [How to capture stdout/stderr output — pytest documentationhttps: — Use for console-reader assertions.

## Applicable guardrails

- **The plan’s “## Plan intent”, evidence support separate from severity** — Render confidence as context only; do not change severity meaning or let the label make a calibration claim.
- **The plan’s “## Step intent”, user and LLM finding contexts** — Cover the human output and direct LLM prompt contexts named in this step’s file list, including non-interactive and history paths.
- **The plan’s “## Out of scope”, informational confidence** — Do not change gates, exit codes, apply handling, blocking, or convergence behavior.

## Deferred

- Annotate-section confidence — Annotate has a separate confidence contract and remains outside this `Recommendation` reader sweep.
- Confidence calibration or benchmarking — BACKLOG #216 first measures
  deterministic corpus noise floors. This step displays deterministic support
  categories and does not measure probability, calibration, or a decision
  rule.
- Scope-guard handoffs and split-criteria diagnostics — These derived internal records stay outside the confidence display contract unless a future consumer needs their own confidence comparison.
