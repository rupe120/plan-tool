> **Auto-archived**: this plan was swept on 2026-07-12 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 1 — Add a retry-guard seam and `stop`/`restore` policy to `run_with_rate_limit_recovery`

## Summary

Add one injected callback, `retry_guard`, to `plan_tool/rate_limit_loop.py:run_with_rate_limit_recovery`, consulted **once, whenever the loop predicts a re-invoke** (`will_retry_rate_limit or will_retry_transient`), placed before the recovery arms so it runs before any backoff or rate-limit wait — so one check covers every retry arm (transient backoff **and** rate-limit wait/switch/ASK-switch), since all of them re-invoke the same `run_once`. The guard returns a small policy value (`RetryDecision` carrying a `RetryPolicy` of `RETRY` or `STOP`) so the leaf can refuse to blindly re-drive. This step ships only the leaf-side plumbing and the `STOP` branch (surface the guard's hint, return the prior attempt as terminal — no sleep, no re-invoke); the git-delta detection that decides `STOP` lands caller-side in step 2, and the batch no-op wiring in step 3. The seam defaults to "always retry" so the two existing callers (`shell.claude_invoke`, `launcher.shell_invoker`), which don't pass it yet, behave the same. The leaf stays stdlib-only with no first-party import, and the `stop`/`restore` policy (response B's restore) lives **caller-side**, not in the leaf — the leaf seam only ever returns `RETRY`/`STOP`. Files touched: `plan_tool/rate_limit_loop.py` and `tests/test_rate_limit_loop.py`.

## Table of Contents

- [Why](#why) — the transient double-apply bug this seam exists to stop
- [Files (creates vs edits)](#files-creates-vs-edits) — the two files this step edits
- [Implementation](#implementation) — the seam shape, where it's consulted, and the invariants to hold
- [Tests](#tests) — leaf unit tests to add and the green-before-done gate
- [Acceptance criteria](#acceptance-criteria) — checkable behaviors on green
- [References](#references) — the docs relevant to this leaf-side step
- [Deferred](#deferred) — what this step deliberately leaves to steps 2–4

## Why

Today the leaf re-invokes `run_once` unconditionally after a retry — not only on the TRANSIENT arm's backoff, but also on the RATE_LIMIT arm's wait path and its SWITCH / ASK-switch paths, all of which loop back to the same `run_once`. On the streaming `run` path that re-invoke is a fresh `claude -p` session against whatever the aborted turn left in the working tree, so a turn that applied partial edits and then aborted (as a transient *or* a usage-limit/429) gets its edits re-applied on top of the partial ones — a double-apply that lands as a green step and corrupts the committed diff (the outstanding `RISK` entry in `BUG_BACKLOG.md`). The fix needs a place to say "a retry here would re-drive a partially-mutated tree — don't." The leaf is stdlib-only and knows nothing about git or `repo_root`, so that decision has to be **injected**. This step adds the injection point (at the shared re-invoke) and the `STOP` response; the actual git-delta check is caller work (step 2), and the batch path stays unchanged by wiring the seam to a constant (step 3).

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/rate_limit_loop.py` — add the `RetryPolicy` enum and `RetryDecision` value type; add the `retry_guard` keyword-only param (default preserves current behavior); consult it once when the loop predicts a re-invoke (`will_retry_rate_limit or will_retry_transient`), before the recovery arms, and dispatch on the returned policy.
  - `tests/test_rate_limit_loop.py` — extend the `drive` harness with a `retry_guard` seam and add unit tests for the new branch (guard consulted on every re-invoke — transient and rate-limit — but not on the first attempt or on a terminal-without-re-invoke path; `STOP` refuses the re-drive, `RETRY` behaves as today, default keeps current behavior).

## Implementation

**Add a neutral decision vocabulary to the leaf.** Mirror the existing `AttemptCategory` / `RecoveryAction` style already in `plan_tool/rate_limit_loop.py`:
- A `RetryPolicy` enum (`str, Enum`) with exactly two members: `RETRY` (proceed with the re-invoke — today's behavior) and `STOP` (refuse the retry, surface a hint, return terminal). Do **not** add a `RESTORE` member: the leaf is stdlib-only and cannot restore a tree, so a leaf `RESTORE` branch would be inert. Response B's restore lives **caller-side** (the launcher guard closure has git): on a dirty tree it restores to its snapshot and returns `RETRY`, so B adds no leaf member — the leaf contract stays `RETRY`/`STOP` forever.
- A small frozen `RetryDecision` (fields: `policy: RetryPolicy`, `hint: str = ""`). The `hint` lets the caller supply the partial-mutation message (e.g. "uncommitted edits were left in the tree; discard them with `git restore` / `git checkout` and re-run the step, or accept them as complete — do **not** commit-then-re-run"), since the leaf is caller-agnostic and can't author that text. Provide a module-level always-retry singleton (e.g. `ALWAYS_RETRY = RetryDecision(RetryPolicy.RETRY)`) so the default path allocates nothing.

**Add the seam to the signature.** Add a keyword-only `retry_guard: Optional[Callable[[Any], RetryDecision]] = None` beside the other injected seams. The argument the guard receives should be the opaque `outcome` of the attempt that just failed and triggered this re-invoke (the same shape `on_nonsuccess`'s first arg carries). Note the streaming guard will likely **ignore** `outcome` and read git state instead — that's expected; pass it anyway for parity and future use.
- **The default must preserve current behavior.** Both callers (`plan_tool/shell.py` at the `run_with_rate_limit_recovery(` call, `plan_tool/launcher.py` at the `run_with_rate_limit_recovery(` call) do **not** pass `retry_guard` yet — steps 3 and 2 wire it. So `None` (or the `ALWAYS_RETRY` singleton) must mean "retry as today," or this step breaks both callers.

**Consult the guard once, before any recovery arm re-drives.** Every retry arm — the TRANSIENT backoff, the RATE_LIMIT wait, and the SWITCH / ASK-switch paths — ends by re-invoking `run_once`. Rather than one check per arm, gate on the loop's *already-computed* prediction that a re-invoke is coming: `will_retry_rate_limit or will_retry_transient` (lines 114–122). Put the consult **after** that prediction (and after the existing `on_nonsuccess` call) and **before** the rate-limit/transient arms, so it runs before any wait or backoff — not after. Recommended shape:
- When a re-invoke is predicted (`will_retry_rate_limit or will_retry_transient`), resolve the decision: `decision = retry_guard(outcome) if retry_guard is not None else ALWAYS_RETRY`.
  - `STOP` → `notify(decision.hint or result.hint, kind="info")` and `return result.rc, result.payload` — the just-failed attempt's result, returned as terminal. Do **not** wait, **not** back off, **not** re-invoke. This is the "retry becomes terminal" change, and it keeps the rc contract (rc still reflects the attempt's completion, not a finding).
  - `RETRY` → fall through to the existing recovery arms unchanged.
- **One check covers all arms, before the wait.** Because the gate is the shared "a retry is coming" prediction and it sits before the arms, a single consultation covers transient *and* rate-limit (wait/switch/ASK-switch) re-invokes — the identical double-apply the HIGH `rate-limit-arm-redrive` finding named — and it refuses **before** paying the backoff or the (potentially long) rate-limit wait. Because restore is caller-side, B is a later branch in the launcher closure, not a new leaf arm here.
- **Guard placement invariants:**
  - **Only where a re-invoke would otherwise happen.** Gating on `will_retry_rate_limit or will_retry_transient` means the guard is not consulted on `SUCCESS` (returns earlier) or on any terminal-without-re-invoke path (transient budget spent, rate-limit already retried once / recovery disabled, context overflow, unknown non-zero — all have both predictions false and `return` from the body). It is also never consulted before attempt 1's own initial `run_once` (there's no failure yet). It *is* consulted after a first attempt that fails-and-predicts-retry — which is exactly what catches a first-attempt partial-edit-then-abort (the streaming guard reads a non-empty delta vs the pre-attempt baseline).
  - Leave `on_nonsuccess` and its predictive `will_retry` **unchanged.** `on_nonsuccess` fires just before this consult with `will_retry_*` as the budget prediction; a guard that then `STOP`s does not retroactively flip that already-emitted signal. That's acceptable and deliberate: the only caller that can return `STOP` is launcher, whose `on_nonsuccess` is empty; shell wires the guard to always-retry and never reaches `STOP`. Do not thread the guard's decision back into `on_nonsuccess` — it would change shell's canary/raw-nonzero surface ordering, which steps 2/3 depend on.

**Foundational logic and where it lives.** The core rule this step adds is "before re-driving *any* retry, ask an injected policy whether to." After BACKLOG #101 the rate-limit/transient control flow has a **single home** — this leaf; `plan_tool/shell.py` and `plan_tool/launcher.py` route through it and carry no separate retry arm (confirmed: their only reference to the loop is the `run_with_rate_limit_recovery(` call site). So there is no duplicate branch to also change, and guarding the one shared re-invoke covers every arm — the seam is added once here and each caller wires it in steps 2/3.

**Leaf purity.** The new enum, dataclass, and callable are all stdlib. Add **no** `plan_tool` import — `test_leaf_has_no_first_party_runtime_import` greps the whole source for a column-0 `^(from|import) plan_tool` and also loads the module in isolation to assert nothing under `plan_tool.` leaks. Keep the new types local to the leaf; the caller maps its own git result onto `RetryDecision`, the leaf never imports git or `repo_root`.

## Tests

All tests live in `tests/test_rate_limit_loop.py` and drive the leaf directly through the `drive` harness. First extend `drive` to accept a `retry_guard=None` param and forward it into `run_with_rate_limit_recovery`; a recording spy (append the received `outcome`) makes "was the guard consulted?" assertions cheap.

Cases to add (each one line):
- `test_transient_guard_stop_refuses_retry` — a transient (attempt 1) whose guard returns `STOP` does not re-invoke: `run_once_attempts == [1]`, `sleeps == []`, result is the transient's `(rc, payload)`, and the guard's hint is notified. (Attempt-1 failure ⇒ this also pins the guard catches a first-attempt abort.)
- `test_transient_guard_retry_behaves_as_today` — a transient whose guard returns `RETRY` retries with the same backoff the existing transient tests prove (guard recorded once with the opaque outcome; result reaches the later `success`).
- `test_rate_limit_guard_stop_refuses_reinvoke` — a `RATE_LIMIT` whose guard returns `STOP` does not re-invoke **and does not pay the wait**: `run_once_attempts == [1]`, `wait`/`sleep` not called, result is the rate-limit attempt's `(rc, payload)`, hint notified. This is the HIGH `rate-limit-arm-redrive` coverage — the guard now covers the rate-limit arm, not only the transient arm.
- `test_rate_limit_guard_retry_waits_then_reinvokes` — a `RATE_LIMIT` whose guard returns `RETRY` waits and re-invokes exactly as today (guard recorded once; behavior matches the existing rate-limit-then-success oracle).
- `test_guard_not_consulted_on_success` — a first-attempt `SUCCESS` with a recording guard leaves the guard un-called (returns before the predicted-retry gate; also pins "not consulted before attempt 1's own call").
- `test_guard_not_consulted_when_transient_budget_exhausted` — the last transient (budget spent, `will_retry_transient` false) goes terminal without consulting the guard.
- `test_guard_not_consulted_on_terminal` — a terminal unknown-non-zero (both predictions false) returns without consulting the guard.
- `test_default_no_guard_preserves_retry` — with `retry_guard=None`, the existing transient- and rate-limit-retry behavior is unchanged (the existing `test_transient_retries_with_exponential_backoff` / `test_transient_gives_up_after_max_attempts` and the rate-limit oracles stay green unmodified).
- `test_guard_stop_skips_backoff_and_wait` — `STOP` returns before any `sleep` **or** `wait`, pinning that the guard is consulted before both the transient backoff and the rate-limit wait.
- `test_leaf_has_no_first_party_runtime_import` — existing test stays green; the new types are stdlib, so no import is added.

### Test-creation order (feature step)

This is a **feature** step. Write the new leaf tests above alongside the implementation, each covering one branch of the new seam. Green-before-done gate: every new test in `tests/test_rate_limit_loop.py` passes, and the existing characterization tests in that file (the rate-limit, transient, and no-first-party-import pins) stay green unmodified before this step is considered finished.

## Acceptance criteria

- `run_with_rate_limit_recovery` accepts an injected `retry_guard` seam and consults it **once when a re-invoke is predicted** (`will_retry_rate_limit or will_retry_transient`), before the recovery arms — so it covers the transient backoff **and** the rate-limit wait/switch/ASK-switch arms.
- When the guard returns `STOP`, the loop does not sleep, does not wait, does not re-invoke, and returns the just-failed attempt's `(rc, payload)` as terminal, notifying the guard's hint.
- When the guard returns `RETRY` (and when no guard is passed), the transient and rate-limit paths behave exactly as before — existing tests pass unmodified.
- The guard is never consulted on `SUCCESS`, on a terminal-without-re-invoke path (transient budget spent, rate-limit already-retried/recovery-disabled, context overflow, unknown non-zero), or before attempt 1's own initial call.
- The response is a `RetryPolicy` of `RETRY`/`STOP` only (no `RESTORE` member); response B's restore lives caller-side, so B is a later branch in the launcher closure, not a rewrite of the leaf signature or its callers.
- The leaf gains no first-party import — `test_leaf_has_no_first_party_runtime_import` stays green.
- The exit-code convention holds: rc reflects the attempt's completion, not a finding.
- All new tests in `tests/test_rate_limit_loop.py` are green.

## References

- [Python - subprocess module Documentation](https://docs.python.org/3/library/subprocess.html) — Popen/run and return codes, context for why the leaf's `run_once` re-invoke is a fresh subprocess this seam guards against re-driving.
- [Claude Code — Headless / Non-interactive mode](https://docs.claude.com/en/docs/claude-code/headless) — `claude -p` fresh-session-per-invoke behavior, the reason a naive transient retry re-applies edits over a partial tree.

## Deferred

- **The git-delta detection that decides `STOP`** — owned by step 2 (`plan_tool/launcher.py`): capture a baseline before attempt 1 and diff the changed-paths set (scoped to `get_active_spawn_cwd()`, tracked/untracked-non-ignored only) on each predicted re-invoke. This step only provides the seam and the `STOP` branch it drives.
- **Batch no-op wiring** — owned by step 3 (`plan_tool/shell.py`): wire the seam to a constant always-`RETRY` decision so proposals (which never mutate the tree) keep their behavior unchanged.
- **Response B (snapshot + restore + retry)** — the caller-side restore branch (in the launcher guard closure, which has git): restore to the pre-attempt snapshot, then return `RETRY`. The leaf needs no change for B; a `BACKLOG.md` entry names the follow-up (owned by step 4's docs/backlog reconciliation).
- **Docs and `BUG_BACKLOG.md` closure** — owned by step 4 (`docs/RUN_FLOW.md`, `RUNBOOK.md`, `BUG_BACKLOG.md`, `BACKLOG.md`), including the seam-by-seam contract note for the new `retry_guard`.
