> **Auto-archived**: this plan was swept on 2026-07-07 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 3 — Warn on prompt budget in `generate_detail` and print the breakdown on `detail --dry-run`

## Summary

Wire the step-1 prompt-budget leaf into the detail authoring path. After `plan_tool/detail.py:render_detail_prompt` assembles a step's prompt and just before the invoker fires, estimate the prompt against a context-window budget, emit the advisory only when headroom is tight, and record one telemetry event. The key design decision: put the warn-and-record hook inside `plan_tool/detail.py:_author_step_detail` (the one place a real invoke happens) so it fires once per authored step, skips steps that resume from a checkpoint (no send → no advisory), and covers both the serial loop and the concurrent (`jobs > 1`) path with one edit. Separately, `detail --dry-run` prints the full per-block breakdown to stderr for every step it would author — at all levels, not just `warn`/`high` — so an operator can inspect headroom before spending a call. On green, a large detail prompt warns on stderr, telemetry carries a `prompt-budget` event, dry-run always prints a breakdown, and the advisory never changes rc or blocks the write. Edits land only in `plan_tool/detail.py` and `tests/test_detail.py`.

## Table of Contents

- [Why](#why) — the gap this closes in the detail path.
- [Files (creates vs edits)](#files-creates-vs-edits) — the two files this step edits.
- [Implementation](#implementation) — where the hook fires, the named-block breakdown, the dry-run print, and the constraints.
- [Tests](#tests) — the unit cases and the green-before-done gate.
- [Acceptance criteria](#acceptance-criteria) — checkable behaviors on green.
- [References](#references) — the token-counting docs that ground the heuristic.
- [Deferred](#deferred) — accepted shared-seam double-fire (#99), per-model window, and the render-block single-sourcing left to other steps.

## Why

Detail authoring assembles a prompt that embeds each declared file (capped at `_MAX_PROMPT_FILE_BYTES = 4096` per file), the plan references, accumulated lessons, sibling detail bodies, and — on a merge re-author — the folded members' **uncapped** `prior_body`. A step with many declared files or a large merge re-author can build a prompt that overflows the context window, and today the tool only learns that **after** the call fails (`plan_tool/claude_errors.py:ClaudeFailureKind.CONTEXT_OVERFLOW`), after the call is already burned. `prompt_bytes` is already measured on this path (`_author_step_detail` logs `prompt_bytes=len(attempt_prompt.encode("utf-8"))` into the run log via `run_logger.claude_call_start`) but nothing compares it to a budget before sending. Step 1 landed the shared measuring stick (`plan_tool/prompt_budget.py`) and step 2 landed the recorder (`plan_tool/telemetry.py:record_prompt_budget`); this step is the first wiring step — it feeds the detail prompt into that stick and surfaces the result.

## Files (creates vs edits)

- **New files:** none.

- **Existing files (edits only):**
  - `plan_tool/detail.py`:
    - Add module-level imports of the step-1 leaf functions (`estimate_prompt_budget`, `maybe_warn_prompt_budget`) and step-2's `record_prompt_budget`, placed at the top beside the existing `plan_tool.launcher` import (whose comment already explains module-level-so-tests-can-monkeypatch).
    - Add a small module helper that measures the named detail blocks (see Implementation), single-sourced so both render sites and the dry-run branch use it.
    - In `_author_step_detail`, add the warn-and-record hook in the real-invoke branch, before the retry loop.
    - In `generate_detail`, thread the block byte map to `_author_step_detail` from the serial render site and print the breakdown in the `dry_run` branch.
    - In `_generate_detail_concurrent`, add a `budget_blocks` field to the frozen `_DispatchItem` (the worker `_run_worker` only sees that carrier, so it cannot recompute the blocks), fill it at the serial pre-dispatch render site where each prompt is rendered, and pass `d.budget_blocks` into the worker's `_author_step_detail` call so the concurrent path warns too.
  - `tests/test_detail.py` — add the unit tests below (spy on the leaf/recorder functions; use `NullReporter`, fake invokers, and `extract_lessons=False` per this file's convention).

## Implementation

**Fire the advisory once per real invoke, from inside `_author_step_detail`.** That function is the single seam where a detail prompt is actually sent — it is called by both the serial loop (the `outcome = _author_step_detail(...)` call in `generate_detail`) and the concurrent worker (the `_author_step_detail(...)` call in `_generate_detail_concurrent`'s `_run_worker`). Placing the hook there covers both paths in one edit and — because the resumed-from-checkpoint case takes the `if cached is not None:` branch (which skips the invoke and falls through to the shared parse/write path) while the real invoke lives in the paired `else:` — it never warns on a step that will resume. That matters: a warning for a prompt that is never sent is a false positive, and the plan lists advisory fatigue as a named risk.

- **Put the hook in the invoke branch, before the retry loop.** In `_author_step_detail`, the real-invoke path is the `else:` branch that increments `invoke_idx` and enters `for attempt in range(1, _MAX_INVOKE_ATTEMPTS + 1)`. Emit the advisory once, right before that loop — not per attempt (the retry appends `_REPROMPT_SUFFIX` but the size delta is negligible, and one advisory per step is the intent). Use `total_bytes = len(prompt.encode("utf-8"))`, matching the byte count the run log already records at the `claude_call_start` call.

- **Pass the named-block breakdown in as a new keyword arg.** `_author_step_detail` has `prompt`, `step`, and `repo_root` but not `plan` / `sibling_details` / `prior_body`, so it can't rebuild the block sizes on its own. Add a keyword arg (one way: `budget_blocks: Sequence[tuple[str, int]] = ()`) that each render site fills. Default it to empty so any other caller keeps working and the estimate degrades to total-bytes-only.

- **Single-source the block measurement in a module helper.** Add a helper (e.g. `_detail_budget_blocks(...)`) that returns `list[tuple[str, int]]` of `(block-name, bytes)` for the content-bearing blocks `render_detail_prompt` substitutes: the embedded file contents (`_format_files_contents_block`), sibling details (`_format_sibling_details_block`), the merge `prior_body` (`_format_prior_body_block`), the plan references block, the lessons block (`render_lessons_block(load_lessons(...))`), and the already-implemented block (`_format_already_implemented_block`). Call the exact same formatters `render_detail_prompt` uses so the numbers track the prompt. Call the helper at both render sites (the serial `render_detail_prompt(...)` call and the concurrent pre-dispatch render). At the serial site pass its result straight into `_author_step_detail`; on the concurrent path stash it on the new `_DispatchItem.budget_blocks` field so the frozen carrier delivers it to the worker (which passes it into `_author_step_detail`).
  - The breakdown is for **display**, not accounting — it does not need to sum to `total_bytes` (template scaffolding and small blocks are omitted on purpose). `total_bytes` is always measured from the fully rendered `prompt`, so the headroom verdict is judged against the real assembled prompt, not the sum of blocks.

- **Emit and record on the real path.** After building the `PromptBudget`, call step 1's `maybe_warn_prompt_budget(...)` (it emits to stderr only at `warn`/`high`, is `color_enabled`-gated, and returns the budget). Then record the decision with step-2's `record_prompt_budget(repo_root, plan_slug=plan_slug, phase="detail", total_bytes=..., advisory=<budget.level>, ...)`, projecting the budget to primitives at the call site (the recorder takes plain ints/strings, never the `PromptBudget` type). `_author_step_detail` already receives `repo_root` and `plan_slug`, so both are in hand. Both calls are best-effort and must not change the return value or raise into the authoring flow.

- **Resolve `context_window` as `None` (default window).** The detail invoker shells out to a backend CLI; resolving that backend's real window is out of scope (see Deferred). Pass `context_window=None` and let the leaf fall back to its `DEFAULT_CONTEXT_WINDOW`. This matches the plan's deferral of per-model window resolution.

- **Print the breakdown on `dry_run`, unconditionally.** In `generate_detail`, the `if dry_run:` branch renders the prompt and appends a `DetailResult(..., prompt=prompt)` without invoking. There, build the same `budget_blocks` and call `estimate_prompt_budget(...)` directly (not `maybe_warn_prompt_budget`, which stays silent at `ok`), then print the breakdown to **stderr** for every step. Stderr keeps it separate from the prompt itself, which `cmd_detail` prints to stdout — so a piped `detail --dry-run` still yields a clean prompt while the operator sees the breakdown on the terminal. Dry-run is inspection only: it **records no `prompt-budget` telemetry** (nothing is sent) — explicit parity with step 6's `run --dry-run`, so no non-send events pollute the #72 distribution.

- **Surface-relevant remedies are the leaf's job.** The advisory body lists runnable structural remedies for the calling surface (for detail: author one step with `--step N`, `plan-tool split`, `scope-out`). If `maybe_warn_prompt_budget` accepts a surface/remedy hint, pass the detail-relevant one; if the remedy text is owned entirely inside step 1's leaf, pass nothing extra. Treat the exact signature as step 1's contract — reference it, don't restate it.

Constraints and gotchas that are **not** free to vary:

- **The advisory must never block or change rc.** The invoke, the write, the `DetailResult`, and the function's return list must be identical whether the level is `ok`, `warn`, or `high`. The hook only reads bytes and emits.
- **Never let the advisory raise into authoring.** `maybe_warn_prompt_budget` and `record_prompt_budget` are best-effort by contract, but the block-measurement helper you add must also not throw — a formatter slip must not sink a detail run. Guard it the way the foundational-logic sweep is guarded (`except Exception` → skip and continue), or keep it to pure byte-length reads that cannot fail.
- **One advisory per invoked step.** Fire before the attempt loop, not inside it; skip resumed steps and dry-run's non-invoke.
- **Concurrent (`jobs > 1`) emission can interleave — accepted as cosmetic.** On the concurrent path the advisory fires from inside `_author_step_detail` (per worker) and emits its multi-line breakdown straight to stderr via `style.warn`, bypassing the reporter, so two workers warning at once can interleave their lines. This plan accepts that as a known cosmetic residual (the advisory is best-effort and never load-bearing); routing it through the reporter for atomic emission is a later refinement, not scoped here.
- **Keep the leaf functions module-level names in `detail.py`.** Import them at module top (not lazily) so tests can monkeypatch `plan_tool.detail.maybe_warn_prompt_budget` / `estimate_prompt_budget` / `record_prompt_budget`, mirroring how `apply_finding` is imported for the same reason. `plan_tool.telemetry` is a stdlib-only leaf and `plan_tool.prompt_budget` a near-leaf, so neither top-level import creates a cycle with `detail.py`.

## Tests

All in `tests/test_detail.py`. Spy on the leaf/recorder by monkeypatching the module-level names on `plan_tool.detail`; drive `generate_detail` with a fake `invoker`, `NullReporter`, and `extract_lessons=False`. Use `_write_detail_plan(tmp_path)` (or a plan with enough embedded file bytes to make the breakdown non-trivial).

- `test_generate_detail_warns_before_invoke` — on the real path, `maybe_warn_prompt_budget` is called once for the invoked step with `total_bytes == len(prompt.encode("utf-8"))` and a non-empty blocks list; the fake invoker still fires and the detail file is still written.
- `test_generate_detail_records_prompt_budget` — `record_prompt_budget` is called once per invoked step with `phase="detail"`, the plan slug, the total bytes, and `advisory` equal to the returned budget's level.
- `test_advisory_does_not_change_result` — with the warn spy forced to report level `high`, `generate_detail` still returns a `written=True` `DetailResult` and the invoker was called (advisory never blocks or flips rc).
- `test_dry_run_prints_breakdown_and_does_not_invoke` — `dry_run=True` prints a breakdown to stderr (capture with `capsys`) for the step, the fake invoker is never called, and the result carries `prompt`.
- `test_dry_run_does_not_record_telemetry` — `record_prompt_budget` spy is not called under `dry_run=True` (inspection only).
- `test_resumed_step_does_not_warn_or_record` — with a valid checkpoint seeded (reuse `_fresh_now()` / `save_checkpoint`), the step resumes and neither `maybe_warn_prompt_budget` nor `record_prompt_budget` is called (no invoke → no advisory).
- `test_budget_blocks_include_file_contents` — the blocks passed to the estimate include the embedded-file-contents block with `bytes > 0`, so the breakdown shows the dominant detail section.
- `test_concurrent_path_warns_before_invoke` — with `jobs=2` and two fresh steps, the warn hook fires for each invoked step (both paths reach `_author_step_detail`). Mark `@pytest.mark.integration` if it must drive the concurrent dispatch end-to-end.

**Green-before-done gate (feature step):** every test above is authored with the implementation and must pass before this step is done. Existing `TestRenderDetailPrompt` and the `_author_step_detail` / `generate_detail` tests must stay green unchanged — the advisory is additive and must not perturb the prompt, the write, or the result rows.

## Acceptance criteria

- On the real authoring path, `generate_detail` calls the step-1 advisory once per invoked step with `total_bytes` equal to the rendered prompt's UTF-8 byte length and a non-empty per-block breakdown, then records one `prompt-budget` telemetry event with `phase="detail"`.
- A step that resumes from a valid checkpoint triggers no advisory and no telemetry event.
- `detail --dry-run` prints the budget breakdown to stderr for each step it would author, at every level (including `ok`), without invoking and without recording telemetry.
- The advisory never changes the return value or rc and never blocks the invoke: with the level forced to `high`, the detail file is still written and the `DetailResult` is unchanged.
- The block measurement never raises into the authoring flow (a formatter error skips the breakdown, not the run).
- The concurrent (`jobs > 1`) path emits the same advisory before each fresh invoke.
- All new `tests/test_detail.py` cases pass; the existing detail tests remain green.

## References

- [Anthropic — Token counting](https://docs.anthropic.com/en/docs/build-with-claude/token-counting) — how Claude counts prompt tokens, grounding the byte/token estimate the advisory compares against the window.
- [Anthropic — Models overview (context windows)](https://docs.anthropic.com/en/docs/about-claude/models/overview) — per-model context-window sizes behind the ~200K-class default window this step relies on (via `context_window=None`).
- [Python — io.IOBase.isatty / sys streams](https://docs.python.org/3/library/io.html#io.IOBase.isatty) — TTY detection behind the `color_enabled` gating, the reason the advisory prints plain on a pipe and the dry-run breakdown goes to stderr.

## Deferred

- **Double-warn / double-telemetry on the shared seam** — this named-block send funnels through `shell.claude_invoke`, so step 7's total-bytes backstop also fires on it (one extra advisory line + a blockless `shell-backstop` telemetry record per send). This plan **accepts** that double-fire; suppressing it is a separate item, **BACKLOG #99**. This step just emits its named-block advisory and does not attempt to mark or suppress the backstop.
- **Per-model context-window resolution** — this step passes `context_window=None` and uses the leaf's default window; resolving the backend's real window from `plan_tool/model_specs.py` is deferred (plan-level Deferred).
- **Single-sourcing the block sizes from `render_detail_prompt`** — the block helper re-calls the same formatters `render_detail_prompt` uses, a small duplication. Having `render_detail_prompt` return its substitution block sizes so the caller reuses them (instead of recomputing) is a behavior-preserving refactor `detail` cannot mint; route it to reconcile rather than folding a restructure into this feature step.
- **Warning on the detail-quality audit prompt** (`render_detail_quality_prompt`) — a **separate assembly point, deliberately not hooked in this step**. It sends through `shell_review_invoker → shell.claude_invoke`, so it receives only the step-7 total-bytes backstop (no per-block breakdown). Adding a named-block hook there is out of scope; wire it only if a later step or reconcile calls for it.
- **`record_prompt_budget` on dry-run** — deliberately omitted; dry-run sends nothing, so recording it would pollute the pre-send distribution the telemetry is meant to capture.
