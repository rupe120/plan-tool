> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 4 — Refuse enrolled roadmaps before legacy artifact, baseline, seed, or journal overwrites and deletes while preserving unversioned writes

## Summary

Refuse legacy roadmap writers immediately after step 3’s accepted-head boundary identifies a roadmap as enrolled. Update the shared legacy publication checks in `plan_tool/roadmap_revision_publish.py`, the direct stage and seed entry points in `plan_tool/roadmap.py`, and the runner and CLI paths that must stop before backend or evaluator work. Keep the shared generation transaction available to immutable version enrollment and promotion. On green, no candidate-lifecycle step can run with an enrolled roadmap whose legacy artifacts, baselines, seeds, seed state, or legacy journal remain writable, while unversioned roadmaps retain current behavior.

## Table of Contents

- [Summary](#summary) — The refusal outcome and its compatibility boundary.
- [Table of Contents](#table-of-contents) — Links to each section.
- [Why](#why) — Why accepted-head authority needs a legacy-writer fence.
- [Input](#input) — The version, writer-token, and journal contracts this step reads.
- [Files (creates vs edits)](#files-creates-vs-edits) — The existing writer, runner, CLI, and test files to update.
- [Implementation](#implementation) — The shared enrollment check, protected write paths, and allowed exceptions.
- [Tests](#tests) — Refusal, no-side-effect, version-recovery, and unversioned regression coverage.
- [Acceptance criteria](#acceptance-criteria) — Observable completion conditions.
- [References](#references) — Durable replacement behavior used by the existing journal boundary.
- [Applicable guardrails](#applicable-guardrails) — Plan limits on this narrow writer fence.
- [Deferred](#deferred) — Legacy workflow migration that remains outside this step.

## Why

`plan_tool/roadmap_revision_publish.py` and `plan_tool/roadmap.py` still contain routes that replace roadmap artifacts, baselines, seed state, draft seeds, promoted seeds, and journal members in place. Once step 3 selects an accepted head, those routes can create a second source of roadmap authority. Refuse them before any mutation while retaining the old behavior for roadmaps that have not enrolled.

## Input

- **Accepted-head decision:** Step 3 provides `plan_tool/roadmap_versions.py:is_roadmap_enrolled()` and `load_accepted_version()` as the only enrollment decision. Treat a selected accepted head as enrolled; do not infer enrollment from a baseline, version directory, or live artifact contents.

- **Writer lease:** `plan_tool/roadmap_revision_publish.py:RoadmapWriterToken`, `roadmap_writer_guard()`, and `require_roadmap_writer_token()` serialize roadmap mutations. Check enrollment while the active matching token is held.

- **Journal ownership:** `plan_tool/roadmap_source_identity.py:PendingGeneration`, `GenerationMember`, and `pending_generation_path()` identify a transaction that can replace or delete recorded members during `plan_tool/roadmap_revision_publish.py:recover_roadmap_publication()`.

- **Seed writers:** `plan_tool/roadmap.py:accept_roadmap_seed()`, `apply_roadmap_seeds()`, `materialize_plan_seed()`, `materialize_and_diff_one_plan()`, and `refresh_roadmap_seeds()` can write draft or promoted seeds and seed lifecycle state.

## Files (creates vs edits)

- **New files:** None.

- **Existing files (edits only):**
  - `plan_tool/roadmap_revision_publish.py` — Add the shared enrolled-roadmap refusal for legacy publishers, seed invalidation, and legacy journal recovery.
  - `plan_tool/roadmap.py` — Apply the refusal before legacy stage, baseline, and seed entry points can invoke a backend or write roadmap-derived files.
  - `plan_tool/cli/roadmap_cmd.py` — Preflight `--materialize` before it opens its lifecycle, invokes a backend, or writes a refresh report.
  - `plan_tool/roadmap_revision_run.py` — Map enrolled local feedback revision to its preflight-rejected result before invocation.
  - `plan_tool/roadmap_structural_revision_run.py` — Refuse an enrolled structural revision before evaluator setup or invocation.
  - `plan_tool/roadmap_feedback_reopen.py` — Refuse a confirmed feedback reopen before source mutation.
  - `tests/test_roadmap.py` — Cover direct stage, baseline, and seed writer refusal and unversioned behavior.
  - `tests/cli/test_roadmap_cmd.py` — Cover the direct materialize route and unchanged HTML view behavior.
  - `tests/test_roadmap_revision_publish.py` — Cover shared publication and recovery boundaries.
  - `tests/test_roadmap_revision_run.py` — Cover local revision refusal before its backend seam.
  - `tests/test_roadmap_structural_revision_run.py` — Cover structural refusal before evaluator and backend seams.
  - `tests/test_roadmap_feedback_reopen.py` — Cover confirmed reopen refusal without publication.
  - `tests/test_roadmap_impact_run.py` — Preserve immutable impact-evidence publication for an enrolled roadmap without a pending legacy journal.

## Implementation

- **Foundational logic:** A roadmap with an accepted head is not writable through any legacy in-place route.

- **Use one deterministic enrollment check.** Add a token-checked legacy-writer guard near `plan_tool/roadmap_revision_publish.py:require_roadmap_writer_token()`. It must use step 3’s enrollment boundary, allow a missing accepted head, and refuse an unreadable or invalid accepted-head record rather than falling back to legacy mutation. Keep imports acyclic; a deferred read-time import is one acceptable approach if `plan_tool/roadmap_versions.py` depends on the publication module.

- **Fence legacy wrappers, not the shared transaction.** Apply the guard to `preinvalidate_roadmap_seeds()`, `enroll_stage_baselines()`, `publish_stage_artifact()`, `publish_revision_candidate()`, `publish_feedback_reopen_candidate()`, and `publish_structural_revision_proof()`. Do not add an unconditional enrolled-roadmap check inside the generation publisher currently anchored at `plan_tool/roadmap_revision_publish.py:_publish_generation()`: steps 3 and 9 need that shared durable boundary for version-owned records.

- **Preserve only the required version-owned recovery.** `recover_roadmap_publication()` must return unchanged when no journal exists. With an enrolled roadmap and a pending legacy journal, it must refuse before replacing members, unlinking the journal, rolling back, or completing the generation. The only pending generation it may recover after enrollment is step 9’s selector-only promotion: exactly one member at step 3’s fixed accepted-head path whose old and replacement bytes both parse as valid selector records. Step 3’s root-enrollment journal remains recoverable before a head exists. Do not add an ownership field, journal registry, or general path policy.

- **Stop each direct legacy entry point early.** Under `plan_tool/roadmap.py:_roadmap_writer_owner()`, check `enroll_roadmap_baselines()`, `run_roadmap()`, `accept_roadmap_seed()`, `apply_roadmap_seeds()`, `materialize_plan_seed()`, `materialize_and_diff_one_plan()`, and `refresh_roadmap_seeds()` before they reach `_write_brief_source()`, `_write_roadmap_seed_state()`, `_materialize_seed_rows()`, `write_seed_refresh_report()`, a prompt, or a backend invoker. Cover both owned and caller-supplied writer-token arms for seed materialization.

- **Close the materialize-only CLI bypass.** `plan_tool/cli/roadmap_cmd.py:_cmd_roadmap_materialize_owned()` must use the same guard before `_roadmap_command_lifecycle()`, row classification, or `_materialize_seed_rows()`. Do not add a global rejection at `cmd_roadmap()`: views, immutable evidence actions, and the derived HTML output are not legacy artifact writers.

- **Return preflight refusals from bounded runners.** Give the shared guard a distinguishable refusal that `run_local_feedback_revision()`, `run_structural_revision()`, and `run_confirmed_feedback_reopen()` can map to their preflight-rejected result path. The structural runner must make this decision before `verified_structural_evaluator()`; none of the three routes may invoke a backend or publisher after refusal.

- **Keep immutable evidence and derived output available.** `plan_tool/roadmap_impact_run.py:run_roadmap_impact_analysis()` must still publish a new immutable evidence record for an enrolled roadmap when no legacy journal needs recovery. `plan_tool/cli/roadmap_cmd.py:_cmd_roadmap_view()` must retain `--view html`’s existing derived-file overwrite behavior.

## Tests

### Tests for this step

- `tests/test_roadmap_revision_publish.py:test_enrolled_roadmap_refuses_each_legacy_publication_before_journal_write` — Every legacy publication wrapper refuses with unchanged artifact, baseline, seed-state, and journal bytes.

- `tests/test_roadmap_revision_publish.py:test_enrolled_roadmap_refuses_seed_preinvalidation_without_changing_state` — `preinvalidate_roadmap_seeds()` cannot replace enrolled seed lifecycle state.

- `tests/test_roadmap_revision_publish.py:test_enrolled_roadmap_preserves_pending_legacy_journal_and_members` — Recovery refuses a pending legacy generation without deleting its journal or changing recorded members.

- `tests/test_roadmap_revision_publish.py:test_enrolled_roadmap_keeps_selector_only_promotion_recovery_available` — A one-member promotion journal with valid old and replacement accepted-head selectors still uses shared recovery after enrollment, while a mixed or non-selector generation refuses.

- `tests/test_roadmap_revision_publish.py:test_unversioned_roadmap_keeps_legacy_publication_and_recovery_behavior` — The shared guard leaves current legacy publication and recovery behavior intact without an accepted head.

- `tests/test_roadmap.py:test_enrolled_run_refuses_before_stage_invoker_or_source_write` — `run_roadmap()` makes no backend call and changes no legacy roadmap state.

- `tests/test_roadmap.py:test_enrolled_baseline_enrollment_refuses_without_new_sidecars` — `enroll_roadmap_baselines()` creates no baseline or seed-state changes.

- `tests/test_roadmap.py:test_enrolled_seed_entry_points_refuse_before_seed_or_report_writes` — Seed acceptance, apply, refresh, and direct materialization leave draft, promoted, state, and report files unchanged.

- `tests/test_roadmap.py:test_unversioned_stage_and_seed_lifecycle_paths_remain_writable` — Stage and seed routes retain their existing successful results without enrollment.

- `tests/cli/test_roadmap_cmd.py:test_enrolled_materialize_route_refuses_before_lifecycle_backend_or_report` — `--materialize` opens no lifecycle, calls no injected backend, and writes no report for an enrolled roadmap.

- `tests/cli/test_roadmap_cmd.py:test_enrolled_html_view_keeps_derived_output_behavior` — `--view html` remains allowed to write its derived output for an enrolled roadmap.

- `tests/test_roadmap_revision_run.py:test_local_revision_of_enrolled_roadmap_is_preflight_rejected_before_invocation` — Local revision reports a preflight refusal and never calls its injected invoker.

- `tests/test_roadmap_structural_revision_run.py:test_structural_revision_of_enrolled_roadmap_is_preflight_rejected_before_evaluator_or_invoker` — Structural revision refuses before evaluator setup and backend invocation.

- `tests/test_roadmap_feedback_reopen.py:test_confirmed_feedback_reopen_of_enrolled_roadmap_is_preflight_rejected_without_publication` — Confirmed reopen leaves its selected artifact unchanged.

- `tests/test_roadmap_impact_run.py:test_enrolled_roadmap_impact_analysis_still_publishes_immutable_evidence_without_legacy_journal` — An enrolled roadmap without a legacy journal still creates its immutable impact analysis.

Every listed test must be green before this step is complete.

## Acceptance criteria

- An enrolled roadmap makes every listed legacy artifact, baseline, seed, seed-state, and legacy-journal mutation route refuse before replacement or deletion.

- A pending legacy journal on an enrolled roadmap remains present with unchanged member files after refusal.

- The selector-only promotion journal remains recoverable after enrollment without a journal-ownership framework; every other enrolled pending generation remains untouched on refusal.

- Local revision, structural revision, and confirmed feedback reopen report preflight refusal without evaluator, model, or publisher work.

- An unversioned roadmap retains current legacy writer behavior, and an enrolled roadmap retains immutable impact-evidence publication and derived HTML output.

- All tests listed in `## Tests` pass.

## References

- [os — Miscellaneous operating system interfaces](https://docs.python.org/3.13/library/os.html#os.replace) — Review the replacement and deletion behavior that the journaled publisher and recovery path preserve.

## Applicable guardrails

- **The plan’s “## Scope guardrails”, allowed behavior changes** — Limit new behavior to refusing legacy in-place writes after enrollment and preserve the unversioned branch.

- **The plan’s “## Scope guardrails”, allowed reorganization** — Keep this as one shared enrollment decision and do not reorganize unrelated roadmap pipeline or artifact-model code.

- **The plan’s “## Scope guardrails”, bounded feedback and structural rewrite** — Preserve those routes for unversioned roadmaps; do not turn refusal into a broader writer.

- **The plan’s “## Scope guardrails”, model-output boundary** — Do not add a model-assisted fallback from a refused legacy route into the candidate workflow.

- **The plan’s “## Out of scope”, legacy-writer integration and recovery hardening** — Refuse legacy routes rather than migrating them to version production, while retaining the existing version-owned publication recovery contract.

## Deferred

- Migrating bounded feedback, structural rewrite, and seed workflows onto candidate review and promotion — This step only blocks their in-place behavior after enrollment.

- Converting remaining roadmap readers to accepted-head resolution — The plan proves one downstream reader and leaves wider reader migration outside this step.
