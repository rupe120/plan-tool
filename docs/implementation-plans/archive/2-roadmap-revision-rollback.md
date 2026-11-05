> **Auto-archived**: this plan was swept on 2026-11-05 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

---
format_version: 1
title: Roadmap Revision Rollback
intent: When a roadmap stage run fails or is cut short, the operator can return the
  roadmap to exactly the state it had before that revision started, using one explicit,
  confirmed command, and then re-run the revision from a clean start. A revision that
  completed is never rolled back.
status: completed
priority: medium
risk_profile: standard
risk_profile_rationale: Risk declaration uses standard because --yes does not accept
  model risk proposals.
test_command: uv run pytest tests/ -q -n auto
enforce_step_tests: true
source_seed: plan-seeds/roadmap-revision-rollback.md
steps:
- id: 1
  title: Add a roadmap revision checkpoint file that records, for every file a stage
    run can write (the four stage artifacts, their baselines, seed-state.json, and
    source.json), its pre-run bytes and the bytes the run last wrote, with absence
    recorded explicitly; discarding it deletes only the checkpoint file
  intent: Gives the stage run and the restore route one shared, tested record of what
    the roadmap looked like before a revision and what the run itself last wrote.
  creates:
  - plan_tool/roadmap_revision_checkpoint.py
  - tests/test_roadmap_revision_checkpoint.py
  complexity: medium
  change_type: feature
  detail: docs/implementation-plans/plan-details/roadmap-revision-rollback/01-roadmap-revision-checkpoint-file-that.md
  status: done
- id: 2
  title: Move run_roadmap's confirmed brief rebind write of source.json to after recover_roadmap_publication
    (today it runs before), so recover_roadmap_publication always runs first; then
    take the checkpoint right before its first write, that rebind write included,
    keep an earlier failed run's checkpoint and its pre-run bytes, verify each tracked
    file's current bytes against the checkpoint's last-tracked value before writing
    it and refuse the run on a mismatch, update the last-written bytes after each
    stage publish and each source.json write, and delete the checkpoint only when
    the run completes (including a no-change run); a run refused before any write
    creates none, and existing stage publishes and journal cleanup stay unchanged
  intent: Makes a checkpoint that still exists mean exactly that a run did not complete,
    makes it hold the roadmap state from before the first of any consecutive failed
    runs, keeps a later run in the same checkpoint's lineage from silently building
    its own next write on top of a change the checkpoint never tracked, and closes
    the one case today -- the confirmed brief rebind -- where recovery does not yet
    run before the run's first tracked write.
  files:
  - plan_tool/roadmap.py
  - tests/test_roadmap.py
  complexity: high
  change_type: feature
  depends_on:
  - 1
  depends_on_notes:
    1: the checkpoint record, its path, and its write/update/discard operations
  detail: docs/implementation-plans/plan-details/roadmap-revision-rollback/02-move-run-roadmap-confirmed-brief-rebind.md
  status: done
- id: 3
  title: 'Add the revision restore runner: under the writer lock, run recover_roadmap_publication
    first, then refuse and change nothing when there is no checkpoint, the roadmap
    is enrolled, or the files differ from both the last-written and the pre-run bytes;
    otherwise publish the pre-run bytes as one journaled generation through the unchanged
    publish_roadmap_generation (overwriting changed inventory files and deleting ones
    that did not exist before the run) and then delete the checkpoint, or just delete
    it when the files already match the pre-run bytes'
  intent: Lets an operator return the roadmap to its pre-revision bytes, and refuses
    whenever doing so would discard a later hand edit, another writer's change, or
    enrollment.
  creates:
  - plan_tool/roadmap_revision_rollback.py
  - tests/test_roadmap_revision_rollback.py
  complexity: high
  change_type: feature
  depends_on:
  - 1
  - 2
  depends_on_notes:
    1: the checkpoint loader and discard operation the matrix reads and clears
    2: real stage runs that leave a checkpoint after an invalid, exhausted, interrupted,
      or crashed run, for the end-to-end restore-then-re-run cases
  detail: docs/implementation-plans/plan-details/roadmap-revision-rollback/03-revision-restore-runner-under-writer.md
  status: done
