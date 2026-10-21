> **Auto-archived**: this plan was swept on 2026-06-16 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 3 — Add `branch_binding.py`: a git-config-backed ad-hoc plan→branch override store

## Summary

Creates `plan_tool/branch_binding.py`, a stdlib-only leaf that persists the optional **ad-hoc plan→branch override** in untracked local git config (`git config --local plan-tool.binding.<slug>`). It exposes `get_binding`, `set_binding`, `clear_binding`, `all_bindings`, and `reverse_binding` — the read/write/enumerate primitives the run guard and the `attach-branch`/`detach-branch` verbs (steps 4–6) need without storing anything tracked. The load-bearing decision is the **set-loud / clear-quiet error posture**: `set_binding` raises `BranchBindingError` on empty input or any git-write failure (a desync the user must see), while `clear_binding` treats an absent binding as a satisfied no-op and returns `False` quietly (the desired end-state already holds). On green every primitive round-trips against a real `tmp_path` repo and `tests/test_branch_binding.py` covers each path. Adds `tests/test_branch_binding.py`.

## Table of Contents

- [Why](#why) — what the override store unblocks and why it's a git-config leaf
- [Files (creates vs edits)](#files-creates-vs-edits) — the two new files
- [Implementation](#implementation) — each primitive's git command, return contract, and the set-loud/clear-quiet split
- [Tests](#tests) — per-primitive unit cases and the green-before-done gate
- [Acceptance criteria](#acceptance-criteria) — observable behaviors a reviewer can check
- [References](#references) — git-config docs for the storage mechanism
- [Deferred](#deferred) — work left to consuming steps

## Why

- **The ad-hoc override needs one cycle-free home that stores nothing tracked.** The architecture derives a plan's branch from its slug and keeps the optional override out of `plans.json` and frontmatter — it lives only in untracked local git config (plan "Architecture", "Out of scope → No tracked binding"). Steps 4–6 (`branch_ownership.py`, the run guard, the `attach-branch`/`detach-branch` verbs) all need to read, write, enumerate, and reverse-look-up that override; without a leaf the `git config` calls scatter or force a cycle through `create`/`locator`.
- **`reverse_binding(B)` is half of the deliberately-separate two-lookup design.** `branch_owner(B)` (step 4) asks "who owns branch B?" and consults `reverse_binding(B)` *before* convention ownership; this module owns that branch→slug reverse map.
- **Override storage in untracked git config is what makes the binding worktree-safe and fail-safe.** It is branch-independent, lost on a machine switch (falling back to the derived name), and never diverges between two devs — the storage property the prior tracked-binding approach lacked.

## Files (creates vs edits)

- **New files:**
  - `plan_tool/branch_binding.py` — the override leaf: `BranchBindingError`, the `plan-tool.binding.<slug>` key helper, and `get_binding` / `set_binding` / `clear_binding` / `all_bindings` / `reverse_binding`.
  - `tests/test_branch_binding.py` — unit coverage for round-trip, overwrite, set-loud raises, clear-quiet idempotence, enumeration, and reverse lookup, against a `tmp_path` git repo.
- **Existing files (edits only):** none. `depends_on` is empty; this step adds no call sites and imports nothing from step 1's `plan_tool/project_config.py` or step 2's `plan_tool/cli/gitcommit.py`.

## Implementation

All work lands in `plan_tool/branch_binding.py`. Keep it a **stdlib-only leaf** — import only `subprocess`, `pathlib.Path`, and typing. Import **nothing** from `plan_tool.create`/`launcher`/`locator`/`cli.*` so `branch_ownership.py` (step 4) and the run guard (step 5) depend on it without a cycle, mirroring the leaf contract of `plan_tool/cli/gitcommit.py` (its module docstring: "imports nothing from the cli package").

### Subprocess shape and key format

- **Mirror `plan_tool/cli/gitcommit.py`'s subprocess call shape verbatim** — `subprocess.run([...], cwd=repo_root, stdin=subprocess.DEVNULL, capture_output=True, text=True)`, the shape used by `working_tree_dirty` / `commit_all` / `path_is_gitignored` and by `plan_tool/bench.py`'s `["git", "config", key, value]` call. Do **not** import `gitcommit.py`; shell `git config` directly so this stays a self-contained root leaf next to step 1's `plan_tool/project_config.py`.
- **Config key is `plan-tool.binding.<slug>`** (the title's literal form). Add one private helper `_binding_key(slug: str) -> str` returning `f"plan-tool.binding.{slug}"`. Git treats the trailing `<slug>` as the config *key name* (`plan-tool` section, `binding` subsection, `<slug>` key), which git lowercases — canonical slugs are already lowercase kebab-case (numeric prefix stripped by `plan_tool/locator.py:slug_from_filename`), so they are valid key tails. Slug/ref *validity* is step 1/step 4's concern (`project_config._is_valid_ref`); this store does not re-validate the slug shape.

### Primitives

- **`get_binding(repo_root: Path, slug: str) -> str | None`** (reader) — run `git config --local --get plan-tool.binding.<slug>`. Return `proc.stdout.strip()` on rc 0; return `None` on any non-zero rc (folds key-absent, rc 1, and non-repo, rc 128, into one `None` — the `path_is_gitignored` rc-0-is-the-only-positive posture).
- **`set_binding(repo_root: Path, slug: str, branch: str) -> None`** (mutator, **loud**) — raise `BranchBindingError` when `slug` or `branch` is empty after `.strip()`; otherwise run `git config --local plan-tool.binding.<slug> <branch>` and raise `BranchBindingError` (message including the git stderr tail) on any non-zero rc. A bad git write (including `--local` outside a work tree → rc 128) is a real failure the caller must surface, not swallow.
  - **Do not embed a registration / uniqueness / clean-tree precondition here.** Keep this a thin primitive; the "plan must be registered" and "branch not already owned by another plan" checks are the `attach-branch` handler's policy (step 6), enforced caller-side before the call — the primitive-vs-policy division. This lets both `attach-branch` and any future caller reuse the same store.
- **`clear_binding(repo_root: Path, slug: str) -> bool`** (mutator, **quiet**) — run `git config --local --unset plan-tool.binding.<slug>`. Return `True` on rc 0 (a binding existed and was removed); return `False` on any non-zero rc (no binding to unset → git rc 5, or non-repo → rc 128). Treat a missing binding as a satisfied no-op so an idempotent `detach-branch` retry never errors — never raise.
- **`all_bindings(repo_root: Path) -> dict[str, str]`** (reader) — run `git config --local --get-regexp ^plan-tool\.binding\.`. On rc 0 parse each output line (`plan-tool.binding.<slug> <branch>`) into `{slug: branch}` by splitting key from value on the first whitespace and stripping the `plan-tool.binding.` prefix off the key; return `{}` on any non-zero rc (no matches → rc 1, non-repo → rc 128).
- **`reverse_binding(repo_root: Path, branch: str) -> str | None`** (derived reader) — call `all_bindings(repo_root)` and return the slug whose bound branch equals `branch` (compare on `.strip()`); return `None` when none match. **Iterate in sorted-slug order** so the result is deterministic if the caller-enforced one-branch-per-plan invariant is ever violated. Derive `reverse_binding` from `all_bindings` (one parse path) rather than a second `git config` call, so the forward and reverse views can never disagree on which slug owns a branch.

### `BranchBindingError`

- **Define `BranchBindingError(Exception)`** at module top with a one-line docstring (e.g. "Failed to write/clear an ad-hoc branch binding in local git config."), mirroring `plan_tool/create.py:CreateError`. Only `set_binding` raises it; readers and `clear_binding` never do.

### Foundational logic / duplication scan

- **Foundational logic:** an untracked, slug-keyed plan→branch override store in local git config with a set-loud/clear-quiet posture.
- **No existing duplicate of the binding store** — `grep` for `bind_branch` / `reverse_binding` / `plan-tool.binding` returns nothing on disk; the manifest-backed `bind_branch`/`unbind_branch` named in older accumulated lessons were never implemented (this re-created plan moved the override from a manifest `{path,branch}` entry to git config).
- **The `subprocess.run([...], cwd=..., stdin=DEVNULL, capture_output=True, text=True)` shape is duplicated** across `plan_tool/cli/gitcommit.py`, `plan_tool/cli/run_cmd.py` (`_working_tree_dirty`/`_commit_green_step`), and `plan_tool/bench.py`. Consolidating that shape into one git-shell helper is a cross-module refactor `detail` cannot mint → see [Deferred](#deferred).

## Tests

All cases land in `tests/test_branch_binding.py` (unit, unmarked, fast). Add a module-local `_init_git_repo(root)` helper that runs `git init -q` + `git config user.email/user.name`, copied from `tests/cli/test_gitcommit.py:_init_git_repo` (top-level test file, so it defines its own; the git subprocess gate in `tests/conftest.py` only blocks the registered *claude*/*codex* binaries, not `git`, so no marker is needed). Enumerate the tests **with** the implementation; the green-before-done gate: every case below must pass before this step is complete.

- `test_get_binding_unset_returns_none` — `get_binding` on a fresh repo with no binding returns `None`.
- `test_set_then_get_round_trips` — after `set_binding(slug, "feat/x")`, `get_binding(slug)` returns `"feat/x"`.
- `test_set_overwrites_existing` — a second `set_binding(slug, "other")` makes `get_binding(slug)` return `"other"`.
- `test_set_empty_branch_raises` — `set_binding(slug, "")` (and whitespace-only) raises `BranchBindingError`; nothing is written.
- `test_set_empty_slug_raises` — `set_binding("", "feat/x")` raises `BranchBindingError`.
- `test_set_outside_repo_raises` — `set_binding` against a non-git `tmp_path` raises `BranchBindingError` (git `--local` rc 128 surfaces loud).
- `test_clear_existing_returns_true` — after a `set_binding`, `clear_binding(slug)` returns `True` and `get_binding(slug)` is then `None`.
- `test_clear_absent_returns_false` — `clear_binding` on a slug with no binding returns `False` and never raises (quiet no-op).
- `test_clear_is_idempotent` — calling `clear_binding(slug)` twice returns `True` then `False`.
- `test_all_bindings_empty` — `all_bindings` on a repo with no bindings returns `{}`.
- `test_all_bindings_returns_all_pairs` — after binding two slugs, `all_bindings` returns both `{slug: branch}` pairs.
- `test_reverse_binding_found` — `reverse_binding(branch)` returns the slug bound to it.
- `test_reverse_binding_not_found` — `reverse_binding` for an unbound branch returns `None`.
- `test_reverse_binding_deterministic_on_collision` — two slugs bound to the same branch → `reverse_binding` returns the sorted-first slug (defensive determinism; the one-branch-per-plan invariant is caller-enforced).

## Acceptance criteria

- `plan_tool/branch_binding.py` imports nothing from `plan_tool.create`/`launcher`/`locator`/`cli.*` (verifiable by inspection / an import-time check).
- `get_binding` returns `None` for an unset slug and the stored value after a `set_binding`.
- `set_binding` raises `BranchBindingError` on empty slug, empty branch, or a non-zero git rc (including outside a git repo); a valid call persists the value to `git config --local`.
- `clear_binding` returns `True` when it removed a binding, `False` when none existed, and never raises.
- `all_bindings` returns `{}` with no bindings and the full `{slug: branch}` map otherwise.
- `reverse_binding` returns the bound slug for a branch, `None` otherwise, deterministically.
- Every test in `tests/test_branch_binding.py` passes; the full suite (`uv run pytest -m "not integration" tests/ -q`) stays green.

## References

- [Git - git-config Documentation](https://git-scm.com/docs/git-config) — Authoritative reference for `--local`, `--get`, `--unset`, and `--get-regexp` semantics and exit codes (rc 1 key-absent, rc 5 nothing-to-unset) the primitives' return contracts rely on, and for how a dotted `section.subsection.key` name is parsed.
- [subprocess — Subprocess management (Python docs)](https://docs.python.org/3/library/subprocess.html) — Stdlib reference for the argument-list `subprocess.run` shape and return-code handling matching the tool's git-shell discipline.

## Deferred

- **Slug/ref validity beyond the git key-name constraint** — the store does not re-validate that `<slug>` or `branch` is a well-formed git ref; `plan_tool/project_config.py:_is_valid_ref` (step 1) and `branch_ownership.py` (step 4) own that, and `attach-branch` (step 6) gates on it before calling `set_binding`.
- **Registration / uniqueness / clean-tree preconditions** — enforced caller-side in the `attach-branch` handler (step 6), not in this primitive (primitive-vs-policy division).
- **Consolidating the duplicated `subprocess.run` git-shell shape** across `plan_tool/branch_binding.py`, `plan_tool/cli/gitcommit.py`, `plan_tool/cli/run_cmd.py`, and `plan_tool/bench.py` — a cross-module refactor `detail` cannot mint; route to reconcile.
- **Consumers of these primitives** — `branch_ownership.py`'s `branch_owner`/`expected_branch` (step 4), the run guard (step 5), and the `attach-branch`/`detach-branch` verbs (step 6) wire the store in; this step ships only the store and its unit tests.
