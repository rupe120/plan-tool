> **Auto-archived**: this plan was swept on 2026-07-12 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

---
title: Transient Retry Partial Mutation Guard
status: completed
priority: medium
enforce_step_tests: true
steps:
- id: 1
  title: Add a retry-guard seam and stop/restore policy to run_with_rate_limit_recovery
  files:
  - plan_tool/rate_limit_loop.py
  - tests/test_rate_limit_loop.py
  complexity: medium
  change_type: feature
  detail: docs/implementation-plans/plan-details/transient-retry-partial-mutation-guard/01-retry-guard-seam-stop-restore-policy.md
  status: done
- id: 2
  title: Wire the streaming shell_invoker retry-guard to refuse retry when the aborted
    turn left uncommitted edits
  files:
  - plan_tool/launcher.py
  - tests/test_launcher.py
  complexity: medium
  change_type: feature
  depends_on:
  - 1
  detail: docs/implementation-plans/plan-details/transient-retry-partial-mutation-guard/02-wire-streaming-shell-invoker-retry.md
  status: done
- id: 3
  title: Wire the batch claude_invoke seam to an always-retry constant and pin byte-for-byte
    behavior
  files:
  - plan_tool/shell.py
  - tests/test_shell.py
  complexity: low
  change_type: feature
  depends_on:
  - 1
  detail: docs/implementation-plans/plan-details/transient-retry-partial-mutation-guard/03-wire-batch-claude-invoke-seam-always.md
  status: done
- id: 4
  title: Document the terminal-on-partial-mutation behavior and close the BUG_BACKLOG
    RISK entry
  files:
  - docs/RUN_FLOW.md
  - RUNBOOK.md
  - BUG_BACKLOG.md
  - BACKLOG.md
  complexity: medium
  change_type: non-code
  depends_on:
  - 1
  - 2
  - 3
  detail: docs/implementation-plans/plan-details/transient-retry-partial-mutation-guard/04-document-terminal-on-partial-mutation.md
  status: done
---
# Transient Retry Partial Mutation Guard

## Overview

