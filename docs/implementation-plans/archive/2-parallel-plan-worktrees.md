> **Auto-archived**: this plan was swept on 2026-07-05 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

---
title: Parallel Plan Worktrees
status: completed
priority: medium
steps:
- id: 1
  title: Add git worktree + clone primitives to gitcommit.py (worktree_add/list/remove/prune,
    clone_repo)
  files:
  - plan_tool/cli/gitcommit.py
  - tests/cli/test_gitcommit.py
  complexity: medium
  change_type: feature
  detail: docs/implementation-plans/plan-details/parallel-plan-worktrees/01-git-worktree-clone-primitives-gitcommit.md
  status: done
- id: 2
  title: Add pure worktree path derivation + base-path resolution (deterministic per-slug
    path, default sibling base, target validation)
  creates:
  - plan_tool/worktree.py
  - tests/test_worktree.py
  complexity: medium
  change_type: feature
  detail: docs/implementation-plans/plan-details/parallel-plan-worktrees/02-pure-worktree-path-derivation-base-path.md
  status: done
- id: 3
  title: Add `worktree` command group with `add` + `list` verbs and wire it into the
    CLI (provision/reuse workspace on the plan's branch; report branch/path/dirty;
    regenerate the CLI reference)
  files:
  - plan_tool/cli/app.py
  - plan_tool/cli/parser.py
  - plan_tool/cli/__init__.py
  - tests/cli/package_surface_help.golden.txt
  - docs/cli/README.md
  creates:
  - plan_tool/cli/worktree_cmd.py
  - tests/cli/test_worktree_cmd.py
  - docs/cli/worktree.md
  allowed_mentions:
  - plan_tool/cli/runs.py
  complexity: high
  change_type: feature
  depends_on:
  - 1
  - 2
  detail: docs/implementation-plans/plan-details/parallel-plan-worktrees/03-worktree-command-group-list-verbs-wire.md
  status: done
- id: 4
  title: Add destructive `worktree remove` + `prune` verbs with clean-tree / confirmation
    safety gates
  files:
  - plan_tool/cli/worktree_cmd.py
  - tests/cli/test_worktree_cmd.py
  complexity: medium
  change_type: feature
  depends_on:
  - 3
  detail: docs/implementation-plans/plan-details/parallel-plan-worktrees/04-destructive-worktree-remove-prune-verbs.md
  status: done
- id: 5
  title: Document the worktree command group across the six operator surfaces (group
    + verbs, worktree_base config + don't-change-while-workspaces-exist orphan caveat,
    --clone tradeoff + clone manual-cleanup (remove/prune never auto-delete a clone),
    per-branch manifest/gc/dirty-remove + orphan-branch-on-remove caveats)
  files:
  - README.md
  - RUNBOOK.md
  - CLAUDE.md
  - BACKLOG.md
  - integrations/claude/SKILL.md
  - integrations/codex/SKILL.md
  complexity: medium
  change_type: non-code
  depends_on:
  - 3
  - 4
  detail: docs/implementation-plans/plan-details/parallel-plan-worktrees/05-document-worktree-command-group-across.md
  status: done
---
# Parallel Plan Worktrees

## Overview

Add the ability for plan-tool to provision **isolated local working copies** so different plans' long-running processes (`create`, `detail`, `run`, `reconcile`, `completeness`, …) can run in parallel without contending on a single working tree, index, or checked-out branch. The default mechanism is **git worktrees** (cheap, shared object store, one branch per worktree) with `--clone` as an explicit opt-in for full isolation; the verb is abstracted over both as a "workspace". The feature is mostly provisioning + lifecycle + conventions: it depends on the branch-awareness plan's git helpers and leans on existing per-cwd plan discovery (`locator.py`), so a worktree "just works" with `plan-tool <cmd> <plan>` run from inside it. Exit codes follow the project convention (non-zero only on failure-to-complete).

## Problem statement

