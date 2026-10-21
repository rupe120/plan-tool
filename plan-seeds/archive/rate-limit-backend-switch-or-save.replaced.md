> **Replaced**: this file has been superseded by `docs/implementation-plans/2-rate-limit-backend-switch-or-save.md`.
> Preserved here for history; do not edit.

# Plan seed: at a backend rate limit, offer switch-backend / save-and-stop / wait (and make the wait itself offer them)

This file is a `plan-tool create` input. Use it via:

```
plan-tool create --from-existing plan-seeds/rate-limit-backend-switch-or-save.md
```

It is **not** itself a plan — `plan-tool create` consumes the prose below
and proposes a step decomposition; the author then runs `plan-tool detail`
per step.

---

## Guiding principle

**A rate limit is a fork in the road, not a forced wait.** Today, when the
active backend reports a rate limit, the tool's only choices are *wait for
the reset* (default) or *give up and return the failed rc* (`--no-wait-on-
rate-limit`). The operator who has a second backend available, or who would
rather stop now and resume later, has no in-flight path to either — they
must Ctrl+C, lose the wait, and re-launch by hand, guessing the right
command. Give the operator a **three-way choice at the rate limit**:

1. **Switch backend** — re-run the same call on a *different* backend
   (e.g. codex → claude) and keep going.
2. **Save & stop** — stop cleanly at the current step boundary and print the
   exact command to **resume** later (same plan, same options).
3. **Wait** — the current behavior (countdown to the reset, then retry).

And critically: **the wait must not be a dead end.** While the countdown is
running, the operator can *at any point* press a key to switch backend or
save & stop, instead of being stuck until reset or a blunt Ctrl+C.

This serves the mission's *operator-in-control* posture: the tool surfaces
the more-useful options and never traps the operator in a single
unattended behavior — while staying **byte-for-byte unchanged when there's
no TTY** (automation must never block on a menu).

## Where the rate limit is handled today (the seam to extend)

The whole rate-limit path lives in two leaves, both already injectable:

- **`plan_tool/launcher.py:shell_invoker`** (~436-498) — the retry loop. The
  RATE_LIMIT arm (~455-478) is the decision point: if `wait_on_rate_limit`
  and not already retried, it computes `target = failure.reset_epoch`
  (falling back to `DEFAULT_RATE_LIMIT_FALLBACK_SECONDS`), calls
  `wait_until_epoch(...)`, and on completion loops to retry once
  (`rate_limit_retried` caps it at a single wait). If `wait_on_rate_limit`
  is off it just returns the failed `(rc, stdout)`.
- **`plan_tool/claude_errors.py:wait_until_epoch`** (~319-387) — the
  countdown. It already accepts an injectable `cancel_check` callback
  (~361) and handles `KeyboardInterrupt` (~378), returning `False` on
  cancel/abort so the invoker returns the failed rc without retrying. The
  `00:00:00 remaining` tick loop is ~360-373.

`wait_on_rate_limit` defaults to the process-wide value set by
`set_default_wait_on_rate_limit(not args.no_wait_on_rate_limit)` in
`plan_tool/cli/app.py:535`; the per-call default is read via
`get_default_wait_on_rate_limit()` (`launcher.py:419-420`).

**This is a shared leaf seam.** `shell_invoker` is the production invoker for
*every* Claude-shelling command (`create`, `detail`, `run`, `review`,
`completeness`, reconcile, …) — not just `run`. Whatever choice mechanism
you add lights up everywhere at once. Build it once at this seam; do not
fork per-command copies. And `tests/conftest.py`'s autouse gate **raises**
if a real backend binary is spawned — keep any real-backend default out of
the leaf and inject in tests (opt out only with
`@pytest.mark.allow_real_claude`).

## Backend selection — how a switch must re-resolve

Switching is **not** a bare `set_active_backend(name)`. The CLI builds the
*effective* backend before dispatch (`app.py:447-497`):
`resolve_backend(name)` → `build_effective_backend(selected, model=…,
extra_batch_argv=…, extra_streaming_argv=…)` (splicing per-project
`.plan-tool/backends.json` overrides and the resolved model) →
`set_active_backend(effective)`. A mid-run switch must run the **same
resolution** for the new backend (resolve → effective-build → set), not
just swap the registry seed, or the new backend loses its model / extra
argv. Factor that selection sequence into a reusable helper (today it's
inline in `app.py`) so both the startup path and the mid-run switch call
one function. Validate the target name against `registered_names()` and
reject / re-prompt on an unknown or same-as-current name.

Because each Claude call is a fresh session (no cross-call context), a
switch is clean: the failed call's partial work is discarded, the loop
re-enters `_run_streaming_once` with the new active backend, and the
single-retry cap (`rate_limit_retried`) should **reset** on a switch — the
new backend gets its own fresh attempt budget, since hitting claude's limit
says nothing about codex's.

## Save & stop — what "context" means here, and the resume command

