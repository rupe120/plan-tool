# Handoff: general branch cleanup

This tracks git branch sprawl in the `plan-tool-1` clone's local and `origin`
(Bitbucket) refs: what is fully merged and safe to delete, what looks
abandoned, and what needs an owner decision before deletion. Merged local
branches in all three clones (`plan-tool-1`, `plan-tool-2`,
`internal/plan-tool`) were deleted 2026-09-29 at the owner's
direction, as were the 7 merged remote branches (see the "deleted 2026-09-29"
tables). Every other row is a recommendation for the owner to action:
`git push origin --delete` is outward-facing (it removes the branch for
everyone with the remote). Work with an actual scope and fence
belongs in `BACKLOG.md`; this file is the branch inventory that keeps the
sprawl legible in one place.

Snapshot re-taken 2026-09-29 after `git fetch --prune`, in the `plan-tool-1`
clone, compared against `origin/main` at `ce7ba9d0` (merge of pull request
#8). An earlier revision of this doc described the `plan-tool-2` clone at
`origin/main` `ca71cabc`; that inventory is superseded — the branch sets
differ per clone, so re-run the comparison in whichever clone the cleanup is
performed in rather than reusing these tables.

## Notable findings first

1. **Eighteen remote branches were deleted on `origin` between the two
   snapshots.** `git fetch --prune` dropped their remote-tracking refs:
   `IPPT-9-code`, `IPPT-9-plan`, `agent/ground-create-synthesis-local-code`,
   `cleanup/backlog-drift-and-version-flag`, the three `codex/*` branches
   (`roadmap-feedback-batch-revision`, `roadmap-stack-aware-approval-seed`,
   `roadmap-structural-approval-handoff`), `docs/team-tracking-jira-model`,
   `feature/create-fetch-reference-docs`, `fix/backlog-entry-id-uniqueness`,
   `fix/reconcile-all-round-2`, `graceful-iteration-failure-and-crash-recovery`,
   `impl/roadmap-candidate-envelope-diagnostics`,
   `jira-tracking-priority-and-ticket-format`,
   `plan/convergence-actuation-and-surfacing`,
   `plan/structural-candidate-vocabulary-retry`,
   `plan/telemetry-linkage-backfill`, and `worktree-code-review-loop-round9`.
   Who deleted them, and whether each was merged first, is not established by
   this snapshot; only the ones listed under "Local branches" as ahead of
   `origin/main` are known to carry commits not in `main`.
2. **The 8 unpushed commits on local `main` landed in `origin/main`,
   2026-09-29.** They were moved to `experiments/typesafe-system-one`, pushed,
   and merged (`origin/main` `b770073e`); the remote branch was removed by the
   merge. The local branch was deleted after `git merge-base --is-ancestor`
   confirmed its tip is in `origin/main` (tip `757698df`, restorable with
   `git branch experiments/typesafe-system-one 757698df`).
3. **The PR #16 pair and `docs/team-tracking-jira-model` were reviewed and
   deleted, 2026-09-29.** Their remotes were gone and neither PR #16 branch was
   an ancestor of `origin/main`, because the work reached `main` as squash
   merges (`c41efd75`, "Land backlog ID guard and documentation cleanup
   (#17)"; `79cfd456`, "...(#14)"), which leaves `git cherry` reporting the
   original commits as unmerged. The review counted each branch's added lines
   that are absent from `main`'s current files. `cleanup/…` and `fix/…` have
   identical trees, and `team-tracking-jira-model` is an ancestor of `fix/…`.
   What remained, and where it went:
   - **`BACKLOG.md` #426 (79 of 84 lines):** `main` holds a promotion stub
     pointing to IPPT-4, whose description carries the 13 broken links.
   - **`docs/RELEASING.md` Fix Version JQL (3 lines):** `main` reversed the
     design; Fix Version is listed under "deliberately not configured".
   - **`fenced_spans` caveats on #308:** not on `main` or in IPPT-17. Posted as
     a comment on IPPT-17 (comment `35273`, 2026-09-29): `review.py` calls
     `jira_grade.fenced_spans` from three parsers, and it disagrees with
     `scope_fence._fenced_code_spans` on indented fences and inline code spans.
   - **Everything else** (`TRACKING.md`, `BUG_BACKLOG.md`, `handoffs/README.md`,
     two dated handoffs; 1–27 lines each): wording that `main` has since
     rewritten or moved past. Not preserved.
   PR #16's own state in Bitbucket was not read (the `twg` Bitbucket token was
   invalid), so "superseded by #17" rests on the content comparison.

## Queued

| Item | Where it is tracked | Next step |
| --- | --- | --- |
| Refresh the `demo/*` branches | This doc, "Kept: the `demo/*` branches" | Kept deliberately (owner decision 2026-09-29); they predate the current pipeline and need updating before the next demo. Not a delete candidate. |
| Open the pull request for the handoff branch `docs/branch-cleanup-handoff-plan-tool-2` | This doc | **Held (owner instruction 2026-09-29): open it only after the owner says the branch review is complete.** Do not open it, or prompt for it, before then. The branch is pushed; the `twg` Bitbucket token was invalid on 2026-09-29, so the PR may need to be opened in the Bitbucket web UI. |

## Fully merged into `origin/main` — safe to delete

### Local — deleted 2026-09-29

Each was removed with `git branch -d`, except the `plan-tool-1` rows from `cleanup/backlog-drift-and-version-flag` on,
`plan-tool-2`'s `impl/structural-candidate-vocabulary-retry`, its three
`codex/*` rows, and `backup/main-before-pr18`, which needed `-D` because squash merges leave them unreachable
from `origin/main` (finding 3 and the notes below). Restore with `git branch <name> <sha>`.

| Clone | Branch | Tip when deleted |
| --- | --- | --- |
| `plan-tool-1` | `agent/backlog-catalog-cleanup` | `2f432a2e` |
| `plan-tool-1` | `docs/readme-roadmap-process` | `23669280` |
| `plan-tool-1` | `feat/roadmap-feedback-evidence-reopen` | `78e59fdb` |
| `plan-tool-1` | `fix/bug-backlog-drain-2026-09-28` | `d8125268` |
| `plan-tool-1` | `jira-tracking-priority-and-ticket-format` | `644d87cd` |
| `plan-tool-1` | `roadmap-artifact-html-output-nested-color` | `4b1b0f01` |
| `plan-tool-1` | `experiments/typesafe-system-one` | `757698df` |
| `plan-tool-1` | `cleanup/backlog-drift-and-version-flag` | `f8a4ade9` |
| `plan-tool-1` | `fix/backlog-entry-id-uniqueness` | `bdf21340` |
| `plan-tool-1` | `docs/team-tracking-jira-model` | `6a9ae30d` |
| `plan-tool-1` | `agent/ground-create-synthesis-local-code` | `607460e8` |
| `plan-tool-1` | `docs/developer-front-door` | `3f0f23c1` |
| `plan-tool-2` | `impl/roadmap-candidate-envelope-diagnostics` | `e988e162` |
| `plan-tool-2` | `plan/roadmap-candidate-row-prose-amendments` | `4e5842d1` |
| `plan-tool-2` | `plan/structural-candidate-vocabulary-retry` | `c21ffb03` |
| `plan-tool-2` | `roadmap-candidate-same-batch-relations` | `4e5842d1` |
| `plan-tool-2` | `run/roadmap-candidate-row-prose-amendments` | `e9984fe7` |
| `plan-tool-2` | `impl/structural-candidate-vocabulary-retry` | `34717adf` |
| `plan-tool-2` | `codex/roadmap-feedback-batch-revision` | `d9a83a82` |
| `plan-tool-2` | `codex/roadmap-stack-aware-approval-seed` | `39358b73` |
| `plan-tool-2` | `codex/roadmap-structural-approval-handoff` | `dba3add7` |
| `plan-tool-2` | `backup/main-before-pr18` | `95f07860` |
| `internal/plan-tool` | _(none — only `main` existed)_ | n/a |

Two rows need a qualifier. `plan-tool-2`'s
`run/roadmap-candidate-row-prose-amendments` was checked out at the time; it was
deleted after switching to `main`. `plan-tool-2`'s
`impl/structural-candidate-vocabulary-retry` had one commit not reachable from
`origin/main`, but `git cherry origin/main <branch>` marked it patch-equivalent
(`-`) to a commit already there, so `git branch -d` refused on the differing SHA
and it was removed with `git branch -D`. Every `main` is kept; `plan-tool-2`'s
`main` was fast-forwarded to `origin/main`.

The three `plan-tool-2` `codex/*` branches (171, 46, and 60 commits ahead) were
deleted 2026-09-29 after a content comparison against `origin/main`, the same
method as finding 3. What remained, and why it was not kept:

- **Code:** 36 of 6,283, 2 of 2,644, and 125 of 1,783 added lines were absent
  from `main`. A sample of the largest residue showed refactored lines around
  features `main` has (`--decide-candidate`, `--candidate-decision`,
  `_render_structural_candidate_disclosure`, `CandidateContextBatchCapsule`,
  the selector prompt); the work shipped as IPPT-9 (#20, #21) and its fixes.
- **Seed:** `plan-seeds/roadmap-structural-feedback-approval.md` is absent from
  `plan-seeds/` on `main` because its plan exists and the seed is archived at
  `plan-seeds/archive/roadmap-structural-feedback-approval.replaced.md`.
- **Changelog fragments:** the two fragments only on these branches
  (`changelog.d/roadmap-versioned-feedback-revision-chain.md` and
  `roadmap-stack-aware-approval.md`) are already in `CHANGELOG.md` under 0.1.0
  (2026-09-25), which folded them in; `changelog.d/` correctly holds only its
  README.
- **Review ledgers:** `main` deleted
  `handoffs/2026-09-23-roadmap-structural-feedback-approval-code-review.md` after
  the feature shipped.
- **Not checked:** the doc residue (155, 11, and 91 lines across
  `DATA_CONTRACT.md`, `docs/how-to/roadmap.md`, and similar) was not read line by
  line; those files were rewritten by IPPT-9 and later commits.

`plan-tool-2`'s `backup/main-before-pr18` (6 commits, tip `95f07860`, no remote
copy; includes a merge from `github.com:rupe120/plan-tool`) was deleted
2026-09-29 after the same comparison. It held 2026-09-22 planning work for the
feedback revision chain, all of it superseded on `main`:

- **Seeds:** both are archived under `plan-seeds/archive/` with their plans
  present; the backup's versions match none of the archived generations, so they
  are earlier drafts. **These drafts exist nowhere else now**; restore from
  `95f07860` if the early wording is ever wanted.
- **Completeness reports:** four 15:15 reports; `main` holds the later 18:01 to
  18:15 reports for the same plan.
- **Handoff:** the pre-implementation coordination handoff (work order, checkout
  state, reconstruction notes); its completion condition is met by 0.1.0.
- **Label:** the "pre-PR-#18 safety snapshot" description was inferred from the
  branch name, not confirmed; PR #18's stability on `main` was not checked, and
  the content comparison does not depend on it.

`plan-tool-1`'s `agent/ground-create-synthesis-local-code` (one commit, tip
`607460e8`, remote gone) was deleted 2026-09-29: every symbol the commit added to
`plan_tool/create.py` (`_LocalCodeAnchor`, `_LocalCodeGrounding`,
`_iter_local_code_files`, and the rest) is on `origin/main`.

`plan-tool-1`'s `docs/developer-front-door` (tip `3f0f23c1`) was deleted
2026-09-29 after a check of its 72 commits that are on neither
`origin/docs/developer-front-door` nor, by patch, `origin/main`. The patch
mismatch has a cause: pull request #13 (`79a8e131`) squash-merged this branch's
docs work, so `git cherry` cannot match it. Each added line of the 72 (15
characters or longer) was looked up in every file of `origin/main`'s tree: 2,517
of 11,857 were absent, and the absent lines account as follows.

- **2,004 lines, 54 commits: the withdrawn evaluator plan.**
  `orchestrator-owned-convergence-eval` was withdrawn by one of these commits and
  is archived on `main` (`docs/implementation-plans/archive/`, status
  `planning`, never executed); the absent lines are intermediate drafts that
  later rounds overwrote. Its deferred backlog entries were reworked on
  purpose: #376 replaced #367, #369 was retitled "separately from #376", and #368
  (evaluator governance) is gone with its premise.
- **408 lines, 13 docs commits: renames.** `WORKFLOWS.md` became
  `common-workflows.md`, `DEVELOPMENT_MODEL.md` became `development-model.md`,
  `DOCUMENTATION_STYLE.md` became `docs/reference/documentation-style.md`, and
  `AI_SDLC_POLICY.md` was relocated to
  `docs/reference/ai-assisted-development-policy.md` (`be0f173e`, on `main`).
- **93 lines, 4 commits: the deprecation warnings.** `completeness-apply`,
  `direct-run`, and `direct-jira` print their warnings on `main`, citing #376
  where the branch cited #367.
- **12 lines, 1 commit: the backlog** (covered by the evaluator bullet above).

The other 29 commits were fully covered. All 36 plan slugs the commits touch
have files on `main`. Not done: the 2,517 absent lines were attributed by commit
topic and sampled, not read one by one.

### Remote-only — deleted 2026-09-29

Each of the first seven tips was an ancestor of `origin/main` (`git branch -r
--merged origin/main`, re-checked after a fresh `git fetch --prune`).
`impl/structural-candidate-vocabulary-retry` was not an ancestor: its one commit
was patch-equivalent to a commit already in `origin/main` (`git cherry` marked it
`-`, re-checked immediately before deletion). `docs/developer-front-door` was not
an ancestor either: its 11 commits are the original PR #13 work, squash-merged,
and its tip is an ancestor of the local twin deleted the same day (see the
`docs/developer-front-door` note under "Local — deleted 2026-09-29"). The remote
tip was re-confirmed as `ce4027b1` immediately before deletion. All nine were
removed with `git push origin --delete`. Restore with
`git push origin <sha>:refs/heads/<name>`.

| Branch | Tip when deleted |
| --- | --- |
| `cleanup-completeness-next-steps` | `26976311` |
| `fence-channel-out-of-scope` | `211f83d1` |
| `fix/annotate-seed-consume-remaining-work` | `60f2dc0a` |
| `pluggable-backends` | `89e5100a` |
| `read-only-audit-split` | `76a14823` |
| `roadmap-01-detail` | `139851dc` |
| `split-overloaded-prompts` | `d25470b4` |
| `impl/structural-candidate-vocabulary-retry` | `34717adf` |
| `docs/developer-front-door` | `ce4027b1` |

## Local branches with unmerged work — needs a decision

_(none — `plan-tool-1` has only `main` and the handoff branch; see "Local —
deleted 2026-09-29".)_

### Unmerged work in `plan-tool-2`

_(none — `plan-tool-2` has only `main`; its last unmerged branch was deleted
2026-09-29, see "Local — deleted 2026-09-29".)_

## Remote-only branches — needs triage

_(none — the only remote branches left besides `main` are the four `demo/*`
branches, kept on purpose; see the next section.)_

## Kept: the `demo/*` branches

**Deliberately not deleted, and probably stale.** Owner decision 2026-09-29:
keep all four, and treat them as needing updates before they are shown again.

`origin/demo/1-seed`, `2-plan`, `3-detail`, and `4-jira` are a stacked,
pre-baked walkthrough of the pipeline on a "dark-mode-toggle" example, so a
demo needs no live Claude calls. Each branch snapshots one stage and carries
its own `DEMO.md` script; `DEMO-BAKING.md` on `1-seed` is the cheatsheet for
re-baking.

| Branch | Stage shown | Adds over the previous branch |
| --- | --- | --- |
| `demo/1-seed` | seed | `plan-seeds/dark-mode-toggle.md`, `DEMO-BAKING.md`, `DEMO.md` |
| `demo/2-plan` | `create` | baked plan `docs/implementation-plans/1-dark-mode-toggle.md`, `.plan-tool/plans.json` entry |
| `demo/3-detail` | `detail` | three per-step detail files, completeness report (`.json`, `.md`) |
| `demo/4-jira` | `jira` | `jira-stories.md`, `jira-config.json` |

All four fork from `main` at `f06dc509` (2026-06-23) and are 5,308 commits
behind `origin/main`, with 2, 3, 4, and 5 unique commits (12 files, about 735
lines). No tracked doc references them.

**Why they likely need updates.** The baked artifacts were produced against the
2026-06-23 tool. Plan and detail formats, the `format_version` markers,
`jira` output, and the audit reports have all changed since; a re-bake against
the current tool, or a diff of each stage's artifact against fresh output, is
the way to find out what drifted. That has not been done, so the extent of the
drift is unknown. Being far behind `main` is not itself a defect: the branches
are meant to be checked out on their own.

## Settled: do not reopen

- **Keep the `demo/*` branches** (2026-09-29, owner decision). Do not propose
  deleting them as abandoned; refresh them instead. See "Kept: the `demo/*`
  branches".
