> **Auto-archived**: this plan was swept on 2026-07-12 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 2 — Refuse the streaming transient retry when the aborted turn left uncommitted edits

## Summary

Wire the streaming `plan_tool/launcher.py:shell_invoker` to the `retry_guard` seam that step 1 adds to `plan_tool/rate_limit_loop.py:run_with_rate_limit_recovery`. Before the retry loop starts, `shell_invoker` snapshots the git changed-paths set once (scoped to the spawn cwd). It then hands the loop a guard closure that, when the loop is about to re-drive **any** retry (transient backoff or rate-limit wait/switch), re-reads the changed-paths set and compares it to the snapshot: any newly-changed tracked or untracked-non-ignored path means the aborted turn already edited the tree, so the guard returns `STOP` with an actionable hint instead of re-applying the prompt. The primary file is `plan_tool/launcher.py` (plus tests in `tests/test_launcher.py`). Design decision: the guard reuses the existing `plan_tool/launcher.py:_git_changed_paths` helper and reads the repo via `plan_tool/backend.py:get_active_spawn_cwd`, so no new git parsing and no widening of the `Invoker` signature. On green, a `run` step whose Claude turn partially edits the tree and then aborts (as a transient *or* a rate-limit) surfaces a terminal non-zero result — no double-apply — while out-of-tree callers (no spawn cwd) retry exactly as before.

## Table of Contents

