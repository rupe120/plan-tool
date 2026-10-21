> **Auto-archived**: this plan was swept on 2026-07-05 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 1 — Add git worktree + clone primitives to `gitcommit.py`

## Summary

Add five new git-subprocess wrappers to `plan_tool/cli/gitcommit.py` so later steps can provision and inspect isolated workspaces: `worktree_add`, `worktree_list`, `worktree_remove`, `worktree_prune`, and `clone_repo`. All mirror the module's existing subprocess style — `cwd=`, `stdin=subprocess.DEVNULL`, `capture_output=True`, `text=True`, never raise on git failure — and return either `(rc, stderr-tail)` for mutating verbs or a parsed value for the read verb. `worktree_list` parses `git worktree list --porcelain` into a small frozen `WorktreeEntry` dataclass (path + short branch + detached/bare flags). The key design rule: **branch creation/checkout happens inside the provisioning call** (`git worktree add -b`, or `git -C <clone> switch -c`), never via a main-tree `git switch -c`, because git refuses to add a worktree on a branch already checked out in the main tree. On green, every primitive is callable against a real `tmp_path` git repo and its unit tests pass; no command-group wiring yet (that is step 3).

## Table of Contents

- [Why](#why) — what this step unblocks and why it lives in `gitcommit.py`
- [Files (creates vs edits)](#files-creates-vs-edits) — the two in-scope files
- [Implementation](#implementation) — the five primitives, their signatures, and the porcelain parser
- [Tests](#tests) — per-primitive unit cases against a real `tmp_path` repo
- [Test-creation order (feature step)](#test-creation-order-feature-step) — write-with-implementation, green-before-done gate
- [Acceptance criteria](#acceptance-criteria) — observable behaviors a reviewer can check
- [References](#references) — git docs for the subcommands and porcelain format
- [Deferred](#deferred) — what later steps own (path/config, command group, kind dispatch)

## Why

The Parallel Plan Worktrees feature needs to provision a second working tree (or full clone) per plan so long-running `create`/`detail`/`run` processes stop contending on one index/branch/checkout. Every higher layer — path derivation (step 2), the `worktree` command group (step 3), and the destructive `remove`/`prune` verbs (step 4) — depends on a thin set of git-call primitives that don't exist yet. `plan_tool/cli/gitcommit.py` is the right home: it is the **stdlib-only leaf** that already owns the repo's git-subprocess plumbing (`current_branch`, `branch_exists`, `create_and_checkout_branch`, `list_branches`, …) under the same `(rc, tail)` / rc-0-is-the-only-positive conventions, so any command module can import it without an import cycle. Adding the worktree/clone calls here keeps one git-call vocabulary instead of forking a parallel one.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/cli/gitcommit.py` — add `WorktreeEntry` dataclass, `worktree_add`, `worktree_list`, `worktree_remove`, `worktree_prune`, `clone_repo`; add `from dataclasses import dataclass` to the import block.
  - `tests/cli/test_gitcommit.py` — add one test class per new primitive (driving real `git worktree`/`git clone` against `tmp_path`, reusing the existing `_init_git_repo`/`_git`/`_commit_initial` helpers).

## Implementation

All five functions follow the module's established subprocess shape — see `commit_all` and `create_and_checkout_branch` for the exact `(rc, stderr-tail)` idiom, and `branch_exists`/`list_branches` for the rc-0-is-the-only-positive read idiom. **Never raise on git failure**; fold every non-zero rc into the returned tuple/empty value so callers stay in control.

### `WorktreeEntry` dataclass

- **Add a frozen dataclass** so `worktree_list` returns typed records instead of dicts:
  - `path: str` — the absolute path git reports in the `worktree <path>` line (kept as the raw porcelain string; callers normalize/`resolve()` for comparison).
  - `branch: str | None` — short branch name with the `refs/heads/` prefix stripped; `None` when the entry is detached or bare.
  - `head: str | None` — the commit sha from the `HEAD <sha>` line; `None` when absent.
  - `detached: bool` — set when the block carries a bare `detached` line.
  - `bare: bool` — set when the block carries a bare `bare` line (the main repo can appear bare).
- **Why a dataclass, not a dict:** step 3's `list` verb dispatches on branch/path per entry; typed fields prevent key-typo drift across the two steps. Add `from dataclasses import dataclass` next to the existing `from pathlib import Path`. This is the module's first dataclass — acceptable; it stays stdlib-only.

### `worktree_add(repo_root: Path, path: Path, branch: str, *, create: bool, start_point: str) -> tuple[int, str]`

- **`create=True`** (branch does not exist yet): run `git worktree add -b <branch> <path> <start_point>` — the branch is **born inside the add**, off `start_point`.
- **`create=False`** (branch already exists): run `git worktree add <path> <branch>`.
- **`start_point` is always a real, locally-resolvable commit-ish on the `create=True` path** — the caller (step 3) resolves it to the default branch's HEAD only when `default_branch(repo_root)` returns a name **with a matching local ref**, and falls back to the repo's literal `HEAD` whenever the named default branch has no local ref (e.g. an `origin/HEAD` that points at a branch never checked out locally, or a fetch-only mirror) — not only when `default_branch` returns `None`. This primitive does **not** default or validate it; a `None`/empty or non-resolvable start-point is a caller bug. `create=False` ignores `start_point` (the existing branch is checked out as-is), so document in the docstring that the non-empty-ref requirement applies only when `create=True`.
- **Do not** create/checkout the branch in the main tree first (`create_and_checkout_branch`'s `git switch -c`): git then refuses to add a worktree on that already-checked-out branch. This is the single most important rule of the step — state it in the docstring.
- Return `(proc.returncode, proc.stderr.strip())`. The same-branch-in-two-worktrees case and the non-empty-target-dir case both surface here as a non-zero rc + git's stderr tail; the caller turns those into clean messages (step 3/4).

### `worktree_list(repo_root: Path) -> list[WorktreeEntry]`

- Run `git worktree list --porcelain`; return `[]` on any non-zero rc (non-repo, old git), matching `list_branches`'s posture.
- **Parse the porcelain stream** into blocks separated by blank lines. Per block:
  - `worktree <path>` → `path` (required; a block without it is skipped).
  - `HEAD <sha>` → `head`.
  - `branch refs/heads/<name>` → `branch` with `refs/heads/` stripped (use `str.removeprefix("refs/heads/")`).
  - bare line `detached` → `detached=True`, leave `branch=None`.
  - bare line `bare` → `bare=True`.
- The main working tree appears as the first entry; **do not filter it here** — return every block and let the caller decide (step 3 dispatches by kind). Keep the parser tolerant: ignore unknown lines (`locked`, `prunable`, …) so a future git field doesn't break the read.

### `worktree_remove(repo_root: Path, path: Path, *, force: bool) -> tuple[int, str]`

- Run `git worktree remove <path>`, appending `--force` when `force` is true.
- Return `(rc, stderr.strip())`. The clean-tree gate is **not** enforced here — git's own dirty-tree refusal surfaces as a non-zero rc, and step 4 adds the explicit pre-gate + confirmation. Keep this primitive policy-free, exactly like `create_and_checkout_branch` leaves the clean-tree precondition to the caller.

### `worktree_prune(repo_root: Path) -> tuple[int, str]`

- Run `git worktree prune` (drops admin files for worktrees whose directory is gone). Return `(rc, stderr.strip())`. No flags; step 4's prune verb layers the discovery/confirmation/dirty-surfacing policy on top.

### `clone_repo(repo_root: Path, path: Path, *, branch: str, create: bool, start_point: str) -> tuple[int, str]`

- **Two-phase**, because a clone is an independent repo with no main-tree co-checkout conflict — so the worktree `-b` rationale does **not** apply:
  1. `git clone <repo_root> <path>` (full clone of the local source). On non-zero rc, return `(rc, tail)` immediately — do not attempt the branch step.
  2. Land the branch **inside the clone**:
     - `create=True`: `git -C <path> switch -c <branch> <start_point>` (new branch off the start point).
     - `create=False`: `git -C <path> switch <branch>` (existing branch; DWIM tracks the cloned `origin/<branch>`).
- **Do not** use `git clone -b <branch>` — it fails when the branch does not yet exist in the source.
- **Signature note (deviation from the plan's rough scope line):** the plan's scope sketch wrote `clone_repo(repo, path, *, branch, start_point)`, but the new-vs-existing branch behavior it describes in the same paragraph requires a discriminator. Add the `create: bool` keyword so `clone_repo` mirrors `worktree_add`'s shape (the two provisioning primitives stay symmetric). Flag this added keyword explicitly in the PR description.
- Return `(rc, stderr.strip())` from whichever phase ran last.

### Foundational logic & shared call sites

- **Foundational logic:** the git-subprocess wrapper idiom (`cwd=repo_root`, `stdin=subprocess.DEVNULL`, `capture_output=True`, `text=True`; mutating → `(rc, tail)`, read → typed value or empty on failure). This already repeats across `working_tree_dirty`, `path_is_gitignored`, `commit_all`, `current_branch`, `default_branch`, `branch_exists`, `list_branches`, `create_and_checkout_branch`, `checkout_existing_branch` in this same file. The new functions extend the same pattern in place — no consolidation needed.
- **A sibling clean-tree check exists at `plan_tool/cli/run_cmd.py` (`_working_tree_dirty` there).** It is deliberately separate (`run`'s own `--commit` helper, per this module's docstring); do **not** route the new worktree primitives through it or fold the two. Left out of scope on purpose.

## Tests

Add to `tests/cli/test_gitcommit.py`, reusing the existing `_init_git_repo`, `_git`, and `_commit_initial` helpers. Real `git` against `tmp_path` (no `claude`), matching the file's existing branch-helper tests.

`TestWorktreeAdd`:
- `test_create_new_branch_off_start_point` — `create=True`, `start_point="HEAD"` provisions a worktree dir whose `current_branch(<wt>)` equals the new branch; rc 0, empty tail.
- `test_add_existing_branch` — pre-create a branch, then `create=False` adds a worktree checked out on it; rc 0.
- `test_same_branch_twice_refused` — adding a second worktree on a branch already checked out (main tree or another worktree) returns rc != 0 and a non-empty tail (git's same-branch refusal).
- `test_non_repo_returns_nonzero` — calling against a non-git `tmp_path` yields rc != 0, never raises.

`TestWorktreeList`:
- `test_lists_main_and_added_worktree` — after one `worktree_add`, the result contains the main entry plus the new one; the added entry's `branch` is the short name (no `refs/heads/`), `path` matches.
- `test_detached_entry_has_none_branch` — a detached worktree parses to `branch=None`, `detached=True`.
- `test_non_repo_returns_empty` — non-git `tmp_path` → `[]`.

`TestWorktreeRemove`:
- `test_removes_clean_worktree` — clean worktree removes with rc 0 and the dir is gone.
- `test_dirty_refused_without_force` — an uncommitted change in the worktree → rc != 0 without `force`.
- `test_dirty_removed_with_force` — same dirty worktree removes with rc 0 when `force=True`.

`TestWorktreePrune`:
- `test_prune_clears_deleted_worktree` — after `rm -rf` of a worktree dir, `worktree_prune` returns rc 0 and the entry disappears from `worktree_list`.

`TestCloneRepo`:
- `test_clone_creates_new_branch` — `create=True` clones the source and the clone's `current_branch` is the new branch; rc 0.
- `test_clone_switches_existing_branch` — pre-create a branch in the source, then `create=False` clones and switches to it; rc 0.
- `test_clone_bad_source_returns_nonzero` — cloning a non-git source path returns rc != 0 and never attempts the switch (no clone dir / non-zero rc), never raises.

### Test-creation order (feature step)

- This is a **feature** step (new behavior). Write each test class **with** the function it covers, in the order listed above.
- **Green-before-done gate:** every new test in `tests/cli/test_gitcommit.py` must pass (`uv run pytest tests/cli/test_gitcommit.py -q`) before this step is considered finished. No new function ships without its covering test green.

## Acceptance criteria

- `worktree_add(repo, path, "feat", create=True, start_point="HEAD")` provisions a worktree on a freshly-created `feat` branch and returns `(0, "")`; `current_branch(path)` returns `"feat"`.
- `worktree_add` on a branch already checked out elsewhere returns a non-zero rc with a non-empty stderr tail (no exception).
- `worktree_list(repo)` returns a `list[WorktreeEntry]` with short branch names (`refs/heads/` stripped), `branch=None` for detached entries, and `[]` for a non-git path.
- `worktree_remove(repo, path, force=False)` returns non-zero on a dirty worktree and `(0, "")` once `force=True`.
- `worktree_prune(repo)` returns `(0, "")` and drops a worktree whose directory was deleted.
- `clone_repo(repo, path, branch="x", create=True, start_point="HEAD")` produces a clone checked out on a new `x` branch and returns `(0, "")`; `create=False` switches to an existing branch; a bad source returns non-zero without attempting the switch.
- All new tests in `tests/cli/test_gitcommit.py` pass; the rest of the suite stays green.

## References

- [git-worktree Documentation](https://git-scm.com/docs/git-worktree) — `add -b`/`list --porcelain`/`remove`/`prune` syntax, the porcelain record format this step parses, and git's refusal to check the same branch out in two worktrees.
- [git-clone Documentation](https://git-scm.com/docs/git-clone) — local-source clone behavior backing the `--clone` path and why `git clone -b <branch>` is avoided (fails for a not-yet-existing branch).
- [git-switch Documentation](https://git-scm.com/docs/git-switch) — `switch -c <branch> <start-point>` (new branch inside the clone) vs plain `switch <branch>` (DWIM onto the cloned remote-tracking ref).
- [git-rev-parse Documentation](https://git-scm.com/docs/git-rev-parse) — `HEAD` resolution, relevant to the always-defined `start_point` the caller passes.

## Deferred

- **Per-slug path derivation and `worktree_base` config resolution** — step 2 (`plan_tool/worktree.py`); this step takes `path` as a given.
- **Start-point resolution (default-branch HEAD else `HEAD`) and branch-name resolution (`--branch` / `derive_branch` / slug fallback)** — step 3's caller; `worktree_add`/`clone_repo` consume an already-resolved `start_point` and `branch`.
- **Kind dispatch (worktree vs clone) in `list`, and filtering out the main working tree** — step 3; `worktree_list` returns every block untouched.
- **Clean-tree pre-gate, confirmation, and dirty-surfacing policy on remove/prune** — step 4; the primitives here stay policy-free and rely on git's own dirty refusal.
- **Submodule re-init** (`git submodule update --init --recursive`) — scoped out of the whole plan (see the plan's Out of scope); not added to any primitive.
- **Reusing `run_cmd.py`'s `_working_tree_dirty`** — deliberately not consolidated; it is `run`'s separate `--commit` helper.
