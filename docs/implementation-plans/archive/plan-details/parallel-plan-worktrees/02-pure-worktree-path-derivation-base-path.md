> **Auto-archived**: this plan was swept on 2026-07-05 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 2 — Add pure worktree path derivation + base-path resolution

## Summary

Add a new stdlib-plus-`project_config` leaf module `plan_tool/worktree.py` that answers three pure questions for the worktree command group, with no git shell-out: *where is the worktree base?* (`worktree_base`), *what path does a plan's slug map to?* (`derive_worktree_path`), and *what is sitting at that path right now?* (`classify_target`). The base resolves project config → user config → a default sibling of the repo (`<repo-parent>/<repo-name>.worktrees`), never inside the repo. The per-slug path is `base / slug`, derived deterministically so `list`/`remove`/`prune` can recompute it without stored state. Target validation is a pure filesystem classifier (`absent` / `empty` / `non-empty` / `not-a-dir`) — the git-aware "is this a healthy reusable worktree" decision stays in step 3. On green, every function is callable against a `tmp_path` and its unit tests pass; no CLI wiring yet (step 3).

## Table of Contents

- [Why](#why) — what this step unblocks and why it's a pure leaf
- [Files (creates vs edits)](#files-creates-vs-edits) — the two new files
- [Implementation](#implementation) — the base resolver, path derivation, and target classifier
- [Tests](#tests) — unit cases against `tmp_path`
- [Test-creation order (feature step)](#test-creation-order-feature-step) — write-with-implementation, green-before-done gate
- [Acceptance criteria](#acceptance-criteria) — observable behaviors a reviewer can check
- [References](#references) — git-config / git-worktree docs for the base/path conventions
- [Deferred](#deferred) — what steps 3/4 own and the shared-reader consolidation

## Why

- **Step 3's `worktree add`/`list`/`remove`/`prune` need a deterministic per-plan path with no extra bookkeeping.** The plan's "no extra state" tenet means `list`/`remove`/`prune` must recompute a plan's workspace path from its slug alone — there is no registry to look it up in. That derivation, plus the configurable base it hangs off, doesn't exist yet.
- **Keep resolution pure and git-free so it's trivially testable and reusable.** The path/base math has no reason to shell out to git; isolating it in a leaf lets step 3's command module import it without dragging git calls into unit tests, and keeps the impure kind-dispatch / reuse-vs-fail decision (which needs `worktree_list`) in step 3 where it belongs.
- **The default base must be a sibling, never inside the repo.** A worktree provisioned inside the main working tree pollutes the tree and confuses git; this step encodes that rule (default sibling + a guard that rejects a configured base resolving inside the repo).

## Files (creates vs edits)

- **New files:**
  - `plan_tool/worktree.py` — the pure leaf: `WORKTREE_BASE_KEY`, `default_worktree_base`, `worktree_base`, `derive_worktree_path`, `TargetState`, `classify_target` (+ private `_read_worktree_base`, `_validate_slug`, `_base_inside_repo` helpers).
  - `tests/test_worktree.py` — one test class per public function, driving real `tmp_path` dirs and config files (no git, no `claude`).
- **Existing files (edits only):** none. This step adds no CLI wiring and edits no existing module. (`plan_tool/cli/gitcommit.py` from step 1 is **not** touched — this module never shells out.)

## Implementation

`plan_tool/worktree.py` is a **cycle-free leaf**: it imports only stdlib (`enum`, `json`, `sys`, `pathlib.Path`, `typing`) plus the two public config-path helpers from `plan_tool/project_config.py`. It calls no git, reads no plan files, and takes `repo_root` / `slug` as parameters (never resolves them itself) so it stays hermetic against a `tmp_path`. It sits **below** step 3's `plan_tool/cli/worktree_cmd.py`, which imports it.

### Config-path reuse

- **Reuse `plan_tool/project_config.py`'s `project_config_path(repo_root)` and `user_config_path()`** as the single source for the `.plan-tool/config.json` (project) and `~/.plan-tool/config.json` (user) locations. Do **not** re-derive those paths — importing the existing public helpers keeps one source for the config-file layout, which is exactly the "reuse `project_config.py`" the plan's scope line (`Path/config resolution`) calls for.
- **`user_config_path()` evaluates `Path.home()` in-body**, so the user-level tests can patch `$HOME` / `Path.home()` per test. Don't cache `user_config_path()`'s result at module level — call it per resolution so the patched home takes effect.

### `default_worktree_base(repo_root: Path) -> Path`

- **Return `<repo-parent>/<repo-name>.worktrees`** — a sibling directory of the repo. For a repo at `/home/u/plan-tool`, this is `/home/u/plan-tool.worktrees`.
- Resolve `repo_root` first (`repo_root.resolve()`) so `.name` and `.parent` are stable regardless of how the caller passed the root.
- This default is structurally never inside the repo, so it always passes the inside-repo guard below.

### `worktree_base(repo_root: Path) -> Path`

- **Resolve precedence: project config → user config → `default_worktree_base(repo_root)`.** Mirror `project_config.py`'s `branch_prefixes` / `validation_machinery_paths` accessor *layering* (project → user → default), but **fall through to the next level on a present-but-invalid value** — not the same invalid-value handling: `branch_prefixes` short-circuits straight to the default (with a warn-once) when the project value is present-but-invalid, whereas a present-but-invalid project base here falls through to the user level (and only then the default), per the "Per-level tolerance" bullet below. **No env axis** (the base is a repo/user setting, not a per-invocation toggle) — matching `branch_prefixes`, which also has no env axis.
- **Per-level tolerance, never raises.** A malformed config file (absent, bad JSON, top-level not a dict, key missing, value not a non-empty `str`) is treated as "level unset" and falls through silently to the next level — the same posture as `project_config.py:_read_level`. Because `_read_worktree_base` collapses a present-but-invalid value into `None` (indistinguishable from key-absent), there is no warn-once branch here; an all-levels-unset/invalid state simply yields the default without raising. (Only the inside-repo guard below warns, since it acts on a *valid* string that resolves to a forbidden location.)
- **Normalize a configured base:** `Path(raw).expanduser()`; if the result is relative, resolve it against `repo_root.parent` (the sibling neighborhood the default lives in), then `.resolve()`.
- **Inside-repo guard:** if a configured base resolves to `repo_root` itself or anywhere under it (`_base_inside_repo`), warn to stderr and return `default_worktree_base(repo_root)` instead. A worktree under the main tree corrupts it; refuse the misconfiguration tolerantly rather than honoring it. **An inside-repo base goes straight to the default — it does not fall through to the next level:** a valid-but-inside-repo *project* base returns the default even when a valid *user* base exists, because the guard fires on the resolved location of the level that supplied the value, not on validity (contrast the present-but-invalid fall-through above, where an unparseable project value collapses to `None` and the user level is consulted).

### `_read_worktree_base(path: Path) -> Optional[str]`

- **Read one config file and return the raw `worktree_base` string, or `None`.** Return `None` on: file absent, `OSError`, `json.JSONDecodeError`, top-level value not a `dict`, `worktree_base` missing, or value not a non-empty `str`. Never raises. This is the worktree analog of `project_config.py:_read_level` — keyed on the top-level `worktree_base` key (see Deferred for why it's a fresh reader, not a shared one).
- `WORKTREE_BASE_KEY = "worktree_base"` — the JSON key, exported as a module constant so step 3 / docs / tests reference one name.

### `derive_worktree_path(repo_root: Path, slug: str, *, base: Optional[Path] = None) -> Path`

- **Return `base / slug`**, where `base` defaults to `worktree_base(repo_root)` when not supplied. Deterministic: same `(repo_root, slug, base)` always yields the same path, so step 3's `list`/`remove`/`prune` recompute it with no stored state.
- **The optional `base` keyword** lets step 3 pass an already-resolved base (e.g. from a `--base`/flag) without re-reading config, and keeps the function a pure function of its inputs for testing.
- **Validate the slug** via `_validate_slug(slug)` before joining — the slug becomes a path segment, so a slug containing a path separator, `..`, a leading/trailing whitespace-only value, or empty string could escape the base directory. Raise `ValueError` with a clear message on any of these. Although callers derive the slug from `plan_tool/locator.py:slug_from_filename` (a file stem that normally can't contain `/`), this guard is the path-safety boundary and is cheap.

### `TargetState` + `classify_target(path: Path) -> TargetState`

- **`TargetState`** — a `str`-valued `enum.Enum` with four members:
  - `ABSENT` — nothing exists at `path`.
  - `EMPTY` — a directory exists and has no entries.
  - `NON_EMPTY` — a directory exists and contains at least one entry.
  - `NOT_A_DIR` — something exists at `path` but is not a directory (a file or symlink-to-file).
- **`classify_target`** is the **pure** half of step 3's reuse-vs-fail tiebreak: it reports *what is on disk*, not *whether it is a healthy worktree of the expected kind/branch* (that needs `worktree_list` / a `.git` probe and lives in step 3). Keep it filesystem-only so it's git-free and unit-testable.
- Determine `EMPTY` vs `NON_EMPTY` with `any(path.iterdir())`; guard the `iterdir` against `OSError` and treat an unreadable directory as `NON_EMPTY` (fail safe — don't let step 3 overwrite a dir it can't inspect).

### Foundational logic & shared call sites

- **Foundational logic: tolerant project→user→default config resolution with per-level fallback.** This same shape already lives in `plan_tool/project_config.py` — `branch_prefixes`, `validation_machinery_paths`, and the private block readers `_read_level` / `_read_smell_block`. This step adds a **third** block reader (`_read_worktree_base`) keyed on `worktree_base` rather than reaching into `project_config`'s private branch-awareness/smell readers (they parse different keys and are not exported). `project_config.py` already documents this exact "second small reader … rather than a shared `_read_block` … deferred" decision on `_read_smell_block`; this is the third instance and strengthens the case for one shared reader — routed to Deferred (a consolidation refactor `detail` can't mint).
- **The strict readers `plan_tool/backend_config.py` / `plan_tool/jira_config.py` are the opposite posture** (raise on malformed, single authoritative parse). Do **not** model `worktree_base` on them — the worktree base is a tolerant fallback like branch-awareness, so a broken user file must never crash an otherwise-fine project.

## Tests

Add to `tests/test_worktree.py`. Unit tests (unmarked, hermetic, own `tmp_path`); no git, no `claude`. Patch `$HOME` / `Path.home()` (e.g. via `monkeypatch`) for the user-level cases so `user_config_path()` points into `tmp_path`.

`TestDefaultWorktreeBase`:
- `test_default_is_repo_sibling` — `default_worktree_base(repo)` equals `<repo.parent>/<repo.name>.worktrees`.

`TestWorktreeBaseResolution`:
- `test_unconfigured_returns_default` — no config files → returns `default_worktree_base`.
- `test_project_base_overrides_default` — a project `worktree_base` string is honored.
- `test_project_overrides_user` — both levels set → project wins.
- `test_user_used_when_project_absent` — only user config set → user value used.
- `test_tilde_expanded` — `"~/wt"` resolves under the patched home, not a literal `~`.
- `test_relative_base_resolved_against_repo_parent` — a relative config value resolves against `repo.parent`.
- `test_malformed_config_falls_back_to_default` — bad JSON / non-dict top level / non-string value → default, no raise.
- `test_base_inside_repo_warns_and_falls_back` — a configured base under `repo_root` is rejected; result is the default and a warning hits stderr (capture with `capsys`).

`TestDeriveWorktreePath`:
- `test_path_is_base_slash_slug` — with config base `B`, `derive_worktree_path(repo, "my-plan")` equals `B / "my-plan"`.
- `test_explicit_base_overrides_config` — passing `base=` ignores config.
- `test_deterministic_same_slug_same_path` — two calls with the same inputs return equal paths.
- `test_rejects_traversal_slug` — slug containing `/`, `..`, empty, or whitespace-only raises `ValueError`.

`TestClassifyTarget`:
- `test_absent_path` — a non-existent path → `TargetState.ABSENT`.
- `test_empty_dir` — an empty dir → `TargetState.EMPTY`.
- `test_non_empty_dir` — a dir with one file → `TargetState.NON_EMPTY`.
- `test_file_at_path_is_not_a_dir` — a regular file at the path → `TargetState.NOT_A_DIR`.

### Test-creation order (feature step)

- This is a **feature** step (new behavior). Write each test class **with** the function it covers, in the order above (default base → resolver → path derivation → classifier).
- **Green-before-done gate:** every test in `tests/test_worktree.py` must pass (`uv run pytest tests/test_worktree.py -q`) and the rest of the suite must stay green before this step is finished. No function ships without its covering test green.

## Acceptance criteria

- `default_worktree_base(repo)` returns `<repo.parent>/<repo.name>.worktrees`.
- `worktree_base(repo)` returns the default when no config is present; a valid project value overrides it; project overrides user; a `~`-prefixed value is expanded; a relative value resolves against `repo.parent`.
- A malformed config (bad JSON, non-dict, non-string value) makes `worktree_base` return the default without raising; a base resolving inside `repo_root` is rejected (default returned + stderr warning).
- `derive_worktree_path(repo, slug)` returns `worktree_base(repo) / slug` and is deterministic; passing `base=` overrides config; a slug with a path separator / `..` / empty / whitespace-only raises `ValueError`.
- `classify_target(path)` returns `ABSENT` / `EMPTY` / `NON_EMPTY` / `NOT_A_DIR` matching the on-disk state.
- All tests in `tests/test_worktree.py` pass; the full suite stays green.

## References

- [git-worktree Documentation](https://git-scm.com/docs/git-worktree) — confirms a worktree must live outside the main working tree, motivating the default-sibling base and the inside-repo guard.
- [git-config Documentation](https://git-scm.com/docs/git-config) — context for `.plan-tool/config.json` layering (project vs user) this module reads the `worktree_base` key from; not git config itself, but the same project/user precedence model.

## Deferred

- **Git-aware reuse-vs-fail tiebreak** (healthy-workspace-on-expected-branch → reuse; broken/foreign dir → fail) — step 3; needs `worktree_list` / a `.git` probe. This step only ships the pure `classify_target` filesystem half.
- **Kind dispatch (worktree vs clone)** — step 3; `classify_target` is kind-agnostic.
- **Branch-name and start-point resolution** (`--branch` / `derive_branch` / slug fallback; default-branch HEAD else `HEAD`) — step 3's caller; not a path/config concern.
- **Clean-tree / confirmation gates on remove/prune** — step 4.
- **Consolidating the three tolerant config readers** (`project_config.py:_read_level`, `_read_smell_block`, and this module's `_read_worktree_base`) into one shared reader — a behavior-preserving refactor `detail` can't mint; route to `reconcile`. `project_config.py` already records this deferral for `_read_smell_block`. **Differing return shapes:** `_read_level` / `_read_smell_block` return a nested `dict` block (`branch_awareness` / `smell_checks`), whereas `_read_worktree_base` returns a top-level scalar `str` — so a single `_read_block(path, key)` returning a dict block wouldn't cleanly unify with the scalar reader; the consolidation must span both shapes (e.g. parameterize by expected value type) rather than assume one dict-returning signature.
- **Wiring slug resolution** (`locator.py:slug_from_filename`) — step 3 passes the slug in; this module takes it as a parameter and only validates it.