There is **no rich conversational context** to serialize — each invoker
call is a fresh backend session. The durable state is already on disk:
`run` persists per-step status in the plan frontmatter
(`StepStatus.PENDING/CURRENT/DONE`, advanced by `mark_done_and_advance`,
`launcher.py:1298`), and the next launch resumes from `current_step()` /
`next_runnable_step()` (`launcher.py:1284-1295`). So "save & stop" means:

- **Stop cleanly** at the current step boundary — the failed step's
  uncommitted work is discarded (nothing was committed), the step stays
  `CURRENT`/`PENDING`, and the loop returns without retrying.
- **Print the exact resume command** so the operator doesn't reconstruct it:
  the same subcommand + plan name + the salient flags (`--backend <chosen>`,
  `--commit`, `--all`, `--step`, etc.). If the operator picked a *different*
  backend at the save prompt, bake that backend into the printed command
  (e.g. resume with `--backend claude`).

Be precise in the plan about scope: the only first-class "resumable"
command is `run` (step state is its checkpoint). For non-`run` callers
(`create`/`detail`/`review`/…), "save & stop" degrades to *stop cleanly +
print the command to re-invoke* — there's no mid-command checkpoint to
restore, and the plan should say so rather than imply one. Do **not**
invent a new on-disk session-context format in this plan; if a richer
checkpoint is ever wanted, that's a separate seed.

## The interactive choice — behavior

When RATE_LIMIT is hit **and stdin/stderr is a TTY and the run is
interactive** (not `-y`, not non-TTY, not an unattended/CI context), present
a small menu instead of silently waiting:

```
rate limit on <backend>; reset at HH:MM (<N>s).
  (w)ait   (b) switch backend   (s)ave & stop   Ctrl+C abort
```

- `w` → fall into the existing `wait_until_epoch` countdown.
- `b` → prompt for / pick a target backend, re-resolve it (see above), and
  retry the call now.
- `s` → save & stop: return cleanly and print the resume command.

**Make the wait itself a live menu, not a blind countdown.** While
`wait_until_epoch` ticks, poll the TTY non-blockingly each tick (e.g.
`select.select([sys.stdin], …, 0)` on POSIX) so a keypress can interrupt:
the same `b` / `s` keys take effect mid-wait, and Ctrl+C still aborts. The
countdown leaf must stay testable, so the keypress source is injectable —
add a `key_check`-style callback alongside the existing `cancel_check`
(`claude_errors.py:361`), returning the pressed action (or `None`) so unit
tests drive it without a real terminal. `wait_until_epoch`'s return type
likely needs to widen from a bare `bool` to a small result that says *which*
action ended the wait (completed / cancelled / switch-backend / save-stop)
so the invoker can branch.

## Non-interactive / `-y` / non-TTY (load-bearing)

This is the safety contract. With no TTY, or under `-y`/apply-all/unattended,
the tool must behave **exactly as today**: honor `wait_on_rate_limit`
(wait, or return the failed rc) with **no prompt and no stdin read**. Never
block automation waiting on a menu keypress; never read stdin when there is
no TTY. A new non-interactive default policy (if any) must be opt-in via a
flag/env, not a silent behavior change. Gate the whole menu on the same
interactive condition the rest of the tool already uses, and add tests that
assert the non-TTY path is byte-for-byte unchanged.

## CLI surface (decide during create)

Options to consider — prefer the smallest surface that works:

- A `--on-rate-limit {wait,switch,stop,ask}` flag (and/or
  `PLAN_TOOL_ON_RATE_LIMIT` env) to set the **non-interactive** policy and
  the default the interactive menu pre-selects. `ask` = show the menu (TTY
  only). Default stays `wait` to preserve today's behavior.
- A `--fallback-backend <name>` (and/or env) so `switch` is fully
  unattended-capable: on a rate limit, auto-switch to the named backend
  without a prompt. This makes the "switch" option usable in CI, not just
  interactively.
- Keep `--no-wait-on-rate-limit` working as the existing alias for the
  "don't wait" policy; reconcile it with `--on-rate-limit` (one should map
  onto the other, not contradict it).

Whatever flags land, regenerate `docs/cli/` (drift-guarded by
`tests/cli/test_cli_reference.py`) — the source of truth is the argparse
parser (`plan_tool/cli/parser.py`, where `--no-wait-on-rate-limit` /
`--backend` live, ~141/150).

## Scope of work

1. **Selection helper** — extract the `resolve_backend →
   build_effective_backend → set_active_backend` sequence from `app.py`
   (~447-497) into a reusable function both startup and the mid-run switch
   call. No behavior change at startup.
2. **Wait loop** (`claude_errors.py:wait_until_epoch`) — add an injectable
   `key_check` callback and non-blocking TTY polling per tick; widen the
   return to carry the action that ended the wait (completed / cancelled /
   switch / save-stop). Keep `cancel_check` + Ctrl+C working.
