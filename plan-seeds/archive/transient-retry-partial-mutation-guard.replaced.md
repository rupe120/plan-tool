> **Replaced**: this file has been superseded by `docs/implementation-plans/2-transient-retry-partial-mutation-guard.md`.
> Preserved here for history; do not edit.

# Plan seed: guard the transient retry against re-driving a partially-mutated tree

This file is a `plan-tool create` input. Use it via:

```
plan-tool create --from-existing plan-seeds/transient-retry-partial-mutation-guard.md
```

It is **not** itself a plan — `plan-tool create` consumes the prose below and
proposes a step decomposition; the author then runs `plan-tool detail` per step.

> **Backlog source.** This plan resolves the single outstanding `RISK` entry in
> `BUG_BACKLOG.md`: *"Transient retry re-drives the `acceptEdits` streaming run
> over a partially-mutated tree."* When the work ships, the plan's final
> docs/status step **must remove that entry from `BUG_BACKLOG.md`** (or, if any
> phase is deferred, downgrade it to name exactly what remains). This bookkeeping
> is an acceptance criterion, not operator memory — it applies the same through
> the `claude`, `codex`, and `cursor` backends.

---

## Overview

On the streaming `run`/`detail` execution path, a `claude -p` turn that applies
**partial file edits and then aborts mid-stream** classifies as `TRANSIENT` and
is retried with backoff. The retry re-invokes the **same prompt** in a **fresh
session** against the **already-edited working tree**, so the model can re-apply
its changes on top of the partial ones (a function/import added twice), which
then land as a green step and corrupt the committed diff.

Make the streaming-run transient retry **idempotent-aware**: detect that the
aborted turn left uncommitted edits and refuse to blindly re-drive the same
prompt over them.

## Problem statement — grounded in the code

The retry loop is the shared stdlib-only leaf
`plan_tool/rate_limit_loop.py:run_with_rate_limit_recovery`. Its `TRANSIENT`
arm (around lines 199–210) simply calls `run_once(current_attempt)` again. Via
`launcher.py`, `run_once` is `_run_once_seam` → `_run_streaming_once`, which is a
**fresh Claude session** — "Each call is a fresh Claude session with only this
prompt in context" (`launcher.py:533`) — spawned with `cwd=get_active_spawn_cwd()`
against whatever state the aborted turn left behind.

Key facts the fix must respect:

- **The leaf is stdlib-only and imports nothing first-party** (no git, no
  `repo_root`, no `ClaudeFailureKind`). It stays that way — the guard is an
  **injected seam**, not a git call inlined into the leaf.
- **The batch/audit path (`shell.py:claude_invoke`) is unaffected.** Proposal
  calls don't mutate the tree, so re-running is idempotent; it must wire the new
  seam to a **no-op** and keep behaving byte-for-byte as today.
- **`run_step` already has the pieces:** `repo_root`, `_git_changed_paths(repo_root)`
  (`launcher.py:1182`), and it already snapshots a git baseline for the
  test-authoring gate (`git_test_baseline`, `launcher.py:1801`). The batch invoker
  has `gitcommit.working_tree_dirty`.
- The truncated-turn marker (`response above may be incomplete`) **widens** the
  bug: a truncation tail is a *stronger* signal the turn ran far enough to have
  edited before aborting, so the naive retry hurts most exactly when it fires.

## Chosen design (from the spike)

The three candidate fixes are **one detection with different responses**, plus a
separate, more expensive path:

- **A — clean-tree gate (detect + STOP).** Capture a git baseline before the
  first attempt; before each transient retry, if the tree gained changes, the
  aborted turn mutated it → **skip the retry** and surface the outcome as a
  terminal failure the operator resolves and re-runs. Backend-agnostic, smallest
  blast radius (read-only git). Cost: it **gives up** transient resilience for
  exactly the truncated-turn case.
- **B — snapshot + RESTORE + retry.** Same detection; on a dirty tree, restore
  to the pre-attempt snapshot, then re-drive → idempotent recovery that keeps
  resilience. Cost: it **mutates the working tree mid-run**, so the restore must
  be scoped not to clobber a `--commit`-less run's earlier legitimate dirty edits.
- **C — session-resume.** Resume the aborted session instead of re-sending the
  prompt. Rejected here (see Out of scope): it is per-backend, gives a weaker
  correctness guarantee than B's hard restore, and — decisively — an *aborted*
  stream often never reaches the `result` envelope that carries `session_id`, so
  there'd be nothing to resume and it would fall back to A/B anyway.

**This plan builds A now and structures the response as a swappable policy so B
is a later add, not a rewrite.**

### The shared detection seam

