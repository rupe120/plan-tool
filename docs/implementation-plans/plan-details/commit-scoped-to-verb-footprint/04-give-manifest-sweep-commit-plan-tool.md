# Step 4 — Give `manifest sweep --commit` its footprint from the sweep's own records

<!-- plan-tool:detail-format-version: 1 -->

## Summary

`cmd_sweep` in `plan_tool/cli/manifest.py` builds a footprint from records the sweep already returns and passes it to step 1's `commit_all` in place of `[ctx.repo_root]`. The footprint is the manifest path, each `ArchiveOutcome.plan_path` (a delete) and `archived_to` (an add), and both sides of every `plan_details_moved` and `duplicate_archive_results` pair. The whole-tree `working_tree_dirty` check before the commit becomes a check for dirt inside that footprint, so an unrelated dirty file no longer turns "sweep moved nothing" into a commit. The archive moves and manifest rewrites are unchanged; only what gets staged is narrowed. On green, a file dirtied outside the footprint stays dirty and uncommitted, and every footprint path is clean after the commit. The `--commit` help text and `docs/cli/sweep.md` match.

## Table of Contents

- [Why](#why) — what the whole-tree check and commit do today
- [Input](#input) — step 1's contract and the sweep's returned records
- [Files (creates vs edits)](#files-creates-vs-edits) — edits per file
- [Implementation](#implementation) — footprint, dirt check, help text
- [Tests](#tests) — cases in `tests/cli/test_manifest_cmds.py`
- [Acceptance criteria](#acceptance-criteria) — observable checks
- [References](#references) — docs and symbols to read
- [Applicable guardrails](#applicable-guardrails) — plan fences that bind this step
- [Deferred](#deferred) — work this step leaves out

## Why

After the sweep, the `--commit` block asks `working_tree_dirty(ctx.repo_root)` about the whole tree and then calls `commit_all(ctx.repo_root, subject)`, which stages everything. A file another process changes while the sweep runs is committed with the archive moves. The same whole-tree check also decides "nothing to commit", so an unrelated dirty file turns a sweep that moved nothing into a reported commit attempt. Step 1 makes an empty footprint a successful no-op, so the check now only decides which message the sweep prints. Step 1 gives `commit_all` a required `paths` footprint. This step supplies it for `manifest sweep`.

## Input

- **Step 1's `commit_all`.** The signature is `commit_all(repo_root, subject, paths)`. It stages with `git add -A -- <paths>`, skips gitignored entries and entries that exist nowhere, ignores entries outside `repo_root`, returns success without a commit when the footprint has nothing to commit, and returns a non-zero rc naming any footprint path still dirty afterwards. Read the landed code in `plan_tool/cli/gitcommit.py` and let it win over this description.
- **Records the sweep already returns** (grepped in `plan_tool/sweep.py` and `plan_tool/cli/manifest.py`):
  - `ArchiveOutcome` in `plan_tool/sweep.py` has `plan_path`, `archived_to` (None when the archive was skipped), and `plan_details_moved: list[tuple[Path, Path]]`. `SweepReport.archived` holds these.
  - `duplicate_archive_results` is the `list[tuple[Path, Path]]` that `_archive_duplicate_plans` returns, as `(source, destination)`.
  - `manifest_path` in `cmd_sweep` is `args.manifest or default_manifest_path(ctx.repo_root)`. Both `sweep_plans` and `_prompt_remove_missing` rewrite it.
- **Under `--dry-run`** the `--commit` gate already rejects the run, so these records always describe real moves.
- **Duplicates** live under non-selected candidate repo roots, so they can sit outside `ctx.repo_root`. Step 1's rule of ignoring out-of-repo entries covers that case; this step passes them without filtering.
- **The up-front clean-tree check stays.** It is the precondition, and this step does not touch it.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/cli/manifest.py`: add a small footprint helper beside `_sweep_commit_subject`; use it in the `--commit` block of `cmd_sweep`; rewrite the `--commit` help text in `register`.
  - `tests/cli/test_manifest_cmds.py`: add cases to the existing `sweep --commit` test class, which uses `_git_commit_all` and `tmp_repo`.
  - `docs/cli/sweep.md`: regenerate with `python -m plan_tool.cli_reference --write`; do not hand-edit.

## Implementation

- **Footprint helper.** One way: a function that takes `manifest_path`, the `SweepReport`, and `duplicate_archive_results` and returns a `list[Path]`. It adds the manifest path, then for each outcome in `report.archived` its `plan_path`, its `archived_to` when not None, and both sides of each `plan_details_moved` pair. It then adds both sides of each duplicate pair.
- **Why both sides of each move.** The source is a delete and the destination is an add. With both in the pathspec, `git add -A` stages them together and git reports a rename. A footprint with only the destination would leave the deletion unstaged.
- **Missing-entry deregistrations** need no extra paths. They only edit the manifest, which is already in the footprint.
- **Dirt check.** Replace the second `working_tree_dirty(ctx.repo_root)` call with a check for dirt inside the footprint.
  - Preferred: skip the check and call `commit_all` directly. Step 1 already returns success with no commit when the footprint is clean. Then print "nothing to commit" when nothing was committed.
  - If the caller needs to tell "committed" from "nothing to commit" apart, reuse the status logic step 1 added rather than writing a second `git status` parser. `unexpected_dirty_paths` in `plan_tool/cli/gitcommit.py` is the model for the status handling.
  - The existing message `--commit: nothing to commit (sweep moved nothing)` must still print for the no-change case.
- **Count for the subject.** Keep `n_archived` as computed today and keep `_sweep_commit_subject` unchanged.
- **Keep `working_tree_dirty` imported.** The first check before the sweep and the re-home gate at the top of the file still use it.
- **Help text.** Replace "stage all changes (git add -A)" with wording that says the commit holds only the archived plans, their plan-details moves, and the manifest edits. Keep the clean-tree, `--dry-run` / `--report-only`, off-by-default, and "only commits when the sweep moved something" statements.
- **Constraint.** Do not change the archive moves, the manifest rewrites, the commit subject, the clean-tree precondition, or the exit codes.

## Tests

All cases go in `tests/cli/test_manifest_cmds.py`, in the existing `sweep --commit` class.

- `test_commit_records_archived_plan_move_as_rename` — after `sweep --commit -y`, the commit shows the plan file as a rename into the archive directory (check with `git show --name-status -M`).
- `test_commit_includes_plan_details_move_as_rename` — a completed plan with a `plan-details/<slug>/` file has its details move committed as a rename.
- `test_commit_leaves_unrelated_dirty_file_uncommitted` — an unrelated file is dirtied during the sweep (for example by patching `sweep_plans` to write it, then calling the real one); it is absent from the commit and still dirty afterwards. This pins the narrowing that replaces `git add -A`.
- `test_commit_unrelated_dirty_file_alone_gives_nothing_to_commit` — nothing to sweep plus an unrelated file dirtied mid-run prints "nothing to commit", makes no commit, and exits 0. This is the case the whole-tree check got wrong.
- `test_commit_footprint_is_clean_after_commit` — after a successful sweep commit, `git status --porcelain` shows no entry for the manifest, the archived plan, or the details move.
- `test_commit_includes_manifest_edit_for_missing_entry_prune` — a missing-entry deregistration under `-y` lands in the commit through the manifest path alone.
- Existing cases in this class (`test_commit_archives_completed_plan_and_commits`, `test_commit_nothing_to_sweep_makes_no_commit`, `test_commit_rejects_dirty_tree`, `test_commit_rejects_dry_run`) must stay green unchanged.

### Tests for this step

The six new cases above are the roster. Every new and existing case in the `sweep --commit` class must be green before this step is finished. Verify the narrowing by mutation: temporarily restore `[ctx.repo_root]` as the footprint and confirm the unrelated-file cases go red.

## Acceptance criteria

- `sweep --commit` stages only the manifest, archived plans, plan-details moves, and duplicate moves; an unrelated dirty file is not in the commit.
- An archived plan and its plan-details file appear in the commit as renames.
- An unrelated dirty file with nothing swept gives "nothing to commit" and no new commit.
- Every footprint path is clean after the commit.
- `--commit` help text no longer says "git add -A"; `docs/cli/sweep.md` is regenerated and the CLI reference drift test (`tests/cli/test_cli_reference.py`) passes.
- Commit subjects, the clean-tree precondition, and exit codes are unchanged.
- `rg "commit_all\(" plan_tool/cli/manifest.py` shows a call with a footprint argument, and `rg "ctx.repo_root\]" plan_tool/cli/manifest.py` no longer matches the commit call.

## References

- BUG_BACKLOG.md, "`--commit` stages the whole working tree with `git add -A`…"
- `plan_tool/cli/gitcommit.py` (`commit_all`, `unexpected_dirty_paths`) — the landed step 1 contract and status handling.
- `plan_tool/sweep.py` (`ArchiveOutcome`, `SweepReport`) — the records the footprint is built from.
- `plan_tool/cli/manifest.py` (`cmd_sweep`, `_archive_duplicate_plans`, `_sweep_commit_subject`) — the commit block and its inputs.
- `docs/TRACKING.md` § "Scope contract and anti-creep".

## Applicable guardrails

- **The plan's "## Scope guardrails", first bullet:** this step changes only what the sweep stages and commits. The clean-tree precondition, commit subject, and which verbs accept `--commit` stay as they are, and so does the `--dry-run` / `--report-only` rejection.
- **The plan's "## Scope guardrails", footprint-bookkeeping bullet:** the footprint comes only from records the sweep already returns. Do not add tracking code to `plan_tool/sweep.py`, a hook, `--no-verify`, or an attribution trailer.
- **The plan's "## Scope guardrails", added-check bullet:** the only new check is that footprint paths are clean after the commit, which step 1 supplies. Do not add content-quality or exit-code changes here.
- **The plan's "## Out of scope":** a concurrent process editing a path the sweep wrote is not detected. That path is committed with the sweep's version of the change.

## Deferred

- Widening `--commit` to other verbs — BACKLOG #89, which lands after this plan.
- Changes to `commit_all` itself — owned by step 1; this step only calls it.
- Moving footprint tracking into `plan_tool/sweep.py` — the plan's fence forbids a footprint-tracking subsystem; the records it already returns are enough.
