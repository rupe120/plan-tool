> **Replaced**: this file has been superseded by `docs/implementation-plans/2-transient-retry-partial-mutation-guard.md`.
> Preserved here for history; do not edit.

## Overview

Make the streaming `run`/`detail` transient retry idempotent-aware. Today a `claude -p` turn that applies partial file edits and then aborts mid-stream classifies as `TRANSIENT` and is retried with backoff; the retry re-invokes the same prompt in a fresh session against the already-edited tree, so the model re-applies its changes on top of the partial ones (a function/import added twice) and the double-apply lands as a green step, corrupting the committed diff. This plan adds a shared detection seam (a `retry_guard` callback consulted only on the TRANSIENT arm) that detects the aborted turn left uncommitted edits and refuses to blindly re-drive. It builds response **A (clean-tree gate: detect + STOP)** now and shapes the response as a swappable `stop`/`restore` policy so B (snapshot-restore) is a later add, not a rewrite. The exit-code convention (rc reflects completion, not findings) is preserved.

## Problem statement

On the streaming `run`/`detail` execution path, the retry loop is the shared stdlib-only leaf `plan_tool/rate_limit_loop.py:run_with_rate_limit_recovery`. Its `TRANSIENT` arm (around lines 199–210) simply calls `run_once(current_attempt)` again. Via `launcher.py`, `run_once` is `_run_once_seam` → `_run_streaming_once`, a fresh Claude session — "Each call is a fresh Claude session with only this prompt in context" (`launcher.py:533`) — spawned with `cwd=get_active_spawn_cwd()` against whatever state the aborted turn left behind. Because the retry re-sends the same prompt over a partially-mutated working tree, the model can re-apply its edits on top of the partial ones; the double-apply then lands as a green step and corrupts the committed diff. The truncated-turn marker (`response above may be incomplete`) widens the bug: a truncation tail is a stronger signal the turn ran far enough to have edited before aborting, so the naive retry hurts most exactly when it fires. This resolves the single outstanding `RISK` entry in `BUG_BACKLOG.md`: "Transient retry re-drives the `acceptEdits` streaming run over a partially-mutated tree."

## Architecture

**The shared detection seam.** Add one injected callback to `run_with_rate_limit_recovery` — e.g. `retry_guard(outcome) -> RetryDecision` (or a narrower "may I retry?" seam) — consulted only on the TRANSIENT retry arm, before the backoff sleep and re-invoke. The leaf stays stdlib-only and imports nothing first-party (no git, no `repo_root`, no `ClaudeFailureKind`); the decision is computed caller-side and injected, not inlined into the leaf.

**Caller wiring.** The batch caller (`shell.claude_invoke`) wires the seam to a constant "always safe to retry" (proposals never mutate the tree) — no behavior change. The streaming caller (`launcher.shell_invoker`) wires a git-delta check: capture the baseline once before attempt 1, and on each retry diff the current changed-paths set (scoped to `get_active_spawn_cwd()`) against it. A non-empty delta of tracked or untracked-non-ignored paths is a partial mutation; gitignored writes (run-log, `.plan-tool/telemetry`) do not appear in porcelain, so they don't false-trigger. `run_step` already has the pieces: `repo_root`, `_git_changed_paths(repo_root)` (`launcher.py:1182`), and it already snapshots a git baseline for the test-authoring gate (`git_test_baseline`, `launcher.py:1801`); the batch invoker has `gitcommit.working_tree_dirty`.

**The STOP response (A).** On a detected partial mutation, do not retry: return the attempt as a terminal failure with a clear, actionable hint (partial edits were left in the tree; resolve them via `git checkout`/commit/inspect and re-run the step). This changes when a transient becomes terminal, not the rc contract.

**Structure B as a policy swap.** Shape the response as a policy value (`stop` vs `restore`) so a future change adds the restore branch without touching the detection seam or its callers. Do not implement the restore/snapshot mechanism in this plan unless the author elects to land A+B together; if deferred, leave a `BACKLOG.md` (not `BUG_BACKLOG.md`) entry naming the restore-policy follow-up, since it's forward-looking work, not an outstanding bug once A closes the corruption.

## Out of scope

