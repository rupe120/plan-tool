---
format_version: 1
title: Commit Scoped To Verb Footprint
intent: Every `--commit` surface commits only the paths its verb wrote, so a file
  that another process changes during the run is never swept into the verb's commit.
status: planning
priority: medium
risk_profile: standard
risk_profile_rationale: Risk declaration uses standard because --yes does not accept
  model risk proposals.
test_command: uv run pytest tests/ -q -n auto
enforce_step_tests: true
source_seed: docs/implementation-plans/plan-seeds/commit-scoped-to-verb-footprint.md
steps:
- id: 1
  intent: Give every `--commit` surface one helper that can only commit a named footprint
    and that reports a written path left uncommitted.
  files:
  - plan_tool/cli/gitcommit.py
  - plan_tool/cli/authoring.py
  - plan_tool/cli/completeness_cmd.py
  - plan_tool/cli/manifest.py
  - tests/cli/test_gitcommit.py
  complexity: medium
  change_type: feature
  detail: docs/implementation-plans/plan-details/commit-scoped-to-verb-footprint/01-change-commit-all-plan-tool-cli.md
  status: done
  description: 'Change `commit_all` in `plan_tool/cli/gitcommit.py` so it takes a
    required `paths` argument. It stages with `git add -A -- <literal pathspecs>`
    and commits with `git commit -m <subject> -- <pathspecs>`, so only those paths
    are committed and other index entries are not swept in. A directory entry covers
    everything beneath it, which matches how `unexpected_dirty_paths` already treats
    directories. Before staging, a gitignored expected path is skipped with a one-line
    warning naming it, using the existing `path_is_gitignored`. After a successful
    commit, any non-ignored expected path that is still dirty in `git status --porcelain
    --untracked-files=all` produces a non-zero result whose tail names the path. A
    gitignored path skipped this way does not fail the commit. A footprint entry that
    is neither on disk nor tracked is skipped before staging (it names nothing to
    commit), and is outside the post-commit check. A tracked path deleted on disk
    is still staged by `-A`. An entry with no change is staged harmlessly. After staging,
    `commit_all` commits only the entries git knows (tracked, or newly staged by the
    add), so an entry that matches nothing git knows, such as an empty directory or
    one holding only ignored files, is skipped like an absent one instead of failing
    `git commit -- <pathspec>`. When no entry has a change, `commit_all` makes no
    commit and returns success with a tail saying nothing changed, rather than the
    non-zero ''nothing to commit'' git would give. Existing callers keep their whole-tree
    behaviour for now by passing `[repo_root]` as the footprint; steps 2–5 replace
    that. Destructive-operation disposition: `commit_all` deletes nothing itself.
    Through `-A`, a delete or rename inside the footprint is still staged, and a delete
    outside it is no longer staged. Update the module docstring, which describes `--commit`
    as staging the produced edits. Unit tests go in `tests/cli/test_gitcommit.py`
    against a real temporary repo: an unrelated dirty file is not committed, a pre-staged
    unrelated file is not committed, a delete and a rename inside the footprint are
    staged, a directory entry stages its new nested files, an ignored path warns and
    the commit still succeeds, an expected path left dirty (for example when a hook
    rewrites it) is reported by name with a non-zero rc, an absent untracked entry
    is skipped without failing, an empty directory entry beside a changed entry does
    not fail the commit, a tracked deleted entry is staged, and a footprint with no
    changes returns success with no commit.'
