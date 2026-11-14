# Plan seed: `--commit` stages only the verb's own footprint

## Outcome

Every `--commit` surface commits only the paths its verb wrote, so a file that
another process changes during the run is never swept into the verb's commit.

## Overview

`--commit` requires a clean tree up front, which makes "everything in the tree is
this verb's output" true only at the start. Anything written during a multi-step
run (a concurrent session, an editor sidecar, a hook) is staged by `git add -A`
and committed under a subject describing the verb's work. A 2026-07-31
`detail --commit` run on `roadmap-01-domain-constraints` was one step from
committing four unrelated `plan_tool/` source files edited by a second session
in the same worktree. Source entry: BUG_BACKLOG.md, "`--commit` stages the whole
working tree with `git add -A`…" (moved from BACKLOG #209). No Jira key.

## Problem statement

Two helpers stage the whole tree, and two others already limit their paths:

- `plan_tool/cli/gitcommit.py:commit_all` runs a bare `git add -A` then
  `git commit -m`. Its callers are `completeness-audit --commit`
  (`cli/completeness_cmd.py`), `manifest sweep --commit` (`cli/manifest.py`) and
  `detail --commit` through `cli/authoring.py:_commit_if_dirty`, which serves
  three commits: per converged step, the end-of-run batch for `--jobs>1`, and the
  residual sweep after a per-step run.
- `cli/run_cmd.py:_commit_green_step` stages with `git add -A` unless the caller
  passes `paths` (the `--accept` mode), in which case it stages and commits
  exactly those paths and skips a gitignored one silently. It is the in-repo
  precedent for a caller-supplied footprint.
- `cli/gitcommit.py:commit_receipt` is a second path-limited precedent
  (`git commit --only … -- <path>`), force-adding its one path.
- `bench.py:_git_commit_baseline` also runs `git add -A`, but in a private
  scratch repository the bench creates; it is not an operator tree and stays.

## Architecture

Decisions a later reader must not re-litigate:

- **The footprint is a path set the verb supplies, and the commit helper stages
  `git add -A -- <paths>` and commits `-- <paths>`.** `-A` with a pathspec keeps
  deletes and renames inside the set (the seed-archive move). The existing
  `commit_all` gains the path set as a required argument rather than a second
  helper, so a caller cannot opt back into whole-tree staging by omission;
  `_commit_green_step`'s unscoped branch takes the same set.
- **Each verb owns its footprint.** A verb names the paths it wrote: the plan
  file, the step's detail file, the saved audit report and its sidecar, the
  manifest, archived and moved files, run-log artifacts it creates. Deriving
  each verb's set against live code is `create`'s job. Build order: the helper's
  new contract first, then each caller, then the docs and backlog entry, so no
  caller is converted before the helper can scope it. Where the verb already
  tracks what it wrote, reuse that record; the precedents are
  `gitcommit.py:unexpected_dirty_paths` and `launcher._git_changed_paths_or_none`.
- **After the commit, assert that no expected path is still dirty.** The change
  inverts the failure mode from over-staging to silent under-staging, so a path
  the verb wrote but did not commit is reported as a non-zero commit result that
  names the path. Observable: `git status` shows the path clean.
- **A gitignored expected path is skipped with a one-line warning naming it.**
  This matches what `git add -A` does today and what `_commit_green_step`'s
  `paths` mode does, where an explicit pathspec would instead fail the add. A
  skipped ignored path is exempt from the post-commit assertion, because it can
  never be committed.
- **A verb whose footprint cannot be enumerated without new bookkeeping is not
  converted.** Ship the surfaces that can and file the rest in BUG_BACKLOG.md;
  do not add a tracking layer to make one verb convertible.

## In scope

- `commit_all`'s contract and its three callers, including the three `detail`
  commit sites.
- `_commit_green_step`'s whole-tree branch, so `run --commit` without
  `--accept` takes a footprint too.
- The per-verb footprint for `detail`, `completeness-audit`, `manifest sweep`
  and `run`.
- The post-commit clean assertion and the ignored-path warning, shared by every
  converted surface.