- **Option C (session-resume).** Rejected: per-backend contract work (`backend.py` + fixtures for claude/codex/cursor), a weaker correctness guarantee than a hard restore, and an aborted stream frequently emits no `session_id` to resume against — record the rationale, don't build it.
- **The batch/audit path.** Already idempotent (proposal calls don't mutate the tree); only wire it to the no-op seam.
- **Changing the failure classifier (`claude_errors.py`).** The set of TRANSIENT classes is unchanged; this plan guards the *response* to a transient, not the classification.
- **`--commit`'s per-green-step semantics.** Untouched; the guard reads git state, it does not add commits.

## Risks

- **False-abort on incidental writes.** Severity: UX. If the guard counts a gitignored run-log/telemetry write as a mutation it would refuse a legitimate retry. Mitigation: scope the delta to tracked + untracked-non-ignored paths (porcelain already omits ignored files); add a test with a gitignored write during the aborted turn that must not trip the guard.
- **Baseline captured too late.** Severity: correctness. The baseline must be snapshotted before attempt 1, or the first attempt's own edits hide in the baseline and the guard never fires. Mitigation: capture at loop entry / first `run_once`; test a first-attempt partial-edit-then-abort.
- **Resilience regression (A only).** Severity: scoping. Refusing the retry turns some previously-recovered transients into surfaced failures. This is the deliberate trade for correctness; document it in `RUNBOOK.md`/`docs/RUN_FLOW.md` and leave B as the resilience-restoring follow-up.
- **Leaf purity.** Severity: architecture. `rate_limit_loop.py` must stay stdlib-only with no first-party import. Mitigation: the seam is a plain callable injected by each caller; add no `plan_tool` import to the leaf.

## Testing

Follow the project's unit-first convention. Unit-test the leaf `run_with_rate_limit_recovery` in isolation: it consults the injected `retry_guard` only on the TRANSIENT arm (before backoff/re-invoke) and gains no first-party import. Cover the streaming caller's git-delta guard: a transient whose aborted turn left uncommitted tracked/untracked-non-ignored edits does not re-drive (terminal failure with actionable hint); a gitignored write during the aborted turn does not trip the guard; and a first-attempt partial-edit-then-abort is caught (baseline captured before attempt 1). Cover the batch caller wiring the seam to a no-op and behaving byte-for-byte as before. Assert the exit-code convention (rc reflects completion, not findings). Per TESTING.md, override the invoker seams / stub module-level proposal functions so no real backend is spawned; add cross-module `@pytest.mark.integration` coverage only if a unit test on the seam and its caller wiring would miss the double-apply end-to-end.

## Acceptance criteria

- `run_with_rate_limit_recovery` consults an injected retry-guard seam on the TRANSIENT arm only; the leaf gains no first-party import.
- On the streaming `run`/`detail` path, a transient failure whose aborted turn left uncommitted tracked/untracked-non-ignored edits does not re-drive the prompt; it surfaces as a terminal failure with an actionable hint, and the double-apply no longer occurs.
- The batch/audit path wires the seam to a no-op and behaves byte-for-byte as before (covered by a test).
- A gitignored write during the aborted turn does not trip the guard.
- The baseline is captured before the first attempt (test: first-attempt partial-edit-then-abort is caught).
- The response is shaped as a `stop`/`restore` policy so B (snapshot-restore) is a later branch, not a rewrite; if B is deferred, a `BACKLOG.md` entry names the follow-up.
- The exit-code convention is preserved (rc reflects completion, not findings).
- The plan's final step updates `BUG_BACKLOG.md`: removes the transient-retry RISK entry when the corruption is closed, or downgrades it to name exactly what remains if B is deferred.
- `docs/RUN_FLOW.md` (and `RUNBOOK.md` if operator-facing recovery changes) note the new terminal-on-partial-mutation behavior.

## Deferred

- **Response B (snapshot + RESTORE + retry).** Same detection; on a dirty tree, restore to the pre-attempt snapshot and re-drive → idempotent recovery that keeps transient resilience. Deferred because it mutates the working tree mid-run, so the restore must be scoped not to clobber a `--commit`-less run's earlier legitimate dirty edits; this plan builds the `stop`/`restore` policy seam so B is a later branch, not a rewrite. If deferred, a `BACKLOG.md` entry names the restore-policy follow-up.
