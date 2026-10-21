> **Replaced**: this file has been superseded by `docs/implementation-plans/2-attach-branch-to-plan.md`.
> Preserved here for history; do not edit.

# Plan seed: branch-aware plans (tool-created branch, manifest-stored, create on default only)

This file is a `plan-tool create` input. Use it via:

```
plan-tool create --from-existing plan-seeds/attach-branch-to-plan.md
```

It is **not** itself a plan — `plan-tool create` consumes the prose
below and proposes a step decomposition. The author then runs
`plan-tool detail` per step to flesh the plan out.

---

## Goal

> **The entire feature is gated by a project-config flag that defaults
> to OFF.** With the flag off (the default, and the state of every
> existing repo), `plan-tool` behaves exactly as it does today: no
> branch field is honored, no run-time guard fires, the binding
> commands refuse as disabled, and `create` runs on any branch. Every
> behavior described below is contingent on the flag being explicitly
> turned on in the project config. See "Configuration gate" below.

Let a registered plan be **bound to a git branch**, so that the
branch becomes part of the plan's identity. Once bound:

1. **The tool creates the branch as part of binding.** Attaching a
   branch to a plan (or registering with `--branch`) **creates that git
   branch if it does not already exist** and checks it out — the user
   does not pre-create it. Creation is from the default branch
   (`git checkout -b <branch> <default>`), only when the working tree
   is clean; an already-existing branch is reused (and checked out), not
   recreated. The binding is then recorded in the **manifest** (see
   "Where binding lives").
2. **The branch is used when running commands for the plan.** When a
   mutating command (`run`, and `run --iterate` reconcile) executes a
   bound plan, the tool verifies the current branch matches the
   plan's bound branch and refuses to proceed on a mismatch — with an
   actionable message. The point is to stop a plan's step-commits
   from landing on the wrong branch.
3. **No more than one plan per branch.** A branch may be claimed by at
   most one registered plan. Attaching a branch that another
   registered plan already claims fails loudly and names the
   conflicting plan.

This is **opt-in** for binding: an unbound plan behaves exactly as
today (no branch guard, no enforcement). The feature only activates
once a plan is bound to a branch.

3. **Plan creation always happens on the default branch.** Plans (and
   the manifest edits that register them) belong on `main`. If
   `plan-tool create` is invoked while checked out on a **non-default**
   branch, it does **not** create the plan or touch the manifest.
   Instead it writes a **seed file** (a `--from-existing` input
   capturing the brief), so that after the feature branch merges into
   the default branch the user can run
   `plan-tool create --from-existing <that seed>` on `main` to
   actually create the plan. This keeps plan files from being born —
   and stranded — on feature branches.

## Where binding lives (load-bearing decision — settle, do not relitigate)

The bound branch is stored in the **manifest** (`.plan-tool/plans.json`),
**not** in plan frontmatter. The branch is tool/VCS state the tool
creates and owns, not plan content — so it belongs in plan-tool's own
registry, not in the plan document.

Extend the manifest entry from a bare path **string** to an **object**
carrying the path plus an optional branch:

```json
{ "plans": [
    { "path": "docs/implementation-plans/2-foo.md", "branch": "feature/foo" },
    "docs/implementation-plans/2-bar.md"
] }
```

- **Backward compatible on read.** A legacy bare-string entry is an
  unbound plan (`branch: null`). `locator.py:load_manifest_plan_paths`
  must accept both shapes (string → `{path, branch: None}`); the
  writer (`create.py:append_to_manifest` / `remove_from_manifest`,
  and the new bind/unbind helpers) emits the object form only when a
  branch is set, leaving unbound plans as bare strings so existing
  manifests diff minimally.
- **One reader/writer owns the schema.** Centralize the
  string-or-object normalization in `locator.py` so every consumer
  (resolution, sweep, list) sees a uniform `(path, branch)` view and no
  caller hand-parses the manifest JSON.
- Binding lives next to the registry of "which plans exist", which is
  exactly what a branch claim is — registry metadata.