- id: 4
  title: Add the paired restore and confirm options to plan-tool roadmap, exclusive
    with every other roadmap option (-y is not confirmation), map the runner's outcomes
    to exit codes, and regenerate docs/cli/roadmap.md
  intent: Gives operators one explicit, confirmed command to trigger the restore,
    following the existing --reopen-feedback / --confirm-feedback-reopen shape.
  files:
  - plan_tool/cli/roadmap_cmd.py
  - tests/cli/test_roadmap_cmd.py
  - docs/cli/roadmap.md
  allowed_mentions:
  - docs/how-to/roadmap.md
  complexity: medium
  change_type: feature
  depends_on:
  - 3
  depends_on_notes:
    3: the restore runner and its outcome/refusal result the CLI dispatches to and
      renders
  detail: docs/implementation-plans/plan-details/roadmap-revision-rollback/04-paired-restore-confirm-options-plan.md
  status: done
- id: 5
  title: Name the restore command, when a checkpoint exists, at all four of cmd_roadmap's
    disconnected outcome paths -- the RoadmapResult-based invalid/exhausted branch
    that already reaches _print_invalid/_print_exhausted, the except (OSError, RoadmapEnvironmentalError)
    branch that today only calls error() and returns _RC_INCOMPLETE, the except (RoadmapError,
    RoadmapArtifactError, RoadmapWriterGuardError) branch that today only calls error()
    and returns _RC_USAGE, and the except KeyboardInterrupt branch that today only
    prints "interrupted" -- and never after a completed run
  intent: Tells the operator of a run that did not complete that a restore is available
    and exactly how to invoke it, at every path a run can end without completing,
    not only the two that already produce a RoadmapResult.
  files:
  - plan_tool/cli/roadmap_cmd.py
  - tests/cli/test_roadmap_cmd.py
  complexity: low
  change_type: feature
  depends_on:
  - 2
  - 4
  depends_on_notes:
    2: the checkpoint that exists exactly when a run did not complete
    4: the restore and confirm option names the message must print
  detail: docs/implementation-plans/plan-details/roadmap-revision-rollback/05-name-restore-command-when-checkpoint.md
  status: done
- id: 6
  title: 'Document the checkpoint file and the restore route and its refusal matrix
    for operators, stating plainly that this checkpoint is unrelated to plan-tool
    checkpoint list/clear''s create/detail authoring cache, and remove BACKLOG.md
    #394 once the route ships and its tests pass'
  intent: Makes the restore route discoverable from the operator docs, keeps an operator
    from conflating this checkpoint with the unrelated plan-tool checkpoint list/clear
    subcommand family, and closes the backlog entry it discharges.
  files:
  - ROADMAP_FORMAT.md
  - docs/how-to/roadmap.md
  - RUNBOOK.md
  - CAPABILITIES.md
  - docs/ARCHITECTURE.md
  - BACKLOG.md
  allowed_mentions:
  - docs/cli/roadmap.md
  complexity: medium
  change_type: non-code
  depends_on:
  - 2
  - 3
  - 4
  - 5
  depends_on_notes:
    2: the checkpoint lifecycle ROADMAP_FORMAT.md describes
    3: the restore matrix and module the docs and ARCHITECTURE.md name
    4: the shipped option names the operator docs cite
    5: the closing-message pointer the how-to and runbook describe
  detail: docs/implementation-plans/plan-details/roadmap-revision-rollback/06-document-checkpoint-file-restore-route.md
  status: done
---
# Roadmap Revision Rollback

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

