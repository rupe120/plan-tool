# Roadmap versioned-from-birth — code review ledger

| Field | Value |
| --- | --- |
| Change | `roadmap-versioned-from-birth`: the roadmap folder holds versions from its first stage run; the removed routes (stage re-entry, enrollment, rollback checkpoint, escalation, impact analysis, structural rewrite) and their modules are deleted |
| Branch | `impl/roadmap-versioned-from-birth` |
| Review range | pass 1: merge-base `main...HEAD` at `7b021100` (40 commits, 137 files); later passes at `db82e058`, `8a5ea497..HEAD`, `49a1663b~1..HEAD` |
| Checks run | Full suite `uv run pytest tests/ -q -n auto` after each fix batch: 13,385 (pass 1), 13,398 (pass 2), 13,400 (pass 3), 13,402 passed (pass 4), 65-67 skipped (`.tmp/roadmap-versioned-from-birth.review{1..4}-fixes.log`); mutation checks recorded per finding |
| Reviewer | headless review sessions, report-only, four passes (`.tmp/roadmap-versioned-from-birth-code-review-1.md` to `-4.md`); no reviewer could run programs, so runtime evidence is the suite plus failing-test-first and mutation checks |
| Disposition | passes 1 to 4 triaged; loop closed 2026-10-06 (see "Closure") |

## Settled decisions (hand to each reviewer)