The **one-plan-per-branch invariant is manifest-wide** and now trivially
enforced: scan the manifest's own branch bindings (no need to open and
parse every plan's frontmatter). The manifest answers both "which plans
exist" and "what branch does each claim".

## Configuration gate (load-bearing — settle, do not relitigate)

Introduce a config file holding a single boolean feature flag, readable
at **two levels** by a small stdlib-only leaf module
`plan_tool/project_config.py` (mirroring the existing config-module
pattern — `backend_config.py`, `jira_config.py`):

- **Project level:** `<repo-root>/.plan-tool/config.json` (a new file;
  the package ships none).
- **User level:** `~/.plan-tool/config.json` — the same `~/.plan-tool/`
  home-dir convention the tool already uses for the general-lessons
  store and the git-roots cache. Resolve `Path.home()` lazily (at call
  time, not import time) so `$HOME`-overriding test fixtures work, as
  `lessons.py` / `locator.py` already do.

Both files use the same shape:

```json
{ "branch_awareness": { "enabled": false } }
```

- **Default OFF.** Absent file, absent key, or malformed value at a
  given level contributes nothing; with neither level set and no env
  override, the resolved value is `false`. The flag is *opt-in*.
- **Resolution precedence (first that is explicitly set wins):**
  1. `PLAN_TOOL_BRANCH_AWARENESS` env override
  2. **project** `.plan-tool/config.json` (if it sets `enabled`)
  3. **user** `~/.plan-tool/config.json` (if it sets `enabled`)
  4. built-in default `false`

  So the user-level value is the **default for every project that does
  not set it explicitly**; any project that sets `enabled` (true *or*
  false) overrides the user default for that repo. "Explicitly set"
  means the key is present — a project can set `false` to force the
  feature off even when the user default is on.
- **Single master switch, not per-behavior toggles.** One flag gates
  all three behaviors (binding guard, one-per-branch enforcement,
  create-on-default gate). Per-behavior granularity is a non-goal
  (recorded below) — adding it later is purely additive.
- **When off, every new code path short-circuits to today's behavior**
  *before* reading branches or the manifest binding — the guard is a no-op, the
  create gate is skipped, and the `attach-branch` / `detach-branch`
  commands refuse with "branch awareness is disabled; enable it in
  `.plan-tool/config.json`" and exit non-zero (failure-to-complete).

Keep `project_config.py` a leaf below the orchestrators (stdlib only,
no imports from `create`/`launcher`/`locator`) so any command can ask
"is branch awareness on?" without an import cycle.

## Seams already in place (pre-this-plan)

These exist and the steps below build on them — verify before
extending:

- **Manifest read/write** — `locator.py:load_manifest_plan_paths`
  reads the array; `create.py:append_to_manifest` /
  `remove_from_manifest` register/deregister a path (idempotent). These
  are the seams that grow the string-or-object entry shape and the
  branch read/write; keep the normalization in `locator.py`.
- **Plan resolution** — `locator.py:resolve_plan_for_context` /
  `resolve_registered_plan` map a slug/name to a registered plan.
  This is where the plan's manifest entry — and thus its branch
  binding — becomes available to the run guard.
- **Step resolution / run entry** — `launcher.py:resolve_step` picks
  the step to run; `cli/run_cmd.py` is the `run` subcommand dispatcher
  and the natural home for a preflight guard *before* step resolution.
- **Git helpers** — `plan_tool/cli/gitcommit.py` already shells to git
  (`working_tree_dirty` via `git status --porcelain`,
  `path_is_gitignored`, `commit_all`). There is **no** current-branch
  reader yet — add one here.
- **CLI registration pattern** — each module in `app.py:COMMAND_MODULES`
  exports `register(subparsers) -> dict[str, Handler]`.
  `cli/manifest.py` already groups `register` / `deregister` / `sweep`
  subparsers; the new branch commands join that group.

## Scope of work

