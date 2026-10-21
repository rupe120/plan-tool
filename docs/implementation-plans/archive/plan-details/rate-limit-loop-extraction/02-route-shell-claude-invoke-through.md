> **Auto-archived**: this plan was swept on 2026-07-12 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 2 — Route `shell.claude_invoke` through the shared rate-limit loop

## Summary

Reroute `plan_tool/shell.py:claude_invoke`'s inline `while True` recovery loop through the shared leaf `plan_tool/rate_limit_loop.py` that step 1 adds. Delete the batch copy of the 429-detect / SWITCH / ASK / wait / transient-backoff cascade from the body of `claude_invoke` and replace it with one call to the leaf's `run_with_rate_limit_recovery`, passing shell's caller-specific pieces (the batch `_run_once` + `_emit_call_end`, the `_notify_or_tool` sink, `_select_rate_limit_backend` / `_ask_rate_limit_action` / `_can_prompt_on_rate_limit`, the missed-limit canary, and the `_rate_limit_backend_scope` ContextVar) in as injected seams. This is a behavior-preserving refactor: the `shutil.which` path guard, the `_maybe_warn_shell_prompt_budget` backstop, and the `ExitStack` backend scope stay in the wrapper. On green, `claude_invoke` returns the same `(rc, stdout)` for every path and the existing `tests/test_shell.py` rate-limit suite passes unchanged.

## Table of Contents

