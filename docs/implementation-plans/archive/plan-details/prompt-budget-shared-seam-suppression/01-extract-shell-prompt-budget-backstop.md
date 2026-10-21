> **Auto-archived**: this plan was swept on 2026-07-08 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 1 — Extract the shell prompt-budget backstop helper

## Summary

Extract the prompt-budget backstop logic in `plan_tool/shell.py:claude_invoke` into a private helper owned by the shell module. Keep the current observable behavior unchanged: the backstop still measures with `backend.batch_transport(prompt).prompt_bytes`, warns once before the retry loop, records telemetry only when `get_active_spawn_cwd()` is set, and never changes the `(rc, stdout)` result. The main design choice is to make `claude_invoke` call one small helper before any subprocess attempt, rather than keeping warning and telemetry code inline in the retry-heavy function. Green means the existing backstop tests in `tests/test_shell.py` still pass unchanged, with any helper-level tests added only to make the extraction easier to maintain.

## Table of Contents

- [Summary](#summary) — The short version of the refactor and expected result.
- [Why](#why) — Why the shell backstop needs a named helper now.
- [Input](#input) — Existing contracts the helper reads and must preserve.
- [Files creates vs edits](#files-creates-vs-edits) — The exact file footprint for this step.
- [Implementation](#implementation) — The intended helper boundary, preserved behavior, and gotchas.
- [Tests](#tests) — The characterization and helper tests that cover the refactor.
- [Acceptance criteria](#acceptance-criteria) — Observable checks for reviewers and CI.
- [References](#references) — Primary docs relevant to this small refactor.
- [Deferred](#deferred) — Work that belongs to later suppression or caller-wiring steps.

## Why

`plan_tool/shell.py:claude_invoke` already owns the generic batch Claude call path and already has inline prompt-budget backstop behavior. That behavior is partly implemented in HEAD, so this step should not add a new warning policy; it should make the existing policy a named helper that future suppression work can call, skip, or wrap without editing the retry and subprocess control flow. The value is a clearer boundary: `claude_invoke` keeps process execution and failure recovery, while the helper owns the best-effort budget warning and telemetry side effect.

## Input

- `plan_tool/backend.py` (`PromptTransport.prompt_bytes`) — The helper must use the transport byte count from `backend.batch_transport(prompt)`, not `len(prompt.encode("utf-8"))`, because stdin-carried backends measure the sent payload differently from argv-carried backends.
- `plan_tool/backend.py:get_active_spawn_cwd` — Telemetry may be written only when this returns a scoped repo root. Do not fall back to `Path.cwd()`.
- `plan_tool/prompt_budget.py:maybe_warn_prompt_budget` — The helper passes total bytes, `context_window=None`, empty blocks, `_BACKSTOP_SURFACE`, and `_BACKSTOP_REMEDIES`.
- `plan_tool/telemetry.py:record_prompt_budget` — The helper projects the returned budget into primitive recorder fields and uses `phase="shell-backstop"` plus an empty `plan_slug`.
- `plan_tool/shell.py:claude_invoke` — The helper must preserve the current call ordering: skip entirely when the executable is missing, run once before the retry loop when the executable is present, and avoid adding any `ClaudeCallEnd` sink event.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/shell.py` — Extract the inline backstop block from `claude_invoke` into a private helper, likely near `_BACKSTOP_SURFACE` / `_BACKSTOP_REMEDIES` or near `_run_once`, and leave `claude_invoke` with a single best-effort helper call.
  - `tests/test_shell.py` — Keep the current backstop characterization coverage, and add or adjust focused tests only as needed to pin the helper boundary without changing the existing behavior assertions.

## Implementation

- **Foundational logic:** one best-effort shell prompt-budget backstop helper.
- **Extract the existing behavior, do not redesign it.** Move the inline `try:` block in `plan_tool/shell.py:claude_invoke` that calls `maybe_warn_prompt_budget` and `record_prompt_budget` into a private helper, for example `_maybe_warn_shell_prompt_budget(prompt, backend)`. The exact name is flexible, but it should make clear that this is the generic shell backstop, not the named-block detail/create/review budget checks.
- **Keep `claude_invoke` as the execution owner.** `claude_invoke` should still resolve `backend = get_active_backend()`, run the `shutil.which(backend.binary)` guard, and return `EXEC_NOT_FOUND_EXIT, ""` before any backstop work when the binary is missing. After that guard, it should call the helper once before `resolve_on_rate_limit_policy(...)` and before the retry loop.
- **Pass the active backend into the helper.** The helper should reuse the backend object already resolved by `claude_invoke` so it does not select a different backend if state changes between checks. This also keeps the helper easy to test with the existing fake backend pattern in `tests/test_shell.py:test_backstop_reuses_backend_prompt_bytes`.
- **Use the backend transport byte count.** Inside the helper, compute `total_bytes` with `backend.batch_transport(prompt).prompt_bytes`. Preserve the current behavior pinned by `tests/test_shell.py:test_backstop_reuses_backend_prompt_bytes`; stdin-carried transports must be measured by their stdin payload, not by argv length.
- **Preserve best-effort semantics.** The helper should swallow all exceptions from measuring, warning, or recording. A failure in `maybe_warn_prompt_budget`, `record_prompt_budget`, `get_active_spawn_cwd`, or `backend.batch_transport` must not change the return value from `claude_invoke`.
- **Preserve telemetry scoping.** The helper should call `record_prompt_budget` only when `get_active_spawn_cwd()` returns a path. Keep `plan_slug=""`, `phase="shell-backstop"`, `blocks=()` omitted or empty as currently done, and pass the advisory fields from the returned budget.
- **Preserve warning shape.** Keep `_BACKSTOP_SURFACE` and `_BACKSTOP_REMEDIES` as the source of the shell warning label and remedy text. The shell helper has no plan, step, or per-block context, so it should continue to pass `blocks=()` and should not invent named blocks.
- **Do not add suppression in this step.** The plan title points toward shared suppression, but this step is a refactor. Do not add `note_prompt_budget_advised`, a `ContextVar` suppression flag, or caller updates in `plan_tool/create.py`, `plan_tool/detail.py`, `plan_tool/review.py`, `plan_tool/jira.py`, `plan_tool/lessons.py`, or `plan_tool/annotate.py`.
- **Keep the batch/run split unchanged.** This helper belongs only to `plan_tool/shell.py:claude_invoke`, the batch path used by wrappers like `plan_tool/create.py:shell_claude_invoker`, `plan_tool/detail.py:shell_detail_invoker`, `plan_tool/review.py:shell_review_invoker`, `plan_tool/jira.py:shell_jira_invoker`, `plan_tool/lessons.py:shell_equivalence_invoker`, and `plan_tool/annotate.py:shell_annotate_invoker`. It must not touch `plan_tool/launcher.py:run_step` or `plan_tool/launcher.py:shell_invoker`, which are the streaming run path.

## Tests

- `tests/test_shell.py:test_backstop_checks_budget_on_real_send` — The backstop calls `maybe_warn_prompt_budget` once on a present binary with the canonical backend prompt byte count, empty blocks, and a non-empty surface.
- `tests/test_shell.py:test_backstop_records_telemetry_on_real_send` — A scoped spawn cwd records one telemetry event with `phase="shell-backstop"`, empty `plan_slug`, and the advisory level returned by the budget helper.
- `tests/test_shell.py:test_backstop_skips_telemetry_without_spawn_cwd` — The advisory still runs without a scoped repo root, but telemetry is not written.
- `tests/test_shell.py:test_backstop_reuses_backend_prompt_bytes` — A stdin-carried backend measures the stdin payload via `PromptTransport.prompt_bytes`.
- `tests/test_shell.py:test_backstop_fires_once_per_call_not_per_retry` — A retrying call evaluates and records the backstop once, not once per subprocess attempt.
- `tests/test_shell.py:test_backstop_skipped_on_missing_executable` — The missing-binary path returns before warning, recording, or emitting a sink event.
- `tests/test_shell.py:test_backstop_silent_at_ok_still_records` — An `ok` budget writes no stderr warning but still records telemetry when a spawn cwd is scoped.
- `tests/test_shell.py:test_backstop_warns_on_large_prompt` — A large prompt still emits a `warning:` line through the prompt-budget advisory.
- `tests/test_shell.py:test_backstop_never_breaks_invoke` — A raising advisory or recorder still leaves `claude_invoke` returning the subprocess result.
- `tests/test_shell.py:test_backstop_does_not_touch_sink` — The helper does not create extra `ClaudeCallEnd` events.

### Test-creation order (refactor step)

Write or confirm the characterization tests first, before extracting the helper. Start with the current `tests/test_shell.py` backstop group because it pins the behavior visible through `claude_invoke`, then add a helper-focused test only if the extraction creates a meaningful private boundary that is hard to cover through `claude_invoke`. After the extraction, the same characterization tests must stay green, unmodified.

## Acceptance criteria

- `plan_tool/shell.py:claude_invoke` contains a single call to the extracted shell backstop helper after the `shutil.which(backend.binary)` guard and before the retry loop.
- The extracted helper uses `backend.batch_transport(prompt).prompt_bytes` for `total_bytes`.
- A missing executable returns `(EXEC_NOT_FOUND_EXIT, "")` without calling `maybe_warn_prompt_budget`, `record_prompt_budget`, or the active sink.
- A transient retry still produces one shell backstop warning/record attempt for the overall `claude_invoke` call.
- The helper records telemetry only when `get_active_spawn_cwd()` returns a path, with `phase="shell-backstop"` and `plan_slug=""`.
- `pytest tests/test_shell.py` passes.

## References

- [contextlib — Utilities for with-statement contexts](https://docs.python.org/3/library/contextlib.html) — Useful if tests need a small local context helper while keeping cleanup reliable.
- [subprocess — Subprocess management](https://docs.python.org/3/library/subprocess.html) — Background for preserving the subprocess result contract while moving non-subprocess advisory code aside.
- [unittest.mock — mock object library](https://docs.python.org/3/library/unittest.mock.html) — Covers spies and side effects for warning and recorder assertions.
- [pytest monkeypatch](https://docs.pytest.org/en/stable/how-to/monkeypatch.html) — The existing shell tests use monkeypatch to isolate `shutil.which`, `subprocess.run`, budget warnings, and telemetry recording.
- [pytest stdout/stderr capture](https://docs.pytest.org/en/stable/how-to/capture-stdout-stderr.html) — Relevant for preserving the large-prompt warning and silent-ok stderr behavior.

## Deferred

- Shell suppression flag — Add the one-shot “already advised” suppression mechanism in a later step, where caller updates can be made in the same plan-owned scope.
- Caller wiring outside `plan_tool/shell.py` — Do not edit `plan_tool/create.py`, `plan_tool/detail.py`, `plan_tool/review.py`, `plan_tool/jira.py`, `plan_tool/lessons.py`, or `plan_tool/annotate.py` in this refactor.
- Streaming run path — Leave `plan_tool/launcher.py:run_step` and `plan_tool/launcher.py:shell_invoker` unchanged; they do not go through `claude_invoke`.
- Backstop warning content changes — Keep `_BACKSTOP_SURFACE`, `_BACKSTOP_REMEDIES`, empty blocks, and `context_window=None` unchanged unless a later behavior step chooses a new operator-facing policy.
