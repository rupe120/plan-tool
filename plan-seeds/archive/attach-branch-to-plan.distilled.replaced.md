> **Replaced**: this file has been superseded by `docs/implementation-plans/2-attach-branch-to-plan.md`.
> Preserved here for history; do not edit.

## Overview

Lets a registered plan be **bound to a git branch** so the branch becomes part of the plan's identity. The entire feature is gated by a single project-config flag (`branch_awareness`) that **defaults OFF** — with the flag off (every existing repo), `plan-tool` behaves byte-for-byte as today. When on, three behaviors activate: (1) binding creates+checks-out the branch and records it in the manifest, (2) `run`/reconcile refuse on a branch mismatch, and (3) `create` on a non-default branch deflects to a seed file instead of writing a plan. Binding is itself opt-in per plan: an unbound plan never triggers a guard. The bound branch lives in the manifest (`.plan-tool/plans.json`), never in plan frontmatter.

## Problem statement

Today nothing ties a plan to a branch, so a plan's step-commits can land on the wrong branch, and a plan file created while checked out on a feature branch is born — and stranded — on that branch instead of living on the default branch (`main`) where plans and manifest edits belong. There is also no current-branch reader in `plan_tool/cli/gitcommit.py`. This plan adds opt-in branch identity so a bound plan refuses to run on the wrong branch and `create` on a feature branch emits a re-runnable seed instead of a stranded plan.

## Architecture

**Configuration gate.** A new stdlib-only leaf module `plan_tool/project_config.py` (mirroring `backend_config.py` / `jira_config.py`) reads the flag at two levels — project `<repo-root>/.plan-tool/config.json` and user `~/.plan-tool/config.json` (lazy `Path.home()` so `$HOME`-overriding fixtures work, as `lessons.py`/`locator.py` do). Both files share the shape `{ "branch_awareness": { "enabled": false } }`. Resolution precedence, first explicitly-set wins: (1) `PLAN_TOOL_BRANCH_AWARENESS` env, (2) project config if `enabled` present, (3) user config if `enabled` present, (4) built-in `false`. "Explicitly set" means the key is present, so a project can set `false` to override a user `true`. One master switch gates all three behaviors. Keep `project_config.py` a leaf below the orchestrators (no imports from `create`/`launcher`/`locator`) so any command can ask "is branch awareness on?" without an import cycle. Every gated path checks `branch_awareness_enabled` as its first action and falls straight through to today's behavior when off.

**Where binding lives (settled).** The bound branch is stored in the manifest, not plan frontmatter — it is tool/VCS state the tool creates and owns, so it belongs in plan-tool's own registry. The manifest entry grows from a bare path **string** to an **object** `{ "path": ..., "branch": ... }`, e.g. `{ "path": "docs/implementation-plans/2-foo.md", "branch": "feature/foo" }`. Backward compatible on read: a legacy bare string is an unbound plan (`branch: null`). Centralize string-or-object normalization in `locator.py` so every consumer sees a uniform `(path, branch)` view and no caller hand-parses the JSON; `locator.py:load_manifest_plan_paths` accepts both shapes, and the writers (`create.py:append_to_manifest`/`remove_from_manifest` plus new bind/unbind helpers) emit the object form **only** when a branch is set, leaving unbound plans as bare strings so manifests diff minimally. No `Plan`/frontmatter/`schema.py` change. The one-plan-per-branch invariant is manifest-wide and enforced by scanning the manifest's own branch bindings — no need to open every plan's frontmatter.

