> **Auto-archived**: this plan was swept on 2026-07-08 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

---
title: Parallel Rate Limit Switch Scope
status: completed
priority: medium
enforce_step_tests: true
steps:
- id: 1
  title: Characterize active backend global selection behavior
  files:
  - plan_tool/backend.py
  - tests/test_backend.py
  complexity: low
  change_type: refactor
  gate:
  - python -c "import ast,pathlib,sys; allowed={'plan_tool.backend_config'}; tree=ast.parse(pathlib.Path('plan_tool/backend.py').read_text());
    mods=[]; [mods.append(n.module or '') for n in ast.walk(tree) if isinstance(n,
    ast.ImportFrom)]; [mods.extend(a.name for a in n.names) for n in ast.walk(tree)
    if isinstance(n, ast.Import)]; bad=[m for m in mods if m and m.split('.')[0] not
    in ({'__future__'} | set(sys.stdlib_module_names)) and m not in allowed]; assert
    not bad, bad"
  - pytest tests/test_backend.py -q
  detail: docs/implementation-plans/plan-details/parallel-rate-limit-switch-scope/01-characterize-active-backend-global.md
  status: done
- id: 2
  title: Add scoped active backend helper APIs
  files:
  - plan_tool/backend.py
  - tests/test_backend.py
  complexity: medium
  change_type: feature
  gate:
  - python -c "import ast,pathlib,sys; allowed={'plan_tool.backend_config'}; tree=ast.parse(pathlib.Path('plan_tool/backend.py').read_text());
    mods=[]; [mods.append(n.module or '') for n in ast.walk(tree) if isinstance(n,
    ast.ImportFrom)]; [mods.extend(a.name for a in n.names) for n in ast.walk(tree)
    if isinstance(n, ast.Import)]; bad=[m for m in mods if m and m.split('.')[0] not
    in ({'__future__'} | set(sys.stdlib_module_names)) and m not in allowed]; assert
    not bad, bad"
  - pytest tests/test_backend.py -q
  depends_on:
  - 1
  detail: docs/implementation-plans/plan-details/parallel-rate-limit-switch-scope/02-scoped-active-backend-helper-apis.md
  status: done
- id: 3
  title: Scope batch rate-limit backend switches to the current invoke
  files:
  - plan_tool/shell.py
  - tests/test_shell.py
  complexity: medium
  change_type: feature
  gate:
  - pytest tests/test_shell.py -q -k 'rate_limit and switch'
  depends_on:
  - 2
  detail: docs/implementation-plans/plan-details/parallel-rate-limit-switch-scope/03-scope-batch-rate-limit-backend-switches.md
  status: done
- id: 4
  title: Scope streaming rate-limit backend switches to the current invoke
  files:
  - plan_tool/launcher.py
  - tests/test_launcher.py
  complexity: medium
  change_type: feature
  gate:
  - pytest tests/test_launcher.py -q -k 'rate_limit and switch'
  depends_on:
  - 2
  detail: docs/implementation-plans/plan-details/parallel-rate-limit-switch-scope/04-scope-streaming-rate-limit-backend.md
  status: done
- id: 5
  title: Add parallel apply backend leakage coverage
  files:
  - tests/cli/test_completeness_apply_parallel.py
  complexity: medium
  change_type: feature
  gate:
  - pytest tests/cli/test_completeness_apply_parallel.py -q
  depends_on:
  - 3
  - 4
  detail: docs/implementation-plans/plan-details/parallel-rate-limit-switch-scope/05-parallel-apply-backend-leakage-coverage.md
  status: done
- id: 6
  title: Document scoped rate-limit switch behavior
  files:
  - README.md
  - RUNBOOK.md
  - CLAUDE.md
  - docs/design-plans/BACKEND_SELECTION.md
  - docs/cli/README.md
  - docs/cli/completeness-apply.md
  - tests/cli/test_package_surface.py
  - tests/cli/test_cli_reference.py
  - tests/cli/package_surface_help.golden.txt
  - plan_tool/cli/parser.py
  complexity: low
  change_type: feature
  gate:
  - python -c "from pathlib import Path; checks={'README.md':['--on-rate-limit switch','restore
    the backend'],'RUNBOOK.md':['--on-rate-limit switch','restores the backend'],'CLAUDE.md':['Rate-limit
    fallback is scoped'],'docs/design-plans/BACKEND_SELECTION.md':['retry the current
    limited call','restore the previously','active backend after'],'tests/cli/package_surface_help.golden.txt':['retries
    the current call with --fallback-backend']}; missing=[(p,s) for p,needles in checks.items()
    for s in needles if s not in Path(p).read_text(encoding='utf-8')]; assert not
    missing, missing"
  - pytest tests/cli/test_package_surface.py -q
  - pytest tests/cli/test_cli_reference.py -q
  depends_on:
  - 3
  - 4
  - 5
  detail: docs/implementation-plans/plan-details/parallel-rate-limit-switch-scope/06-document-scoped-rate-limit-switch.md
  status: done
