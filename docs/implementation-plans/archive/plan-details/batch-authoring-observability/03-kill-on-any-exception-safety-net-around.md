> **Auto-archived**: this plan was swept on 2026-08-18 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 3 — Add a kill-on-any-exception safety net around the shared runner's proc.wait()

## Summary

`plan_tool/backend_runner.py:run_streaming_once` (moved from `launcher.py` in step 2) wraps its child process's `proc.wait()` in a bare `try/finally` that only stops the heartbeat thread — it never touches the child itself. Any exception raised while `proc.wait()` is blocked, most commonly a `KeyboardInterrupt` from Ctrl-C, leaves the backend child running and leaves the two non-daemon stdout/stderr pump threads blocked reading its still-open pipes. This step adds an `except BaseException` arm around that same `proc.wait()` call that kills the child and reaps it before re-raising, matching the kill-then-raise guarantee `subprocess.run` already gives the batch path today (`plan_tool/shell.py:_run_once`). The exception itself is not classified or renamed here — it propagates unchanged; the closed termination-reason vocabulary is step 4's job. `run` is the only caller that reaches this function today (the batch lane isn't wired onto it until step 6), so this is new, real protection for `run`'s own Ctrl-C handling, not merely carrying forward an existing guarantee.

## Table of Contents

- [Summary](#summary) — what changes and why it matters now, before the safety net exists
- [Why](#why) — the two-part failure this step closes: an orphaned child and threads that block process exit
- [Input](#input) — the shape step 2 hands this step, and the recovery loop's existing non-catching contract
- [Files (creates vs edits)](#files-creates-vs-edits) — both files step 2 already created
- [Implementation](#implementation) — the except arm, the reap, and what stays untouched
- [Tests](#tests) — the new fakes and cases this step adds
- [Acceptance criteria](#acceptance-criteria) — observable, checkable facts
- [References](#references) — subprocess and signal semantics behind the fix
- [Applicable guardrails](#applicable-guardrails) — the plan fences this step's new behavior sits inside
- [Deferred](#deferred) — what stays out, and which later step covers it

## Why

Today, `run_streaming_once`'s only protection around the child process is the heartbeat thread's own silence-triggered kill ladder (`terminate()`, then `kill()` after a grace window) — a *detected-stall* mechanism, not an *unwind* mechanism. The block around the blocking call itself is:

```python
try:
    proc.wait()
finally:
    stop.set()
```

`finally` only signals the heartbeat thread to stop polling; it never touches `proc`. If `proc.wait()` raises — a `KeyboardInterrupt` from an operator's Ctrl-C is the case this step's test proves, but the same gap exists for any other exception — the function exits with the child still alive and its stdout/stderr pipes still open.

That's worse than a leaked background process. `t_out` and `t_err`, the stdout/stderr pump threads, are plain (non-daemon) `threading.Thread` instances blocked in `for line in proc.stdout:` / `for line in proc.stderr:`, which only return once the child's pipes close — i.e., once the child exits. CPython does not let the interpreter exit while a non-daemon thread is still running. So an unhandled exception here doesn't just orphan the child in the background: it can leave plan-tool's own process unable to exit at all, still waiting on `t_out.join()`/`t_err.join()` (which today never even run on this path, since they sit after the `try/finally`, not inside it) for pipes that won't close until a child nobody killed exits on its own. The existing code already anticipated half of this — the heartbeat thread is deliberately `daemon=True` "so an exception elsewhere can't leave it pinning the process" — but that comment only covers the heartbeat thread itself; the pump threads and the child process have no equivalent protection.

`plan_tool/shell.py:_run_once`, the batch lane's current path, doesn't have this problem, but not because it does anything special — `subprocess.run` at that call site already wraps its own internal `process.communicate()` in a bare `except: process.kill(); raise`. The batch path inherits kill-on-any-exception for free, simply by being built on `subprocess.run`; the streaming runner never had it, because it was written around a raw `proc.wait()` instead. This step gives the streaming runner the same guarantee `subprocess.run` already provides, so `run` ends up no worse off than the batch lane is today — and, per the plan's Architecture "allowed behavior changes" item 2, this is deliberately new, real behavior for `run`'s own call sites, not merely an extraction carrying forward something that already existed.

The batch lane doesn't reach `run_streaming_once` yet — that's step 6 — so this step's audience is `run` alone. But because the net lives inside the shared function itself rather than in a per-caller wrapper, step 6 inherits it automatically the moment `claude_invoke` starts calling the same function; no batch-specific code is needed later for this particular guarantee.

## Input

- **Step 2 produces `plan_tool/backend_runner.py:run_streaming_once(prompt, transport, *, run_logger=None, phase="claude_call", attempt=1, sibling_log_dir=None)`** — the relocated Popen supervisor, byte-compatible with `run`'s pre-move behavior. This step edits only the block around `proc.wait()`; every other part of the function (the `_pump_stdout`/`_pump_stderr`/`_heartbeat` closures, the `stop`/`killed_fired`/`stall_fired` state, the thread creation and `contextvars.copy_context()` wiring) is Input, not something this step rewrites.
- **The heartbeat's own kill ladder** (inside the `_heartbeat` closure) already guards its `proc.terminate()`/`proc.kill()` calls with `except (OSError, ProcessLookupError): pass`, because the child can already be gone by the time it fires. This step's own kill call needs the identical guard, for the identical reason — a race against the heartbeat thread's own kill, or a child that already exited on its own.
- **`plan_tool/rate_limit_loop.py:run_with_rate_limit_recovery`'s call to `run_once(current_attempt)`** has no exception handling around it today — an exception from `run_once` (for `run`'s lane, `shell_invoker`'s `_run_once_seam`, which calls `run_streaming_once` directly) already propagates untouched. This step relies on that fact: it doesn't need to add or change any handling in the recovery loop for the re-raised exception to reach `run`'s CLI layer unchanged.

## Files (creates vs edits)

Both files are step 2's `creates:`; this step only edits them.

- `plan_tool/backend_runner.py` — add the `except BaseException` arm around `run_streaming_once`'s `proc.wait()` call; move the existing post-wait `t_out.join()` / `t_err.join()` / `t_hb.join(timeout=...)` calls into the same `finally` so they run on both the normal and the exception path.
- `tests/test_backend_runner.py` — add a fake process whose `wait()` raises on its first call (mirroring the `_HangingProc`/`_StubbornProc` shape `TestRunStreamingOnceStreamJson`'s existing silence-kill tests already use) and the cases listed under Tests.

## Implementation

**The gap is narrow and specific: only the `try: proc.wait() finally: stop.set()` block.** Nothing before it (the `Popen()` call itself, the thread starts, the optional `proc.stdin.write()`) is this step's concern — a spawn-time exception there raises straight out today with `proc.wait()` never reached, and the plan's own step 4 names wrapping `Popen()` itself as its own work, not this step's. State that boundary rather than silently expanding this step to cover it.

**One way to shape the fix**, keeping the file's existing defensive style (the heartbeat's own `except (OSError, ProcessLookupError): pass` around its `terminate()`/`kill()` calls, and the bare `except BaseException:` pattern already used elsewhere in this repo, e.g. `plan_tool/fileio.py`'s atomic-write cleanup):

```python
try:
    proc.wait()
except BaseException:
    try:
        proc.kill()
    except (OSError, ProcessLookupError):
        pass
    proc.wait()  # reap; safe even if the heartbeat already killed it
    raise
finally:
    stop.set()
    t_out.join()
    t_err.join()
    t_hb.join(timeout=_PROGRESS_INTERVAL_S + 1.0)
```

The parts that are not free to vary:

- **The except clause must be `except BaseException`, not `except Exception`.** `KeyboardInterrupt` (what SIGINT becomes on the main thread) does not inherit from `Exception`, so `except Exception` would silently skip the one case this step's test names.
- **Kill, don't terminate-then-wait-then-escalate.** The heartbeat's own kill ladder is a *detected-stall* mechanism that deliberately gives the child a grace window to exit cleanly on SIGTERM before escalating. This step's net fires only once the caller is already unwinding for an unrelated reason — there's no reason to wait on it, and `subprocess.run`'s own bare-except path (the parity target) calls `process.kill()` directly with no grace period either.
- **Guard the kill call itself.** `proc.kill()` can raise `ProcessLookupError`/`OSError` if the child is already gone — a real race against the heartbeat thread's own kill ladder, which can be mid-flight on another thread at the exact moment the main thread's `proc.wait()` raises. Swallow it the same way the heartbeat does; don't let it mask the exception this block exists to propagate.
- **Reap after killing.** `SIGKILL` cannot be blocked, so the follow-up `proc.wait()` call returns essentially immediately and needs no timeout of its own — but skipping it leaves a zombie process entry until something else reaps `proc`, which is exactly the kind of orphaned state this step exists to close.
- **Moving the three `join()` calls into `finally` is required, not optional, for the fix to actually protect process exit.** They currently run only after the `try/finally` block completes normally — on the exception path they never execute at all today, which is the second half of the Why section's failure mode (the pump threads stay unjoined, not just the child unkilled). Once the child is killed, the pipes it holds close, so `t_out`/`t_err` finish draining and the joins return quickly instead of hanging.
- **Don't change what the function returns on the success path, and don't have it return anything on the exception path** — it re-raises, so no `(rc, stdout, stderr, stats)` tuple is meaningful there. The code after the `try/finally` (the `sibling_log_dir` transcript write and the final `return`) already only runs when the `try/finally` completes without propagating, which stays true unchanged.
- **No termination-reason classification, no new run-log event, no change to `claude_errors.py` or `run_log.py`.** The re-raised exception is exactly the exception `proc.wait()` raised — step 4 is where a caught exception first gets sorted into `operator_interrupt`/`unknown`/etc. and bridged into `ClaudeFailureKind`.
- Consider updating `run_streaming_once`'s docstring to note it can now raise instead of returning when `proc.wait()` fails — a small, non-mandatory addition, not an acceptance criterion.

## Tests

### Tests for this step

- `test_keyboard_interrupt_during_wait_kills_and_reaps_the_child` (`tests/test_backend_runner.py`, `TestRunStreamingOnceStreamJson`) — a fake `Popen` double whose `wait()` raises `KeyboardInterrupt` on its first call asserts `terminate`/`kill` was called and that the raised exception is `KeyboardInterrupt`, propagated out of `run_streaming_once` unchanged (same type, not wrapped or swallowed).
- `test_non_keyboard_interrupt_exception_during_wait_also_kills_the_child` — the same fake, but `wait()` raises a plain `OSError` on its first call, proving the net isn't limited to `KeyboardInterrupt` — matches this step's own "any exception" intent, not only the operator-interrupt case step 4 later names.
- `test_kill_guards_against_already_exited_child` — the fake's `kill()` raises `ProcessLookupError`; asserts the *original* exception (not the `ProcessLookupError`) is what propagates, proving the guard around the kill call doesn't mask the real failure.
- `test_exception_during_wait_still_joins_pump_and_heartbeat_threads` — asserts the call raises (and thus returns control) without hanging once the child is killed, and that the heartbeat's `stop` event was set — the regression proof for the second half of Why (threads left unjoined on today's exception path).
- `test_shell_invoker_propagates_keyboard_interrupt_with_child_killed` (`tests/test_backend_runner.py`) — drives the same fake through `launcher.shell_invoker` (not the raw runner) by patching `subprocess.Popen` via `plan_tool.backend_runner.subprocess` (the module the real `Popen()` call now lives in after step 2's move — equivalent to patching `launcher.subprocess`, since both names reference the same `subprocess` module object, but patching at the runner's own module keeps the test grounded in where the call actually happens). Asserts the `KeyboardInterrupt` still reaches the caller unchanged (`rate_limit_loop.run_with_rate_limit_recovery` doesn't swallow or retry it) and that `kill()` was called on the fake. This is the "through `run`'s actual call path" half of the plan's own per-step test-strategy line for step 3; the batch lane isn't reachable yet (step 6), so that line's "for both lanes" is proven here as "at both the raw-runner level and through `run`'s existing caller" — the two levels that actually exist at this point in the plan.
- Every existing case in `TestRunStreamingOnceStreamJson` (the silence-kill tests included) stays green with no changes to their bodies — the new `except` arm must not alter the return value or timing on any path that doesn't raise.

Every test above, plus the full pre-existing `tests/test_backend_runner.py` roster, must be green before this step is done.

## Acceptance criteria

- A `KeyboardInterrupt` raised from inside `proc.wait()` results in `proc.kill()` (or an equivalent kill call reaching the fake process's hook) being invoked before the exception leaves `run_streaming_once`.
- The same holds for at least one non-`KeyboardInterrupt` exception type, proving the net isn't interrupt-specific.
- The original exception instance/type is what propagates — nothing wraps, replaces, or reclassifies it.
- `proc.kill()` raising `ProcessLookupError`/`OSError` does not prevent the original exception from propagating.
- `t_out.join()`, `t_err.join()`, and `t_hb.join(...)` all run on the exception path (verified by the test completing rather than hanging once the fake's `wait()`/pipes resolve after the kill).
- `launcher.shell_invoker` (and, transitively, `rate_limit_loop.run_with_rate_limit_recovery`) still lets a `KeyboardInterrupt` from `run_streaming_once` propagate out unchanged — no retry, no swallow.
- The success path (no exception raised) is byte-identical to before this step: same return tuple, same join order, same timing.
- `plan_tool/backend_runner.py` still imports no first-party module besides `plan_tool.backend` and `plan_tool.run_log` (`test_leaf_has_bounded_first_party_imports` from step 2 stays green with no changes).
- `uv run pytest tests/test_backend_runner.py tests/test_launcher.py tests/test_shell.py -q` passes; `uv run pytest tests/ -q -n auto` passes.
- `git diff --stat` against this step's base commit touches only `plan_tool/backend_runner.py` and `tests/test_backend_runner.py`.

## References

- [subprocess — Subprocess management (Python 3.13)](https://docs.python.org/3/library/subprocess.html) — `Popen.wait`/`terminate`/`kill` semantics and the reap requirement after a kill; also the reference for `subprocess.run`'s own bare-except-then-kill behavior this step matches.
- [signal — Set handlers for asynchronous events (Python)](https://docs.python.org/3/library/signal.html) — confirms SIGINT becomes `KeyboardInterrupt` on the main thread specifically, which is why the exception surfaces inside `proc.wait()` on the same thread running this function, not on a background thread.

## Applicable guardrails

- **Architecture's "allowed behavior changes" bullet, item 2** — explicitly licenses this step's new behavior for `run`'s call sites ("`run`'s call sites gain the kill-on-any-exception net step 3 adds"). Without that item, this step would read as a violation of step 2's byte-compatibility promise; cite it as the reason this step is allowed to change `run`'s observable behavior when step 2 deliberately couldn't.
- **Architecture's ordering-constraint bullet** — places this kill-on-any-exception net as a baseline that must land as part of the extraction, before richer interrupt classification (`operator_interrupt`, step 4) exists. This step must not wait for or depend on step 4's vocabulary; it kills and re-raises the exception exactly as received.
- **Plan's "## Out of scope"** — this step must not add termination-reason classification, a new run-log event, or any roadmap-specific behavior; the batch lane isn't reachable through this function yet.

## Deferred

- Classifying the exception into the closed termination-reason vocabulary (`operator_interrupt`, `unknown`, etc.) and bridging a runner-initiated kill into `claude_errors.ClaudeFailureKind` — step 4.
- Wrapping the `Popen()` call itself (a spawn-time failure before `proc.wait()` is ever reached) — step 4's own scope names this explicitly; this step's net starts at `proc.wait()`, not before it.
- A configured-timeout kill, and the per-caller silence-threshold override hook — step 4.
- Any new run-log event (`backend_spawn`, `backend_termination`, `run_interrupted`) recording that this kill happened — steps 5, 7, 9.
- Wiring the batch lane (`plan_tool/shell.py:claude_invoke`) onto `run_streaming_once` — step 6; until then, `run` is the only caller this net protects.
- A clean, non-traceback Ctrl-C exit with code 130 at the CLI layer — step 8 (`plan_tool/cli/roadmap_cmd.py`, `plan_tool/cli/run_cmd.py`); this step only guarantees the child is killed, not the process's own exit code.
