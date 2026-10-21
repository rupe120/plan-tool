# Step 11 — Publish scope-out changes transactionally

## Summary

This step routes approved scope-out operations in `plan_tool/scope_out.py` through the all-or-recoverable concept publication authority. The transaction covers the narrowed plan, concept record, forward seed, detail renames, and detail archives as one prepared generation. The key design decision is to include the forward seed in the transaction instead of keeping the current seed-first partial-failure behavior. On green, both scope-out CLI surfaces report verified success, verified restoration, or exact rollback uncertainty without leaving an unreported mix of old and new artifacts.

## Table of Contents

- [Summary](#summary) — The transaction boundary and observable result.
- [Why](#why) — Why scope-out’s local rollback is no longer sufficient.
- [Input](#input) — The prepared bundle and publication contracts consumed here.
- [Files (creates vs edits)](#files-creates-vs-edits) — The six source and test files changed by this step.
- [Implementation](#implementation) — The authority handoff, result mapping, and required invariants.
- [Tests](#tests) — Unit and CLI cases for success, restoration, and uncertainty.
- [Acceptance criteria](#acceptance-criteria) — Checkable proof that scope-out publishes one recoverable generation.
- [References](#references) — Primary guidance for recoverable filesystem publication and failure injection.
- [Deferred](#deferred) — Related enforcement and documentation owned by later steps.

## Why

`plan_tool/scope_out.py:scope_out_step` currently writes the forward seed before `plan_tool/scope_out.py:apply_narrow` starts its separate detail, plan, and concept mutations. `apply_narrow` can undo caught failures through `_rollback`, but restoration is best effort, process interruption loses the in-memory journal, and neither CLI can name every artifact whose state is uncertain. Step 10 supplies one write-free scope-out bundle, so this step can replace that partial publication path with the common authority and make the forward seed part of the same recoverable generation.

## Input

- **Step 10 prepared bundle:** consume the complete write-free scope-out publication value produced by step 10. It supplies the source snapshots, narrowed plan, concept update or explicit absence, seed target and text, ordered detail renames, archive actions, and result metadata.
- **Step 3 publication authority:** use the all-or-recoverable publication entry point and its implemented success, conflict, invalid-state, restored-failure, and rollback-failed result vocabulary. Preserve its exact uncertain-path set instead of creating scope-out-specific rollback strings.
- **Lock ownership:** use the repository lock capability supplied through command context by step 3. The publishing core must not reacquire the non-reentrant repository mutation lock.
- **Existing scope-out policy:** preserve `plan_tool/scope_out.py:compute_narrow`, `_outcome_for_blockers`, `_prepare_concept_narrow_update`, and `_confirm_scope_out` as the authorities for graph safety, concept preparation, opt-in, and confirmation.
- **Existing public results:** retain the useful committed metadata in `plan_tool/scope_out.py:NarrowResult` and `ScopeOutResult`. Prepared paths must not appear as completed archive, migration, or seed results until publication succeeds.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `plan_tool/scope_out.py` — translate step 10’s prepared scope-out bundle into the shared publication request, remove direct live publication from the production scope-out path, and preserve publication outcomes in `ScopeOutResult`.
  - `plan_tool/cli/scope_out_cmd.py` — pass lock ownership into scope-out publication and map restored-failure and rollback-failed results to accurate messages and exit codes.
  - `plan_tool/cli/convergence_cmd.py` — replace the orphan-seed-specific `NarrowError` handling in `_actuate_scope_out` with the shared publication outcome mapping.
  - `tests/test_scope_out.py` — cover full-bundle commit, restoration, rollback uncertainty, compare-and-swap refusal, fingerprints, and direct-call lock behavior.
  - `tests/cli/test_scope_out_cmd.py` — cover operator messages and exit codes for transactional scope-out outcomes.
  - `tests/cli/test_convergence_cmd.py` — cover the same outcomes through `convergence --apply-scope-out` and remove assumptions that failed publication leaves a new seed behind.

## Implementation

The foundational logic is: **publish every scope-out artifact as one all-or-recoverable generation**.

- **Submit one complete request.** In the approved branch of `plan_tool/scope_out.py:scope_out_step`, translate step 10’s prepared bundle into the scope-out intent accepted by the step 3 authority. Include the plan, concept record when applicable, seed creation, detail moves, and archive moves in that single request.

- **Do not keep the seed outside the transaction.** Remove the production sequence that calls `Path.write_text` for the seed before invoking `plan_tool/scope_out.py:apply_narrow`. A restored failure must return the seed target to its original state, including removing it when it did not exist before the operation.

- **Use the shared coordinator, not a larger local journal.** Retire the production path through `plan_tool/scope_out.py:_rollback`, `_archive_file_strict`, `plan_tool/parser.py:write_plan`, and direct concept persistence for the approved carve. Extending those helpers with more best-effort restoration would still lack the durable recovery and exact uncertainty contract owned by step 3.

- **Preserve preparation and policy order.** Keep the flow in `plan_tool/scope_out.py:scope_out_step` as reparse, graph preview, blocker refusal, concept validation, opt-in, confirmation, write-free bundle preparation, then publication. Blocked, recommend-only, declined, and invalid-concept paths must still stop before staging or live mutation.

- **Keep stale checks effective at commit time.** Carry the source plan, concept sidecar, detail source, seed-target absence, and archive-target assumptions from the prepared bundle into the authority’s compare-and-swap inputs. A successful preview or confirmation is not permission to overwrite an artifact changed before commit.

- **Harden occupied archive targets at the feature boundary.** Convert any legacy fallback-target overwrite behavior characterized by step 10 into an explicit conflict before live mutation. Include that target in the typed compare-and-swap set and test both a pre-existing collision and a target created after staging.

- **Fingerprint the final generation.** Let the publication authority assign the concept record’s fingerprint from the exact staged narrowed-plan bytes and final ordered detail set. Scope-out must not recompute the fingerprint from partially published live files or call the low-level concept saver afterward.

- **Preserve legacy no-sidecar scope-out.** A plan with no applicable concept record still publishes its plan, seed, and detail changes through the same recoverable authority. Do not create an empty concept record merely to enter the transaction path.

- **Keep committed result fields accurate.** Build `plan_tool/scope_out.py:NarrowResult.archived`, `NarrowResult.migrated`, `ScopeOutResult.seed_path`, cursor, status, and renumbering from a verified successful publication. On any other publication result, do not claim that prepared destinations committed.

- **Preserve deliberate non-application outcomes.** `ScopeOutResult` must continue to distinguish `recommended`, `unsafe`, `empty-plan`, and `step-missing`. Carry the shared publication result for an approved carve rather than folding restored failure or rollback failure into one `NarrowError`.

- **Keep direct callers safe.** Adapt the checked-in direct `plan_tool/scope_out.py:apply_narrow` contract to the step 3 direct-call wrapper or an equivalent safe adapter. Direct library use must acquire the repository lock once and reach the same publication core; CLI callers must pass their existing lock ownership and never acquire it again.

- **Report restored failure plainly.** Update `plan_tool/cli/scope_out_cmd.py:cmd_scope_out` and `render_scope_out_result` so a verified restoration says the carve failed, every original artifact was restored, and retry is safe after correcting the reported cause. Return non-zero because the requested mutation did not complete.

- **Report rollback uncertainty exactly.** For a rollback-failed result, both CLI surfaces must print every path supplied by the authority and state that operator action is required. Do not say the plan was restored, do not suggest an automatic retry, and do not replace the path set with only the plan or seed directory.

- **Remove convergence’s orphan-seed inference.** Replace the seed-directory before/after glob logic in `plan_tool/cli/convergence_cmd.py:_actuate_scope_out`. The transaction result already identifies success, restoration, and uncertainty; guessing which seed a failed call created is no longer correct.

- **Keep command parity.** `plan_tool/cli/scope_out_cmd.py:render_scope_out_result` remains the shared rendering point where practical. `plan_tool/cli/convergence_cmd.py:_actuate_scope_out` may retain its diagnosis freshness checks and command-specific retry hint, but the two commands must describe the same publication result consistently.

- **Preserve zero-Claude behavior.** Transactional publication must not add an invoker seam or backend call to `plan_tool/scope_out.py:scope_out_step`. Seed rendering and narrowing remain deterministic.

## Tests

- `tests/test_scope_out.py:test_scope_out_transaction_commits_complete_generation` — a successful carve verifies the narrowed plan, final concept record, seed, detail archives, detail renames, fingerprint, and result fields together.
- `tests/test_scope_out.py:test_scope_out_transaction_supports_plan_without_concept_record` — legacy scope-out publishes plan, seed, and details without creating a concept sidecar.
- `tests/test_scope_out.py:test_scope_out_stages_before_first_live_change` — every artifact is prepared and accepted before any plan, seed, detail, archive, or concept target changes.
- `tests/test_scope_out.py:test_scope_out_compare_and_swap_conflict_writes_nothing` — a changed source or target after preparation prevents the whole commit.
- `tests/test_scope_out.py:test_scope_out_failure_restores_every_original_artifact` — injected failure at each publication operation restores prior bytes, prior paths, and prior absence, including the seed.
- `tests/test_scope_out.py:test_scope_out_restored_failure_does_not_report_committed_paths` — restored failure returns no false seed, archive, migration, or narrowed-plan result.
- `tests/test_scope_out.py:test_scope_out_rollback_failure_preserves_exact_uncertain_paths` — failed restoration returns the complete authority-provided path set without collapsing it.
- `tests/test_scope_out.py:test_scope_out_final_fingerprint_uses_published_plan_and_details` — the concept fingerprint identifies the verified staged generation, including renamed and archived details.
- `tests/test_scope_out.py:test_scope_out_recommendation_never_enters_publication` — blocked, declined, and recommend-only calls do not stage or publish.
- `tests/test_scope_out.py:test_scope_out_cli_lock_token_reaches_publication_core` — an already-held CLI lock is accepted without nested acquisition.
- `tests/test_scope_out.py:test_apply_narrow_direct_call_uses_locking_wrapper` — direct library use acquires one lock and reaches the same coordinator.
- `tests/cli/test_scope_out_cmd.py:test_restored_publication_failure_reports_safe_retry_and_exits_nonzero` — the scope-out command reports verified restoration without claiming success.
- `tests/cli/test_scope_out_cmd.py:test_rollback_failed_reports_all_uncertain_paths_and_exits_nonzero` — the scope-out command prints every uncertain path and requires operator action.
- `tests/cli/test_convergence_cmd.py:test_apply_scope_out_restored_failure_removes_new_seed_and_exits_nonzero` — convergence no longer leaves or reports an orphan seed after verified restoration.
- `tests/cli/test_convergence_cmd.py:test_apply_scope_out_rollback_failed_reports_exact_uncertain_paths` — convergence preserves the shared rollback-failed distinction and path set.
- `tests/cli/test_convergence_cmd.py:test_apply_scope_out_success_message_is_unchanged` — a verified successful single-step or range carve keeps the existing useful success details.
- `tests/cli/test_convergence_cmd.py:test_apply_scope_out_no_flag_and_refusal_paths_remain_read_only` — diagnosis-only, stale, missing-step, empty-plan, and non-TTY refusal paths remain non-mutating.

### Test-creation order (feature step)

1. Add the full-generation success and no-sidecar tests.
2. Add compare-and-swap and pre-publication no-write tests.
3. Add failure injection for each seed, archive, rename, plan, and concept operation, asserting complete verified restoration.
4. Add rollback-failed tests that compare the exact uncertain-path set.
5. Update the old orphan-seed assertions around `tests/test_scope_out.py:test_seed_persists_when_narrow_fails`, `tests/test_scope_out.py:test_concept_save_failure_rolls_back_narrow`, and `tests/cli/test_convergence_cmd.py:test_apply_scope_out_narrow_error_reports_orphan_seed_and_exits_nonzero` to the new transactional contract.
6. Add lock handoff and direct-call wrapper coverage.
7. Add both CLI surfaces’ message and exit-code tests.

Every new or updated test must be green before this step is considered finished.

## Acceptance criteria

- An approved scope-out submits one publication request containing the narrowed plan, concept update or absence, forward seed, detail renames, and detail archives.
- Successful single-step and region carves leave every artifact at the verified target generation and return committed `ScopeOutResult` and `NarrowResult` metadata.
- The published concept record fingerprints the exact final plan and ordered detail generation.
- A plan without a concept record can still complete a transactional scope-out without creating an empty sidecar.
- Validation, staging, lock, or compare-and-swap failure changes no live artifact.
- A recoverable publication failure restores and verifies the original plan, concept record, detail layout, archive layout, and seed absence or prior contents.
- A rollback-failed publication returns and displays the exact uncertain-path set from the shared authority.
- Neither CLI claims that a rollback-failed plan was restored or recommends an automatic retry.
- `plan_tool/cli/convergence_cmd.py:_actuate_scope_out` no longer finds failed-operation seeds by comparing directory globs.
- Blocked, recommend-only, declined, stale, and missing-step paths retain their existing no-write behavior.
- CLI publication uses the lock already held by command dispatch; direct library publication acquires the lock once through the shared wrapper.
- Production scope-out no longer directly saves the final concept sidecar.
- Scope-out remains deterministic and makes no backend call.
- All focused tests in `tests/test_scope_out.py`, `tests/cli/test_scope_out_cmd.py`, and `tests/cli/test_convergence_cmd.py` pass.

## References

- [POSIX.1-2024 Rationale — File-system atomicity and durability](https://pubs.opengroup.org/onlinepubs/9799919799/xrat/V4_xbd_chap01.html) — Use the filesystem update discussion to keep the guarantee all-or-recoverable rather than calling the multi-file operation atomic.
- [Python 3.13 os — Miscellaneous operating system interfaces](https://docs.python.org/3.13/library/os.html) — Consult the replacement, synchronization, and directory-operation behavior behind the shared publication result.
- [pytest — Monkeypatching functions and environments](https://docs.pytest.org/en/stable/how-to/monkeypatch.html) — Use controlled failure seams to test every publication and restoration boundary.

## Deferred

- Production single-writer enforcement — step 12 adds the repository-wide guard against direct final concept-sidecar writes.
- Operator recovery documentation — step 13 documents journals, restored failures, rollback-failed state, and uncertain-path handling.
- General repository transactions — the shared coordinator remains limited to the typed concept-publication artifact set delivered by step 3.
- Automatic repair of rollback-failed state — the authority reports uncertain paths and requires operator review; it does not guess which generation to keep.