- id: 2
  intent: Stop `detail --commit` from committing files another process changed during
    a multi-step authoring run, which is the incident behind this plan.
  files:
  - plan_tool/cli/authoring.py
  - tests/cli/test_authoring_cmds.py
  - docs/cli/detail.md
  complexity: medium
  change_type: feature
  depends_on:
  - 1
  depends_on_notes:
    1: the path-scoped `commit_all` with the ignored-path warning and the post-commit
      clean check
  detail: docs/implementation-plans/plan-details/commit-scoped-to-verb-footprint/02-give-detail-commit-its-own-footprint.md
  status: done
  description: 'Give `detail --commit` its own footprint at all three commit sites
    in `plan_tool/cli/authoring.py`: the per-step commit (`_commit_detail_step`),
    the `--jobs>1` batch commit and the residual sweep after a per-step run. The footprint
    is the plan file, the plan''s `plan-details/<slug>/` directory (detail files,
    `archive/` moves from `_archive_orphan_details`, saved reports from the completeness
    tail), every `steps[].detail` path the plan declares (the same rule as step 3
    and step 5, since a pointer can name a file outside the canonical directory),
    and the lesson files the run appends under `.plan-tool/lessons/`. Confirm the
    exact set in detail against the write sites in `plan_tool/detail.py`. Pass the
    footprint to `commit_all` in place of the transitional `[repo_root]`. Change `_commit_if_dirty`
    so it decides ''nothing to commit'' from dirt inside the footprint, not from a
    dirty tree. The check decides only whether a commit is reported; step 1 already
    makes an empty footprint a successful no-op, so it no longer prevents a failure.
    Keep its never-raises contract and the stop-after-first-failure rule. The rule
    still matters because a failed commit leaves footprint paths staged. Rewrite the
    `--commit` help text, which says it stages everything, and regenerate `docs/cli/detail.md`
    with `python -m plan_tool.cli_reference --write`. Tests go in `tests/cli/test_authoring_cmds.py`,
    written separately for each site because the sites run at different times against
    different dirt. Each site needs a case where an unrelated file dirtied mid-run
    is left out of the commit, a case where an archive rename inside the plan-details
    directory is staged, and a case where every footprint path is clean after the
    commit. A test that patches `authoring._commit_all` follows the new signature.'
- id: 3
  intent: Make an audit commit carry only the plan and report edits the audit produced.
  files:
  - plan_tool/cli/completeness_cmd.py
  - tests/cli/test_completeness_cmd.py
  - docs/cli/completeness-audit.md
  complexity: low
  change_type: feature
  depends_on:
  - 1
  depends_on_notes:
    1: the path-scoped `commit_all`
  detail: docs/implementation-plans/plan-details/commit-scoped-to-verb-footprint/03-give-completeness-audit-commit-plan.md
  status: done
  description: 'Give `completeness-audit --commit` in `plan_tool/cli/completeness_cmd.py`
    its own footprint: the plan file, the plan''s `plan-details/<slug>/` directory
    (the saved report and sidecar from `write_completeness_report`, plus detail files
    the iterate loop edits) and any lesson file the run appends. Confirm the set in
    detail against the run''s write sites. Pass it to `commit_all` in place of `[repo_root]`.
    The subject, the clean-tree precondition and the `--json` / `budget.enabled` gating
    stay as they are. Rewrite the `--commit` help text (''stage all …'') and regenerate
    `docs/cli/completeness-audit.md`. Tests go in `tests/cli/test_completeness_cmd.py`,
    in a real temporary repo: an unrelated file dirtied during the run is not committed,
    the report and sidecar are committed, and every footprint path is clean afterwards.'
- id: 4
  intent: Make a sweep commit carry only the archive moves and manifest edits the
    sweep made.
  files:
  - plan_tool/cli/manifest.py
  - tests/cli/test_manifest_cmds.py
  - docs/cli/sweep.md
  complexity: low
  change_type: feature
  depends_on:
  - 1
  depends_on_notes:
    1: the path-scoped `commit_all`
  detail: docs/implementation-plans/plan-details/commit-scoped-to-verb-footprint/04-give-manifest-sweep-commit-plan-tool.md
  status: done
  description: 'Give `manifest sweep --commit` in `plan_tool/cli/manifest.py` its
    footprint from records the sweep already returns: the manifest path, and each
    `ArchiveOutcome`''s original `plan_path` (a delete) and `archived_to` (an add).
    It also includes the source and destination of each `plan_details_moved` pair
    and each `duplicate_archive_results` pair. Missing-entry deregistrations are covered
    by the manifest path. Replace the whole-tree `working_tree_dirty` check before
    the commit with a check for dirt inside the footprint, so an unrelated dirty file
    no longer turns ''sweep moved nothing'' into a commit. Destructive-operation disposition:
    the archive moves and the manifest rewrites themselves are unchanged. Their deletes
    still reach the commit through `-A`, and only what gets staged is narrowed. Rewrite
    the `--commit` help text (''stage all changes (git add -A)'') and regenerate `docs/cli/sweep.md`.
    Tests go in `tests/cli/test_manifest_cmds.py`: an archived plan''s move and its
    plan-details move are committed as renames, an unrelated dirty file is not committed,
    an unrelated dirty file alone gives ''nothing to commit'', and the footprint is
    clean afterwards.'
