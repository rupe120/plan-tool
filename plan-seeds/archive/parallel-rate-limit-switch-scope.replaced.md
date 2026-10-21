> **Replaced**: this file has been superseded by `docs/implementation-plans/2-parallel-rate-limit-switch-scope.md`.
> Preserved here for history; do not edit.

# Parallel rate-limit backend switch scope

Source backlog entry: `BUG_BACKLOG.md` RISK, "Auto-`SWITCH` flips the process-wide backend for all parallel workers".

Author a plan to harden the `--on-rate-limit switch` behavior when multiple workers share one Python process, especially `completeness-apply --jobs N`.

Current behavior to ground in code:

- `plan_tool.backend.get_active_backend` / `set_active_backend` use one process-wide active backend.
- `plan_tool.shell.claude_invoke` and `plan_tool.launcher.shell_invoker` handle `OnRateLimitAction.SWITCH` by calling `select_active_backend` through their local `_select_rate_limit_backend` helpers.
- `RATE_LIMIT_PROMPT_LOCK` serializes switch/prompt/wait handling, but it does not make backend selection worker-local.
- Parallel completeness apply uses threads in one process, so one worker's auto-switch can affect another worker that has not spawned yet.

Required design decision:

- Decide and encode the intended contract:
  - whole-process switch semantics are intentional because rate limits are account-wide, or
  - each worker/spawn should keep its own backend selection and switching should be scoped to that worker/spawn.
- Do not leave the current behavior implicit. If preserving whole-process semantics, document it and pin it with tests. If changing semantics, implement the smallest scoped backend mechanism that preserves existing single-threaded behavior.

Implementation constraints:

- Keep `backend.py` cycle-free and stdlib-only.
- Preserve existing CLI precedence: `--backend` / `PLAN_TOOL_BACKEND` selects the initial backend, and `--fallback-backend` / `PLAN_TOOL_FALLBACK_BACKEND` only matters for switch policy.
- Cover both subprocess sites: batch `shell.py` and streaming `launcher.py`.
- Cover both successful switch and failed/misconfigured fallback paths.
- Include concurrency-oriented tests that would fail if one worker's auto-switch leaks into another worker unexpectedly, or if the chosen contract is intentionally whole-process, tests that prove and document that behavior.
- Update operator docs/help where the contract needs to be visible.

Backlog reconciliation requirement:

- The resulting plan's final step must update `BUG_BACKLOG.md`: remove the RISK if the behavior is documented/pinned or fixed, or replace it with a narrower follow-up if a residual design risk remains.