- [Why](#why) — the double-apply this guard stops on the streaming path
- [Input](#input) — step 1's `retry_guard` seam contract this step consumes
- [Files (creates vs edits)](#files-creates-vs-edits) — the two files this step edits
- [Implementation](#implementation) — snapshot-before-attempt-1, the guard closure, and the invariants
- [Tests](#tests) — the caller-side guard cases to add and the green gate
- [Acceptance criteria](#acceptance-criteria) — checkable behaviors on green
- [References](#references) — git status/ignore/restore docs for this step
- [Deferred](#deferred) — response B and what stays out

## Why

On the streaming `run` path the retry loop re-invokes `run_once` after any retry arm — transient backoff, and the rate-limit wait/switch/ASK-switch paths. Through `shell_invoker`, that re-invoke is a fresh `claude -p` session (`cwd=get_active_spawn_cwd()`) against whatever the aborted turn left in the tree, so a turn that applied partial edits then aborted gets its edits re-applied on top of the partial ones — a double-apply that lands as a green step and corrupts the committed diff (the outstanding `RISK` in `BUG_BACKLOG.md`). Step 1 ships the injection point (consulted whenever a re-invoke is predicted, covering all arms) and the `STOP` branch in the stdlib-only leaf; the leaf knows nothing about git or a repo root, so the decision has to be computed here, caller-side, and injected. This step is that decider for the streaming caller. The batch caller wires a constant no-op in step 3.

## Input

This step consumes the seam step 1 adds to `plan_tool/rate_limit_loop.py:run_with_rate_limit_recovery`. Step 1 is the owner of that contract; follow its shipped names rather than the sketch here:

- **The `retry_guard` keyword param.** Step 1 adds it to `run_with_rate_limit_recovery` and consults it **once when the loop predicts a re-invoke** (`will_retry_rate_limit or will_retry_transient`), before the recovery arms — so it fires ahead of both the transient backoff and the rate-limit wait, on every arm. This step passes a closure into that param and does not touch where or how the loop consults it.
- **The decision value + policy enum.** Step 1 returns a small frozen decision (a `RetryPolicy` of `RETRY` / `STOP` — no `RESTORE` member; restore is caller-side — plus a `hint` string). The `STOP` branch surfaces the guard's `hint` through the loop's `notify` seam and returns the attempt as terminal — no wait, no re-invoke. This step builds a `STOP` decision carrying the partial-mutation hint, and a `RETRY` decision otherwise.
- **The always-retry default.** Step 1 provides a module-level always-retry singleton and defaults `retry_guard` to it, so an un-wired caller is unchanged. When this step decides the guard should be inert (no spawn cwd), it passes that same singleton (or omits the param).

If step 1's final seam name, decision type, or singleton name differ from this sketch, follow step 1's shipped contract — do not re-specify the leaf here.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/launcher.py` — in `shell_invoker`: snapshot the git changed-paths set once before calling `run_with_rate_limit_recovery`, define the `retry_guard` closure, and pass it into the loop. Import step 1's decision type / policy / singleton from `plan_tool.rate_limit_loop` alongside the existing `RecoveryAction` / `run_with_rate_limit_recovery` import.
  - `tests/test_launcher.py` — add caller-side tests for the guard: partial edit → `STOP`; gitignored write → retries; first-attempt edit caught (baseline captured before attempt 1); no spawn cwd → retries as before. Reuse the existing `_git_init` helper and `spawn_cwd`.

## Implementation

**Snapshot the baseline once, before attempt 1.** At the top of `shell_invoker` (near where it reads `_run_logger_var` / `_sibling_log_dir_var`), read the spawn cwd via `get_active_spawn_cwd()` and, when it is a real path, capture `baseline = _git_changed_paths(spawn_cwd)`. This must happen before `run_with_rate_limit_recovery` is called, so attempt 1's own edits are *not* folded into the baseline. Capturing inside the loop or inside `_run_once_seam` would hide the first attempt's partial edits and the guard would never fire — this is the plan's "baseline captured too late" risk, so keep the capture at `shell_invoker` entry.

**Reuse `_git_changed_paths`, don't re-parse porcelain.** The module already has `plan_tool/launcher.py:_git_changed_paths`, which runs `git status --porcelain -z --untracked-files=all` and returns the repo-relative changed set. Reuse it for both the baseline and each in-guard re-read. Two of its contracts carry the correctness for free:
- **Ignored files are already excluded.** Porcelain omits gitignored paths, so a run-log or `.plan-tool/telemetry` write during the aborted turn never appears in the set and can't false-trigger the guard.
- **A non-git tree (or any git error) returns the empty set.** So when the spawn cwd isn't a git repo, baseline and re-read are both empty, the delta is always empty, and the guard degrades to always-retry — same as today.

**Build the guard closure.** Define a small closure inside `shell_invoker` that the loop calls before any predicted re-invoke (transient backoff **or** rate-limit wait/switch — the loop gates the call on `will_retry_rate_limit or will_retry_transient`, so this same closure covers every arm):
- Re-read `current = _git_changed_paths(spawn_cwd)`.
- Compute `delta = current - baseline` — paths that became changed *after* the baseline snapshot. A pre-existing dirty tree (paths already in `baseline`) does not trip the guard; only new mutations do.
- **Non-empty `delta` → `STOP`**, with a hint that names the partial-mutation problem and the recovery: the aborted turn left uncommitted edits (list the delta paths), so re-running would double-apply; **discard** them (`git restore` / `git checkout` for modified files, plus `git clean -f` / `rm` for newly-created ones — restore/checkout don't remove untracked files, and the delta counts untracked-non-ignored paths) and re-run the step, or accept the partial work as complete and do **not** re-run. Do **not** commit-then-re-run — that leaves the partial work in the tree and re-drives over it (the same double-apply), and re-running without reverting also re-baselines the leftover edits so the guard can't catch it (see the known limit below). Empty `delta` → the `RETRY` decision.

**Wire inert behavior when there's no spawn cwd.** When `get_active_spawn_cwd()` returns `None` (tests, direct `shell_invoker` users, any non-run path), pass step 1's always-retry singleton (or omit `retry_guard`) so those callers are unchanged. The `Invoker` protocol carries only the prompt, which is exactly why `repo_root` reaches the spawn sites through `get_active_spawn_cwd` rather than a parameter — mirror that here instead of threading a new argument.

**Leave the rest of `shell_invoker` alone.** The `ExitStack` + `_rate_limit_backend_scope` scope, `resolve_on_rate_limit_policy`, the `_last_stats` sentinel reset, the two ContextVar reads, `_run_once_seam`, and the absent `on_nonsuccess` (launcher has no batch-only surfacings) all stay as they are. This step only adds the baseline capture and the `retry_guard=` argument to the `run_with_rate_limit_recovery(...)` call.

**Constraints and gotchas:**
- **`rate_limit_loop.py` stays a stdlib-only leaf.** The git decision lives entirely in `launcher.py`; do not add any git or `plan_tool` import to the leaf. This step only imports step 1's already-shipped decision type from `plan_tool.rate_limit_loop` into `launcher.py`.
- **Delta direction matters.** Use `current - baseline`, not set inequality or `baseline - current`. New edits are what signal a partial mutation.
- **Known limit — a file already dirty in the baseline that the aborted turn edits further.** Its path is in both sets, so it's masked from the delta and won't trip the guard (the delta is path-level, not byte-level; byte diffing is out of scope). This bites in **two** ways, both mitigated by `--commit`:
  - *Cross-invocation* — re-running after a `STOP` without reverting (the re-guard-after-`STOP` limit below).
  - *Within a single `--commit`-less multi-step run* — step N's `shell_invoker` snapshots a baseline that still contains steps 1..N-1's uncommitted edits, so if step N's aborted turn re-edits a file a prior step already left dirty (the shared `tests/test_detail.py` case CLAUDE.md calls out for the test-authoring gate), the current changed-paths set equals the baseline, the delta is empty → `RETRY` → the exact double-apply. This is the same masking that makes `--commit` load-bearing for the test-authoring gate: with `--commit` each green step is committed, so step N's baseline carries no prior-step dirty edits and the mask can't form. Document it; don't try to solve byte-level diffs here.
- **Known limit — re-running after `STOP` without first reverting defeats the guard.** After a `STOP`, `run_step` surfaces a terminal failure and **leaves the partial edits in the tree**. A *fresh* `shell_invoker` invocation snapshots its baseline at entry, so an unresolved re-run folds those leftover edits into the new baseline — the delta is then empty (or path-masked, per the limit above) and the re-drive double-applies exactly what `STOP` prevented. This is why the hint and the `RUNBOOK.md` recovery entry (step 4) say *revert first, then re-run* (or accept the partial work and don't re-run) — a bare re-run silently re-baselines the corruption. **When it bites:** the run-start clean-tree preflight (`run_cmd.py:_working_tree_dirty`) is **`--commit`-only** (gated on `commit_active`), so a `--commit` run refuses to start over the dirty tree and catches this automatically; a `--commit`-less bare re-run has no such gate, so the revert-first discipline is load-bearing only there.
- **Guard failure semantics — fail closed on a mid-run git error, inert on a non-git tree.** Use `_git_changed_paths_or_none` (returns `None` on a `git status` error, `set()` on a clean tree) so the guard can tell "couldn't read git" from "nothing changed" — the reused `_git_changed_paths` collapses both to `set()`, which fails **open** (empty delta → `RETRY` → double-apply). Classify by the **baseline**: `None` at entry (no spawn cwd, non-git tree, or unreadable-at-entry repo) → guard **inert** (retry as before, out-of-tree callers unchanged); a baseline set but a *later* `None` at a retry check → genuine mid-run error (e.g. `index.lock`) → fail **closed** (`STOP` with a git-state hint) rather than re-drive an unverifiable tree. This distinguishes the deliberately-inert non-git case from a real error and closes the fail-open corruption. Residual cost: a transient git hiccup on an active repo surfaces terminally (the safe direction).
- **A dirty-tree `STOP` pre-empts the interactive ASK menu.** Because the guard is consulted on the *predicted* re-invoke (before the rate-limit arm runs), a partial-mutation `STOP` on a rate-limit fires **before** `ask_action()` — the operator never sees the wait/switch/stop menu for a dirty tree. This is intended: a partial mutation must hard-stop regardless of the menu choice (waiting or switching would still re-drive the dirty tree). Stated so the pre-emption isn't read as a lost menu.
- **Terminal-without-retry paths leave partial edits too.** The guard only fires when the loop predicts a re-invoke, so a failure that goes terminal without retrying (transient past its budget; a second rate-limit via the `if rate_limit_retried:` branch) leaves any partial edits with only the generic hint, not this step's revert-first hint. No double-apply (no re-invoke), so correctness holds; step 4's `RUNBOOK.md` entry gives the revert guidance for *any* terminal failure that leaves partial edits, not only the `STOP` path.
- **rc contract preserved.** `STOP` returns the just-failed attempt's `(rc, payload)` — a non-zero rc, whether the failure was transient or rate-limit — so `run_step` sees a failed step and does not advance. No new exit codes; rc still reflects completion, not findings.

**Foundational logic and its other homes.** The core rule is "a non-empty post-attempt git changed-paths delta means don't re-drive." The batch caller `shell.claude_invoke` never needs that rule — proposals don't mutate the tree — so step 3 wires its seam to a constant always-`RETRY` decision; that wiring is step 3's concern, do not touch it here. `run_step` also snapshots a git baseline for the test-authoring gate (`git_test_baseline` via `_git_changed_paths`); that is a separate baseline for a different gate and is out of scope — this guard snapshots its own baseline inside `shell_invoker`.

## Tests

Add to `tests/test_launcher.py`, in the `shell_invoker` retry-behavior section. Drive `shell_invoker` with a Popen mock; use a real tmp git repo via `_git_init` and wrap calls in `spawn_cwd(tmp_path)` where the guard must be active. Simulating a partial edit needs a Popen stub that writes a file into the repo before returning a transient rc — `_make_popen_factory` only returns canned `_FakeProc` responses and has no per-call side-effect seam, so use a custom stub or extend the factory. The existing `test_shell_invoker_retries_transient_with_exponential_backoff` is the behavior oracle for the retry-happens case.

- `test_shell_invoker_stops_transient_retry_on_partial_edit` — first attempt writes a tracked/untracked file then returns transient; under `spawn_cwd(repo)`, the loop does **not** re-invoke, returns the transient's non-zero rc, and the partial-mutation hint is surfaced. Popen is called once.
- `test_shell_invoker_stops_rate_limit_retry_on_partial_edit` — first attempt writes a file then returns a `RATE_LIMIT` outcome (with recovery enabled, so the loop would otherwise wait+re-invoke); under `spawn_cwd(repo)`, the guard `STOP`s before the wait — Popen called once, no wait paid, rate-limit rc returned, hint surfaced. This proves the same closure covers the rate-limit arm (HIGH `rate-limit-arm-redrive`), not just the transient arm.
- `test_shell_invoker_partial_edit_is_caught_on_first_attempt` — proves the baseline is captured before attempt 1: the very first attempt's edit trips the guard (no retry).
- `test_shell_invoker_gitignored_write_does_not_stop_retry` — with a `.gitignore` covering the written path, the aborted turn's ignored write leaves the delta empty, so the transient retries and eventually succeeds (Popen called for each attempt).
- `test_shell_invoker_preexisting_dirty_does_not_stop_retry` — a path already dirty before the call sits in the baseline; a transient whose aborted turn adds no new path retries as before.
- `test_shell_invoker_bare_rerun_after_stop_rebaselines` — documents the re-guard-after-`STOP` known limit: a *second* `shell_invoker` call over a tree that still carries the leftover partial edits snapshots them into its baseline, so a transient-then-would-retry no longer trips the guard (the delta is empty) — pinning that recovery requires reverting first, not a bare re-run.
- `test_shell_invoker_retry_guard_inert_without_spawn_cwd` — no `spawn_cwd` scope (spawn cwd `None`); a transient followed by success retries normally, proving out-of-tree callers are unchanged.
- `test_shell_invoker_stop_preserves_rc_contract` — the `STOP` path returns the attempt's non-zero rc (completion, not a findings code).

### Test-creation order (feature step)

This is a **feature** step. Write each test above alongside the `shell_invoker` guard wiring, covering: the `STOP`-on-delta behavior on both the transient and rate-limit arms, first-attempt capture, the gitignore and pre-existing-dirty non-triggers, the re-guard-after-`STOP` re-baseline limit, the no-spawn-cwd inert path, and the rc contract. Green-before-done gate: every new test in `tests/test_launcher.py` must pass, and the existing `shell_invoker` transient/rate-limit tests must stay green unmodified, before this step is considered finished.

## Acceptance criteria

- Under a spawn cwd pointing at a git repo, a `TRANSIENT` **or** `RATE_LIMIT` attempt whose aborted turn left a newly-changed tracked or untracked-non-ignored path makes `shell_invoker` return the attempt's non-zero rc without re-invoking (and, for rate-limit, without paying the wait); the partial-mutation hint is surfaced.
- The baseline is captured before attempt 1: a first-attempt partial-edit-then-abort is caught (test passes).
- A gitignored write during the aborted turn does not stop the retry (test passes).
- A path already dirty before the call (in the baseline) does not stop the retry (test passes).
- The re-guard-after-`STOP` known limit is covered: a bare re-run over an unreverted tree re-baselines the leftover edits (test passes), so recovery is revert-first.
- With no active spawn cwd, `shell_invoker` retries transients/rate-limits exactly as before (test passes).
- `plan_tool/rate_limit_loop.py` gains no git or `plan_tool` import from this step.
- The rc convention is preserved: the `STOP` path returns the failed attempt's rc, not a findings code.

## References

- [Git - git-status Documentation](https://git-scm.com/docs/git-status) — porcelain `-z` / `--untracked-files=all` format and the default exclusion of ignored files, the exact output `_git_changed_paths` parses to build the baseline and delta.
- [Git - git-check-ignore Documentation](https://git-scm.com/docs/git-check-ignore) — how git decides a path is ignored, the basis for the gitignored-write-does-not-trip test.
- [Git - git-restore Documentation](https://git-scm.com/docs/git-restore) — working-tree restore semantics for the operator recovery hint the `STOP` decision surfaces (discard partial edits and re-run).

## Deferred

- **Response B (snapshot + restore + retry).** Same detection, but restore the pre-attempt tree and re-drive for idempotent recovery. Out of scope; B is a later branch **in this same closure** (which has git): on a non-empty delta it restores to a pre-attempt snapshot and returns `RETRY` instead of `STOP` — no leaf change, since the leaf contract stays `RETRY`/`STOP`. Step 4 files the `BACKLOG.md` follow-up if B stays deferred.
- **Batch path wiring.** `shell.claude_invoke` wiring the seam to an always-retry constant is step 3.
- **Docs and `BUG_BACKLOG.md` closeout.** Documenting the terminal-on-partial-mutation behavior and closing the RISK entry is step 4.
- **Byte-level detection of edits to an already-dirty file.** The delta is path-level, so further edits to a path already in the baseline are masked (known limit, mitigated by `--commit`); solving it is not in this plan.
