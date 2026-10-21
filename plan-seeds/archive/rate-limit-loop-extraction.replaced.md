> **Replaced**: this file has been superseded by `docs/implementation-plans/2-rate-limit-loop-extraction.md`.
> Preserved here for history; do not edit.

## Overview

Factor out the **rate-limit / transient-retry recovery loop** that is maintained
as two near-identical copies — `plan_tool/shell.py:claude_invoke` (the batch
Claude seam) and `plan_tool/launcher.py:shell_invoker` (the streaming run-step
seam) — into **one shared leaf**, `plan_tool/rate_limit_loop.py`, parameterized
so each invoker injects its incidental differences (notify sink, run-once
callable, backend-scope ContextVar). Both invokers become thin wrappers around
the shared loop. This is a **behavior-preserving structural refactor**: the goal
is that a future fix to the recovery state machine is written **once**, not
twice, and the existing shell + launcher rate-limit test suites stay green as the
parity oracle. (Source: `BACKLOG.md` **#101**.)

> **Why this refactor exists — a live, recurring hazard, not a theoretical one.**
> The two copies encode the *same* state machine but must be edited in lockstep.
> The `already_active` hot-loop guard (a fallback naming the active backend and
> re-selecting forever) had to land in **both** copies plus mirrored tests. Then
> the `parallel-rate-limit-switch-scope` branch extended both copies again
> (invoke-scoped `ContextVar`/`ExitStack`), and the parity hazard **materialized**:
> `launcher.py`'s `RATE_LIMIT_PROMPT_LOCK` comment was left describing the old
> process-wide mutation while `shell.py`'s twin was updated. Comment drift was
> fixed that session; the structural duplication that *causes* the drift is this
> plan's subject.

## Problem statement

**Parity-by-copy is a standing correctness hazard.** A bug fixed in one invoker
silently persists in the other until someone notices. `shell.py:claude_invoke`
(the loop body spans roughly `447–638`) and `launcher.py:shell_invoker`
(roughly `562–687`) implement a byte-for-byte-identical recovery cascade —
one-shot `rate_limit_retried` guard, SWITCH → `_select_rate_limit_backend` →
degrade-to-wait, the `already_active` hot-loop guard, the interactive ASK menu,
`wait_until_epoch` semantics, and transient exponential backoff — differing only
in **incidental seams** (a notifier object vs a plain `print`; a batch
`subprocess.run` vs a streaming `Popen`; where per-attempt telemetry is emitted;
a couple of caller-only pre-guards). Every one of those shared behaviors is
maintained twice. The differences are injectable, not structural, so the loop is
a clean extraction candidate.

## Architecture

**A new shared leaf: `plan_tool/rate_limit_loop.py`.** The import layering today
is `backend < claude_errors < shell < launcher` (`launcher` imports from
`shell`; `shell` imports `claude_errors`; `claude_errors` imports `backend`;
`backend` is a stdlib-only leaf). The extracted loop needs
`ClaudeFailureKind` / `OnRateLimitAction` / `wait_until_epoch` /
`format_user_hint` / `RATE_LIMIT_PROMPT_LOCK` / the policy resolver (all in
`claude_errors`) plus `get_active_backend` / `scoped_select_active_backend`
(`backend`) and `BackendConfigError` (`backend_config`). The **only** placement
that stays acyclic and single-concern is a **new leaf that imports strictly
downward** (`claude_errors` + `backend` + `backend_config`) and is imported *down
into* by both `shell` and `launcher`:

- **`backend.py` is ruled out** — it would need `claude_errors` symbols, forcing
  `backend → claude_errors → backend`, breaking the documented stdlib-only-leaf
  invariant.
- **`claude_errors.py` is possible but rejected** — it could host the loop only
  if the notify sink and backend-scope var stay injected (importing
  `get_active_notifier` from `shell` would cycle), and it would bloat a
  classification/policy module with full recovery orchestration. Prefer the leaf.

The new leaf sits **between `claude_errors` and `shell`**. It hosts the shared
loop **and** the three helpers that are near-identical copies today —
`_select_rate_limit_backend`, `_ask_rate_limit_action`, `_can_prompt_on_rate_limit`
(the last is already byte-identical in both) — each parameterized by the injected
notify sink so the notifier difference is passed in, never imported.

**The extraction contract.** A single entry point both invokers delegate to.
Candidate shape (final names/params are the implementer's to refine, but the
seams must all be injectable):

```
run_with_rate_limit_recovery(
    run_once,            # attempt -> the classification inputs; owns its own per-attempt telemetry
    *, policy, classify, notify, select_backend, ask_action,
    backend_scope_var,   # each caller's own ExitStack ContextVar, passed in (NOT unified)
    on_nonsuccess=None,  # shell's missed-limit canary + raw-nonzero surface; launcher passes None
    max_transient_retries=..., transient_base_delay=..., sleep=time.sleep, clock=time.time,
) -> tuple[int, str]
```

**The injectable seams (what stays caller-side).** Each invoker keeps its
differences inside the closures it injects; none change the recovery control
flow. They must be enumerated and individually preserved:

1. **Notify sink** — shell's `_notify_or_tool(notifier, …)` vs launcher's
   `_notify_or_print(…)` (the no-notifier fallback formats differently: `tool()`
   vs a raw `plan-tool:` print — both are asserted by their tests).
2. **Run-once callable / invocation mode** — shell's batch `_run_once` (returns
   rc/stdout/stderr/duration/bytes/stats) vs launcher's streaming
   `_run_streaming_once` (NDJSON `Popen`, takes run_logger/attempt/sibling_log_dir).