- id: 5
  intent: Bring `run --commit` onto a footprint as far as the existing git-delta record
    allows, and record the limit that remains.
  files:
  - plan_tool/cli/run_cmd.py
  - plan_tool/git_state.py
  - tests/cli/test_run_cmd.py
  - tests/test_git_state.py
  - docs/cli/run.md
  complexity: medium
  change_type: feature
  depends_on:
  - 1
  depends_on_notes:
    1: the path-scoped `commit_all` that `_commit_green_step` delegates to
  detail: docs/implementation-plans/plan-details/commit-scoped-to-verb-footprint/05-make-paths-required-on-commit-green.md
  status: done
  description: 'Make `paths` required on `_commit_green_step` in `plan_tool/cli/run_cmd.py`
    and have it delegate staging and committing to `commit_all`, so `run --commit`
    uses the same ignored-path warning and post-commit clean check. The `--accept`
    caller keeps its existing `expected` set. Its silent skip of an ignored path becomes
    the shared one-line warning, which is an allowed change. The single-step and `--all`
    sweep callers pass: the plan file, the plan''s `plan-details/<slug>/` directory,
    every `steps[].detail` path the plan declares, the archived plan and manifest
    when `--archive` completed the plan, and the paths changed since a baseline taken
    just before `run_step`. That baseline uses `git_state.changed_paths_or_none` for
    the changed paths. Rename origins come from a separate, additive rename-aware
    read of the same `git status --porcelain -z` output, added beside it in `git_state.py`;
    `changed_paths_or_none` keeps its current return value, so the test-authoring
    gate in `launcher.py` sees exactly what it sees today. The backend writes arbitrary
    code and nothing records those writes except this git delta. As a result, a file
    another process writes during the backend call is still indistinguishable from
    the step''s own work. The residual is filed in BUG_BACKLOG.md in step 6 and is
    not tracked further here. Dirt left between steps, or dirt from before the baseline,
    is excluded. The git delta holds path names only, so it cannot tell whether the
    step edited a path that was already dirty at the baseline. Such a path is not
    in the footprint and stays uncommitted, and `run` names each path that was dirty
    at the baseline and is still dirty after the commit in a one-line warning (left
    uncommitted because it was dirty before the step; the step may also have edited
    it), so the exclusion is never silent and the warning claims no more than the
    record shows. When `changed_paths_or_none` returns `None` (git state unreadable)
    at the baseline or after the step, `run --commit` fails closed for that step.
    It makes no commit, exits non-zero naming the unreadable snapshot, and leaves
    the step work in the tree for `git reset` recovery. It never falls back to the
    whole tree. Both sides of a rename in the delta are footprint entries. The footprint
    takes the origin path of each rename record from that rename-aware read, so a
    staged `git mv a b` commits the deletion of `a` with `b`. `launcher.py`''s test-authoring
    delta gate is not touched. Destructive-operation disposition: an archive move
    during a completing step is still staged inside the footprint, and a failed commit
    still leaves that step''s work for `git reset` recovery. Rewrite the `--commit`
    help text (''stage all changes (git add -A)'') and regenerate `docs/cli/run.md`.
    Tests go in `tests/cli/test_run_cmd.py`: an unrelated file dirtied after the baseline
    is excluded only when it is outside the delta (pinning the known residual), a
    file dirty before the step is not committed, a file dirty before the step and
    still dirty after is left uncommitted and named in the warning, an unreadable
    git state at either snapshot makes no commit and exits non-zero, a staged rename
    inside the step commits both paths and leaves both clean, the archive move is
    committed, an `--accept` ignored path warns, and the plan file is clean after
    each green commit.'
