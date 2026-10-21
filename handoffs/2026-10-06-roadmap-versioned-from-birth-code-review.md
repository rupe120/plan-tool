# Roadmap versioned-from-birth — code review ledger

| Field | Value |
| --- | --- |
| Change | `roadmap-versioned-from-birth`: the roadmap folder holds versions from its first stage run; the removed routes (stage re-entry, enrollment, rollback checkpoint, escalation, impact analysis, structural rewrite) and their modules are deleted |
| Branch | `impl/roadmap-versioned-from-birth` |
| Review range | pass 1: merge-base `main...HEAD` at `7b021100` (40 commits, 137 files) |
| Checks run | Pass 1 fixes: targeted suites (roadmap, revision publish, CLI, create, seed state, data contract, roadmap format, run log, duplication, decision settlement, candidate run) 4,583 passed, 65 skipped; full suite `uv run pytest tests/ -q -n auto`: 13,385 passed, 67 skipped (`.tmp/roadmap-versioned-from-birth.review1-fixes.log`). Fixes 1 and 2 verified by mutation (see each finding). Pass 2 fixes: full suite 13,398 passed, 67 skipped (`.tmp/roadmap-versioned-from-birth.review2-fixes.log`); findings 9 and 11 verified by mutation. Pass 3 fixes: full suite 13,400 passed, 67 skipped (`.tmp/roadmap-versioned-from-birth.review3-fixes.log`); findings 15 and 16 verified by mutation. Pass 4 fixes: full suite 13,402 passed, 67 skipped (`.tmp/roadmap-versioned-from-birth.review4-fixes.log`); findings 22 and 25 verified by mutation. |
| Reviewer | headless review sessions, report-only (`.tmp/roadmap-versioned-from-birth-code-review-1.md` to `-4.md`) |
| Disposition | passes 1 to 4 triaged; loop concluded 2026-10-06 (see "Loop conclusion") |

## Settled decisions (hand to each reviewer)

