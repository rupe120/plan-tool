> **Auto-archived**: this plan was swept on 2026-07-07 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 6 — Warn on prompt budget in `run_step`, reusing `_streaming_prompt_bytes` for the total

## Summary

Wire the step-1 prompt-budget leaf into the `run` execution path. In `plan_tool/launcher.py:run_step`, after the prompt is fully assembled (including the appended test-order directive) and just before `invoker(prompt)` fires, estimate the prompt against a context-window budget, emit the advisory only when headroom is tight, and record one telemetry event tagged `run-step`. The key design decision: measure the total with the path's existing `plan_tool/launcher.py:_streaming_prompt_bytes(prompt)` — the same byte count the run log already logs at `claude_call_start` — rather than a fresh `len(prompt.encode("utf-8"))`, so the advisory and the run log agree on one number. As a secondary deliverable, the `dry_run` branch (which renders without sending) prints the per-block breakdown to stderr so an operator can inspect headroom before spending a call. On green, a large `run`/`check`/`security`/`reconcile` prompt warns on stderr, telemetry carries one `prompt-budget` event per real invoke, dry-run prints a breakdown and records nothing, and the advisory never changes the `RunResult`, the exit code, or whether the plan advances. Edits land only in `plan_tool/launcher.py` and `tests/test_launcher.py`.

## Table of Contents