- id: 7
  title: Remove the resolved rate-limit switch risk
  files:
  - BUG_BACKLOG.md
  - BACKLOG.md
  complexity: low
  change_type: non-code
  gate:
  - python -c 'from pathlib import Path; text="\n".join(Path(p).read_text(encoding="utf-8")
    for p in ["BUG_BACKLOG.md","BACKLOG.md"]); needles=["process-wide backend for
    all parallel workers","cross-worker backend leakage","Auto-`SWITCH` flips"]; found=[n
    for n in needles if n in text]; assert not found, found'
  depends_on:
  - 6
  detail: docs/implementation-plans/plan-details/parallel-rate-limit-switch-scope/07-remove-resolved-rate-limit-switch-risk.md
  status: done
---
# Parallel Rate Limit Switch Scope

## Overview

Harden `--on-rate-limit switch` behavior when multiple workers share one Python process, especially `completeness-apply --jobs N`. The plan makes the backend-switching contract explicit, then either documents and tests whole-process switch semantics or implements worker/spawn-scoped backend selection while preserving existing single-threaded behavior. The work preserves CLI precedence for `--backend`, `PLAN_TOOL_BACKEND`, `--fallback-backend`, and `PLAN_TOOL_FALLBACK_BACKEND`, covers both subprocess sites in `shell.py` and `launcher.py`, and ends by reconciling the `BUG_BACKLOG.md` RISK entry.

## Problem statement

Today `plan_tool.backend.get_active_backend` / `set_active_backend` use one process-wide active backend. `plan_tool.shell.claude_invoke` and `plan_tool.launcher.shell_invoker` handle `OnRateLimitAction.SWITCH` by calling `select_active_backend` through local `_select_rate_limit_backend` helpers, and `RATE_LIMIT_PROMPT_LOCK` serializes switch/prompt/wait handling without making backend selection worker-local. Because parallel completeness apply uses threads in one process, one worker's auto-switch can affect another worker that has not spawned yet. The current contract is implicit, so operators and tests cannot tell whether this cross-worker backend change is intended account-wide behavior or a bug.

## Architecture

The first design choice is to encode the intended contract for `--on-rate-limit switch`: either whole-process switch semantics are intentional because rate limits are account-wide, or each worker/spawn keeps its own backend selection and switching is scoped to that worker/spawn. The plan must not leave the current behavior implicit.

If preserving whole-process semantics, the architecture is documentation and tests around the existing process-wide active backend in `plan_tool.backend.get_active_backend` / `set_active_backend`, with operator-facing docs/help that make the cross-worker behavior visible.

If changing semantics, introduce the smallest scoped backend mechanism that keeps `backend.py` cycle-free and stdlib-only, preserves existing single-threaded behavior, and lets `plan_tool.shell.claude_invoke` and `plan_tool.launcher.shell_invoker` apply `OnRateLimitAction.SWITCH` without leaking one worker/spawn's fallback selection into another. The initial backend must still come from `--backend` / `PLAN_TOOL_BACKEND`, while `--fallback-backend` / `PLAN_TOOL_FALLBACK_BACKEND` only matters for switch policy.

For scoped semantics, prefer a stdlib concurrency primitive that matches the chosen scope. `contextvars.ContextVar` supports context-local state, should be declared at module top level, and uses `set()` tokens plus `reset()` to restore previous values; `copy_context()` is O(1) and `Context.run()` contains changes inside that context. `threading.local` provides thread-specific attributes whose changes in one thread do not affect another thread, while `ThreadPoolExecutor` runs submitted callables concurrently in worker threads within the same process. Subprocess launch sites should continue to pass child environment through subprocess APIs rather than thread-unsafe child-process hooks such as `preexec_fn`.

## Input

