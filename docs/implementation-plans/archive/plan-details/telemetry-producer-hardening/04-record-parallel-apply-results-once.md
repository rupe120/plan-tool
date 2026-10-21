> **Auto-archived**: this plan was swept on 2026-07-16 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 4 — Record parallel apply results once from the canonical replay

## Summary

Make `plan_tool/cli/completeness_apply_parallel.py:replay_results` the sole durable telemetry owner for `completeness-apply --jobs N`. Preserve `plan_tool/launcher.py:apply_finding` as the source of apply-result classification, but let isolated workers return that classification without writing authoritative decision rows. Thread the evaluated plan fingerprint and run binding from `plan_tool/cli/completeness_cmd.py:_apply_walk_recs_parallel` into the serial replay, recomputing the former for conflict reruns. Use the same deferred seam so interactive review records only kept edits. On green, each selected, landed result produces at most one `apply-verdict` event with canonical repository, plan, run, step, and finding keys.

## Table of Contents

- [Summary](#summary) — Reviewer-level overview of canonical parallel telemetry ownership.
- [Why](#why) — Why worker-side recording loses keys or creates duplicates.
- [Input](#input) — Upstream failure token and parallel result contracts used by this step.
- [Files (creates vs edits)](#files-creates-vs-edits) — Scoped source, test, and contract changes.
- [Implementation](#implementation) — Ownership, result selection, join keys, and failure rules.
- [Tests](#tests) — Focused launcher, replay, command, and documentation cases.
- [Acceptance criteria](#acceptance-criteria) — Observable at-most-once attempt and canonical-key requirements.
- [References](#references) — Primary worktree and concurrency documentation.
- [Deferred](#deferred) — Related work intentionally left outside this step.

## Why

`plan_tool/cli/completeness_apply_parallel.py:apply_finding_in_tree` calls `plan_tool/launcher.py:apply_finding` inside disposable worktrees, while `plan_tool/cli/completeness_apply_parallel.py:replay_results` may later discard that worker result and run the finding again against the canonical tree. Recording inside each call can put an event under a worker repository, omit the command’s canonical run binding, or count both a stale worker response and its conflict rerun. The decision log must describe the result selected by canonical replay, not every speculative isolated attempt, while retaining the serial path’s existing telemetry behavior.

## Input

- **Step 3 output** — step 3 gives unusable primary and auto-fix follow-up backend responses a distinct apply-verdict value while preserving host disposition. This step carries that classification and restoration safety through deferred ownership rather than redefining it.
- **Launcher result** — `plan_tool/launcher.py:ApplyFindingResult` supplies the resolved step, exit code, parsed verdict, summary, and pre-edit snapshot. Keep `plan_tool/launcher.py:parse_apply_verdict` as the only parser for successful response tokens.
- **Parallel result** — `plan_tool/cli/completeness_apply_parallel.py:FindingApplyResult` carries one finding’s worker or serial-rerun outcome into `plan_tool/cli/completeness_apply_parallel.py:replay_results`.
- **Finding join key** — the `anchor` field on `plan_tool/review.py:Recommendation` is optional. Canonical recording must keep the existing empty-string behavior when no anchor is present.
- **Canonical snapshot** — `plan_tool/review_persistence.py:compute_plan_fingerprint`, already used by the serial convergence loop in `plan_tool/cli/completeness_cmd.py:_run_iterate_convergence_loop`, provides the plan fingerprint to compute once before parallel dispatch.
- **Run binding** — `plan_tool/run_log.py:RunLogWriter` provides `telemetry_run_id_scope`, which binds the active telemetry run id only for the calling context. Canonical replay must run inside that scope; worker threads must not own the durable event.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `plan_tool/launcher.py` — let deferred callers suppress durable recording while still receiving the launcher’s apply classification and restoration-safety metadata; keep authoritative non-interactive serial callers recording by default.
  - `plan_tool/cli/completeness_apply_parallel.py` — carry the recordable launcher outcome through `FindingApplyResult` and make at most one recording attempt when `replay_results` accepts the canonical result.
  - `plan_tool/cli/completeness_cmd.py` — compute one canonical pre-dispatch plan fingerprint and bind the parallel command’s run id around dispatch and replay.
  - `plan_tool/cli/review_actions.py` — defer the interactive serial verdict and record it only after the edit is kept.
  - `tests/test_launcher.py` — prove deferred/suppressed recording returns the same apply result without writing an event.
  - `tests/cli/test_completeness_apply_parallel.py` — cover worker suppression, canonical keys, conflicts, failures, skips, ordering, and recorder errors.
  - `tests/cli/test_completeness_cmd.py` — cover command-level fingerprint and run-id forwarding through `--jobs N`.
  - `tests/cli/test_review_actions.py` — cover kept, rejected, and empty-diff interactive ownership.
  - `tests/test_data_contract.py` — guard the documented parallel ownership and at-most-once best-effort rules.
  - `DATA_CONTRACT.md` — update the Apply verdict section for serial recording versus canonical parallel replay.

## Implementation

The foundational logic is: **canonical replay records only the final selected recordable apply outcome**.

- **Keep classification in the launcher.** `plan_tool/launcher.py:apply_finding` must remain the source of normal parsed verdicts and step 3’s unusable-response classification. Do not inspect backend text again in `plan_tool/cli/completeness_apply_parallel.py`.

- **Add a deferred-recording seam.** A practical approach is an optional recording mode or outcome observer on `plan_tool/launcher.py:apply_finding` whose default preserves current serial behavior. `plan_tool/cli/completeness_apply_parallel.py:apply_finding_in_tree` should use that seam to capture the recordable verdict and resolved step without writing a durable event from an isolated tree.

- **Preserve authoritative serial callers.** Calls in `plan_tool/cli/completeness_cmd.py:_run_iterate_convergence_loop`, `plan_tool/create.py:create_plan`, and `plan_tool/detail.py:generate_detail` keep launcher recording by default because their accepted result is authoritative. Interactive `plan_tool/cli/review_actions.py:_dispatch_apply_finding` must opt into deferred recording: record the captured outcome only after the user keeps the edit, and emit nothing when the user rejects/restores it or when `APPLIED` has an empty diff. Step 5 owns the cross-caller regression sweep.

- **Distinguish an apply outcome from worker setup failure.** Extend `plan_tool/cli/completeness_apply_parallel.py:FindingApplyResult` with enough structured metadata to tell whether `plan_tool/launcher.py:apply_finding` reached a recordable outcome. A parse, worktree, or dispatch failure before the apply invocation has no apply verdict and must not be turned into `UNKNOWN` or the step 3 failure token.

- **Carry classification after safe restoration.** Use the step resolved by `plan_tool/launcher.py:apply_finding`, not only `Recommendation.step_id`. The deferred-recording observer must receive the resolved step and `INVOCATION-FAILED` classification plus restoration success before an invocation exception is re-raised. Only a fully restored failure may be caught by `apply_finding_in_tree` and packaged with no captured changes. Incomplete restoration remains a propagated batch-level abort. This applies equally to an isolated worker and a conflict rerun against the canonical tree, so replay never accepts or continues atop uncertain partial edits. Unrelated setup/dispatch exceptions still become metadata-free worker failures, and the original failure text and worker failure disposition remain unchanged.

- **Suppress every speculative write.** Both the initial worker call in `plan_tool/cli/completeness_apply_parallel.py:run_parallel_apply` and its canonical conflict `_rerun` call must defer launcher recording. Otherwise a conflict rerun would write once inside `apply_finding` and again when replay accepts the result.

- **Record in `replay_results`.** Put the durable recorder call beside the point where `plan_tool/cli/completeness_apply_parallel.py:replay_results` accepts a result for annotation and outcome accounting. Keep annotation persistence and telemetry as separate best-effort actions; a telemetry exception must not block file replay, parse restoration, annotation persistence, later findings, or the command return.

- **Use the selected conflict result.** When `_conflicts` is false, record the worker result once. When `_conflicts` is true, discard the stale worker result for telemetry and record only the fresh `_rerun` result. Never emit both.

- **Define every path explicitly.**
  - A pre-skipped finding in `plan_tool/cli/completeness_cmd.py:_apply_walk_recs_parallel` emits nothing because no apply ran.
  - A worker setup or pre-invocation parse failure emits nothing because there is no apply outcome.
  - A selected `APPLIED` response with a non-empty landed diff, or a selected `NOT-APPLICABLE`, `BLOCKED`, `BLOCKED-STRUCTURAL`, or `UNKNOWN` response, emits that verdict once.
  - A selected `APPLIED` response with an empty diff emits nothing because no edit landed; it follows the existing no-op disposition instead of resolving as acted-on.
  - A selected unusable backend response emits step 3’s failure verdict once.
  - A stale worker result replaced by a conflict rerun emits nothing; the selected rerun emits once if it reached a recordable outcome.
  - A canonical parse-gate restoration emits no apply-verdict event: the selected edit was rejected and restored, so recording its parsed `APPLIED` token would falsely resolve inline as `acted-on`. The saved annotation remains the failure record. No new replay-disposition token is introduced.

- **Use canonical join keys.** The recorder in `plan_tool/cli/completeness_apply_parallel.py:replay_results` must receive the canonical `repo_root`, `plan_name`, selected resolved step id, the finding's `anchor`, and one caller-supplied plan fingerprint. Do not derive any of these from an isolated worktree.

- **Fingerprint the state actually evaluated.** In `plan_tool/cli/completeness_cmd.py:_apply_walk_recs_parallel`, compute the canonical fingerprint once before `run_parallel_apply` and attach it to non-conflicting worker results, which evaluated that pre-dispatch state. Before a canonical conflict rerun, recompute the fingerprint from the now-current plan and attach that value only to the fresh result. Guard each caller-side computation separately and fall back to `""`; the recorder’s own best-effort behavior does not cover argument computation.

- **Bind the command run.** Run parallel dispatch and replay inside the `telemetry_run_id_scope` context manager on `plan_tool/run_log.py:RunLogWriter` in `plan_tool/cli/completeness_cmd.py:_apply_walk_recs_parallel`. The durable recorder executes on the canonical serial tail and therefore reads the command’s real run id. Reset the scope before `run_end` completes so it cannot leak into a later command.

- **Keep replay behavior unchanged.** Preserve `plan_tool/cli/completeness_apply_parallel.py:replay_sort_key`, worktree isolation, conflict detection, parse restoration, incremental annotation persistence, and `ReplayOutcome` counting. This step changes telemetry ownership, not replay order or apply disposition semantics.

- **State the guarantee truthfully.** Canonical replay makes one best-effort recording attempt for each accepted recordable result and never attempts more than one; a swallowed append failure can still leave zero rows. Describe this as at-most-once persistence, not guaranteed exactly-once delivery.

- **Update the contract without a schema change.** `DATA_CONTRACT.md:Apply verdict` should state that serial applies record at the launcher boundary, while `completeness-apply --jobs N` defers worker recording and emits from canonical replay. Document the no-event paths (including parse restoration), conflict replacement rule, canonical join keys, at-most-once best-effort guarantee, exception-metadata transport, and step 3 failure token. The persisted fields do not change, so this step does not require a telemetry schema bump.

## Tests

- `test_apply_finding_can_defer_apply_verdict_recording` — `tests/test_launcher.py` proves the parallel-facing mode returns the normal structured result but writes no decision event.
- `test_apply_finding_deferred_failure_keeps_classification` — `tests/test_launcher.py` proves step 3’s unusable-response classification remains available when durable recording is deferred.
- `test_worker_apply_does_not_write_authoritative_telemetry` — `tests/cli/test_completeness_apply_parallel.py` proves an isolated `apply_finding_in_tree` call captures metadata without writing a decision row.
- `test_replay_records_clean_result_once_in_canonical_repo` — `tests/cli/test_completeness_apply_parallel.py` proves a clean worker result produces one canonical event.
- `test_replay_records_not_applicable_once_without_file_changes` — `tests/cli/test_completeness_apply_parallel.py` proves an intentional no-edit apply still records its selected verdict once.
- `test_replay_records_selected_invocation_failure_once` — `tests/cli/test_completeness_apply_parallel.py` proves a recordable failed backend result emits the step 3 token once.
- `test_replay_does_not_record_pre_invocation_worker_failure` — `tests/cli/test_completeness_apply_parallel.py` proves setup or parse errors do not become fake apply verdicts.
- `test_conflict_records_only_fresh_serial_rerun` — `tests/cli/test_completeness_apply_parallel.py` proves the stale worker verdict is discarded and the selected rerun verdict appears once.
- `test_conflict_rerun_failure_records_once` — `tests/cli/test_completeness_apply_parallel.py` proves a selected unusable rerun response produces one failure event without retaining the stale worker event.
- `test_parse_gate_restore_records_no_acted_on_verdict` — `tests/cli/test_completeness_apply_parallel.py` proves a rejected/restored edit emits no `APPLIED` row and cannot be falsely counted as acted on.
- `test_applied_empty_diff_records_no_acted_on_verdict` — proves an `APPLIED` response without landed changes follows the no-event no-op rule.
- `test_raised_invocation_transports_failure_metadata_to_replay` — proves the observer captures the resolved step and failure token before re-raise and the worker result preserves them for canonical replay.
- `test_raised_invocation_result_contains_no_partial_changes` — proves an invoker that edits before raising is restored by the launcher and packaged without replayable changes.
- `test_conflict_rerun_raised_invocation_records_selected_failure_attempt` — proves the stale worker result is discarded, partial canonical edits are restored, replay proceeds from the pre-rerun state, and the selected rerun's captured failure metadata is the only recording attempt.
- `test_replay_telemetry_failure_is_best_effort` — `tests/cli/test_completeness_apply_parallel.py` proves a raising recorder does not change canonical files, annotations, replay order, or `ReplayOutcome`.
- `test_parallel_replay_threads_anchor_resolved_step_and_plan_fingerprint` — `tests/cli/test_completeness_apply_parallel.py` proves each event carries the selected result’s canonical join keys.
- `test_parallel_command_hoists_pre_dispatch_fingerprint_for_worker_results` — `tests/cli/test_completeness_cmd.py` proves the helper runs once for non-conflicting worker results and those events share the evaluated pre-dispatch value.
- `test_conflict_rerun_recomputes_plan_fingerprint` — proves the fresh rerun event joins to the post-earlier-replay plan state rather than the stale pre-dispatch fingerprint.
- `test_interactive_rejected_edit_records_no_applied_verdict` — proves review action defers recording and rejection/restoration leaves no misleading acted-on event.
- `test_interactive_kept_edit_records_once` — proves the kept interactive outcome is recorded once with the captured launcher classification.
- `test_parallel_command_binds_replay_events_to_run_logger` — `tests/cli/test_completeness_cmd.py` records through the real consumer, reads the decision log back, and proves its event run id matches the parallel command’s `RunLogWriter.run_id`.
- `test_parallel_command_run_scope_does_not_leak` — `tests/cli/test_completeness_cmd.py` proves a later event outside the command does not inherit the completed parallel run id.
- `test_apply_verdict_parallel_ownership_documented` — `tests/test_data_contract.py` proves `DATA_CONTRACT.md:Apply verdict` names canonical replay, conflict replacement, and worker suppression.

### Test-creation order (feature step)

Add the launcher deferral tests with the launcher seam, then add lower-level worker/replay tests with the structured result changes. Add command-level fingerprint and run-binding tests when wiring `plan_tool/cli/completeness_cmd.py:_apply_walk_recs_parallel`, and finish with the contract drift guard. Every new test must be green before this step is considered finished.

## Acceptance criteria

- A normal serial `plan_tool/launcher.py:apply_finding` call still records one apply-verdict event by default.
- An isolated parallel worker returns a recordable outcome without writing an authoritative event from its worktree.
- `plan_tool/cli/completeness_apply_parallel.py:replay_results` makes at most one best-effort recording attempt for each accepted recordable result and none for pre-invocation or parse-restoration failures.
- A replay conflict records only the fresh canonical rerun result; the stale worker result produces no event.
- A pre-skipped or already-answered finding produces no apply-verdict event.
- Every parallel event is written under the canonical repository and carries the canonical plan slug, command run id, the fingerprint of the plan state its selected apply evaluated, resolved step id, and finding anchor.
- Step 3’s unusable-response verdict and resolved-step metadata survive returned and raised worker failures and are attempted once when that result is selected; raised invocations contribute no partial file changes because the tracked snapshot is restored before propagation.
- Interactive review records a kept result once and emits nothing for rejected/restored or `APPLIED`-empty-diff outcomes.
- A recorder or plan-fingerprint computation failure does not change replayed files, saved annotations, remaining findings, or command return behavior.
- `plan_tool/cli/completeness_apply_parallel.py:replay_sort_key`, conflict handling, parse restoration, and `ReplayOutcome` counts retain their existing behavior.
- The focused tests in `tests/test_launcher.py`, `tests/cli/test_completeness_apply_parallel.py`, `tests/cli/test_completeness_cmd.py`, and `tests/test_data_contract.py` pass.
- `DATA_CONTRACT.md:Apply verdict` documents serial/parallel ownership, at-most-once best-effort persistence, parse-restoration suppression, and raised-exception metadata transport without a telemetry schema bump. This is the declared `DATA_CONTRACT.md` deliverable for step 4.

## References

- [Git git-worktree Documentation](https://git-scm.com/docs/git-worktree) — Read for the lifetime and isolation rules that make worker-local state disposable.
- [Python concurrent.futures — Launching parallel tasks](https://docs.python.org/3/library/concurrent.futures.html) — Read for worker result, exception, and completion-order behavior before the deterministic serial replay.

## Deferred

- **General parallel-apply refactoring** — Keep `WorktreePool`, `dispatch_parallel`, conflict detection, and replay ordering intact unless a separate reconcile step identifies a behavior-preserving extraction.
- **Telemetry forwarding across all serial apply callers** — Step 5 owns direct coverage for create, detail, review, completeness, and escalation wrappers.
- **Historical telemetry repair** — Existing worker-local, missing, or duplicated rows are not backfilled.
- **New replay-disposition event vocabulary** — Parse restoration and annotation failure remain represented by existing annotations; rejected/restored edits emit no apply-verdict rather than a misleading inline outcome.
