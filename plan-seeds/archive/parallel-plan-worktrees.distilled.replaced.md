> **Replaced**: this file has been superseded by `docs/implementation-plans/2-parallel-plan-worktrees.md`.
> Preserved here for history; do not edit.

## Overview

Add the ability for plan-tool to provision **isolated local working copies** so different plans' long-running processes (`create`, `detail`, `run`, `reconcile`, `completeness`, …) can run in parallel without contending on a single working tree, index, or checked-out branch. The default mechanism is **git worktrees** (cheap, shared object store, one branch per worktree) with `--clone` as an explicit opt-in for full isolation; the verb is abstracted over both as a "workspace". The feature is mostly provisioning + lifecycle + conventions: it depends on the branch-awareness plan's git helpers and leans on existing per-cwd plan discovery (`locator.py`), so a worktree "just works" with `plan-tool <cmd> <plan>` run from inside it. Exit codes follow the project convention (non-zero only on failure-to-complete).

## Problem statement

Today every plan-tool process shares one working copy: you can only be on one branch at a time, `--commit` flows interleave, and the branch-awareness guard (separate plan) blocks running plan B while you're on plan A's branch. A `detail` run alone can take ~45 minutes, so serializing several plans is painfully slow. Users need a dedicated working copy per plan, each on that plan's own branch, so their processes are fully independent and can run concurrently.

## Architecture

Use **git worktrees** as the default mechanism, not full `git clone`s. A worktree (`git worktree add <path> <branch>`) is a second working tree + index + HEAD that shares the repo's object store — cheap, instant, each on its own branch. Git forbids checking out the same branch in two worktrees, which *structurally* enforces one-working-copy-per-plan-branch with no bookkeeping. Full clones duplicate the object store (heavy, slow) and split remotes/config; their only advantage is total isolation, so `--clone` is an explicit opt-in. Abstract the verb over both (a "workspace") so the user picks the backing mechanism.

Composition with existing systems:
- **Branch-awareness (companion plan).** A worktree is the natural home for a plan's branch: provisioning a workspace for plan P creates/uses P's branch via `derive_branch`, `default_branch`, `create_and_checkout_branch` and checks it out in the new worktree. When branch-awareness is off (or for an explicit branch), accept a `--branch` argument. This plan depends on those git helpers rather than re-minting them.
- **Per-cwd plan discovery already works.** `locator.py` scopes resolution to the cwd's git tree, and a worktree *is* a git tree (`git rev-parse --show-toplevel` returns the worktree root), so running `plan-tool <cmd> <plan>` with the cwd inside a worktree resolves that worktree's tracked `.plan-tool/plans.json`. Minimal new execution plumbing.
- **Cache isolation falls out for free.** The untracked `.plan-tool/` caches (checkpoints, run logs, lessons-warnings) live in the working tree, so each worktree gets its own — parallel runs don't clobber each other's checkpoint/run state. The one shared surface is `git config --local` (where branch-awareness stores ad-hoc bindings), shared across a repo's worktrees — fine, since bindings are keyed by slug.

**Where worktrees live:** a configurable base path, default a sibling of the repo (never inside it — a worktree inside the main working tree pollutes the tree and confuses git). Default `<repo-parent>/<repo-name>.worktrees/<slug>`, overridable via `.plan-tool/config.json` (`worktree_base`) or a flag. Derive the per-plan path deterministically from the slug so `list`/`remove` can find it without storing extra state.

Scope of work (rough — `create` will decompose):
1. **Git worktree helpers** (extend `cli/gitcommit.py` or a new leaf): `worktree_add(repo, path, branch, *, base)`, `worktree_list(repo)` (parse `git worktree list --porcelain`), `worktree_remove(repo, path, *, force)`, `worktree_prune(repo)`. Mirror the existing subprocess / `(rc, tail)` failure style; never raise on git failure.
2. **Path/config resolution** — the `worktree_base` config (project + user levels, reusing `project_config.py` from the branch-awareness plan) and the deterministic per-slug path derivation.
3. **The `worktree` command group** (a new `cli/` module + `register`): `worktree add <plan> [--branch B] [--clone]` (resolve the plan's branch, provision worktree/clone at derived path, print path + `cd` hint, reuse existing rather than failing); `worktree list` (each plan's worktree, branch, path, dirty/clean state); `worktree remove <plan> [--force]` (refuse on uncommitted changes unless `--force`); `worktree prune` (drop worktrees whose plan is archived/deregistered/whose path is gone; confirm, honor `-y`).
4. **Safety + ergonomics** — clean-tree / confirmation gates on every destructive path; clear messages; deterministic exit codes.
5. **(Optional, possibly its own increment) a `--worktree` convenience** on `run`/`detail` that provisions the plan's worktree and executes the command inside it. Keep the primitive (`worktree add`) and the convenience separable.