- Plan files under `docs/implementation-plans/**` are canonical for this change and are not edited by review fixes.
- Out of scope for review: `BACKLOG.md` #444 (callerless `structural_codex_*`, run-log structural/impact/escalation events, update-judgment section and prompt), `BACKLOG.md` #445 (docs outside the version-only docs sweep), and the render-version constraint on the byte-stable feedback key comment in `plan_tool/roadmap_artifacts.py`.
- `NoPublishedRoadmapVersionError` from `create`'s research-target reader is pinned by a test; only a corrupt version store becomes a `CreateError`.
- Callerless leftovers found by review are filed, not deleted, in this change (`BACKLOG.md` #446).

## Findings

Every claim was static reading; each was reproduced (failing test first) or checked in the driving session before a fix. "fixed" below means fixed in this change set (no per-finding commit is recorded).

Pass 1 (`7b021100`):

1. medium, fixed: recovery did not recognize a completed root generation because the ledger member was missing from the expected member list (`roadmap_revision_publish.py`; a crash after the head write left a journal every guarded writer refused). The recognizer now expects the version record, brief, four artifacts, the initial ledger (`old=None`), then the selector; the masking test now feeds `captured[0]` unmodified; two sibling tests that pinned the old shape publish the real member list. New: `test_recognizer_accepts_the_real_root_member_list_including_the_initial_ledger`, `test_recognizer_refuses_a_root_member_list_that_is_not_exactly_the_published_one`. Mutation removing the ledger member turns five tests red.
2. low-medium, fixed: a corrupt or missing version store was an uncaught exception in `create --from-existing` on a roadmap-promoted seed (`RoadmapVersionError`). `_confirm_invalidated_roadmap_seed` prints and returns `False`; `_load_roadmap_research_targets` raises `CreateError`; missing head still raises `NoPublishedRoadmapVersionError`. Tests `test_corrupt_accepted_head_is_an_error_message_not_a_traceback`, `test_corrupt_accepted_head_is_a_create_error_not_a_traceback` fail with the fix stashed.
3. low-medium, tracked #446: dead stage-feedback revision path and never-populated `RoadmapResult` fields. The review's "only test callers" claim was partly wrong (machine-verified counts in #446: `_run_bounded_stage_feedback`, `_check_predecessor_review_rows`, `_awaiting_review_count`, `_newly_settled_decision_ids`, `_feedback_counts_by_state`, `_has_open_feedback` have no caller anywhere; three result fields are set by neither construction). `invalidated_seed_count` in `run_log.py` is a different record (#444), not in #446.
4. low, fixed: `DATA_CONTRACT.md` and `docs/OPERATIONS.md` described removed run-log events and preflight categories; `check` list now names the emitted values, `RoadmapStageWritten` describes one event per held stage with `replaced` always `false`, removed bullets dropped. Declined: adding the categories to a drift test (documented prose; no consumer needs it closed).
5. low, fixed: operator/model-visible text still described on-disk artifacts and stage re-entry (`roadmap_cmd.py` help/docstring, `roadmap.py` docstrings, four `roadmap-*.md` stage prompts); `docs/cli/roadmap.md` regenerated; the byte-stable key comment untouched.
6. low, fixed: `_create_handoff_lines` `plans_dir` fallback computed the roadmap folder; `plans_dir` is now a required keyword (test comment corrected, not the fixture line).
7. low, fixed: backlog entries described removed rollback/checkpoint/enrollment routes; after verifying each subject is gone, #398, #399, #400, #401, #274, #275, #429 and two `BUG_BACKLOG.md` entries deleted, dead clauses trimmed from #355 and one receipt entry; `BUG_BACKLOG.md` joins `_REMOVED_ROUTE_DOC_FILES`. Dated closed entries and the connectivity-recovery entry (its design decision) left as written.
8. low, fixed in part: `current =` spacing and a ledger-less-roadmap comment corrected. Declined: the successor-slug remedy on the missing-ledger read (different site from decision settlement, where absence is supported; reachable only by hand-deleting the ledger; no test pins a new message).

Pass 2 (`db82e058`; six findings, no wrong-content or store-corruption defect; not clean):

9. medium, fixed: a SIGKILL during a durable write left `.<name>.<random>.tmp` that `_pre_head_state_paths` counted, blocking every retry with `RoadmapPreHeadStateError`. `fileio.is_write_temp_name` (leading dot, `.tmp` suffix, at least three dots) is skipped; any other stored file still counts. Tests `test_stray_durable_write_temp_files_are_not_pre_head_state`, `test_a_real_stored_file_still_refuses_even_when_it_resembles_a_temp_name`; mutations (drop filter; loosen to `endswith(".tmp")`) turn them red. Declined: unlinking temp siblings in recovery (inert once ignored).
10. medium-low, fixed in part, deferred in part: after a crash between head write and journal unlink no ordinary writer recovers and the refusal named no route. Fixed: the refusal names the journal path and `plan-tool roadmap <slug> --from-existing <brief>`; `docs/how-to/roadmap.md` § 3 and `RUNBOOK.md` updated; test `test_publish_beside_a_leftover_journal_names_the_recovery_command_and_changes_nothing`. Deferred, tracked #447: recover-before-publish in the shared writer guard and unrecoverable non-root journal kinds beside a head (design decision).
11. low-medium, fixed: `delete_resume` failing after the head commit reported a published roadmap as a failed run; the call warns and returns the completed result. Test `test_a_failing_resume_cleanup_after_the_head_commit_warns_and_still_completes`; mutation (catch `ZeroDivisionError`) red.
12. low, fixed: the completed-root recognizer re-implemented initial-ledger construction; `roadmap_feedback_ledger.initial_ledger(slug, ledger_state)` is the one construction. Test `test_initial_ledger_bytes_are_one_construction_shared_by_publisher_and_recognizer`.
13. low, fixed in part: first-run stage loop sent revision-era correction text and rationale; retry correction now reads in first-run terms, predecessor branches deleted (`_authored_review_rows` takes the artifact alone), CLI exhaustion line updated. Test `test_the_retry_correction_names_the_dropped_entries_in_first_run_terms`. Producer-less names tracked #446 (`source_recheck` of `_run_stage`, `RoadmapSourceAdmissionError` raises/handlers, `_StageOutcome.invalid_detail` and `.reused_predecessor`, `OUTCOME_STAGE_INVALID`/`_print_invalid`, `OUTCOME_COMPLETED_NO_CHANGE`/`_print_completed_no_change`); not deleted here per the settled decision.
14. low, fixed: resume-directory files were written without fsync; both writers use `durable_write_bytes` and `read_held_stages` skips write-temp names silently while other strays still warn. Tests `TestResumeWritesAreDurable`, `TestInterruptedWriteLeftoversAreNotWarnedAbout`.

Pass 3 (`8a5ea497..HEAD`; none above low-medium; low-yield by severity):

15. low-medium, fixed: `_require_no_accepted_head` called `delete_resume` unguarded, turning the head refusal into a raw `OSError` and skipping the index refresh; `_delete_resume_or_warn` serves both sites. Test `test_a_failing_resume_cleanup_beside_an_accepted_head_still_refuses_and_refreshes_the_index`; mutation red.
16. low-medium, fixed: stage files after a gap or damaged stage were warned as "not held" but left on disk, so a later run could re-gate a stale stage; `_run_roadmap` calls `discard_stages_from(repo_root, slug, len(held.stages) + 1)` after the digest check. Test `test_stages_after_a_damaged_stage_are_discarded_so_a_later_run_cannot_regate_them`; mutation red.
17. low, declined (no code change): continuing in memory when the resume directory is unwritable would break the owner-decided resume guarantee; failing at the first write bounds loss to one stage reply (`cannot hold stage 1 for resume (...)` via `RoadmapEnvironmentalError`); `docs/how-to/roadmap.md` § 3 states it.
18. low, fixed: `roadmap-plans.md` still told the model it may author `feedback` and `removals`; sentence replaced and "a newly authored or revised row" became "a newly authored row" after a vocabulary sweep of all four stage prompts and the other roadmap prompts (remaining hits legitimate).
19. low, tracked #447: root-journal recognizer pins initial ledger bytes, so a hand edit between a crash and recovery makes recovery refuse with no remedy; same class as 10. Remedy options recorded there: exempt the ledger member once the head names the published version, or name the hand-removal remedy in the refusal.
20. low, declined (documented): the newly created resume directory chain is not fsynced; a power loss costs only regeneration of held stages, nothing published or corrupted.

Pass 4 (`49a1663b~1..HEAD`; five low, no medium; eleven crash points walked):

21. low, tracked #448 (a), `decision-needed`: resume directory keyed by (repo root, slug) while head and writer guard are keyed by plans directory, so two plans dirs sharing a slug can delete/reuse each other's held stages; scoping choice (path vs recorded owner) is a design decision, bounded loss, nothing published affected. Verified by reading only.
22. low, fixed: `discard_stages_from` could raise at preflight on a stray entry the resume module promises only to warn about (side effect of the finding 16 fix); each entry is unlinked in `try/except OSError`, warning and continuing. Test `test_discard_warns_and_continues_when_an_entry_cannot_be_removed`; mutation red.
23. low, tracked #448 (b), `decision-needed`: one unreadable historic record makes `INDEX.md` stale (still labeling the previous version `accepted head`) instead of marking it; remedies (stale marker, absence, partial rows) change what the index promises, so the owner chooses. Verified by reading only.
24. low, fixed: `roadmap-plans.md` gave a false rationale ("reviewers add those rows after the roadmap is published"); now "A first run authors `decisions` only; do not author `feedback` or `removals` rows." Sweep over the four stage prompts found no other live hit.
25. low, fixed: `_print_exhausted` told the operator to delete the resume directory without naming it; it now prints the directory via `roadmap.stage_resume_directory` (the CLI must not import the resume module; `test_resume_directory_is_referenced_only_by_the_stage_run_and_its_owner`) and says deleting restarts at stage 1. Test `test_gates_exhaustion_names_the_resume_directory_and_that_deleting_it_restarts`; mutation red.

## Closure

Closure label: **stopped at exit 2** (the loop was auditing its own edits; neither converged nor clean). Passes 1 and 2 found medium crash-recovery gaps, all fixed with reproducing tests; passes 3 and 4 found nothing above low-medium, and findings 22 and 24 were side effects of pass-3 edits (16 and 18). Per the exit-2 rule the loop finished applying and stopped; no fifth pass.

## Tracked

- **tracked** `BACKLOG.md` #444: callerless escalation, impact-analysis, and structural-rewrite leftovers.
- **tracked** `BACKLOG.md` #446: callerless stage-feedback revision path and result fields (findings 3, 13).
- **tracked** `BACKLOG.md` #447: recover an interrupted publication journal before any writer publishes (findings 10, 19).
- **tracked** `BACKLOG.md` #448: resume directory scoped by plans directory; `INDEX.md` after a failed refresh (findings 21, 23).
- The render-version constraint on the byte-stable feedback key comment in `plan_tool/roadmap_artifacts.py` (settled out of scope).

Not verified: findings 21 and 23 are verified by reading only; no multi-plans-dir scenario and no filesystem-level failure (power loss, unwritable runs directory beyond the monkeypatched and directory-entry cases) was exercised end to end.
