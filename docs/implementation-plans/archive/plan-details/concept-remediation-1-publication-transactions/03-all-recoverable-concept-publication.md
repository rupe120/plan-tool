# Step 3 — Add all-or-recoverable concept publication

## Summary

This step adds the durable publication coordinator in `plan_tool/concept_sync.py` and covers it in `tests/test_concept_sync.py`. It consumes the typed publication intents from step 2, stages and validates every artifact before changing live files, and records enough durable state to recover an interrupted commit. The key design decision is to promise all-or-recoverable publication, not filesystem-wide atomicity: a successful operation is fully verified, a normal failure restores the original state, and a failed restoration reports the exact uncertain paths. On green, a later publication can safely recover an interrupted operation before committing new concept state.

## Table of Contents

- [Summary](#summary) — The publication and recovery behavior delivered by this step.
- [Why](#why) — Why the current in-memory rollback is not enough.
- [Input](#input) — Contracts consumed from step 2 and existing repository state.
- [Files (creates vs edits)](#files-creates-vs-edits) — The two files changed by this step.
- [Implementation](#implementation) — The durable journal, commit, recovery, result, and lock rules.
- [Tests](#tests) — Unit and subprocess cases for success, failure, and recovery.
- [Acceptance criteria](#acceptance-criteria) — Observable proof of all-or-recoverable publication.
- [References](#references) — Primary filesystem, hashing, and test documentation.
- [Deferred](#deferred) — Caller migrations and repository-wide wiring owned elsewhere.

## Why

`plan_tool/concept_sync.py:synchronize_concepts` currently stages each file separately and tracks completed replacements only in a local `published` list. Its `_restore` path can undo caught failures, but a process or host stop loses that in-memory state, and a failed restoration is reduced to a message without a complete set of uncertain artifacts. Concept publication needs a durable transaction record so mixed generations can be detected after restart, restored or safely completed, and kept from overlapping with another publication.

## Input

- **Step 2 publication contract.** Consume the typed intent and result shapes introduced by step 2. This step adds filesystem coordination around those validated requests; it must not duplicate or loosen their intent-specific validation.
- **Original and target snapshots.** Preserve the distinction used by `plan_tool/concept_sync.py:synchronize_concepts`: durable state is compared with the original snapshot, while the prepared target contains the requested changes.
- **Plan and concept integrity.** Continue using `plan_tool/schema.py:Plan`, `plan_tool/concept_tree.py:ConceptTree`, and `plan_tool/concept_tree.py:_validate_tree` before staging any live change.
- **Final-byte fingerprint.** Preserve the framing used by `plan_tool/concept_sync.py:_fingerprint`, but supply the exact final ordered detail set from step 2’s prepared artifact contract: staged bytes for replacements, explicit removals, and compare-and-swap snapshots for unchanged details. Do not fingerprint the pre-transaction filesystem or recompute a different generation after commit.
- **Repository mutation ownership.** `plan_tool/repo_lock.py:RepoMutationLock` is the existing proof that one repository mutation is active. `plan_tool/cli/app.py:main` already acquires the non-reentrant lock around mutating command dispatch.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `plan_tool/concept_sync.py` — add the bounded publication coordinator, durable journal and recovery operations, live-byte verification, explicit lock-ownership boundary, and precise failure results.
  - `plan_tool/cli/app.py` — retain the yielded repository lock token, run recovery at each ordinary command’s effective mutation boundary, exempt the explicit operator-recovery handler from pre-dispatch recovery, and pass lock ownership through command context.
  - `plan_tool/cli/publication_recovery_cmd.py` — add the explicit operator workflow for selecting and verifying an original or staged generation after rollback failure.
  - `plan_tool/repo_lock.py` — expose the narrow token validation/context surface needed by the publishing core without making the lock reentrant.
  - `tests/test_concept_sync.py` — add success, failure-injection, rollback-failure, durability, lock, and subprocess restart-recovery coverage.
  - `tests/cli/test_app_lock.py` — prove recovery precedes mutating dispatch and the yielded token reaches command context.
  - `tests/cli/test_publication_recovery_cmd.py` — cover operator selection, digest verification, interruption, refusal, and marker cleanup.
  - `tests/test_repo_lock.py` — cover token identity, process/repository matching, and unchanged non-reentrant behavior.

## Implementation

The foundational logic is **a durable publication state machine that leaves every artifact either fully verified at the requested generation or recoverable from an on-disk journal**.

- **Keep preparation separate from publication.** Accept the validated publication request produced through step 2 and turn it into a fixed ordered set of artifact operations. Finish all schema checks, concept-reference checks, rendering, fingerprint assignment, path checks, and compare-and-swap checks before the first live replacement.

- **Keep the coordinator concept-specific.** Support the closed artifact-action union represented by the step 2 concept publication contract: plan/sidecar/detail file publication, manifest edits, collision archives, paired directory moves, forward seeds, and resume promotion or cleanup. Reject any untyped filesystem action. Do not turn `plan_tool/concept_sync.py` into a general repository transaction library.

- **Capture exact starting state.** Record each target’s path, whether it existed, its original bytes or a durable backup, and its digest. Also record the staged path and digest, operation order, transaction identifier, and completion state. A missing original is a real state that recovery must restore by removing the newly published target.

- **Manifest directory trees recursively.** For each typed directory move, walk the source without following symlinks and record a canonical, sorted manifest containing the root existence, every descendant’s normalized relative path and entry type, each regular file’s byte digest, each symlink’s link text, and the required destination absence or prior manifest. Reject path escape, duplicate normalized paths, sockets, devices, FIFOs, and other unsupported entry types before staging. Persist this manifest and any required durable backup in the journal so restart and operator recovery do not depend on a later best-effort directory listing.

- **Stage before commit.** Write every replacement to durable staging storage on the same filesystem as its live target. Flush and `fsync` staged file contents before declaring the transaction ready. If staging or validation fails, remove staging data where possible and leave all live artifacts unchanged.

- **Make the journal durable first.** Store the transaction under a transaction-specific path within the repository’s `.plan-tool` state. The ready journal and its directory entry must be durable before the first live replacement. Journal updates must never claim an operation completed before its replacement and affected parent directory are durable.

- **Use atomic replacement per file.** Follow the same-file-system temporary-file approach already used by `plan_tool/concept_sync.py:_atomic_publish`, but treat each `os.replace` as one operation in a larger recoverable sequence. Do not describe the collection of replacements as atomic.

- **Derive and verify the final bundle fingerprint.** Before commit, derive `plan_fingerprint` from the exact staged plan bytes and the final ordered detail set: staged replacement bytes for changed details, explicit absence for removed details, and compare-and-swap snapshots for unchanged details. Immediately before the first replacement, recheck every target and every unchanged fingerprint input. After the last operation, hash every live target and fingerprint input and prove the sidecar names that same final generation. Mark the transaction complete only after these checks and the required parent-directory `fsync` calls succeed.

- **Recover at the effective mutation boundary.** `plan_tool/cli/app.py:main` must retain the `RepoMutationLock` yielded by dispatch and expose it through a scoped command-context accessor consumed by the command-facing publication entry point; `cmd_create` and `cmd_detail` need no new positional token parameter. Definitely mutating commands run automatic recovery before dispatch. `--dry-run` is classified as non-mutating and acquires no recovery side effect. Commands with an interactive/block/decline gate retain the token but defer automatic recovery until immediately before their first actual write. A decline before that boundary remains byte-for-byte non-mutating. Create concept review is different by design: run automatic recovery immediately before its first durable unsigned resume-record save; accepted selections and a later declined final approval may retain only that resume progress, while the plan, finalized concept sidecar, manifest, archives, and details remain unchanged. The explicit `publication-recover` command is the sole dispatch exemption: dispatch acquires and supplies the repository lock but must not invoke ordinary automatic recovery before its handler, because the selected `operator_required` marker is the input that handler must resolve. For an ordinary incomplete journal, compare live, staged, and original digests and choose a direction only when one complete generation is provable. Recovery must be idempotent so another interruption can restart it.

- **Never auto-resolve rollback-failed state.** Persist a terminal `operator_required`/rollback-failed journal marker with the complete uncertain-path set. Startup and publication preflight must block on that marker or contradictory evidence and report it without restoring or completing either generation. Only an explicit operator recovery workflow documented in step 13 may clear or supersede it.

- **Implement explicit operator recovery.** Add a command such as `plan-tool publication-recover <transaction-id> --choose original|staged` in `plan_tool/cli/publication_recovery_cmd.py`. Under the repository lock it must load the named operator-required journal, show the complete affected and uncertain path sets, require explicit confirmation unless `--yes`, verify that every chosen source byte/digest is still available, durably apply the chosen generation with resumable journal markers, verify every live digest and bundle fingerprint, and only then clear the blocking marker. Missing evidence, drift, or a second restoration failure leaves the marker intact. The command is recovery of a recorded transaction, not arbitrary undo.

- **Recheck throughout commit and rollback.** Immediately before each live replacement, compare that target and all not-yet-consumed source/fingerprint inputs with their journaled digests. After each replacement, verify its staged digest again before continuing. Before rollback overwrites or removes any path, compare its current bytes with the state produced by this transaction; external drift converts the journal to operator-required instead of overwriting an editor or foreign process. These per-operation guards supplement the repository lock, which excludes only cooperating plan-tool commands.

- **Recheck directory moves as complete trees.** Immediately before a directory rename, recompute the complete source manifest and destination existence/manifest and require exact equality with the journal. After rename and parent-directory durability, verify the same tree manifest at the destination and the required source absence before marking the operation complete. Rollback may reverse the move only when the destination still matches the transaction-produced tree and the source has the journaled expected absence; after reversal it verifies the original source manifest and destination state. Any descendant addition, removal, byte change, type change, symlink retarget, or competing source/destination creation produces operator-required uncertainty instead of being overwritten. Operator recovery applies the same manifest checks and uses only journaled sources/backups whose full tree manifests remain provable.

- **Fail safely on bad recovery metadata.** A missing, malformed, or contradictory journal must block new publication without guessing. Report the journal and affected paths so the operator does not unknowingly publish over uncertain state.

- **Remove recovery state last.** Delete the transaction journal, backups, and staging files only after the final generation is verified and the cleanup directory changes are durable. Cleanup failure after a verified commit may leave harmless recovery files, but it must not make a later run replay an already completed transaction.

- **Report three distinct outcomes.**
  - Success means every requested artifact matches its staged bytes and no incomplete transaction remains.
  - Recoverable publication failure means the original existence and bytes were restored and verified for every artifact.
  - Rollback failure means restoration could not be proved. Return a distinct status with the complete set of uncertain paths; do not collapse it into `SyncStatus.PUBLICATION_FAILURE` plus an unstructured `rollback_error`.

- **Preserve exact path reporting.** Build uncertain paths from failed or unverifiable restoration checks, not merely from the operation that first raised. Continue attempting every reverse operation so the result names the full uncertain set.

- **Require explicit lock ownership in the publishing core.** The core coordinator must consume a `plan_tool/repo_lock.py:RepoMutationLock` for the same repository and current process. Reject a missing, stale, or different-repository token before staging.

- **Offer a direct-call wrapper.** Library callers that do not already hold the mutation lock need a wrapper that acquires `plan_tool/repo_lock.py:repo_mutation_lock` once and passes the yielded token into the core. The core must never reacquire the lock because `plan_tool/repo_lock.py:acquire_repo_mutation_lock` is deliberately non-reentrant.

- **Keep legacy callers stable during this step.** Do not migrate `plan_tool/cli/scope_review_cmd.py:cmd_scope_review`, `plan_tool/create.py:create_plan`, `plan_tool/detail.py:generate_detail`, or `plan_tool/scope_out.py:apply_narrow` here. Steps 4, 7, 9, and 11 own those integrations. Existing `synchronize_concepts` behavior must remain available until its callers move to the new authority.

- **Retain provenance behavior.** Call `plan_tool/parser.py:refresh_plan_provenance` only after the plan’s live bytes are known to match either the verified target or the verified restored original. Never refresh provenance for an uncertain plan.

- **Use injectable filesystem seams for unit tests.** One way is to group stage, replace, hash, `fsync`, and cleanup operations behind small callables. Keep the production defaults in `plan_tool/concept_sync.py`; the important constraint is that tests can fail each durability boundary without changing real process state.

## Tests

- `test_publication_commits_all_artifacts_and_removes_journal` — every live target matches its staged bytes, the fingerprint matches the published plan, and completed recovery state is removed.
- `test_publication_validates_every_target_before_first_live_write` — invalid intent state, invalid tree state, or a stale original causes no live mutation.
- `test_publication_stages_every_target_before_first_replacement` — commit cannot begin while any artifact remains unstaged or undurable.
- `test_publication_failure_at_each_replacement_restores_original_generation` — each injected replacement failure restores exact prior bytes and prior absence across the full artifact set.
- `test_publication_restores_new_target_to_absent_state` — rollback removes a target that did not exist before the transaction.
- `test_publication_rollback_continues_after_one_restore_failure` — recovery attempts every inverse operation and reports the complete uncertain-path set.
- `test_publication_returns_distinct_rollback_failed_result` — failed restoration is not reported as an ordinary publication failure.
- `test_publication_refuses_changed_target_after_staging` — a compare-and-swap change before commit stops without overwriting concurrent state.
- `test_publication_refuses_changed_unchanged_fingerprint_input` — a detail file used only as a fingerprint input changing after staging blocks commit.
- `test_publication_rechecks_each_target_immediately_before_replace` — external drift after the initial preflight is detected before that target is overwritten.
- `test_directory_move_manifest_covers_descendants_types_and_symlinks` — the journal records a stable recursive manifest without following symlinks and rejects unsupported or escaping entries.
- `test_directory_move_refuses_descendant_drift_before_rename` — additions, removals, content changes, type changes, and symlink retargets after staging prevent the move.
- `test_directory_move_verifies_destination_tree_and_source_absence` — commit is not complete until the full manifest is present at the destination and the source is absent.
- `test_directory_move_rollback_refuses_external_tree_drift` — rollback and operator recovery never reverse over a changed descendant or competing source/destination and retain operator-required state with exact uncertain paths.
- `test_rollback_refuses_to_overwrite_external_drift` — a path changed after this transaction touched it becomes operator-required rather than being blindly restored.
- `test_publication_fingerprints_final_replacement_detail_set` — replacement, removal, and unchanged detail inputs produce the sidecar fingerprint for the exact final bundle.
- `test_publication_verifies_live_bytes_before_success` — a replacement that returns without publishing the staged bytes cannot produce success.
- `test_publication_fsyncs_journal_before_first_live_replacement` — the ready journal and required directory entry become durable before commit starts.
- `test_publication_fsyncs_target_directory_before_marking_operation_complete` — each journal completion marker follows durable replacement.
- `test_recovery_is_idempotent` — repeating recovery after interruption produces the same verified generation without extra mutations.
- `test_recovery_blocks_on_malformed_or_contradictory_journal` — unsafe recovery metadata prevents a new publication and identifies the affected recovery state.
- `test_rollback_failed_journal_requires_operator` — startup never chooses a generation for a journal whose restoration already failed.
- `test_mutating_dispatch_recovers_at_effective_boundary` — every ordinary definitely mutating CLI dispatch invokes recovery under the yielded lock token before its first write, while dry-run, pre-write decline, create-resume, and explicit operator-recovery paths preserve their specified boundaries.
- `test_dry_run_and_prewrite_decline_do_not_recover_or_mutate` — non-mutating flags and interactive declines that occur before any accepted write leave both requested and prior transaction state unchanged.
- `test_create_review_recovers_before_first_resume_write` — create runs automatic recovery before saving its first accepted unsigned selection, and a later approval decline retains only resume progress without publishing final artifacts.
- `test_command_context_supplies_lock_without_authoring_signature_changes` — create/detail publication read the app-scoped token without nested acquisition or new `cmd_create`/`cmd_detail` plumbing.
- `test_operator_recovery_verifies_selected_generation_before_clearing_marker` — the explicit recovery command clears rollback-failed state only after full durable verification.
- `test_operator_recovery_dispatch_bypasses_automatic_recovery_under_lock` — dispatch supplies the repository lock to `publication-recover` without pre-dispatch recovery blocking on the selected operator-required marker.
- `test_subprocess_restart_recovers_interrupted_publication` — a subprocess stopped between live replacements leaves a journal that a fresh process uses to restore or complete one consistent generation.
- `test_publishing_core_requires_matching_repo_lock` — missing, stale, wrong-process, and wrong-repository lock tokens are rejected before staging.
- `test_direct_publication_wrapper_acquires_lock_once` — the wrapper acquires one lock and the core does not attempt nested acquisition.
- `test_existing_synchronize_concepts_characterization_remains_green` — current success, divergence, conflict, and caught-failure behavior remains available until caller migration.

### Test-creation order (feature step)

Add the tests with the implementation in this order:

1. Add result-state tests for success, restored failure, and rollback failure.
2. Add preflight, staging, compare-and-swap, and final-byte fingerprint tests.
3. Add parameterized replacement and restoration failure tests.
4. Add journal ordering and file/directory durability tests.
5. Add idempotent recovery and malformed-journal refusal tests.
6. Add explicit-lock and no-nested-acquisition tests.
7. Add the subprocess interruption and fresh-process recovery test.
8. Re-run the existing `synchronize_concepts` characterization cases.

Every new test in `tests/test_concept_sync.py` must be green before this step is considered finished.

## Acceptance criteria

- A valid step 2 publication request commits only after every target is validated, staged, flushed, and represented by a durable ready journal.
- No live artifact changes when validation, staging, lock verification, or the final pre-commit compare-and-swap check fails.
- A caught failure after any live replacement restores and verifies every target’s original bytes or original absent state.
- A directory move commits or reverses only after exact recursive source/destination manifests and required absence states match; descendant drift or unsupported entry types stop safely and preserve operator-required recovery evidence.
- A restoration failure returns a distinct rollback-failed result containing exactly every path whose original or target state cannot be verified.
- An abrupt subprocess stop between replacements leaves durable recovery state, and a fresh process restores or completes one verified generation before another concept publication.
- Re-running recovery is safe and produces the same result.
- Success proves that every live artifact matches its staged digest and that the concept record fingerprints the exact published plan bytes.
- Recovery metadata is removed only after final-byte verification and required file and directory durability operations complete.
- The publishing core rejects calls without a matching live `RepoMutationLock`; the direct-call wrapper acquires that lock exactly once.
- `plan_tool/concept_sync.py:synchronize_concepts` remains callable by existing production callers until their owning migration steps land.
- All existing and new tests in `tests/test_concept_sync.py` pass.

## References

- [Python 3.13 os — Miscellaneous operating system interfaces](https://docs.python.org/3.13/library/os.html) — Read the `os.replace`, `fsync`, file-descriptor, and directory-operation contracts used by commit and recovery.
- [Python 3.13 tempfile — Generate temporary files and directories](https://docs.python.org/3.13/library/tempfile.html) — Use secure same-filesystem staging without exposing partial target contents.
- [POSIX.1-2024 Rationale — File-system atomicity and durability](https://pubs.opengroup.org/onlinepubs/9799919799/xrat/V4_xbd_chap01.html) — Use the durability discussion to order file flushes, replacement, directory flushes, and journal markers.
- [Python hashlib — Secure hashes and message digests](https://docs.python.org/3/library/hashlib.html) — Use SHA-256 to verify original, staged, and live byte generations.
- [pytest — Monkeypatching functions and environments](https://docs.pytest.org/en/stable/how-to/monkeypatch.html) — Use controlled filesystem seams for failure-boundary tests; use a subprocess for abrupt-stop recovery.

## Deferred

- Scope-review caller migration — step 4 moves `plan_tool/cli/scope_review_cmd.py:cmd_scope_review` to the new authority and preserves its result distinctions.
- Create publication migration — step 7 moves `plan_tool/create.py:create_plan` after step 6 prepares its artifact bundle.
- Detail publication migration — step 9 moves detail files and concept deferrals into one publication request.
- Scope-out publication migration — step 11 replaces the in-memory journal in `plan_tool/scope_out.py:apply_narrow` with the shared authority.
- Automatic repair after rollback itself fails — the common result reports every uncertain path and stops; automatic repair is explicitly outside the plan.
- General repository transactions — the coordinator remains limited to concept publication intents and their declared artifacts.
