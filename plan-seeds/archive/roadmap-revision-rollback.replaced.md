> **Replaced**: this file has been superseded by `docs/implementation-plans/2-roadmap-revision-rollback.md`.
> Preserved here for history; do not edit.

# Seed: roadmap revision rollback

Source: `BACKLOG.md` #394 — "Roll back a roadmap revision that fails or is cut
short." This seed inherits that entry's scope contract. The resulting plan's
final step removes #394 from `BACKLOG.md` once the rollback ships and its tests
pass.

## Outcome

When a roadmap stage run fails or is cut short, the operator can return the
roadmap to exactly the state it had before that revision started, using one
explicit, confirmed command, and then re-run the revision from a clean start.
A revision that completed is never rolled back.

## In scope

- A checkpoint for the roadmap stage run (`plan_tool/roadmap.py:run_roadmap`):
  the pre-run bytes of every file a stage run can write, taken before the
  run's first write.
- One explicit, confirmation-gated restore route on the roadmap CLI. The
  closing message of a run that did not complete names it.
- Operator documentation for the route (`ROADMAP_FORMAT.md`,
  `docs/how-to/roadmap.md`, `RUNBOOK.md`), plus the regenerated CLI reference.
- Focused tests for every case in the restore matrix below.

## Overview

A stage run holds the roadmap writer lock for the whole run
(`run_roadmap` → `_roadmap_writer_owner`) and refuses an enrolled roadmap
(`require_unenrolled_roadmap_writer`). Inside the run, each stage publishes on
its own (`publish_stage_artifact` in the stage loop). Each publish rewrites that
stage's baseline, and `publish_roadmap_generation` deletes its journal once the
stage commits. So a run that stops partway leaves earlier stages revised,
later stages untouched, and no record of the pre-run state.

## Problem statement

On Integration's `integration-aidlc-mvp` roadmap (2026-09-17), a `--from-stage 1` run
committed Domain, then ran out of attempts at Components after three parse
failures, and the retry was interrupted. The operator needed the roadmap back
as it was before that revision process started, and could only get there by
hand. The owner's rule (2026-09-18): roll back only revisions that fail or are
cut short, never one that completed.

## Architecture

Settled decisions (owner-confirmed 2026-09-18; do not re-open):

- **Explicit trigger.** Restore runs only when the operator invokes it. It
  uses the codebase's paired action/confirm CLI shape
  (`--reopen-feedback SELECTOR` / `--confirm-feedback-reopen`), and `-y` is
  not confirmation. Nothing restores automatically, so an operator who would
  rather resume from a partial revision still can.
- **The checkpoint decides eligibility, not the run log.** A run creates the
  checkpoint before its first write and discards it only when it completes,
  including a completed run that changed nothing. A checkpoint that still
  exists means the run did not complete: it was invalid, ran out of
  attempts, was interrupted, or crashed. That includes a crash after the last
  stage publish but before the run recorded completion; restore then returns
  to the pre-run state, and a re-run reproduces the revision.
- **An enrolled roadmap is refused.** Restore never touches enrollment or the
  immutable version namespace. An operator restores before enrolling.

**One checkpoint per roadmap, spanning consecutive failed runs.** The owner's
target is the state "before the revision process started". So a run that
starts while an earlier failed run's checkpoint exists keeps that checkpoint,
and its pre-run bytes stay those of the first failed run. The new run continues
tracking what it writes. A completed run or a finished restore discards the
checkpoint.

**The checkpoint's contents.**
- **Restore target:** the pre-run bytes of the four stage artifacts, their
  baselines, `seed-state.json`, and the recorded brief source.
- **Change check:** the bytes of each of those files as the run itself last
  wrote them, updated after every stage publish commits.
- **Excluded:** run logs are append-only telemetry and are never restored.
  Stage runs write no draft seeds (they record `draft_seed_count=0`;
  `--materialize` owns drafts).
- **Exact inventory:** derived by `detail` from the stage-run write path, not
  from this list.

**Restore case matrix.** Restore holds the writer lock and runs
`recover_roadmap_publication` first, like every other roadmap writer, so any
half-written stage publish resolves before restore reads anything. Then
exactly one case applies:

