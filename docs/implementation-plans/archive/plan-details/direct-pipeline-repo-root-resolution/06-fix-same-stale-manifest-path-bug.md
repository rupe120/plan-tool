> **Auto-archived**: this plan was swept on 2026-08-03 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 6 — Fix the stale-manifest-path bug in register, deregister, sweep, and list

## Summary

`plan_tool/cli/manifest.py`'s `cmd_register`, `cmd_deregister`, and `cmd_sweep`, plus `plan_tool/cli/inspect.py`'s `cmd_list` (at two of its three call sites), each resolve a fallback manifest path with a bare `args.manifest or default_manifest_path()` — the same no-argument call step 1 fixes in `create.py:create_plan`, repeated at five more sites. Each of these functions already builds a `ctx = _load_context(args)` with a correctly resolved `ctx.repo_root` before hitting the buggy line, so the fix is the same one-line swap five times over: pass `ctx.repo_root` into `default_manifest_path`. The design decision worth calling out is scope discipline — don't touch the two sibling call sites in the same files that already do this correctly (`cmd_list`'s manifest-mode header print, `cmd_root`), and don't refactor the five sites into a shared helper. On green, running `register` / `deregister` / `sweep` / `list` with `--repo-root` pointed away from cwd and `--manifest` omitted reads and writes the manifest under `--repo-root`, never under cwd.

## Table of Contents

