> **Auto-archived**: this plan was swept on 2026-07-12 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

---
title: Rate Limit Loop Extraction
status: completed
priority: medium
enforce_step_tests: true
steps:
- id: 1
  title: Add plan_tool/rate_limit_loop.py with the shared recovery loop and helpers
  creates:
  - plan_tool/rate_limit_loop.py
  - tests/test_rate_limit_loop.py
  complexity: high
  change_type: refactor
  detail: docs/implementation-plans/plan-details/rate-limit-loop-extraction/01-plan-tool-rate-limit-loop-py-shared.md
  status: done
- id: 2
  title: Route shell.claude_invoke through the shared rate-limit loop
  files:
  - plan_tool/shell.py
  - tests/test_shell.py
  complexity: medium
  change_type: refactor
  depends_on:
  - 1
  detail: docs/implementation-plans/plan-details/rate-limit-loop-extraction/02-route-shell-claude-invoke-through.md
  status: done
- id: 3
  title: Route launcher.shell_invoker through the shared rate-limit loop
  files:
  - plan_tool/launcher.py
  - tests/test_launcher.py
  complexity: medium
  change_type: refactor
  depends_on:
  - 1
  - 2
  detail: docs/implementation-plans/plan-details/rate-limit-loop-extraction/03-route-launcher-shell-invoker-through.md
  status: done
- id: 4
  title: 'Remove BACKLOG #101 and note the new leaf in CLAUDE.md'
  files:
  - BACKLOG.md
  - CLAUDE.md
  complexity: low
  change_type: non-code
  depends_on:
  - 1
  - 2
  - 3
  detail: docs/implementation-plans/plan-details/rate-limit-loop-extraction/04-remove-backlog-101-note-new-leaf-claude.md
  status: done
---
# Rate Limit Loop Extraction

## Overview

This plan extracts the rate-limit recovery loop that `shell` and `launcher` each carry today into a shared `plan_tool/rate_limit_loop.py` leaf, then routes both callers through it so the 429-detect / wait-or-switch state machine lives in one place. The two copies share an **identical recovery control flow** but differ in **surfacings** (shell emits `ClaudeCallEnd` inline and carries a missed-limit canary + a raw "exited with code" line; launcher emits from `run_step` and resolves its notifier internally), so the leaf owns the shared control flow while each caller's differences are handled at the boundary. Those differences split two ways: some are **injected into the leaf** (the run-once closure — batch `subprocess.run` vs streaming `Popen` — the sleep/clock seams, the notify sink, and the backend-select / ask closures), while others stay **entirely caller-side and never cross the leaf boundary** (shell's `EXEC_NOT_FOUND` `shutil.which` path guard and prompt-budget backstop, launcher's `_last_stats` handoff, and the two per-invoke backend-scope ContextVars — each scoped by the caller's own `ExitStack`, reaching the loop only through the injected `select_backend` closure). Being a pure refactor, it changes no observable behavior or exit codes: characterization tests pinned before the change pass unchanged after. Shipping it closes BACKLOG #101 and registers the new leaf in CLAUDE.md.

## Problem statement