Today every plan-tool process shares one working copy: you can only be on one branch at a time, `--commit` flows interleave, and the branch-awareness guard (separate plan) blocks running plan B while you're on plan A's branch. A `detail` run alone can take ~45 minutes, so serializing several plans is painfully slow. Users need a dedicated working copy per plan, each on that plan's own branch, so their processes are fully independent and can run concurrently.

## Architecture

Use **git worktrees** as the default mechanism, not full `git clone`s. A worktree is a second working tree + index + HEAD that shares the repo's object store — cheap, instant, each on its own branch. **Branch creation and checkout happen *inside* the worktree-add**, never against the main tree: a new branch is `git worktree add -b <branch> <path> <start-point>`, and an existing branch is `git worktree add <path> <branch>`. **The start-point is always defined and locally resolvable:** the resolved default branch's HEAD only when `default_branch` returns a name **with a matching local ref**, *else the repo's current `HEAD`* — falling back to `HEAD` not only when `gitcommit.py:default_branch` returns `None` (a local-only repo with no `origin/HEAD` and no `PLAN_TOOL_DEFAULT_BRANCH` — the common default, and every `tmp_path` test repo) but also when it returns a bare branch name with no local ref (e.g. an `origin/HEAD` pointing at a branch never checked out locally, or a fetch-only mirror), since `default_branch` strips `origin/` and returns a name that need not resolve as a commit-ish. Falling back to `HEAD` is what makes the bare `worktree add <plan>` genuinely "just work" there (`git worktree add -b <branch> <path> HEAD`). (Creating/checking the branch out in the main tree first — e.g. `create_and_checkout_branch`'s `git switch -c` — then `git worktree add <path> <branch>` *cannot* work: git refuses to add a worktree on a branch already checked out in the main tree.) Git forbids checking out the same branch in two worktrees, which *structurally* enforces one-working-copy-per-plan-branch with no bookkeeping. Full clones duplicate the object store (heavy, slow) and split remotes/config; their only advantage is total isolation, so `--clone` is an explicit opt-in. Abstract the verb over both (a "workspace") so the user picks the backing mechanism.

Composition with existing systems:
- **Branch-awareness (companion plan).** A worktree is the natural home for a plan's branch. The dependency on branch-awareness is for **branch-name derivation only** (`derive_branch`, `default_branch`) — *not* checkout: the branch is created+checked-out by the worktree-add itself (`-b`, above), so `create_and_checkout_branch` is **not** used here (it switches the main tree, which the worktree-add then can't co-checkout). **Branch resolution is always defined**, in precedence order: (1) explicit `--branch B` always wins; (2) branch-awareness ON → `derive_branch`; (3) branch-awareness OFF (the project default) → a deterministic **slug-derived fallback** branch name (the plan slug). (`project_config.branch_prefixes` defaults to `["plan/"]` and rejects an empty list, so an ON-but-prefix-less state that would make `derive_branch` index an empty list is unreachable; clause (3) keys on awareness-OFF only — guarding the empty-prefix case is defensive, not a live path.) In all cases the branch is created from the resolved start-point (above) if it doesn't yet exist, so the bare `plan-tool worktree add <plan>` is fully defined under the default-off config. This plan depends on the name-derivation helpers rather than re-minting them.
- **Per-cwd plan discovery already works.** `locator.py` scopes resolution to the cwd's git tree, and a worktree *is* a git tree (`git rev-parse --show-toplevel` returns the worktree root), so running `plan-tool <cmd> <plan>` with the cwd inside a worktree resolves that worktree's tracked `.plan-tool/plans.json`. Minimal new execution plumbing. **Write prerequisite:** because the worktree checks out a branch off the default-branch HEAD, the plan resolves inside it *only if* the plan's `.md` and its tracked `plans.json` entry are committed on that base — provision from a base that lacks them and `plan-tool <cmd> <plan>` reports "plan not found." For now this is an **operator caveat**: provision from a base that has the plan committed, or commit the plan onto the worktree's branch afterward (both legitimate). An up-front `worktree add` pre-check that inspects the base commit's tree (`git show <start-point>:<plan-rel-path>` for the plan `.md` and the slug's entry in `<start-point>:.plan-tool/plans.json`) and warns when either is absent is **deferred** — it needs a new git-read-at-ref primitive outside this plan's scope (see Deferred).
- **Cache isolation falls out for free.** The untracked `.plan-tool/` caches (checkpoints, run logs, lessons-warnings) live in the working tree, so each worktree gets its own — parallel runs don't clobber each other's checkpoint/run state. The one shared surface is `git config --local` (where branch-awareness stores ad-hoc bindings), shared across a repo's worktrees — fine, since bindings are keyed by slug.