**Keeping the checkpoint's tracked bytes true.** Both the pre-run snapshot and
the ongoing last-written bytes are trusted only after
`recover_roadmap_publication` has resolved any dangling journal — a run takes
its pre-run snapshot only after that call, not before, so a journal left by an
earlier crash is settled to its fully-committed state first. Before a run
continuing an existing checkpoint's lineage writes to a file the checkpoint
already tracks, it first confirms that file's current bytes (read after that
same recovery call) still equal the checkpoint's own last-tracked value for
it; a mismatch means something outside this tool's own generation history
touched the file since the checkpoint was created, and the run refuses rather
than silently building its own next write on top of that untracked change.
This ordering is not automatic today: `_run_roadmap`'s confirmed brief rebind
writes `source.json` (`_write_brief_source`, in the `confirm_brief_rebind`
preflight branch) before `recover_roadmap_publication` runs at all, so step 2
also moves that write to after the recovery call -- making it the run's first
tracked write, like every other case, rather than an exception to the
recovery-first rule.

**The checkpoint's contents.** This is a distinct artifact from `plan-tool
checkpoint list`/`clear`'s create/detail authoring cache
(`.plan-tool/checkpoints/<plan-slug>/`); the two share a name but no
subcommand family, location, or lifecycle.
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
- No change to how a pending decision is accepted; that gap is addressed by
  separate work (see `docs/history/backlog-decisions.md`, "No supported route
  can accept a pending roadmap decision").

## References

- `BACKLOG.md`'s former #394, "Roll back a roadmap revision that fails or is
  cut short" (shipped and removed 2026-09-18; the number has since been
  reused for an unrelated entry): the source entry and its scope contract.
- `plan_tool/roadmap.py:run_roadmap`, `_run_roadmap`, the stage-loop
  `publish_stage_artifact` call: the run, its lock, and its per-stage
  commits. `_write_brief_source`'s call in the `confirm_brief_rebind` branch
  (around line 2647) is the confirmed-rebind write step 2 moves to after
  `recover_roadmap_publication` (around line 2687).
- `plan_tool/roadmap_revision_publish.py:publish_roadmap_generation`,
  `recover_roadmap_publication`: the journal restore reuses, and the
  recover-first step every writer runs. Its `states == new or states == old`
  branch (lines 388-393) is what silently completes an already-fully-committed
  generation without raising -- the source of the accepted stale-checkpoint
  residual named in Risks, for any tracked file a dangling journal covers
  that this plan does not itself reconcile.
- `plan_tool/cli/roadmap_cmd.py`: `--reopen-feedback` /
  `--confirm-feedback-reopen`, the CLI shape to follow; `cmd_roadmap`'s four
  disconnected non-completion paths (the `RoadmapResult`-based
  invalid/exhausted branch, the `except (OSError, RoadmapEnvironmentalError)`
  branch, the `except (RoadmapError, RoadmapArtifactError,
  RoadmapWriterGuardError)` branch, and the `except KeyboardInterrupt` branch)
  step 5 must all reach.
- `RUNBOOK.md`'s command-families table and `plan_tool/cli/checkpoints.py`:
  the existing `plan-tool checkpoint list`/`clear` subcommand family this
  plan's checkpoint artifact shares a name with but no other relation to.
- `docs/history/backlog-decisions.md`: the withdrawn root-enrollment
  rollback, and why this seed does not touch enrollment.

## Steps

See the `steps:` block in the frontmatter.

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
- Taking the pre-run snapshot before resolving a dangling journal left by an
  earlier crash would capture transient, never-stable bytes instead of the
  roadmap's actual last-committed state. `recover_roadmap_publication` must
  run first, both when a run takes its snapshot and whenever restore or a
  continuing run reads current bytes to compare against the checkpoint. At
  HEAD this ordering does not hold for the confirmed brief rebind: its
  `source.json` write runs before recovery, so step 2 moves it to after
  recovery rather than leaving it exempt from this risk.
- A run continuing an existing checkpoint's lineage that writes to a tracked
  file without first checking that file's current bytes against the
  checkpoint would silently fold an intervening hand edit into its own
  last-written record — restore would then treat that edit as if the run
  itself had produced it, and discard it along with everything else on
  restore. This is the failure mode the change check exists to prevent,
  reached from a direction the check itself doesn't cover; the write-time
  verification in step 2 is what closes it.
- A crash strictly between a tracked write committing and step 2's own
  checkpoint bookkeeping update for it would leave the checkpoint stale in a
  way its own write-time check cannot distinguish from an outside change --
  whether that write went through a `PendingGeneration` journal (a stage
  publish, or another roadmap writer sharing `recover_roadmap_publication`'s
  journal path) or a plain write (`source.json`). Step 2 closes the one case
  where a cheap, reliable signal already exists without reasoning about any
  other writer's state: when `admission` resolves to `"matched"`, current
  `source.json` bytes already reflect this tool's own settled write (a
  genuine divergence would have produced a `"refused-*"` admission instead),
  so the checkpoint's stale entry is reconciled to current bytes as part of
  capture-or-continue. Every other case -- `publish_stage_artifact`'s own
  three-member write, and any dangling journal left by a different roadmap
  writer that happens to touch a tracked file -- is a known, accepted
  residual rather than a case this plan closes: closing the former would
  require duplicating `_publication_members`'s internal derivation outside
  `roadmap_revision_publish.py`, and closing the latter would require
  reasoning about another writer's state, which the seed's own Deferred
  section (carried into this plan's own `## Deferred`) routes to a follow-up
  backlog item (`BACKLOG.md` #399) rather than in-plan scope. A run or
  restore call that hits either residual refuses as "changed since the
  failed run" -- the same outcome an unrelated hand edit already produces,
  resolved by hand or by starting a fresh revision, so the residual is a
  known limitation, not a correctness gap.
- `seed-state.json` is one of the ten tracked files, and `--refresh-seeds`,
  `--accept-seed`, and `--apply` are legitimate other writers of it, each
  dispatched straight from `cmd_roadmap` without going through `run_roadmap`.
  Running one of them between two runs of the same failed-revision lineage,
  or between a failed run and its restore, changes `seed-state.json` the same
  way an unrelated hand edit would; the existing change check and "anything
  else" refusal already catch this and refuse rather than silently
  overwriting the seed action's work, at the cost of discarding the
  failed-run restore/retry along with it, which the operator resolves by
  hand.

## Testing

- For each way a run can stop (an invalid stage, running out of attempts, an
  operator interrupt, a crash between stages, and a mid-run environmental
  failure such as a missing stage prompt template after an earlier stage
  already committed): set up a run that commits at least one stage and then
  stops. Restore it and assert every inventory file matches its pre-run bytes
  and that a re-run proceeds.
- After a mid-run environmental failure reaches `cmd_roadmap`'s
  `except (RoadmapError, RoadmapArtifactError, RoadmapWriterGuardError)`
  branch with a checkpoint already present, its printed message names the
  restore command, matching the other three non-completion paths.
- A confirmed brief rebind run takes its pre-run snapshot, `source.json`
  included, only after `recover_roadmap_publication` has run -- proving the
  rebind write was moved after recovery, not just that recovery runs before
  an ordinary stage write.
- Two failed runs in a row restore to the state before the first.
- A completed run, including a no-change run, leaves no checkpoint.
- Each row of the restore matrix gets its own test. That includes an
  interrupted restore that recovery rolls back and a retry then completes, and
  an interrupted restore that already landed.
- A restore after a hand edit, after another writer's change, or after
  enrollment refuses and changes nothing.
- A run that starts with a dangling journal left by an earlier crash resolves
  it (via `recover_roadmap_publication`) before taking or comparing against
  the checkpoint, both for the first run's pre-run snapshot and for a later
  run continuing the same lineage.
- A second run in the same checkpoint's lineage that is about to write a file
  hand-edited since the first run's failure refuses before writing it, rather
  than reading the hand-edited value, writing its own new value on top, and
  recording that as the checkpoint's last-tracked bytes.
- A run whose `admission` resolves to `"matched"` reconciles a stale
  `source.json` checkpoint entry to current on-disk bytes as part of
  capture-or-continue (proof that an earlier crashed attempt's write landed
  without its checkpoint bookkeeping), rather than leaving that entry stale
  until a later write or a restore call falsely refuses against it. A
  genuine divergence never reaches `"matched"`, so it still refuses through
  the ordinary path. A test also pins the accepted residual: a stage-publish
  crash between the commit and its checkpoint update still refuses, as a
  known, named limitation rather than a silently-absent one.
- Restore reports "already-restored" for its own prior, interrupted attempt
  with no special-casing: a completed prior restore lands every tracked
  file's bytes at `pre_run_bytes`, and the ordinary whole-vector comparison
  already matches that uniformly, so this falls out of the existing matrix
  rather than needing a dedicated mechanism.
- A dangling journal from any other roadmap writer that happens to touch a
  tracked file (a crashed root enrollment, review-seal promotion, or any
  other writer sharing `recover_roadmap_publication`'s journal) is a
  known, accepted residual: a continuing run or a direct restore refuses as
  "changed since the failed run" rather than raising or silently absorbing
  it, pinned by a test as a known limitation.
- Run the complete suite. Regenerate the CLI reference with
  `python -m plan_tool.cli_reference --write`.

## Acceptance criteria

- After a stage run that did not complete, one explicit, confirmed command
  restores every inventory file to its bytes from before the first
  consecutive failed run, and a re-run starts from there.
- A completed run is never rolled back: its checkpoint is gone.
- Restore refuses, changing nothing, when there is no checkpoint, when the
  roadmap is enrolled, or when anything changed since the failed run.
- A checkpoint's pre-run snapshot and every comparison against its
  last-tracked bytes happen only after `recover_roadmap_publication` has
  resolved any dangling journal left by an earlier crash.
- A run continuing an existing checkpoint's lineage refuses before writing a
  file whose current bytes no longer match the checkpoint's last-tracked
  value for it, instead of silently recording its own new write over an
  untracked change.
- A `"matched"`-admission run recognizes and reconciles a `source.json`
  checkpoint entry left stale by an earlier crashed attempt's write, rather
  than refusing or silently masking a genuine divergence; the equivalent gap
  for a stage-publish write, or for a dangling journal from another roadmap
  writer touching a tracked file, is an accepted, explicitly-named residual
  rather than a silently-missing case.
- Restore reports "already-restored", not "restored", when the checkpoint it
  is resolving is its own prior, interrupted attempt -- an emergent property
  of the ordinary whole-vector comparison, not a dedicated mechanism.
- An interrupted restore can be retried to completion without manual file
  edits.
- The restore route is documented for operators, distinguished from
  `plan-tool checkpoint list`/`clear`'s unrelated authoring cache, and this
  plan's own former `BACKLOG.md` entry (#394, shipped and removed
  2026-09-18) is removed once the route ships and its tests pass.

## Deferred

If `detail` finds that a file outside the stated inventory is written by a
stage run, add it to the inventory and name it in the plan. If covering it
requires reasoning about another writer's state, stop and file a separate
backlog item instead of widening restore.

This clause is invoked, not just carried forward: closing the checkpoint's
staleness window against a dangling journal from another roadmap writer
(`enroll_roadmap_root`, review-seal promotion, `enroll_stage_baselines`, or
any of the feedback/structural-revision publishers sharing
`recover_roadmap_publication`'s journal) requires exactly that kind of
cross-writer reasoning, and is filed as `BACKLOG.md` #399 rather than solved
in this plan. The accepted residual and its refusal behavior are covered in
Risks and Testing.
