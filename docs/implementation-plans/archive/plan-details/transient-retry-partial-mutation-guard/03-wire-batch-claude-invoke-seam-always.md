> **Auto-archived**: this plan was swept on 2026-07-12 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 3 — Wire the batch `claude_invoke` seam to an always-retry constant and pin byte-for-byte behavior

## Summary

Wire `plan_tool/shell.py:claude_invoke`'s call into `run_with_rate_limit_recovery` to step 1's always-retry singleton for the new `retry_guard` seam, making the batch path's "never refuse a transient retry" decision explicit at the call site. The batch (authoring/audit/jira/lessons/annotate) path runs proposal turns that don't edit the working tree, so it needs no git-delta guard — the streaming counterpart (step 2, `launcher.py:shell_invoker`) owns the real partial-mutation check. The only production change is one added keyword argument in the `run_with_rate_limit_recovery(...)` call inside `claude_invoke`; the two files touched are `plan_tool/shell.py` and `tests/test_shell.py`. On green, every existing transient-retry behavior in the batch path is unchanged and a new test pins that the batch path passes the always-retry constant so a future edit can't silently start stopping batch retries.

## Table of Contents

- [Why](#why) — why the batch path opts out of the guard
- [Input](#input) — step 1's `retry_guard` seam and singleton this step consumes
- [Files (creates vs edits)](#files-creates-vs-edits) — the two files this step edits
- [Implementation](#implementation) — the one-line wire, the explicit-vs-default choice, invariants
- [Tests](#tests) — the pass-unchanged pins plus one wiring test
- [Acceptance criteria](#acceptance-criteria) — checkable behaviors on green
- [References](#references) — the docs relevant to this wiring step
- [Deferred](#deferred) — what this step deliberately leaves out

## Why

Step 1 adds a `retry_guard` seam to `plan_tool/rate_limit_loop.py:run_with_rate_limit_recovery`, consulted whenever the loop predicts a re-invoke (covering the transient and rate-limit arms), defaulting to an always-retry singleton so un-wired callers behave the same. Step 2 wires the streaming caller (`plan_tool/launcher.py:shell_invoker`) with a real guard that stops a transient- or rate-limit re-drive when the aborted turn left uncommitted edits — the double-apply the whole plan exists to stop. The batch caller `plan_tool/shell.py:claude_invoke` is different: it runs authoring/audit proposal turns (create, detail, jira, lessons, annotate) that don't edit the repo working tree, so re-driving there can't double-apply partial edits regardless of arm. This step makes that opt-out explicit rather than implicit-by-default, so the batch path's stance is visible at its own call site and a reader doesn't have to infer it from an omitted argument.

**Why the batch path is safe — the load-bearing assumption.** The safety rests on the batch *prompts*, not the permission mode. The batch argv (`backend.py:_claude_batch_argv`) carries the **same** `--permission-mode acceptEdits` as the streaming argv (`_claude_streaming_argv`), so nothing at the CLI level stops a batch turn from editing the tree; batch non-mutation holds only because the create/detail/jira/annotate/lessons prompts emit *proposals* the orchestrator writes, never direct edits. Wiring the always-retry constant is correct **for those prompts**. If a future batch authoring prompt ever mutates the working tree, this opt-out would re-open the double-apply the plan exists to stop, and the batch path would then need the same git-delta guard as step 2 — a `BUG_BACKLOG.md`/`BACKLOG.md` follow-up at that point, not a silent regression. Naming the assumption here keeps that trip-wire visible.

## Input

This step consumes the seam step 1 adds to `plan_tool/rate_limit_loop.py:run_with_rate_limit_recovery`. Step 1 owns that contract; follow its shipped names rather than any sketch here.

- **The `retry_guard` keyword param.** Step 1 adds it to `run_with_rate_limit_recovery` and consults it once when the loop predicts a re-invoke (`will_retry_rate_limit or will_retry_transient`), covering the transient and rate-limit arms, before any backoff or wait. This step passes step 1's always-retry singleton into that param and does not touch where or how the loop consults it — the batch path always retries regardless of arm.
- **The always-retry singleton.** Step 1 provides a module-level always-retry value (its `RetryDecision` with policy `RETRY`) and defaults `retry_guard` to it. Import that singleton from `plan_tool.rate_limit_loop` and pass it explicitly. If step 1's final singleton name differs from the sketch below, use step 1's shipped name.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/shell.py` — in `claude_invoke`, add `retry_guard=<step 1's always-retry singleton>` to the `run_with_rate_limit_recovery(...)` call inside the `contextlib.ExitStack()` block; add the singleton to the existing `from plan_tool.rate_limit_loop import (...)` block near the top of the module.
  - `tests/test_shell.py` — add one wiring test asserting the batch path hands the always-retry constant to the loop; keep the existing transient-retry pins unmodified.

## Implementation

- **Pass the always-retry singleton explicitly at the batch call site.** In `plan_tool/shell.py:claude_invoke`, the `run_with_rate_limit_recovery(...)` call lives inside the `with contextlib.ExitStack() as backend_scope:` block. Add one keyword: `retry_guard=<step 1 singleton>`. Everything else in that call stays the same.
- **Import the singleton from the leaf.** `plan_tool/shell.py` already imports from `plan_tool.rate_limit_loop` (the `run_with_rate_limit_recovery` import). Extend that same import to pull step 1's always-retry singleton — do not add a second import line for the leaf.
- **Explicit pass, not reliance on the default — the key decision.** Step 1 defaults `retry_guard` to the always-retry singleton, so omitting the argument here would produce the same runtime behavior. Pass it anyway. The explicit argument documents that the batch path *chose* to never stop a transient, matching how step 2 passes the same singleton on its inert path (no spawn cwd). The rejected alternative — leave `retry_guard` unset and rely on the default — reads downstream as "the author forgot to wire this caller", not "this caller deliberately opts out".
- **Do not add a git snapshot or any guard closure here.** The batch path is proposal-only; it must not reach for `plan_tool/launcher.py:_git_changed_paths` or `plan_tool/backend.py:get_active_spawn_cwd`. Those belong to step 2's streaming decider. This step's whole change is one constant argument.
- **Leave every wrapper-owned piece untouched.** The `shutil.which` PATH guard, `_maybe_warn_shell_prompt_budget` backstop, `resolve_on_rate_limit_policy`, the `ExitStack` + `_rate_limit_backend_scope.set/reset` scope, and the `on_nonsuccess` seam (`_on_nonsuccess_seam`, carrying shell's `_MISSED_LIMIT_CANARY` + raw-nonzero surfacings) all stay exactly as they are. This step adds an argument; it moves nothing.
- **Constraint — one keyword only.** The change is additive and must not alter the value of any other argument to `run_with_rate_limit_recovery`. If adding the keyword tempts a reorder or reformat of the call, keep the diff to the single added line.

## Tests

`tests/test_shell.py`.

### Test-creation order (feature step)

This is a thin wiring step over step 1's already-tested seam, so the existing transient-retry suite is the pass-unchanged oracle and only one new test is needed.

- `test_claude_invoke_passes_always_retry_guard_to_loop` — monkeypatch `plan_tool.shell.run_with_rate_limit_recovery` with a spy that records its kwargs and returns a fixed `(rc, stdout)`; call `claude_invoke`; assert the spy was called once with `retry_guard` set to step 1's always-retry singleton (identity check against the imported singleton). This is the guard against a future edit silently dropping the wire or swapping in a stopping guard.

Existing pins that must stay green **unmodified** (they are the byte-for-byte behavior oracle for the batch transient path):

- `test_claude_invoke_retries_transient_with_exponential_backoff` — two transient blips then success still yields three calls and `sleeps == [2.0, 4.0]`.
- `test_claude_invoke_transient_gives_up_after_max_attempts` — a persistent transient still returns after the 3-attempt budget with exactly 3 recorded `ClaudeCallEnd` events.
- `test_transient_retry_tool_plain` / `test_transient_retry_routes_through_bound_notifier` — the transient retry notice text and notifier routing are unchanged.
- `test_backstop_fires_once_per_call_not_per_retry` — a transient-forced retry still fires the prompt-budget backstop exactly once.

Green-before-done gate: the new wiring test and every listed existing pin must pass before this step is finished. A red pin here means the wire changed batch behavior — a regression, not an expected adaptation.

## Acceptance criteria

- `plan_tool/shell.py:claude_invoke` passes `retry_guard=<step 1's always-retry singleton>` to `run_with_rate_limit_recovery`, and the singleton is imported from `plan_tool.rate_limit_loop`.
- `test_claude_invoke_passes_always_retry_guard_to_loop` passes: the spy records `retry_guard` equal (by identity) to the imported always-retry singleton.
- `test_claude_invoke_retries_transient_with_exponential_backoff` and `test_claude_invoke_transient_gives_up_after_max_attempts` pass unmodified.
- No new git-state read, guard closure, or spawn-cwd lookup is added to `plan_tool/shell.py`.
- The change to `claude_invoke` is limited to the added `retry_guard` keyword and the extended leaf import; no other argument value changes.

## References

- `plan_tool/shell.py` — `claude_invoke` and its `run_with_rate_limit_recovery(...)` call site inside the `contextlib.ExitStack()` block, the one call this step adds the `retry_guard` keyword to, plus the existing `from plan_tool.rate_limit_loop import (...)` block to extend.
- `plan_tool/rate_limit_loop.py` — step 1's `retry_guard` seam on `run_with_rate_limit_recovery` and the module-level always-retry singleton this step imports and passes explicitly.
- `docs/implementation-plans/plan-details/transient-retry-partial-mutation-guard/01-retry-guard-seam-stop-restore-policy.md` — step 1's detail file, authority for the seam's shipped param and singleton names to follow over any sketch here.
- [Python - subprocess module Documentation](https://docs.python.org/3/library/subprocess.html) — reference for `subprocess.run` (batch transport, cwd, return codes) that `claude_invoke`'s `_run_once` drives per attempt and that the transient retry loop re-invokes.
- [Claude Code — Headless / Non-interactive mode](https://docs.claude.com/en/docs/claude-code/headless) — `claude -p` print mode and the fresh-session-per-invoke behavior the transient retry re-drives, the behavior this step deliberately keeps unchanged on the batch path.

## Deferred

- The real partial-mutation guard on the streaming path — owned by step 2 (`plan_tool/launcher.py:shell_invoker`); this step wires only the batch caller.
- Response B (snapshot-restore) — a caller-side branch in the streaming launcher closure (the leaf contract stays `RETRY`/`STOP`); the batch path never participates.
- Any change to `plan_tool/cli/gitcommit.py` or other batch-side git helpers — out of scope; this step touches only the `claude_invoke` call site and its test.