| Current state | Outcome |
| --- | --- |
| No checkpoint | Refuse: no revision to roll back. |
| Roadmap enrolled | Refuse, naming enrollment as the reason. |
| Files equal the run's last-tracked bytes | Restore to the pre-run bytes, then discard the checkpoint. |
| Files already equal the pre-run bytes | Discard the checkpoint and report it already restored (an interrupted restore that already landed). |
| Anything else | Refuse: the roadmap changed since the failed run. |

**The restore write reuses the existing publication journal.** It publishes
the pre-run bytes as one `PendingGeneration` through `publish_roadmap_generation`.
An interrupted restore is then rolled back to the failed-run state by the
existing unenrolled recovery path, and the operator can retry. No new
atomicity mechanism is added.

## Scope guardrails

- No automatic restore, and no restore offered on anything but an explicit
  command.
- No change to enrollment, candidates, review seals, promotion, or the
  `.roadmap-versions/` namespace.
- No new persisted state except the checkpoint: no receipt, evidence-store
  namespace, or content-addressed record.
- Eligibility never reads run logs.
- No change to `--revise-feedback`, `--materialize`, `--enroll-baselines`, or
  `--enroll-version`.
- No change to how a pending decision is accepted (BUG_BACKLOG "No supported
  route can accept a pending roadmap decision").

## Out of scope

- Rolling back a completed run.
- The enrolled candidate lifecycle and its interrupted journals (BUG_BACKLOG
  "Incomplete immutable lifecycle journals…").
- Un-enrolling a valid root (withdrawn 2026-09-18; see
  `docs/history/backlog-decisions.md`).
- Retry, resume, or re-run automation after a restore.

## Risks

- Restoring after another change would silently discard that work. The change
  check (last-tracked bytes) and the "anything else" refusal exist to prevent
  it, and each needs its own mutation test.
- Restoring artifacts without their baselines, seed state, or brief source
  would make the next run's source check refuse. Restore covers every file in
  the inventory or none of them.
- Keeping the first failed run's checkpoint across later failed runs is only
  right if each later run keeps updating the tracked bytes. If it doesn't, the
  change check refuses a legitimate restore.

## Allowed behavior changes

- A stage run writes, updates, and discards the checkpoint as described, and
  its closing message on a run that did not complete names the restore
  command.
- The new restore route exists. Nothing else changes.

## Allowed reorganization

None beyond what the checkpoint and restore need.

## Testing

- For each way a run can stop (an invalid stage, running out of attempts, an
  operator interrupt, and a crash between stages): set up a run that commits
  at least one stage and then stops. Restore it and assert every inventory
  file matches its pre-run bytes and that a re-run proceeds.
- Two failed runs in a row restore to the state before the first.
- A completed run, including a no-change run, leaves no checkpoint.
- Each row of the restore matrix gets its own test. That includes an
  interrupted restore that recovery rolls back and a retry then completes, and
  an interrupted restore that already landed.
- A restore after a hand edit, after another writer's change, or after
  enrollment refuses and changes nothing.
- Run the complete suite. Regenerate the CLI reference with
  `python -m plan_tool.cli_reference --write`.

## Acceptance criteria

- After a stage run that did not complete, one explicit, confirmed command
  restores every inventory file to its bytes from before the first
  consecutive failed run, and a re-run starts from there.
- A completed run is never rolled back: its checkpoint is gone.
- Restore refuses, changing nothing, when there is no checkpoint, when the
  roadmap is enrolled, or when anything changed since the failed run.
- An interrupted restore can be retried to completion without manual file
  edits.
- The restore route is documented for operators, and `BACKLOG.md` #394 is
  removed once the route ships and its tests pass.

## Deferred

If `detail` finds that a file outside the stated inventory is written by a
stage run, add it to the inventory and name it in the plan. If covering it
requires reasoning about another writer's state, stop and file a separate
backlog item instead of widening restore.

## References

- `BACKLOG.md` #394: the source entry and its scope contract.
- `plan_tool/roadmap.py:run_roadmap`, `_run_roadmap`, the stage-loop
  `publish_stage_artifact` call: the run, its lock, and its per-stage
  commits.
- `plan_tool/roadmap_revision_publish.py:publish_roadmap_generation`,
  `recover_roadmap_publication`: the journal restore reuses, and the
  recover-first step every writer runs.
- `plan_tool/cli/roadmap_cmd.py`: `--reopen-feedback` /
  `--confirm-feedback-reopen`, the CLI shape to follow.
- `docs/history/backlog-decisions.md`: the withdrawn root-enrollment
  rollback, and why this seed does not touch enrollment.
