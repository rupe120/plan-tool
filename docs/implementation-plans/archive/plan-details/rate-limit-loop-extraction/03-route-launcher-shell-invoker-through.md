> **Auto-archived**: this plan was swept on 2026-07-12 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 3 — Route `launcher.shell_invoker` through the shared rate-limit loop

## Summary

Reroute `plan_tool/launcher.py:shell_invoker`'s inline `while True` recovery loop through the shared leaf `plan_tool/rate_limit_loop.py` that step 1 adds. Delete the streaming copy of the 429-detect / SWITCH / ASK / wait / transient-backoff cascade from the body of `shell_invoker` and replace it with one call to the leaf's `run_with_rate_limit_recovery`, passing launcher's own pieces (the streaming `_run_streaming_once` call plus the `_last_stats` stash, the `_notify_or_print` sink, `_select_rate_limit_backend` / `_ask_rate_limit_action` / `_can_prompt_on_rate_limit`, the `_rate_limit_backend_scope` ContextVar) in as injected seams. This is a behavior-preserving refactor: the `_last_stats` sentinel reset, the two ContextVar reads (`_run_logger_var` / `_sibling_log_dir_var`), and the `ExitStack` backend scope stay in the wrapper. The key parity point vs step 2 (shell) is that `shell_invoker`'s loop has **no** batch-only surfacings — no missed-limit canary, no raw "exited with code" line (launcher's "exited with code" lines live in `run_step`/siblings, outside the loop) — so its `on_nonsuccess` seam is empty. On green, `shell_invoker` returns the same `(rc, stdout)` for every path, `_last_stats` still reflects the most recent call, and the existing `tests/test_launcher.py` rate-limit suite passes unchanged.

## Table of Contents

- [Why](#why) — the duplication this reroute removes
- [Input](#input) — the leaf seam contract step 1 owns
- [Files (creates vs edits)](#files-creates-vs-edits) — the one file this step edits plus its test module
- [Implementation](#implementation) — how launcher wires each seam and what stays in the wrapper
- [Tests](#tests) — the characterization pins that must stay green
- [Acceptance criteria](#acceptance-criteria) — checkable outcomes on green
- [References](#references) — the stdlib and vendor docs that bear on this step
- [Deferred](#deferred) — what this step leaves out

## Why

`plan_tool/launcher.py:shell_invoker` carries one of the two near-identical copies of the rate-limit recovery loop; `plan_tool/shell.py:claude_invoke` carries the other. Step 1 lands the shared loop as a leaf and step 2 reroutes shell through it, leaving launcher as the last remaining private copy. This step deletes the streaming copy from `shell_invoker` so the leaf becomes the single source of truth for both callers. Until launcher also routes through the leaf, a policy tweak applied to the shared loop still silently diverges from launcher's private copy, and the divergence only shows under a live rate limit — the hardest condition to reproduce. Doing launcher last keeps this reroute a small, independently reviewable diff against a leaf already proven by shell.

## Input

This step consumes the leaf entry point **step 1 produces**: `run_with_rate_limit_recovery` in `plan_tool/rate_limit_loop.py`, plus its injected-seam signature (see step 1's Implementation for the full seam list). What matters for correctness here:

- **The loop owns only the shared control flow** — the one-shot `rate_limit_retried` guard, the SWITCH branch (including the already-active no-op that degrades to a wait), the ASK branch, the wait-honoring, the transient exponential backoff, and the terminal path.
- **Every first-party behavior is a seam** — `run_once`, `classify`, `notify`, `select_backend`, `ask_action`, `can_prompt`, `wait`, `prompt_lock`, `sleep`/`clock`, `current_backend_name`, plus the plain values `fallback_seconds` / `max_transient_retries` / `transient_base_delay` / starting `attempt`.
- **The loop emits no telemetry and owns no `ExitStack`** — launcher emits `ClaudeCallEnd` from `run_step` (via `_emit_claude_call_end`), never inside `shell_invoker`, so the loop has nothing to emit; launcher's wrapper owns the ContextVar scoping.

Follow step 1's shipped contract — it is the owner. If step 1's final seam names or the `classify` result shape differ from the above, use what step 1 ships. Do not re-specify the leaf here.

## Files (creates vs edits)

**New files:**
- None.

**Existing files (edits only):**
- `plan_tool/launcher.py` — in `shell_invoker`, delete the inline `while True` recovery loop (everything from `while True:` through the terminal `return rc, stdout_text`) and replace it with a single `run_with_rate_limit_recovery(...)` call wired to launcher's seams. Add `from plan_tool.rate_limit_loop import run_with_rate_limit_recovery`. Keep the policy resolution, the `_last_stats` sentinel reset, the `_run_logger_var` / `_sibling_log_dir_var` reads, and the `ExitStack` + `_rate_limit_backend_scope.set/reset` scope in the wrapper. The launcher helpers `_select_rate_limit_backend`, `_ask_rate_limit_action`, `_can_prompt_on_rate_limit`, and `_notify_or_print` stay as-is and become seam targets — not moved, not edited.
- `tests/test_launcher.py` — add at most one thin wiring test that mocks `run_with_rate_limit_recovery` to catch an accidental future re-inline (see Tests). Every existing rate-limit and stats-handoff test stays unchanged.

## Implementation

**What changes.** `shell_invoker`'s body stops containing the recovery cascade and instead calls the shared leaf. The behavior a developer must preserve is exactly what the current loop does; the mechanism is to hand the leaf launcher's caller-specific pieces as closures and let the leaf run the branch order.

**What stays in the wrapper — do not move these into the leaf:**
- `resolve_on_rate_limit_policy(wait_on_rate_limit)` and the `recover_rate_limit = policy.action is not OnRateLimitAction.STOP` derivation.
- The `_last_stats` reset: `shell_invoker._last_stats = ClaudeRunStats()` before the leaf call, so an exception or early return can't leak a prior call's stats into the next `ClaudeCallEnd`.
- The two ContextVar reads `run_logger = _run_logger_var.get()` and `sibling_log_dir = _sibling_log_dir_var.get()`.
- The `with ExitStack() as backend_scope:` block, `_rate_limit_backend_scope.set(backend_scope)`, and the `finally: _rate_limit_backend_scope.reset(scope_token)`. This scope is what `_select_rate_limit_backend` reads via `_rate_limit_backend_scope.get()`; it must wrap the leaf call so a SWITCH selection unwinds when `shell_invoker` returns.

**The seams launcher passes to `run_with_rate_limit_recovery` — each is a caller-side adapter that narrows launcher's rich types to the leaf's neutral vocabulary:**
- **`run_once`** — a closure that calls `_run_streaming_once(prompt, run_logger=run_logger, attempt=<current attempt>, sibling_log_dir=sibling_log_dir)`, stashes `shell_invoker._last_stats = stats`, and returns the pieces the leaf needs to classify (rc, stdout text, stderr text). Two constraints:
  - Call `_run_streaming_once` through the **module attribute** (`launcher._run_streaming_once` at call time, e.g. a bare in-module reference resolved each call), because `TestShellInvokerContextVarPlumbing` monkeypatches `launcher._run_streaming_once` and expects the seam to honor the patch.
  - The `attempt` value comes from the leaf (the leaf owns the counter and passes the current attempt into `run_once`), so `attempt` increments across retries. `test_attempt_increments_across_transient_retries` pins `attempts == [1, 2]`.
  - Stash `_last_stats` on **every** call so the most recent run wins on a retry (`test_last_stats_reflects_most_recent_call_on_retry` pins `tokens_input == 99` from the second call).
- **`classify`** — wrap `_classify_failure` (`plan_tool.claude_errors.classify`) and map its `ClaudeFailureKind` result onto the leaf's neutral category enum. Keep `ClaudeFailureKind` out of the leaf.
- **`notify`** — pass `_notify_or_print`. It already resolves `get_active_notifier()` per call, so a notifier bound mid-run (a live progress line in `run_step`) is still honored. Do not capture the notifier once before the leaf call.
- **`select_backend`** — pass `_select_rate_limit_backend` (returns `bool`; it reads the wrapper's `_rate_limit_backend_scope`).
- **`ask_action`** — wrap `_ask_rate_limit_action`. It returns a rich `OnRateLimitAction`; the adapter narrows the result to the leaf's neutral WAIT/SWITCH/STOP vocabulary so `OnRateLimitAction` stays caller-side.
- **`can_prompt`** — pass `_can_prompt_on_rate_limit`.
- **`wait`** — wrap `wait_until_epoch(target, sleep=_sleep, clock=_clock)` and return `True` only when its `.action is WaitUntilAction.RETRY` (else the leaf takes the give-up path and returns the failed call). Keep `WaitUntilAction` out of the leaf.
- **`prompt_lock`** — pass `RATE_LIMIT_PROMPT_LOCK` so the SWITCH swap + interactive prompt + key-poll wait stays serialized across parallel completeness-apply workers.
- **`sleep` / `clock`** — pass `_sleep` / `_clock` (the invoker's own kwargs, `time.sleep` / `time.time` by default).
- **`current_backend_name`** — a callable returning `get_active_backend().name`, used by the leaf for the SWITCH already-active check and the "no reset time in `<backend>` output" fallback message.
- **Plain values** — `fallback_seconds=DEFAULT_RATE_LIMIT_FALLBACK_SECONDS`, `max_transient_retries`, `transient_base_delay`, starting `attempt=1`, and `recover_rate_limit` (or the resolved policy the leaf reads for the SWITCH fallback backend name).
- **`on_nonsuccess`** — **empty / absent.** `shell_invoker`'s loop has no `_MISSED_LIMIT_CANARY` and no raw "exited with code {rc}" surface — the "exited with code" lines in `launcher.py` all live in `run_step`/siblings, not in `shell_invoker`'s recovery loop. Its only non-success surfacing is the terminal `format_user_hint(failure)` hint, which the leaf's terminal path emits through the `notify` seam. This is the deliberate difference from step 2, where shell injects a canary-then-raw-nonzero `on_nonsuccess`.

**Foundational logic and its other home.** The rule this step touches is the rate-limit recovery state machine, whose only other copy is `plan_tool/shell.py:claude_invoke` — already routed through the same leaf by step 2. After this step, both callers share one implementation and no third copy exists. No new consolidation surfaces here; step 2 already handled shell's copy.

**The alternative rejected.** Folding launcher's `_select_rate_limit_backend` / `_ask_rate_limit_action` / `_notify_or_print` into the leaf (unify-don't-inject) would drag `plan_tool.backend`, `plan_tool.claude_errors`, and the notifier into the leaf and re-form the import edge the leaf forbids. Inject-don't-unify keeps the leaf stdlib-only; the type-narrowing adapters are this step's owned work.

## Tests

### Test-creation order (refactor step)

This is a **refactor** step — behavior-preserving. The characterization tests already exist and must be treated as the write-first oracle: read them before touching `shell_invoker`, then keep them green **unmodified** after the restructuring. They drive the whole cascade by mocking `launcher.subprocess.Popen` (so the real `_run_streaming_once` runs) or by monkeypatching `launcher._run_streaming_once` directly.

Existing pins that must stay green unchanged (in `tests/test_launcher.py`):
- `test_shell_invoker_returns_success_first_try` — rc=0, no retry, stdout buffer returned.
- `test_shell_invoker_waits_then_retries_on_rate_limit` — one wait, two Popen calls, recovered output.
- `test_shell_invoker_skips_wait_when_flag_disabled` — `wait_on_rate_limit=False` returns the failed call, no sleep.
- `test_shell_invoker_retries_transient_with_exponential_backoff` — sleeps `[2.0, 4.0]`, then success.
- `test_shell_invoker_context_overflow_does_not_retry` — no retry; the "split a large seed" hint reaches stderr (proves the terminal hint still routes through `notify`).
- `test_shell_invoker_detects_rate_limit_on_stderr` — stderr-only quota copy still triggers the wait path.
- `test_shell_invoker_rate_limit_non_tty_does_not_prompt` — non-TTY waits instead of prompting.
- `test_shell_invoker_rate_limit_menu_stop_returns_failed_call` / `_menu_switch_reselects_backend` — the ASK menu's STOP and SWITCH arms.
- `test_shell_invoker_switch_policy_switches_without_prompt` / `_degrades_to_wait_when_fallback_bad` / `_degrades_when_fallback_binary_missing` — the SWITCH policy branch and its degrade-to-wait fallbacks.
- `test_shell_invoker_switch_to_active_backend_does_not_hot_loop` — the already-active SWITCH no-op; exactly two Popen calls, `selected == []`, backend unchanged.
- `test_shell_invoker_rate_limit_switch_resets_wait_budget` / `_switch_policy_restores_after_fallback_rate_limit` — SWITCH resets the one-shot guard; argv order `["claude", "codex", "codex"]`.
- `test_shell_invoker_parallel_switches_are_isolated` — the `RATE_LIMIT_PROMPT_LOCK` + per-invoke ContextVar scope keeps threads isolated.
- `test_shell_invoker_honors_module_default_when_kwarg_is_none` — `wait_on_rate_limit=None` honors the process policy.
- `TestShellInvokerStatsHandoff::*` — `_last_stats` default exists, is populated from the result envelope, and reflects the most recent call on retry.
- `TestShellInvokerContextVarPlumbing::*` — `_run_logger_var` / `_sibling_log_dir_var` forwarded to `_run_streaming_once`, attempt increments `[1, 2]`, defaults to `None` with no surrounding frame.

New test (one, optional):
- `test_shell_invoker_routes_through_shared_leaf` — monkeypatch `plan_tool.launcher.run_with_rate_limit_recovery`, call `shell_invoker("p")`, assert it is called once and its return propagates. Guards only the structural claim that the reroute happened; a red here is a wiring regression, not an expected adaptation.

## Acceptance criteria

- `plan_tool/launcher.py` imports `run_with_rate_limit_recovery` from `plan_tool.rate_limit_loop`, and `shell_invoker` contains no `while True:` recovery loop.
- `shell_invoker` still returns `(rc, stdout)` identically for success, rate-limit-then-success, wait-disabled, transient-backoff, context-overflow, SWITCH, and ASK paths.
- `shell_invoker._last_stats` is reset to a default before the leaf call and holds the most recent call's `ClaudeRunStats` after return (default `ClaudeRunStats()` on a never-called read).
- The `ExitStack` + `_rate_limit_backend_scope.set/reset` scope still wraps the leaf call, so a SWITCH selection unwinds on return (parallel-isolation pin stays green).
- `attempt` passed to `_run_streaming_once` increments across retries (`[1, 2]` for one transient retry).
- The full `tests/test_launcher.py` rate-limit and stats-handoff suite passes unmodified.
- `grep -E '^(from|import) plan_tool' plan_tool/rate_limit_loop.py` still returns nothing (leaf stays stdlib-only; this step adds no first-party import to it).

## References

- [contextvars — Context Variables (Python Standard Library)](https://docs.python.org/3/library/contextvars.html) — Confirms the `_rate_limit_backend_scope` / `_run_logger_var` / `_sibling_log_dir_var` semantics the wrapper must preserve around the leaf call.
- [contextlib — ExitStack (Python Standard Library)](https://docs.python.org/3/library/contextlib.html) — The register-and-unwind mechanism launcher's wrapper uses to scope the SWITCH backend selection around the extracted loop.
- [subprocess — Popen and run (Python Standard Library)](https://docs.python.org/3/library/subprocess.html) — Reference for the streaming `Popen` path in `_run_streaming_once` that stays caller-side as the `run_once` seam.
- [time — sleep, time, monotonic (Python Standard Library)](https://docs.python.org/3/library/time.html) — The `_sleep` / `_clock` primitives passed through as the leaf's injectable sleep/clock seams.
- [Rate limits — Anthropic Claude API](https://docs.claude.com/en/api/rate-limits) — The 429 / retry-after behavior the recovery state machine detects and waits on.

## Deferred

- **Rerouting `plan_tool/shell.py:claude_invoke`** — owned by step 2; not touched here.
- **Adding the shared leaf `plan_tool/rate_limit_loop.py`** — owned by step 1; this step only calls it.
- **Consolidating the two notify sinks (`_notify_or_print` vs shell's `_notify_or_tool`) into one** — deliberately kept caller-side per inject-don't-unify; each caller's no-notifier fallback format is asserted by its own tests, so unifying them is a separate follow-up, not this refactor.
- **Any change to where `ClaudeCallEnd` is emitted** — launcher emits it from `run_step`, not `shell_invoker`; this step leaves that telemetry path untouched.
