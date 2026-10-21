> **Auto-archived**: this plan was swept on 2026-07-12 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 1 — Add the shared rate-limit recovery loop leaf (`plan_tool/rate_limit_loop.py`)

## Summary

This step creates one new module, `plan_tool/rate_limit_loop.py`, that owns the 429-detect / wait-or-switch / transient-backoff recovery **control flow** today copied — with identical control flow but differing surfacings — inside `plan_tool/shell.py:claude_invoke` and `plan_tool/launcher.py:shell_invoker`. The loop is written as a **stdlib-only leaf**: every first-party concern (classification, backend selection, the ASK menu, the notify sink, `wait_until_epoch`, the prompt lock) is passed in as an injected seam, so the module has no runtime `plan_tool` import and cannot form an edge to `shell`, `launcher`, or `backend`. The key design decision is **inject-don't-unify** — the caller-specific pieces the two copies genuinely differ on are handled at the boundary rather than folded in, and they fall into two kinds: pieces **injected into the loop** (defined caller-side but *called by* the loop), such as the batch `subprocess.run` vs streaming `Popen` run-once closure, the sleep/clock seams, and shell's missed-limit canary + raw-nonzero line (via the `on_nonsuccess` hook the loop invokes mid-cascade); and pieces that stay **wrapper-only** and never reach the loop, such as the two per-invoke backend-scope ContextVars (each scoped by the caller's own `ExitStack`, reaching the loop only through the injected `select_backend` closure). Step 1 adds the leaf plus its direct tests in `tests/test_rate_limit_loop.py` only; it does **not** reroute either caller (steps 2 and 3 do that) and edits no existing file. On green, the new module drives every recovery branch against a fake `run_once` and the full existing suite still passes, proving no import cycle and no accidental breakage.

## Table of Contents

- [Why](#why) — the duplication this leaf removes and why now
- [Files (creates vs edits)](#files-creates-vs-edits) — the two new files this step adds
- [Implementation](#implementation) — the loop contract, the injected seams, and the stdlib-only constraint
- [Tests](#tests) — the direct branch tests that characterize the leaf
- [Acceptance criteria](#acceptance-criteria) — checkable outcomes on green
- [References](#references) — the stdlib and vendor docs that bear on this leaf
- [Deferred](#deferred) — what this step deliberately leaves for steps 2–4

## Why

The rate-limit recovery state machine lives in two places whose control flow must stay identical but nothing keeps in sync: `plan_tool/shell.py:claude_invoke` (batch `subprocess.run`) and `plan_tool/launcher.py:shell_invoker` (streaming `Popen`) each carry their own near-identical copy of the same one-shot-guard → SWITCH/degrade → ASK → wait → transient-backoff cascade (identical control flow; the surfacings differ). A fix or policy tweak applied to one silently diverges from the other, and the divergence only shows up under a live rate limit — the hardest condition to reproduce. BACKLOG #101 tracks this. This step lands the shared implementation first (nothing routes through it yet) so steps 2 and 3 can delete each duplicate body and prove parity against it.

## Files (creates vs edits)

**New files:**
- `plan_tool/rate_limit_loop.py` — the stdlib-only leaf hosting the shared recovery loop and its small helpers.
- `tests/test_rate_limit_loop.py` — direct tests driving each recovery branch of the loop with a fake `run_once` and recording seams.

**Existing files (edits only):**
- None. This step is additive; `plan_tool/shell.py`, `plan_tool/launcher.py`, and their test modules are untouched here — rerouting is steps 2 and 3.

## Implementation

**What changes.** Add one module that exposes a single recovery-loop entry point (call it `run_with_rate_limit_recovery` — the name is the implementer's to refine). It reproduces the control flow that `claude_invoke` and `shell_invoker` run today, but takes the parts the two callers differ on as arguments instead of hard-coding them.

**Keep the leaf stdlib-only — this is the key constraint.** The plan's acceptance check is `grep -E '^(from|import) plan_tool' plan_tool/rate_limit_loop.py` returns nothing. The shared primitives the loop conceptually needs — `ClaudeFailureKind`, `OnRateLimitAction`, `wait_until_epoch`, `format_user_hint`, `RATE_LIMIT_PROMPT_LOCK` in `plan_tool/claude_errors.py`, and `get_active_backend` / `scoped_select_active_backend` in `plan_tool/backend.py` — all live in modules that themselves import first-party code (`plan_tool/claude_errors.py` imports `plan_tool.backend` and `plan_tool.style`). So the loop must **not import them at runtime**. Two rules make that work:
- **Inject every first-party behavior** as a callable or plain value passed in by the caller (see the seam list below).
- **If you need a first-party type only for annotations**, put its import under an indented `if TYPE_CHECKING:` block — the grep is anchored at column 0, so an indented import does not match and creates no runtime edge. This mirrors the existing `if TYPE_CHECKING:` import of `ClaudeRunStats` in `plan_tool/shell.py`.

**The loop owns only the control flow that is identical across both callers:**
- the one-shot `rate_limit_retried` guard (wait at most once, then surface "already retried once" and return),
- the SWITCH branch: try the configured fallback backend via the injected `select_backend`, and on success reset the guard + transient counter, bump the attempt, and retry; on failure **degrade to waiting**,
- the **already-active hot-loop guard**: a fallback naming the currently-active backend is treated as a no-op that degrades to a wait, so it can never reset the one-shot guard forever,
- the ASK branch: when the injected `can_prompt` is true, route through the injected `ask_action`, honoring STOP (return) and SWITCH (reset + retry),
- honoring the wait: resolve the target epoch from the failure's reset time or fall back to the injected fallback-seconds value, then call the injected `wait`; retry only when it reports RETRY, else return,
- transient **exponential backoff**: `transient_base_delay * (2 ** transient_attempts)` up to `max_transient_retries` total attempts, using the injected `sleep`,
- the terminal fallthrough: for context-overflow, unknown-nonzero, rate-limit-with-recovery-disabled, or transient-past-budget, surface the hint and return the attempt's `(rc, payload)`.

**The injected seams (what stays caller-side).** These are the pieces the two copies genuinely differ on; the loop takes each one rather than picking a side. Enumerate and preserve each:
- **`run_once(attempt)`** — the caller's attempt closure. Batch (`plan_tool/shell.py:_run_once`) vs streaming (`plan_tool/launcher.py:_run_streaming_once`). It returns an opaque per-attempt outcome the caller's own `classify` understands. Telemetry stays caller-side, so the loop must not emit any: shell emits `ClaudeCallEnd` via `_emit_call_end` today, while launcher's `_run_streaming_once` emits only stream-progress events and its terminal `ClaudeCallEnd` is owned by `run_step` (via `_emit_claude_call_end`, outside `shell_invoker` and the recovery loop) — so launcher's `run_once` need not carry a `ClaudeCallEnd` emission. The loop just hands `run_once` the current attempt number.
- **classification** — a `classify(outcome)` seam that yields a small loop-legible result: a category the loop can branch on, plus the reset epoch, the return `rc`, the payload to return, the user hint, **and the caller's opaque `failure` object carried through untouched**. The loop never inspects `failure` — doing so would need `ClaudeFailureKind`, a first-party type — it only threads it to `on_nonsuccess`, whose shell closure reads `failure.kind is ClaudeFailureKind.UNKNOWN_NONZERO` for the canary gate; treating `failure` as an opaque passthrough keeps the leaf stdlib-only. For the *category*, to stay off `ClaudeFailureKind`, define a tiny loop-local enum (stdlib `enum` only) and let each caller map `ClaudeFailureKind` onto it. This is one way; the implementer may instead pass boolean predicates. Say which you chose.
- **`notify(message, *, kind)`** — the notify sink: shell's `plan_tool/shell.py:_notify_or_tool` and launcher's `plan_tool/launcher.py:_notify_or_print`. Both fall back to a byte-identical `plan-tool: <message>` line (asserted by their no-notifier tests); the load-bearing reason to inject is the differing bound state, not the output — shell takes its `notifier` as a param, while launcher resolves one internally via `get_active_notifier()`.
- **`select_backend(name) -> bool`** — the fallback-backend selection seam. Each caller keeps its own `_select_rate_limit_backend` (they close over the notify sink and the caller's own backend-scope ContextVar). The leaf calls it **only on the auto-SWITCH policy path**. It must **not** call it on the ASK-switch: `ask_action` (i.e. `_ask_rate_limit_action`) performs its swap *internally* and returns SWITCH only after the swap already succeeded, so on an ASK-SWITCH the leaf merely resets the guard + transient counter and retries — re-selecting there would double-switch the backend.
- **`ask_action()`** and **`can_prompt()`** — the interactive menu and the TTY check (each caller's `_ask_rate_limit_action` / `_can_prompt_on_rate_limit`).
- **`wait(target_epoch) -> bool`** — wraps `plan_tool/claude_errors.py:wait_until_epoch`; return True to retry, False to stop. Wrapping to a bool keeps `WaitUntilAction` out of the leaf.
- **`prompt_lock`** — the `RATE_LIMIT_PROMPT_LOCK` context manager, passed in. The SWITCH swap + ASK prompt + wait must all run inside it, exactly as both copies do today, so parallel workers don't fight over stdin.
- **`sleep` / `clock`** — the test seams for backoff and wait timing.
- **`fallback_seconds`, `max_transient_retries`, `transient_base_delay`, starting `attempt`** — plain values the caller supplies (`DEFAULT_RATE_LIMIT_FALLBACK_SECONDS` etc. resolved caller-side).
- **`on_nonsuccess` (optional, default None)** — shell's missed-limit canary (`_MISSED_LIMIT_CANARY`) plus its "surface the raw nonzero unless about to retry" block. Launcher has neither and passes None. The loop calls it, when present, with the outcome, the opaque `failure` (see the classify seam), and a **predictive `will_retry` signal** — computed *before* the wait/switch resolves, True exactly when this attempt is a fresh recoverable failure the recovery path will take up (a `RATE_LIMIT` with recovery enabled and the one-shot guard not yet spent, or a transient within budget). This must mirror shell's current `will_retry_rate_limit` / `will_retry_transient` flags, **not** the post-hoc actual-retry outcome: a rate-limit that switches-then-stops or waits-then-stops is predicted-recoverable (so its raw "exited with code" line stays suppressed) even though the invoke ultimately terminates without retrying. Wiring `will_retry` to the actual outcome would newly surface "exited with code" on those abandoned-recovery paths and break byte-preservation. The loop then continues its normal flow.
- **`current_backend_name() -> str`** — used for the already-active comparison and for messages (`get_active_backend().name` today).
- **recovery policy inputs** — the loop's SWITCH / ASK / recovery-disabled branches structurally require three policy values, resolved caller-side and passed in: **`recover_rate_limit`** (gates the whole `RATE_LIMIT` block — when false, a rate-limit returns immediately without waiting, as `test_rate_limit_recovery_disabled_returns_without_waiting` asserts), the **wait-vs-switch action** (the `if action is SWITCH … elif can_prompt …` fork the loop owns), and **`fallback_backend`** (the SWITCH swap target and the `already_active = fallback_backend == current_backend_name()` comparand). Because `policy.action` is a first-party `OnRateLimitAction`, the caller **narrows it to the leaf's neutral SWITCH / WAIT / STOP vocabulary** before passing it in — the same narrowing this step specifies for `classify`'s category and that step 3 specifies for `ask_action`'s return — so the leaf stays stdlib-only.

**What deliberately stays out of the leaf (caller wrappers own these in steps 2/3):** shell's `EXEC_NOT_FOUND_EXIT` / `shutil.which` path guard, shell's `_maybe_warn_shell_prompt_budget` pre-send backstop, launcher's `shell_invoker._last_stats` **initial reset** (`= ClaudeRunStats()` before the loop — note the *per-attempt* stash `_last_stats = stats` after each streaming call is **not** wrapper-only; it rides inside launcher's injected `run_once`, exactly as shell folds `_emit_call_end` into its own, so the returning attempt's stats survive a retry), launcher's `_run_logger_var` / `_sibling_log_dir_var` streaming ContextVars, and the **two distinct backend-scope ContextVars** (`plan_tool_rate_limit_backend_scope` vs `plan_tool_launcher_rate_limit_backend_scope`) each scoped by the caller's own `ExitStack`. The loop never creates or resets an `ExitStack`; the caller sets the ContextVar around the call and passes `select_backend` in.

**Constraints and gotchas that are not free to vary:**
- **Branch order and the guards must match the two current copies exactly** — one-shot guard before the SWITCH/ASK block, SWITCH reaching the wait only after a failed swap, the already-active no-op degrading to a wait. This is a behavior-preserving extraction; any reordering is a regression that only shows under a live limit.
- **The prompt lock scope** must wrap the same three actions (swap, ask, wait) it wraps today.
- **`run_once` owns telemetry** — do not emit `ClaudeCallEnd` from the loop.
- **No `ExitStack` inside the leaf** — the ContextVar scoping is the caller's, kept distinct per caller.

**Foundational logic and its other home.** The core behavior this step adds is the recovery control flow. The only other places that exercise it are the two callers this plan reroutes — `plan_tool/shell.py:claude_invoke` and `plan_tool/launcher.py:shell_invoker` (steps 2 and 3). No third caller carries a copy. The three small helpers `_select_rate_limit_backend`, `_ask_rate_limit_action`, and `_can_prompt_on_rate_limit` are near-duplicates across shell and launcher, but under the stdlib-only contract they stay caller-side and are **injected** rather than hosted here; folding them into the leaf would require importing `backend` / `backend_config` / `claude_errors` and break the leaf. Fuller de-duplication of those helpers is left out — see Deferred.

## Tests

All tests go in `tests/test_rate_limit_loop.py`. Drive `run_with_rate_limit_recovery` with a fake `run_once` that yields a scripted sequence of outcomes, a recording `notify`, and injected `sleep` / `clock` / `wait` so nothing blocks. Each case is one line:

- `test_success_first_attempt_returns_immediately` — a SUCCESS outcome returns `(rc, payload)` with no wait, no notify.
- `test_rate_limit_waits_then_retries_once` — a RATE_LIMIT then SUCCESS waits via the injected `wait` and returns the retried result; `wait` called once.
- `test_rate_limit_second_hit_surfaces_already_retried_and_returns` — RATE_LIMIT twice returns after one wait with the "already retried once" notice; the one-shot guard holds.
- `test_rate_limit_recovery_disabled_returns_without_waiting` — with `recover_rate_limit` false, a RATE_LIMIT returns immediately, `wait` never called.
- `test_switch_policy_swaps_backend_and_retries` — SWITCH with a good `select_backend` retries on the new backend without prompting; guard and transient counter reset.
- `test_switch_policy_degrades_to_wait_when_select_fails` — SWITCH with `select_backend` returning False degrades to the wait path.
- `test_switch_to_already_active_backend_degrades_to_wait` — a fallback naming the current backend degrades to a wait and does not hot-loop.
- `test_ask_menu_stop_returns_without_retry` — `can_prompt` true and `ask_action` returning STOP returns without waiting.
- `test_ask_menu_switch_retries` — `ask_action` returning SWITCH resets and retries.
- `test_wait_stop_result_returns` — `wait` returning False (stop) returns the current `(rc, payload)`.
- `test_no_reset_epoch_uses_fallback_seconds` — a RATE_LIMIT with no reset epoch waits on `fallback_seconds` and notes the fallback.
- `test_transient_retries_with_exponential_backoff` — TRANSIENT then SUCCESS sleeps `transient_base_delay * 2**n`; assert the delay sequence.
- `test_transient_gives_up_after_max_attempts` — TRANSIENT past `max_transient_retries` surfaces the hint and returns.
- `test_terminal_failure_surfaces_hint_and_returns` — CONTEXT_OVERFLOW / UNKNOWN_NONZERO returns with the hint, no retry.
- `test_prompt_lock_held_across_switch_and_wait` — a recording lock confirms the swap/ask/wait run inside `prompt_lock`.
- `test_on_nonsuccess_hook_fires_when_provided` — the `on_nonsuccess` hook is called on a non-success attempt with the expected context.
- `test_on_nonsuccess_absent_is_noop` — with `on_nonsuccess=None` (launcher's shape), no canary/raw-nonzero surface happens.
- `test_run_once_receives_incrementing_attempt` — each attempt passes the incremented attempt number to `run_once`.
- `test_leaf_has_no_first_party_runtime_import` — importing `plan_tool.rate_limit_loop` pulls in neither `plan_tool.shell` nor `plan_tool.launcher`, and the `^(from|import) plan_tool` grep over the source returns nothing.

### Test-creation order (refactor step)

This is a behavior-preserving extraction, so write the characterization tests **first**, then implement the loop to satisfy them:

1. Write the branch tests above **before** writing `plan_tool/rate_limit_loop.py`. Each pins one recovery behavior that the existing `tests/test_shell.py` and `tests/test_launcher.py` rate-limit suites already prove for the two copies (for example `test_claude_invoke_waits_then_retries_on_rate_limit`, `test_claude_invoke_switch_to_active_backend_does_not_hot_loop`, `test_claude_invoke_retries_transient_with_exponential_backoff`). They are the expected-behavior oracle for the leaf.
2. Implement the loop until those tests pass.

**Pass-unchanged gate:** this step edits no existing source file, so the whole current suite — `tests/test_shell.py`, `tests/test_launcher.py`, `tests/test_claude_errors.py`, and the rest — must stay green **unmodified** after adding the leaf. A red anywhere means an accidental import cycle or a name collision, not an expected adaptation.

## Acceptance criteria

- `plan_tool/rate_limit_loop.py` exists and `grep -E '^(from|import) plan_tool' plan_tool/rate_limit_loop.py` returns nothing (no runtime first-party import; no edge to `shell`, `launcher`, or `backend`).
- Importing `plan_tool.rate_limit_loop` does not import `plan_tool.shell` or `plan_tool.launcher`, and the package still imports with no cycle.
- `run_with_rate_limit_recovery` (or the chosen name) drives, against injected `sleep` / `clock` / `wait` seams, all four loop-owned invariants: rate-limit wait-or-switch handling, the wait-vs-switch policy branching, transient exponential backoff, and honoring the injected wait's RETRY/STOP result.
- `tests/test_rate_limit_loop.py` covers each recovery branch listed above with a fake `run_once`, and the `on_nonsuccess` hook is exercised both present (fires) and absent (no-op).
- `uv run pytest tests/test_rate_limit_loop.py -q` exits 0, and the full existing suite (`uv run pytest tests/ -q`) stays green with no edits to existing test files.

## References

- [contextvars — Context Variables (Python Standard Library)](https://docs.python.org/3/library/contextvars.html) — Semantics for the two distinct per-invoke backend-scope ContextVars the loop must accept without unifying (each stays caller-side).
- [contextlib — ExitStack (Python Standard Library)](https://docs.python.org/3/library/contextlib.html) — The dynamic register-and-unwind the callers use to scope backend selection; the leaf takes `select_backend` in and never owns an `ExitStack`.
- [subprocess — Popen and run (Python Standard Library)](https://docs.python.org/3/library/subprocess.html) — The batch `subprocess.run` vs streaming `Popen` modes that stay caller-side as the injected `run_once` closures.
- [time — sleep, time, monotonic (Python Standard Library)](https://docs.python.org/3/library/time.html) — The clock and sleep primitives behind the injected backoff and wait timing seams.
- [Rate limits — Anthropic Claude API](https://docs.claude.com/en/api/rate-limits) — The 429 / retry-after behavior the recovery state machine detects and waits on.

## Deferred

- **Rerouting `shell.claude_invoke` and `launcher.shell_invoker` through the leaf** — steps 2 and 3; this step lands the shared implementation and its direct tests only, deleting no duplicate body yet.
- **De-duplicating the `_select_rate_limit_backend` / `_ask_rate_limit_action` / `_can_prompt_on_rate_limit` helpers** — they stay caller-side and injected under the stdlib-only contract; hosting them in the leaf would require first-party imports and break it. A later home for them is out of scope for this plan.
- **Unifying the caller-specific seams** (batch vs streaming `run_once`, the two backend-scope ContextVars, the `on_nonsuccess` canary, the `_last_stats` handoff) — the inject-don't-unify trade-off keeps them caller-side by design.
- **Any rate-limit policy or behavior change** (429 detection copy, wait-vs-switch policy, backoff math, `wait_until_epoch` timing) — this is a pure extraction; the loop must stay behavior-identical to the two copies.
- **Removing BACKLOG #101 and registering the leaf in CLAUDE.md** — step 4.
