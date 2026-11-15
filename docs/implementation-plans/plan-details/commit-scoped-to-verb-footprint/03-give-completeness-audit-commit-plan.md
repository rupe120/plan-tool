# Step 3 — Give `completeness-audit --commit` its own footprint

<!-- plan-tool:detail-format-version: 1 -->

## Summary

`completeness-audit --commit` stops committing the whole repo. `cmd_completeness` in `plan_tool/cli/completeness_cmd.py` builds a footprint and passes it to step 1's `commit_all` in place of `[ctx.repo_root]`. The footprint is the plan file, the plan's `plan-details/<slug>/` directory (reports, sidecar, detail files), every `step.detail` file the plan declares, and the project lessons directory. The subject, the clean-tree precondition and the `--json` / `budget.enabled` gating stay as they are. On green, a file dirtied mid-run outside the footprint stays dirty and uncommitted, and every footprint path is clean afterwards. The `--commit` help text and `docs/cli/completeness-audit.md` match.

## Table of Contents

- [Why](#why) — what the whole-tree commit sweeps in
- [Input](#input) — the step 1 contract and the write sites for this verb
- [Files (creates vs edits)](#files-creates-vs-edits) — edits per file
- [Implementation](#implementation) — footprint, call site, help text
- [Tests](#tests) — cases in `tests/cli/test_completeness_cmd.py`
- [Acceptance criteria](#acceptance-criteria) — observable checks
- [References](#references) — docs and symbols to read
- [Applicable guardrails](#applicable-guardrails) — plan fences that bind this step
- [Deferred](#deferred) — work this step leaves out

## Why

The `--commit` block in `cmd_completeness` calls `commit_all(ctx.repo_root, subject)`, which stages everything. A file another process changes while a long `--iterate` run is in flight lands in the audit commit with the plan edits. Step 1 gives `commit_all` a required `paths` footprint. This step supplies the footprint for this verb.

## Input

- **Step 1's `commit_all`.** The signature is `commit_all(repo_root, subject, paths)`. It stages and commits only `paths`, skips gitignored and missing entries, returns success with no commit when the footprint is clean, and returns a non-zero rc naming any footprint path still dirty after the commit. Read the landed code in `plan_tool/cli/gitcommit.py` and let it win over this description. At HEAD the call here still uses the two-argument form, so this step cannot start until step 1 lands.
- **Write sites for a `--iterate` run** (grepped at HEAD):
  - The plan file, edited by `apply_finding` in `plan_tool/launcher.py`.
  - Detail files, edited by the same `apply_finding`. A step's `detail:` pointer can name a file outside `plan-details/<slug>/`; the existing test helper `_attach_minimal_detail` uses `plans/details/01-only-step.md`. The footprint must cover the declared path, not only the canonical directory.
  - The saved report and sidecar, written by `write_completeness_report` in `plan_tool/completeness_report.py` under `plan_reports_dir(plan_path)` in `plan_tool/review_persistence.py`. That directory is `<plan dir>/plan-details/<slug>/reports/`.
  - Lessons: no call to `append_lessons` exists on the completeness path at HEAD (the only hits are inside `plan_tool/lessons.py`). The lessons directory is included because the step names it, not because a write site was found.
- **Not in the footprint on purpose.** Checkpoints, the purity cache and run logs sit under gitignored `.plan-tool/` subdirectories. `commit_all` would skip them anyway.
- **Slug.** The commit subject uses `_plan_slug` from `plan_tool/detail.py`. `plan_reports_dir` derives the same slug through `slug_from_filename`. Build the directory from `plan_reports_dir(path).parent` so it matches where reports land.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/cli/completeness_cmd.py`: add a small footprint helper and use it in the `--commit` block of `cmd_completeness`; rewrite the `--commit` help text in `register`.
  - `tests/cli/test_completeness_cmd.py`: add cases to the `--commit` section (near `TestCompletenessCommitGates`).
  - `docs/cli/completeness-audit.md`: regenerate with `python -m plan_tool.cli_reference --write`; do not hand-edit.

## Implementation

- **Footprint helper.** Add one private function in `completeness_cmd.py` that returns a list of paths: the plan path, `plan_reports_dir(path).parent`, each `ctx.repo_root / step.detail` for steps with a `detail` set, and the project lessons directory from `plan_tool/lessons.py` (`PROJECT_LESSONS_REL` joined onto the repo root). Take the steps from the plan parsed after the loop, since `apply_finding` can change `detail:` pointers. Re-parse the plan at commit time rather than reusing an earlier object.
- **Reuse, don't copy.** Do not recompute the reports directory by hand; call `plan_reports_dir`. Do not write a new path-normalizing or dirty-checking routine; step 1's `commit_all` already skips missing and ignored entries.
- **Call site.** Replace `commit_all(ctx.repo_root, subject)` with `commit_all(ctx.repo_root, subject, footprint)`. Keep the surrounding condition (`commit` set, not `--json`, `budget.enabled`), the subject from `_completeness_commit_subject`, and the success / failure messages and `return 1` on a failed commit.
- **Clean-tree precondition unchanged.** The `working_tree_dirty(ctx.repo_root)` check before the run still looks at the whole tree. Do not narrow it.
- **Failure to parse the plan at commit time.** Fall back to the plan file plus the canonical directory rather than raising; a parse error here must not turn a finished run into a crash. One way: wrap the parse in the helper and skip the detail pointers on `ParseError`.
- **Help text.** Replace "stage all changes (git add -A)" with wording that names the footprint: the plan file, its `plan-details/<slug>/` directory and the project lessons directory. Keep the subject, the `--iterate` requirement, the clean-tree requirement, "off by default" and "ignored with --json".
- **Rejected alternative.** Tracking written paths during the run was rejected: it is a footprint-tracking subsystem, which the plan's scope guardrails rule out.

## Tests

All in `tests/cli/test_completeness_cmd.py`, in a real temporary repo (reuse `_init_git_repo` and `_git_commit_all`), with the audit and `apply_finding` seams stubbed so no backend is spawned.

### Tests for this step

- `test_audit_commit_leaves_unrelated_file_dirtied_during_run_uncommitted` — a file created by the stubbed apply outside the footprint stays untracked and out of the commit.
- `test_audit_commit_includes_report_and_sidecar` — the report `.md` and `-completeness.json` under `plan-details/<slug>/reports/` are in the commit.
- `test_audit_commit_footprint_paths_clean_afterwards` — `git status` shows nothing dirty for the plan file, the plan-details directory and a declared detail file.
- `test_audit_commit_covers_detail_file_declared_outside_plan_details` — a `step.detail` pointing at `plans/details/…` is committed. This pins the declared-pointer rule, which reads like an extra but is required.
- `test_audit_commit_footprint_excludes_stray_pre_staged_file` — a file staged during the run is not in the audit commit.
- `test_completeness_commit_uses_the_detail_footprint_with_plan_dir_and_declared_details` — unit check of the shared `_detail_commit_footprint` output the audit commits.

Every test above must be green before the step is finished. Existing tests in `TestCompletenessCommitSubjects` and `TestCompletenessCommitGates` stay unchanged and green.

## Acceptance criteria

- With `--commit --iterate`, a file dirtied outside the footprint during the run is not in the commit and is still dirty afterwards.
- The commit contains the saved report and sidecar.
- Every footprint path is clean after the run.
- The commit subject is unchanged; the clean-tree precondition still rejects any dirty tree before the run.
- `rg 'commit_all\(' plan_tool/cli/completeness_cmd.py` shows a call with three arguments and no `ctx.repo_root` as the footprint.
- `python -m plan_tool.cli_reference --write` produces no further diff, and `docs/cli/completeness-audit.md` no longer says "git add -A".

## References

- BUG_BACKLOG.md, "`--commit` stages the whole working tree with `git add -A`…"
- `plan_tool/cli/gitcommit.py` (`commit_all`); `plan_tool/review_persistence.py` (`plan_reports_dir`); `plan_tool/completeness_report.py` (`write_completeness_report`); `plan_tool/lessons.py` (`PROJECT_LESSONS_REL`)
- `docs/TRACKING.md` § "Scope contract and anti-creep"

## Applicable guardrails

- The plan's "## Scope guardrails": this step changes only what `completeness-audit --commit` stages and commits. The clean-tree precondition, commit subject, verbs that accept `--commit` and per-step granularity stay as they are.
- The plan's "## Scope guardrails", footprint-tracking bullet: the footprint is computed from known locations, with no tracking, hook or `--no-verify`.
- The plan's "## Out of scope": the only added check is that written paths are clean after the commit, which step 1 owns. This step adds no content judgments or exit-code changes beyond the failed-commit result.

## Deferred

- Widening `--commit` to other verbs — tracked as BACKLOG #89, lands after this plan.
- A lessons write site for the completeness path — none exists at HEAD; if one is added later, its path must be in the footprint then.
- A concurrent process editing a file the verb wrote — out of scope per the plan; that file is committed with the verb's version.
