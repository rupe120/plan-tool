# Step 2 — Give `detail --commit` its own footprint at all three commit sites

<!-- plan-tool:detail-format-version: 1 -->

## Summary

`detail --commit` passes a footprint to `commit_all` at all three commit sites in `plan_tool/cli/authoring.py`. The sites are the per-step commit (`_commit_detail_step`), the `--jobs>1` batch commit and the residual sweep after a per-step run. The footprint is the plan file, the plan's `plan-details/<slug>/` directory and the project lessons directory `.plan-tool/lessons/`. A helper in `authoring.py` computes it once per run. `_commit_if_dirty` decides "nothing to commit" from dirt inside the footprint, so an unrelated dirty file no longer triggers a commit. On green, a file dirtied mid-run outside the footprint stays dirty and uncommitted, and every footprint path is clean after the commit. The `--commit` help text and the generated `docs/cli/detail.md` match the new behavior.

## Table of Contents

- [Why](#why) — what the current whole-tree commit sweeps in
- [Input](#input) — the step 1 contract and the write sites this step maps
- [Files (creates vs edits)](#files-creates-vs-edits) — edits per file
- [Implementation](#implementation) — footprint, `_commit_if_dirty`, call sites, help text
- [Tests](#tests) — per-site cases in `tests/cli/test_authoring_cmds.py`
- [Acceptance criteria](#acceptance-criteria) — observable checks
- [References](#references) — docs and symbols to read
- [Applicable guardrails](#applicable-guardrails) — plan fences that bind this step
- [Deferred](#deferred) — work this step leaves out

## Why

`_commit_if_dirty` asks `_working_tree_dirty` about the whole tree and then calls `_commit_all`. A file another process changes while a multi-step authoring run is in flight is committed with the verb's own edits. The serial path commits once per converged step, so one unrelated edit lands in the first step's commit. After step 1, `commit_all` can commit a named footprint. This step supplies that footprint at the `detail --commit` sites. It also fixes the "is there anything to commit" test, which must stop looking at the whole tree. Step 1 already makes an empty footprint a successful no-op, so the check no longer prevents a failure. It decides only whether `_commit_if_dirty` returns `None` (nothing to commit) and so whether the run prints a commit line; with a whole-tree check, an unrelated dirty file would make the run report a commit that did not happen.

## Input

- **Step 1's `commit_all`.** The landed signature is `commit_all(repo_root, subject, paths)`, with `paths` required. It stages and commits only those paths. It skips gitignored and missing entries and returns `(rc, tail)`. It returns success without a commit when the footprint has nothing to commit. It fails with a non-zero rc naming any footprint path still dirty after the commit. Read the landed code in `plan_tool/cli/gitcommit.py` rather than this description, and let the landed behavior win. At the time of writing, HEAD still has the old two-argument form, so this step cannot start until step 1 lands.
- **Write sites for `detail --commit`** (grepped in `plan_tool/detail.py` and `plan_tool/cli/authoring.py`):
  - The detail file, written by `output_path.write_text` in the per-step authoring routine. The path comes from `derive_detail_path`.
  - `_archive_orphan_details`, which moves stale `NN-*.md` files into `archive/` beside the output path. Both sides of each rename are inside `plan-details/<slug>/`.
  - The plan file, whose `steps[].detail` pointer is updated by `update_step_detail_field`.
  - Saved completeness reports under `plan-details/<slug>/reports/`, from `plan_tool/review_persistence.py:plan_reports_dir`. The completeness tail runs with `commit = False`, so the caller owns the one commit.
  - Project lessons, appended by `append_lessons` under `<repo_root>/.plan-tool/lessons/` (`PROJECT_LESSONS_REL` in `plan_tool/lessons.py`). General lessons live under the user's home directory, outside the repo, so they are not in the footprint.
- **Not in the footprint on purpose.** Checkpoints, the purity cache, parse-failure captures and run logs live under gitignored `.plan-tool/` subdirectories. `commit_all` skips gitignored entries anyway, but leaving them out keeps the footprint honest.
- **Unverified, to confirm while implementing.** Whether any `detail` code path writes another tracked file, for example a manifest update. Grep `plan_tool/detail.py` and the completeness tail for tracked writes before settling the list. If one exists, add its path to the footprint.
- **Existing sites to change in `plan_tool/cli/authoring.py`:**
  - `_commit_if_dirty` (shared by the other two).
  - `_commit_detail_step`, called from `_commit_step_cb` inside `cmd_detail`.
  - The end-of-run block that calls `_commit_if_dirty` for the batch and residual subjects.
- **Existing seams to keep.** `_commit_all` and `_working_tree_dirty` are module-level aliases that tests patch (`monkeypatch.setattr(authoring, "_commit_all", ...)`). Keep the module-global call form for `_commit_all`.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/cli/authoring.py`:
    - Add a footprint helper for `detail --commit`.
    - Change `_commit_if_dirty` and `_commit_detail_step` to take the footprint.
    - Pass the footprint at the three call sites in `cmd_detail`.
    - Rewrite the `--commit` help text in the `p_detail` parser.
  - `tests/cli/test_authoring_cmds.py`: add per-site tests and update the existing tests that patch `_commit_all` or call `_commit_if_dirty` to the new signature.
  - `docs/cli/detail.md`: regenerated, not hand-edited.

## Implementation

**Footprint helper.**
- Add one small function that takes the repo root and the plan path and returns the footprint as a list of paths. Call it once per run, next to `_commit_slug` in `cmd_detail`, and hand the result to all three sites.
- The list holds three entries:
  - the plan file;
  - the plan's `plan-details/<slug>/` directory, taken as the parent of `plan_reports_dir(path)`. This reuses the existing derivation instead of re-deriving the slug;
  - `repo_root / ".plan-tool" / "lessons"`, built from `PROJECT_LESSONS_REL`.
- Pass the directory as a directory. `git add -A -- <dir>` stages new files, edits and deletions under it, including both halves of an `archive/` rename. This is why the archive-rename case holds without listing archive paths one by one.
- A fixed three-entry list is enough. Do not build a tracker that records which files the run wrote. The plan fences that out.

**`_commit_if_dirty`.**
- New shape: `(repo_root, subject, footprint)`. Return `None` when nothing inside the footprint is dirty, and otherwise call `_commit_all(repo_root, subject, footprint)`.
- To test for dirt inside the footprint, one likely approach is `git status --porcelain --untracked-files=all -- <footprint paths>`. A narrower alternative is a helper from `plan_tool/cli/gitcommit.py` if step 1 left one reusable. Do not add a second helper if one exists. Prefer the smallest call that reports footprint-only dirt.
- If the footprint has a missing or gitignored entry (for example no `.plan-tool/lessons/` yet), that entry must not count as dirt and must not raise.
- Keep the never-raises contract. Wrap the dirt check and the commit in the same `except (OSError, ValueError)` that returns `(1, "git subprocess error: …")`.
- When the dirt check cannot read git, fail closed: return the non-zero tuple. Do not return `None`, because that would report a clean run when git could not be read.
- **Reason for the new check:** with the old whole-tree check, an unrelated dirty file passes it, step 1's `commit_all` finds nothing in the footprint to commit, and the caller needs a clear outcome for that. `None` is the right outcome, and it needs the footprint-scoped check.

**`_commit_detail_step`.** Add the footprint parameter and forward it. Keep the `None`-on-clean return.

**Per-step site (`_commit_step_cb`).**
- Pass the footprint to `_commit_detail_step`.
- Keep the stop-after-first-failure rule exactly as it is. A failed commit leaves footprint paths staged, so a later step's `git add` would fold those into the wrong commit. The guard on `_commit_failed_steps` must stay. Update its comment, which still says `git add -A`.

**Batch and residual sites (end-of-run block).**
- Both reach the single `_commit_if_dirty(ctx.repo_root, subject)` call, which picks the batch or residual subject. Pass the footprint there. No separate code per site is needed in production.
- Subjects, which-site-fires logic and the `wrote` gate do not change.

**Help text.**
- Rewrite the `--commit` help for `detail` so it no longer says it stages everything or mentions `git add -A`.
- It must state that only the plan file, the plan's `plan-details/<slug>/` directory and project lessons are committed, and that other changed files are left alone.
- Keep the facts already in the text: the commit subject, the clean-tree requirement up front, off by default, and ignored under `--dry-run` or when nothing was authored.
- Regenerate `docs/cli/detail.md` with `python -m plan_tool.cli_reference --write`. The doc is drift-guarded by `tests/cli/test_cli_reference.py`.

**Not free to vary.**
- `_commit_all` is called through the module global, so the existing patches keep working.
- The clean-tree precondition at the top of `cmd_detail`, the subjects and the `wrote` gate are unchanged. That precondition guards the start of the run only. Anything dirtied after it is the case this step handles.
- No `--no-verify` and no trailer.

**Rejected alternatives.**
- Tracking each written file in a list. It adds bookkeeping the plan fences out, and the directory-plus-plan-file footprint covers every write site above.
- Skipping the footprint for the batch site because it runs after all writes. The unrelated file can still be dirtied during a long parallel run.

## Tests

All in `tests/cli/test_authoring_cmds.py`. Reuse the helpers in `TestDetailCommitHelpers` and `TestDetailCommitCmd` (`_git_commit_all`, the `tmp_repo` fixture). The three sites run at different times against different dirt, so each gets its own cases and no case is shared across sites.

**Helper-level (`TestDetailCommitHelpers`):**
- `test_detail_commit_includes_a_declared_detail_path_outside_the_canonical_directory` — a step whose `detail:` pointer names a file outside `plan-details/<slug>/` has that file committed and clean after `detail --commit`.
- `test_commit_if_dirty_returns_none_when_only_unrelated_file_is_dirty` — dirt outside the footprint yields `None` and makes no commit. This pins the empty-commit failure mode.
- `test_commit_if_dirty_commits_footprint_and_leaves_unrelated_dirty` — the footprint edit is committed and the unrelated file stays modified and unstaged.
- `test_commit_if_dirty_never_raises_on_git_error` — the existing `boom` test, updated to the new signature, still gets a non-zero `(rc, tail)` instead of an exception.
- `test_commit_if_dirty_fails_closed_when_git_status_unreadable` — an `OSError` from the dirt check returns non-zero, not `None`.
- `test_commit_if_dirty_footprint_with_missing_lessons_dir_does_not_raise` — a footprint entry that does not exist is not dirt.

**Per-step site (`TestDetailCommitCmd`, serial run):**
- `test_per_step_commit_leaves_file_dirtied_mid_run_out_of_commit` — a file outside the footprint is dirtied inside the stubbed `generate_detail`, before the step callback fires. The per-step commit excludes it.
- `test_per_step_commit_stages_archive_rename_in_plan_details` — a stale `NN-*.md` is moved into `plan-details/<slug>/archive/` before the callback. The commit contains the deletion and the archive add.
- `test_per_step_commit_leaves_every_footprint_path_clean` — after the run, `git status` shows nothing under the plan file, the plan-details directory or the lessons directory.
- `test_per_step_failure_stops_later_step_commits_and_leaves_footprint_staged` — a failing first commit still blocks later steps' commits. This keeps the stop-after-first-failure rule pinned under the new signature.

**Batch site (`--jobs 2`, concurrent path, callback never fires):**
- `test_batch_commit_leaves_file_dirtied_mid_run_out_of_commit` — an unrelated file dirtied during the stubbed concurrent run is not committed.
- `test_batch_commit_stages_archive_rename_in_plan_details` — the archive move is part of the one batch commit.
- `test_batch_commit_leaves_every_footprint_path_clean` — nothing under the footprint is dirty afterward.

**Residual site (serial run, then the completeness-tail edits):**
- `test_residual_sweep_leaves_file_dirtied_mid_run_out_of_commit` — an unrelated file dirtied after the last step's commit is not swept in.
- `test_residual_sweep_stages_archive_rename_in_plan_details` — a rename written after the last per-step commit is staged by the residual commit.
- `test_residual_sweep_leaves_every_footprint_path_clean` — a saved report and a lessons append written after the per-step commits are committed, and the footprint is clean.
- `test_residual_sweep_with_only_unrelated_dirt_makes_no_commit` — a run whose only leftover dirt is outside the footprint makes no residual commit and exits 0.

**Existing tests to update:**
- The test that patches `authoring._commit_all` with `flaky_commit_all(repo_root, subject)` takes `(repo_root, subject, paths)` and forwards `paths` to the real function.
- Every test that calls `_commit_if_dirty` or `_commit_detail_step` directly passes a footprint.

**Green-before-done gate.** Every test above must pass before this step is done. Run `uv run pytest tests/cli/test_authoring_cmds.py tests/cli/test_cli_reference.py -q`, then the full suite with `-n auto`.

**Verify by breaking the code.** Revert one site to `[repo_root]` and confirm that site's unrelated-file case goes red. A green run says nothing about the sites that were not changed.

## Acceptance criteria

- At each of the three sites, a file outside the footprint that is dirtied after the run starts is still modified and uncommitted afterward, and is absent from the commit.
- An archive rename inside `plan-details/<slug>/` appears in the commit as part of the same commit, at each site.
- After a successful `detail --commit` run, `git status --porcelain` is empty for the plan file, the plan's `plan-details/<slug>/` directory and `.plan-tool/lessons/`.
- `_commit_if_dirty` returns `None` when the only dirt is outside the footprint, and does not invoke `commit_all` in that case.
- `_commit_if_dirty` never raises. A git error returns a non-zero `(rc, tail)`.
- A failed per-step commit still stops later per-step commits.
- No `commit_all` call from `plan_tool/cli/authoring.py` passes `[repo_root]` or `[ctx.repo_root]`. Check with `rg 'commit_all\(.*repo_root\]' plan_tool/cli/authoring.py`, which must return nothing.
- The `--commit` help for `detail` does not contain `git add -A` or the words "all changes".
- `docs/cli/detail.md` matches the parser output, and `uv run pytest tests/cli/test_cli_reference.py -q` passes.
- Commit subjects, the clean-tree precondition and `launcher.py` are unchanged (`git diff` touches only the three files in scope).

## References

- `plan_tool/cli/gitcommit.py` (`commit_all`, `unexpected_dirty_paths`, `working_tree_dirty`) — the landed step 1 contract and the status-reading helpers.
- `plan_tool/cli/authoring.py` (`_commit_if_dirty`, `_commit_detail_step`, `_commit_step_cb` in `cmd_detail`, the end-of-run `--commit` block) — the three sites.
- `plan_tool/detail.py` (`_archive_orphan_details`, the per-step `output_path.write_text`, `update_step_detail_field`) — the write sites that define the footprint.
- `plan_tool/review_persistence.py` (`plan_reports_dir`) and `plan_tool/lessons.py` (`PROJECT_LESSONS_REL`) — where reports and lessons land.
- BUG_BACKLOG.md, the entry on `--commit` staging the whole working tree with `git add -A` — the source defect.
- `docs/TRACKING.md` § "Scope contract and anti-creep" — the fence for this step.

## Applicable guardrails

- **The plan's "Scope guardrails" (change only what `--commit` stages and commits).** This step may change only the footprint, the "nothing to commit" decision and the `--commit` help text. It does not touch the clean-tree precondition, subjects, per-step commit granularity or `launcher.py`.
- **The plan's "Scope guardrails" (no footprint-tracking subsystem, no hook, no `--no-verify`, no attribution trailer).** The footprint is a fixed list built once from the plan path and repo root. The tempting place to add tracking is the per-step callback, and it stays a plain pass-through.
- **The plan's "Scope guardrails" (the only check is that a written path is clean after the commit).** That check lives in step 1's `commit_all`. This step adds no further verification, caps or exit-code changes beyond the failed-commit result.
- **The plan's "Out of scope" (a concurrent process editing a file the verb wrote).** A footprint file edited by another process is committed with the verb's version. This step does not detect it.
- **The plan's "Out of scope" (`commit_receipt`, `bench.py`, other verbs, BACKLOG #89).** Nothing in this step touches those.

## Deferred

- The `completeness-audit` footprint in `plan_tool/cli/completeness_cmd.py` — owned by a later step of this plan.
- The `manifest sweep` footprint in `plan_tool/cli/manifest.py` — owned by a later step of this plan.
- `run --commit` (`plan_tool/cli/run_cmd.py:_commit_green_step`) — owned by a later step of this plan.
- Widening `--commit` to more verbs — BACKLOG #89, which lands after this plan.
- Consolidating the footprint helper with the other verbs' footprint code — a separate consolidation entry in BACKLOG.md if the later steps leave duplicates. Not part of this step.