## Out of scope

- **Not a job scheduler / queue.** plan-tool provisions isolated workspaces; it doesn't orchestrate, schedule, or cap concurrency, and doesn't auto-run plans in parallel — you launch the processes yourself.
- **No distributed / remote execution.** Local working copies only; no CI, no remote runners.
- **No automatic cleanup without confirmation.** Removing a worktree is destructive; always gate on clean/confirm. `prune` only touches clearly-dead worktrees.
- **No merge / PR management of the parallel branches.** Getting each plan's branch back to `main` stays the normal git/PR flow.
- **No re-minting of git/branch helpers.** Reuse the branch-awareness plan's `derive_branch` / `default_branch` / `create_and_checkout_branch`; this plan adds worktree-specific git calls only.
- **No full-clone default.** Clones are an explicit `--clone` opt-in; the default and recommended path is worktrees.
- **Per-worktree git config.** `extensions.worktreeConfig` is out of scope unless a real case appears.

## Risks

- **Orphaned worktrees / disk usage.** Worktrees accumulate and can leave stale admin files; lean on `git worktree prune` plus plan-tool's own prune, and surface dirty/stale ones in `list`.
- **Dirty-tree removal is data loss.** Never remove a worktree with uncommitted work without explicit `--force`; mirror the branch-awareness clean-tree posture.
- **Shared object store.** Worktrees share `.git/objects`; concurrent git ops are generally safe (git locks), but an aggressive concurrent `gc` could interfere — don't trigger gc in parallel; note the caveat.
- **Per-branch manifest visibility.** A plan registered on `main` but not on the worktree's branch (e.g. created on another branch, unmerged) won't be discoverable in that worktree — consistent with branch-aware plan lifecycle, but document it so a "plan not found" in a worktree isn't surprising.
- **Path pitfalls.** Spaces, long paths, case-insensitive filesystems (macOS APFS), and an existing non-empty target dir — validate and fail clearly rather than letting git error cryptically.
- **Nested repos / submodules.** A worktree of a repo with submodules needs the submodules re-initialized in the new tree; either handle it or scope it out explicitly.

## Testing

Drive `git worktree` against a `tmp_path` repo (real git is fine here, like the existing `--commit` tests; no `claude`). Follow TESTING.md. Cover: add creates a worktree on the right branch at the derived path; same-plan add is idempotent (reuse); same-branch-twice is refused by git and surfaced cleanly; `list` parses porcelain; `remove` refuses on a dirty worktree without `--force` and succeeds with it; `prune` drops archived/missing; `worktree_base` config precedence (project over user); non-git / bad path → clean error, never a crash.

## Acceptance criteria

- `plan-tool worktree add <plan>` provisions a git worktree at a deterministic sibling path, checked out to the plan's branch (derived via branch-awareness, created from default when absent), and prints the path; re-running reuses the existing worktree.
- With the cwd inside that worktree, `plan-tool <cmd> <plan>` resolves that worktree's manifest and runs in isolation — two plans can run concurrently in two worktrees without sharing index/branch/checkpoint state.
- `plan-tool worktree list` reports each plan's worktree (branch, path, dirty state).
- `plan-tool worktree remove <plan>` refuses to delete a dirty worktree without `--force`.
- `plan-tool worktree prune` drops worktrees for archived/deregistered/missing plans on confirmation.
- `worktree_base` config (project over user) relocates the base path; default is a sibling of the repo, never inside it.
- `--clone` provisions a full clone instead of a worktree (documented tradeoff); the default is a worktree.
- Git failures (same-branch-twice, dirty remove, bad path, non-git) surface clean messages and non-zero exit only on failure-to-complete.

## Deferred

- **`--worktree` convenience on `run`/`detail`** — provisioning + in-worktree execution in one command; possibly its own increment, kept separable from the `worktree add` primitive.