1. **Add the config reader + feature flag (two-level).** New leaf
   module `plan_tool/project_config.py` that reads both
   `<repo-root>/.plan-tool/config.json` (project) and
   `~/.plan-tool/config.json` (user, lazy `Path.home()`), and exposes a
   single accessor, e.g. `branch_awareness_enabled(repo_root) -> bool`,
   applying the precedence env → project (if `enabled` present) → user
   (if `enabled` present) → default `false`. Distinguish "key absent at
   this level" from "key set to false here" so a project can override a
   user default in either direction. Tolerate absent/malformed config at
   either level by treating that level as unset (never raise). This step
   lands first because every step below guards on it. (Optional: a tiny
   `plan-tool config` read/set surface — with a `--user` flag to target
   the user-level file — to flip the flag without hand-editing JSON;
   nice-to-have, not required.)

2. **Extend the manifest schema to carry an optional branch per entry.**
   In `locator.py`, accept both a bare path string (unbound) and an
   object `{"path": ..., "branch": ...}` (bound), normalizing every
   entry to a uniform `(path, branch)` view for consumers. Update
   `create.py:append_to_manifest` / `remove_from_manifest` to preserve
   and round-trip the branch, emitting the object form only when a
   branch is set (unbound plans stay bare strings). A non-empty branch
   is a single name (one branch per plan — not a list). No `Plan`/
   frontmatter/`schema.py` change — the branch is manifest-only.
   (The branch may sit in the manifest regardless of the flag; it is
   simply *ignored* while the flag is off.) Document the entry shape in
   `PLAN_FORMAT.md`'s manifest section (not the frontmatter schema).

