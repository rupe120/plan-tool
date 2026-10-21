> **Auto-archived**: this plan was swept on 2026-07-05 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 4 — Add destructive `worktree remove` + `prune` verbs with clean-tree / confirmation safety gates

## Summary

Extend `plan_tool/cli/worktree_cmd.py` (created in step 3) with two destructive verbs: `worktree remove <plan> [--force]` (delete one plan's **worktree**; on a **clone**, surface a manual-cleanup message — plan-tool never deletes a clone) and `worktree prune` (sweep dead, plan-tool-provisioned **worktrees**; clones are out of scope). Both layer the **clean-tree pre-gate + confirmation policy** that step 1's policy-free `worktree_remove` / `worktree_prune` primitives deliberately left to the caller: refuse to delete a worktree with uncommitted work unless `--force`, confirm at the TTY (bypassed under `-y`), and surface a clean message — never git's raw error — when `remove` targets the workspace the operator is standing in. The key safety rule: **`prune` never deletes a dirty workspace, even under `-y`** — it surfaces it for explicit `remove --force` instead, so prune can't become a data-loss backdoor around the dirty gate. Neither verb deletes the branch born inside the workspace (out of scope by plan decision). On green, `plan-tool worktree remove <plan>` and `plan-tool worktree prune` are dispatchable, gated, and covered by new unit tests against a real `tmp_path` repo, and the regenerated `docs/cli/worktree.md` drift guard passes.

## Table of Contents

- [Why](#why) — what these verbs complete and the gate policy they add
- [Files (creates vs edits)](#files-creates-vs-edits) — the command module, its test, and the regenerated reference
- [Implementation](#implementation) — the two verb handlers, the shared dirty gate + confirm helper, kind dispatch reuse, and registration
- [Tests](#tests) — `remove`/`prune` cases against a real `tmp_path` repo
- [Test-creation order (feature step)](#test-creation-order-feature-step) — write-with-implementation, green-before-done gate
- [Acceptance criteria](#acceptance-criteria) — observable behaviors a reviewer can check
- [References](#references) — git docs for `remove`/`prune` and cwd resolution
- [Deferred](#deferred) — branch deletion, clone auto-deletion (manual cleanup), write-prerequisite warning, builder consolidation

## Why

- **Step 3 ships `add` + `list`; the lifecycle has no teardown.** A provisioned workspace can only be created and inspected, never removed through plan-tool. Worktrees and clones accumulate on disk with no in-tool way to reclaim them.
- **The destructive primitives are policy-free by design.** Step 1's `worktree_remove(repo, path, *, force)` relies on git's own dirty-tree refusal and adds no pre-gate; `worktree_prune(repo)` only clears git admin metadata. The clean-tree pre-gate, the confirmation prompt, the discovery of *which* workspaces are dead, and the dirty-skip rule on prune are all explicitly assigned to this step (step 1's Deferred: "Clean-tree pre-gate, confirmation, and dirty-surfacing policy on remove/prune — step 4").
- **Clones are never auto-deleted (plan decision).** A clone is an *independent* repo whose objects aren't shared, so it can hold committed-but-unmerged work the uncommitted-only dirty gate can't see, and it carries no plan-tool provenance marker. `remove` on a clone surfaces a manual-cleanup message rather than deleting; `prune` ignores clones entirely. So the destructive teardown this step gates is **worktrees only** — a worktree's removal is non-destructive (commits live in the shared object store; only the branch ref is orphaned, recoverable).

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/cli/worktree_cmd.py` — add the `_cmd_worktree_remove` / `_cmd_worktree_prune` verb handlers; add the private `_dirty_gate`, `_confirm`, and `_inside_target` helpers; add `remove` and `prune` arms to `cmd_worktree`'s `args.action` dispatch; register the two sub-parsers (with a locally-built `-y/--yes` parent and `remove`'s `--force`) in `register`; extend the gitcommit import to add `worktree_remove`, `worktree_prune`, and the `plan_tool.worktree` import to add `worktree_base`.
  - `tests/cli/test_worktree_cmd.py` — add `TestWorktreeRemove`, `TestWorktreePrune`, and a `TestRemovePruneConfirmGate` class (real `git` against `tmp_path`, no `claude`); extend `TestWorktreeWiring` to assert the two new verbs dispatch.
- **Required generated-file addition (flagged — outside the declared `files:` list, but mandatory):**
  - `docs/cli/worktree.md` — adding the `remove`/`prune` sub-parsers changes the generated per-command reference (it enumerates every subaction + flag). Regenerate with `python -m plan_tool.cli_reference --write`; it is drift-guarded by `tests/cli/test_cli_reference.py` and will fail that test if left stale. Do **not** hand-edit it. The top-level `tests/cli/package_surface_help.golden.txt` does **not** change — sub-verbs are internal to the `worktree` group and don't alter `plan-tool --help`'s top-level subcommand list.

## Implementation

### Foundational logic & shared call sites

- **Foundational logic of this step:** the **clean-tree pre-gate** — `working_tree_dirty(target)` and not `force` → refuse — applied to **worktree** deletion in both verbs (`remove` and `prune`), with prune's variant *surfacing-not-deleting* a dirty worktree even under `-y`. (Clones aren't deleted by either verb, so the gate doesn't apply to them — `remove` on a clone short-circuits to a manual-cleanup message; `prune` ignores clones.)
- **Reuse `working_tree_dirty` from `plan_tool/cli/gitcommit.py`**, the same dirty check step 3's `list` uses. Do **not** route through `plan_tool/cli/run_cmd.py`'s separate `_working_tree_dirty` — that one belongs to `run`'s `--commit` helper and folding the two would couple the worktree group to `run`'s commit lifecycle (step 1's Deferred records this non-consolidation).
- **Reuse step 3's `_classify_workspace_kind(target, wt_by_path)`** (already in `worktree_cmd.py`) to decide worktree-vs-clone for a target — do not duplicate the kind probe. This step adds no behavior-preserving restructuring of step 3's code; it only calls the existing helpers. (If step 3's classifier is private and shaped only for `list`, call it as-is — a wrapper, not a rewrite.) **Confirm the helper's actual return signature/sentinel where step 3 lands it** — step 3's detail only describes the "skip" outcome inside `list`'s loop and does not pin a return shape, so do **not** assume a kind-or-`None` value. Read what `_classify_workspace_kind` returns (e.g. a kind enum/string, a `(kind, branch)` tuple, a record, or `None`/a sentinel on the skip case) and branch on that exact shape in the remove/prune handlers below; the unrecognized-target and delete-by-kind arms must key off whatever step 3 returns, not a presumed signature.
- **The `-y/--yes` flag is built locally per module** (the project convention — see `plan_tool/cli/manifest.py`, `plan_tool/cli/checkpoints.py`, `plan_tool/cli/bench_cmd.py`, each minting its own parent). Do not import a shared parent; mint `worktree`'s own. Folding the repo's many local `-y` parents into one shared parser is a standing deferred reconcile item, not this step's work.

### `plan_tool/cli/worktree_cmd.py` — import additions

- **Extend the existing step-1 gitcommit import** to add `worktree_remove`, `worktree_prune` (already in `gitcommit.py` from step 1): `from plan_tool.cli.gitcommit import (... worktree_remove, worktree_prune ...)`.
- **Extend the step-2 worktree import** to add `worktree_base`: `from plan_tool.worktree import (... worktree_base ...)` — needed to scope prune's discovery to plan-tool-provisioned worktrees (base path), not every worktree of the repo.
- **Extend step 3's style import** to add `warn`: `from plan_tool.style import info, error, success, warn` — prune's dead-but-dirty surfacing prints a `warn(...)` line.
- **Add `import sys`** (`_confirm` calls `sys.stdin.isatty()`; step 3 does not import it); reuse the in-body `import builtins` (mirror `manifest.py`'s confirm idiom). (No `import shutil` — clones are never deleted by plan-tool, so there is no `rmtree`.)

### `cmd_worktree(args)` — extend the dispatcher

- **Add two arms** to the `args.action` dispatch: `"remove"` → `_cmd_worktree_remove(args)`, `"prune"` → `_cmd_worktree_prune(args)`. Return the verb handler's exit code, exactly like the existing `add`/`list` arms.

### `_dirty_gate(target, *, force) -> str | None` — the shared clean-tree check

- **Return `None` when it is safe to delete:** either `force` is true, or `working_tree_dirty(target)` is false.
- **Return a one-line refusal message** (a non-empty `str`) when `working_tree_dirty(target)` is true and not `force` — e.g. `f"{target} has uncommitted changes; re-run with --force to delete it."`. The caller decides whether a non-None result is a hard error (`remove`) or a skip-and-surface (`prune`).
- **Single source for both verbs** so the dirty policy can't drift between `remove` and `prune`.

### `_inside_target(target, repo_root) -> bool` — the standing-in-the-workspace guard

- **Return true when the current working directory is `target` or any descendant of it** — compare `Path.cwd().resolve()` against `target.resolve()` (equality or `is_relative_to`). git refuses to remove a worktree you are inside or the main working tree; detecting it up front lets the handler print a clean message instead of git's raw `fatal:` text.
- **Also true when `target.resolve() == repo_root.resolve()`** (defensive — a misconfigured base could resolve onto the main tree). Treat that as "refuse, you're targeting the main tree." `repo_root` is threaded in by the caller (`ctx.repo_root`) because a one-arg helper has no `ctx` in scope.

### `_confirm(prompt, *, yes) -> bool` — the destructive confirmation

- **Mirror `plan_tool/cli/manifest.py`'s `_prompt_remove_missing` idiom exactly:**
  - `yes` is true → return `True` (no prompt).
  - not a TTY (`not sys.stdin.isatty()`) and not `yes` → print a hint to stderr (`re-run with -y to proceed`) and return `False` — an unattended run never silently deletes.
  - interactive TTY → `builtins.input(f"{prompt} [y/N]: ")`, return true only on `y`/`yes`; catch `EOFError`/`KeyboardInterrupt` → print "cancelled" and return `False`.
- **One helper for both verbs.** Local to this module (not imported from `manifest.py`).

### `_cmd_worktree_remove(args)` — delete one named plan's workspace

- **Resolve inputs:** `ctx = _load_context(args)`; `path = resolve_plan_for_context(ctx, args.name)`; `slug = slug_from_filename(path)`; `target = derive_worktree_path(ctx.repo_root, slug)`.
- **No workspace at `target`** (gate on `classify_target(target) == TargetState.ABSENT`, the same step-3 helper that filters absence upstream of `_classify_workspace_kind`) → print an informational `info(...)` line ("no workspace for <plan> at <target>") and return 0. Removing a non-existent workspace is a successful no-op (idempotent), not a failure.
- **Find the workspace and its kind:** build `wt_by_path = {Path(e.path).resolve(): e for e in worktree_list(ctx.repo_root)}` and call step 3's `_classify_workspace_kind(target, wt_by_path)`. Absence is already excluded above, so the result is `worktree`, `clone`, or step 3's third "not a recognized workspace; skip" outcome (a non-ABSENT EMPTY / foreign-NON_EMPTY / NOT_A_DIR target).
- **Unrecognized (non-workspace) target → fail clearly, never delete:** when `_classify_workspace_kind` returns its skip/unrecognized result (no `worktree`/`clone` kind), `error(...)` ("the path at <target> is not a plan-tool workspace; refusing to remove it") and return non-zero. This guards against an unset `kind` reaching the delete arms and reporting a phantom success on a foreign/broken dir.
- **Clone → short-circuit to a manual-cleanup message (never delete), *before* the gate/confirm:** when the kind is `clone`, `warn(f"{target} is a --clone workspace (an independent repo); plan-tool won't delete it. After confirming no unmerged commits, remove it by hand: rm -rf {target}")` and return 0. A clone's commits live only in its own `.git` (objects not shared), and the uncommitted-only dirty gate can't see committed-but-unmerged work, so deleting could destroy the sole copy — hence plan-tool surfaces, never deletes. This returns *before* `_inside_target` / `_dirty_gate` / confirm, which exist only for the worktree delete path below.
- **Refuse when standing inside the target:** `_inside_target(target, ctx.repo_root)` true → `error(...)` ("cannot remove the workspace you are inside; cd elsewhere first") and return non-zero. Do this before shelling out so the operator sees a clean message.
- **Clean-tree gate:** `msg = _dirty_gate(target, force=args.force)`; if `msg is not None` → `error(msg)` and return non-zero (hard stop for `remove`).
- **Confirm:** `_confirm(f"Remove {kind} workspace for {slug} at {target}?", yes=args.yes)` false → print "kept" and return 0 (declined, nothing deleted, not an error).
- **Delete the worktree** (only reachable for a worktree — clones short-circuited above): `rc, tail = worktree_remove(ctx.repo_root, target, force=args.force)`; on non-zero `rc` → `error(tail)` and return the rc.
- **Branch is not deleted** — the workspace dir is removed; the branch born inside the `add` stays (plan Out of scope: "remove/prune delete the working tree but not the branch"). State this in the success message if helpful ("branch <b> left in place").
- **On success:** `success(f"removed {kind} workspace for {slug}")` and return 0.

### `_cmd_worktree_prune(args)` — sweep dead plan-tool workspaces

- **Resolve inputs:** `ctx = _load_context(args)` (no positional plan — prune sweeps the whole repo).
- **Discover candidate worktrees via git's own worktree registry** (`worktree_list` — `git worktree list --porcelain`), scoped to plan-tool's base. **Worktrees only** — clones are out of prune's scope (see below):
  - `base = worktree_base(ctx.repo_root).resolve()`.
  - `registered = {derive_worktree_path(ctx.repo_root, e.slug).resolve(): e for e in ctx.entries}` — live registered plans' workspace paths → entries.
  - From `worktree_list(ctx.repo_root)`, keep entries whose path is **under `base`** and matches the deterministic derived-path scheme (the dir name round-trips through `derive_worktree_path(...)`), so an operator's *unrelated* worktree is never a candidate.
  - A candidate is **dead** when no live registered plan owns its path (`target not in registered`) **or** the owning plan's `.md` is missing on disk — i.e. **deregistered / plan-file-missing**. This is safe to automate because removing a worktree is non-destructive (shared object store; only the branch ref is orphaned, recoverable).
- **Clear git admin for path-gone worktrees:** call `worktree_prune(ctx.repo_root)` (git's own admin GC) so worktrees whose directory was deleted by hand stop lingering in the registry. This deletes nothing on disk (the dir is already gone), so no dirty gate applies to it.
- **Apply the clean-tree gate per surviving on-disk candidate** (dir still exists):
  - `working_tree_dirty(target)` true → **surface, do not delete**: print a `warn(...)` line ("dead-but-dirty workspace at <target>; use `plan-tool worktree remove <plan> --force` to delete") and skip it — **even under `-y`**. This is the rule that keeps prune from being a data-loss backdoor.
  - clean → add to the deletion list.
- **Confirm once for the whole batch:** if the clean deletion list is non-empty, `_confirm(f"Prune {n} dead workspace(s)?", yes=args.yes)`; declined → print "kept" and return 0.
- **Delete confirmed worktrees** via `worktree_remove(ctx.repo_root, target, force=False)` (the dirty ones were already surfaced-and-skipped above). Report each removed path; a failure on one is reported and the rest proceed (best-effort, matching `manifest.py`'s per-entry posture). (No clone deletion — clones are out of prune's scope.)
- **Empty case:** no dead candidates → print "no dead workspaces to prune" and return 0.
- **Always returns 0 on completion** (non-zero only on a genuine failure-to-complete) and never spends Claude.

### Why prune covers worktrees only — clones are entirely out of scope

- **Clones are never swept by `prune`** — two independent reasons: (1) **safety** — a clone is an independent repo whose commits live only in its own `.git`, and the uncommitted-only dirty gate can't see committed-but-unmerged work, so auto-`rm -rf` risks destroying the sole copy; (2) **discrimination** — a clone carries no plan-tool provenance marker, so *no* scan can safely tell a dead plan-tool clone from an operator's unrelated repo parked under `worktree_base`. Worktrees avoid both: git's registry is authoritative (no path-scan needed, no foreign-repo confusion) and removal is non-destructive (shared object store). So `prune` is worktree-only; clones are visible via `list` and deleted by the operator's manual `rm -rf` (Out of scope: "No auto-deletion of clones"). No per-workspace registry is added — that would violate the plan's no-extra-state tenet.

### `register(subparsers)` — add the two sub-parsers

- **Mint a local `-y/--yes` parent** in this module (copy the `manifest.py` / `checkpoints.py` shape): an `ArgumentParser(add_help=False)` with `-y`/`--yes` (`action="store_true"`, `dest="yes"`, default `False`). Step 3's `register` had no confirm parent; this step adds it.
- **`remove` verb:** `p_remove = sub.add_parser("remove", parents=[yes_parent], help="delete a plan's workspace (clean-tree gated; --force to override)")`; positional `name`; `--force` (`action="store_true"`, `dest="force"`, default `False`).
- **`prune` verb:** `p_prune = sub.add_parser("prune", parents=[yes_parent], help="sweep dead (deregistered/path-gone) worktrees; dirty ones are surfaced, not deleted")`; no positional, no `--force` (force-deleting a dirty workspace via prune is exactly what must not be possible — the operator uses `remove --force`).
- **`add`/`list` stay unchanged** — they remain non-destructive and keep no confirm parent.
- **`register` still returns `{"worktree": cmd_worktree}`** — one group handler; the four verbs are internal arms of `cmd_worktree`.

## Tests

Add to `tests/cli/test_worktree_cmd.py`. Drive real `git` against a `tmp_path` repo (reuse the step-3 / `tests/cli/test_gitcommit.py` repo-init helper style; no `claude`). Exercise verbs through `cmd_worktree` with a built `argparse.Namespace`; point `worktree_base` under `tmp_path` via config or the default writable sibling base. Provision a workspace with `add` first where a target is needed.

`TestWorktreeRemove`:
- `test_remove_clean_worktree_succeeds` — after `add`, `remove` (no `--force`, `-y`) deletes the worktree dir and returns 0.
- `test_remove_dirty_refused_without_force` — an uncommitted change in the workspace → `remove` returns non-zero with a clear "uncommitted changes" message; dir still exists.
- `test_remove_dirty_succeeds_with_force` — same dirty workspace + `--force` → rc 0, dir gone.
- `test_remove_clone_surfaces_manual_cleanup_not_deleted` — a `--clone` workspace: `remove` prints the manual-cleanup message and returns 0, and the clone dir **still exists** (plan-tool never deletes a clone). Assert the dir survives for both a clean and a dirty clone, and that `--force` does **not** change this (clones are never deleted).
- `test_remove_missing_workspace_is_noop` — `remove` for a plan with no provisioned workspace prints an info line and returns 0.
- `test_remove_from_inside_target_clean_message` — with cwd inside the target, `remove` returns non-zero with a clean message (not git's raw `fatal:`).
- `test_remove_leaves_branch` — after `remove`, the branch created inside the `add` still exists in the repo.

`TestWorktreePrune`:
- `test_prune_removes_deregistered_worktree` — provision a worktree, deregister its plan (drop from the manifest), then `prune -y` deletes that now-orphaned worktree; rc 0.
- `test_prune_keeps_registered_worktree` — a live registered plan's worktree is never pruned.
- `test_prune_never_touches_clone` — provision a `--clone` workspace under `worktree_base` and deregister its plan; `prune -y` leaves the clone dir **fully intact** (prune is worktree-registry-based and ignores clones entirely — no path-scan, no clone deletion).
- `test_prune_discovers_via_worktree_registry_not_path_scan` — prune's candidates come from `worktree_list` scoped to `worktree_base`; a non-worktree dir parked under `worktree_base` (e.g. a plain directory or an operator's unrelated repo) is never a prune candidate.
- `test_prune_surfaces_dirty_not_deletes_even_with_yes` — a dead-but-dirty workspace under `-y` is reported (warn line) and left on disk; rc 0.
- `test_prune_path_gone_clears_admin` — after `rm -rf` of a worktree dir, `prune` runs `git worktree prune` so the entry disappears from `worktree_list`.
- `test_prune_empty_when_nothing_dead` — no dead workspaces → "no dead workspaces" line, rc 0.

`TestRemovePruneConfirmGate`:
- `test_remove_declined_at_tty_keeps_workspace` — interactive `input` returning "n" leaves the workspace; rc 0.
- `test_prune_non_tty_without_yes_declines` — non-TTY without `-y` prints the hint and deletes nothing; rc 0.
- `test_yes_bypasses_prompt` — `-y` deletes without calling `input`.

`TestWorktreeWiring` (extend step 3's class):
- `test_remove_and_prune_dispatch` — `plan-tool worktree remove`/`worktree prune` reach their handlers via `cmd_worktree`'s action dispatch.

The regenerated `docs/cli/worktree.md` (now listing `remove`/`prune` + `--force`/`-y`) is covered by `tests/cli/test_cli_reference.py` once regenerated — no new assertion needed there.

### Test-creation order (feature step)

- This is a **feature** step (new behavior). Write each test class **with** the code it covers, in order: the shared `_dirty_gate` / `_confirm` helpers → `remove` → `prune` → confirm-gate → wiring.
- **Green-before-done gate:** every new test in `tests/cli/test_worktree_cmd.py` plus the regenerated `tests/cli/test_cli_reference.py` must pass, and the full suite must stay green, before this step is finished. No verb ships without its covering test green.

## Acceptance criteria

- `plan-tool worktree remove <plan>` deletes a clean **worktree** (via `git worktree remove`) and returns 0, leaving the branch in place; on a **clone** it never deletes — prints a manual-cleanup message and returns 0 (the clone dir remains).
- `plan-tool worktree remove <plan>` on a dirty workspace returns non-zero with a clear "uncommitted changes; re-run with --force" message and deletes nothing; `--force` deletes it (rc 0).
- `plan-tool worktree remove <plan>` run from a cwd inside the target (or against the main tree) returns non-zero with a clean message, not git's raw `fatal:` text.
- `plan-tool worktree remove <plan>` for a plan with no workspace prints an info line and returns 0 (idempotent no-op).
- `plan-tool worktree prune` deletes deregistered, plan-tool-provisioned worktrees (discovered via `worktree_list` scoped to `worktree_base`, never a path-scan) after confirmation/`-y`, and runs `git worktree prune` to clear admin for path-gone worktrees. **Clones are never pruned** (out of scope — visible via `list`, deleted manually).
- `plan-tool worktree prune -y` leaves a dead-but-dirty workspace on disk and surfaces it for `remove --force` — it is never blanket-deleted.
- A non-TTY run of either verb without `-y` deletes nothing and prints a hint; `-y` bypasses the prompt.
- Both verbs return 0 on completion (non-zero only on failure-to-complete); the regenerated `docs/cli/worktree.md` matches `python -m plan_tool.cli_reference --write` (drift guard green).

## References

- [git-worktree Documentation](https://git-scm.com/docs/git-worktree) — `git worktree remove [--force]` (its dirty-tree and "cannot remove current/main worktree" refusals) and `git worktree prune` (admin GC for worktrees whose directory is gone), the two primitives this step gates.
- [git-rev-parse Documentation](https://git-scm.com/docs/git-rev-parse) — `--show-toplevel` and path resolution, backing the `_inside_target` cwd-inside-workspace guard.

## Deferred

- **Branch deletion on remove/prune** — out of scope by plan decision (plan Out of scope: "remove/prune delete the working tree but not the branch"). Branch cleanup stays the normal `git branch -d` flow; a future increment could offer an opt-in `--delete-branch`.
- **Auto-deletion of clones (any path)** — out of scope by plan decision (Out of scope: "No auto-deletion of clones"). `remove` surfaces a manual-cleanup message and `prune` ignores clones entirely (independent repos: possible unmerged-commit loss + no provenance marker to distinguish from an operator's repo). Clone teardown is the operator's `rm -rf` after confirming no unmerged work; `list` keeps them visible. A future increment could add a guarded clone-removal (e.g. refuse unless fully merged), but it's not this step's teardown.
- **The write-prerequisite warning on `add`** (inspecting the base commit's tree for the plan `.md` + manifest entry) — step 3's deferred item, needs a new git-read-at-ref primitive in `gitcommit.py`; unrelated to teardown.
- **Consolidating the repo's many local `-y/--yes` parents and the `_confirm` idiom into one shared helper** — a cross-module behavior-preserving refactor `detail` can't mint; route to reconcile. This step adds the fourth-or-later local copy, per the established convention.
- **Sharing `prune`'s "dead worktree" discovery with any future workspace-GC surface** — single-use here; fold to one builder only if a sibling appears (reconcile refactor).
- **Operator docs** for `remove`/`prune`, the dirty-gate behavior, and the custom-path-clone cleanup limit — step 5 (non-code).