- [Why](#why) — the duplication this reroute removes
- [Input](#input) — the leaf seam contract step 1 owns
- [Files (creates vs edits)](#files-creates-vs-edits) — the two files this step touches
- [Implementation](#implementation) — how shell wires each seam and what stays in the wrapper
- [Tests](#tests) — the characterization pins that must stay green
- [Acceptance criteria](#acceptance-criteria) — checkable outcomes on green
- [References](#references) — the stdlib and vendor docs that bear on this step
- [Deferred](#deferred) — what this step leaves for step 3 and step 4

## Why

`plan_tool/shell.py:claude_invoke` carries one of the two near-identical copies of the rate-limit recovery loop (identical control flow, differing surfacings); `plan_tool/launcher.py:shell_invoker` carries the other. Step 1 lands the shared loop as a leaf but reroutes nobody. This step deletes the batch copy from `claude_invoke` so the leaf becomes the single source of truth for the batch path. Until both callers route through the leaf, a policy tweak to one still silently diverges from the other, and the divergence only shows under a live rate limit — the hardest condition to reproduce. Doing shell first (step 2) then launcher (step 3) keeps each reroute a small, independently reviewable diff against the same leaf.

## Input

This step consumes the leaf entry point **step 1 produces**: `run_with_rate_limit_recovery` in `plan_tool/rate_limit_loop.py`, plus its injected-seam signature (see step 1's Implementation section for the full seam list). What matters for correctness here:

- **The loop owns only the shared control flow** — the one-shot `rate_limit_retried` guard, the SWITCH branch, the already-active hot-loop guard, the ASK branch, the wait-honoring, transient exponential backoff, and the terminal fallthrough.
- **Every first-party behavior is a seam** — `run_once`, `classify`, `notify`, `select_backend`, `ask_action`, `can_prompt`, `wait`, `prompt_lock`, `sleep`/`clock`, `on_nonsuccess`, `current_backend_name`, plus the plain values `fallback_seconds` / `max_transient_retries` / `transient_base_delay` / starting `attempt`.
- **The loop emits no telemetry and owns no `ExitStack`** — shell's injected `run_once` owns the `ClaudeCallEnd` emit, and shell's wrapper owns the ContextVar scoping.

If step 1's final seam names or the `classify` result shape differ from the above, follow step 1's shipped contract — it is the owner. Do not re-specify the leaf here.

## Files (creates vs edits)

**New files:**
- None.

**Existing files (edits only):**
- `plan_tool/shell.py` — in `claude_invoke`, delete the inline `while True` recovery loop (everything from the `while True:` through the terminal `return rc, stdout`) and replace it with a single `run_with_rate_limit_recovery(...)` call wired to shell's seams. Add the `from plan_tool.rate_limit_loop import run_with_rate_limit_recovery` import. Keep the `shutil.which` guard, `_maybe_warn_shell_prompt_budget`, the policy resolution, and the `ExitStack` + `_rate_limit_backend_scope` scoping in the wrapper. Keep the helpers `_run_once`, `_emit_call_end`, `_notify_or_tool`, `_select_rate_limit_backend`, `_ask_rate_limit_action`, `_can_prompt_on_rate_limit`, `_MISSED_LIMIT_CANARY`, and `_output_tail` — they become the seam bodies.
- `tests/test_shell.py` — add at most one wiring test that shell now calls the leaf (see Tests). The existing rate-limit characterization tests stay unchanged.

## Implementation

**What changes.** `claude_invoke` keeps its pre-loop wrapper work, then hands the recovery loop to the leaf instead of running it inline. The result `(rc, stdout)` the leaf returns is what `claude_invoke` returns. No branch order, guard, message, or exit code changes — this is a behavior-preserving reroute.

**Keep these in the wrapper, before the leaf call (do not move into the leaf):**
- **The PATH guard** — `shutil.which(backend.binary) is None → return EXEC_NOT_FOUND_EXIT, ""`. Fires before any subprocess and before the leaf.
- **The pre-send backstop** — `_maybe_warn_shell_prompt_budget(prompt, backend)`, fired once per call.
- **Policy resolution** — `resolve_on_rate_limit_policy(wait_on_rate_limit)` and `recover_rate_limit = policy.action is not OnRateLimitAction.STOP`. Pass the policy fields the loop needs (the action, `policy.fallback_backend`, and `recover_rate_limit`) into the leaf.
- **The backend scope** — the `with contextlib.ExitStack() as backend_scope:` block and `_rate_limit_backend_scope.set(...)` / `.reset(...)`. Wrap the `run_with_rate_limit_recovery(...)` call, exactly as it wraps the inline loop today. The leaf never creates or resets this stack.

**Wire each seam to shell's existing pieces:**
- **`run_once`** — a closure over `prompt` that calls `_run_once(prompt)` and then `_emit_call_end(...)` with the current attempt, returning the outcome shell's `classify` seam understands. This is the key wiring decision: shell emits `ClaudeCallEnd` **inside `run_once`**, not the loop, so the per-attempt emit and its attempt-number stay exactly as today. The loop hands `run_once` the incremented attempt number.
- **`classify`** — wrap `plan_tool/claude_errors.py:classify(rc, stdout, stderr_text)` and map its `ClaudeFailureKind` onto the loop-local category step 1 defines, carrying the reset epoch, the return `rc`, the payload (`stdout`), and the user hint (`format_user_hint(failure)`).
- **`notify`** — a closure that resolves `get_active_notifier()` at call time and routes through `_notify_or_tool(notifier, message, kind=kind)`. Resolving per call preserves today's per-iteration `notifier = get_active_notifier()` read, so a notifier bound mid-run still receives the message.
- **`select_backend`** — a closure that resolves `get_active_notifier()` at call time and calls `_select_rate_limit_backend(name, notifier=notifier)`, used by the SWITCH auto-swap and the ASK-switch. It closes over `_rate_limit_backend_scope`, which the wrapper set.
- **`ask_action`** / **`can_prompt`** — `_ask_rate_limit_action(notifier)` and `_can_prompt_on_rate_limit`. **`ask_action` must resolve the notifier at call time too**, not capture one before the loop: today `_select_rate_limit_backend(policy.fallback_backend, notifier=notifier)` and `_ask_rate_limit_action(notifier)` both read the same per-iteration `notifier`, so the SWITCH-swap and ASK messages honor a notifier bound mid-run exactly as the `notify` seam does — capturing once would silently drop that for these two sibling seams.
- **`wait`** — wrap `wait_until_epoch(target, sleep=_sleep, clock=_clock)` to a bool: True when its result is `WaitUntilAction.RETRY`, False otherwise. This keeps `WaitUntilAction` out of the leaf.
- **`prompt_lock`** — `RATE_LIMIT_PROMPT_LOCK`. The leaf holds it across the swap/ask/wait, exactly as the inline loop does now.
- **`sleep` / `clock`** — shell's `_sleep` / `_clock` kwargs, so tests still drive backoff and wait timing deterministically.
- **`on_nonsuccess`** — a closure carrying shell's two batch-only surfacings, which launcher lacks:
  - the missed-limit canary (`_MISSED_LIMIT_CANARY.search(...)` over stdout/stderr on an `UNKNOWN_NONZERO`, emitting the "possible missed rate-limit … NOT waiting" notice with `_output_tail`),
  - the raw-nonzero surface (`rc != 0 and not will_retry → notify "exited with code {rc}"` in the notifier form or the `warn(...)` form). The `will_retry` input the loop passes **must be shell's predictive flag** — the `will_retry_rate_limit` / `will_retry_transient` shape (`RATE_LIMIT and recover_rate_limit and not rate_limit_retried`, and the transient-within-budget analog), computed *before* the recovery block resolves — **not** the actual retry outcome. That distinction is load-bearing: a fresh recoverable rate-limit that then switches-then-stops or waits-then-stops is predicted-recoverable, so today it emits **no** "exited with code" line even though the invoke terminates without retrying. Wiring `will_retry` to whether a retry actually happened would newly surface that line on those abandoned-recovery paths and break byte-preservation (no existing pin exercises it, so this is guard-by-construction).

  Preserve the current order: the canary notice comes before the raw-nonzero surface.
- **`current_backend_name`** — `lambda: get_active_backend().name`, used for the already-active comparison and the messages.
- **Plain values** — `fallback_seconds=DEFAULT_RATE_LIMIT_FALLBACK_SECONDS`, `max_transient_retries`, `transient_base_delay`, and the starting `attempt`, all from `claude_invoke`'s existing kwargs/constants.

**Constraints and gotchas that are not free to vary:**
- **`run_once` owns the `ClaudeCallEnd` emit** — do not let the leaf emit. Every attempt (initial + each retry) must still emit exactly one event with the incremented attempt, or the sink tests regress.
- **The ContextVar scope stays the wrapper's** — the `ExitStack` + `_rate_limit_backend_scope.set/reset` must wrap the leaf call so a fallback backend selection cannot outlive the invoke. `test_claude_invoke_scoped_switch_restores_after_fallback_failure` and `test_claude_invoke_parallel_switches_do_not_leak_between_threads` pin this.
- **`notify` must resolve the notifier at call time**, not capture it once before the loop, so a notifier pushed by a live progress line is honored — `test_transient_retry_routes_through_bound_notifier` pins it.
- **The prompt lock must wrap the same three actions** (swap, ask, wait) — this is the leaf's job; shell just passes `RATE_LIMIT_PROMPT_LOCK`. `test_concurrent_rate_limit_prompts_are_serialized` pins it.
- **No message text or exit code changes.** The "already retried once", "no reset time … waiting Ns as fallback", and terminal-hint strings must read identically; the tests assert on them.

**Foundational logic and its other home.** The core behavior is the batch recovery control flow, which now lives once in the leaf. The only sibling copy is `plan_tool/launcher.py:shell_invoker`, rerouted in **step 3** — do not touch it here. The three helpers `_select_rate_limit_backend` / `_ask_rate_limit_action` / `_can_prompt_on_rate_limit` remain near-duplicates of launcher's; the stdlib-only contract keeps them caller-side and injected, so de-duplicating them is not in scope (see Deferred).

## Tests

This is a **refactor** — the characterization tests already exist in `tests/test_shell.py` and are the behavior oracle. They must pass **unchanged** after the reroute. Do not rewrite them; a red is a regression, not an expected adaptation.

Pass-unchanged pins (existing, in `tests/test_shell.py`):
- `test_claude_invoke_waits_then_retries_on_rate_limit` — a RATE_LIMIT then success waits once and retries.
- `test_claude_invoke_skips_wait_when_flag_disabled` — recovery disabled returns without waiting.
- `test_claude_invoke_rate_limit_menu_stop_returns_without_retry` — ASK → STOP returns.
- `test_claude_invoke_rate_limit_menu_switches_backend_and_retries` — ASK → SWITCH retries.
- `test_claude_invoke_switch_policy_switches_backend_without_prompt` — SWITCH policy swaps without a prompt.
- `test_claude_invoke_switch_policy_degrades_to_wait_when_fallback_bad` — bad fallback degrades to wait.
- `test_claude_invoke_switch_policy_degrades_when_fallback_binary_missing` — missing fallback binary degrades to wait.
- `test_claude_invoke_switch_to_active_backend_does_not_hot_loop` — fallback naming the active backend degrades to a wait.
- `test_claude_invoke_switch_bounds_when_fallback_also_rate_limited` — a rate-limited fallback still honors the one-shot guard.
- `test_claude_invoke_scoped_switch_restores_after_fallback_failure` — the backend scope is restored after a failed swap.
- `test_claude_invoke_parallel_switches_do_not_leak_between_threads` — per-thread ContextVar scoping holds.
- `test_concurrent_rate_limit_prompts_are_serialized` — the prompt lock serializes swap/ask/wait.
- `test_claude_invoke_retries_transient_with_exponential_backoff` — transient backoff sequence.
- `test_claude_invoke_transient_gives_up_after_max_attempts` — transient past budget surfaces the hint and returns.
- `test_session_limit_banner_waits_and_retries` — a session-limit banner waits and retries.
- `test_missed_limit_canary_on_unknown_nonzero` — the canary fires on an UNKNOWN_NONZERO that mentions a limit.
- `test_rate_limit_hint_tool_plain` / `test_transient_retry_tool_plain` — the no-notifier `tool()` message forms.
- `test_transient_retry_routes_through_bound_notifier` — a bound notifier receives the retry notice.
- `test_invoke_returns_127_when_claude_not_on_path` — the wrapper PATH guard returns `(127, "")` before the leaf.
- `test_invoke_non_zero_rc_still_emits_event` — a non-zero attempt still emits one `ClaudeCallEnd` (emit stays in `run_once`).
- `test_backstop_reuses_backend_prompt_bytes` — the pre-send backstop still runs in the wrapper.

New (optional, one test):
- `test_claude_invoke_routes_through_shared_leaf` — monkeypatch `plan_tool.shell.run_with_rate_limit_recovery` (or the imported name) and assert `claude_invoke` calls it once with shell's seams, returning its result. Keep it thin — the behavior pins above already prove the wiring; this only nails the reroute so a future accidental re-inline is caught.

### Test-creation order (refactor step)

- The characterization tests listed above are already written (they proved the batch copy). Treat them as the **write-first** set: run the full `tests/test_shell.py` green **before** editing `claude_invoke`, then reroute, then confirm the same tests stay green **unmodified**.
- Add the optional wiring test after the reroute, if at all.
- **Pass-unchanged gate:** every pin above stays green with no edits to its body. A change to any assertion string, wait count, or emit count means the extraction changed behavior — fix the wiring, not the test.

## Acceptance criteria

- `claude_invoke`'s body no longer contains the inline `while True` recovery loop; it calls `run_with_rate_limit_recovery` from `plan_tool/rate_limit_loop.py` once and returns its `(rc, stdout)`.
- `plan_tool/shell.py` imports `plan_tool.rate_limit_loop`; it does **not** import `plan_tool.launcher`.
- The wrapper still returns `(EXEC_NOT_FOUND_EXIT, "")` when `shutil.which(backend.binary)` is None, without reaching the leaf.
- Every attempt still emits exactly one `ClaudeCallEnd` via `_emit_call_end` inside the injected `run_once`; `test_invoke_non_zero_rc_still_emits_event` and the sink tests pass.
- `uv run pytest tests/test_shell.py -q` exits 0 with the listed characterization tests unchanged.
- `uv run pytest tests/ -q` exits 0 (no import cycle, no cross-caller regression).

## References

- [contextlib — ExitStack (Python Standard Library)](https://docs.python.org/3/library/contextlib.html) — The register-and-unwind the wrapper keeps around the leaf call so a fallback-backend selection cannot outlive the invoke.
- [contextvars — Context Variables (Python Standard Library)](https://docs.python.org/3/library/contextvars.html) — Semantics for `_rate_limit_backend_scope`, the per-invoke ContextVar shell keeps caller-side and passes the loop via `select_backend`.
- [subprocess — Popen and run (Python Standard Library)](https://docs.python.org/3/library/subprocess.html) — The batch `subprocess.run` mode inside `_run_once` that stays caller-side as shell's injected `run_once`.
- [shutil.which (Python Standard Library)](https://docs.python.org/3/library/shutil.html) — The None-on-missing-binary contract behind the `EXEC_NOT_FOUND_EXIT` guard the wrapper keeps ahead of the leaf.
- [Rate limits — Anthropic Claude API](https://docs.claude.com/en/api/rate-limits) — The 429 / retry-after behavior the rerouted recovery path detects and waits on.

## Deferred

- **Rerouting `launcher.shell_invoker` through the leaf** — step 3; this step reroutes only the batch `shell.claude_invoke` copy.
- **De-duplicating `_select_rate_limit_backend` / `_ask_rate_limit_action` / `_can_prompt_on_rate_limit`** — they stay caller-side and injected under the leaf's stdlib-only contract; a shared home would need first-party imports and break the leaf. Out of scope for this plan.
- **Removing BACKLOG #101 and registering the leaf in CLAUDE.md** — step 4.
- **Any rate-limit policy or behavior change** — this is a pure reroute; the extracted loop must stay behavior-identical to the copy it replaces.
