# Step 1 — Make `commit_all` commit only a named footprint

<!-- plan-tool:detail-format-version: 1 -->

## Summary

`commit_all` in `plan_tool/cli/gitcommit.py` takes a required `paths` footprint. It stages that footprint with `git add -A -- <paths>` and commits it with `git commit -m <subject> -- <paths>`, so unrelated dirty files and pre-staged entries stay out of the commit. Before staging it skips gitignored entries with a warning and entries that exist nowhere. After a successful commit it re-reads `git status` and fails with a non-zero result naming any footprint path that is still dirty. When the footprint has nothing to commit, it returns success without a commit. The three existing callers pass `[repo_root]` for now, which keeps their whole-tree behaviour until steps 2–5 replace it.

## Table of Contents

- [Why](#why) — what `git add -A` sweeps in today
- [Input](#input) — existing helpers and the caller set this step reuses or touches
- [Files (creates vs edits)](#files-creates-vs-edits) — the edits per file
- [Implementation](#implementation) — contract, recommended approach, constraints
- [Tests](#tests) — the test roster in `tests/cli/test_gitcommit.py`
- [Acceptance criteria](#acceptance-criteria) — observable checks
- [References](#references) — the docs and symbols to read
- [Applicable guardrails](#applicable-guardrails) — plan fences that bind this step
- [Deferred](#deferred) — work this step leaves to other steps

## Why

`commit_all` runs `git add -A` and then `git commit -m`. Any file that changed while the verb ran is committed with the verb's own edits, and so is anything already in the index. The plan needs one helper that can commit only a named footprint. It also needs that helper to report a written path that is still dirty afterward, for example when a hook rewrote the file. This step builds the helper. Steps 2–5 give each `--commit` surface its real footprint.

## Input

- **`path_is_gitignored(repo_root, path)`** in `plan_tool/cli/gitcommit.py` is reused unchanged. It returns `True` only when `git check-ignore` exits 0.
- **`unexpected_dirty_paths`** in the same file is the model for status handling. It runs `git status --porcelain --untracked-files=all`, relativizes entries against `repo_root.resolve()`, and treats an entry as covering a reported path when the path equals the entry or sits under `entry + "/"`. It also skips entries that are not under `repo_root`. The `-uall` flag is required so a new untracked directory is not collapsed into one line.
- **Current callers at HEAD** (found by grepping `commit_all`):
  - `plan_tool/cli/authoring.py:_commit_if_dirty`, which wraps `_commit_all` in a try/except for `OSError` and `ValueError`.
  - `plan_tool/cli/completeness_cmd.py:cmd_completeness`, in the `--commit` block after the report is saved.
  - `plan_tool/cli/manifest.py:cmd_sweep`, in the `--commit` block.
- Every caller treats `(rc, tail)` as "rc 0 means committed". A success result with a "nothing changed" tail is safe for all three, because they only print `tail` on failure.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/cli/gitcommit.py`: change the `commit_all` signature and body, and update the module docstring.
  - `plan_tool/cli/authoring.py`: `_commit_if_dirty` passes `[repo_root]`.
  - `plan_tool/cli/completeness_cmd.py`: the `commit_all` call passes `[ctx.repo_root]`.
  - `plan_tool/cli/manifest.py`: the `commit_all` call in `cmd_sweep` passes `[ctx.repo_root]`.
  - `tests/cli/test_gitcommit.py`: add a `TestCommitAll` class.

## Implementation

**Target signature.** `commit_all(repo_root: Path, subject: str, paths: Sequence[Path])`. `paths` is required and has no default, so a caller cannot drop back to the whole tree by accident. The return stays `(rc, tail)`.

**Behaviour the step must deliver, in order:**

1. **Normalize the footprint.** Make each entry repo-relative to `repo_root.resolve()`. Skip an entry that is not under `repo_root`, as `unexpected_dirty_paths` does. Pass entries to git as literal pathspecs. One way: set `GIT_LITERAL_PATHSPECS=1` in the subprocess environment, or prefix each entry with `:(literal)`. This stops a filename containing glob characters from matching other files.
2. **Skip ignored entries with a warning.** For each entry where `path_is_gitignored` is true, print a one-line warning that names the path, and drop it from staging and from the post-commit check. Write the warning to stderr in the style the neighbouring helpers use (`warn_recommended_paths_ignored` takes an `emit` callable and is the nearest precedent). An ignored entry does not fail the commit.
3. **Skip entries that name nothing.** Drop an entry that is not on disk and is not tracked. Check tracked state with `git ls-files --error-unmatch` or `git ls-files -- <path>`. A tracked path deleted on disk stays in, so `-A` stages the deletion. Skipped entries are also outside the post-commit check.
4. **Stage.** Run `git add -A -- <remaining paths>`. An entry with no change stages harmlessly. A directory entry covers everything beneath it, including new nested files, deletions and renames inside it. Return git's rc and stderr if it fails.
5. **Detect "nothing to commit".** After staging, test whether the footprint has staged changes, for example `git diff --cached --quiet -- <paths>`. If there are none, make no commit and return `(0, <tail saying nothing changed>)`. This replaces git's non-zero "nothing to commit". Recommended: check this rather than parsing git's message, which depends on locale and git version.
6. **Commit.** Run `git commit -m <subject> -- <paths>`. The pathspec form commits only those paths, so an unrelated entry already in the index stays staged but uncommitted. Return git's rc and stderr tail on failure. Do not add `--no-verify` or any trailer. Hooks run, and a hook rejection is a non-zero result as today.
7. **Check the footprint is clean.** After a successful commit, run `git status --porcelain --untracked-files=all` over the remaining (non-ignored, non-skipped) paths. If any is still dirty, return a non-zero rc whose tail names each such path. Use the same equals-or-under-`entry/` matching as `unexpected_dirty_paths`. If `git status` cannot be read, treat that as a failure, not as clean.

**Key design decisions:**
- **Pathspec-limited commit, not `git add -A` followed by a whole-index commit.** This is the property that keeps a pre-staged unrelated file out. The rejected alternative is unstaging everything first, which would mutate the operator's index.
- **No new abstraction.** Use one function with a fixed sequence. Do not add a footprint type, a registry or a configuration knob.
- **Reuse the status parsing idea, not a second fence of helpers.** If the equals-or-under matching can be shared with `unexpected_dirty_paths` as a small private function without changing that function's behaviour, do so. Otherwise write the few lines locally. Do not alter `unexpected_dirty_paths` results.

**Constraints that are not free to vary:**
- `commit_all` deletes nothing itself. A delete or rename inside the footprint is staged by `-A`. A delete outside it is no longer staged.
- Both sides of a rename must be in the footprint for the rename to be committed as a rename. An origin outside the footprint is not staged. Steps 2–5 own deciding the footprint, so this step only guarantees the behaviour for paths it is given.
- `commit_receipt` and `bench.py:_git_commit_baseline` are not touched.
- The three callers pass `[repo_root]` and nothing else. Their commit subjects, their clean-tree precondition and their error handling stay unchanged.
- Update the module docstring. It currently says `--commit` stages the plan/detail edits the verbs produce. State that `commit_all` stages and commits only the footprint it is given, and that a footprint path left dirty after the commit is a failure.

## Tests

All new cases go in a `TestCommitAll` class in `tests/cli/test_gitcommit.py`. They use the existing helpers `_init_git_repo`, `_commit_initial` and `_git` against a real `tmp_path` repo, and make no backend call.

- `test_unrelated_dirty_file_is_not_committed` — with footprint `[a.txt]`, a dirty `b.txt` stays uncommitted and still shows in `git status`.
- `test_pre_staged_unrelated_file_is_not_committed` — a file staged by `git add` before the call but outside the footprint is absent from the new commit and remains staged.
- `test_delete_inside_footprint_is_staged` — deleting a tracked footprint file produces a commit that removes it.
- `test_rename_inside_footprint_is_staged` — a rename with both sides in the footprint (directory entry or both paths) commits as a rename.
- `test_directory_entry_stages_new_nested_files` — a directory entry commits new files created several levels beneath it.
- `test_ignored_path_warns_and_commit_still_succeeds` — an ignored footprint entry is named in the warning, is not committed, and rc is 0 when another entry has a change.
- `test_expected_path_left_dirty_is_reported_by_name_with_nonzero_rc` — a pre-commit hook rewrites a footprint file after staging, so the file is dirty after the commit. The result is non-zero and the tail names that path. This pins the post-commit check as deliberate behaviour.
- `test_absent_untracked_entry_is_skipped_without_failing` — an entry that is neither on disk nor tracked does not fail the call or appear in the failure tail.
- `test_tracked_deleted_entry_is_staged` — a tracked path deleted on disk, named directly as an entry, is committed as a deletion.
- `test_footprint_with_no_changes_returns_success_and_makes_no_commit` — `HEAD` is the same before and after, rc is 0, and the tail says nothing changed.
- `test_literal_pathspec_does_not_match_glob_characters` — an entry with `*` in its name does not stage a sibling file that the glob would match. This pins literal handling.

**Green-before-done gate:** every case above and the existing `tests/cli/test_gitcommit.py` suite must pass before the step is finished. The three caller suites (`tests/cli/test_authoring_cmds.py`, `tests/cli/test_completeness_cmd.py`, `tests/cli/test_manifest_cmds.py`) must stay green with `[repo_root]` as the footprint. Verify the new tests by breaking the code each one names, for example dropping the `--` pathspec from the commit command, and confirming the test goes red.

## Acceptance criteria

- `commit_all(repo_root, subject)` with no `paths` raises `TypeError`.
- With footprint `[a]`, an unrelated dirty file and an unrelated pre-staged file are not in the commit.
- A delete and a rename inside the footprint are in the commit. A directory entry commits its nested new files.
- A gitignored entry produces a one-line warning naming it, and the call still returns rc 0.
- A footprint path still dirty after the commit gives a non-zero rc with that path named in the tail.
- An absent untracked entry is skipped and does not change the result.
- A footprint with no changes returns rc 0, makes no new commit, and the tail says nothing changed.
- No `--no-verify` and no attribution trailer appear in the commit command.
- The module docstring no longer describes `--commit` as staging whatever the verbs produced.
- `authoring.py`, `completeness_cmd.py` and `manifest.py` each pass `[repo_root]` and have no other behaviour change.

## References

- BUG_BACKLOG.md, "`--commit` stages the whole working tree with `git add -A`…" — the defect this step starts to fix.
- `plan_tool/cli/gitcommit.py` — `commit_all`, `path_is_gitignored`, `unexpected_dirty_paths`, `warn_recommended_paths_ignored`.
- `plan_tool/cli/authoring.py` — `_commit_if_dirty`.
- `plan_tool/cli/completeness_cmd.py` — `cmd_completeness`, the `--commit` block.
- `plan_tool/cli/manifest.py` — `cmd_sweep`, the `--commit` block.
- `docs/TRACKING.md` § "Scope contract and anti-creep".

## Applicable guardrails

- **The plan's "Scope guardrails", first bullet:** this step changes only what a `--commit` surface stages and commits. It does not touch the clean-tree precondition, commit subjects, which verbs accept `--commit`, per-step commit granularity, or the test-authoring gate in `plan_tool/launcher.py`.
- **The plan's "Scope guardrails", second bullet:** this step leaves `commit_receipt` and `bench.py:_git_commit_baseline` as they are, and widens `--commit` to no other verb (BACKLOG #89).
- **The plan's "Scope guardrails", third bullet:** the tempting site here is the post-commit check. It stays one binary fact (a written path is clean). It must not grow into a content check, a hook, `--no-verify`, a trailer or any footprint-tracking bookkeeping.
- **The plan's "Out of scope", exit-code limit:** the only new non-zero results are the post-commit-dirty failure and a failed staging or commit. The no-change case returns success.

## Deferred

- Real per-verb footprints for `detail`, `completeness-audit` and the sweep — steps 2–5 replace the `[repo_root]` placeholder.
- A concurrent process editing a file the verb wrote — out of scope in the plan; the file is committed with the verb's version and is not detected.
- Widening `--commit` to more verbs — BACKLOG #89, which lands after this plan.
- Sharing the equals-or-under path matching between `commit_all` and `unexpected_dirty_paths` beyond a small private helper — a consolidation, not part of this step; file it in BACKLOG.md if noticed.