3. **Per-attempt telemetry placement** — shell emits `ClaudeCallEnd` in the loop
   via `_emit_call_end`; launcher emits it inside the streaming helper via the
   injected `run_logger`. The shared loop must not assume either — the run-once
   closure owns its own emission.
4. **Path guard** — shell's upfront `shutil.which(binary) is None →
   EXEC_NOT_FOUND_EXIT` guard; launcher has none. Stays in shell's wrapper.
5. **Prompt-budget backstop** — shell's `_maybe_warn_shell_prompt_budget` before
   the loop; launcher has no equivalent here. Stays in shell's wrapper.
6. **Missed-limit canary + raw-nonzero surface** — shell's `_MISSED_LIMIT_CANARY`
   UNKNOWN_NONZERO handling and "surface raw nonzero unless about-to-retry"
   block; launcher has neither. Injected via the `on_nonsuccess` hook (launcher
   passes `None`).
7. **`attempt`/`phase` params** — shell exposes a caller-settable starting
   `attempt` and `phase="claude_invoke"`; launcher hard-starts at 1, no phase.
8. **Stats handoff** — launcher stashes `shell_invoker._last_stats = stats` on
   the function object so `run_step` reads usage without widening the `Invoker`
   protocol; shell has no such attribute. Stays in launcher's wrapper.
9. **Backend-scope ContextVar** — the two are **distinct** vars
   (`plan_tool_rate_limit_backend_scope` vs
   `plan_tool_launcher_rate_limit_backend_scope`); pass each caller's var into
   the loop, do **not** unify them.
10. **Streaming-only ContextVars** — launcher reads `_run_logger_var` /
    `_sibling_log_dir_var` to feed streaming; shell has no analog. Stays in
    launcher's run-once closure.
11. **Cosmetic** — return-var naming, comment wording. No behavioral weight.

**Thin wrappers.** After extraction, `shell.claude_invoke` and
`launcher.shell_invoker` retain their public signatures and their caller-only
pre-guards, build their run-once closure + notify sink, and delegate the recovery
loop to the shared leaf. Neither retains its own copy of the state machine or the
three shared helpers.

**Parity-first discipline (a required early step, before any deletion).** Prove
the two loop bodies behaviorally identical modulo the eleven seams above —
diff them stage by stage against the shared-state-machine table (SUCCESS →
RATE_LIMIT one-shot guard → SWITCH/degrade → ASK → wait → transient backoff →
terminal fallthrough). Extract the shared loop and route **one** invoker through
it with its full test suite green *before* routing the second and deleting the
duplicated bodies. Do not delete a copy until its invoker delegates and its tests
pass.

## Out of scope

- **Changing the recovery semantics.** This is a pure extraction — the observable
  behavior of both invokers (what they wait on, when they switch, what they
  print, what they return) must be identical before and after. No new policy, no
  new backoff math, no changed prompts.
- **`backend.py`'s leaf status.** It stays stdlib-only; the new module imports it,
  never the reverse.
- **The `Invoker` protocol.** Keep launcher's `_last_stats` function-attribute
  handoff exactly as-is; do not widen the protocol to carry stats.
- **CLI policy resolution** (`--on-rate-limit`, `PLAN_TOOL_ON_RATE_LIMIT`,
  `--fallback-backend`) — unchanged; the shared loop consumes the already-resolved
  policy.
- **`claude_errors.py`'s existing primitives** (`wait_until_epoch`, `classify`,
  `ask_on_rate_limit_action`, `resolve_on_rate_limit_policy`,
  `RATE_LIMIT_PROMPT_LOCK`) — reused unchanged, not moved.

## Risks

- **A parity break slips through** — the whole point is behavior-preservation, so
  a subtle divergence (e.g. the canary firing for launcher, or the two backend-
  scope vars getting unified) would be a regression the extraction was meant to
  prevent. Mitigation: the parity-first discipline above (diff first; route one
  invoker at a time; keep both invoker test modules green as the oracle; delete a
  copy only after its wrapper delegates and passes).
- **An import cycle** — placing the loop wrong (in `backend`, or importing
  `get_active_notifier` from `shell` into the new leaf) would cycle. Mitigation:
  the new leaf imports strictly downward (`claude_errors`/`backend`/`backend_config`)
  and the notify sink is **injected**, never imported; a targeted import test
  asserts the leaf pulls in neither `shell` nor `launcher`.
- **The `on_nonsuccess` hook mis-scopes shell's canary** — if it fires for
  launcher, launcher gains a surface it never had. Mitigation: launcher passes
  `on_nonsuccess=None`; a launcher test asserts no canary/raw-nonzero surface.

## Testing

- **Parity oracle (must stay green, unchanged):** the module-level rate-limit
  functions in `tests/test_shell.py` (wait-then-retry, skip-when-disabled, the
  ASK-menu stop/switch pair, the SWITCH-policy switch/degrade/missing-binary/
  hot-loop/bounds/scoped-restore/parallel-isolation set, the serialized-prompt
  lock, transient backoff, context-overflow-no-retry, transient-give-up,
  unknown-nonzero-no-retry) plus `TestNotifierRouting`; and the matching
  functions in `tests/test_launcher.py` plus `TestShellInvokerStatsHandoff` and
  `TestShellInvokerContextVarPlumbing`. These pin the notify-sink, `_last_stats`,
  and streaming-ContextVar seams that differ between copies.
- **Primitives (stay green trivially):** `tests/test_claude_errors.py` exercises
  the shared building blocks the extracted loop reuses.
- **Integration guard:** the `--on-rate-limit` policy-resolution and
  parallel-worker serialization coverage under `tests/cli/`.
- **New direct coverage:** `tests/test_rate_limit_loop.py` (mirrors the new
  source module) drives `run_with_rate_limit_recovery` with a **fake run-once**
  callable and a recording notify sink, asserting each recovery branch
  (one-shot guard, switch-then-retry, degrade-to-wait, ask-stop, ask-switch,
  transient backoff, terminal fallthrough) once, at the leaf, so a future fix is
  test-covered in one place instead of two.

## Acceptance criteria

- A new module `plan_tool/rate_limit_loop.py` exists and hosts the recovery loop
  plus the `_select_rate_limit_backend` / `_ask_rate_limit_action` /
  `_can_prompt_on_rate_limit` helpers, parameterized by an injected notify sink.
- `plan_tool/shell.py:claude_invoke` and `plan_tool/launcher.py:shell_invoker`
  each contain **no** rate-limit state-machine loop body and **no** private copy
  of those three helpers; both delegate to `rate_limit_loop`.
- Importing `plan_tool.rate_limit_loop` pulls in neither `plan_tool.shell` nor
  `plan_tool.launcher` (a test asserts this), and the package still imports with
  no cycle.
- Every rate-limit / switch / wait / transient / notifier / stats / ContextVar
  test named in **Testing** passes unchanged (no test edits to accommodate the
  refactor beyond import-path updates), and the full `pytest` suite passes.
- `tests/test_rate_limit_loop.py` covers each recovery branch of the shared loop
  directly with a fake run-once callable.
- The final step updates `BACKLOG.md`: remove the shipped **#101** entry (and its
  mention in the priority-tier roll-up), so the backlog reflects the extraction
  landing.

## Deferred

- **Collapsing the two backend-scope ContextVars into one.** They are kept
  distinct here (each caller passes its own) to preserve exact isolation behavior;
  whether a single shared var is safe across the batch and streaming seams is a
  separate question, not required for the de-duplication.
- **Unifying the batch vs streaming run-once helpers.** `_run_once` and
  `_run_streaming_once` stay caller-side; a shared subprocess-invocation
  abstraction is a larger, separate refactor.