**Where worktrees live:** a configurable base path, default a sibling of the repo (never inside it — a worktree inside the main working tree pollutes the tree and confuses git). Default `<repo-parent>/<repo-name>.worktrees/<slug>`, overridable via `.plan-tool/config.json` (`worktree_base`) or a flag. Derive the per-plan path deterministically from the slug so `list`/`remove` can find it without storing extra state. **Caveat of the stateless derivation:** changing `worktree_base` after workspaces exist re-derives a *different* path, orphaning the already-provisioned ones from `list`/`remove`/`prune` (worktrees can still be recovered via git's own registry; clones cannot, so this bites `--clone` hardest). Document that `worktree_base` should not be changed while workspaces exist — re-provision after a change.

Scope of work (rough — `create` will decompose):
1. **Git worktree + clone helpers** (extend `cli/gitcommit.py` or a new leaf): `worktree_add(repo, path, branch, *, create, start_point)` — emits `git worktree add -b <branch> <path> <start_point>` when `create` (new branch off the start point), else `git worktree add <path> <branch>` (existing branch); the branch is born inside the add, never via a main-tree `switch -c`. The caller resolves `start_point` to the default-branch HEAD when available, else `HEAD` (never `None`/empty — a `None` start-point would make `git worktree add -b` fail cryptically on a local-only/no-remote repo). Plus `worktree_list(repo)` (parse `git worktree list --porcelain`), `worktree_remove(repo, path, *, force)`, `worktree_prune(repo)`, and `clone_repo(repo, path, *, branch, start_point)` for the `--clone` path: a clone is an *independent* repo with no main-tree co-checkout conflict, so the worktree `-b` rationale does **not** apply — `clone_repo` does `git clone <repo> <path>` then lands the branch *inside the clone* (`git -C <path> switch -c <branch> <start_point>` for a new branch, plain `switch <branch>` for an existing one). It does **not** use `git clone -b <branch>`, which fails when the branch doesn't yet exist in the source. Mirror the existing subprocess / `(rc, tail)` failure style; never raise on git failure.
2. **Path/config resolution** — the `worktree_base` config (project + user levels, reusing `project_config.py` from the branch-awareness plan) and the deterministic per-slug path derivation.
3. **The `worktree` command group** (a new `cli/` module + `register`; adding it regenerates the drift-guarded CLI reference — `docs/cli/worktree.md` + the `docs/cli/README.md` index row, via `python -m plan_tool.cli_reference --write`, asserted unchanged by `tests/cli/test_cli_reference.py`):
   - `worktree add <plan> [--branch B] [--clone]` — resolve the branch (precedence above), provision a worktree (or clone under `--clone`) at the derived per-slug path, print path + `cd` hint. **Reuse-vs-fail tiebreak at the derived path:** a healthy workspace of the expected kind on the expected branch → reuse (idempotent); a broken/foreign non-empty dir (stale/pruned worktree admin, or an unrelated dir) → fail clearly. This single rule resolves what "reuse existing" and "validate-and-fail on a non-empty target" each cover.
   - `worktree list` — every plan's workspace, **dispatched by kind at the derived path**: worktrees (reported by `git worktree list --porcelain`) *and* clones (a standalone repo dir whose `.git` is a directory, not a worktree gitlink). Reports branch, path, kind, dirty/clean.
   - `worktree remove <plan> [--force]` — for a **worktree**: clean-tree gate (refuse on uncommitted work unless `--force`), then `git worktree remove` — safe to automate because the commits live in the repo's *shared* object store; only the branch ref is orphaned (recoverable). For a **clone**: plan-tool does **not** delete it. A clone is an *independent* repo whose objects aren't shared, so its branch + commits live only in its own `.git`; the uncommitted-only dirty gate can't see committed-but-unmerged work, and `rm -rf` would destroy the sole copy. `remove` on a clone surfaces a **manual-cleanup message** (`rm -rf <path>` yourself after confirming no unmerged commits), never deletes. Run from a cwd *inside* the target workspace (or targeting the main working tree) → git refuses; surface a clean message, not git's raw error.
   - `worktree prune` — drop dead **worktrees** (**deregistered / plan-file-missing / path-gone**); confirm, honor `-y`. **Discovery is git's own worktree registry** (`git worktree list --porcelain`), scoped to worktrees under `worktree_base` whose path matches the deterministic derived-path scheme (so an operator's unrelated worktree is never a candidate). This is safe to automate precisely because worktree removal is non-destructive — commits live in the shared object store; only the branch ref is orphaned (recoverable). **Clones are out of `prune`'s scope** — a clone is an independent repo (may hold committed-but-unmerged work, and carries no plan-tool provenance marker, so *no* path-scan can safely tell a dead plan-tool clone from an operator's unrelated repo parked under the base). `prune` never enumerates or deletes clones; clone visibility is `list`'s job and clone deletion is the operator's manual `rm -rf` (see Out of scope). **The clean-tree gate applies to `prune` too:** a dead-but-dirty worktree is *not* blanket-deleted even under `-y` — surface it for explicit `remove --force` instead (prune must not be a data-loss backdoor around the dirty gate).