Make the streaming `run` transient/rate-limit retry idempotent-aware. Today a `claude -p` turn that applies partial file edits and then aborts mid-stream classifies as `TRANSIENT` (or hits a usage-limit/429 classified `RATE_LIMIT`) and is retried; the retry re-invokes the same prompt in a fresh session against the already-edited tree, so the model re-applies its changes on top of the partial ones (a function/import added twice) and the double-apply lands as a green step, corrupting the committed diff. This plan adds a shared detection seam (a `retry_guard` callback consulted at the loop's shared re-invoke point — every retry, transient backoff and rate-limit wait/switch alike) that detects the aborted turn left uncommitted edits and refuses to blindly re-drive. It builds response **A (baseline-delta guard: detect + STOP)** now; the `stop`/`restore` policy is shaped **caller-side** (in the launcher guard closure that owns git) so B (snapshot-restore) is a later branch there, not a rewrite, and never touches the stdlib-only leaf. The exit-code convention (rc reflects completion, not findings) is preserved.

## Problem statement

On the streaming `run` execution path, the retry loop is the shared stdlib-only leaf `plan_tool/rate_limit_loop.py:run_with_rate_limit_recovery`. Every one of its retry arms loops back to a single `run_once(current_attempt)` re-invoke (line 103): the `TRANSIENT` arm (around lines 199–210), and the `RATE_LIMIT` arm's wait path (`current_attempt += 1; continue`, ~193–197) and SWITCH / ASK-switch paths (~157–160, ~179–182). Via `launcher.py`, `run_once` is `_run_once_seam` → `_run_streaming_once`, a fresh Claude session — "Each call is a fresh Claude session with only this prompt in context" (`launcher.py:533`) — spawned with `cwd=get_active_spawn_cwd()` against whatever state the aborted turn left behind. Because any of these re-invokes re-sends the same prompt over a partially-mutated working tree, the model can re-apply its edits on top of the partial ones; the double-apply then lands as a green step and corrupts the committed diff. The truncated-turn marker (`response above may be incomplete`) illustrates why transients are dangerous — a truncation tail is a stronger signal the turn ran far enough to have edited before aborting — but the guard deliberately does **not** key on that marker. It keys on the git changed-paths delta, a strictly broader signal that catches any partial mutation whether or not the turn was marked truncated, so the marker motivates the fix but needs no separate handling. This resolves the single outstanding `RISK` entry in `BUG_BACKLOG.md`: "Transient retry re-drives the `acceptEdits` streaming run over a partially-mutated tree" — whose own text enumerates "every transient class (ECONNRESET/timeout/429/overload already retry here)", so the fix must cover the rate-limit arms too.

## Architecture

**The shared detection seam.** Add one injected callback to `run_with_rate_limit_recovery` — e.g. `retry_guard(outcome) -> RetryDecision` (or a narrower "may I retry?" seam) — consulted **once, whenever the loop predicts a re-invoke** (`will_retry_rate_limit or will_retry_transient`), placed before the recovery arms so it runs before any backoff or rate-limit wait. One check there covers every retry arm (transient backoff, and rate-limit wait/switch/ASK-switch), since all of them re-invoke the same `run_once`; it is deliberately *not* consulted on `SUCCESS`, on a terminal-without-re-invoke path, or before attempt 1's initial call. The leaf stays stdlib-only and imports nothing first-party (no git, no `repo_root`, no `ClaudeFailureKind`); the decision is computed caller-side and injected, not inlined into the leaf.

**Caller wiring.** The batch caller (`shell.claude_invoke`) wires the seam to a constant "always safe to retry" and does **no** git read — safe because its authoring/audit *prompts* (create/detail/jira/annotate/lessons) never mutate the working tree, not because of the permission mode (batch shares the streaming path's `--permission-mode acceptEdits`); step 3 names that assumption. The streaming caller (`launcher.shell_invoker`) wires a git-delta check: capture the baseline once before attempt 1, and on each predicted re-invoke diff the current changed-paths set (scoped to `get_active_spawn_cwd()`) against it. A non-empty delta of tracked or untracked-non-ignored paths is a partial mutation; gitignored writes (run-log, `.plan-tool/telemetry`) do not appear in porcelain, so they don't false-trigger. `run_step` already has the pieces: `repo_root`, `_git_changed_paths(repo_root)` (`launcher.py:1182`), and it already snapshots a git baseline for the test-authoring gate (`git_test_baseline`, `launcher.py:1801`). Note `_git_changed_paths` returns the empty set on any git error, which shapes the guard's failure semantics (see Risks).

**The STOP response (A).** On a detected partial mutation, do not retry: return the attempt as a terminal failure with a clear, actionable hint — partial edits were left in the tree; either **discard them** (`git restore` / `git checkout` for modified files, plus `git clean -f` / `rm` for newly-created ones — restore/checkout do **not** remove untracked files, which the delta counts via `--untracked-files=all`) and re-run the step, or accept the partial work as complete and do **not** re-run. Never *commit-then-re-run*: re-running the step over files that already carry the partial work re-drives the prompt and reintroduces the exact double-apply the guard exists to stop (see the re-guard-after-STOP known limit in Risks). This changes when a retry becomes terminal, not the rc contract.

**Structure B as a caller-side policy swap.** Shape the `stop`/`restore` policy **caller-side**, in the launcher guard closure that owns git — not in the leaf. The leaf seam only ever returns `RETRY` or `STOP`; it is stdlib-only and cannot restore a tree, so a leaf `RESTORE` member would be inert. B's restore is therefore a later branch *inside that closure*: on a detected dirty tree it restores to the pre-attempt snapshot and returns `RETRY`, so B adds no leaf member and touches neither the leaf signature nor its other caller — a stronger purity guarantee than a reserved-enum swap. Do not implement the restore/snapshot mechanism in this plan unless the author elects to land A+B together; if deferred, leave a `BACKLOG.md` (not `BUG_BACKLOG.md`) entry naming the restore-policy follow-up, since it's forward-looking work, not an outstanding bug once A closes the corruption.

## References

- [Git - git-status Documentation](https://git-scm.com/docs/git-status) — Official spec for git status porcelain v1/v2 machine-readable output and untracked/ignored file modes, the exact format the streaming caller parses to compute the changed-paths delta.
- [Git - git-check-ignore Documentation](https://git-scm.com/docs/git-check-ignore) — Documents how Git decides whether a path is gitignored, the basis for scoping the guard to tracked/untracked-non-ignored paths so run-log and .plan-tool/telemetry writes don't false-trigger.
- [Git - git-restore Documentation](https://git-scm.com/docs/git-restore) — Reference for reverting working-tree files (source, --worktree, --staged, overlay semantics), needed for the operator's git checkout recovery hint in response A and the deferred snapshot-restore policy B.
- [Python - subprocess module Documentation](https://docs.python.org/3/library/subprocess.html) — Primary reference for Popen/run, cwd, streaming stdout, and return codes, since the retry loop re-invokes the Claude CLI as a subprocess against get_active_spawn_cwd() and the guard inspects its state.
- [Claude Code — Headless / Non-interactive mode](https://docs.claude.com/en/docs/claude-code/headless) — Official docs for claude -p print mode, stream-json output, and session resume/session_id, defining the fresh-session-per-invoke behavior the transient retry re-drives and the session-resume path Option C rejects.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

- **Option C (session-resume).** Rejected: per-backend contract work (`backend.py` + fixtures for claude/codex/cursor), a weaker correctness guarantee than a hard restore, and an aborted stream frequently emits no `session_id` to resume against — record the rationale, don't build it.
- **The batch/audit path.** Already idempotent (proposal calls don't mutate the tree); only wire it to the no-op seam.
- **Changing the failure classifier (`claude_errors.py`).** The set of TRANSIENT / RATE_LIMIT classes is unchanged; this plan guards the *response* to a retryable failure (transient backoff or rate-limit wait/switch), not the classification.
- **`--commit`'s per-green-step semantics.** Untouched; the guard reads git state, it does not add commits.

## Risks

- **False-abort on incidental writes.** Severity: UX. If the guard counts a gitignored run-log/telemetry write as a mutation it would refuse a legitimate retry. Mitigation: scope the delta to tracked + untracked-non-ignored paths (porcelain already omits ignored files); add a test with a gitignored write during the aborted turn that must not trip the guard.
- **Concurrent non-turn writes read as turn edits.** Severity: UX. `_git_changed_paths` can't distinguish an edit made by the Claude turn from a concurrent non-turn write (an editor autosave, a background formatter/watcher, a sibling process in the same tree); a non-ignored such write during the loop yields a non-empty delta → a false `STOP` that surfaces a legitimate transient/rate-limit as terminal. The failure direction is **safe** — a false `STOP`, never a double-apply — so this is an accepted known limit of a path-level git-delta guard, not a correctness hole; the operator inspects and re-runs. Named here so it isn't mistaken for the guard misfiring.
- **Baseline captured too late.** Severity: correctness. The baseline must be snapshotted before attempt 1, or the first attempt's own edits hide in the baseline and the guard never fires. Mitigation: capture at loop entry / first `run_once`; test a first-attempt partial-edit-then-abort.
- **Resilience regression (A only).** Severity: scoping. Refusing the retry turns some previously-recovered transient/rate-limit failures into surfaced failures. This is the deliberate trade for correctness; document it in `RUNBOOK.md`/`docs/RUN_FLOW.md` and leave B as the resilience-restoring follow-up.
- **Re-run after STOP without reverting defeats the guard.** Severity: correctness (operator). A fresh `shell_invoker` invocation snapshots its baseline at entry, so re-running the step *without first reverting* folds the leftover partial edits into the new baseline — the delta is then empty (or masked, for same-path edits) and the re-drive double-applies exactly what STOP prevented. Mitigation: the STOP hint and the `RUNBOOK.md` recovery entry state that recovery is *revert first, then re-run* (or accept the partial work and don't re-run). Note *when* this bites: the run-start clean-tree preflight (`run_cmd.py:_working_tree_dirty`) is **`--commit`-only** (gated on `commit_active`), so a `--commit` run **refuses to start** over the STOP-left dirty tree — an automatic backstop against the silent re-baseline — while a `--commit`-less bare re-run has no such gate, which is exactly where the operator revert-first discipline is load-bearing.
- **Path-level masking within a `--commit`-less multi-step run.** Severity: correctness. The delta is path-level, so a partial mutation to a file **already dirty in the baseline** is masked. Beyond the re-run case above, this also bites *within a single run*: step N's baseline still contains steps 1..N-1's uncommitted edits, so an aborted step N re-editing an already-dirty file (e.g. a shared `tests/test_detail.py`) yields an empty delta → `RETRY` → double-apply. Mitigation: `--commit` — the mandated flag for multi-step runs — commits each green step, so step N's baseline carries no prior-step dirty edits and the mask can't form (the same reason `--commit` is load-bearing for the test-authoring gate). Byte-level diffing to catch same-path edits is out of scope.
- **Guard failure semantics on an unreadable git state.** Severity: correctness. `git status` can fail mid-run (e.g. an `index.lock` during a `--commit` run). The guard uses `_git_changed_paths_or_none`, which returns `None` on a git error (vs an empty set on a clean tree), and **classifies by the baseline**: an unreadable read *at entry* (no spawn cwd, a non-git tree, or a repo unreadable at start) leaves the guard **inert** — retry as before, preserving out-of-tree behavior; but once a baseline was captured (a readable repo), a *later* unreadable read is a genuine error and the guard fails **closed** (`STOP` with a git-state hint) rather than re-driving over an unverifiable tree. This resolves the fail-open corruption the naive `_git_changed_paths` (empty-set-on-error) would have allowed, while keeping the non-git-tree case inert. Two residuals remain and are tracked in `BACKLOG.md` #120 (guard hardening): a **baseline-instant** git error still reads as inert (a narrow fail-open window, vs the closed mid-run window), and a spurious mid-run git failure converts a recoverable transient into a step failure (the resilience cost — safe direction). A robust fix (repo-detection to split non-git from unreadable, plus retry-on-lock) is deferred there.
- **Terminal-without-retry paths also leave partial edits.** Severity: UX. The guard only fires when a re-invoke is predicted, so a failure that goes terminal *without* retrying (a transient past its budget, or a second rate-limit taking the `if rate_limit_retried:` "already retried once" branch) surfaces the generic hint, not step 2's revert-first partial-mutation hint — yet it too can leave uncommitted partial edits. No double-apply occurs (no re-invoke), so correctness holds, but the operator gets no revert guidance. Mitigation: step 4's `RUNBOOK.md` recovery entry covers *any* terminal failure that leaves partial edits, not only the STOP path.
- **Leaf purity.** Severity: architecture. `rate_limit_loop.py` must stay stdlib-only with no first-party import. Mitigation: the seam is a plain callable injected by each caller; add no `plan_tool` import to the leaf, and keep restore caller-side so B adds no leaf branch.

## Testing

Follow the project's unit-first convention. Unit-test the leaf `run_with_rate_limit_recovery` in isolation: it consults the injected `retry_guard` on every re-invoke (transient backoff **and** rate-limit wait/switch), skips it on the first attempt and when a failure goes terminal without re-invoking, and gains no first-party import. Cover the streaming caller's git-delta guard: a transient (or rate-limit) whose aborted turn left uncommitted tracked/untracked-non-ignored edits does not re-drive (terminal failure with actionable hint); a gitignored write during the aborted turn does not trip the guard; and a first-attempt partial-edit-then-abort is caught (baseline captured before attempt 1). Cover the batch caller wiring the seam to a no-op and behaving byte-for-byte as before. Assert the exit-code convention (rc reflects completion, not findings). Per TESTING.md, override the invoker seams / stub module-level proposal functions so no real backend is spawned; add cross-module `@pytest.mark.integration` coverage only if a unit test on the seam and its caller wiring would miss the double-apply end-to-end.

**Per-step test strategy** (derived from each step's `change_type`):

- step 1 (feature) — unit tests added with the implementation; green before completion.
- step 2 (feature) — unit tests added with the implementation; green before completion.
- step 3 (feature) — unit tests added with the implementation; green before completion.
- step 4 (non-code) — verification appropriate to the artifacts; no test-ordering directive.

## Acceptance criteria

- `run_with_rate_limit_recovery` consults an injected retry-guard seam at its shared re-invoke point — on every retry (transient backoff and rate-limit wait/switch), skipped on the first attempt and when a failure goes terminal without re-invoking; the leaf gains no first-party import.
- On the streaming `run` path, a transient or rate-limit failure whose aborted turn left uncommitted tracked/untracked-non-ignored edits does not re-drive the prompt; it surfaces as a terminal failure with an actionable hint, and the double-apply no longer occurs.
- The batch/audit path wires the seam to a no-op and behaves byte-for-byte as before (covered by a test).
- A gitignored write during the aborted turn does not trip the guard.
- The baseline is captured before the first attempt (test: first-attempt partial-edit-then-abort is caught).
- The `stop`/`restore` policy is shaped **caller-side** (the launcher guard closure) so B (snapshot-restore) is a later branch there, not a leaf change or a rewrite; the leaf seam returns only `RETRY`/`STOP`. If B is deferred, a `BACKLOG.md` entry names the follow-up.
- The re-guard-after-STOP limit is documented: re-running the step *without first reverting* re-baselines the leftover edits and defeats the guard, so recovery is revert-first (or accept-and-don't-re-run) — never commit-then-re-run.
- The exit-code convention is preserved (rc reflects completion, not findings).
- The plan's final step updates `BUG_BACKLOG.md`: because the guard now covers every re-invoke arm (transient and rate-limit), the transient-retry RISK entry is fully removed once the corruption is closed (no residual rate-limit hole to caveat).
- `docs/RUN_FLOW.md` (and `RUNBOOK.md` if operator-facing recovery changes) note the new terminal-on-partial-mutation behavior.

## Deferred

- **Response B (snapshot + restore + retry).** Same detection; on a dirty tree, restore to the pre-attempt snapshot and re-drive → idempotent recovery that keeps transient/rate-limit resilience. Deferred because it mutates the working tree mid-run, so the restore must be scoped not to clobber a `--commit`-less run's earlier legitimate dirty edits. B lives **caller-side** in the launcher guard closure (which has git): it restores then returns `RETRY`, so it is a later branch there — not a leaf change or a rewrite. If deferred, a `BACKLOG.md` entry names the restore-policy follow-up.