- Plan files under `docs/implementation-plans/**` are canonical for this change and are not edited by review fixes.
- Out of scope for review: `BACKLOG.md` #444 (callerless `structural_codex_*`, run-log structural/impact/escalation events, update-judgment section and prompt), `BACKLOG.md` #445 (docs outside the version-only docs sweep), and the render-version constraint on the byte-stable feedback key comment in `plan_tool/roadmap_artifacts.py`.
- `NoPublishedRoadmapVersionError` from `create`'s research-target reader is pinned by a test; only a corrupt version store becomes a `CreateError`.
- Callerless leftovers found by review are filed, not deleted, in this change (`BACKLOG.md` #446).

## Review pass 1 — /code-review (headless), 2026-10-06

Scope: `main...HEAD` at `7b021100`. Method: static reading of the stage run, resume, publish, version readers, decision settlement, ledger, CLI and the new tests; a sweep of every deleted top-level symbol and module against surviving references; a reader sweep for any fallback to top-level `0N-*.md` files; a check that every `publish_roadmap_generation` call is followed by an index refresh. The reviewer could not run any program (every interpreter, linter, and `uv run` call was denied), so every claim is grep- or reading-based. Each claim was verified in the driving session by running the code before a fix was applied.

### 1. Recovery does not recognize a completed root generation because the ledger member is not in its expected member list — medium
Category: correctness (crash recovery). `plan_tool/roadmap_revision_publish.py:417-451` (recognizer), `:344-353` (raise); producer `plan_tool/roadmap.py:2329-2337`; masking test `tests/test_roadmap.py` (`test_pending_root_journal_is_recovered_before_the_resume_directory_is_read`).
Failure scenario: `_publish_root_version` inserts the initial feedback ledger before the head. A crash after the head write and before the journal unlink leaves a journal whose member list the recognizer rejects, so `recover_roadmap_publication` raises `RoadmapPublicationRecoveryError` and every guarded writer refuses until the journal is deleted by hand. The existing test passed only because it stripped the ledger member.
Suggested fix: expect the ledger member (ledger path, `old=None`, ahead of the selector) and feed the unmodified journal in the test.
**Disposition:** fixed (this change set). Reproduced first: with the strip-the-ledger workaround removed, the test raised `enrolled roadmap refuses recovery of a non-version-owned generation`. The recognizer now expects exactly the version record, brief, four artifacts, the rendered initial ledger at the ledger path with `old=None`, then the selector; the decision-settlement kind is untouched. The test feeds `captured[0]` unmodified. Two sibling tests that built root generations without a ledger (`test_completed_root_enrollment_journal_is_dropped_without_touching_members`, `test_completed_version_owned_generation_is_still_recognized`) pinned the old shape and now publish the real member list through `_with_initial_feedback_ledger`. New: `test_recognizer_accepts_the_real_root_member_list_including_the_initial_ledger`, and `test_recognizer_refuses_a_root_member_list_that_is_not_exactly_the_published_one` (unknown extra member, ledger missing, ledger with old bytes, ledger after the selector). Mutation: removing the ledger member from the recognizer turns five tests red, including the real-journal test.

### 2. A corrupt or missing version store surfaces as an uncaught exception in `create --from-existing` on a roadmap-promoted seed — low-medium
Category: correctness (error handling). `plan_tool/cli/authoring.py:321-364`; `plan_tool/create.py:3544-3551`.
Failure scenario: both call sites read through `load_accepted_version`, which raises `RoadmapVersionError` (a `ValueError`) for an unreadable head or damaged member; `_confirm_invalidated_roadmap_seed` did not catch it, and `_load_roadmap_research_targets` raised a non-`CreateError`.
Suggested fix: catch `RoadmapVersionError` in `authoring.py`; convert it in `create.py`.
**Disposition:** fixed (this change set). `_confirm_invalidated_roadmap_seed` catches `RoadmapVersionError`, prints the message, and returns `False`; `_load_roadmap_research_targets` converts it to a `CreateError`. The missing-head case still raises `NoPublishedRoadmapVersionError`, as pinned. Tests: `test_corrupt_accepted_head_is_an_error_message_not_a_traceback` and `test_corrupt_accepted_head_is_a_create_error_not_a_traceback`; both fail with the fix stashed.

### 3. Dead stage-feedback revision path and never-populated result fields — low-medium
Category: simplification (dead code). Named functions in `plan_tool/roadmap.py`, three `RoadmapResult` fields, three CLI summary helpers, four path helpers, `_revise_feedback_has_conflict`, `LoadedRoadmap.directory_exists`, and the `stages` parameter of `decision_settlement_receipt_proves_completion`.
**Disposition:** deferred — tracked as `BACKLOG.md` #446 with machine-verified caller counts. The review's claim that all of them have only test callers is partly wrong: `_run_bounded_stage_feedback`, `_check_predecessor_review_rows`, `_awaiting_review_count`, `_newly_settled_decision_ids`, `_feedback_counts_by_state`, and `_has_open_feedback` have no caller in `plan_tool/` or `tests/`; `recheck_feedback_snapshot`, `_render_stage_feedback_prompt`, and `_stage_feedback_corrections_block` are referenced only from the two dead runners; the three result fields are set by neither `RoadmapResult(...)` construction. The `invalidated_seed_count` field in `plan_tool/run_log.py` is a different record (#444) and stays out of #446.

### 4. Persisted-contract and operations docs still describe removed run-log events and preflight categories — low
Category: documentation drift. `DATA_CONTRACT.md` (`RoadmapPreflightFailed`, `RoadmapStageWritten`); `docs/OPERATIONS.md:270-279`.
**Disposition:** fixed (this change set). The `check` list now names the values the stage run emits (`accepted_head`, `pre_head_state`, `brief_source`, `brief_read`, `publication_recovery`, `resume_brief_digest`, `carried_decisions`); `RoadmapStageWritten` describes one event per stage held under `roadmap-stage-resume/` with `replaced` always `false`; the `revision_feedback_delivered` and `roadmap_source_*` bullets and the `--revise-feedback` receipt clause are removed from `docs/OPERATIONS.md`; the `RoadmapPreflightFailed` docstring example no longer names a removed value. The reviewer's suggestion to add the categories to a drift test is not applied: the set is documented prose, and no consumer needs it closed.

### 5. Operator-visible and model-visible text still describes on-disk artifacts and stage re-entry — low
Category: operator-visible text. `plan_tool/cli/roadmap_cmd.py` (module docstring, `--apply` and `--view` help); `plan_tool/roadmap.py` (docstrings); the four `plan_tool/prompts/roadmap-*.md` stage prompts.
**Disposition:** fixed (this change set). The help strings and docstrings say the accepted version; each stage prompt now says only that a human reads the file. `docs/cli/roadmap.md` is regenerated. The byte-stable key comment in `roadmap_artifacts.py` is untouched. The top-level help golden is unaffected.

### 6. `_create_handoff_lines` fallback for `plans_dir` computes the roadmap folder, not the plans directory — low
Category: correctness (latent). `plan_tool/cli/roadmap_cmd.py:2073-2094`; `tests/cli/test_roadmap_cmd.py:5067`.
**Disposition:** fixed (this change set). `plans_dir` is a required keyword and the `parent.parent.parent` fallback is gone. The test comment is corrected rather than the fixture line removed: the handoff tests name the top-level copy in `result.artifacts` and three tests fail without it.

### 7. Open backlog entries still describe the removed rollback, checkpoint and enrollment routes — low
Category: documentation hygiene. `BACKLOG.md` #398–#401; `BUG_BACKLOG.md`.
**Disposition:** fixed (this change set), after verifying each subject is gone (`--restore-revision`, `--enroll-baselines`, `roadmap_revision_checkpoint.py`, `roadmap_revision_rollback.py`, `roadmap_revision_run.py`, `tests/test_roadmap_structural_revision_run.py`, `read_recorded_brief_source`, `_write_brief_source` no longer exist). Deleted: #398, #399, #400, #401, and the same-class entries #274, #275, #429 (all about the deleted `roadmap_revision_run.py`), plus two `BUG_BACKLOG.md` entries (the structural-revision-run stale-attempt test, the `source.json` classification race). Trimmed the dead clauses from #355 and the model-failure-receipt entry, and the `see #429` pointer in the same-receipt entry. `BUG_BACKLOG.md` joins `_REMOVED_ROUTE_DOC_FILES`; the guard passes. Left as written: closed entries that cite the removed flags with dates, and the connectivity-recovery entry whose opt-out clause names `roadmap_revision_run.py:shell_local_revision_invoker` (its design decision, not a hygiene edit).

### 8. Small leftovers in touched code — low
Category: simplification / conventions. `plan_tool/roadmap_candidate_run.py:1639`; `plan_tool/roadmap_decision_settlement.py:204-206`.
**Disposition:** fixed in part (this change set). The `current =` spacing and the comment (a ledger-less roadmap stays on embedded-feedback evidence and is not migrated) are corrected. Not applied: the successor-slug remedy on the missing-ledger read. The review names the candidate-proposal read, which is a different site from the decision-settlement site (where an absent ledger is a supported branch, not a failure), and a ledger-less enrolled roadmap is reachable only by deleting the ledger by hand; no test pins a new message, so the change is left for whoever picks that route.

## Review pass 2 — /code-review (headless), 2026-10-06

Scope: `main...HEAD` at `db82e058` (144 files), weighted toward `7b021100..HEAD` and the crash safety of the stage run. Method: static reading only; the reviewer could not run any program, so every claim was reading-based and each was reproduced or checked in the driving session before a fix was applied (findings 1 and 3 by a failing test first, then by mutation). Result: six findings, no defect that publishes wrong content or corrupts the version store; three residual crash-recovery gaps (1 to 3), one drift risk (4), stale text (5, 6). Pass 2 is not a clean pass, so pass 3 follows. Checks run: `.tmp/roadmap-versioned-from-birth.review2-fixes.log` (full suite, counts below).

### 9. A hard kill during a durable write leaves a temp file that permanently blocks the stage run — medium
Category: correctness (crash recovery). `plan_tool/roadmap.py` (`_pre_head_state_paths`), `plan_tool/roadmap_revision_publish.py` (rollback), `plan_tool/fileio.py` (`durable_write_bytes`).
Failure scenario: a SIGKILL between the temp-file create and `os.replace` leaves `.<name>.<random>.tmp` under `.roadmap-versions/`; recovery unlinks the journal and recorded members only, and `_pre_head_state_paths` counts any file there, so every retry is refused with `RoadmapPreHeadStateError` although the held stages are intact.
Suggested fix: ignore the temp names in the state check, or clean them in recovery.
**Disposition:** fixed (this change set). Reproduced first: a test planting `.version.json.<random>.tmp` in a version directory and a head-selector temp beside it failed with `RoadmapPreHeadStateError`. `fileio.is_write_temp_name` matches exactly the leading-dot, `.tmp`-suffixed, at-least-three-dots shape; `_pre_head_state_paths` skips those names, and every other stored file still counts. Tests: `test_stray_durable_write_temp_files_are_not_pre_head_state`, and `test_a_real_stored_file_still_refuses_even_when_it_resembles_a_temp_name` (`version.json`, `notes.tmp`, `.hidden`, `x.tmp`). Mutations: dropping the filter turns the first test red; loosening the predicate to `endswith(".tmp")` turns the `notes.tmp` and `x.tmp` cases red. Not applied: unlinking the temp siblings of recorded members in the rolled-back-journal path. A leftover temp is inert once the state check ignores it (version loading does not scan the directory and a retry writes a fresh random name), so the cleanup would add a glob per member to recovery for no behavior change.

### 10. After a crash between the head write and the journal unlink, no ordinary writer recovers and the refusal names no route — medium-low
Category: correctness (recovery reachability) and documentation. `plan_tool/roadmap_revision_publish.py` (`publish_roadmap_generation`, `recover_roadmap_publication`); `docs/how-to/roadmap.md` § 3; `RUNBOOK.md`.
Failure scenario: recovery runs only inside the stage run and `--settle-decision`; `--submit-feedback`, `--propose-candidate`, `--promote`, and the ledger edits refuse on a journal with a message naming no command, and `docs/how-to/roadmap.md` § 3 says a crash leaves only the resume directory. With a head present the recognizer accepts only root, selector, and decision-settlement journals.
Suggested fix: name the route, or add recover-before-publish to the shared writer guard.
**Disposition:** fixed in part (this change set), deferred in part. Fixed: the refusal now names the journal path and `plan-tool roadmap <slug> --from-existing <brief>`. Behavior confirmed by the existing test `test_pending_root_journal_is_recovered_before_the_resume_directory_is_read` (recovery runs, the journal is gone, the run then raises `RoadmapHeadExistsError`): a plain stage run recovers a completed root journal and then refuses with `already has an accepted head`, which is the expected outcome. `docs/how-to/roadmap.md` § 3 no longer says a crash leaves only the resume directory and states the publication-journal case; `RUNBOOK.md` carries the refusal and its remedy in the refusal table. Test: `test_publish_beside_a_leftover_journal_names_the_recovery_command_and_changes_nothing`. Deferred: recover-before-publish in the shared writer guard and the unrecoverable non-root kinds beside a head, a design decision, filed as `BACKLOG.md` #447.

### 11. `delete_resume` failing after the head commit reports a published roadmap as a failed run — low-medium
Category: correctness (error handling). `plan_tool/roadmap.py` (`_run_roadmap`, after `_publish_root_version`).
Failure scenario: an `OSError` from `shutil.rmtree` propagates, the lifecycle records `run_end outcome=error rc=1`, and the CLI exits 1 although the version, ledger, and head are committed.
Suggested fix: warn and still return the completed result.
**Disposition:** fixed (this change set). The call is wrapped; an `OSError` prints `warning: roadmap <slug>: published, but could not delete the resume directory (...)` to stderr and the completed result is returned (the next run already deletes a stale directory beside a head). Test: `test_a_failing_resume_cleanup_after_the_head_commit_warns_and_still_completes` (outcome completed, head committed, warning printed). Mutation: catching `ZeroDivisionError` instead of `OSError` turns it red.

### 12. The completed-root recognizer re-implements the initial-ledger construction — low
Category: reuse / drift risk. `plan_tool/roadmap_revision_publish.py` and `plan_tool/roadmap.py` (`_with_initial_feedback_ledger`).
**Disposition:** fixed (this change set). `roadmap_feedback_ledger.initial_ledger(slug, ledger_state)` is the one construction; both sites call it, and the two now-unused `RoadmapFeedbackLedger` imports (and `LedgerState` in the publisher) are removed. Test: `test_initial_ledger_bytes_are_one_construction_shared_by_publisher_and_recognizer` (the published ledger member equals `render_ledger(initial_ledger(slug))` and the recognizer accepts the journal). `tests/test_duplication.py` stays green.

### 13. The first-run-only stage loop still sends revision-era correction text and carries revision-era rationale — low
Category: operator/model-visible text, conventions. `plan_tool/roadmap.py` (correction text, `FAILURE_AUTHORED_REVIEW_ROWS` comment, `_authored_review_rows` docstring), `plan_tool/cli/roadmap_cmd.py` (exhaustion text).
**Disposition:** fixed in part (this change set), the rest filed. The retry correction now reads "a first run has no feedback or removals; drop the 'feedback' and 'removals' entries" and names the invented rows; the "do not narrow this check to `predecessor is None`" comment and the predecessor branches are deleted (`_authored_review_rows` takes the artifact alone, since both call sites passed `None`); the CLI exhaustion line says a first run has none. Test: `test_the_retry_correction_names_the_dropped_entries_in_first_run_terms` (the retry prompt names the rows and the drop instruction and carries no "revision" or "proposed_response"). Machine-verified (`rg` over `plan_tool` and `tests`) and added to `BACKLOG.md` #446: the `source_recheck` parameter of `_run_stage` (passed by one test only) and the `RoadmapSourceAdmissionError` raises and handlers it feeds, `_StageOutcome.invalid_detail` (set, never read) and `.reused_predecessor` (set only in a dead runner, read by one test), `OUTCOME_STAGE_INVALID` with `_print_invalid`, and `OUTCOME_COMPLETED_NO_CHANGE` with `_print_completed_no_change` (no `RoadmapResult(...)` construction uses either outcome). Not deleted here, per the settled decision above.

### 14. Resume-directory files are written without fsync while publication is durable — low
Category: crash safety. `plan_tool/roadmap_stage_resume.py` (`write_brief_digest`, `write_stage`, `read_held_stages`).
Failure scenario: after a power loss `brief.digest` can read as empty, so every held stage is regenerated; a SIGKILL leaves `.stage-N.md.<pid>.tmp`, which warns on every later resume.
**Disposition:** fixed (this change set). Both writers use `durable_write_bytes` (a drop-in: it creates the missing resume directory and unlinks its temp on failure, so `test_write_failure_keeps_the_previous_file` is unchanged), and `read_held_stages` skips `is_write_temp_name` entries without a warning while any other unexpected file still warns. Tests: `TestResumeWritesAreDurable` (fsync observed on both writes; first write creates the directory) and `TestInterruptedWriteLeftoversAreNotWarnedAbout` (temp names ignored and left in place; `stray.txt`, `stage-9.tmp`, `.hidden` still warn).

### Pass 2 result

Six findings: three medium or low-medium crash or error-handling gaps (9 to 11, all fixed; 10 deferred in its design half as #447), one drift risk (12, fixed), two low text and durability items (13, 14, fixed; 13 adds producer-less names to #446). Pass 3 is needed: the pass-2 findings were real, so this is not a low-yield pass.

## Review pass 3 — /code-review (headless), 2026-10-06

Scope: `main...HEAD`, weighted toward `8a5ea497..HEAD` and the crash safety of the first-run stage run (resume writes, root publication, head write, journal recovery, resume deletion). Method: static reading only; the reviewer ran no programs. Each claim was reproduced in the driving session with a failing test before a fix, or refuted/declined with the reasoning below.

### 15. `_require_no_accepted_head` calls `delete_resume` unguarded, so a stuck resume directory turns the head refusal into a raw `OSError` and skips the index refresh — low-medium
Category: correctness (error handling, crash recovery). `plan_tool/roadmap.py` (`_require_no_accepted_head`), beside the post-publish cleanup fixed in finding 11.
Failure scenario: the pass-2 fix made the post-commit `delete_resume` warn; the next-run call that finding relied on ("the next run deletes a stale resume directory beside a head") had no guard. A directory that cannot be removed raised `OSError` before `refresh_roadmap_index` and `RoadmapHeadExistsError`, so the CLI reported a started-run failure instead of the rc 2 refusal, and the index repair never ran.
Suggested fix: one shared warn-and-continue helper for both sites; refresh and refusal independent of the cleanup.
**Disposition:** fixed (this change set). `_delete_resume_or_warn` serves both sites. Test: `test_a_failing_resume_cleanup_beside_an_accepted_head_still_refuses_and_refreshes_the_index` (monkeypatched `delete_resume` raising `OSError` beside an accepted head with a stale `INDEX.md`: `RoadmapHeadExistsError`, the warning on stderr, index rewritten). Mutation: restoring the bare `delete_resume` call turns it red with the raw `OSError`.

### 16. Stage files after a gap or damaged stage are warned as "not held" but left on disk — low-medium
Category: correctness (crash recovery, mixed provenance). `plan_tool/roadmap_stage_resume.py` (`read_held_stages`), `plan_tool/roadmap.py` (`_run_roadmap`).
Failure scenario: held `stage-1.md`, an unreadable `stage-2.md`, and `stage-3.md`. The run regenerates stage 2, stage 3 exhausts its attempts and never overwrites the stale file, and the next run sees stages 1 to 3 as contiguous and re-gates the stale stage 3 against the new stage 2 with no model call and no warning.
Suggested fix: discard every file past the contiguous prefix before any stage runs.
**Disposition:** fixed (this change set). Reproduced first: the scenario left `stage-3.md` on disk. After the digest check, `_run_roadmap` calls `discard_stages_from(repo_root, slug, len(held.stages) + 1)`, matching the digest-`None` and gate-failure paths; `read_held_stages` stays read-only. Test: `test_stages_after_a_damaged_stage_are_discarded_so_a_later_run_cannot_regate_them` (stage 2 damaged, regenerated; stage 3 exhausts; stage 2 held, stage 3 file gone). Mutation: removing the discard turns it red.

### 17. A resume-directory write failure aborts the run and discards a freshly paid stage reply — low
Category: correctness (error handling, design proportion). `plan_tool/roadmap.py` (`cannot hold stage N for resume`).
Failure scenario: `.plan-tool/runs/<slug>/` is unwritable; stage 1 passes its gates, `write_stage` raises, the run exits and the reply is lost. The review suggests continuing in memory, since publication does not need the directory.
**Disposition:** not applied (deliberate; no code change). The resume guarantee is the owner-decided purpose of the directory: a failed run keeps its paid stages. Continuing silently in memory would break exactly that promise on the runs that need it (a later stage fails, the process dies, and nothing was held), and a warning that the guarantee is off is easy to miss in a long run. Failing at the first write bounds the loss to one stage reply. Verified what happens: no preflight writes the directory, so the refusal comes at the first write after stage 1 passes, as `cannot hold stage 1 for resume (...)` via `RoadmapEnvironmentalError`. `docs/how-to/roadmap.md` § 3 now says so.

### 18. `roadmap-plans.md` still tells the model it may author `feedback` and `removals` — low
Category: model-visible text drift. `plan_tool/prompts/roadmap-plans.md:111-112`.
Failure scenario: the sentence "follow the same contract as earlier stages when a revision carries them forward" invites rows that `_authored_review_rows` rejects, burning an attempt whose correction text then contradicts the prompt.
**Disposition:** fixed (this change set). The sentence now reads "A first run authors `decisions` only. Leave `feedback` and `removals` empty; reviewers add those rows after the roadmap is published." Class sweep over all four stage prompts and the other model-visible roadmap prompts by identifier and vocabulary ("carries them forward", "revision", "revise", "hand edit", "re-enter", "review rows", "feedback", "removals"): one more live residue, "a newly authored or revised row" in the same prompt (line 79), now "a newly authored row". Remaining hits are legitimate (the constraints prompt's "feedback targets", `prioritized`, the seed prompt, and the feedback and candidate revision prompts, which serve published roadmaps). No test pins the old text.

### 19. The root-journal recognizer pins the initial ledger bytes, so a hand edit between a crash and recovery makes recovery refuse with no stated remedy — low
Category: correctness (crash recovery). `plan_tool/roadmap_revision_publish.py` (expected ledger member, `states != expected`).
**Disposition:** deferred, folded into `BACKLOG.md` #447 (What and In scope), not a new entry: it is the same class (a recoverable journal that refuses with no remedy) and needs the same per-kind recovery-policy decision. The window is narrow: a crash between the head write and the journal unlink, plus a hand edit before any command runs. Remedy options recorded there: exempt the ledger member once the head names the published version, or name the hand-removal remedy in the refusal.

### 20. The newly created resume directory chain is not fsynced — low
Category: crash safety (durability claim). `plan_tool/fileio.py` (`durable_write_bytes`).
**Disposition:** not applied (documented; no code change). Each file is fsynced and its directory synced, so the claim finding 14 made holds. A power loss in the narrow window after the first write can drop the new directory entry, which costs only regeneration of the held stages for that run; nothing is published or corrupted, and the next run starts clean. Syncing every created ancestor adds a recursive helper to `fileio.py` for a loss the design already tolerates.

### Pass 3 result

Six findings, none above low-medium. Two fixed with reproducing tests and mutation checks (15, 16), one model-visible text fix with a class sweep (18), one deferred into #447 (19), two deliberately not applied with reasoning (17, 20). The pass found no gap in the root generation order, the crash points between journal write and unlink, the temp-name recognizer, digest handling, or CLI exception mapping. Low-yield by severity; one more low-yield or clean pass completes convergence.

## Review pass 4 — /code-review (headless), 2026-10-06

Scope: `main...HEAD`, weighted toward `49a1663b~1..HEAD` (the shared `_delete_resume_or_warn` helper and both call sites, the `discard_stages_from(... len(held.stages) + 1)` call, the `roadmap-plans.md` edit) and the crash safety of the first-run stage run; eleven crash points (C1 to C11) walked. Method: static reading only; the reviewer ran no programs (`uv run pytest` was refused). Each claim was read against the code in the driving session; the claims fixed were reproduced with a failing test first. Result: five low findings, no medium. No defect that publishes wrong content, corrupts the version store, or loses a published version.

### 21. The resume directory is keyed by (repo root, slug) while the head and the writer guard are keyed by plans directory — low
Category: correctness (state scoping, destructive cleanup). `plan_tool/roadmap_stage_resume.py:40-42` (`resume_dir_path`), `plan_tool/roadmap.py` (`_delete_resume_or_warn` in `_require_no_accepted_head`, the post-publish cleanup).
Failure scenario: two plans directories in one repo share a slug; a head beside plans dir A makes `_require_no_accepted_head` delete the shared resume directory that plans dir B's aborted run holds, and a first run against B can reuse stages an aborted run against A held when the brief text matches. The writer lock does not span the two.
Suggested fix: scope the directory by plans dir, or record the resolved plans dir beside `brief.digest` and treat a mismatch like a digest mismatch.
**Disposition:** deferred, filed as `BACKLOG.md` #448 (a), `decision-needed`. Verified by reading: `resume_dir_path` takes only `(repo_root, slug)`; `load_accepted_head` takes `plans_dir`; `brief.digest` records only the digest. Not applied here: the scoping choice (path versus recorded owner) is a design decision, the trigger needs two plans directories with one slug, the loss is bounded to regenerating paid stages, and nothing published is affected.

### 22. `discard_stages_from` can raise at preflight on a stray entry the resume module promises only to warn about — low
Category: correctness (error handling, contract drift). `plan_tool/roadmap.py` (`_run_roadmap`, the discard after the digest check), `plan_tool/roadmap_stage_resume.py` (`discard_stages_from`).
Failure scenario: a stray `stage-9.md` that is a directory, or an entry the process cannot unlink, was only warned about before the pass-3 discard; `entry.unlink` now raised `OSError` before any stage ran, ending the run with a bare errno message. A side effect of the finding 16 fix.
Suggested fix: warn per entry and let the later `write_stage` fail loudly.
**Disposition:** fixed (this change set). Reproduced first: a `stage-9.md` directory past the prefix raised `PermissionError` out of `discard_stages_from`. Each entry is now unlinked inside `try/except OSError`, printing `warning: <path>: could not discard stage file (<error>)` to stderr and continuing; the file-level contract (warned, never raised) holds again. Test: `test_discard_warns_and_continues_when_an_entry_cannot_be_removed` (a removable `stage-3.md` is removed, the `stage-9.md` directory stays, its name is in the warning). Mutation: catching `ZeroDivisionError` instead of `OSError` turns it red.

### 23. One unreadable historic record makes `INDEX.md` stale instead of marking it, and stale means it names the wrong accepted head — low
Category: correctness (derived-file freshness). `plan_tool/roadmap_index.py` (`collect_index_rows`, `write_roadmap_index`), `plan_tool/roadmap.py` (`refresh_roadmap_index`).
Failure scenario: `collect_index_rows` raises `RoadmapVersionError` for any malformed stored record; `refresh_roadmap_index` warns once on stderr; after a promotion the old `INDEX.md` stays and still labels the previous version `accepted head`.
Suggested fix: unlink it, rewrite it with a could-not-refresh body, or degrade per version.
**Disposition:** deferred, filed as `BACKLOG.md` #448 (b), `decision-needed`. Verified by reading: `refresh_roadmap_index` catches `Exception` and only prints; `write_roadmap_index` replaces the file only after `collect_index_rows` succeeds, and `collect_index_rows` has no per-version degrade. Not applied here: the three remedies change what the index promises (stale marker, absence, or partial rows), a choice the roadmap owner should make; it needs a damaged historic record first, and the file is a human aid, not a reader input.

### 24. `roadmap-plans.md` tells the model that reviewers add feedback and removals rows after publication — low
Category: model-visible text drift. `plan_tool/prompts/roadmap-plans.md:111-112`.
Failure scenario: the pass-3 wording ("Leave `feedback` and `removals` empty; reviewers add those rows after the roadmap is published") gives a false rationale (a published version is immutable; reviewer feedback lives in the ledger through `--submit-feedback`) and names two collections the preceding sentence does not list.
Suggested fix: state the behavior only, and sweep the other stage prompts for the same sentence shape.
**Disposition:** fixed (this change set). The sentence reads "A first run authors `decisions` only; do not author `feedback` or `removals` rows." Sweep by shape and vocabulary (`reviewers`, `removals`, `feedback`) over `roadmap-{domain,constraints,components,plans}.md`: the only other hit is the constraints prompt's "feedback targets" (a different sense, unchanged), and `roadmap-candidate-delta.md` line 79 states a prohibition, not a rationale. No test pins the old text.

### 25. `_print_exhausted` tells the operator to delete the resume directory without naming it — low
Category: operator-visible text. `plan_tool/cli/roadmap_cmd.py` (`_print_exhausted`, the gates-failure arm).
Failure scenario: the message gave no path and no warning that deleting the directory discards every held, already paid stage; the digest-mismatch refusal names the directory only after a failed re-run.
Suggested fix: print the resolved directory and say deletion restarts at stage 1.
**Disposition:** fixed (this change set). `_print_exhausted` takes `repo_root` (the caller already resolves it) and prints the directory through `roadmap.stage_resume_directory` (the CLI must not import the resume module; `test_resume_directory_is_referenced_only_by_the_stage_run_and_its_owner` pins that) with "this discards every held stage; the next run restarts at stage 1". Reproduced first: the new test failed on the old text. Test: `test_gates_exhaustion_names_the_resume_directory_and_that_deleting_it_restarts`. Mutation: replacing the path with a generic phrase turns it red.

### Pass 4 result

Five low findings, none medium. Fixed: 22, 24, 25. Deferred into one entry, `BACKLOG.md` #448: 21 and 23 (design decisions on scoping and index degrade). Findings 22 and 24 are side effects of pass-3 edits (findings 16 and 18).

## Loop conclusion — 2026-10-06

The review loop stops after four passes. Two of the four (passes 1 and 2) found medium crash-recovery gaps, all fixed with reproducing tests. Passes 3 and 4 found nothing above low-medium, and pass 4 found only low severity. Findings 22 and 24 in pass 4 are side effects of pass-3 edits, so the loop is auditing its own edits; the repo's exit-2 rule says to finish applying and stop, not to run a fifth pass.

Remaining deferrals, each tracked outside this change set:

- `BACKLOG.md` #444: callerless escalation, impact-analysis, and structural-rewrite leftovers.
- `BACKLOG.md` #446: callerless stage-feedback revision path and result fields.
- `BACKLOG.md` #447: recover an interrupted publication journal before any writer publishes (includes the hand-edited ledger refusal, finding 19).
- `BACKLOG.md` #448: resume directory scoped by plans directory; `INDEX.md` after a failed refresh (findings 21 and 23).
- The render-version constraint on the byte-stable feedback key comment in `plan_tool/roadmap_artifacts.py`.

### Not verified

- All four reviewers were unable to run programs. The evidence for runtime behavior is the test suite plus the failing-test-first and mutation checks recorded per finding.
- Findings 21 and 23 are verified by reading only; neither was reproduced with a test.
- No multi-plans-dir scenario and no filesystem-level failure (power loss, unwritable runs directory beyond the monkeypatched and directory-entry cases) was exercised end to end.