The 429-detect / wait-or-switch rate-limit recovery state machine is duplicated: `shell.claude_invoke` (batch `subprocess.run`) and `launcher.shell_invoker` (streaming `Popen`) each carry their own near-identical copy of the same loop — the *recovery control flow* is the same; only the surfacings (telemetry emit site, shell's canary + raw-nonzero line, notifier resolution) differ. The two copies must stay behavior-identical on that shared control flow — same detection, same wait-vs-switch policy, same backoff and `wait_until_epoch` timing — yet nothing enforces that, so a fix or policy change to one silently diverges from the other. BACKLOG #101 tracks this duplication as the motivating debt.

The user-visible symptom is drift risk: a rate-limit tweak applied in one caller but not the other means the `run` path and the batch/authoring paths recover from 429s differently, and the divergence surfaces only under a live rate limit — the hardest condition to reproduce or test. Consolidating the loop into one leaf makes the shared policy the single source of truth while keeping each caller's genuinely-distinct concerns (run-once closure, sleep/clock seams, `EXEC_NOT_FOUND` guard, the two backend-scope ContextVars) injectable rather than unified.

## Architecture

The plan introduces one new module, `plan_tool/rate_limit_loop.py`, a stdlib-only leaf that owns the 429-detect / wait-or-switch recovery state machine today duplicated inside `shell.claude_invoke` and `launcher.shell_invoker`. It sits **below** both `shell` and `launcher` in the dependency graph — a sibling of the other cycle-free leaves — so both wrappers import it and neither imports the other; the extraction must not introduce a `shell`↔`launcher` edge or a cycle through `backend`.

The leaf's contract is a single recovery loop; the caller-specific concerns split into two disjoint categories, and conflating them would blur the very contract this refactor exists to define:

- **Injected into the leaf** (cross the boundary as parameters the loop consumes or calls): the **run-once closure** — the loop calls it **each iteration with the current, live-incrementing attempt** (`current_attempt += 1` on every retry), so it is not merely "batch vs streaming `Popen`": shell folds its `_emit_call_end(attempt=…)` into it and launcher its `_run_streaming_once(attempt=…)`, and a stale attempt would drift telemetry / sibling-log labeling; the **notify sink**, the **`select_backend` / `ask_action` / `can_prompt` closures**, the **classify seam** and the **wait wrapper**, the recovery **policy inputs** (`recover_rate_limit`, the narrowed wait-vs-switch action, `fallback_backend`), the **sleep/clock seams** (so tests drive backoff and `wait_until_epoch` timing deterministically), and the optional **`on_nonsuccess` hook** (shell provides it; launcher passes `None`). `on_nonsuccess` is genuinely *injected*, not wrapper-only: shell's missed-limit canary and raw "exited with code" line are emitted **mid-loop** (between `classify` and the rate-limit branch), so the loop must **call** the hook — handing it the outcome, the opaque `failure`, and its own **predictive will-retry decision** (computed from `rate_limit_retried` / `transient_attempts` / `recover_rate_limit`), because the raw-nonzero line's suppression is gated on that loop state today (`rc != 0 and not (will_retry_rate_limit or will_retry_transient)`). A surfacing tied to loop state is a seam the loop feeds, not a wrapper-only concern.
- **Wrapper-only — never crosses the leaf boundary**: `shell`'s upfront **`EXEC_NOT_FOUND` `shutil.which` path guard** and its **prompt-budget backstop**, `launcher`'s **`_last_stats` *initial reset*** (`shell_invoker._last_stats = ClaudeRunStats()` set once *before* the loop), and the **two per-invoke backend-scope ContextVars** (each scoped by the caller's own `ExitStack`). The ContextVar's effect reaches the loop *only* through the injected `select_backend` closure that closes over it — the leaf never sees, creates, or resets an `ExitStack`. Note only the *initial reset* of `_last_stats` is wrapper-only: the **per-attempt stash** (`_last_stats = stats` after each `_run_streaming_once`) runs inside the loop and so rides in launcher's injected `run_once` closure — the same shape as shell folding `_emit_call_end` into its `run_once` — so the most recent attempt's stats win on a retry.

The shared loop owns only the shared **control flow**: the wait-or-switch cascade, the one-shot guard, exponential backoff for transients, and honoring the injected `wait`'s RETRY/STOP result. **Detection** (429 vs transient vs terminal) and the **epoch resolution** are *injected*, not leaf-owned — the `classify` seam categorizes the outcome and the `wait` wrapper owns `wait_until_epoch` — so the leaf branches on a neutral category and a bool, never on `ClaudeFailureKind` or `WaitUntilAction` (both first-party, which would break the stdlib-only leaf). This keeps the rate-limit policy a single source of truth while leaving each wrapper's observable behavior unchanged. Note the boundary is not a clean "control flow here, surfacings there" split: a surfacing gated on loop state (the raw-nonzero line, the per-attempt telemetry) is fed by the loop through an injected seam, while a surfacing independent of loop state (the PATH guard, the prompt-budget backstop) stays wrapper-only.

The major trade-off is **inject-don't-unify**: fusing the run-once modes or the ContextVar scoping into the leaf would shrink the seam count but would either change one caller's behavior or leak subprocess-mode knowledge into a module that should stay agnostic. Parameterizing those concerns costs a wider function signature but preserves the pure-refactor guarantee — no observable behavior or exit-code change — which the characterization tests pinned before the change (and passing unchanged after) enforce. Rollout is ordered by dependency: the leaf lands first (step 1) with its own characterization tests, then `shell` (step 2) and `launcher` (step 3) route through it, and step 4 closes BACKLOG #101 and registers the leaf in CLAUDE.md.

## References

- [contextvars — Context Variables (Python Standard Library)](https://docs.python.org/3/library/contextvars.html) — Official reference for ContextVar semantics, needed to preserve the two distinct per-invoke backend-scope ContextVars (seam #9) the shared loop must accept without unifying.
- [contextlib — ExitStack (Python Standard Library)](https://docs.python.org/3/library/contextlib.html) — Documents ExitStack's dynamic register-and-unwind behavior, the mechanism each caller uses to scope its rate-limit backend selection around the extracted recovery loop.
- [subprocess — Popen and run (Python Standard Library)](https://docs.python.org/3/library/subprocess.html) — Reference for the batch subprocess.run vs streaming Popen invocation modes that stay caller-side as the injectable run-once closures (seam #2).
- [shutil.which (Python Standard Library)](https://docs.python.org/3/library/shutil.html) — Specifies shutil.which's None-on-missing-binary contract, which drives shell's upfront EXEC_NOT_FOUND path guard (seam #4) that must remain in the wrapper, not the shared leaf.
- [time — sleep, time, monotonic (Python Standard Library)](https://docs.python.org/3/library/time.html) — Covers the clock and sleep primitives underlying the transient exponential-backoff and wait_until_epoch timing that the loop parameterizes as injectable sleep/clock seams.
- [Rate limits — Anthropic Claude API](https://docs.claude.com/en/api/rate-limits) — Authoritative source for 429 responses and retry-after semantics, the vendor behavior the extracted recovery state machine is built to detect and wait on.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

- **Unifying the caller-specific seams** (run-once closure, sleep/clock, `EXEC_NOT_FOUND` guard, the two backend-scope ContextVars) — the inject-don't-unify trade-off keeps them caller-side; folding them into the leaf would change one caller's behavior or leak subprocess-mode knowledge into an agnostic module.
- **Any change to rate-limit policy or behavior** (429 detection, wait-vs-switch, backoff, `wait_until_epoch` timing) — this is a pure refactor; the extracted loop must stay byte-for-byte behavior-identical to the two copies it replaces.
- **Callers other than `shell.claude_invoke` and `launcher.shell_invoker`** — no other surface carries a duplicate of this loop, so none is in scope to reroute.
- **Backend selection / fallback mechanics** (`backend.py`, `--on-rate-limit`, `--fallback-backend`) — the leaf consumes the existing wait-vs-switch decision; it does not alter how backends are chosen or scoped.

## Risks

- **Behavioral drift during extraction** — pulling the loop out of each wrapper silently changes one caller's 429 detection, wait-vs-switch policy, backoff, or `wait_until_epoch` timing. Severity: high (surfaces only under a live rate limit, the hardest condition to reproduce). Mitigation: characterization tests pinned on both callers before the change and required to pass unchanged after. Residual gap: pinned tests only cover the paths they exercise; a rate-limit edge not represented in a fixture can still drift undetected.
- **New import cycle** — routing both wrappers through the leaf introduces a `shell`↔`launcher` edge or a cycle through `backend`. Severity: medium (caught at import time, so it fails fast). Mitigation: keep `rate_limit_loop.py` a stdlib-only leaf below both wrappers, neither importing the other. Residual gap: none beyond ordinary import-graph review.
- **Over-unification of injected seams** — folding a caller-specific concern (run-once closure, sleep/clock, `EXEC_NOT_FOUND` guard, the two backend-scope ContextVars) into the leaf to shrink the signature, changing one caller's behavior or leaking subprocess-mode knowledge into the agnostic module. Severity: medium. Mitigation: the inject-don't-unify contract keeps each concern caller-side and passed in; the Out-of-scope section names this explicitly.
- **ContextVar scope leak** — the two per-invoke backend-scope ContextVars are re-scoped incorrectly across the extracted loop, so a backend selection outlives its `ExitStack` and bleeds into the next invoke. Severity: high if it occurs (corrupts subsequent invocations). Mitigation: each caller keeps its own `ExitStack` scoping and passes the ContextVar in rather than the leaf owning it. Residual gap: correct scoping depends on the wrapper, not the leaf, so the leaf cannot enforce it.

## Testing

**Per-step test strategy** (derived from each step's `change_type`):

- step 1 (refactor) — characterization tests pinned before the change; pass unchanged after.
- step 2 (refactor) — characterization tests pinned before the change; pass unchanged after.
- step 3 (refactor) — characterization tests pinned before the change; pass unchanged after.
- step 4 (non-code) — verification appropriate to the artifacts; no test-ordering directive.

## Acceptance criteria

- `plan_tool/rate_limit_loop.py` exists and is a stdlib-only leaf: `grep -E '^(from|import) plan_tool' plan_tool/rate_limit_loop.py` returns no first-party imports (no edge to `shell`, `launcher`, or `backend`).
- No `shell`↔`launcher` import edge is introduced: neither `plan_tool/shell.py` imports `plan_tool.launcher` nor vice versa, and both import `plan_tool.rate_limit_loop`.
- `tests/test_rate_limit_loop.py` covers, against injected sleep/clock/wait seams and a fake `run_once` that yields scripted categories, the loop-owned invariants: rate-limit wait-or-switch handling, the wait-vs-switch policy branching, transient exponential backoff, and honoring the injected wait's RETRY/STOP result. (Detection and epoch-resolution are injected seams, exercised at the callers, not re-tested in the leaf.)
- Characterization tests pinned on `shell.claude_invoke` (`tests/test_shell.py`) and `launcher.shell_invoker` (`tests/test_launcher.py`) before the extraction pass unchanged after it — same detection, wait-vs-switch policy, backoff, and timing.
- The full suite is green after all steps land: `uv run pytest tests/ -q` exits 0.
- BACKLOG #101 is removed from `BACKLOG.md`, and `CLAUDE.md` registers `rate_limit_loop.py` as a leaf below `shell`/`launcher`.

## Deferred

- **Broadening characterization fixtures to cover un-exercised rate-limit edges** — the pinned tests only cover the paths they represent (the residual gap named under the "Behavioral drift" risk); widening fixture coverage for 429 edges not currently exercised is a separate testing-scope concern beyond the byte-for-byte extraction, and could return once a real edge surfaces.
- **Routing any future third caller through the shared leaf** — today only `shell.claude_invoke` and `launcher.shell_invoker` carry the loop; a later surface that grows its own copy would reuse this leaf, but no such caller exists now, so it is postponed rather than permanently excluded.