- id: 6
  intent: Keep the operator docs and the backlog true to what `--commit` now commits,
    and record what is still not covered.
  files:
  - docs/how-to/pipeline/detail.md
  - docs/how-to/pipeline/run.md
  - BUG_BACKLOG.md
  complexity: low
  change_type: non-code
  depends_on:
  - 2
  - 3
  - 4
  - 5
  depends_on_notes:
    5: which part of `run --commit` stays deferred, and why
  detail: docs/implementation-plans/plan-details/commit-scoped-to-verb-footprint/06-rewrite-how-statements-that-say-commit.md
  status: current
  description: 'Rewrite the how-to statements that say `--commit` stages the whole
    tree. In `docs/how-to/pipeline/detail.md`, retire the ''per-step `git add -A`
    is only safe while no prior step left the tree dirty'' safety invariant and its
    surrounding lines. In `docs/how-to/pipeline/run.md`, update the flow diagrams
    at the `git add -A + one commit per green step` lines and the archive and `.gitignore`
    notes so they describe footprint staging and the post-commit clean check. In BUG_BACKLOG.md,
    reduce the originating "`--commit` stages the whole working tree with `git add
    -A`…" entry to the deferred residual: under `run --commit`, a concurrent write
    during the backend call still lands in the step''s commit, because the backend''s
    writes are recorded only as a git delta. Only that undetected case goes in the
    entry; a path already dirty at the step''s baseline is not a residual, since `run`
    names it in a warning at run time. Also name any other surface that steps 2–5
    could not convert, with its reason. Remove the entry outright if nothing is deferred.
    Verify with `rg ''git add -A'' docs/how-to plan_tool/cli`, which should return
    no claim that `--commit` stages everything, and with a clean `uv run pytest tests/cli/test_cli_reference.py`.'
---
# Commit Scoped To Verb Footprint

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

## Scope guardrails

- Change only what each `--commit` surface stages and commits. Do not change the
  clean-tree precondition, commit subjects, which verbs accept `--commit`,
  per-step commit granularity, or `launcher.py`'s test-authoring git-delta gate.
- Do not convert `bench.py:_git_commit_baseline` or `commit_receipt`, and do not
  widen `--commit` to another verb (BACKLOG #89).
- Do not add a footprint-tracking subsystem, a hook, `--no-verify`, or an
  attribution trailer. A verb whose footprint needs new bookkeeping is filed in
  BUG_BACKLOG.md, not converted.
- The only check added is that a written path is clean after the commit. Do not
  add content-quality judgments, prose-agreement checks, caps, or exit-code
  changes beyond the failed-commit result.

## Audit guardrails

- Content-quality judgments, prose-agreement checks, size or count caps, and
  exit-code changes beyond the failed-commit result are out of scope.
- Widening `--commit` to more verbs (BACKLOG #89) and a concurrent process
  editing a written file are out of scope.

## Expected placement

None.

## References

- BUG_BACKLOG.md, "`--commit` stages the whole working tree with `git add -A`…"
- `plan_tool/cli/gitcommit.py` (`commit_all`, `commit_receipt`,
  `unexpected_dirty_paths`); `plan_tool/cli/authoring.py` (`_commit_if_dirty`);
  `plan_tool/cli/completeness_cmd.py`; `plan_tool/cli/manifest.py`;
  `plan_tool/cli/run_cmd.py` (`_commit_green_step`)
- `docs/TRACKING.md` § "Scope contract and anti-creep"
- BACKLOG #89 (`--commit` widening, lands after this)

## Steps

See the `steps:` block in the frontmatter.

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
expected path warns and takes the decided branch; a path the verb wrote but left out of its footprint is caught by the per-verb tests in steps 2–5 that compare the commit with the verb's real writes, not by the post-commit assertion, which checks only the paths the footprint names. Break the
footprint code and confirm each of these goes red. Cover the three `detail`
sites separately, since they run at different times against different dirt.

## Acceptance criteria

- No `--commit` surface commits a path outside its verb's footprint; the
  unrelated-dirty-file test passes on every converted surface. For `run`, the
  footprint is the git delta since the step's baseline, so the guarantee covers
  dirt present before that baseline; a file another process writes during the
  backend call is a named residual, filed in BUG_BACKLOG.md.
- A footprint entry that is absent and untracked, or unchanged, never fails the
  commit, and a footprint with no changes makes no commit and succeeds.
- A path dirty at a `run` step's baseline and still dirty after it is left
  uncommitted and named in a warning; an unreadable git state makes that step's
  commit fail closed, never fall back to the whole tree.
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
