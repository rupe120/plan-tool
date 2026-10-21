# Step 10 — Publish scope-out changes through the concept authority

## Summary

This step routes scope-out publication in `plan_tool/scope_out.py` through the all-or-recoverable concept authority delivered by step 3. One publication must cover the narrowed plan, concept record, rendered scope prose, forward seed, and every detail archive or rename. `plan_tool/cli/scope_out_cmd.py` and `plan_tool/cli/convergence_cmd.py` must preserve the authority’s distinct restored-failure and rollback-failed results, including exact uncertain paths. On green, a successful carve publishes one verified generation, a recoverable failure restores the original generation without leaving an orphan seed, and an unverified rollback stops with precise diagnostics.

## Table of Contents

- [Summary](#summary) — The scope-out migration and its observable result.
- [Why](#why) — Why the current local journal is not a sufficient publication boundary.
- [Input](#input) — The step 3 authority and existing scope-out contracts this step consumes.
- [Files (creates vs edits)](#files-creates-vs-edits) — The production and test files changed by this step.
- [Implementation](#implementation) — How to prepare and publish one complete scope-out transaction.
- [Tests](#tests) — Unit and CLI coverage for success, refusal, restoration, and uncertainty.
- [Acceptance criteria](#acceptance-criteria) — Observable checks required for completion.
- [References](#references) — Filesystem, locking, hashing, and failure-test guidance.
- [Deferred](#deferred) — Related work owned by later steps.

## Why

`plan_tool/scope_out.py:apply_narrow` currently coordinates detail moves with an in-memory `_rollback` journal, then writes the plan and concept sidecar through separate paths. `plan_tool/scope_out.py:scope_out_step` writes the forward seed before calling that code, so a failure can leave the seed published while the plan is restored, and rollback failures can be hidden by best-effort restoration. Step 3 provides the durable concept publication authority needed to treat every scope-out artifact as one recoverable operation; this step must remove the local publication bypass and preserve the authority’s full failure information at both CLI surfaces.

## Input

- **Step 3 publication outcome** — consume the all-or-recoverable coordinator, its lock-ownership contract, and its distinct success, restored-failure, and rollback-failed results. Do not duplicate its staging, durable journal, digest verification, recovery, or rollback rules in `plan_tool/scope_out.py`.
- **Typed scope-out publication input** — use the scope-out intent prepared through the step 2 contract and published by step 3. It must represent the narrowed plan, original and target concept state, forward-seed target and contents, and detail-file target changes as one operation.
- **Scope-out graph preview** — `plan_tool/scope_out.py:compute_narrow` and `NarrowPreview` remain the source of the narrowed plan, blocker list, renumbering, detail archives, detail renames, cursor, and final plan status.
- **Concept preparation** — `plan_tool/scope_out.py:_prepare_concept_narrow_update` and `ownerless_carved_concept_ids` preserve the rule that only concepts losing their final committed owner change from approved include to approved defer.
- **Command policy** — `plan_tool/scope_out.py:scope_out_step` retains the blocker, opt-in, and `yes → non-TTY → interactive` confirmation gates. `plan_tool/cli/convergence_cmd.py:classify_report_staleness` remains the saved-diagnosis freshness gate.
- **Existing result shape** — `plan_tool/scope_out.py:ScopeOutResult` and `NarrowResult` remain the command-facing description of the carve. Extend them only as needed to carry the authority’s publication status and exact uncertain paths.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `plan_tool/scope_out.py` — prepare one complete scope-out publication, delegate live changes to the step 3 authority, remove the local concept save and in-memory publication journal, and carry publication failure details through `ScopeOutResult`.
  - `plan_tool/cli/scope_out_cmd.py` — render successful, restored-failure, and rollback-failed scope-out results without losing uncertain paths.
  - `plan_tool/cli/convergence_cmd.py` — replace the orphan-seed-specific `NarrowError` handling in `_actuate_scope_out` with the shared publication result contract.
  - `tests/test_scope_out.py` — cover complete artifact preparation, authority delegation, no-write exits, restoration, rollback failure, and removal of direct publication.
  - `tests/cli/test_scope_out_cmd.py` — cover the command’s synchronized success and failure messages.
  - `tests/cli/test_convergence_cmd.py` — cover the convergence actuator’s synchronized success, restored failure, rollback-failed diagnostics, and unchanged freshness gates.
  - `plan_tool/cli/app.py` — **required footprint addition:** retain the `RepoMutationLock` yielded in `main` and make its ownership proof available to mutating handlers. Step 3 requires an explicit token and forbids nested acquisition, but `main` currently discards the yielded value. This addition is required for both scope-out CLI entry points to call the publishing core under the lock already held by dispatch.

## Implementation

The foundational logic is: **publish the forward seed, narrowed plan, concept changes, scope prose, and detail moves as one scope-out intent through the concept authority**.

- **Keep preview and policy local.** Continue using `plan_tool/scope_out.py:scope_out_step` to reparse the plan, call `compute_narrow`, reject `NarrowPreview.blockers`, enforce `allow_scope_out`, and run `_confirm_scope_out`. Blocked, recommend-only, declined, and non-TTY calls must return before staging or publishing.

- **Prepare every final artifact before publication.** After confirmation, derive:
  - The forward-seed path and final contents using `render_carved_seed` or `render_carved_region_seed`.
  - The narrowed target plan from `NarrowPreview.narrowed_plan`.
  - The original and prepared concept state from `_prepare_concept_narrow_update`.
  - The final archive and rename targets represented by `NarrowPreview.archive_details` and `NarrowPreview.detail_renames`.
  - The final `Deferred` and `Out of scope` prose required by the prepared concept decisions.

  Submit these values as one typed scope-out request. Do not write the seed, create archive directories, rename details, save concepts, or write the plan while building the request.

- **Use one final path set.** Fix every source and target path before the authority begins staging. Reject destination collisions, missing expected sources, stale plan frontmatter, changed concept bytes, or changed detail sources before the first live replacement. Preserve `compute_narrow`’s deterministic archive and rename ordering as input to the transaction, but let the authority own commit and reverse-operation ordering.

- **Publish scope prose with the concept decision.** When an ownerless concept changes from include to defer, the target plan’s owned scope sections and target concept record must describe the same decision. Do not retain the current shape where `apply_narrow` can save a changed sidecar without updating the rendered plan sections.

- **Support the no-sidecar case explicitly.** A carve with no concept-owned work still publishes its seed, plan, and detail changes through the scope-out intent. Absence of a concept record is valid only when the carved steps carry no concept ownership that requires validation or transition.

- **Remove direct writers from `apply_narrow`.** Replace its `write_plan`, `save_concepts`, raw `Path.write_text`, `_archive_file_strict`, and `_rollback` publication tail with preparation and delegation to the step 3 authority. `apply_narrow` may remain the public narrow entry point for compatibility, but it must no longer be an independent transaction coordinator.

- **Do not preserve seed-first partial publication.** The forward seed remains an important output, but it is now a member of the transaction. If staging or commit fails and restoration succeeds, the seed must return to its original bytes or original absent state. Existing tests and CLI prose that promise a durable orphan seed after failure must change.

- **Preserve exact output reporting.** A successful authority result should still populate `NarrowResult.archived`, `NarrowResult.migrated`, renumbering, cursor, and plan status. These values should come from the prepared and verified operation set rather than from observing partially completed moves.

- **Keep failure states distinct.**
  - A preflight or stale-state refusal performs no write and reports the refusal.
  - A publication failure followed by verified restoration reports a recoverable failure and confirms that the original generation remains.
  - A rollback-failed result reports every uncertain path exactly as returned by the authority and must not claim that the plan was restored.
  - Do not convert rollback failure into a generic `NarrowError`, omit paths, or infer certainty from the first failed operation.

- **Share rendering across both command surfaces.** Extend `plan_tool/cli/scope_out_cmd.py:render_scope_out_result` so `cmd_scope_out` and `plan_tool/cli/convergence_cmd.py:_actuate_scope_out` display the same publication statuses and uncertain-path list. Keep command-specific retry guidance in each caller’s existing `recommend_hint`.

- **Remove orphan-seed discovery from convergence.** `plan_tool/cli/convergence_cmd.py:_actuate_scope_out` no longer needs the pre/post seed glob used to identify a seed left by `NarrowError`. Report the structured publication result instead. Preserve `classify_report_staleness`, the unattended refusal for unverifiable history, and the interactive warning path unchanged.

- **Pass lock ownership without reacquiring it.** Update `plan_tool/cli/app.py:main` to retain the value yielded by `repo_mutation_lock` and expose it to the selected handler through a narrow internal argument or command context. Forward that proof through `cmd_scope_out` and `_actuate_scope_out` into `scope_out_step` and the step 3 publishing core. Direct library calls to `scope_out_step` may use step 3’s lock-acquiring wrapper; a CLI call already under `main` must not use that wrapper or attempt nested acquisition.

- **Keep deterministic and backend-free behavior.** `scope_out_step` must continue to take no LLM invoker and must spend no backend calls. Publication recovery and digest verification are filesystem work, not an authoring round trip.

## Tests

- `tests/test_scope_out.py:test_scope_out_prepares_one_complete_publication_intent` — one request contains the seed, narrowed plan, concept target, scope prose, detail archives, and detail renames.
- `tests/test_scope_out.py:test_scope_out_publishes_plan_concepts_seed_and_details_together` — success leaves every live artifact at the verified target generation.
- `tests/test_scope_out.py:test_scope_out_ownerless_concept_updates_record_and_scope_prose` — the sole owner changes to defer in both the concept record and rendered plan sections.
- `tests/test_scope_out.py:test_scope_out_surviving_owner_preserves_include_decision` — a committed surviving owner prevents the concept transition.
- `tests/test_scope_out.py:test_scope_out_without_concept_record_publishes_nonconcept_artifacts` — a plan with no concept-owned carved work can publish seed, plan, and detail changes.
- `tests/test_scope_out.py:test_scope_out_owned_work_without_current_concept_record_refuses_before_staging` — required concept state that is missing or stale causes no filesystem change.
- `tests/test_scope_out.py:test_scope_out_blocked_declined_and_recommend_only_do_not_publish` — every no-apply gate avoids staging and authority calls.
- `tests/test_scope_out.py:test_scope_out_seed_staging_failure_leaves_every_live_artifact_unchanged` — failure before commit produces no seed, plan, concept, or detail change.
- `tests/test_scope_out.py:test_scope_out_replacement_failure_restores_complete_original_generation` — a failure after each artifact boundary restores original bytes and original absence.
- `tests/test_scope_out.py:test_scope_out_restored_failure_leaves_no_orphan_seed` — verified rollback removes a newly created seed rather than preserving the old seed-first behavior.
- `tests/test_scope_out.py:test_scope_out_rollback_failed_preserves_exact_uncertain_paths` — the result contains the authority’s complete uncertain-path set without reduction.
- `tests/test_scope_out.py:test_apply_narrow_has_no_direct_plan_concept_or_detail_publication` — `apply_narrow` delegates instead of calling the former writers and rename journal.
- `tests/test_scope_out.py:test_scope_out_cli_lock_token_reaches_publishing_core` — the lock held by CLI dispatch is forwarded and the authority does not acquire a nested lock.
- `tests/cli/test_scope_out_cmd.py:test_apply_yes_publishes_complete_scope_out_generation` — the direct command publishes synchronized plan, concept, prose, seed, and detail results.
- `tests/cli/test_scope_out_cmd.py:test_restored_publication_failure_reports_no_changes` — a recoverable failure exits with clear restored-state output and no orphan-seed claim.
- `tests/cli/test_scope_out_cmd.py:test_rollback_failed_lists_every_uncertain_path` — the command prints the exact uncertain paths and does not claim restoration.
- `tests/cli/test_convergence_cmd.py:test_apply_scope_out_uses_authority_without_nested_lock` — convergence actuation publishes under the dispatch-owned lock.
- `tests/cli/test_convergence_cmd.py:test_apply_scope_out_restored_failure_reports_no_orphan_seed` — the old seed-glob failure message is gone and restored state is reported.
- `tests/cli/test_convergence_cmd.py:test_apply_scope_out_rollback_failed_exits_nonzero_and_lists_paths` — unverified restoration is a real failure-to-complete with complete diagnostics.
- `tests/cli/test_convergence_cmd.py:test_apply_scope_out_staleness_gates_remain_nonmutating` — mismatch and unverifiable unattended history still stop before publication.

### Test-creation order (feature step)

1. Add tests for the complete scope-out intent and its final path set.
2. Add synchronized success tests for concept transitions, scope prose, seeds, plans, and detail moves.
3. Add blocked, declined, recommend-only, stale, malformed, and no-sidecar cases.
4. Add staging and replacement failure tests that require verified restoration and no orphan seed.
5. Add rollback-failed tests that pin the complete uncertain-path set.
6. Add lock-forwarding tests for direct scope-out and convergence dispatch.
7. Update existing seed-first failure tests and CLI messages to the transactional contract.
8. Run all existing graph, range-carve, cursor, renumbering, backend-free, and staleness tests unchanged.

Every new and updated test in the three scoped test files must be green before this step is considered finished.

## Acceptance criteria

- A confirmed scope-out submits exactly one publication request covering the forward seed, narrowed plan, concept record when applicable, rendered scope prose, and all detail archive or rename operations.
- Blocked, recommend-only, declined, non-TTY, stale, malformed, and invalid-concept calls make no live filesystem change.
- A successful scope-out leaves every target at the authority-verified generation and returns accurate `NarrowResult` archive, migration, renumbering, cursor, and status values.
- A concept that loses its final committed owner is approved as deferred in the concept record and appears in the plan’s rendered deferred scope; a concept with a committed surviving owner remains included.
- A caught publication failure restores and verifies the entire original generation, including removing a seed that did not exist before the call.
- A failed restoration remains distinct from an ordinary publication failure and reaches both CLI surfaces with the complete set of uncertain paths.
- `plan_tool/scope_out.py:apply_narrow` no longer directly calls `write_plan`, `save_concepts`, raw concept or plan writes, `_archive_file_strict`, or `_rollback` to publish a scope-out.
- `plan_tool/cli/convergence_cmd.py:_actuate_scope_out` no longer scans for an orphan seed after failure.
- `plan_tool/cli/app.py:main` forwards the already-held `RepoMutationLock` to scope-out publication, and neither scope-out CLI path reacquires it.
- `plan_tool/scope_out.py:scope_out_step` remains deterministic, accepts no invoker seam, and performs no backend call.
- All new and existing tests in `tests/test_scope_out.py`, `tests/cli/test_scope_out_cmd.py`, and `tests/cli/test_convergence_cmd.py` pass.

## References

- [Python 3.13 os — Miscellaneous operating system interfaces](https://docs.python.org/3.13/library/os.html) — Use the `os.replace`, `fsync`, and directory-operation contracts inherited from the step 3 coordinator.
- [Python 3.13 tempfile — Generate temporary files and directories](https://docs.python.org/3.13/library/tempfile.html) — Read for same-filesystem staging of new seeds and replacement artifacts.
- [POSIX.1-2024 Rationale — File-system atomicity and durability](https://pubs.opengroup.org/onlinepubs/9799919799/xrat/V4_xbd_chap01.html) — Use the durability guidance when verifying the coordinator’s journal and replacement ordering.
- [Python 3.13 fcntl — File locking interfaces](https://docs.python.org/3.13/library/fcntl.html) — Read for the non-reentrant repository mutation lock that CLI dispatch already owns.
- [Python hashlib — Secure hashes and message digests](https://docs.python.org/3/library/hashlib.html) — Use SHA-256 digests to compare original, staged, restored, and live artifact bytes.
- [pytest — Monkeypatching functions and environments](https://docs.pytest.org/en/stable/how-to/monkeypatch.html) — Use injected failure seams to cover each staging, replacement, and restoration boundary.

## Deferred

- Direct-writer enforcement — step 11 owns the repository scan that blocks production bypasses through `save_concepts`, `write_concepts`, `concepts_path`, and equivalent raw writes.
- Automatic repair after rollback failure — the authority reports every uncertain path and stops; choosing or rebuilding a generation remains operator work.
- General repository transactions — the step 3 coordinator remains limited to typed concept publication operations and their declared artifacts.