3. **Add the git branch helpers** in `cli/gitcommit.py`:
   - `current_branch(repo_root) -> str | None` — use
     `git rev-parse --abbrev-ref HEAD` (or `symbolic-ref --short HEAD`).
     Return `None` (don't raise) when not a git repo or on detached
     HEAD, so callers degrade gracefully.
   - `default_branch(repo_root) -> str | None` — resolve the repo's
     default branch via `git symbolic-ref --short refs/remotes/origin/HEAD`
     (strip the `origin/` prefix), falling back to a local `main` then
     `master` when there's no remote HEAD, and overridable by a
     `PLAN_TOOL_DEFAULT_BRANCH` env / `--default-branch` flag. Return
     `None` when it can't be determined.
   - `branch_exists(repo_root, name) -> bool` — `git rev-parse --verify
     --quiet refs/heads/<name>` (rc 0 → exists).
   - `create_and_checkout_branch(repo_root, name, *, base) -> (rc, tail)`
     — `git checkout -b <name> <base>`; the binding-time branch creator.
     Callers gate on a clean tree (`working_tree_dirty`) before invoking,
     and on `branch_exists` (reuse + plain checkout when it already
     exists, create when it doesn't). Return `(rc, stderr-tail)` like
     `commit_all` so the caller surfaces git's own message on failure.
   Mirror the existing helpers' subprocess + failure-handling style.

4. **Add the branch-binding CLI commands** under the `manifest` group
   (binding edits the manifest, so it lives there naturally). **All of
   these refuse-as-disabled when the flag is off (step 1).**
   - `plan-tool manifest attach-branch <plan> <branch>` — binds the
     branch to the plan. Must (a) confirm the plan is registered,
     (b) enforce one-plan-per-branch by scanning the manifest's
     bindings, (c) **create + checkout the branch** when it doesn't
     exist (reuse + checkout when it does) via the step-3 helper, gated
     on a clean working tree, and (d) record the branch on the plan's
     manifest entry. A dirty tree (when the branch must be created)
     fails with an actionable message rather than creating over
     uncommitted work.
   - `plan-tool manifest detach-branch <plan>` — clears the manifest
     binding. Leaves the git branch itself untouched (the tool creates
     branches but never deletes them).
   - `--branch <name>` convenience flag on the existing
     `manifest register` to create + bind at registration time (same
     uniqueness check and clean-tree gate).
   Diff/confirm semantics consistent with the other manifest
   subcommands; non-zero exit only on failure-to-complete (a uniqueness
   conflict, or a branch-creation failure, is a failure-to-complete).

5. **Enforce one-plan-per-branch at attach/register time.** A shared
   helper takes the target branch + target plan path and scans every
   *other* manifest binding; if any match (case/format per git's own
   normalization), fail and name the conflicting plan and its path. This
   is the *write-side* half of the invariant, and it runs **before**
   the branch is created so a conflict never leaves a stray new branch.

6. **Add the run-time branch guard (the "branch is used" half).**
   A preflight in `run_cmd.py` (before `launcher.resolve_step`) that
   **does nothing unless the flag is on (step 1)**, and when on and the
   resolved plan has a non-empty manifest branch binding:
   - reads the current branch via the step-2 helper;
   - if current branch != bound branch, refuse with an actionable
     message naming both branches and suggesting `git checkout <bound>`
     (or the step-6 opt-in flag);
   - skips silently when the plan is unbound, or when current branch is
     unknown/not-a-git-repo (don't block non-git workflows — log a
     note, don't fail).
   Scope the guard to the **mutating** path (`run`, and reconcile under
   `run --iterate`), since that's where step-commits land. Keep the
   guard a single reusable function so authoring/read commands can opt
   in later without duplicating logic.

7. **Add an explicit opt-in switch** (e.g. `run --switch-branch`) that,
   instead of refusing, checks out the bound branch before running —
   **only when the working tree is clean** (reuse
   `gitcommit.working_tree_dirty`). The bound branch already exists
   (the tool created it at bind time, step 4), so this is a plain
   checkout, not a create; never switch over uncommitted changes — on a
   dirty tree the guard still refuses with the same message. Default
   behavior without the flag is refuse-on-mismatch.

8. **Gate `create` to the default branch (deflect-to-seed on a
   feature branch).** Add a preflight in `create.py` / `cli/authoring.py`
   (the `create` entry, before any plan write or `append_to_manifest`)
   that **is skipped entirely unless the flag is on (step 1)**:
   - Read current + default branch via the step-3 helpers.
   - **On the default branch (or when branch is unknown / non-git):**
     proceed normally — no behavior change.
   - **On a non-default branch:** do **not** create the plan and do
     **not** touch the manifest. Instead write a seed file capturing
     the original brief (the `--from` string or the resolved
     `--from-existing` contents) plus a header noting the originating
     branch and the exact re-run command. Default the seed's
     destination to `plan-seeds/<slug>.md` (configurable), print the
     path and the "merge to <default>, then
     `plan-tool create --from-existing <path>`" instruction, and exit
     0 (this is a successful deflection, not a failure-to-complete).
   - Add a `--force` / `--allow-non-default-branch` escape hatch for
     the rare intentional case, and skip the whole gate when running in
     directory-mode without a git repo.
   The emitted seed must itself be a valid `create --from-existing`
   input (same shape as this file) so the round-trip actually works.

9. **Tests.** Unit coverage for: the two-level config reader — neither
   level set → off; user on / project unset → on; user on / project
   `false` → off (project overrides user); user off / project on → on;
   malformed at one level → that level ignored, other still honored; env
   override beats both (drive via `$HOME`-redirected tmp dirs like the
   lessons tests). Plus: **every gated behavior is a strict no-op /
   today's behavior when the flag resolves off** (guard, create gate, binding
   commands refuse-as-disabled); the manifest branch round-trips through
   `load_manifest_plan_paths` / `append_to_manifest` (object form when
   bound, bare string when unbound, legacy bare-string read as unbound);
   `current_branch` helper (git repo / not-a-repo /
   detached HEAD, via a tmp repo or stubbed subprocess); `branch_exists`
   / `create_and_checkout_branch` (creates from default on a clean tree,
   reuses an existing branch, refuses on a dirty tree); attach-branch
   happy path (branch created + bound) + uniqueness conflict naming the
   other plan and leaving no stray branch; detach-branch (binding
   cleared, branch left intact); `register --branch`; the run preflight
   guard (bound
   match → proceeds, mismatch → refuses, unbound → no-op, non-git →
   no-op); `--switch-branch` (clean tree switches, dirty tree refuses);
   `default_branch` resolution (origin HEAD / local fallback / env
   override / undeterminable); and the `create` default-branch gate
   (on default → creates; on feature branch → writes a seed, no plan,
   no manifest edit, exit 0; `--force` overrides; round-trip: the
   emitted seed re-runs as a valid `--from-existing` input).
   Follow the invoker-seam discipline in TESTING.md — no real `claude`
   or real `git checkout` against the dev repo; drive git against a
   `tmp_path` repo or stub the subprocess.

10. **Docs.** Update `PLAN_FORMAT.md` (the manifest entry's
    string-or-object shape and the optional `branch` key — in the
    manifest section, not the frontmatter schema),
    `RUNBOOK.md` (how to enable the feature per-project in
    `.plan-tool/config.json` or for all projects in
    `~/.plan-tool/config.json`, and how project overrides user,
    the attach/detach/run-on-bound-branch walkthrough, recovery when
    stranded on the wrong branch, and the create-on-feature-branch →
    seed → merge → re-create workflow), and CLAUDE.md's command list if
    the manifest subcommand surface is enumerated there. Make the
    default-off, opt-in nature explicit.

## Non-goals

- **No on-by-default.** The feature ships OFF and stays OFF until a repo
  opts in via `.plan-tool/config.json`. Changing the default is out of
  scope.
- **No per-behavior config granularity.** One master `branch_awareness`
  flag gates all three behaviors. Separate toggles for guard
  vs. create-gate vs. enforcement are a future, additive change — not
  this plan.
- **Two config levels only — project and user.** No XDG
  (`~/.config`) lookup, no system/etc-wide level, no per-plan override.
  User level (`~/.plan-tool/config.json`) sets the cross-project
  default; project level overrides per repo. That's the whole ladder.
- **No per-plan frontmatter branch field.** The branch lives in the
  manifest entry, never in `schema.py` / plan frontmatter. `Plan` gains
  no `git_branch` field.
- **No multi-branch binding.** Exactly one branch per plan, one plan
  per branch — a 1:1 partial mapping, not many-to-many.
- **No branch deletion.** The tool *creates* the bound branch (at bind
  time, on a clean tree, from the default branch) and checks it out, but
  it never deletes a branch — `detach-branch` clears the binding and
  leaves the git branch in place. Branch creation only happens at
  attach/register time; `--switch-branch` and the run guard only ever
  check out an already-existing branch.
- **No guard on read-only / authoring commands** in this plan
  (`create`, `detail`, `audit`, `jira`, `verify`, `inspect`,
  `annotate`). The guard helper is reusable so they can opt in later,
  but only `run`/reconcile enforce it now.
- **No remote/upstream tracking, no PR linkage, no worktree
  awareness.** Branch matching is purely local current-branch vs.
  bound-branch name.
- **No auto-rebind on rename.** If a branch is renamed out from under a
  bound plan, the guard refuses and the user re-runs `attach-branch`.
- **The create gate does not auto-merge, auto-checkout, or
  auto-register.** On a feature branch it only emits a seed; the user
  merges and re-runs `create` themselves. It also does not
  auto-bind the resulting plan to any branch — binding stays a separate
  explicit `attach-branch` step.

## Acceptance criteria (plan-level)

- **With no config (or `enabled:false`), the tool behaves byte-for-byte
  as before this plan:** `run` ignores any manifest branch binding, `create` works on
  any branch, and `attach-branch`/`detach-branch` refuse with a
  "disabled — enable in `.plan-tool/config.json`" message and exit
  non-zero. Every existing test passes unchanged.
- Setting `{"branch_awareness": {"enabled": true}}` in the project's
  `.plan-tool/config.json` (or `PLAN_TOOL_BRANCH_AWARENESS=1`) activates
  all three behaviors below; unsetting it fully deactivates them.
- Setting `enabled:true` in `~/.plan-tool/config.json` turns the feature
  on **for every project that does not set the key**; a project that
  sets `enabled:false` stays off despite the user default, and a project
  that sets `enabled:true` is on even if the user default is off.
- A registered plan can carry `branch: feature/foo` on its manifest
  entry and round-trip through `load_manifest_plan_paths` /
  `append_to_manifest` unchanged; a legacy bare-string entry reads as
  unbound.
- `plan-tool manifest attach-branch <plan> feature/foo` creates and
  checks out `feature/foo` (when absent) and records it on the plan's
  manifest entry; attaching `feature/foo` to a second registered plan
  fails (naming the first plan and its path) and leaves no stray
  branch. On a dirty tree, when the branch must be created, it refuses.
- `plan-tool manifest detach-branch <plan>` clears the binding and
  leaves the `feature/foo` branch in place.
- `plan-tool manifest register <path> --branch feature/foo` registers,
  creates+binds in one step, subject to the same uniqueness check.
- `plan-tool run <bound-plan>` on `feature/foo` proceeds; on any other
  branch it refuses with a message naming both branches and exits
  non-zero (failure-to-complete) — **without** running any step.
- `plan-tool run <bound-plan> --switch-branch` on a clean tree checks
  out `feature/foo` then runs; on a dirty tree it refuses.
- An **unbound** plan runs exactly as today — no branch read, no guard,
  no behavior change.
- Outside a git repo (or detached HEAD), a bound plan's run logs a note
  and proceeds rather than crashing.
- `plan-tool create` on the default branch creates the plan as today.
- `plan-tool create` on a non-default branch writes a `plan-seeds/`
  seed, creates **no** plan and makes **no** manifest edit, prints the
  re-run instruction, and exits 0. Running
  `plan-tool create --from-existing <that seed>` on the default branch
  afterward produces the plan.
- The create gate is skipped (creates normally) when the default branch
  can't be determined or there's no git repo, and is overridable with
  `--force`.

## Risks

- **Flag-check leakage.** The biggest correctness risk is a new code
  path that runs *before* the flag check and changes behavior when the
  flag is off (e.g. reading branches, refusing a `create`, creating a
  branch, mutating the manifest binding). Every gated path must check `branch_awareness_enabled`
  as its first action and fall straight through to today's behavior.
  Make the off-state a no-op an explicit test on each path, not an
  afterthought.
- **Guard placement too broad.** Enforcing in
  `resolve_plan_for_context` would block read-only commands
  (`manifest list`, `inspect`) on the wrong branch. Keep the guard a
  `run_cmd.py` preflight, not a context-load gate.
- **Uniqueness scan.** Checking one-plan-per-branch reads the single
  manifest file (not every plan's frontmatter), so it's cheap and has
  one source of truth. Re-read the manifest at scan time rather than
  caching, so a concurrent register/bind isn't missed.
- **Manifest schema migration.** Mixing bare-string and object entries
  risks a consumer that hand-parses the JSON and trips on the object
  form. Funnel every read through the `locator.py` normalizer and add a
  test with a mixed-shape manifest; emit bare strings for unbound plans
  so legacy manifests and diffs stay clean.
- **Branch creation is a mutation — gate it.** `attach-branch` /
  `register --branch` run `git checkout -b`, which switches the working
  tree. Create only on a clean tree (refuse otherwise), only after the
  uniqueness check passes (so a conflict leaves no stray branch), and
  reuse + checkout an existing branch rather than failing or recreating.
  Never create over uncommitted work.
- **`--switch-branch` over a dirty tree** is a data-loss footgun.
  Gate strictly on `working_tree_dirty` and refuse — never stash, never
  force. (It only ever checks out the already-created bound branch.)
- **Detached HEAD / non-git** must not hard-fail bound plans, or the
  feature breaks non-git and CI-checkout workflows. The "unknown branch
  → proceed with a note" path is load-bearing; test it explicitly.
- **Branch-name normalization.** `rev-parse --abbrev-ref` vs.
  `symbolic-ref` can differ; pick one reader and compare normalized
  strings on both the write (uniqueness) and read (guard) sides so they
  can't disagree.
- **Default-branch detection is fragile.** No remote, a renamed
  default, or a stale `origin/HEAD` can all mislead the create gate.
  Treat an undeterminable default as "don't block" (create normally)
  rather than "refuse", and honor the `PLAN_TOOL_DEFAULT_BRANCH`
  override so CI / unusual setups have an escape hatch.
- **Deflect-to-seed must not silently swallow the brief.** If the seed
  write fails (bad path, unwritable dir), fail loudly rather than
  dropping the user's input on the floor — the brief is the only
  artifact at that point.
