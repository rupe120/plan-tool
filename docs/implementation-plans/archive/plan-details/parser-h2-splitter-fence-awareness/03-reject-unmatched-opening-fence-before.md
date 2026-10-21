> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 3 — Reject unmatched opening fences before parser-driven writes

## Summary

Reject an unmatched opening code fence before any listed parser-driven route changes a durable published target. Reuse step 1’s shared fence result and step 2’s safe H2 readers; check source already known at a command boundary before preferences or lifecycle logs, and check a model-composed candidate immediately before materialization. Keep existing archive, cleanup, rollback, and target ownership behavior unchanged. On green, an operator receives a clear source-path error and the affected published targets remain unchanged.

## Table of Contents

- [Summary](#summary) — The completed behavior and its write-boundary rule.
- [Table of Contents](#table-of-contents) — Links to every section in this detail.
- [Why](#why) — The unsafe partial-read behavior this step stops.
- [Input](#input) — The fence and safe-parser contracts from steps 1 and 2.
- [Files (creates vs edits)](#files-creates-vs-edits) — Production, documentation, and test changes.
- [Implementation](#implementation) — Route-specific preflight and preservation requirements.
- [Tests](#tests) — Regression coverage for every write route.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Markdown and test references.
- [Applicable guardrails](#applicable-guardrails) — Plan boundaries that constrain this step.
- [Deferred](#deferred) — Related work left outside this step.

## Why

An unmatched opening fence makes the H2 reader treat all following text as code, so a route can silently lose real sections and then write a plan, report, seed, or export based on that partial view. Step 1 exposes that condition and step 2 makes closed-fence reads safe; this step makes the remaining unsafe outcome fail clearly before a parser-driven write can publish it.

## Input

- **Step 1 fence result** — Use the shared unmatched-opening signal from `plan_tool/scope_fence.py:_fenced_code_spans` and its fence grammar. Do not add a route-local backtick or tilde scanner.

- **Step 2 safe readers** — Keep using the fence-safe modes of `plan_tool/parser.py:parse_body_sections`, `split_body_sections`, and `plan_tool/scope_fence.py:extract_h2_sections`. This step decides when a detected unmatched opener blocks publication; it does not change their default behavior.

- **Source body selection** — Inspect the same frontmatter-stripped plan or seed body that each route supplies to its H2 reader. Create also checks the assembled body that it will publish, and completeness/reconcile check the resolved `plan.source_seed`, including its archive fallback, before the audit can parse that source or save a report. Do not reject fence-looking text in unrelated YAML, a generated fragment that will not become a plan body, or a document shape this plan does not cover.

## Files (creates vs edits)

- **New files:** None.

- **Existing files (edits only):**
  - `plan_tool/annotate_render.py` — Make `render_annotated_report` and `render_create_seed` reject an unmatched source fence before rendering parser-derived artifacts.
  - `plan_tool/cli/annotate_cmd.py` — Preflight each source in `_annotate_one` before classification, report rendering, output writes, or `--archive`.
  - `plan_tool/cli/authoring.py` — Preflight every raw create seed before `resolve_create_slug` performs its parser-derived read or a model call begins, and a detail plan before `cmd_detail` opens its lifecycle log.
  - `plan_tool/cli/app.py` — Present unmatched-fence failures as known command errors rather than crash reports.
  - `plan_tool/cli/run_cmd.py` — Preflight the selected plan before run preferences or a per-step lifecycle log, including every `--all` sweep iteration.
  - `plan_tool/create.py` — Reject an unsafe source seed in `validate_from_existing_seed`, `_prepare_create_plan`, and direct `create_plan` use before collision archival, plan publication, or manifest mutation; also reject an unsafe assembled plan body before publication.
  - `plan_tool/detail.py` — Reject an unsafe plan body before `generate_detail` reaches `_author_step_detail`, detail archival, or `update_step_detail_field`.
  - `plan_tool/cli/completeness_cmd.py` — Gate completeness processing before it can persist a report or sidecar.
  - `plan_tool/cli/review_cmd.py` — Gate a fresh reconcile before `review_plan_full` and `save_review`; leave saved-report reuse unchanged.
  - `plan_tool/jira.py` — Check only a run-grade paired export in `export_jira` before `_publish_companion_pair`; preserve `render_jira_export` preview behavior.
  - `plan_tool/jira_handoff.py` — Keep `render_handoff_body` a pure renderer for both publishing and preview; expose only the captured plan-body input that `export_jira` validates at the publishing boundary.
  - `plan_tool/cli/jira_cmd.py` — Keep `--no-write` on the render-only path and map paired-export rejection cleanly.
  - `plan_tool/launcher.py` — Stop `run_step` before prompt invocation or status write when its plan body has an unmatched opener.
  - `plan_tool/reprocess.py` — Check both the live plan body and archive source before `reprocess_plan` writes the live plan.
  - `plan_tool/renderer.py` — Carry the run-lane fence failure through `_scope_fence_section` and `render_prompt` without changing unrelated prompt modes.
  - `plan_tool/roadmap_gates.py` — Add a deterministic draft-seed violation in `validate_draft_seed_content` before roadmap materialization can write a seed.
  - `plan_tool/roadmap.py` — Validate an operator-supplied draft before `_roadmap_command_lifecycle` writes a lifecycle receipt, while a model-generated draft validates immediately before materialization.
  - `plan_tool/review.py` — Keep reconcile’s plan-body reads safe and expose the route-level rejection needed before a report is saved.
  - `plan_tool/review_persistence.py` — Validate a resolved source seed, including its archive fallback, before `AuditInputSnapshot.capture` makes it available to audit parsing or report persistence.
  - `plan_tool/scope_out.py` — Reject before `scope_out_step` writes its carved seed or calls `apply_narrow`.
  - `ROADMAP_FORMAT.md` — Document the draft-seed unmatched-fence refusal beside its body-reference validation contract.
  - `tests/test_annotate_render.py`, `tests/test_create.py`, `tests/test_detail.py`, `tests/test_jira.py`, `tests/test_jira_handoff.py`, `tests/test_reprocess.py`, `tests/test_review.py`, `tests/test_review_persistence.py`, `tests/test_scope_out.py`, `tests/test_launcher.py`, `tests/test_renderer.py`, `tests/test_roadmap.py`, `tests/test_roadmap_gates.py`, `tests/test_roadmap_format.py`, `tests/cli/test_annotate_cmd.py`, `tests/cli/test_app.py`, `tests/cli/test_authoring_cmds.py`, `tests/cli/test_completeness_cmd.py`, `tests/cli/test_jira_cmds.py`, `tests/cli/test_review_cmds.py`, and `tests/cli/test_run_cmd.py` — Add route-specific refusal and unchanged-target coverage.

## Implementation

- **Foundational logic: refuse a parser-driven write when its source body has an unmatched opening fence.** Use step 1’s shared result as the only authority. The error must name the source path and explain that the opening fence needs a matching closure.

- **Check before the first published target side effect.** Do not rely on rollback after a target changes. The rejection point must precede output-directory creation, temporary paired-export staging, collision archival, manifest updates, detail replacement, plan pointer updates, report persistence, and scope-out seed creation. When a known source is available at command entry, preflight it before run preferences or `RunLogWriter.start`; a model-composed candidate can only be checked after model work, and its existing run log remains the refusal receipt while every published target stays unchanged.

- **Keep the check at route boundaries.** A global write wrapper cannot know whether a write came from an H2-derived interpretation and would broaden this step beyond its contract. Put narrow direct-API checks at `plan_tool/create.py:create_plan`, `plan_tool/detail.py:generate_detail`, `plan_tool/reprocess.py:reprocess_plan`, `plan_tool/scope_out.py:scope_out_step`, `plan_tool/launcher.py:run_step`, and the report/export entry points. Mirror those checks before command state writes at `plan_tool/cli/annotate_cmd.py:_annotate_one`, `plan_tool/cli/authoring.py:cmd_detail`, `plan_tool/cli/run_cmd.py:cmd_run` and `_cmd_run_sweep`, `plan_tool/cli/review_cmd.py:_run_logged_audit`, and the roadmap materialization entry.

- **Preflight known command sources before operational state.** `cmd_run` must check before `_save_run_prefs` and before its single-step log; `_cmd_run_sweep` must recheck each re-parsed plan before that iteration’s log because earlier steps can change it. `cmd_detail` and a fresh reconcile must check before `_run_logged_audit` / `RunLogWriter.start`. An operator-supplied roadmap draft checks before `_roadmap_command_lifecycle`; a model-generated draft checks after generation and before materialization, retaining the active lifecycle log as a failure receipt.

- **Preflight every create body before it can be interpreted or published.** `plan_tool/cli/authoring.py:cmd_create` must reject an unsafe raw `seed_body`, description, or `--from-existing` source before `resolve_create_slug` parses it. `plan_tool/create.py:_prepare_create_plan` and any rebound distilled seed must repeat the same narrow validation before their own parser-derived reads, so direct APIs cannot bypass the command boundary. After model work composes the final candidate body, validate that assembled plan body before collision archival, plan publication, or manifest mutation; a generated fragment that never becomes the plan body is not a refusal target.

- **Preflight audit origin seeds before audit parsing or persistence.** `plan_tool/review_persistence.py:AuditInputSnapshot.capture` must validate the resolved `plan.source_seed` bytes, including `latest_seed_archive` fallback, before `plan_tool/review.py:_format_scope_contract_block` can parse them and before completeness or reconcile saves a report. Preserve the current no-seed/unreadable-seed behavior; only a readable matched source in the plan/seed H2 shape gets the fence refusal.

- **Make live H2 rewriters fence-safe too.** `plan_tool/create.py:_patch_plan_body_section` and `plan_tool/reprocess.py:_substitute_todo_sections` must select and bound real headings with the shared parser rule. A closed fenced pseudo-heading remains source text: create must not patch it, and reprocess must not substitute a `_(TODO)_` inside it.

- **Keep preview renderers pure; fence only publishing.** `plan_tool/annotate_render.py:render_create_seed` and `plan_tool/renderer.py:render_prompt` retain their direct validation seams. `plan_tool/jira_handoff.py:render_handoff_body` is shared by `render_jira_export` and `--no-write`, so it must render an unmatched body without refusing. `plan_tool/jira.py:export_jira` instead validates the captured run-grade plan body before `_publish_companion_pair`; Jira-grade export and render-only preview do not inherit that publishing rule.

- **Preserve closed-fence behavior.** A properly closed backtick or tilde block remains valid, and headings inside it remain non-headings under step 2’s safe parsing. Do not repair, strip, or reinterpret an unmatched fence; reject it.

- **Preserve create and detail lifecycle behavior.** `plan_tool/create.py:archive_existing_source`, `plan_tool/detail.py:_archive_existing_detail`, `_author_step_detail`, and `update_step_detail_field` must remain untouched on rejection. Direct API callers must receive the module’s established error type rather than a partial result.

- **Preserve reprocess and scope-out recovery rules.** `plan_tool/reprocess.py:reprocess_plan` must leave both input files unchanged. `plan_tool/scope_out.py:scope_out_step` must reject before its seed-first write, leaving `apply_narrow` and its journal rollback behavior unchanged for ordinary later failures.

- **Keep run rejection before the backend.** `plan_tool/launcher.py:run_step` must reject before `render_prompt` can lead to an invoker call, including under `dry_run`. Keep existing prompt-build logging and normal run-state behavior unchanged for valid input.

- **Limit Jira rejection to run-grade publication.** `plan_tool/jira.py:export_jira` validates its captured `plan_tool/jira_handoff.py:HandoffRenderInput` body only on the run-grade publishing path before `_publish_companion_pair`. `plan_tool/cli/jira_cmd.py:_cmd_jira_paired_export` keeps `--no-write` render-only, and jira-grade behavior does not gain this retired scanner’s contract.

- **Stop report persistence, not report semantics.** `plan_tool/cli/completeness_cmd.py:cmd_completeness` and `plan_tool/cli/review_cmd.py:_cmd_review_body` must reject before `write_completeness_report` or `save_review`. Keep successful report formats, report paths, reuse behavior, and existing sidecar schemas unchanged.

- **Use roadmap’s existing gate channel.** Add an explicit violation through `plan_tool/roadmap_gates.py:validate_draft_seed_content`, so generated draft seeds retry and operator-supplied seeds refuse before materialization. Keep violation messages self-contained and anchored to the draft seed and plan row, not a line number.

- **Document the exact roadmap rule once.** Update `ROADMAP_FORMAT.md`’s draft-seed section to name the unmatched-opening-fence refusal and its enforcing gate. Do not broaden the document into a general Markdown parser reference.

## Tests

- `tests/cli/test_annotate_cmd.py::test_unmatched_opening_fence_skips_classifier_outputs_and_archive` — An unsafe source produces no report or seed, does not invoke classification, and leaves an archive request untouched.

- `tests/test_annotate_render.py::test_direct_annotate_renderers_reject_unmatched_source_fence` — Direct report and create-seed renderer calls reject their unsafe source instead of relying on the CLI wrapper.

- `tests/test_create.py::test_create_rejects_unmatched_seed_before_collision_archive_manifest_or_model` — A rejected source seed creates no plan, does not archive an existing collision, and does not mutate the manifest.

- `tests/test_create.py::test_create_preflights_raw_and_rebound_seed_before_slug_or_model` — Raw descriptions, inline seeds, `--from-existing` content, and a rebound distilled seed fail before their first parser-derived read or model work.

- `tests/test_create.py::test_create_rejects_unmatched_assembled_body_before_publication` — A model-composed plan body with an unmatched opener reaches no collision archive, plan, or manifest write.

- `tests/test_create.py::test_patch_plan_body_section_ignores_closed_fenced_pseudo_heading` — A live closed-fence example named like the target section remains unchanged while the real section is patched.

- `tests/test_detail.py::test_generate_detail_rejects_unmatched_plan_before_detail_archive_or_pointer_update` — An unsafe plan leaves an existing detail body and its `step.detail` pointer unchanged.

- `tests/cli/test_authoring_cmds.py::test_detail_unmatched_fence_opens_no_run_log` — A known unsafe plan fails before detail command lifecycle artifacts appear.

- `tests/test_reprocess.py::test_reprocess_rejects_unmatched_fence_in_live_or_archive_source_without_mutation` — Unsafe live and archive inputs each leave the live plan unchanged.

- `tests/test_reprocess.py::test_substitute_todo_sections_ignores_closed_fenced_pseudo_heading` — A `_(TODO)_` in a closed fence remains unchanged while a real section can be substituted.

- `tests/test_scope_out.py::test_scope_out_rejects_unmatched_fence_before_seed_or_narrow` — No carved seed, detail migration, or plan narrowing occurs.

- `tests/test_renderer.py::test_run_grade_render_rejects_unmatched_plan_body` — Run rendering with a plan path raises the route-owned fence error instead of producing a partial scope fence.

- `tests/test_launcher.py::test_run_step_unmatched_fence_never_reaches_invoker_or_plan_write` — Normal and dry-run execution reject before the backend and preserve plan state.

- `tests/cli/test_run_cmd.py::test_run_unmatched_fence_writes_no_preferences_or_run_log` and `tests/cli/test_run_cmd.py::test_run_sweep_rechecks_before_each_iteration_log` — Single-step and sweep command boundaries leave no operational state for a known unsafe plan.

- `tests/test_jira_handoff.py::test_handoff_preview_renders_unmatched_plan_body` — The shared pure handoff renderer remains available to preview the captured source without publishing it.

- `tests/test_jira.py::test_run_grade_paired_export_rejects_before_staging_or_replacing_targets` — Existing story and handoff targets remain unchanged and no staged companion file remains.

- `tests/test_jira.py::test_jira_grade_export_does_not_adopt_run_grade_fence_rejection` — The run-grade-only boundary remains explicit.

- `tests/cli/test_jira_cmds.py::test_no_write_keeps_render_only_behavior_for_unmatched_run_grade_body` — `--no-write` does not enter the paired-publication gate.

- `tests/cli/test_completeness_cmd.py::test_unmatched_fence_writes_no_completeness_report_or_sidecar` — Completeness rejects before report persistence and backend audit work.

- `tests/test_review_persistence.py::test_audit_snapshot_rejects_unmatched_archived_source_seed` and `tests/cli/test_completeness_cmd.py::test_unmatched_archived_source_seed_writes_no_report_or_sidecar` — Archive fallback source-seed parsing refuses before either direct audit capture or CLI report persistence.

- `tests/test_review.py::test_reconcile_rejects_unmatched_plan_before_review_invocation_or_saved_report` — A fresh reconcile does not invoke review work or create a saved report.

- `tests/cli/test_review_cmds.py::test_fresh_reconcile_unmatched_fence_opens_no_run_log` — A known unsafe plan rejects before its logged audit lifecycle begins; saved-report reuse remains unchanged.

- `tests/cli/test_app.py::test_unmatched_fence_is_reported_as_a_known_command_error` — Top-level command handling returns a normal error result without a crash trace.

- `tests/test_roadmap_gates.py::test_draft_seed_unmatched_opening_fence_is_a_materialization_violation` — Draft-seed validation returns the dedicated actionable violation.

- `tests/test_roadmap.py::test_unmatched_operator_draft_rejects_before_lifecycle_log` and `tests/test_roadmap.py::test_unmatched_generated_draft_keeps_only_failure_receipt_before_materialization` — A known draft opens no lifecycle log, while a model-generated draft leaves no materialized seed and retains only its already-started failure receipt.

- `tests/test_roadmap_format.py::test_draft_seed_fence_refusal_documentation_names_its_gate` — The documented rule names the current enforcing validator.

Every listed test must be green before this step is complete.

## Acceptance criteria

- An unmatched opening fence in a parser-derived source causes each listed write route to fail with a source-path error before its first published target change; a known command source is rejected before preferences or lifecycle logs, while a model-composed candidate may retain only its failure receipt.

- A rejected annotate, create, detail, reprocess, scope-out, run, completeness, or reconcile route leaves its existing published targets unchanged, including when create assembled its final body or audit resolved an archived source seed.

- Direct annotate renderers reject an unmatched source fence, raw create source forms reject before slug resolution, parser-derived reads, or model work, and an unsafe model-composed candidate body rejects before publication.

- A rejected run does not invoke its backend, including with `--dry-run`.

- A rejected run-grade Jira paired export does not stage, replace, archive, or otherwise alter either target, while `render_handoff_body` and `--no-write` remain render-only.

- Jira `--no-write` remains render-only, and jira-grade export does not inherit the run-grade publication rule.

- Roadmap draft-seed validation reports an actionable unmatched-fence violation before materialization writes a seed.

- Closed fences and fenced pseudo-headings retain step 2’s safe-reader behavior.

- Closed fenced pseudo-headings are never patched by create or substituted by reprocess.

- The focused test files listed above pass.

## References

- [CommonMark Spec — Fenced code blockshttps: — Use the matching and end-of-document rules already reflected in the shared scanner.

- [CommonMark Spec — ATX headingshttps: — Confirm that only headings outside a fenced block form plan-body sections.

- [Python 3.13 `re` documentationhttps: — Reference multiline matching and source spans when working with the shared detector.

- [pytest parametrization documentationhttps: — Use parameterization where the same unmatched-fence case reaches multiple route boundaries.

## Applicable guardrails

- **The plan’s “## Plan intent”.** Keep all work focused on real H2 boundaries and the listed consumers; do not add a separate Markdown parsing system.

- **The plan’s “## Step intent”.** Reject before a truncated H2 read can produce or modify a target. Do not repair source text as part of this route.

- **The plan’s “## Out of scope”, allowed behavior changes.** Limit behavior changes to safe closed-fence parsing and unmatched-opening refusal at the named write routes.

- **The plan’s “## Out of scope”, parser and Jira-grade exclusions.** Do not change parser defaults, `plan_tool/detail.py:parse_detail_file_sections`, or the retiring Jira-grade scanner.

- **The plan’s “## Out of scope”, reorganization boundary.** Keep the existing writer and rollback structure; do not use this work to reorganize unrelated command flows.

## Deferred

- `plan_tool/jira_grade.py` legacy unterminated-fence validation — The plan’s “## Out of scope” assigns this retiring lane to its separate removal work.

- Global unmatched-fence enforcement for unrelated Markdown formats — Those formats do not share the plan and seed H2 contract this step protects.
