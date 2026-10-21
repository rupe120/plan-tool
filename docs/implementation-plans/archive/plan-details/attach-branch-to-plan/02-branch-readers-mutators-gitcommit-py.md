> **Auto-archived**: this plan was swept on 2026-06-16 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 2 — Add branch readers/mutators to `gitcommit.py`

## Summary

Adds five branch-aware git helpers to `plan_tool/cli/gitcommit.py` — the stdlib-only git-shell leaf — so the branch-awareness feature has one cycle-free home for every git branch read/write it needs: `current_branch`, `default_branch`, `branch_exists` (readers → `None`/`False` sentinels), and `create_and_checkout_branch` / `checkout_existing_branch` (mutators → `(rc, stderr-tail)`, never raise), plus `list_branches` (local + remote refs, no network). The load-bearing decision is **command choice by error posture**: `current_branch`/`default_branch` resolve via `git symbolic-ref`, whose native non-zero rc folds detached-HEAD and non-repo into one `None` branch with no magic-string special-casing. `default_branch` additionally honors a `PLAN_TOOL_DEFAULT_BRANCH` env override for local-only repos with no `origin/HEAD`. On green, every helper returns a deterministic value (or sentinel) against a real `tmp_path` repo and never raises, and `tests/cli/test_gitcommit.py` covers each happy path and edge.

## Table of Contents