- [Why](#why) — the read/write manifest split-brain this bug causes, worst in `sweep`
- [Files (creates vs edits)](#files-creates-vs-edits) — the two in-scope source files plus their test files
- [Implementation](#implementation) — the five call sites, their downstream fan-out, and the sites to leave alone
- [Tests](#tests) — why the existing suite never caught this, and the new regression tests
- [Acceptance criteria](#acceptance-criteria) — observable behaviors to check
- [References](#references) — relevant docs
- [Deferred](#deferred) — what this step deliberately leaves out

## Why

`_load_context(args)` (`plan_tool/cli/context.py`) builds a `PlanToolContext` via `build_plan_tool_context`, which already resolves `ctx.entries` from the *correct* manifest — `plan_tool/locator.py:load_manifest_plan_paths` does `mf = manifest_path or default_manifest_path(repo_root)`, threading the resolved root through. So by the time `cmd_register`, `cmd_deregister`, or `cmd_sweep` runs, `ctx.entries` / `ctx.missing_paths` already reflect the right file. But each of these functions then computes a *second*, independent manifest-path local for its own write, using the bare `default_manifest_path()` — which walks up from cwd, not from `ctx.repo_root`. When cwd and `ctx.repo_root` diverge (the scenario this whole plan is about: a relocated `create`, or simply invoking with an explicit `--repo-root` from elsewhere), the write local names a different file than the one `ctx.entries` just came from. Concretely:

- `cmd_register` (`mf = args.manifest or default_manifest_path()`) can silently create a brand-new `.plan-tool/plans.json` under the wrong directory tree instead of appending to the manifest `ctx.entries` was built from.
- `cmd_deregister` (same shape) can read a nonexistent manifest under the wrong root and print the false-negative `not registered ...` for a plan that *is* registered — because `remove_from_manifest` just returns `False` when its target file doesn't exist.
- `cmd_sweep` (`manifest_path = args.manifest or default_manifest_path()`) is the worst case: that one wrong local threads into four downstream calls — `sweep_plans` (which both physically archives a completed plan's file *and* deregisters it via `archive_completed_plan`), `_print_sweep_report`, `_prompt_register_orphans`, and `_prompt_remove_missing`. A completed plan gets physically moved (using `ctx.entries`' correct path) but deregistered from the wrong manifest — the real manifest is left listing a path that no longer exists at its old location.
- `cmd_list`'s two bare sites are read-only, so lower stakes, but still misdirect the operator: the "manifest entry not found on disk" hint and the "no plan-tool plans registered" hint both name the wrong file for the operator to go edit.

The already-implemented signal flagging `plan_tool/cli/inspect.py`'s `register` symbol is a false positive — that's `inspect.py`'s own `register(subparsers)` function that wires the `list`/`root`/`status`/`validate` subparsers, unrelated to the `cmd_register` manifest-mutation bug (which lives in `manifest.py`, not `inspect.py`). This step is not already done.

Two sibling call sites in the same two files already do this correctly and are the shape to copy: `cmd_list`'s manifest-mode header (`mf = args.manifest or default_manifest_path(ctx.repo_root)`) and `cmd_root` (`default_manifest_path(root)`, using its own resolved `root` local). Step 1 (`depends_on: 1`) fixes the identical single-line shape at its one call site in `create.py:create_plan`; this step closes the remaining five call sites of the same pattern.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/cli/manifest.py` — three call sites, each a one-line change from `default_manifest_path()` to `default_manifest_path(ctx.repo_root)`: `cmd_register`'s `mf = args.manifest or default_manifest_path()`, `cmd_deregister`'s identical line, and `cmd_sweep`'s `manifest_path = args.manifest or default_manifest_path()`.
  - `plan_tool/cli/inspect.py` — two call sites inside `cmd_list`, both changed the same way: the `if ctx.missing_paths:` warning block's `manifest = args.manifest or default_manifest_path()`, and the `if not ctx.entries:` empty-manifest block's `mf = args.manifest or default_manifest_path()`.
  - `tests/cli/test_manifest_cmds.py` — add regression tests for the three `manifest.py` sites.
  - `tests/cli/test_inspect_cmds.py` — add regression tests for the two `inspect.py` sites.

## Implementation

- **Foundational logic:** resolving an unset `args.manifest` via `default_manifest_path`, reusing the already-loaded `ctx.repo_root` instead of an independent cwd walk. Same shape as step 1's fix, repeated at five sibling sites in two files.
- Each site is a one-line change — swap the bare `default_manifest_path()` call for `default_manifest_path(ctx.repo_root)`. `ctx` is already built by `_load_context(args)` at the top of each of these functions/blocks, so nothing new needs to be threaded in — just use what's already in scope, the same way `cmd_list`'s third call site and `cmd_root` already do.
- Downstream fan-out per site — confirms no other call needs to change, since each already reads from the corrected local:
  - `cmd_register`: `mf` flows only into `append_to_manifest(mf, ctx.repo_root, target)`.
  - `cmd_deregister`: `mf` flows only into `remove_from_manifest(mf, ctx.repo_root, target)`.
  - `cmd_sweep`: `manifest_path` flows into `sweep_plans(..., manifest_path=manifest_path, ...)`, `_print_sweep_report(..., manifest_path=manifest_path, ...)`, `_prompt_register_orphans(..., manifest_path=manifest_path, ...)`, and `_prompt_remove_missing(..., manifest_path=manifest_path, ...)` — fixing the one assignment fixes all four call sites at once.
  - `cmd_list`'s two sites are display-only: each local is interpolated into a hint string (stderr for the missing-entries warning, stdout for the empty-manifest message) and never flows into a write.
- **Leave alone:** `cmd_list`'s third call site (the "registered in manifest:" header, already `default_manifest_path(ctx.repo_root)`) and `cmd_root`'s call site (already `default_manifest_path(root)`) — both are already correct and are the precedent to match, not additional instances of the bug.
- **Leave alone:** `cmd_attach_branch` / `cmd_detach_branch` in `manifest.py`, and `cmd_status` / `cmd_validate` in `inspect.py` — none of these call `default_manifest_path` at all, so there's nothing to change there.
- Constraint: keep the exact call shape used by the two already-correct sibling sites (`default_manifest_path(ctx.repo_root)`) rather than inventing a different spelling — a reader scanning the file should see one consistent pattern, not two "correct" variants.

## Tests

The existing suite never exercises the buggy branch, for the same reason step 1's suite didn't: every helper that drives these commands pins `--manifest` explicitly. `tests/cli/conftest.py`'s `CliRepo.argv(...)` (used by `tmp_repo` / `registered_plan`, and by `tests/cli/test_manifest_cmds.py`'s own `_ctx` helper) always appends `--manifest <path>` alongside `--repo-root`, and every legacy `tests/test_cli.py` register/deregister test (`test_register_by_path_succeeds`, `test_register_is_idempotent`, `test_deregister_by_path_removes_entry_keeps_file`, etc.) does the same. With `args.manifest` always set, `args.manifest or default_manifest_path()` never falls through to the buggy call. New tests must omit `--manifest` *and* set up a `repo_root` that genuinely differs from cwd — not just drop `--manifest` while cwd happens to equal repo_root, which would pass by coincidence rather than proving the fix.

### Test-creation order (feature step)

Add each test next to the site it covers. Every one needs two distinct `.git`-rooted directories (one used as `--repo-root`, a separate one as the ambient cwd via `monkeypatch.chdir`) and omits `--manifest` from argv, so `main([...])` is built by hand rather than via `CliRepo.argv(...)` / `tmp_repo.argv(...)`.

- `test_manifest_lands_under_repo_root_not_cwd` (`tests/cli/test_manifest_cmds.py`, `cmd_register`) — two-root setup, chdir into the unrelated directory, run `main(["--repo-root", str(repo_root), "register", str(plan_path)])`, assert the manifest is created at `repo_root/.plan-tool/plans.json` containing the new entry, and assert no `.plan-tool/plans.json` was created under the chdir'd directory.
- `test_deregister_reads_repo_root_manifest_not_cwd` (`tests/cli/test_manifest_cmds.py`, `cmd_deregister`) — same two-root setup, pre-register a plan directly into `repo_root/.plan-tool/plans.json`, chdir elsewhere, run `deregister` with `--manifest` omitted, and assert it prints `deregistered ...` (not the false-negative `not registered ...`) and the entry is actually removed from `repo_root`'s manifest.
- `test_sweep_archives_and_deregisters_under_repo_root_not_cwd` (`tests/cli/test_manifest_cmds.py`, `cmd_sweep`) — same two-root setup, register a plan with `status: completed` and its one step `done`, chdir elsewhere, run `sweep` with `--manifest` omitted, and assert the plan file is archived *and* removed from `repo_root`'s manifest (not left dangling there while an unrelated manifest absorbs the deregistration).
- `test_missing_entry_warning_names_repo_root_manifest` (`tests/cli/test_inspect_cmds.py`, `cmd_list`) — two-root setup with a manifest entry pointing at a nonexistent file, chdir elsewhere, run `list` with `--manifest` omitted, and assert the stderr hint names `repo_root/.plan-tool/plans.json`, not a path under the chdir'd directory.
- `test_empty_manifest_hint_names_repo_root_manifest` (`tests/cli/test_inspect_cmds.py`, `cmd_list`) — two-root setup with an empty manifest, chdir elsewhere, run `list` with `--manifest` omitted, and assert the stdout hint (`add repo-relative paths … in …`) names `repo_root/.plan-tool/plans.json`.

Every new test must be green before this step is considered finished.

## Acceptance criteria

- `plan_tool/cli/manifest.py`'s `cmd_register`, `cmd_deregister`, and `cmd_sweep` each call `default_manifest_path(ctx.repo_root)` instead of the bare `default_manifest_path()`.
- `plan_tool/cli/inspect.py`'s `cmd_list` calls `default_manifest_path(ctx.repo_root)` at both of its remaining bare call sites; its third (already-correct) call site and `cmd_root`'s call site are unchanged.
- Running `register` / `deregister` / `sweep` with `--repo-root` set to a directory other than cwd, and `--manifest` omitted, reads and writes the manifest under that `--repo-root`, never under cwd.
- `list` run the same way (`--manifest` omitted, `--repo-root` differing from cwd) prints hints naming the `--repo-root`-derived manifest path in both the missing-entries warning and the empty-manifest message.
- Callers that pass an explicit `--manifest` see no behavior change — the fix touches only the `args.manifest is None` fallback branch.
- The five new tests pass, and `uv run pytest tests/cli/test_manifest_cmds.py tests/cli/test_inspect_cmds.py -q` stays green.

## References

- [pathlib — Object-oriented filesystem paths](https://docs.python.org/3/library/pathlib.html) — `Path.resolve()` and path equality are what the new tests rely on to assert each command's manifest path landed under `repo_root`, not cwd.

## Deferred

- Re-fixing `create.py:create_plan`'s own bare `default_manifest_path()` call — that's step 1's territory (`depends_on: 1`); this step only closes the five sibling sites in `manifest.py` / `inspect.py`.
- Threading a relocated `created_repo_root` from `create` into a chained `direct-jira` / `direct-run` run — step 2's `_stage_namespace` overrides handle that; this step fixes the CLI commands' own fallback independent of whether they're invoked directly or via the chain.
- Consolidating the now six sibling `X or default_manifest_path(...)` call sites (this step's five plus `create.py`'s one) into a single shared helper — a refactor/consolidation step this detail file can't mint; each site stays an independent one-line fix per the existing precedent in the codebase.
