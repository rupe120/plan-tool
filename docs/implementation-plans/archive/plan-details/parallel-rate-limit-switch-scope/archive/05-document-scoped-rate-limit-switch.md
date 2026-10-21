> **Auto-archived**: this plan was swept on 2026-07-08 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 5 — Document Scoped Rate-Limit Switch Behavior

## Summary

This step updates operator and maintainer docs after steps 2 and 3 have implemented scoped backend switch behavior. The primary files are `README.md`, `RUNBOOK.md`, `CLAUDE.md`, and `docs/design-plans/BACKEND_SELECTION.md`. The main design decision is to document the observable behavior those dependencies must make true: `--on-rate-limit switch` and interactive backend switching retry the current invoke on the fallback backend, then restore the original active backend for later work. On green, readers can tell that rate-limit switching is a retry-local recovery action, not a persistent backend selection change.

## Table of Contents

- [Summary](#summary) — The short version of the docs update and expected result.
- [Why](#why) — The ambiguity this step removes from backend docs.
- [Input](#input) — The upstream scoped-switch contracts this docs step depends on.
- [Files creates vs edits](#files-creates-vs-edits) — The docs this step changes and what belongs in each.
- [Implementation](#implementation) — The intended wording, anchors, and constraints for the docs.
- [Tests](#tests) — The doc checks and link checks that cover this step.
- [Verification (non-code step)](#verification-non-code-step) — Manual verification for this docs-only step.
- [Acceptance criteria](#acceptance-criteria) — Observable checks for completion.
- [References](#references) — Primary references for scoped state, parallel execution, and rate limits.
- [Deferred](#deferred) — Related behavior and docs intentionally left out.

## Why

The current backend docs explain how to select a backend and how `--on-rate-limit switch` chooses a fallback, but they do not clearly say what happens after the retry. This docs step depends on steps 2 and 3 first making fallback selections during `plan_tool/shell.py:claude_invoke` and `plan_tool/launcher.py:shell_invoker` scoped to one invoke, without changing the backend seen by sibling parallel work or later calls. Operators need that guarantee documented before they use fallback switching during parallel detail, completeness apply, or run workflows.

## Input

- **Step 2 required outcome:** batch rate-limit fallback switches in `plan_tool/shell.py:claude_invoke` must be scoped to the current invoke and restored afterward before this docs step lands.
- **Step 3 required outcome:** streaming rate-limit fallback switches in `plan_tool/launcher.py:shell_invoker` must be scoped to the current invoke and restored afterward before this docs step lands.
- **Existing public knobs:** `plan_tool/cli/parser.py` exposes `--on-rate-limit` and `--fallback-backend`; `plan_tool/cli/app.py` resolves `PLAN_TOOL_ON_RATE_LIMIT` and `PLAN_TOOL_FALLBACK_BACKEND`.
- **Existing policy symbols:** `plan_tool/claude_errors.py:OnRateLimitAction`, `plan_tool/claude_errors.py:OnRateLimitPolicy`, and `plan_tool/claude_errors.py:RATE_LIMIT_PROMPT_LOCK` remain implementation details unless a maintainer doc needs a precise anchor.

## Files (creates vs edits)

- **New files:** none.

- **Existing files (edits only):**
  - `README.md` — Update `## Backends`, especially `### Rate-limit recovery`, to state that fallback switching is scoped to the current backend call and does not persist as the active backend after the retry completes.
  - `RUNBOOK.md` — Update `### backend rate-limit choice` under Recovery and the `## Backends` quick-reference section with the same operator-facing scoped-switch rule.
  - `CLAUDE.md` — Refresh the `Backend abstraction (backend.py)` guidance so future agents preserve the scoped switch contract when editing backend, shell, launcher, or parallel apply code.
  - `docs/design-plans/BACKEND_SELECTION.md` — Update `### 5. Failover on quota limit (shared helper + both retry loops)` so the design note matches the scoped lifetime now required by this plan.

## Implementation

- **Foundational logic:** retry-local rate-limit backend switch documentation.

- **Document the observable rule, not the helper internals.** The docs should say that `wait`, `stop`, and `ask` keep their existing meanings, while `switch` uses the configured fallback backend only for the current retrying invoke. After that invoke finishes, fails, or falls back to waiting, the original active backend remains the backend for later commands and sibling work.

- **Keep backend selection separate from fallback switching.** In `README.md:### Selecting a backend`, keep `--backend` and `PLAN_TOOL_BACKEND` as the persistent selection controls. In `README.md:### Rate-limit recovery`, describe `--on-rate-limit switch --fallback-backend ...` as recovery behavior, not as a second way to set the process active backend.

- **Use the existing operator locations.** In `RUNBOOK.md:### backend rate-limit choice`, add the practical recovery rule near the policy precedence and interactive `ask` text. In `RUNBOOK.md:## Backends`, add a short pointer that rate-limit fallback is scoped and link back to the recovery subsection if the wording would otherwise duplicate too much.

- **Keep `CLAUDE.md` concise.** In `CLAUDE.md:Backend abstraction (backend.py)`, add one maintainer-facing sentence that backend fallback during rate-limit recovery must stay scoped to `plan_tool/shell.py:claude_invoke` or `plan_tool/launcher.py:shell_invoker`, and must not leave `plan_tool/backend.py:get_active_backend` changed for unrelated work.

- **Repair the design-plan wording.** In `docs/design-plans/BACKEND_SELECTION.md:### 5. Failover on quota limit (shared helper + both retry loops)`, make the lifetime explicit: a fallback backend scope must cover the retry loop that later calls `get_active_backend`, and must close before the invoke returns. Avoid line-number references to `shell.py` or `launcher.py`; use symbolic anchors like `plan_tool/shell.py:claude_invoke` and `plan_tool/launcher.py:shell_invoker`.

- **Preserve command semantics.** Do not document `--fallback-backend` as changing `--backend`, `PLAN_TOOL_BACKEND`, or the global default. Do not imply that interactive `ask` stores the chosen backend for later invocations.

- **Call out parallel behavior plainly.** State that scoped switching is safe for overlapping batch and streaming calls because a fallback chosen by one rate-limited invoke is not visible to sibling invokes except inside that invoke's retry.

- **Do not add new behavior.** This step is docs-only. If the docs cannot be made true because a dependency did not land the scoped behavior, stop and route that back to steps 2, 3, or 4 instead of changing production code here.

## Tests

- Documentation wording check — Confirm `README.md`, `RUNBOOK.md`, `CLAUDE.md`, and `docs/design-plans/BACKEND_SELECTION.md` describe fallback switching as current-invoke scoped recovery.
- Documentation accuracy check — Confirm no edited doc claims `--fallback-backend` changes `--backend`, `PLAN_TOOL_BACKEND`, or the default backend for later work.
- Documentation link check — Assert links added between `README.md` and `RUNBOOK.md` point to existing anchors.

### Verification (non-code step)

- Read `README.md:### Rate-limit recovery` and confirm `switch` is described as current-invoke scoped recovery.
- Read `RUNBOOK.md:### backend rate-limit choice` and confirm the operator recipe says later work keeps the original active backend.
- Read `CLAUDE.md:Backend abstraction (backend.py)` and confirm the maintainer guidance warns against process-wide backend mutation during rate-limit recovery.
- Read `docs/design-plans/BACKEND_SELECTION.md:### 5. Failover on quota limit (shared helper + both retry loops)` and confirm the scoped lifetime covers the retry loop, not only the selection helper.
- Run a markdown anchor check or targeted grep for the new cross-links so no stale anchor is introduced.

## Acceptance criteria

- `README.md:### Rate-limit recovery` states that `--on-rate-limit switch` uses the fallback backend only for the current retrying invoke and does not persistently change the active backend.
- `RUNBOOK.md:### backend rate-limit choice` gives the same scoped-switch operator guidance for both policy `switch` and interactive `ask`.
- `RUNBOOK.md:## Backends` points readers to the rate-limit recovery section without duplicating conflicting policy text.
- `CLAUDE.md:Backend abstraction (backend.py)` tells maintainers to preserve scoped fallback behavior in `plan_tool/shell.py:claude_invoke` and `plan_tool/launcher.py:shell_invoker`.
- `docs/design-plans/BACKEND_SELECTION.md:### 5. Failover on quota limit (shared helper + both retry loops)` no longer implies a process-wide backend switch for rate-limit recovery.
- No edited doc claims `--fallback-backend` changes `--backend`, `PLAN_TOOL_BACKEND`, or the default backend for later work.

## References

- [Python contextvars — Context Variables](https://docs.python.org/3/library/contextvars.html) — Use for the scoped-state model behind retry-local backend selection.
- [Python concurrent.futures — ThreadPoolExecutor](https://docs.python.org/3/library/concurrent.futures.html#threadpoolexecutor) — Use for the parallel-worker behavior that the docs must not contradict.
- [Claude Platform Docs — Rate limits](https://platform.claude.com/docs/en/api/rate-limits) — Use for the external rate-limit behavior that motivates wait, stop, and switch recovery.

## Deferred

- Production scoped-switch fixes — Owned by steps 2 and 3; this step only documents their resulting behavior.
- Parallel leakage test implementation — Owned by step 4; this step may cite the guarantee but should not add or change test code.
- New per-aspect backend selection or automatic failover policy — Outside this plan step unless the plan frontmatter is expanded.
- CLI reference regeneration under `docs/cli/` — Not in this step's file list; only update if a separate docs or generated-reference step adds it.
