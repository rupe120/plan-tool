> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 10 — Refuse enrolled roadmaps before legacy artifact, baseline, seed, or journal overwrites and deletes while preserving unversioned writes

## Summary

Refuse every legacy roadmap mutation path once step 3 has selected an accepted head. Update `plan_tool/roadmap.py` and `plan_tool/roadmap_revision_publish.py` at the shared writer boundaries, then make the local revision, structural revision, and feedback-reopen runners report the refusal as preflight failure. Keep the accepted-head check separate from the generic generation transaction so version enrollment and promotion can still use their own immutable publication path. On green, enrolled roadmap artifacts, baselines, seed state, and pending legacy journals stay unchanged, while roadmaps with no accepted head keep their current write behavior.

## Table of Contents

- [Summary](#summary) — The step outcome and main design choice.
- [Table of Contents](#table-of-contents) — Links to each detail section.
- [Why](#why) — Why legacy writers must stop after enrollment.
- [Input](#input) — The accepted-head, writer-token, and journal contracts this step reads.
- [Files (creates vs edits)](#files-creates-vs-edits) — The existing writer and test files this step changes.
- [Implementation](#implementation) — The enrolled-roadmap refusal boundary and preserved paths.
- [Tests](#tests) — Focused refusal, no-write, and unversioned regression coverage.
- [Acceptance criteria](#acceptance-criteria) — Observable completion conditions.
- [References](#references) — Durable replacement guidance for the shared publication path.
- [Applicable guardrails](#applicable-guardrails) — Plan fences that keep this a narrow bypass block.
- [Deferred](#deferred) — Legacy workflow migration that remains outside this step.

## Why

`plan_tool/roadmap_revision_publish.py` still lets legacy stage, baseline, feedback, structural, seed, and recovery paths replace or remove files below a roadmap root. After step 3 enrolls an accepted version, those writes can make the live files disagree with the accepted head that readers now trust. The fix must stop the old writers at their mutation boundary without blocking the immutable evidence writes and unversioned roadmap behavior that remain valid.

## Input

- **Accepted-head selection:** Step 3 provides `plan_tool/roadmap_versions.py:load_accepted_version()` as the single enrolled-roadmap decision. Treat a selected head as enrolled; do not infer enrollment from a version directory, a baseline sidecar, or current artifact contents.

- **Legacy writer lease:** `plan_tool/roadmap_revision_publish.py:RoadmapWriterToken`, `roadmap_writer_guard()`, and `require_roadmap_writer_token()` serialize mutations for one roadmap. Make the enrollment check while this lease is active so a head change cannot race a legacy write.

- **Generation journal:** `plan_tool/roadmap_source_identity.py:PendingGeneration`, `GenerationMember`, and `pending_generation_path()` describe the old journaled transaction. A pending journal can cause both replacement and deletion through `plan_tool/roadmap_revision_publish.py:recover_roadmap_publication()`.

- **Seed lifecycle state:** `plan_tool/roadmap_seed_state.py:seed_state_path()` and `write_seed_state()` back the mutations reached from `plan_tool/roadmap.py:accept_roadmap_seed()`, `apply_roadmap_seeds()`, and `refresh_roadmap_seeds()`.

## Files (creates vs edits)

- **New files:** None.

- **Existing files (edits only):**
  - `plan_tool/roadmap_revision_publish.py` — Add the shared enrolled-roadmap refusal check at legacy publication, baseline, seed-state invalidation, and recovery boundaries.
  - `plan_tool/roadmap.py` — Run the refusal check before legacy stage, baseline, and seed lifecycle paths can invoke a backend or write files.
  - `plan_tool/cli/roadmap_cmd.py` — Preflight the direct `--materialize` batch route under its existing writer token before lifecycle logging, model invocation, or seed/report writes.
  - `plan_tool/roadmap_revision_run.py` — Return an existing preflight-style refusal for an enrolled local feedback revision before invoking the backend.
  - `plan_tool/roadmap_structural_revision_run.py` — Return an existing preflight-style refusal for an enrolled structural revision before evaluator or publication work.
  - `plan_tool/roadmap_feedback_reopen.py` — Return a preflight refusal, not a generic write failure, for an enrolled feedback reopen.
  - `tests/test_roadmap.py` — Cover stage, baseline, and seed entry-point refusal plus unversioned regressions.
  - `tests/cli/test_roadmap_cmd.py` — Cover enrolled and unversioned `--materialize` dispatch before backend and report effects.
  - `tests/test_roadmap_revision_publish.py` — Cover the shared legacy publication and recovery boundaries.
  - `tests/test_roadmap_revision_run.py` — Cover local-revision refusal before the model invoker.
  - `tests/test_roadmap_structural_revision_run.py` — Cover structural-revision refusal before evaluator and invoker work.
  - `tests/test_roadmap_feedback_reopen.py` — Cover confirmed reopen refusal without publication.
  - `tests/test_roadmap_impact_run.py` — Prove an enrolled roadmap can still publish new immutable impact evidence when no legacy journal needs recovery.

## Implementation

- **Use one enrolled-roadmap predicate.** Add a small token-checked guard near `plan_tool/roadmap_revision_publish.py:require_roadmap_writer_token()` that asks step 3’s accepted-head boundary whether the roadmap is enrolled. A missing accepted head must allow the legacy path unchanged. An unreadable or invalid accepted-head record must refuse rather than fall back to legacy mutation.

- **Keep the generic generation transaction available to version writers.** Apply the new check at the legacy public entry points, not as an unconditional rule inside `plan_tool/roadmap_revision_publish.py:_publish_generation()`. Step 3’s enrollment and step 8’s promotion need the shared transaction for immutable version files and accepted-head updates; they must not be mistaken for legacy artifact publication.

- **Block every legacy publication shape before it writes a journal or member.** Cover `preinvalidate_roadmap_seeds()`, `enroll_stage_baselines()`, `publish_stage_artifact()`, `publish_revision_candidate()`, `publish_feedback_reopen_candidate()`, and `publish_structural_revision_proof()`. The refusal must occur before `durable_write_bytes()`, `_replace_generation_members()`, or seed-state writing can replace or remove a file.

- **Treat pending legacy journals as protected after enrollment.** In `plan_tool/roadmap_revision_publish.py:recover_roadmap_publication()`, preserve the current no-journal return so read-only callers can continue. When an enrolled roadmap has a pending journal, refuse before parsing, unlinking, rolling back, or completing its members. Keep the journal and every referenced file unchanged for later manual handling.

- **Preflight the direct legacy entry points.** In `plan_tool/roadmap.py`, check enrollment under `_roadmap_writer_owner()` before `enroll_roadmap_baselines()`, `run_roadmap()`, `accept_roadmap_seed()`, `apply_roadmap_seeds()`, `materialize_plan_seed()`, `materialize_and_diff_one_plan()`, and `refresh_roadmap_seeds()` reach recovery, a stage or seed invoker, `_write_brief_source()`, `_write_roadmap_seed_state()`, `_materialize_seed_rows()`, promoted seed writes, or `write_seed_refresh_report()`. In `plan_tool/cli/roadmap_cmd.py:_cmd_roadmap_materialize_owned()`, run the same token-checked refusal before opening the command lifecycle or classifying rows so the direct batch route cannot bypass the public domain guard. Do not add the check to read-only loaders or view code.

- **Return a clear refusal from bounded legacy runners.** Make `plan_tool/roadmap_revision_run.py:run_local_feedback_revision()`, `plan_tool/roadmap_structural_revision_run.py:run_structural_revision()`, and `plan_tool/roadmap_feedback_reopen.py:run_confirmed_feedback_reopen()` classify enrollment as their existing preflight-rejected result shape. Do not send a model prompt, publish a candidate, or report the condition as a successful gate failure or generic write failure.

- **Leave immutable evidence writes alone.** `plan_tool/roadmap_impact_run.py:run_roadmap_impact_analysis()` remains outside this step’s source edits. Its call to `recover_roadmap_publication()` must continue past an enrolled roadmap when no journal exists, so `plan_tool/roadmap_evidence_store.py:publish_evidence()` can create a new immutable analysis record.

- **Keep refusal data minimal.** Reuse the existing exception and result channels without adding candidate content, feedback text, accepted-version bytes, or a new lifecycle framework to logs or return records.

## Tests

### Tests for this step

- `tests/test_roadmap_revision_publish.py:test_enrolled_roadmap_refuses_legacy_stage_baseline_revision_reopen_and_structural_publications_before_journal_write` — Each legacy publication entry point refuses with the accepted head present and leaves artifact, baseline, seed-state, and journal bytes unchanged.

- `tests/test_roadmap_revision_publish.py:test_enrolled_roadmap_refuses_seed_preinvalidation_without_changing_state` — `preinvalidate_roadmap_seeds()` cannot replace enrolled seed lifecycle state.

- `tests/test_roadmap_revision_publish.py:test_enrolled_roadmap_recovery_preserves_a_pending_legacy_journal_and_members` — Recovery refuses an enrolled roadmap with a pending journal without unlinking the journal or rolling back its recorded members.

- `tests/test_roadmap_revision_publish.py:test_unversioned_roadmap_keeps_legacy_publication_and_recovery_behavior` — The shared guard does not change successful legacy publication or recovery when no accepted head exists.

- `tests/test_roadmap.py:test_enrolled_run_refuses_before_recovery_or_stage_invoker` — `run_roadmap()` rejects before recovery can mutate and before any stage backend call.

- `tests/test_roadmap.py:test_enrolled_baseline_enrollment_refuses_without_new_sidecars` — `enroll_roadmap_baselines()` creates no baseline or seed-state change after enrollment.

- `tests/test_roadmap.py:test_enrolled_seed_accept_apply_and_refresh_refuse_before_seed_writes` — Seed acceptance, promotion, and refresh do not overwrite draft, promoted, state, or report files for an enrolled roadmap.

- `tests/test_roadmap.py:test_enrolled_seed_materialization_refuses_before_invocation_or_seed_and_report_writes` — Direct single-row and shared batch materialization refuse under the same accepted-head guard without invoking a backend or changing draft, promoted, state, or report files.

- `tests/cli/test_roadmap_cmd.py:test_enrolled_materialize_route_refuses_before_lifecycle_backend_or_report` — The `--materialize` CLI route reaches the same guard before it opens per-row work, invokes the fake backend, or writes a refresh report.

- `tests/test_roadmap.py:test_unversioned_stage_and_seed_lifecycle_paths_remain_writable` — The stage and seed paths retain their current results when the roadmap has no accepted head.

- `tests/cli/test_roadmap_cmd.py:test_unversioned_materialize_route_keeps_current_behavior` — The direct batch CLI route retains its current materialization and report behavior without an accepted head.

- `tests/test_roadmap_revision_run.py:test_local_revision_of_enrolled_roadmap_is_preflight_rejected_before_invocation` — The local feedback runner returns a preflight refusal and never calls its injected invoker.

- `tests/test_roadmap_structural_revision_run.py:test_structural_revision_of_enrolled_roadmap_is_preflight_rejected_before_evaluator_or_invoker` — The structural runner refuses before evaluator setup or backend invocation.

- `tests/test_roadmap_feedback_reopen.py:test_confirmed_feedback_reopen_of_enrolled_roadmap_is_preflight_rejected_without_publication` — A confirmed reopen returns a preflight refusal and leaves its selected artifact unchanged.

- `tests/test_roadmap_impact_run.py:test_enrolled_roadmap_impact_analysis_still_publishes_immutable_evidence_without_a_pending_journal` — An enrolled roadmap with no legacy journal still completes impact analysis and creates its immutable evidence record.

Every listed test must be green before this step is complete.

## Acceptance criteria

- An accepted head makes every listed legacy artifact, baseline, seed materialization, seed lifecycle, and journal mutation entry point refuse before model invocation or file replacement/deletion.

- A pending legacy journal on an enrolled roadmap remains present with unchanged member files after recovery refuses.

- Local feedback revision, structural revision, and confirmed feedback reopen report enrollment through their preflight refusal path and do not invoke a model or publisher.

- A roadmap with no accepted head keeps its current legacy stage, baseline, seed, and recovery behavior.

- An enrolled roadmap can still create a new immutable impact-analysis evidence record when no pending legacy journal exists.

- All tests listed in `## Tests` pass.

## References

- [os — Miscellaneous operating system interfaces](https://docs.python.org/3.13/library/os.html#os.replace) — Review the atomic replacement and deletion behavior that the existing generation transaction and recovery path rely on.

## Applicable guardrails

- **The plan’s “## Scope guardrails”, allowed behavior changes** — Limit behavior changes to refusing legacy in-place writers for enrolled roadmaps and preserve the unversioned branch.

- **The plan’s “## Scope guardrails”, candidate and promotion ordering** — Do not create, alter, approve, or promote a candidate here; this step only blocks bypass writes.

- **The plan’s “## Scope guardrails”, model-output boundary** — Do not add a model-assisted fallback from a refused legacy writer into the candidate workflow.

- **The plan’s “## Out of scope”, legacy-writer integration** — Refuse the old routes instead of migrating them into candidate versions or broadening their authority.

- **The plan’s “## Out of scope”, recovery hardening** — Keep the existing recovery protocol intact for unversioned roadmaps and add only the enrolled no-mutation refusal it requires.

## Deferred

- Migrating bounded feedback, structural rewrite, and seed workflows onto candidate review and promotion — This step only prevents their legacy in-place mutation after enrollment.

- Broader roadmap-reader conversion and version-management features — The plan converts one reader and does not add history, rollback, retention, or migration surfaces.
