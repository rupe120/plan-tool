> **Replaced**: this file has been superseded by `docs/implementation-plans/2-parallel-rate-limit-switch-scope.md`.
> Preserved here for history; do not edit.

## Overview

Harden `--on-rate-limit switch` behavior when multiple workers share one Python process, especially `completeness-apply --jobs N`. The plan must make the backend-switching contract explicit, then either document and test whole-process switch semantics or implement worker/spawn-scoped backend selection while preserving existing single-threaded behavior. The work must preserve CLI precedence for `--backend`, `PLAN_TOOL_BACKEND`, `--fallback-backend`, and `PLAN_TOOL_FALLBACK_BACKEND`, cover both subprocess sites in `shell.py` and `launcher.py`, and end by reconciling the `BUG_BACKLOG.md` RISK entry.

## Problem statement

Today `plan_tool.backend.get_active_backend` / `set_active_backend` use one process-wide active backend. `plan_tool.shell.claude_invoke` and `plan_tool.launcher.shell_invoker` handle `OnRateLimitAction.SWITCH` by calling `select_active_backend` through local `_select_rate_limit_backend` helpers, and `RATE_LIMIT_PROMPT_LOCK` serializes switch/prompt/wait handling without making backend selection worker-local. Because parallel completeness apply uses threads in one process, one worker's auto-switch can affect another worker that has not spawned yet. The current contract is implicit, so operators and tests cannot tell whether this cross-worker backend change is intended account-wide behavior or a bug.

## Architecture

The first design choice is to encode the intended contract for `--on-rate-limit switch`: either whole-process switch semantics are intentional because rate limits are account-wide, or each worker/spawn keeps its own backend selection and switching is scoped to that worker/spawn. The plan must not leave the current behavior implicit.

If preserving whole-process semantics, the architecture is documentation and tests around the existing process-wide active backend in `plan_tool.backend.get_active_backend` / `set_active_backend`, with operator-facing docs/help that make the cross-worker behavior visible.

If changing semantics, introduce the smallest scoped backend mechanism that keeps `backend.py` cycle-free and stdlib-only, preserves existing single-threaded behavior, and lets `plan_tool.shell.claude_invoke` and `plan_tool.launcher.shell_invoker` apply `OnRateLimitAction.SWITCH` without leaking one worker/spawn's fallback selection into another. The initial backend must still come from `--backend` / `PLAN_TOOL_BACKEND`, while `--fallback-backend` / `PLAN_TOOL_FALLBACK_BACKEND` only matters for switch policy.

## Risks

- Cross-worker backend leakage: one worker's auto-switch can affect another worker in the same process; severity is high for parallel `completeness-apply --jobs N`; mitigation is either explicit whole-process documentation and tests or a scoped backend mechanism.
- Misconfigured fallback path: switch handling may fail when the fallback backend is invalid; severity is medium because rate-limit recovery can fail; mitigation is coverage for failed/misconfigured fallback paths.
- Dependency-cycle regression: backend hardening could introduce imports that make `backend.py` cyclic or non-stdlib; severity is medium; mitigation is keeping `backend.py` cycle-free and stdlib-only.

## Testing

Verify both subprocess sites: batch `shell.py` and streaming `launcher.py`. Cover successful switch behavior and failed/misconfigured fallback paths. Include concurrency-oriented tests that fail if one worker's auto-switch leaks into another worker unexpectedly, or, if whole-process semantics are intentionally preserved, tests that prove and document that behavior. Existing suites covering `plan_tool.shell.claude_invoke`, `plan_tool.launcher.shell_invoker`, `OnRateLimitAction.SWITCH`, and backend selection should still pass.

## Acceptance criteria

- The intended `--on-rate-limit switch` contract is explicitly encoded as either whole-process switch semantics or worker/spawn-scoped backend selection.
- `--backend` / `PLAN_TOOL_BACKEND` still select the initial backend.
- `--fallback-backend` / `PLAN_TOOL_FALLBACK_BACKEND` only affects switch policy.
- `plan_tool.shell.claude_invoke` handles `OnRateLimitAction.SWITCH` according to the encoded contract.
- `plan_tool.launcher.shell_invoker` handles `OnRateLimitAction.SWITCH` according to the encoded contract.
- Successful fallback switching is covered by tests.
- Failed or misconfigured fallback switching is covered by tests.
- Parallel worker behavior is covered by concurrency-oriented tests that either catch unexpected switch leakage or prove intentional whole-process behavior.
- Operator docs/help make the chosen switch contract visible.
- The final implementation step updates `BUG_BACKLOG.md` by removing the RISK if the behavior is documented/pinned or fixed, or replacing it with a narrower follow-up if residual design risk remains.
