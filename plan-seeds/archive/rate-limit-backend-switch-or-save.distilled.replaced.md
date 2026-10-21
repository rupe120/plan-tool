> **Replaced**: this file has been superseded by `docs/implementation-plans/2-rate-limit-backend-switch-or-save.md`.
> Preserved here for history; do not edit.

## Overview

Adds a three-way choice when the active backend reports a rate limit: **wait** (today's countdown-then-retry), **switch backend** (re-run the same call on a different backend and keep going), or **save & stop** (stop cleanly at the step boundary and print the exact resume command). The wait countdown itself becomes a live menu — the same switch/save keys take effect mid-wait — instead of a blind block until reset. The mechanism is built once at the shared invoker/wait seam so it lights up for every Claude-shelling command. The default policy stays `wait`, and behavior is byte-for-byte unchanged when there is no TTY or under `-y`/unattended.

## Problem statement

When the active backend reports a rate limit, the tool's only options today are *wait for the reset* (default) or *give up and return the failed rc* (`--no-wait-on-rate-limit`). An operator who has a second backend available, or who would rather stop now and resume later, has no in-flight path to either — they must Ctrl+C, lose the wait, and re-launch by hand while guessing the right command. The wait is also a dead end: once the countdown starts there is no way to change course short of a blunt Ctrl+C. This contradicts the mission's *operator-in-control* posture, which holds that the tool should surface the more-useful options and never trap the operator in a single unattended behavior.

## Architecture

**The seam.** The whole rate-limit path lives in two already-injectable leaves. `plan_tool/launcher.py:shell_invoker` (~436-498) is the retry loop; its RATE_LIMIT arm (~455-478) computes `target = failure.reset_epoch` (falling back to `DEFAULT_RATE_LIMIT_FALLBACK_SECONDS`), calls `wait_until_epoch(...)`, and on completion loops to retry once (`rate_limit_retried` caps it at a single wait); if `wait_on_rate_limit` is off it returns the failed `(rc, stdout)`. `plan_tool/claude_errors.py:wait_until_epoch` (~319-387) is the countdown — it already accepts an injectable `cancel_check` callback (~361), handles `KeyboardInterrupt` (~378) by returning `False`, and ticks at ~360-373. `wait_on_rate_limit` defaults to the process-wide value set by `set_default_wait_on_rate_limit(not args.no_wait_on_rate_limit)` (`plan_tool/cli/app.py:535`), read per-call via `get_default_wait_on_rate_limit()` (`launcher.py:419-420`). This is a **shared leaf seam**: `shell_invoker` is the production invoker for every Claude-shelling command (`create`, `detail`, `run`, `review`, `completeness`, reconcile, …), so the choice mechanism is built once here, not forked per command.

**Selection helper.** Switching is not a bare `set_active_backend(name)`. The CLI builds the *effective* backend before dispatch (`app.py:447-497`): `resolve_backend(name)` → `build_effective_backend(selected, model=…, extra_batch_argv=…, extra_streaming_argv=…)` (splicing per-project `.plan-tool/backends.json` overrides and the resolved model) → `set_active_backend(effective)`. A mid-run switch must run the **same** resolution for the new backend, or it loses its model / extra argv. Extract that sequence into a reusable helper both the startup path and the mid-run switch call (no startup behavior change), and validate the target name against `registered_names()`, rejecting / re-prompting on an unknown or same-as-current name. Because each Claude call is a fresh session, a switch is clean: the failed call's partial work is discarded, the loop re-enters `_run_streaming_once` with the new active backend, and `rate_limit_retried` **resets** on a switch so the new backend gets its own fresh attempt budget.

**Wait loop.** `wait_until_epoch` gains an injectable `key_check`-style callback alongside the existing `cancel_check`, plus non-blocking per-tick TTY polling (e.g. `select.select([sys.stdin], …, 0)` on POSIX) so a keypress can interrupt mid-wait; the same `b` / `s` keys take effect and Ctrl+C still aborts. The keypress source is injectable for testing. Its return type widens from a bare `bool` to a small result naming which action ended the wait (completed / cancelled / switch-backend / save-stop) so the invoker can branch.

**Save & stop.** There is no rich conversational context to serialize — each invoker call is a fresh backend session. The durable state is already on disk: `run` persists per-step status in the plan frontmatter (`StepStatus.PENDING/CURRENT/DONE`, advanced by `mark_done_and_advance`, `launcher.py:1298`) and resumes from `current_step()` / `next_runnable_step()` (`launcher.py:1284-1295`). So save & stop stops cleanly at the current step boundary (the failed step's uncommitted work is discarded, the step stays `CURRENT`/`PENDING`, the loop returns without retrying) and prints the exact resume command — subcommand + plan name + the salient flags (`--backend <chosen>`, `--commit`, `--all`, `--step`, etc.), baking in the chosen backend if one was picked. The only first-class resumable command is `run` (step state is its checkpoint); for non-`run` callers (`create`/`detail`/`review`/…) save & stop degrades to *stop cleanly + print the command to re-invoke*, with no mid-command checkpoint to restore.

**Interactive menu.** When RATE_LIMIT is hit and stdin/stderr is a TTY and the run is interactive (not `-y`, not non-TTY, not unattended/CI), present a small menu instead of silently waiting:
```
rate limit on <backend>; reset at HH:MM (<N>s).
  (w)ait   (b) switch backend   (s)ave & stop   Ctrl+C abort
```
`w` falls into the existing `wait_until_epoch` countdown; `b` prompts for / picks a target backend, re-resolves it via the selection helper, and retries now; `s` saves & stops and prints the resume command. The whole menu and the mid-wait poll are gated on the same interactive/TTY condition the rest of the tool already uses.

**CLI surface.** Prefer the smallest surface that works: a `--on-rate-limit {wait,switch,stop,ask}` flag (and/or `PLAN_TOOL_ON_RATE_LIMIT` env) sets the non-interactive policy and the default the interactive menu pre-selects (`ask` = show the menu, TTY only; default stays `wait` to preserve today's behavior); optionally `--fallback-backend <name>` (and/or env) so `switch` is unattended-capable — auto-switch to the named backend without a prompt, usable in CI. Keep `--no-wait-on-rate-limit` working as the existing "don't wait" alias and reconcile it with `--on-rate-limit` (one maps onto the other, not contradicting it). New flags live with `--no-wait-on-rate-limit` / `--backend` in `plan_tool/cli/parser.py` (~141/150); regenerate `docs/cli/` (drift-guarded by `tests/cli/test_cli_reference.py`).

## Out of scope

- **No new persisted session-context format** — save & stop relies on the plan's existing step-state checkpoint and does not serialize backend conversation state; a richer checkpoint is a separate seed.
- **No change to default behavior without a TTY or without opting in** — default policy stays `wait`; non-TTY/`-y`/CI is unchanged, and any new non-interactive default is reachable only via an explicit flag/env.
- **No per-command forked implementations** — one mechanism at the shared invoker/wait seam serves every Claude-shelling command.
- **No real-backend default in the leaf loops** — keep the `tests/conftest.py` gate green by keeping real selection at the CLI seam and injecting the key/cancel/selection callbacks in tests.
- **Not a multi-backend load balancer / auto-retry-across-all-backends** — this is an operator-chosen (or single configured fallback) switch, not an automatic round-robin across every registered backend.
- **No change to rate-limit classification** — the `RATE_LIMIT` detection (`backend.py` patterns, `claude_errors.py`) is reused as-is; this plan only changes what happens *after* a rate limit is recognized.

## Risks

- **Non-TTY hang** — reading a keypress with no TTY would wedge CI; gate every prompt and the mid-wait poll on the interactive/TTY condition and test the non-interactive path explicitly. (high severity; mitigated by the interactive gate + an explicit non-TTY test.)
- **Seam leakage** — a real-backend default in `wait_until_epoch` or the leaf retry loop trips the conftest gate; keep real selection at the CLI seam and inject in tests.
- **Switch that drops model/extra argv** — a bare `set_active_backend(name)` loses per-project overrides and model; must route through the shared `resolve_backend → build_effective_backend → set_active_backend` helper.
- **Attempt-budget confusion** — the single-retry cap (`rate_limit_retried`) must reset on a *switch* (new backend, new budget) but still prevent unbounded re-waits on the *same* backend.
- **Resume-command drift** — a wrong/stale resume string is worse than none; derive it from the actual parsed args/plan and test it against `run`'s real flag set so it stays correct as flags change.
- **Cross-platform keypress** — non-blocking single-key reads differ (POSIX `select`/`termios` vs Windows); keep the mechanism injectable and degrade to plain wait + Ctrl+C where unsupported rather than breaking.

## Testing

Drive every new seam with injected stubs and no real backend — `tests/conftest.py`'s autouse gate raises if a real backend binary is spawned (opt out only with `@pytest.mark.allow_real_claude`). Mirror source modules: invoker-policy and switch/save routing in `tests/test_launcher.py`, the widened countdown and mid-wait keypress in `tests/test_claude_errors.py`, and the new flags/env in `tests/cli/` (the `docs/cli/` regen is drift-guarded by `tests/cli/test_cli_reference.py`). Cover: menu choice routing (wait/switch/save) under a stubbed TTY; a mid-wait keypress that switches or saves; a switch that re-resolves the new backend (model + extra argv) and retries with a reset attempt budget; save-stop that returns the failed rc cleanly and prints the right resume command; an unknown / same-as-current target backend that is rejected; and — load-bearing — the non-TTY / `-y` path asserted byte-for-byte unchanged (honor `wait_on_rate_limit`, no prompt, no stdin read). Prefer unit tests exercising one leaf with injected `key_check`/`cancel_check`/selection callbacks; reserve integration-tier tests for end-to-end flag wiring through the CLI entry point where a unit test on a single piece would miss it.

## Acceptance criteria

- On a recognized backend rate limit at an interactive TTY, the operator is offered wait / switch-backend / save-&-stop, and each does what it says.
- Switching re-resolves the target backend (model + per-project extra argv via the shared selection helper) and retries the call on it with a fresh attempt budget; an unknown or same-as-current target is rejected.
- During the wait countdown, a keypress can switch backend or save & stop at any point; Ctrl+C still aborts; the wait otherwise completes and retries as today.
- Save & stop returns cleanly (no retry) and prints a copy-pasteable resume command — for `run`, the same plan/flags (and the chosen backend if switched); for other commands, the command to re-invoke.
- With no TTY or under `-y`/unattended, behavior is byte-for-byte identical to today (honor `wait_on_rate_limit`, no prompt, no stdin read); the new non-interactive policy is reachable only via an explicit flag/env.
- New flags/env are documented and `docs/cli/` regenerated; the full suite passes with no real backend binary spawned.