- Every statement that `--commit` stages everything: the `--commit` help text in
  the parser (which regenerates `docs/cli/{run,detail,completeness-audit,sweep}.md`)
  and `docs/how-to/pipeline/{detail,run}.md`, including the detail page's
  "per-step `git add -A` is only safe while…" safety invariant, which the change
  retires. Also removal of the originating BUG_BACKLOG.md entry
  when the work ships, or an update to any deferred surface that remains.

## Out of scope

- The clean-tree precondition, commit subjects, which verbs accept `--commit`,
  per-step commit granularity, and `launcher.py`'s test-authoring git-delta gate.
- Widening `--commit` to more verbs (BACKLOG #89), which lands after this.
- `bench.py:_git_commit_baseline` (private scratch repo) and `commit_receipt`
  (already path-limited).
- Checks beyond the one binary fact that a written path is clean after the
  commit. Deliberately not allowed: judging whether a commit's content is right
  or complete, comparing the footprint with prose, size or count caps, and any
  exit-code change other than the failed-commit result already returned today
  for a commit that cannot complete.
- A new footprint-tracking subsystem, a pre-commit hook, `--no-verify`, any
  AI-attribution trailer, and handling for a concurrent process that edits the
  same file the verb wrote (it is committed with the verb's version of the
  change; this seed does not detect it).

## Allowed behavior changes

Only the commit's contents change: unrelated dirty files are no longer
committed, and an unwritten or ignored expected path produces a warning or a
non-zero commit result as decided above. No flag, subject, or exit-code
convention changes beyond that non-zero result.

## Allowed reorganization

None.

## Risks

- **Under-staging:** a path the verb writes is missing from its footprint and
  silently stays uncommitted. The post-commit assertion only covers paths the
  footprint names, so an omitted one is not caught by it; the per-verb tests
  that diff the commit against the verb's real writes are the guard.
- **Pathspec semantics:** an explicit pathspec rejects an ignored path and
  treats a literal path differently from `-A`. Use a literal pathspec form and
  keep the ignored-path branch tested.
- **Scope expansion:** a footprint tracker can grow into shared bookkeeping.
  Stop and file it instead (see Architecture).

## Testing

Per converted surface, in a real temporary git repository: an unrelated dirty
file present at commit time is not committed; a delete and a rename inside the
footprint still stage; every expected path is clean after the commit; an ignored
expected path warns and takes the decided branch; a path the verb wrote but left
out of its footprint is reported by the post-commit assertion. Break the
footprint code and confirm each of these goes red. Cover the three `detail`
sites separately, since they run at different times against different dirt.

## Acceptance criteria

- No `--commit` surface commits a path outside its verb's footprint; the
  unrelated-dirty-file test passes on every converted surface.
- Deletes and renames inside the footprint stage.
- A footprint path still dirty after the commit makes the verb exit non-zero and
  names the path.
- A gitignored expected path is skipped with a warning and does not fail the
  commit.
- The docs no longer say `--commit` stages the whole tree.
- Any surface that was not converted is named in BUG_BACKLOG.md with the reason.
- The originating BUG_BACKLOG.md entry is removed (or reduced to the deferred
  surfaces) in the plan's final step.

## Deferred

Surfaces whose footprint needs new bookkeeping, and detection of a concurrent
edit to a file the verb also wrote, wait for a separately evidenced request.

Stop / defer: any out-of-scope discovery is filed in BUG_BACKLOG.md (defect) or
BACKLOG.md (forward work), never applied as plan expansion.

## References

- BUG_BACKLOG.md, "`--commit` stages the whole working tree with `git add -A`…"
- `plan_tool/cli/gitcommit.py` (`commit_all`, `commit_receipt`,
  `unexpected_dirty_paths`); `plan_tool/cli/authoring.py` (`_commit_if_dirty`);
  `plan_tool/cli/completeness_cmd.py`; `plan_tool/cli/manifest.py`;
  `plan_tool/cli/run_cmd.py` (`_commit_green_step`)
- `docs/TRACKING.md` § "Scope contract and anti-creep"
- BACKLOG #89 (`--commit` widening, lands after this)