- [Why](#why) — the gap this closes on the run path.
- [Files (creates vs edits)](#files-creates-vs-edits) — the two files this step edits.
- [Implementation](#implementation) — where the hook fires, the total-bytes reuse, the block breakdown, the dry-run print, and the constraints.
- [Tests](#tests) — the unit cases and the green-before-done gate.
- [Acceptance criteria](#acceptance-criteria) — checkable behaviors on green.
- [References](#references) — the token-counting and context-window docs that ground the heuristic.
- [Deferred](#deferred) — the generic backstop, per-mode phase, per-model window, and the uncapped detail embed left to other steps.

## Why

`run_step` sends the largest per-step prompt the tool assembles: the run prompt embeds the step's **entire detail file, uncapped** (`plan_tool/renderer.py:_load_detail` fills the `step_detail` template variable with the full file body — no per-file cap like the detail/audit paths use), plus the lessons section and the file list. A step with a big detail file can build a prompt that overflows the context window, and today the tool only learns that **after** the call fails — `plan_tool/claude_errors.py:ClaudeFailureKind.CONTEXT_OVERFLOW` is classified on a burned call. The bytes are already measured on this path: `run_step` calls `_streaming_prompt_bytes(prompt)` for the `run_logger.claude_call_start` event, but that is accounting, not a safeguard — nothing compares it to a budget before sending. Step 1 landed the shared measuring stick (`plan_tool/prompt_budget.py`) and step 2 landed the recorder (`plan_tool/telemetry.py:record_prompt_budget`); this step is the run-path wiring — it feeds the assembled run prompt into that stick and surfaces the result.

## Files (creates vs edits)

- **New files:** none.

- **Existing files (edits only):**
  - `plan_tool/launcher.py`:
    - Add module-top imports of the step-1 leaf functions (`estimate_prompt_budget`, `maybe_warn_prompt_budget` from `plan_tool.prompt_budget`) and step-2's `record_prompt_budget` (from `plan_tool.telemetry`). Import at module top (not lazily) so tests monkeypatch `plan_tool.launcher.<name>`.
    - Add `slug_from_filename` from `plan_tool.locator` (launcher does not import it today) to derive the telemetry `plan_slug` from `plan_path`.
    - Add a small module helper (one way: `_run_budget_blocks(plan, step, repo_root)`) that returns the named `(block_name, bytes)` breakdown for the run prompt, single-sourced against the loaders `render_prompt` actually substitutes.
    - In `run_step`, print the breakdown in the `if dry_run:` branch (to stderr), and add the warn-and-record hook on the real-invoke path, before the `invoker(prompt)` call.
  - `tests/test_launcher.py` — add the unit tests below (spy on the leaf/recorder by monkeypatching the module-level names on `plan_tool.launcher`).

## Implementation

**Fire the advisory once per real invoke, from inside `run_step`, before `invoker(prompt)`.** `run_step` has a single send seam (the `exit_code, stdout = invoker(prompt)` call in its `claude_call` phase), and the `dry_run` path returns earlier without sending. Placing the hook on the real-invoke path — after the `dry_run` early return and before the invoke — fires it exactly once per sent step and never for a dry run.

- **Reuse `_streaming_prompt_bytes(prompt)` for the total** — this is the step's headline. The run log already computes `_streaming_prompt_bytes(prompt)` for its `claude_call_start` event; use that same value as `total_bytes` for the budget check so the advisory and the run log never disagree. Do **not** switch to `len(prompt.encode("utf-8"))` here — the point of this step is that the streaming-transport byte count is the run path's canonical measure.
  - **Measure after the test-order directive is appended.** The `prompt += _test_order_directive(step.change_type)` append happens before both the `dry_run` check and the invoke, so `_streaming_prompt_bytes(prompt)` at the hook already includes it — matching what `claude_call_start` logs. Keep that ordering.
  - **One way to single-source the count:** compute `total_bytes = _streaming_prompt_bytes(prompt)` once above the `claude_call` phase and reuse it both for the advisory and for the existing `prompt_bytes=` argument to `claude_call_start` (which today recomputes it). That is optional cleanup — the required behavior is only that the advisory's total equals `_streaming_prompt_bytes(prompt)`.

- **Fire for every mode that actually sends.** `run_step` runs `run`, `check`, `security`, and `reconcile` modes — all invoke a prompt. Put the hook on the shared real-invoke path so it is mode-agnostic; do not gate it on `mode in MUTATING_MODES`. The advisory is about prompt size, which matters for review-style modes too. Note `reconcile` here is a **mode-family shorthand** (matching `launcher.py`'s own `(check/security/reconcile)` comment), not a literal template name — the run path has no `reconcile.md`, only `run-reconcile.md` / `detail-reconcile.md` / `reconcile-deep.md`. Keep concrete tests to real template mode names (the roster uses `mode="security"`); a literal `mode="reconcile"` would raise `FileNotFoundError`.

- **Do not gate the advisory on `run_logger`.** The existing `_streaming_prompt_bytes` call sits inside `if run_logger is not None:`. The advisory must fire even when no run logger is bound, so compute its `total_bytes` on the unconditional path, not inside that branch.

- **Build the named-block breakdown from the run prompt's real sources.** Add a helper (one way: `_run_budget_blocks(plan, step, repo_root) -> list[tuple[str, int]]`) that returns `(block-name, bytes)` for the content-bearing blocks the run template substitutes:
  - `("step detail", …)` — the byte length of `plan_tool/renderer.py:_load_detail(step, repo_root=repo_root)` output (the dominant, uncapped block).
  - `("lessons", …)` — the byte length of `plan_tool/renderer.py:_load_lessons_section(plan, repo_root=repo_root)` output.
  - Call the **same** loaders `render_prompt` uses (via `_build_variables`) so the numbers track the actual prompt. Those two loaders are module-private in `plan_tool/renderer.py`; import them into `launcher.py` (which already imports `render_prompt` from that module), or add a thin public accessor if you prefer not to reach for underscored names.
  - The breakdown is for **display**, not accounting — it does **not** need to sum to `total_bytes`. `total_bytes` is always the fully-rendered prompt's `_streaming_prompt_bytes`, so the headroom verdict is judged against the real assembled prompt, never the block sum.

- **Emit and record on the real path.** Call `maybe_warn_prompt_budget(total_bytes, context_window=None, blocks=blocks, ...)` (it emits to stderr only at `warn`/`high`, is `color_enabled`-gated by step 1, and returns the `PromptBudget`). Then record with `record_prompt_budget(repo_root, plan_slug=<slug>, phase="run-step", total_bytes=budget.total_bytes, advisory=budget.level, estimated_tokens=budget.estimated_tokens, context_window=budget.context_window, headroom_ratio=budget.headroom_ratio, blocks=budget.blocks)`, projecting the `PromptBudget` to primitives at the call site (the recorder takes plain ints/strings/lists, never the `PromptBudget` type — treat its signature as step 2's contract). Derive `plan_slug` with `slug_from_filename(plan_path)` (default args return the stem, never `None`).

- **Use `phase="run-step"`.** That is the literal step 2 already names for this surface. All run modes share it; the mode (`run`/`check`/`security`/`reconcile`) is not separately recorded (see Deferred).

- **Resolve `context_window` as `None` (default window).** The run invoker shells out to a backend CLI; resolving that backend's real window is out of scope (plan-level Deferred). Pass `context_window=None` and let the leaf fall back to its `DEFAULT_CONTEXT_WINDOW`.

- **Print the breakdown on `dry_run`, to stderr.** The `if dry_run:` branch renders the prompt, `print(prompt)`s it, and returns without invoking. `print(prompt)` goes to **stdout** (a piped `run --dry-run` yields a clean prompt), so build the same `blocks`, call `estimate_prompt_budget(total_bytes, context_window=None, blocks=blocks)` directly (not `maybe_warn_prompt_budget`, which stays silent at `ok`), and print the breakdown to **stderr** for every step at all levels. Dry-run is inspection only: do **not** call `record_prompt_budget` here (nothing is sent). This mirrors step 3's detail-side dry-run treatment.

- **Never let the advisory raise into a run.** `maybe_warn_prompt_budget` and `record_prompt_budget` are best-effort by contract, but the block helper you add must also not throw — a loader slip must not sink a run. Wrap the block measurement in `except Exception` → return `[]` and continue, or keep it to pure byte-length reads that cannot fail. The advisory reads bytes and emits; it never blocks.

- **The advisory must never change behavior.** The invoke, the exit-code coercion (`is_error` synthesis), the `phase_end` events, whether the plan advances, and the returned `RunResult` must be identical whether the level is `ok`, `warn`, or `high`.

## Tests

Add to `tests/test_launcher.py` (extend `TestRunStep` or add a `TestRunStepPromptBudget` class; spy by monkeypatching `plan_tool.launcher.maybe_warn_prompt_budget` / `estimate_prompt_budget` / `record_prompt_budget`). A step with a detail file on disk (write one and point the plan's `detail:` at it) is needed for the block-content cases.

- `test_run_step_warns_before_invoke` — on the real path, `maybe_warn_prompt_budget` is called once with `total_bytes == _streaming_prompt_bytes(prompt)` and a non-empty blocks list; the fake invoker still fires and the plan still advances.
- `test_total_reuses_streaming_prompt_bytes` — the `total_bytes` passed to the advisory equals `_streaming_prompt_bytes(prompt)` (compute the expected value in the test from the rendered prompt), pinning the reuse the step is named for.
- `test_run_step_records_prompt_budget` — `record_prompt_budget` is called once with `phase="run-step"`, the plan slug, the total bytes, and `advisory` equal to the returned budget's level.
- `test_advisory_does_not_change_result` — with the warn spy forced to report level `high`, `run_step` still returns the same `RunResult` (advanced, done) and the invoker was called (advisory never blocks or flips rc).
- `test_review_mode_also_warns` — `mode="security"` (a non-mutating review mode) still triggers the advisory once before its invoke (the hook is mode-agnostic).
- `test_dry_run_prints_breakdown_to_stderr_and_does_not_record` — under `dry_run=True`, the prompt prints to stdout, the breakdown prints to stderr (`capsys`), `record_prompt_budget` is not called, and `maybe_warn_prompt_budget` is not called.
- `test_blocks_include_step_detail` — the blocks passed to the estimate include a `"step detail"` entry with `bytes > 0` when the step has a detail file, so the breakdown shows the dominant run block.
- `test_no_run_logger_still_warns` — with `run_logger=None`, the advisory still fires (not gated on the run logger).
- `test_block_measurement_failure_does_not_break_run` — force the block helper (or the renderer loader) to raise; `run_step` still completes, invokes, and advances (the advisory never sinks a run).

**Green-before-done gate (feature step):** every test above is authored with the implementation and must pass before this step is done. Existing `TestRunStep` and `TestRunPromptTestOrderDirective` must stay green unchanged — the advisory is additive and must not perturb the prompt, the invoke, the exit code, or plan advancement.

## Acceptance criteria

- On the real run path, `run_step` calls `maybe_warn_prompt_budget` once per invoked step with `total_bytes` equal to `_streaming_prompt_bytes(prompt)` (not a fresh `len(...encode())`), then records one `prompt-budget` telemetry event with `phase="run-step"`.
- The advisory fires for every mode that invokes (`run`, `check`, `security`, `reconcile`), not just mutating modes, and fires even when `run_logger` is `None`.
- The advisory never changes the `RunResult`, the exit code, or whether the plan advances: with the level forced to `high`, the run still advances and the `RunResult` is unchanged.
- `run --dry-run` prints the per-block breakdown to stderr (with the prompt still on stdout) and records no telemetry event.
- A block-measurement failure does not raise into `run_step`; the run completes.
- The blocks passed to the estimate include a `"step detail"` entry measured from `renderer._load_detail`, and the breakdown is not required to sum to `total_bytes`.
- Existing `plan_tool/launcher.py` run tests pass unchanged.

## References

- [Anthropic — Token counting](https://docs.anthropic.com/en/docs/build-with-claude/token-counting) — how Claude counts prompt tokens, grounding the byte/token estimate the advisory compares against the window.
- [Anthropic — Models overview (context windows)](https://docs.anthropic.com/en/docs/about-claude/models/overview) — per-model context-window sizes behind the ~200K-class default window this step relies on via `context_window=None`.
- [Python — io.IOBase.isatty / sys streams](https://docs.python.org/3/library/io.html#io.IOBase.isatty) — TTY detection behind the `color_enabled` gating and the reason the dry-run breakdown goes to stderr while the prompt goes to stdout.

## Deferred

- **Generic total-bytes backstop** — owned by step 7 at `plan_tool/shell.py:claude_invoke`. The run path uses the **streaming** invoker, not `claude_invoke`, so it never reaches that backstop; this step's named-block advisory is the only budget check on the run path, and there is no shared-seam double-fire here (that residual, filed as **BACKLOG #99**, affects only the batch senders).
- **Per-mode telemetry phase** — all run modes record `phase="run-step"`; distinguishing `run` vs `check`/`security`/`reconcile` in the recorded event is a later refinement, not needed for the advisory.
- **Per-model context-window resolution** — this step passes `context_window=None` and uses the leaf's default window; resolving the backend's real window from `plan_tool/model_specs.py` is deferred (plan-level Deferred).
- **Capping `run`'s uncapped full-detail embed** — the advisory measures and warns about the large `step_detail` block but does not cap it; if it recurs, file it to `BACKLOG.md` per the plan's Out-of-scope note (#95 follow-up).