This plan consumes the existing backend-selection API and CLI/environment contract before changing behavior. It relies on `plan_tool.backend.get_active_backend` / `set_active_backend` as the current process-wide state surface, `select_active_backend` as the switch selector, `OnRateLimitAction.SWITCH` as the rate-limit policy trigger, and the subprocess call sites `plan_tool.shell.claude_invoke` and `plan_tool.launcher.shell_invoker`.

The contract that must be preserved is that `--backend` / `PLAN_TOOL_BACKEND` select the initial backend, while `--fallback-backend` / `PLAN_TOOL_FALLBACK_BACKEND` only affects switch policy. The seed identifies the current contract as implicit, so verification is limited to existing code behavior and the tests/docs added by this plan.

## References

- [Python contextvars — Context Variables](https://docs.python.org/3/library/contextvars.html) — Covers ContextVar and Context behavior for scoped state that avoids leaking values across concurrent execution.
- [Python threading — Thread-local Data](https://docs.python.org/3/library/threading.html#thread-local-data) — Documents threading.local for per-thread state when comparing worker-local backend selection with process-wide globals.
- [Python subprocess — Popen Constructor](https://docs.python.org/3/library/subprocess.html#popen-constructor) — Defines subprocess spawning and environment handling needed to preserve backend selection at both subprocess invocation sites.
- [Python concurrent.futures — ThreadPoolExecutor](https://docs.python.org/3/library/concurrent.futures.html#threadpoolexecutor) — Documents thread pool execution semantics relevant to reproducing and testing parallel worker backend leakage.
- [pytest — How to monkeypatch/mock modules and environments](https://docs.pytest.org/en/stable/how-to/monkeypatch.html) — Covers monkeypatching attributes and environment variables for tests around backend precedence and fallback misconfiguration.
- [Claude Platform Docs — Rate limits](https://platform.claude.com/docs/en/api/rate-limits) — Explains Claude API rate-limit scope, 429 behavior, retry-after headers, and organization/workspace limits that inform switch semantics.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

- Reworking provider rate-limit policy beyond backend switching: this plan only scopes or documents how `--on-rate-limit switch` changes the selected backend.
- Changing initial backend precedence: `--backend` / `PLAN_TOOL_BACKEND` behavior stays fixed so the work remains limited to switch handling.
- Replacing subprocess invocation architecture: `shell.py` and `launcher.py` remain the integration points, with only the selected backend propagation contract under review.
- Solving unrelated parallel apply isolation concerns: concurrency coverage is limited to backend leakage caused by rate-limit switching.

## Risks

- Cross-worker backend leakage: one worker's auto-switch can affect another worker in the same process; severity is high for parallel `completeness-apply --jobs N`; mitigation is either explicit whole-process documentation and tests or a scoped backend mechanism.
- Misconfigured fallback path: switch handling may fail when the fallback backend is invalid; severity is medium because rate-limit recovery can fail; mitigation is coverage for failed/misconfigured fallback paths.
- Dependency-cycle regression: backend hardening could introduce imports that make `backend.py` cyclic or non-stdlib; severity is medium; mitigation is keeping `backend.py` cycle-free and stdlib-only.

## Testing

Verify both subprocess sites: batch `shell.py` and streaming `launcher.py`. Cover successful switch behavior and failed/misconfigured fallback paths. Include concurrency-oriented tests that fail if one worker's auto-switch leaks into another worker unexpectedly, or, if whole-process semantics are intentionally preserved, tests that prove and document that behavior. Existing suites covering `plan_tool.shell.claude_invoke`, `plan_tool.launcher.shell_invoker`, `OnRateLimitAction.SWITCH`, and backend selection should still pass.

**Per-step test strategy** (derived from each step's `change_type`):

- step 1 (refactor) — characterization tests pinned before the change; pass unchanged after.
- step 2 (feature) — unit tests added with the implementation; green before completion.
- step 3 (feature) — unit tests added with the implementation; green before completion.
- step 4 (non-code) — verification appropriate to the artifacts; no test-ordering directive.
- step 5 (non-code) — verification appropriate to the artifacts; no test-ordering directive.
- step 6 (feature) — unit tests added with the implementation; green before completion.

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

## Deferred

- Provider-specific retry tuning: postpone until the backend switch scope is explicit and tested.
- Broader parallel apply isolation: track separately because this plan only covers backend leakage caused by rate-limit switching.