- Add one injected callback to `run_with_rate_limit_recovery` — e.g.
  `retry_guard(outcome) -> RetryDecision` (or a narrower "may I retry?" seam) —
  consulted **only on the TRANSIENT retry arm**, before the backoff sleep and
  re-invoke. The leaf stays stdlib-only; the decision is computed caller-side.
- **Batch caller (`shell.claude_invoke`):** wires the seam to a constant
  "always safe to retry" (proposals never mutate). No behavior change.
- **Streaming caller (`launcher.shell_invoker`):** wires a git-delta check.
  Capture the baseline once before attempt 1; on each retry, diff the current
  changed-paths set (scoped to `get_active_spawn_cwd()`) against it. A non-empty
  delta of **tracked or untracked-non-ignored** paths = a partial mutation.
  Gitignored writes (run-log, `.plan-tool/telemetry`) do not appear in porcelain,
  so they don't false-trigger.

### The STOP response (A)

- On a detected partial mutation, do **not** retry. Return the attempt as a
  terminal failure with a clear, actionable hint: partial edits were left in the
  tree; resolve them (e.g. `git checkout`/commit/inspect) and re-run the step.
- Preserve the exit-code convention — a failure-to-complete exits non-zero as
  usual; this changes *when* a transient becomes terminal, not the rc contract.

### Structure B as a policy swap (build the seam, defer the restore)

- Shape the response as a policy value (`stop` vs `restore`) so a future change
  adds the restore branch without touching the detection seam or its callers.
- Do **not** implement the restore/snapshot mechanism in this plan unless the
  author elects to land A+B together; if deferred, leave a `BACKLOG.md` (not
  `BUG_BACKLOG.md`) entry naming the restore-policy follow-up, since it's
  forward-looking work, not an outstanding bug once A closes the corruption.

## Out of scope

- **Option C (session-resume).** Rejected: per-backend contract work
  (`backend.py` + fixtures for claude/codex/cursor), a weaker correctness
  guarantee than a hard restore, and an aborted stream frequently emits no
  `session_id` to resume against — record this rationale, don't build it.
- **The batch/audit path.** It is already idempotent; only wire it to the no-op
  seam.
- **Changing the failure classifier** (`claude_errors.py`). The set of TRANSIENT
  classes is unchanged; this plan guards the *response* to a transient, not the
  classification.
- **`--commit`'s per-green-step semantics.** Untouched; the guard reads git
  state, it does not add commits.

## Risks

- **False-abort on incidental writes.** Severity: UX. If the guard counts a
  gitignored run-log/telemetry write as a mutation it would refuse a legitimate
  retry. Mitigation: scope the delta to tracked + untracked-non-ignored paths
  (porcelain already omits ignored files); add a test with a gitignored write
  during the aborted turn that must **not** trip the guard.
- **Baseline captured too late.** Severity: correctness. The baseline must be
  snapshotted **before attempt 1**, or the first attempt's own edits hide in the
  baseline and the guard never fires. Mitigation: capture at loop entry / first
  `run_once`; test a first-attempt partial-edit-then-abort.
- **Resilience regression (A only).** Severity: scoping. Refusing the retry
  turns some previously-recovered transients into surfaced failures. This is the
  deliberate trade for correctness; document it in `RUNBOOK.md`/`docs/RUN_FLOW.md`
  and leave B as the resilience-restoring follow-up.
- **Leaf purity.** Severity: architecture. `rate_limit_loop.py` must stay
  stdlib-only with no first-party import. Mitigation: the seam is a plain
  callable injected by each caller; add no `plan_tool` import to the leaf.

## Acceptance criteria

- `run_with_rate_limit_recovery` consults an injected retry-guard seam on the
  TRANSIENT arm only; the leaf gains no first-party import.
- On the streaming `run`/`detail` path, a transient failure whose aborted turn
  left uncommitted tracked/untracked-non-ignored edits **does not** re-drive the
  prompt; it surfaces as a terminal failure with an actionable hint, and the
  double-apply no longer occurs.
- The batch/audit path wires the seam to a no-op and behaves byte-for-byte as
  before (covered by a test).
- A gitignored write during the aborted turn does **not** trip the guard.
- The baseline is captured before the first attempt (test: first-attempt
  partial-edit-then-abort is caught).
- The response is shaped as a `stop`/`restore` policy so B (snapshot-restore) is
  a later branch, not a rewrite; if B is deferred, a `BACKLOG.md` entry names the
  follow-up.
- The exit-code convention is preserved (rc reflects completion, not findings).
- The plan's final step **updates `BUG_BACKLOG.md`**: removes the transient-retry
  RISK entry when the corruption is closed, or downgrades it to name exactly
  what remains if B is deferred.
- `docs/RUN_FLOW.md` (and `RUNBOOK.md` if operator-facing recovery changes) note
  the new terminal-on-partial-mutation behavior.