3. **Invoker policy** (`launcher.py:shell_invoker` RATE_LIMIT arm, ~455-478)
   — branch on the chosen action: wait (existing), switch (re-resolve via
   the helper + retry, resetting the single-retry cap for the new backend),
   or save-stop (return cleanly + emit the resume command). Add the
   interactive menu, gated on TTY/interactive.
4. **CLI flags/env** (`parser.py` + `app.py`) — `--on-rate-limit` /
   `PLAN_TOOL_ON_RATE_LIMIT` (default `wait`) and/or `--fallback-backend`;
   reconcile with `--no-wait-on-rate-limit`; set the non-interactive
   default policy.
5. **Resume-command rendering** — compose the precise re-invocation string
   for `run` (subcommand + plan + `--backend`/`--commit`/`--all`/`--step`),
   and the degraded "re-invoke" line for non-`run` callers.
6. **Tests** — drive the new seams with injected stubs (no real backend):
   menu choice routing (wait/switch/save) under a stubbed TTY; mid-wait
   keypress switches/saves; switch re-resolves the new backend (model +
   extra argv) and retries with a reset attempt budget; save-stop returns
   the failed rc cleanly and prints the right resume command; **non-TTY /
   `-y` path is byte-for-byte unchanged**; unknown / same-as-current target
   backend rejected. Mirror modules: `tests/test_launcher.py`,
   `tests/test_claude_errors.py`, `tests/cli/` for the flags.
7. **Docs** — `RUNBOOK.md` (rate-limit recovery walkthrough: switch vs save
   vs wait, and the resume command), `TESTING.md` neutralization table if a
   new injectable seam is added, `docs/cli/` regen for the new flags, and a
   note in `docs/RUN_FLOW.md` if the run resume story changes.

## Non-goals

- **No new persisted session-context format.** "Save & stop" relies on the
  plan's existing step-state checkpoint; it does not serialize backend
  conversation state. A richer checkpoint is a separate seed.
- **No change to default behavior without a TTY or without opting in.**
  Default policy stays `wait`; non-TTY/`-y`/CI is unchanged.
- **No per-command forked implementations.** One mechanism at the shared
  invoker/wait seam serves every Claude-shelling command.
- **No real backend default in the leaf loops.** Keep the conftest gate
  green; inject the key/cancel/selection callbacks in tests.
- **Not a multi-backend load balancer / auto-retry-across-all-backends.**
  This is an operator-chosen (or single configured fallback) switch, not an
  automatic round-robin across every registered backend.
- **No change to rate-limit *classification*.** The `RATE_LIMIT` detection
  (`backend.py` patterns, `claude_errors.py`) is reused as-is; this plan
  only changes what happens *after* a rate limit is recognized.

## Acceptance criteria (plan-level)

- On a recognized backend rate limit at an interactive TTY, the operator is
  offered wait / switch-backend / save-&-stop; each does what it says.
- Switching re-resolves the target backend (model + per-project extra argv
  via the shared selection helper) and retries the call on it, with a fresh
  attempt budget; an unknown or same-as-current target is rejected.
- During the wait countdown, a keypress can switch backend or save & stop at
  any point; Ctrl+C still aborts; the wait otherwise completes and retries
  as today.
- Save & stop returns cleanly (no retry) and prints a copy-pasteable resume
  command — for `run`, the same plan/flags (and the chosen backend if
  switched); for other commands, the command to re-invoke.
- With no TTY or under `-y`/unattended, behavior is byte-for-byte identical
  to today (honor `wait_on_rate_limit`, no prompt, no stdin read); the new
  non-interactive policy is reachable only via an explicit flag/env.
- New flags/env are documented and `docs/cli/` regenerated; the full suite
  passes with no real backend binary spawned.

## Risks

- **Non-TTY hang.** Reading a keypress with no TTY would wedge CI — gate
  every prompt and the mid-wait poll on the interactive/TTY condition, and
  test the non-interactive path explicitly.
- **Seam leakage.** A real-backend default in `wait_until_epoch` or the leaf
  retry loop trips the conftest gate. Keep real selection at the CLI seam;
  inject in tests.
- **Switch that drops model/extra argv.** A bare `set_active_backend(name)`
  loses per-project overrides and model — must route through the shared
  `resolve → build_effective → set` helper.
- **Attempt-budget confusion.** The single-retry cap (`rate_limit_retried`)
  must reset on a *switch* (new backend, new budget) but still prevent
  unbounded re-waits on the *same* backend.
- **Resume-command drift.** A wrong/stale resume string is worse than none —
  derive it from the actual parsed args/plan, and test it against `run`'s
  real flag set so it stays correct as flags change.
- **Cross-platform keypress.** Non-blocking single-key reads differ
  (POSIX `select`/`termios` vs Windows); keep the mechanism injectable and
  degrade to plain wait + Ctrl+C where unsupported rather than breaking.