**Seams built on (pre-existing).** Manifest read/write: `locator.py:load_manifest_plan_paths`, `create.py:append_to_manifest`/`remove_from_manifest`. Plan resolution: `locator.py:resolve_plan_for_context`/`resolve_registered_plan` (where a plan's branch binding becomes available to the run guard). Run entry: `launcher.py:resolve_step` and `cli/run_cmd.py` (home for a preflight guard before step resolution). Git helpers: `plan_tool/cli/gitcommit.py` already has `working_tree_dirty`, `path_is_gitignored`, `commit_all`, but **no** current-branch reader — add one. CLI registration: each `app.py:COMMAND_MODULES` module exports `register(subparsers) -> dict[str, Handler]`; `cli/manifest.py` groups `register`/`deregister`/`sweep` and the new branch commands join it.

**New git helpers (`cli/gitcommit.py`), mirroring existing subprocess/failure style:** `current_branch(repo_root) -> str | None` (`git rev-parse --abbrev-ref HEAD` / `symbolic-ref --short HEAD`; `None` on non-git/detached HEAD); `default_branch(repo_root) -> str | None` (`git symbolic-ref --short refs/remotes/origin/HEAD` stripping `origin/`, falling back to local `main` then `master`, overridable by `PLAN_TOOL_DEFAULT_BRANCH` env / `--default-branch`); `branch_exists(repo_root, name) -> bool` (`git rev-parse --verify --quiet refs/heads/<name>`); `create_and_checkout_branch(repo_root, name, *, base) -> (rc, tail)` (`git checkout -b <name> <base>`, returning `(rc, stderr-tail)` like `commit_all`). Pick one branch-name reader and compare normalized strings on both write (uniqueness) and read (guard) sides so they can't disagree.

**CLI surface (under the `manifest` group).** `manifest attach-branch <plan> <branch>`: confirm plan registered, enforce one-plan-per-branch by scanning bindings, create+checkout the branch when absent (reuse+checkout when present) gated on a clean tree, then record the branch on the entry. `manifest detach-branch <plan>`: clear the binding, leave the git branch untouched. `--branch <name>` flag on `manifest register` to create+bind at registration. All refuse-as-disabled when the flag is off. A shared write-side helper enforces uniqueness **before** branch creation so a conflict never leaves a stray branch.

**Run-time guard.** A preflight in `run_cmd.py` (before `launcher.resolve_step`), a single reusable function, that no-ops unless the flag is on; when on and the resolved plan has a non-empty bound branch, reads current branch and refuses on mismatch with a message naming both branches and suggesting `git checkout <bound>` (or the opt-in flag). Scoped to the mutating path (`run`, reconcile under `run --iterate`). Skips silently for unbound plans or unknown/non-git branch (logs a note, never blocks). Kept out of `resolve_plan_for_context` so read-only commands aren't blocked. An explicit `run --switch-branch` opt-in checks out the already-existing bound branch instead of refusing — only on a clean tree (reuse `working_tree_dirty`), never stashing/forcing; dirty tree still refuses.

**Create gate.** A preflight in `create.py`/`cli/authoring.py` (before any plan write or `append_to_manifest`), skipped entirely unless the flag is on. On the default branch (or unknown/non-git): proceed normally. On a non-default branch: write no plan and touch no manifest; instead write a seed file capturing the original brief (`--from` string or resolved `--from-existing` contents) plus a header noting the originating branch and exact re-run command, defaulting to `plan-seeds/<slug>.md`, print the path and "merge to <default>, then `plan-tool create --from-existing <path>`", and exit 0. The emitted seed must be a valid `create --from-existing` input. A `--force`/`--allow-non-default-branch` escape hatch overrides; the gate is skipped in directory-mode without a git repo.

## Out of scope

- **No on-by-default.** Ships OFF and stays OFF until a repo opts in via `.plan-tool/config.json`; changing the default is out of scope.
- **No per-behavior config granularity.** One master `branch_awareness` flag gates all three behaviors; separate toggles are a future additive change.
- **Two config levels only — project and user.** No XDG (`~/.config`) lookup, no system/etc-wide level, no per-plan override.
- **No per-plan frontmatter branch field.** The branch lives only in the manifest entry; `Plan` gains no `git_branch` field and `schema.py` is untouched.
- **No multi-branch binding.** Exactly one branch per plan, one plan per branch — a 1:1 partial mapping.
- **No branch deletion.** The tool creates the bound branch (clean tree, from default) but never deletes one; `detach-branch` clears the binding and leaves the branch in place. Branch creation only happens at attach/register time.
- **No guard on read-only/authoring commands** (`create`'s own guard aside): `detail`, `audit`, `jira`, `verify`, `inspect`, `annotate` are not guarded here; the helper is reusable so they can opt in later.
- **No remote/upstream tracking, no PR linkage, no worktree awareness.** Matching is purely local current-branch vs. bound-branch name.
- **No auto-rebind on rename.** A renamed branch makes the guard refuse; the user re-runs `attach-branch`.
- **The create gate does not auto-merge, auto-checkout, auto-register, or auto-bind.** On a feature branch it only emits a seed; binding stays a separate explicit `attach-branch` step.

## Risks

- **Flag-check leakage (highest correctness risk).** A new code path that runs *before* the flag check and changes behavior when off (reading branches, refusing a `create`, creating a branch, mutating the binding). Every gated path must check `branch_awareness_enabled` first and fall through to today's behavior; make the off-state no-op an explicit test on each path.
- **Guard placement too broad.** Enforcing in `resolve_plan_for_context` would block read-only commands (`manifest list`, `inspect`) on the wrong branch. Keep the guard a `run_cmd.py` preflight, not a context-load gate.
- **Uniqueness scan.** Checking one-plan-per-branch reads the single manifest file (not every plan's frontmatter), so it's cheap with one source of truth. Re-read the manifest at scan time rather than caching so a concurrent register/bind isn't missed.
- **Manifest schema migration.** Mixing bare-string and object entries risks a consumer that hand-parses the JSON and trips on the object form. Funnel every read through the `locator.py` normalizer, add a mixed-shape manifest test, and emit bare strings for unbound plans so legacy manifests/diffs stay clean.
- **Branch creation is a mutation — gate it.** `attach-branch`/`register --branch` run `git checkout -b`, switching the working tree. Create only on a clean tree (refuse otherwise), only after the uniqueness check passes (so a conflict leaves no stray branch), and reuse+checkout an existing branch rather than failing or recreating. Never create over uncommitted work.
- **`--switch-branch` over a dirty tree** is a data-loss footgun. Gate strictly on `working_tree_dirty` and refuse — never stash, never force; it only ever checks out the already-created bound branch.
- **Detached HEAD / non-git** must not hard-fail bound plans, or the feature breaks non-git and CI-checkout workflows. The "unknown branch → proceed with a note" path is load-bearing; test it explicitly.
- **Branch-name normalization.** `rev-parse --abbrev-ref` vs. `symbolic-ref` can differ; pick one reader and compare normalized strings on both write (uniqueness) and read (guard) sides.
- **Default-branch detection is fragile.** No remote, a renamed default, or stale `origin/HEAD` can mislead the create gate. Treat an undeterminable default as "don't block" (create normally), and honor the `PLAN_TOOL_DEFAULT_BRANCH` override.
- **Deflect-to-seed must not silently swallow the brief.** If the seed write fails (bad path, unwritable dir), fail loudly rather than dropping the user's input — the brief is the only artifact at that point.

## Testing

Follow the invoker-seam discipline in TESTING.md — no real `claude` and no real `git checkout` against the dev repo; drive git against a `tmp_path` repo or stub the subprocess. Drive two-level config tests via `$HOME`-redirected tmp dirs as the lessons tests do. Mirror source modules: `project_config.py` → `tests/test_project_config.py`, `locator.py` → `tests/test_locator.py`, `cli/gitcommit.py` → `tests/test_gitcommit.py`, and the manifest/run/create CLI behaviors under their existing test modules.

Unit coverage:
- **Two-level config reader:** neither level set → off; user on / project unset → on; user on / project `false` → off (project overrides user); user off / project on → on; malformed at one level → that level ignored, other still honored; env override beats both.
- **Flag-off no-ops:** every gated behavior is a strict no-op / today's behavior when the flag resolves off (run guard, create gate, binding commands refuse-as-disabled).
- **Manifest round-trip:** branch round-trips through `load_manifest_plan_paths`/`append_to_manifest` — object form when bound, bare string when unbound, legacy bare-string read as unbound; include a mixed-shape manifest.
- **Git helpers:** `current_branch` (git repo / not-a-repo / detached HEAD); `branch_exists` and `create_and_checkout_branch` (creates from default on a clean tree, reuses an existing branch, refuses on a dirty tree); `default_branch` resolution (origin HEAD / local fallback / env override / undeterminable).
- **Binding commands:** attach-branch happy path (branch created + bound) + uniqueness conflict naming the other plan and leaving no stray branch; detach-branch (binding cleared, branch left intact); `register --branch`.
- **Run preflight guard:** bound match → proceeds, mismatch → refuses, unbound → no-op, non-git → no-op; `--switch-branch` (clean tree switches, dirty tree refuses).
- **Create default-branch gate:** on default → creates; on feature branch → writes a seed, no plan, no manifest edit, exit 0; `--force` overrides; round-trip — the emitted seed re-runs as a valid `--from-existing` input.

All existing tests must pass unchanged (the flag-off path is byte-for-byte today's behavior).

## Acceptance criteria

- With no config (or `enabled:false`), the tool behaves byte-for-byte as before: `run` ignores any manifest branch binding, `create` works on any branch, and `attach-branch`/`detach-branch` refuse with a "disabled — enable in `.plan-tool/config.json`" message and exit non-zero; every existing test passes unchanged.
- Setting `{"branch_awareness": {"enabled": true}}` in the project's `.plan-tool/config.json` (or `PLAN_TOOL_BRANCH_AWARENESS=1`) activates all three behaviors; unsetting it fully deactivates them.
- Setting `enabled:true` in `~/.plan-tool/config.json` turns the feature on for every project that does not set the key; a project that sets `enabled:false` stays off despite the user default, and a project that sets `enabled:true` is on even if the user default is off.
- A registered plan can carry `branch: feature/foo` on its manifest entry and round-trip through `load_manifest_plan_paths`/`append_to_manifest` unchanged; a legacy bare-string entry reads as unbound.
- `plan-tool manifest attach-branch <plan> feature/foo` creates and checks out `feature/foo` (when absent) and records it on the plan's manifest entry; attaching `feature/foo` to a second registered plan fails (naming the first plan and its path) and leaves no stray branch; on a dirty tree, when the branch must be created, it refuses.
- `plan-tool manifest detach-branch <plan>` clears the binding and leaves the `feature/foo` branch in place.
- `plan-tool manifest register <path> --branch feature/foo` registers and creates+binds in one step, subject to the same uniqueness check.
- `plan-tool run <bound-plan>` on `feature/foo` proceeds; on any other branch it refuses with a message naming both branches and exits non-zero without running any step.
- `plan-tool run <bound-plan> --switch-branch` on a clean tree checks out `feature/foo` then runs; on a dirty tree it refuses.
- An unbound plan runs exactly as today — no branch read, no guard, no behavior change.
- Outside a git repo (or detached HEAD), a bound plan's run logs a note and proceeds rather than crashing.
- `plan-tool create` on the default branch creates the plan as today.
- `plan-tool create` on a non-default branch writes a `plan-seeds/` seed, creates no plan and makes no manifest edit, prints the re-run instruction, and exits 0; running `plan-tool create --from-existing <that seed>` on the default branch afterward produces the plan.
- The create gate is skipped (creates normally) when the default branch can't be determined or there's no git repo, and is overridable with `--force`.

## Deferred

- **Tiny `plan-tool config` read/set surface** (with a `--user` flag to target the user-level file) to flip the `branch_awareness` flag without hand-editing JSON — explicitly noted as a nice-to-have, not required for this plan.
