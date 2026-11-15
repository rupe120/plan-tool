# Step 5 — Commit only the step's footprint in `run --commit`

<!-- plan-tool:detail-format-version: 1 -->

## Summary

`_commit_green_step` in `plan_tool/cli/run_cmd.py` makes `paths` required and delegates staging and committing to step 1's `commit_all`. The single-step and `--all` sweep callers build a footprint from the plan file, the plan's `plan-details/<slug>/` directory, any archive outputs, and the paths that changed between a baseline taken just before `run_step` and the state after it. Rename origins come from a new additive read in `plan_tool/git_state.py`, so `changed_paths_or_none` and the test-authoring gate in `launcher.py` are untouched. A path that was dirty at the baseline stays out of the footprint and is named in a one-line warning. An unreadable git state at either snapshot makes that step's commit fail closed with a non-zero exit. The `--commit` help text and `docs/cli/run.md` are updated.

## Table of Contents

- [Why](#why) — what `git add -A` sweeps in during a backend call
- [Input](#input) — the step 1 contract and the git-state reads this step depends on
- [Files (creates vs edits)](#files-creates-vs-edits) — edits per file
- [Implementation](#implementation) — footprint rule, baseline, failure handling, warnings
- [Tests](#tests) — cases in `tests/cli/test_run_cmd.py` and `tests/test_git_state.py`
- [Acceptance criteria](#acceptance-criteria) — observable checks
- [References](#references) — docs and symbols to read
- [Applicable guardrails](#applicable-guardrails) — plan fences that bind this step
- [Deferred](#deferred) — work this step leaves out

## Why

`_commit_green_step` runs `git add -A` and `git commit` (its only scoped form is the `--accept` caller). A step's backend call can take minutes and writes arbitrary code, so anything else that changes the tree meanwhile is committed under the step's subject. The only record of what the backend wrote is the git delta that `launcher.py` already uses for the test-authoring gate. This step uses that delta as the footprint, as far as a path-name-only record allows, and says out loud what it cannot see.

## Input

- **Step 1's `commit_all`.** Signature `commit_all(repo_root, subject, paths)`: stages with `git add -A -- <paths>`, commits only those paths, skips gitignored and missing entries with a one-line warning, returns success with no commit when the footprint is clean, and fails with a non-zero rc naming any footprint path still dirty after the commit. At HEAD `commit_all` still has the two-argument form, so this step cannot start until step 1 lands. Read the landed code and let it win over this description.
- **`git_state.changed_paths_or_none(repo_root)`** returns the set of repo-relative changed paths, or `None` when git cannot be read. It parses `git status --porcelain -z --untracked-files=all` and discards the origin field of a rename or copy record. `launcher._git_changed_paths_or_none` is a thin alias over it; the test-authoring gate depends on its current return value, so that value must not change.
- **Current callers** of `_commit_green_step` in `plan_tool/cli/run_cmd.py`:
  - the `--accept` path in the accept handler (passes `paths=expected`: the plan file plus the lessons file);
  - the single-step path in `cmd_run` (gated by `commit_active and result.done`);
  - the `--all` sweep in `_cmd_run_sweep` (gated by `args.commit and result.done`).
- **Archive outputs.** `_archive_on_completion` returns an `ArchiveOutcome` (`plan_path`, `archived_to`, `plan_details_moved`) or `None`. The single-step caller currently discards the return value; the sweep caller does too. The manifest path comes from `args.manifest` or `default_manifest_path(ctx.repo_root)`.
- **Details directory.** `plan_reports_dir(plan_path).parent` in `plan_tool/review_persistence.py` is `<plan dir>/plan-details/<slug>/`, the same directory steps 2–3 use.
- **What the delta cannot show.** It holds path names only. A path already dirty at the baseline and edited again by the step looks identical to one the step never touched. Another process writing during the backend call is also indistinguishable from the step. These limits are the plan's accepted residual, filed in `BUG_BACKLOG.md` by step 6.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/cli/run_cmd.py`:
    - make `paths` required on `_commit_green_step` and delegate to `commit_all`;
    - add a small helper that takes the baseline and builds the footprint;
    - pass the footprint at the single-step and sweep call sites, capturing the `ArchiveOutcome`;
    - keep `paths=expected` at the `--accept` call site;
    - rewrite the `--commit` help text in `register`.
  - `plan_tool/git_state.py`: add the additive rename-aware read beside `changed_paths_or_none`.
  - `tests/cli/test_run_cmd.py`: new cases and updates to existing `_commit_green_step` cases.
  - `tests/test_git_state.py`: cases for the new read, plus a case pinning `changed_paths_or_none`'s unchanged return on a rename.
  - `docs/cli/run.md`: regenerate with `python -m plan_tool.cli_reference --write`; do not hand-edit.

## Implementation

**`_commit_green_step`.** Signature keeps `slug`, `step_id`, `step_title` and makes `paths` a required keyword with no default, so no caller can fall back to the whole tree. It calls `commit_all(repo_root, _green_commit_subject(...), paths)` and returns its `(rc, tail)`. Drop its own `git add` / `git commit` calls and its own ignored-path filter.

- The `--accept` caller keeps `paths=expected`. An ignored path there used to be skipped silently; it now gets `commit_all`'s shared one-line warning. That is an allowed change.
- Update the docstring to describe the footprint rule and drop the `git add -A` description.

**Baseline.** Take one snapshot with `changed_paths_or_none(ctx.repo_root)` just before each `run_step` call (once per swept step in the sweep, so earlier steps' leftovers are excluded). Keep the result, `None` included.

- Rejected alternative: refuse up front when the baseline is unreadable. The plan's contract is that the step's work stays in the tree and the commit fails closed, so the `None` is carried to commit time.
- Take the after-snapshot just before the commit, after any `_archive_on_completion` call, using the same function.

**Footprint rule.** The footprint is the union of:

- the plan file;
- the plan's `plan-details/<slug>/` directory;
- when `--archive` completed the plan, the `ArchiveOutcome` paths (`plan_path`, `archived_to`, both sides of each `plan_details_moved` pair) and the manifest path;
- the paths in `after − baseline`;
- for each rename record whose destination is in `after − baseline`, its origin path.

Both sides of a rename are footprint entries, so a staged `git mv a b` commits the deletion of `a` with `b`.

- **Rename origins.** Add one function in `plan_tool/git_state.py` (for example `renamed_origins_or_none`) returning a destination-to-origin mapping, or `None` when git cannot be read. It parses the same `git status --porcelain -z --untracked-files=all` output.
- **No second copy of the git call.** If the new function would repeat the subprocess and splitting code in `changed_paths_or_none`, move that shared part into one private helper that both use. `tests/test_duplication.py` fails on a new duplicate body, and `changed_paths_or_none` must return exactly what it returns today.
- **Unreadable rename read.** Treat `None` from this read like `None` from `changed_paths_or_none`: fail closed.

**Fail closed.** If the baseline or the after-snapshot is `None`:

- make no commit and never fall back to the whole tree;
- print an error naming the unreadable snapshot ("baseline" or "after the step");
- return a non-zero rc so the single-step run exits non-zero and the sweep halts;
- leave the step's work in the tree. The existing `_green_commit_failure_msg` already points the operator at `git status` and `git reset`; reuse it rather than writing a second recovery message.

**Dirty-before warning.** After a successful commit, re-read the git state (`changed_paths_or_none`). Any path that was in the baseline and is still dirty gets named in one warning line: left uncommitted because it was dirty before the step; the step may also have edited it.

- Claim no more than the record shows: do not say the step edited the path.
- This read only feeds a warning. If it returns `None`, skip the warning rather than failing a commit that already succeeded.

**Archive and commit order.** Keep the existing order: archive first, then commit. An archive move is staged inside the footprint, and a failed commit leaves that step's work for `git reset` recovery.

**Constraints.**

- `launcher.py` is not edited. Its test-authoring gate sees the same `changed_paths_or_none` as before.
- The clean-tree precondition, commit subject, `commit_active` / `args.commit` gating and per-step granularity are unchanged.
- Read optional namespace flags with `getattr(args, "...", default)`, matching the existing handler style, because tests build `argparse.Namespace` by hand.

**Help text and docs.** Replace "stage all changes (git add -A)" with wording that says the commit holds the plan file, its detail directory, any archive move, and the files the step changed since it started. Regenerate `docs/cli/run.md`.

## Tests

Tests live in `tests/cli/test_run_cmd.py` (cases that drive `_commit_green_step`, `cmd_run` and `_cmd_run_sweep` against a real tmp git repo via the existing `_init_git_repo` helper, with `run_step` stubbed to write files) and `tests/test_git_state.py`.

`tests/cli/test_run_cmd.py`:

- `test_file_dirtied_after_baseline_is_in_delta_and_committed_known_residual` — a file written during the step (the backend and another process look the same) is committed. Pins the known residual that step 6 files.
- `test_unrelated_file_outside_delta_is_excluded` — a file that is dirty but absent from `after − baseline` stays uncommitted.
- `test_file_dirty_before_step_is_not_committed` — a file dirty at the baseline and untouched afterward is left out of the commit.
- `test_file_dirty_before_and_after_is_left_uncommitted_and_named_in_warning` — the warning names the path and says it was dirty before the step and may also have been edited.
- `test_unreadable_baseline_makes_no_commit_and_exits_nonzero` — a `None` baseline leaves HEAD unchanged, exits non-zero, names the baseline, and keeps the step's files in the tree.
- `test_unreadable_after_snapshot_makes_no_commit_and_exits_nonzero` — same for the after-snapshot.
- `test_unreadable_git_state_never_falls_back_to_whole_tree` — an unrelated dirty file is not committed in either failure case.
- `test_staged_rename_in_step_commits_both_paths_and_leaves_both_clean` — a step that runs `git mv a b` commits the deletion of `a` with `b`.
- `test_archive_move_is_committed_with_the_step` — a completing step under `--archive` commits the archived plan and manifest; the tree is clean.
- `test_accept_ignored_path_warns_instead_of_silent_skip` — the `--accept` caller emits the shared warning for a gitignored path.
- `test_plan_file_is_clean_after_each_green_commit` — in single-step and sweep runs, `git status` shows no dirt on the plan file after each commit.
- `test_commit_green_step_requires_paths` — calling `_commit_green_step` without `paths` raises `TypeError`, so the whole-tree default cannot come back.

Existing `_commit_green_step` cases that call it without `paths` must pass one.

`tests/test_git_state.py`:

- `test_renamed_origins_maps_destination_to_origin` — a staged `git mv a b` yields `{"b": "a"}`.
- `test_renamed_origins_is_none_when_git_unreadable` — a non-git directory returns `None`.
- `test_changed_paths_or_none_still_omits_rename_origin` — the existing rename case stays unchanged, pinning that the test-authoring gate sees what it saw before.

### Tests for this step

Every case above must be green before this step is done. Verify the footprint cases by mutation: restore `git add -A` inside `_commit_green_step` and confirm the exclusion cases go red.

## Acceptance criteria

- `_commit_green_step` takes `paths` as a required keyword and calls `commit_all`; `rg 'git", "add' plan_tool/cli/run_cmd.py` returns nothing.
- `run --commit` single-step and `--all` commit only the footprint; an unrelated dirty file outside the delta stays dirty and uncommitted.
- A path dirty at the baseline and still dirty after the commit is named in one warning line.
- An unreadable git state at the baseline or after the step exits non-zero with no commit and with the step's work still in the tree.
- A staged rename commits both paths; an archive move is committed.
- The plan file is clean after each green commit.
- `changed_paths_or_none` returns exactly what it returned before, and `plan_tool/launcher.py` has zero diff.
- `--accept` still commits `expected` and warns on an ignored path.
- `docs/cli/run.md` is regenerated and the `--commit` text no longer says `git add -A`.
- `uv run pytest tests/ -q -n auto` is green, including `tests/test_duplication.py` and the CLI reference drift guard.

## References

- BUG_BACKLOG.md, "`--commit` stages the whole working tree with `git add -A`…" — the defect this plan closes.
- `plan_tool/cli/gitcommit.py` (`commit_all`, `unexpected_dirty_paths`, `path_is_gitignored`) — step 1's contract.
- `plan_tool/git_state.py` (`changed_paths_or_none`) and `plan_tool/launcher.py` (`_git_changed_paths_or_none`) — the delta record and its other consumer.
- `plan_tool/sweep.py` (`ArchiveOutcome`) and `plan_tool/review_persistence.py` (`plan_reports_dir`) — archive and details-directory paths.
- `docs/how-to/pipeline/run.md` — the `--commit` and `--archive` flow this step changes.
- `docs/TRACKING.md` § "Scope contract and anti-creep".

## Applicable guardrails

- **The plan's "## Scope guardrails" and "## Out of scope" (clean-tree precondition, commit subjects, per-step granularity, test-authoring gate).** This step does not edit `launcher.py`. It does not change what gates `--commit` or the subject text. It keeps one commit per green step.
- **The plan's "## Scope guardrails" (no footprint-tracking subsystem).** The footprint comes from the existing git delta plus the plan's own paths. This step adds no hook, no `--no-verify`, no tracking record, and no attribution trailer. The only addition to `git_state.py` is the one additive read of the existing status output.
- **The plan's "## Audit guardrails" and "## Out of scope" (concurrent writer).** A file written by another process during the backend call is committed as the step's work. This step does not try to detect it; step 6 files it.
- **The plan's "## Scope guardrails" (checks added).** The only added check is the binary fact that a footprint path is clean after the commit, which `commit_all` already provides. The dirty-before warning is information only and changes no exit code. The two unreadable-snapshot failures are the plan's named fail-closed result.

## Deferred

- Filing the residual limits of the git delta (a file another process writes during the backend call; a path edited by the step while already dirty) — step 6 records them in `BUG_BACKLOG.md`.
- Removing the `bench.py:_git_commit_baseline` and `commit_receipt` commit paths from this work — the plan's "## Out of scope" leaves both alone.
- Widening `--commit` to other verbs — BACKLOG #89, which lands after this plan.
- Tracking which paths a step really wrote beyond the git delta — would need a new footprint-tracking subsystem, which the plan's scope guardrails exclude.