4. **Safety + ergonomics** — clean-tree / confirmation gates on every destructive path; clear messages; deterministic exit codes.
5. **(Optional, possibly its own increment) a `--worktree` convenience** on `run`/`detail` that provisions the plan's worktree and executes the command inside it. Keep the primitive (`worktree add`) and the convenience separable.

## References

- [git-worktree Documentation](https://git-scm.com/docs/git-worktree) — The primary reference for git worktree add/list/remove/prune, including the --porcelain output format the plan parses and git's same-branch-checkout restriction that structurally enforces one worktree per branch.
- [git-config Documentation](https://git-scm.com/docs/git-config) — Defines --local vs --worktree config scopes and the extensions.worktreeConfig setting, which the implementer needs to understand the shared git config --local surface and the explicitly out-of-scope per-worktree config option.
- [git-clone Documentation](https://git-scm.com/docs/git-clone) — Reference for the full-clone flags and behavior backing the --clone opt-in path, clarifying the object-store/remote/config duplication tradeoff versus worktrees.
- [gitsubmodules Documentation](https://git-scm.com/docs/gitsubmodules) — Explains how submodule state is tracked per working tree, which the plan must account for since a new worktree of a submodule-bearing repo needs submodules re-initialized.
- [git-submodule Documentation](https://git-scm.com/docs/git-submodule) — Reference for `git submodule update --init --recursive`, the command required to populate submodules in a freshly provisioned worktree (one of the plan's listed risks).
- [git-rev-parse Documentation](https://git-scm.com/docs/git-rev-parse) — Documents --show-toplevel and --git-path, which the plan relies on for per-cwd plan discovery resolving the worktree root and for locating per-worktree git paths.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

- **Not a job scheduler / queue.** plan-tool provisions isolated workspaces; it doesn't orchestrate, schedule, or cap concurrency, and doesn't auto-run plans in parallel — you launch the processes yourself.
- **No distributed / remote execution.** Local working copies only; no CI, no remote runners.
- **No automatic cleanup without confirmation.** Removing a worktree is destructive; always gate on clean/confirm. `prune` only touches clearly-dead workspaces (deregistered / plan-file-missing / path-gone).
- **No merge / PR management of the parallel branches.** Getting each plan's branch back to `main` stays the normal git/PR flow. Consistently, `remove`/`prune` delete the *working tree* (worktree or clone dir) but **not** the branch created inside the add — so removing or auto-pruning a dead/deregistered plan's workspace leaves its branch behind. Branch cleanup (e.g. `git branch -d`) stays the normal git flow; plan-tool does not delete branches. Stated so an operator pruning dead workspaces isn't surprised by accumulating dangling branches.
- **No re-minting of git/branch helpers.** Reuse the branch-awareness plan's `derive_branch` / `default_branch` for branch-*name* derivation only; this plan adds worktree/clone-specific git calls (with the branch created+checked-out by the worktree-add itself). `create_and_checkout_branch` is deliberately *not* reused here — it switches the main tree, which the worktree-add then cannot co-checkout.
- **No full-clone default.** Clones are an explicit `--clone` opt-in; the default and recommended path is worktrees.
- **No auto-deletion of clones.** `remove`/`prune` never `rm -rf` a clone. A clone is an *independent* repo whose objects aren't shared, so it can hold committed-but-unmerged work the uncommitted-only dirty gate can't see, and it carries no plan-tool provenance marker (so a path-scan can't safely distinguish a dead plan-tool clone from an operator's unrelated repo under the base). plan-tool *lists* clones and, on `remove`, surfaces a manual-cleanup message; deleting a clone is the operator's `rm -rf` after confirming no unmerged commits. Worktrees keep full lifecycle (safe — shared object store + git's authoritative registry; removal orphans only a recoverable branch ref).
- **No automatic submodule init.** A provisioned worktree/clone of a submodule-bearing repo comes up with *empty* submodule trees; plan-tool does not run `git submodule update --init --recursive` — the operator runs it manually if needed. (Explicitly scoped out, not "handle-or-scope" ambiguous.)
- **Per-worktree git config.** `extensions.worktreeConfig` is out of scope unless a real case appears.

## Risks

- **Orphaned worktrees / disk usage.** Worktrees accumulate and can leave stale admin files; lean on `git worktree prune` plus plan-tool's own `prune` — which path-scans git's worktree registry and is the verb that surfaces deregistered/orphaned worktrees. `list` is manifest-driven (one derived path per registered plan), so it reports dirty/stale state only for still-registered plans' workspaces, not orphans.
- **Dirty-tree removal is data loss.** Never remove a workspace with uncommitted work without explicit `--force`; mirror the branch-awareness clean-tree posture. **The same gate binds `prune`** — `prune -y` must not blanket-delete a dead-but-dirty workspace (it surfaces it for explicit `remove --force` instead), so prune is never a data-loss backdoor around the dirty gate.
- **Shared object store.** Worktrees share `.git/objects`; concurrent git ops are generally safe (git locks), but an aggressive concurrent `gc` could interfere — don't trigger gc in parallel; note the caveat.
- **Per-branch manifest visibility.** A plan registered on `main` but not on the worktree's branch (e.g. created on another branch, unmerged) won't be discoverable in that worktree — consistent with branch-aware plan lifecycle, but document it so a "plan not found" in a worktree isn't surprising.
- **Path pitfalls.** Spaces, long paths, case-insensitive filesystems (macOS APFS), and an existing non-empty target dir — validate and fail clearly rather than letting git error cryptically.
- **Nested repos / submodules.** A worktree/clone of a submodule-bearing repo comes up with empty submodule trees. Resolved by scoping it out (see Out of scope): plan-tool does not auto-init; the operator runs `git submodule update --init --recursive` if needed.

## Testing

Drive `git worktree` against a `tmp_path` repo (real git is fine here, like the existing `--commit` tests; no `claude`). Follow TESTING.md. Cover: add creates a worktree on the right branch at the derived path, the branch born inside the add (`-b`) off default HEAD when absent; branch resolution fallback (default-off config + no `--branch` → slug-derived branch); same-plan add is idempotent (reuse of a healthy workspace) while a foreign/broken non-empty target fails clearly; same-branch-twice is refused by git and surfaced cleanly; `--clone` provisions a clone; `list` parses porcelain and reports both kinds (clone detected by `.git`-dir kind); `remove` on a **worktree** refuses on dirty without `--force` and succeeds with it, emits a clean message when run from inside the target, and on a **clone** never deletes — emits the manual-cleanup message; `prune` discovers dead **worktrees** via git's worktree registry scoped to `worktree_base` (deregistered/plan-file-missing/path-gone), surfaces (does not delete) a dead-but-dirty worktree even under `-y`, and **never touches clones** (assert a dead clone under the base is left untouched by `prune`); `worktree_base` config precedence (project over user); non-git / bad path → clean error, never a crash.

**Per-step test strategy** (derived from each step's `change_type`):

- step 1 (feature) — unit tests added with the implementation; green before completion.
- step 2 (feature) — unit tests added with the implementation; green before completion.
- step 3 (feature) — unit tests added with the implementation; green before completion.
- step 4 (feature) — unit tests added with the implementation; green before completion.
- step 5 (non-code) — verification appropriate to the artifacts; no test-ordering directive.

## Acceptance criteria

- `plan-tool worktree add <plan>` provisions a git worktree at a deterministic sibling path on the plan's branch, the branch created+checked-out *inside* the worktree-add (`-b` off the resolved start-point — default-branch HEAD, else the repo's current `HEAD` — when the branch is absent), and prints the path; re-running reuses an existing healthy workspace on the expected branch, while a broken/foreign target dir fails clearly. The bare command succeeds on a local-only repo with no remote/default-branch config.
- Branch resolution is always defined: `--branch B` wins; else branch-awareness `derive_branch` when ON; else (default-off / no prefixes) a deterministic slug-derived fallback — so the bare `worktree add <plan>` works under the project-default config.
- With the cwd inside that worktree, `plan-tool <cmd> <plan>` resolves that worktree's manifest and runs in isolation — two plans run concurrently in two worktrees without sharing index/branch/checkpoint state — *provided* the plan's `.md` + manifest entry are committed on the worktree's base branch (an operator caveat; the up-front `add` warning for this is **deferred** — see Deferred).
- `plan-tool worktree list` reports every plan's workspace — both worktrees and `--clone` clones — with branch, path, kind, and dirty state.
- `plan-tool worktree remove <plan>` removes a **worktree** behind the clean-tree gate (refuse on dirty without `--force`); for a **clone** it never auto-deletes — it surfaces a manual-cleanup message (independent repo, possible committed-but-unmerged work). Surfaces a clean message when run from inside the target or against the main tree.
- `plan-tool worktree prune` drops dead **worktrees** on confirmation — discovered via git's own worktree registry scoped to `worktree_base` (derived-path scheme), dropped when **deregistered / plan-file-missing / path-gone** (safe: worktree removal is non-destructive). **Clones are out of prune's scope** (independent repos, possible committed-but-unmerged work, no provenance marker to distinguish from an operator's repo) — visible via `list`, deleted manually. A dead-but-dirty worktree is surfaced rather than deleted even under `-y`.
- `worktree_base` config (project over user) relocates the base path; default is a sibling of the repo, never inside it.
- `--clone` provisions a full clone instead of a worktree (documented tradeoff); the default is a worktree. Clones are first-class in `list`; `remove`/`prune` never auto-delete a clone (manual cleanup — independent repo, possible unmerged commits).
- Git failures (same-branch-twice, dirty remove, bad path, non-git) surface clean messages and non-zero exit only on failure-to-complete.

## Deferred

- **`--worktree` convenience on `run`/`detail`** — provisioning + in-worktree execution in one command; possibly its own increment, kept separable from the `worktree add` primitive.
- **Base-commit plan-presence pre-check / warning on `worktree add`** — inspecting the base commit's tree (`git show <start-point>:<plan-rel-path>` + the slug's `plans.json` entry) and warning up front when the plan isn't committed on the base branch. Needs a new git-read-at-ref primitive not in this plan's scope; until it lands the write prerequisite stands as the documented operator caveat above.
