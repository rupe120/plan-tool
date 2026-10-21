> **Withdrawn 2026-08-19** — 2026-08-19 plan-level review rejected the premise: no demonstrated problem shows that a provenance advisory changes an operator decision.
> Preserved here for history; do not edit.

# Step 2 — Save qualified parallel remedy events and preserve replay and worktree safety

## Summary

Make the `--jobs N` completeness-apply path record immutable remedy events only after its serial replay tail determines the final canonical outcome. Update `plan_tool/cli/completeness_apply_parallel.py` to pass final replay evidence to the step 1 persistence contract, and update `plan_tool/cli/completeness_phases.py` to write those events against the selected saved audit. Preserve canonical replay writes and rollback behavior for modified, created, and deleted files, plus worktree reset and cleanup behavior. On green, each parallel result has one durable final disposition in the canonical sidecar, while discarded worker results and reverted edits cannot become causal remedies.

## Table of Contents

- [Summary](#summary) — Reviewer overview of the parallel event and safety work.
- [Table of Contents](#table-of-contents) — Links to every section in this detail.
- [Why](#why) — Why worker-local results cannot be durable provenance.
- [Input](#input) — The step 1 event contract and current parallel replay flow.
- [Files (creates vs edits)](#files-creates-vs-edits) — In-scope code and test changes.
- [Implementation](#implementation) — Final-outcome recording, replay safety, and worktree rules.
- [Tests](#tests) — Focused coverage for event timing, replay, rollback, and cleanup.
- [Acceptance criteria](#acceptance-criteria) — Observable conditions for a finished step.
- [References](#references) — Primary references for durable writes and pytest coverage.
- [Applicable guardrails](#applicable-guardrails) — Plan boundaries that keep this diagnostic-only.

## Why

`plan_tool/cli/completeness_apply_parallel.py:run_parallel_apply` lets workers edit disposable worktrees, then `replay_results` chooses what actually lands in the canonical tree. Persisting worker output would create evidence for an edit that may be discarded on conflict, fail the parse gate, or disappear during cleanup. This step makes canonical replay the only parallel producer of remedy history while keeping the existing file restoration and isolation guarantees intact.

## Input

- **Step 1 event writer:** Step 1 provides the immutable ordered annotation-history contract and its serialized update boundary. This step supplies the selected recommendation, final disposition, and one writer-attempt identity to that contract; it does not add another sidecar or serialization path.

- **Parallel finality boundary:** `plan_tool/cli/completeness_apply_parallel.py:replay_results` sorts worker results with `replay_sort_key`, detects conflicts with `_conflicts`, runs the `parse_plan` gate, and calls its `persist` callback only after each finding has a final disposition.

- **Command persistence bridge:** `plan_tool/cli/completeness_phases.py:_apply_walk_recs_parallel` owns the selected `saved_path`, selected saved review, and current `update_annotation` callback. Its existing `run_parallel_apply` call is the canonical-sidecar handoff.

- **Isolation lifecycle:** `plan_tool/cli/completeness_apply_parallel.py:WorktreePool.acquire` resets each reused worker tree, while `WorktreePool.__exit__` removes worktrees, branches, temporary directories, and stale worktree metadata before `run_parallel_apply` starts canonical replay.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `plan_tool/cli/completeness_apply_parallel.py` — carry final replay evidence through the persistence callback, assign stable writer-attempt identity at the final-outcome boundary, and retain replay, rollback, and worktree lifecycle behavior.
  - `plan_tool/cli/completeness_phases.py` — adapt `_apply_walk_recs_parallel`’s persistence callback to the step 1 writer contract without changing command filtering, exit behavior, or commit handling.
  - `tests/cli/test_completeness_apply_parallel.py` — cover canonical-only event recording, conflict reruns, file overwrite/delete replay, rollback, and real-git worktree reset and cleanup.
  - `tests/cli/test_completeness_cmd.py` — cover the `completeness-apply --jobs N` bridge writing final parallel events to the selected sidecar.

## Implementation

- **Foundational logic: record one event from each final canonical replay decision.** Extend the `persist` handoff between `plan_tool/cli/completeness_apply_parallel.py:replay_results` and `plan_tool/cli/completeness_phases.py:_apply_walk_recs_parallel` so the step 1 writer receives the final result, not only a mutable annotation status and note.

- **Keep workers free of durable provenance writes.** `apply_finding_in_tree` and `dispatch_parallel` must continue to operate only in isolated trees. Do not let a worker update the saved audit sidecar or mint an authoritative event before replay; its result can be stale, superseded, or reverted.

- **Use replay order as producer order.** Preserve `replay_sort_key` ordering and record each event from the serial tail after the result is decided. Give each final decision one writer-attempt identity that remains stable if the same persistence operation retries, allowing step 1 to deduplicate only that retry while retaining later distinct attempts.

- **Record the canonical rerun, not its discarded worker predecessor.** When `_conflicts` causes `replay_results` to call `rerun_fn`, discard the isolated result as provenance. Record exactly the rerun’s final disposition and evidence, whether it applies, skips, or fails.

- **Require a landed canonical edit for a qualifying applied remedy.** Record final non-applied outcomes so the operator can see them, but do not present a worker-only result, an `APPLIED` result with no landed change, or a parse-gated rollback as a successfully applied remedy. Keep `annotation_status` and the command’s existing applied/failed counts compatible with their current meanings.

- **Preserve replay file semantics.** Keep `plan_tool/cli/completeness_apply_parallel.py:_write_change` able to overwrite existing canonical content and delete a target when `FileChange.post` is absent. Keep `_restore` able to restore pre-existing content, restore a deleted original file, and remove a file that was newly created before the parse gate rejected the replay.

- **Persist only after the parse gate.** A replayed change becomes event evidence only after `parse_plan` accepts the canonical plan. On rejection, `_restore` must run before the failed disposition is recorded, and the saved event must remain non-qualifying.

- **Keep worktree cleanup independent of sidecar writes.** Preserve `WorktreePool.acquire`’s hard reset and untracked-file cleanup before each worker receives a tree. Preserve `WorktreePool.__exit__` removal, branch deletion, base-directory cleanup, and `worktree prune`; no event write may depend on a worker worktree surviving after `run_parallel_apply` leaves the pool.

- **Leave command policy unchanged.** Keep `_resolve_apply_walk_targets` as the owner of `--jobs` admission, clean-tree checks, source filtering, and bare-plan behavior. Keep the existing run-log and telemetry calls as observability only; remedy-event persistence must not change return codes, stop reasons, gates, or automatic remediation.

## Tests

### Tests for this step

- `tests/cli/test_completeness_apply_parallel.py:TestReplayPersistCallback.test_final_canonical_replay_persists_one_event_with_a_stable_writer_attempt` — asserts one accepted canonical replay produces one persistence request, and retrying that request keeps the same writer-attempt identity.

- `tests/cli/test_completeness_apply_parallel.py:TestReplayResults.test_conflict_discards_worker_event_and_records_only_the_canonical_rerun` — asserts a stale worker result creates no event and the serial rerun’s final result is the only persisted evidence.

- `tests/cli/test_completeness_apply_parallel.py:TestReplayResults.test_parse_gate_rollback_records_a_nonqualifying_final_disposition` — asserts a parse-failed replay restores files before persistence and cannot record an applied remedy.

- `tests/cli/test_completeness_apply_parallel.py:TestReplayResults.test_canonical_replay_overwrites_existing_files_and_deletes_absent_posts` — asserts `_write_change` replaces existing content and deletes a file when the captured post-content is absent.

- `tests/cli/test_completeness_apply_parallel.py:TestReplayResults.test_parse_gate_restore_restores_original_files_and_deletes_new_files` — asserts `_restore` restores overwritten or deleted originals and removes replay-created files after a rejected plan.

- `tests/cli/test_completeness_apply_parallel.py:TestWorktreePoolRealGit.test_pool_reuse_resets_tracked_and_untracked_worker_changes` — asserts a reused slot returns to HEAD and has no worker-created untracked file.

- `tests/cli/test_completeness_apply_parallel.py:TestWorktreePoolRealGit.test_pool_exit_removes_worktrees_branches_and_temporary_base_directory` — asserts pool teardown leaves no parallel worktree, branch, or temporary directory.

- `tests/cli/test_completeness_apply_parallel.py:TestRunParallelApplyRealWorktrees.test_end_to_end_parallel_replay_persists_only_canonical_events_after_pool_cleanup` — drives isolated workers through replay and proves durable events belong to canonical results after cleanup.

- `tests/cli/test_completeness_cmd.py:TestCompletenessApplyParallel.test_parallel_apply_persists_final_remedy_events_to_the_selected_saved_audit` — drives `completeness-apply --jobs N` and asserts final applied, skipped, and failed dispositions reach the step 1 writer on the selected sidecar.

- `tests/cli/test_completeness_cmd.py:TestCompletenessApplyParallel.test_parallel_command_conflict_rerun_uses_the_final_event_evidence` — asserts the command-level bridge persists the rerun outcome rather than the stale worker outcome.

Every listed test must be green before this step is considered finished.

## Acceptance criteria

- A parallel apply records each final disposition through the step 1 annotation-history writer, never directly from a worker worktree.

- A successfully applied remedy event corresponds to a canonical replay that changed the tree and passed the parse gate.

- A conflict produces evidence only for the serial rerun’s final outcome, not for the discarded isolated result.

- Canonical replay overwrites changed files and deletes files whose captured post-content is absent.

- A rejected replay restores overwritten and deleted original files and removes replay-created files.

- Reusing a worktree resets tracked and untracked worker changes before the next apply.

- Pool teardown removes its worktrees, branches, temporary base directory, and stale worktree metadata.

- The tests listed in `## Tests` are green.

## References

- [Python 3.13 — os.replace](https://docs.python.org/3.13/library/os.html#os.replace) — Review the atomic replacement guarantee beneath the step 1 serialized sidecar writer.

- [pytest API Reference](https://docs.pytest.org/en/stable/reference/reference.html) — Use fixtures, monkeypatching, and integration markers for replay and real-git lifecycle coverage.

## Applicable guardrails

- **The plan’s “## Plan intent”, advisory-only boundary** — record evidence for later diagnosis only; do not add advisory rendering or change convergence behavior.

- **The plan’s “## Step intent”, isolation and cleanup boundary** — preserve canonical replay, rollback, worktree reset, and cleanup while adding the parallel producer.

- **The plan’s “## Out of scope”, command-behavior boundary** — do not change exit codes, stop reasons, gates, plan files, or automatic remediation.

- **The plan’s “## Out of scope”, persistence boundary** — use saved audit annotations through the step 1 writer and do not introduce a second provenance store.