- [Why](#why) — what these helpers unblock and why they belong in `gitcommit.py`
- [Files (creates vs edits)](#files-creates-vs-edits) — the two edited files
- [Implementation](#implementation) — each helper's git command, return contract, and edge folding
- [Tests](#tests) — per-helper unit cases and the green-before-done gate
- [Acceptance criteria](#acceptance-criteria) — observable behaviors a reviewer can check
- [References](#references) — git plumbing docs for each command used
- [Deferred](#deferred) — work left to consuming steps

## Why

The branch-awareness feature spreads git branch operations across several later steps — the run guard (`plan_tool/cli/run_cmd.py:_preflight_branch_guard`, step 5), the attach/detach manifest verbs (step 6 in the manifest module), and the create-time namespace-collision warning + disambiguated-branch creation (step 7) — and each needs to ask "what branch am I on?", "does branch X exist?", "what's the default branch?" and to create/switch branches. Without a single leaf hosting these, the logic scatters or forces a cycle through `locator`/`create`. `plan_tool/cli/gitcommit.py` is already the stdlib-only git-shell leaf (imports nothing from `plan_tool.cli`, so any command imports it cycle-free); hosting the branch helpers here keeps the convention (`working_tree_dirty`, `path_is_gitignored`, `commit_all` already live here) and gives every consumer one import.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/cli/gitcommit.py` — add `current_branch`, `default_branch`, `branch_exists`, `create_and_checkout_branch`, `checkout_existing_branch`, `list_branches`; add the `import os` the env-override read in `default_branch` needs (the module currently imports only `subprocess` and `pathlib.Path`).
  - `tests/cli/test_gitcommit.py` — add one test class per new helper, reusing the existing `_init_git_repo(root)` fixture helper.

## Implementation

All work lands in `plan_tool/cli/gitcommit.py`, following the file's two existing return contracts by helper kind: **readers** collapse every failure to a `None`/`False`/`[]` sentinel (the `path_is_gitignored` rc-0-is-the-only-positive posture); **mutators** return `(rc, stderr.strip())` and never raise (the `commit_all` posture, which lets the caller own the failure UX). Every helper uses the same `subprocess.run([...], cwd=repo_root, stdin=subprocess.DEVNULL, capture_output=True, text=True)` shape already used by `working_tree_dirty`/`commit_all`.

### Readers

- **`current_branch(repo_root: Path) -> str | None`** — run `git symbolic-ref --short HEAD`. Return `proc.stdout.strip()` on rc 0; return `None` on any non-zero rc.
  - **Choose `symbolic-ref`, not `rev-parse --abbrev-ref HEAD`.** `symbolic-ref` exits 128 on both detached HEAD *and* outside a work tree, folding both undeterminable states into the same `None` branch for free. `rev-parse --abbrev-ref HEAD` returns the literal string `"HEAD"` on detached HEAD, forcing a magic-string check. The same reader must be reused on both producer (uniqueness/write) and consumer (guard/read) sides so normalized comparisons can never diverge.

- **`default_branch(repo_root: Path) -> str | None`** — precedence:
  1. **`PLAN_TOOL_DEFAULT_BRANCH` env override.** Read via `os.environ.get`; if set and non-empty after strip, return it. This is the escape hatch for local-only repos with no `origin/HEAD`.
  2. **`git symbolic-ref --short refs/remotes/origin/HEAD`.** On rc 0, the short form is `origin/<branch>`; strip the leading `origin/` segment (split once on `/`, take the remainder) and return the bare branch name.
  3. **`None`** on any non-zero rc (no remote HEAD configured, non-repo).
  - Name the env var `PLAN_TOOL_DEFAULT_BRANCH` to match the existing `PLAN_TOOL_*` env convention (`PLAN_TOOL_BACKEND`, `PLAN_TOOL_PLANS_DIR`).

- **`branch_exists(repo_root: Path, name: str) -> bool`** — run `git show-ref --verify --quiet -- refs/heads/<name>`; return `proc.returncode == 0`. Scope to `refs/heads/` so existence means a **local** branch (what the step-5 run guard checks before `checkout_existing_branch`), not a tag or remote-tracking ref. Any non-zero rc (absent ref, non-repo) returns `False` — the rc-0-is-the-only-positive posture mirroring `path_is_gitignored`.

- **`list_branches(repo_root: Path) -> list[str]`** — run `git for-each-ref --format=%(refname:short) refs/heads refs/remotes` (no network — `for-each-ref` reads local ref storage only). On rc 0, return the non-empty stripped lines of stdout; on any non-zero rc return `[]`. Surfaces both local branches and remote-tracking refs for the step-7 namespace-collision scan. Do **not** add `--sort` or filtering here — keep the producer raw and let the caller dedupe/normalize.

### Mutators

- **`create_and_checkout_branch(repo_root: Path, name: str) -> tuple[int, str]`** — run `git switch -c <name>`; return `(proc.returncode, proc.stderr.strip())`. `switch -c` **fails when the branch already exists** — that's correct for the create-at-attach-time path — and refuses to clobber uncommitted work absent `--discard-changes`/`--merge` (neither passed), the clobber-refusal the plan's Risks lean on. Keep this a thin primitive: the "create only on a clean tree" precondition is the caller's (step 5 gates with `working_tree_dirty` before calling), so do **not** embed a clean-tree check here — both attach-branch (step 6) and the create-gate disambiguated-branch creation (step 7) must reuse this one primitive under their own gates.

- **`checkout_existing_branch(repo_root: Path, name: str) -> tuple[int, str]`** — run `git switch <name>` (plain, no `-c`); return `(proc.returncode, proc.stderr.strip())`. This is the **switch** verb, distinct from `create_and_checkout_branch`'s **create** verb: a bound branch already exists by the time the step-5 run guard wants to switch to it, so `git switch -c` would error "branch already exists". The two are different git verbs and must not be conflated; both share the `(rc, tail)` never-raise shape so the caller surfaces the failure.

### Shared-logic note

- **The `subprocess.run([...], cwd=…, stdin=DEVNULL, capture_output=True, text=True)` shape is duplicated** with `plan_tool/cli/run_cmd.py:_working_tree_dirty` / `_commit_green_step` (and step 5 will add a sibling branch preflight in `run_cmd.py`). Consolidating that shape across the `gitcommit.py`↔`run_cmd.py` seam is a cross-module refactor `detail` cannot mint → **Deferred**. Do not pull `run_cmd.py` into this step's footprint.

## Tests

All cases go in `tests/cli/test_gitcommit.py`, reusing the existing module-level `_init_git_repo(root)` helper. New tests must drive a real `tmp_path` git repo (no monkeypatching of `subprocess` — these are thin git wrappers and the value is the real git contract). To exercise a second branch, run `git checkout -b <name>` / `git branch <name>` via `subprocess.run(..., cwd=tmp_path, check=True, capture_output=True)` in the test body.

### Test-creation order (feature step)

Add these unit tests **with** the implementation; every one must be green before this step is done.

- `TestCurrentBranch`
  - `test_returns_branch_name_on_branch` — on a repo with one commit, returns the checked-out branch name (e.g. `main`/`master`; assert it equals the value `git symbolic-ref --short HEAD` reports rather than hardcoding).
  - `test_detached_head_returns_none` — after `git checkout <commit-sha>` (detached), returns `None`.
  - `test_non_repo_returns_none` — a bare `tmp_path` (no `git init`) returns `None`.
- `TestDefaultBranch`
  - `test_env_override_wins` — with `PLAN_TOOL_DEFAULT_BRANCH=release` set (via `monkeypatch.setenv`), returns `"release"` even when `origin/HEAD` resolves to something else.
  - `test_empty_env_falls_through` — `PLAN_TOOL_DEFAULT_BRANCH=""` (or whitespace) is treated as unset, falling through to symbolic-ref/`None`.
  - `test_origin_head_resolves_and_strips_prefix` — after configuring `refs/remotes/origin/HEAD` (e.g. `git symbolic-ref refs/remotes/origin/HEAD refs/remotes/origin/main`), returns `"main"` with no `origin/` prefix.
  - `test_no_origin_head_returns_none` — local-only repo with no env override and no `origin/HEAD` returns `None`.
- `TestBranchExists`
  - `test_existing_local_branch_is_true` — returns `True` for a branch created with `git branch feat`.
  - `test_absent_branch_is_false` — returns `False` for an unknown name.
  - `test_non_repo_is_false` — bare `tmp_path` returns `False`.
- `TestCreateAndCheckoutBranch`
  - `test_creates_and_switches_rc_zero` — returns `(0, "")` and `current_branch` afterward equals the new name.
  - `test_existing_branch_fails_nonzero` — calling with an already-existing branch name returns a non-zero rc and a non-empty tail (never raises).
- `TestCheckoutExistingBranch`
  - `test_switches_to_existing_rc_zero` — pre-create a branch, then `checkout_existing_branch` returns `(0, …)` and `current_branch` equals it.
  - `test_missing_branch_fails_nonzero` — switching to an absent branch returns a non-zero rc + non-empty tail (never raises).
- `TestListBranches`
  - `test_lists_local_branches` — after creating two branches, both names appear in the returned list.
  - `test_includes_remote_tracking_refs` — after wiring a fake remote-tracking ref (e.g. `git update-ref refs/remotes/origin/main HEAD`), the `origin/main` short ref appears.
  - `test_non_repo_returns_empty` — bare `tmp_path` returns `[]`.

## Acceptance criteria

- `current_branch` returns the branch name on rc 0 and `None` for detached HEAD and non-repo.
- `default_branch` returns `PLAN_TOOL_DEFAULT_BRANCH` when set non-empty; else the `origin/HEAD` branch with the `origin/` prefix stripped; else `None`.
- `branch_exists` returns `True` only for an existing `refs/heads/<name>`, `False` otherwise (including non-repo).
- `create_and_checkout_branch` returns `(0, "")` on success, non-zero `(rc, tail)` when the branch exists, and never raises.
- `checkout_existing_branch` returns `(0, …)` switching to an existing branch, non-zero `(rc, tail)` for a missing branch, and never raises.
- `list_branches` returns local + remote-tracking short ref names on rc 0 and `[]` on failure; issues no network call.
- `plan_tool/cli/gitcommit.py` remains a stdlib-only leaf — imports only `os`, `subprocess`, `pathlib.Path`, and no `plan_tool.cli.*`.
- All new tests in `tests/cli/test_gitcommit.py` pass (`uv run pytest tests/cli/test_gitcommit.py -q`).

## References

- [Git - git-symbolic-ref Documentation](https://git-scm.com/docs/git-symbolic-ref) — Resolving `HEAD` (for `current_branch`) and `refs/remotes/origin/HEAD` (for `default_branch`), and the non-zero exit on detached HEAD / non-repo that folds both into `None`.
- [Git - git-for-each-ref Documentation](https://git-scm.com/docs/git-for-each-ref) — Formatted, no-network listing of `refs/heads` and `refs/remotes`, the basis for `list_branches` and its `%(refname:short)` format.
- [Git - git-show-ref Documentation](https://git-scm.com/docs/git-show-ref) — `--verify --quiet -- refs/heads/<name>` as the existence predicate behind `branch_exists`.
- [Git - git-switch Documentation](https://git-scm.com/docs/git-switch) — `switch -c` (create) vs plain `switch` (switch), the create-vs-switch distinction between the two mutators, and its refusal to clobber uncommitted work absent `--discard-changes`/`--merge`.
- [subprocess — Subprocess management (Python docs)](https://docs.python.org/3/library/subprocess.html) — Stdlib reference for the argument-list shell-out + return-code handling shape these helpers share.

## Deferred

- **Git-backed ref-name validation (`git check-ref-format`)** — branch-name validity is enforced by the pure `plan_tool/project_config.py` predicate (step 1); a real `git check-ref-format` shell-out is not in this step's title and is deferred to wherever a caller needs it.
- **Clean-tree gating around `create_and_checkout_branch`** — the precondition is the caller's (attach-branch step 6 / create-gate step 7); this primitive stays policy-free.
- **Consolidating the `subprocess.run` shell-out shape** shared with `plan_tool/cli/run_cmd.py:_working_tree_dirty`/`_commit_green_step` — a cross-module refactor for reconcile, out of this step's footprint.
- **Remote name other than `origin`** — `default_branch` resolves only `refs/remotes/origin/HEAD`; non-`origin` defaults rely on the `PLAN_TOOL_DEFAULT_BRANCH` override. Multi-remote autodetection is a follow-up if a consumer needs it.
- **Call-site wiring** — every consumer (run guard step 5, attach/detach + `register --branch` step 6, create gate / collision scan step 7) lands in its own step; this step only adds and unit-tests the primitives.
