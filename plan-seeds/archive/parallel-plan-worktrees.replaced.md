> **Replaced**: this file has been superseded by `docs/implementation-plans/2-parallel-plan-worktrees.md`.
> Preserved here for history; do not edit.

# Plan seed: isolated local working copies for running plans in parallel

This file is a `plan-tool create` input. Use it via:

```
plan-tool create --from-existing plan-seeds/parallel-plan-worktrees.md
```

It is **not** itself a plan — `plan-tool create` consumes the prose
below and proposes a step decomposition; the author then runs
`plan-tool detail` per step.

---

## Goal

Let plan-tool provision **isolated local working copies** so different
plans' long-running processes (`create`, `detail`, `run`, `reconcile`,
`completeness`, …) can run **in parallel** without contending on a single
working tree, index, or checked-out branch.

Today every plan-tool process shares one working copy: you can only be on
one branch at a time, `--commit` flows interleave, and the branch-
awareness guard (separate plan) blocks running plan B while you're on
plan A's branch. A `detail` run alone can take ~45 minutes — serializing
several plans is painfully slow. The fix: spin up a dedicated working copy
per plan, each on that plan's own branch, so their processes are fully
independent and can run concurrently.

## Worktrees, not full clones (load-bearing — settle, do not relitigate)

Use **git worktrees** as the default mechanism — **not** full `git clone`s:

- A worktree (`git worktree add <path> <branch>`) is a second working
  tree + index + HEAD that **shares the repo's object store**, so it's
  cheap (no re-download / object duplication), instant, and each is on
  its own branch. That is exactly "run different plans on different
  branches in parallel, locally."
- Git **forbids checking out the same branch in two worktrees**, which
  *structurally* enforces one-working-copy-per-plan-branch — no
  bookkeeping needed.
- Full clones duplicate the object store (heavy, slow) and split remotes/
  config; their only advantage is total isolation. Offer `--clone` as an
  explicit opt-in for the rare "I need a fully independent repo" case, but
  **default to worktrees** and document the tradeoff. Abstract the verb
  over both (a "workspace") so the user picks the backing mechanism.

## How it composes with what already exists

- **Branch-awareness (companion plan).** A worktree is the natural home
  for a plan's branch: provisioning a workspace for plan P creates/uses
  P's branch via the branch-awareness helpers (`derive_branch`,
  `default_branch`, `create_and_checkout_branch`) and checks it out in the
  new worktree. When branch-awareness is off (or for an explicit branch),
  accept a `--branch` argument. This plan **depends on** those git helpers
  rather than re-minting them.
- **Per-cwd plan discovery already works.** `locator.py` scopes
  resolution to the cwd's git tree, and a worktree *is* a git tree
  (`git rev-parse --show-toplevel` returns the worktree root). So running
  `plan-tool <cmd> <plan>` with the cwd inside a worktree "just works" —
  it resolves that worktree's tracked `.plan-tool/plans.json`. Minimal
  integration: the feature is mostly **provisioning + lifecycle +
  conventions**, not new execution plumbing.
- **Cache isolation falls out for free.** The untracked `.plan-tool/`
  caches (checkpoints, run logs, lessons-warnings) live in the working
  tree, so each worktree gets its **own** — parallel runs don't clobber
  each other's checkpoint/run state. (Note the one shared surface:
  `git config --local`, where branch-awareness stores ad-hoc bindings, is
  shared across a repo's worktrees — fine, since bindings are keyed by
  slug.)

## Where worktrees live

A **configurable base path**, default a **sibling** of the repo (never
inside it — a worktree inside the main working tree pollutes the tree and
confuses git). E.g. default `<repo-parent>/<repo-name>.worktrees/<slug>`,
overridable via `.plan-tool/config.json` (`worktree_base`) or a flag.
Derive the per-plan path deterministically from the slug so `list`/
`remove` can find it without storing extra state.

## Scope of work (rough — `create` will decompose)

1. **Git worktree helpers** (extend `cli/gitcommit.py` or a new leaf):
   `worktree_add(repo, path, branch, *, base)`, `worktree_list(repo)`
   (parse `git worktree list --porcelain`), `worktree_remove(repo, path,
   *, force)`, `worktree_prune(repo)`. Mirror the existing subprocess /
   `(rc, tail)` failure style; never raise on git failure.
2. **Path/config resolution** — the `worktree_base` config (project +
   user levels, reusing `project_config.py` from the branch-awareness
   plan) and the deterministic per-slug path derivation.
3. **The `worktree` command group** (a new `cli/` module + `register`):
   - `plan-tool worktree add <plan> [--branch B] [--clone]` — resolve the
     plan's branch (branch-awareness derive, or `--branch`, creating it
     from default on a clean source tree), provision the worktree (or
     clone) at the derived path, and print the path + a `cd` hint. Reuse
     an existing worktree for that plan rather than failing.
   - `plan-tool worktree list` — show each plan's worktree, its branch,
     path, and dirty/clean state.
   - `plan-tool worktree remove <plan> [--force]` — remove the worktree
     **safely**: refuse when it has uncommitted changes unless `--force`;
     never delete unmerged work silently.
   - `plan-tool worktree prune` — drop worktrees whose plan is archived /
     deregistered / whose path is gone (git's own prune + plan-tool's
     manifest view); always confirm (honor `-y`).
