> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 1 — Add a single-path receipt commit helper that preserves unrelated staged and unstaged changes

## Summary

Add a receipt-only Git helper in `plan_tool/cli/gitcommit.py` and focused repository-state tests in `tests/cli/test_gitcommit.py`. The helper stages an ignored receipt path and commits that path alone, rather than using `commit_all`’s whole-tree behavior. On green, the receipt is in `HEAD` with no remaining receipt dirt, while the helper's own operations leave unrelated staged and unstaged changes unchanged.

## Table of Contents

- [Summary](#summary) — The change and its green result.
- [Table of Contents](#table-of-contents) — Links to each detail section.
- [Why](#why) — Why receipt persistence needs a narrower Git operation.
- [Input](#input) — The existing Git and ignore-rule contracts this helper uses.
- [Files (creates vs edits)](#files-creates-vs-edits) — The two files this step changes.
- [Implementation](#implementation) — Required single-path staging, commit, and cleanup behavior.
- [Tests](#tests) — Repository-state tests that prove the helper’s boundaries.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Git, subprocess, and pytest documentation for this change.
- [Applicable guardrails](#applicable-guardrails) — Scope limits that keep this helper narrow.
- [Deferred](#deferred) — Related lifecycle and broad-commit work left to later steps.

## Why

`plan_tool/cli/gitcommit.py:commit_all` uses `git add -A`, which cannot commit a newly published receipt without also taking unrelated user changes from the index or worktree. The current `**/.plan-tool/evidence/` rule in `.gitignore` also prevents normal staging of a receipt. Receipt persistence therefore needs one focused helper before step 2 can make receipt commits durable without changing user-owned state.

## Input

- **Existing helper and hook contract:** Match `plan_tool/cli/gitcommit.py:commit_all`’s `(returncode, stderr-tail)` result shape so step 2 can handle Git failures without a second result format. Keep ordinary repository hooks enabled as external Git policy; this helper does not inspect, suppress, or repair their side effects.
- **Receipt path:** Accept one existing receipt file beneath the Git worktree selected from the roadmap plans directory; this helper owns that path’s staging and no other path’s state.
- **Ignored evidence path:** The `**/.plan-tool/evidence/` entry in `.gitignore` means the helper must handle an ignored receipt until step 2 changes that rule.

## Files (creates vs edits)

- **New files:** None.

- **Existing files (edits only):**
  - `plan_tool/cli/gitcommit.py` — Add the receipt-only commit helper beside `commit_all` without changing the broad commit helper’s behavior or the module’s leaf import boundary.
  - `tests/cli/test_gitcommit.py` — Import the helper and add real-repository tests using `_init_git_repo`, `_commit_initial`, and `_git`.

## Implementation

- **Keep the helper receipt-scoped.** Add one focused helper next to `plan_tool/cli/gitcommit.py:commit_all` that takes a repository root, one receipt path, and a commit subject, then returns the same return-code and stderr-tail shape as `commit_all`.

- **Stage exactly one file.** The helper must use a one-file Git pathspec with `--` and force staging for the supplied receipt path. The force is required while `.gitignore` excludes evidence; broad staging and directory pathspecs must not appear in this helper.

- **Commit only the supplied path.** Use a path-limited commit form that excludes every unrelated pre-existing index entry from the new commit. `git commit --only` with the exact receipt path is one suitable approach; the required result is that the receipt reaches `HEAD` and unrelated staged entries remain staged afterward.

- **Preserve unrelated state through tool operations.** Do not inspect, stage, reset, restore, or delete unrelated paths. The helper's staging, commit invocation, and cleanup leave unrelated content unchanged and leave no receipt worktree change on success. Repository hooks run under ordinary Git policy; their independent side effects are outside this helper's authority.

- **Classify process-launch failure as a normal helper failure.** Return the same failure shape when Git cannot start, rather than raising `OSError`. A failure before staging leaves the receipt untouched; a nonzero or launch failure after staging unstages only the receipt path while retaining its on-disk bytes. Do not use a whole-index reset or any cleanup that changes unrelated staged entries.

- **Let interruption reach the caller.** Do not catch `KeyboardInterrupt` or convert it into a normal Git result. The later receipt lifecycle owns the interrupted outcome, and the helper must not run reset or deletion cleanup on that path.

- **Keep Git invocation behavior consistent.** Mirror `commit_all`’s noninteractive subprocess setup, captured output, and hook-enabled commits. Do not add `--no-verify`; a hook rejection remains a returned failure, while the helper makes no claim to sandbox arbitrary hook effects.

- **Leave broad commit users alone.** `plan_tool/cli/authoring.py:_commit_if_dirty`, `plan_tool/cli/completeness_phases.py`, `plan_tool/cli/direct_cmd.py`, `plan_tool/cli/manifest.py`, and `plan_tool/bench.py` retain their existing `commit_all` behavior. `plan_tool/cli/run_cmd.py:_commit_green_step` also remains separate because it commits a green execution step, not a receipt.

## Tests

Extend `tests/cli/test_gitcommit.py` with a dedicated helper test class near the existing per-primitive classes. Use real temporary Git repositories for index and worktree assertions; use monkeypatching only to make interruption deterministic.

### Tests for this step

- `test_receipt_commit_forces_only_ignored_receipt_into_head` — An ignored receipt commits successfully, the new `HEAD` commit contains only that receipt, and the receipt has no remaining status entry.
- `test_receipt_commit_preserves_unrelated_staged_change` — A pre-staged unrelated tracked change remains staged with the same content and is absent from the receipt commit.
- `test_receipt_commit_preserves_unrelated_unstaged_change` — An unrelated unstaged tracked change keeps its content and worktree status after the receipt commits.
- `test_receipt_commit_failure_unstages_only_receipt_after_simple_hook_rejection` — A hook that only rejects returns a nonzero result and leaves the receipt on disk but unstaged; this proves helper cleanup without claiming control over arbitrary hook effects.
- `test_receipt_commit_process_launch_failure_before_staging_returns_failure` — A Git launch failure before staging returns a failure result without changing the receipt or unrelated Git state.
- `test_receipt_commit_process_launch_failure_after_staging_unstages_only_receipt` — A Git launch failure after receipt staging returns a failure result, retains receipt bytes, and unwinds only that staging.
- `test_receipt_commit_interruption_propagates_without_cleanup` — A `KeyboardInterrupt` from the commit subprocess reaches the caller and does not reset or delete the receipt or unrelated changes.

The green-before-done gate is every listed test plus `uv run pytest tests/ -q -n auto`.

## Acceptance criteria

- A single ignored receipt file can be force-staged and committed without staging a sibling or unrelated path.
- The receipt commit contains only the supplied receipt path, and that receipt has no remaining staged or unstaged status after success.
- The helper's own operations leave a pre-existing unrelated staged change staged and absent from the receipt commit.
- The helper's own operations leave a pre-existing unrelated unstaged change unchanged and unstaged after the receipt commit.
- A hook-rejected or Git process-launch failure returns a failure result, keeps the receipt on disk, and removes only receipt staging when staging occurred.
- A `KeyboardInterrupt` propagates without reset or deletion cleanup.
- `tests/cli/test_gitcommit.py` and the plan test command pass.

## References

- [Git — git-add Documentationhttps: — Use the exact-path, force-add, and pathspec rules for ignored receipts.
- [Git — git-commit Documentationhttps: — Use path-limited commit behavior that excludes unrelated index entries.
- [Git — git-status Documentationhttps: — Check porcelain status without confusing staged and unstaged state.
- [Git — githooks Documentationhttps: — Keep hook rejection as a visible commit failure.
- [subprocess — Subprocess managementhttps: — Preserve return-code, stderr, and interruption handling at the Git boundary.
- [pytest monkeypatch documentationhttps: — Make the interruption path deterministic without a real signal.

## Applicable guardrails

- **The plan’s `## Plan intent` and step intent** — Keep ownership to the exact receipt path and preserve user-owned index and worktree state.
- **The plan’s `## Out of scope`** — Keep this as a focused helper; do not expand the change into adjacent command, storage, or framework work.
- **The plan’s step boundary** — Leave receipt lifecycle wiring and ignore-rule changes to step 2.

## Deferred

- Receipt lifecycle integration — Step 2 consumes the helper from `plan_tool/roadmap_escalation_run.py:run_roadmap_escalation_receipt` and owns result handling.
- Broad automatic commits — `plan_tool/cli/gitcommit.py:commit_all` and its callers remain unchanged because generalizing their behavior exceeds this step’s scope.
- Green-step commits — `plan_tool/cli/run_cmd.py:_commit_green_step` remains a separate execution-specific flow.