4. **Safety + ergonomics** — clean-tree / confirmation gates on every
   destructive path; clear messages; deterministic exit codes
   (non-zero only on failure-to-complete, per the project convention).
5. **(Optional, possibly its own increment) a `--worktree` convenience**
   on `run`/`detail` that provisions the plan's worktree and executes the
   command inside it, so "run plan B in parallel" is one command rather
   than add-then-cd-then-run. Keep the primitive (`worktree add`) and the
   convenience separable.
6. **Tests** — drive `git worktree` against a `tmp_path` repo (real git is
   fine here, like the existing `--commit` tests; no `claude`): add
   creates a worktree on the right branch at the derived path; same-plan
   add is idempotent (reuse); same-branch-twice is refused by git and
   surfaced cleanly; list parses porcelain; remove refuses on a dirty
   worktree without `--force` and succeeds with it; prune drops
   archived/missing; `worktree_base` config precedence; non-git / bad
   path → clean error, never a crash. Follow TESTING.md.
7. **Docs** — RUNBOOK walkthrough (provision a worktree per plan, run two
   plans in parallel, clean up), the `worktree_base` knob, and the
   worktree-vs-clone tradeoff; CLAUDE.md command list if enumerated.

## Non-goals

- **Not a job scheduler / queue.** plan-tool *provisions* isolated
  workspaces; it doesn't orchestrate, schedule, or cap concurrency, and
  it doesn't auto-run plans in parallel for you — you launch the
  processes (in separate shells / background) yourself.
- **No distributed / remote execution.** Local working copies only; no
  CI, no remote runners.
- **No automatic cleanup without confirmation.** Removing a worktree is
  destructive; always gate on clean/confirm. `prune` only touches clearly-
  dead worktrees.
- **No merge / PR management of the parallel branches.** Getting each
  plan's branch back to `main` stays the normal git/PR flow.
- **No re-minting of git/branch helpers.** Reuse the branch-awareness
  plan's `derive_branch` / `default_branch` / `create_and_checkout_branch`;
  this plan adds worktree-specific git calls only.
- **No full-clone default.** Clones are an explicit `--clone` opt-in; the
  default and recommended path is worktrees.

## Acceptance criteria (plan-level)

- `plan-tool worktree add <plan>` provisions a git worktree at a
  deterministic sibling path, checked out to the plan's branch (derived
  via branch-awareness, created from default when absent), and prints the
  path; re-running reuses the existing worktree.
- With the cwd inside that worktree, `plan-tool <cmd> <plan>` resolves
  that worktree's manifest and runs in isolation — two plans can run
  concurrently in two worktrees without sharing index/branch/checkpoint
  state.
- `plan-tool worktree list` reports each plan's worktree (branch, path,
  dirty state); `remove` refuses to delete a dirty worktree without
  `--force`; `prune` drops worktrees for archived/deregistered/missing
  plans on confirmation.
- `worktree_base` config (project over user) relocates the base path;
  default is a sibling of the repo, never inside it.
- `--clone` provisions a full clone instead of a worktree (documented
  tradeoff); the default is a worktree.
- Git failures (same-branch-twice, dirty remove, bad path, non-git) surface
  clean messages and non-zero exit only on failure-to-complete.

## Risks

- **Orphaned worktrees / disk usage.** Worktrees accumulate and can leave
  stale admin files; lean on `git worktree prune` plus plan-tool's own
  prune, and surface dirty/stale ones in `list`.
- **Dirty-tree removal is data loss.** Never remove a worktree with
  uncommitted work without explicit `--force`; mirror the branch-awareness
  clean-tree posture.
- **Shared object store.** Worktrees share `.git/objects`; concurrent git
  ops are generally safe (git locks), but an aggressive concurrent `gc`
  could interfere — don't trigger gc in parallel; note the caveat.
- **Per-branch manifest visibility.** A plan registered on `main` but not
  on the worktree's branch (e.g. created on another branch, unmerged)
  won't be discoverable in that worktree — consistent with branch-aware
  plan lifecycle, but document it so a "plan not found" in a worktree
  isn't surprising.
- **Path pitfalls.** Spaces, long paths, case-insensitive filesystems
  (macOS APFS), and an existing non-empty target dir — validate and fail
  clearly rather than letting git error cryptically.
- **Nested repos / submodules.** A worktree of a repo with submodules
  needs the submodules re-initialized in the new tree; either handle it or
  scope it out explicitly.
- **`git config --worktree` vs `--local`.** Ad-hoc branch bindings in
  `--local` config are shared across worktrees (fine, slug-keyed); if a
  future need wants per-worktree config, it requires
  `extensions.worktreeConfig` — out of scope unless a real case appears.
