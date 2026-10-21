> **Auto-archived**: this plan was swept on 2026-07-07 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 5 — Warn on prompt budget in `audit_plan_until_stable` before the conceptual-audit passes

## Summary

Wire the step-1 prompt-budget leaf into the plan-audit path so an operator sees a headroom warning before the conceptual audit spends any Claude. The audit sends its prompt once per pass through `plan_tool/review.py:check_plan_audit`, but every pass re-audits the *same* plan (only the bounded carried-findings block grows), so the key design decision is to warn and record **once per audit run** in `audit_plan_until_stable` — before the pass loop — instead of once per pass, which would nag with near-identical warnings. Add a small block-breakdown helper beside `render_plan_audit_prompt` so the advisory can show per-block sizes single-sourced with what that renderer actually sends. On green, a large plan body + detail bundle warns on stderr once, telemetry carries one `prompt-budget` event tagged `plan-audit`, and the advisory never changes the unioned findings list or the exit code. Edits land only in `plan_tool/review.py` and `tests/test_review.py`.

## Table of Contents

- [Why](#why) — the gap this closes on the conceptual-audit path.
- [Files (creates vs edits)](#files-creates-vs-edits) — the two files this step edits.
- [Implementation](#implementation) — where the hook fires, the block helper, the once-per-run rule, and the constraints.
- [Tests](#tests) — the unit cases and the green-before-done gate.
- [Acceptance criteria](#acceptance-criteria) — checkable behaviors on green.
- [References](#references) — the token-counting and context-window docs that ground the heuristic.
- [Deferred](#deferred) — per-model window, per-pass re-measurement, and the accepted per-pass backstop nag (#99).

## Why

The conceptual plan audit is the biggest single Claude cost the tool spends up front — `audit_plan_until_stable` runs `check_plan_audit` up to `AUDIT_DEFAULT_MAX_PASSES` times, each pass embedding the whole plan body plus the per-step detail bundle (`_format_audit_detail_bundle`, capped at `_AUDIT_DETAIL_FILE_BYTES = 4096` per detail file) and a carried-findings block. A big plan with a full detail bundle can build a prompt that overflows the context window, and today the tool only learns that **after** a pass fails (`plan_tool/claude_errors.py:ClaudeFailureKind.CONTEXT_OVERFLOW`), after the pass is already burned. The prompt bytes are already logged on this path (`audit_plan_until_stable` binds `run_logger.bind_shell_sink(phase="plan_audit", ...)`), but nothing compares them to a budget before sending. Step 1 landed the shared measuring stick (`plan_tool/prompt_budget.py`) and step 2 landed the recorder (`plan_tool/telemetry.py:record_prompt_budget`); this step is the third wiring step — it feeds the audit prompt into that stick and surfaces the result once per run.

## Files (creates vs edits)

- **New files:** none.

- **Existing files (edits only):**
  - `plan_tool/review.py`:
    - Add module-top imports: `maybe_warn_prompt_budget` from `plan_tool.prompt_budget` (step 1) and `record_prompt_budget` from `plan_tool.telemetry` (step 2), placed beside the existing `from plan_tool.style import tool` import. Import at module top (not body-local) so tests can monkeypatch `plan_tool.review.<name>`.
    - Add a small module helper (name it something like `_plan_audit_budget_blocks`) beside `render_plan_audit_prompt` that returns the named `(block_name, bytes)` breakdown, single-sourced with the formatters `render_plan_audit_prompt` substitutes.
    - In `audit_plan_until_stable`, add the warn-and-record hook once, before the `while passes < cap:` loop.
  - `tests/test_review.py` — add the unit tests below (spy on the leaf/recorder by monkeypatching the module-level names on `plan_tool.review`).

## Implementation

**Fire the advisory once per audit run in `plan_tool/review.py:audit_plan_until_stable`, before the pass loop.** The main alternative — putting the hook at the real send inside `check_plan_audit`'s `for attempt in (1, 2):` retry loop — is rejected: `check_plan_audit` runs once per pass, so it would warn up to `max_passes` times for a prompt that barely changes between passes (only the bounded carried-findings block grows). One warning per audit run is the right dose.

- **Gate the hook on a real send happening.** Fire only when both hold:
  - `invoker is not None` — when it's `None`, `check_plan_audit` returns `[]` without sending, so there is nothing to warn about.
  - the base audit prompt is not `None` — call `render_plan_audit_prompt(plan, plan_path, repo_root=repo_root)` (empty `carried_findings`); it returns `None` when the plan has no body, and a `None` prompt means no send. This matches the resume/skip discipline from step 3 (no send → no advisory).

- **Measure the fully-rendered base prompt, not the block sum.** Set `total_bytes = len(prompt.encode("utf-8"))` from the base prompt `render_plan_audit_prompt` returns. The per-block breakdown is display-only and legitimately omits template scaffolding and the carried-findings block — it need not sum to `total_bytes`. Judge the headroom verdict against the true measured whole.

- **Compute the breakdown with a helper single-sourced against the renderer.** Add `_plan_audit_budget_blocks(plan, plan_path, *, repo_root)` beside `render_plan_audit_prompt`. It returns a list of `(name, byte_len)` pairs for the audit prompt's major blocks, calling the **same** formatters the renderer substitutes so the breakdown tracks what actually ships:
  - `plan body` — `_collect_plan_body(plan_path)`
  - `detail bundle` — `_format_audit_detail_bundle(plan, plan_path, repo_root, max_file_bytes=_AUDIT_DETAIL_FILE_BYTES)`
  - `detail-bundle status` — `_format_detail_bundle_status_block(audit_detail_bundle_status(plan, plan_path, repo_root))`
  - Skip the carried-findings block: it is empty at the base measurement and bounded by `_CARRIED_BLOCK_MAX_FINDINGS` / `_CARRIED_BODY_EXCERPT_CHARS` when it isn't.

- **Call the leaf, then record primitives.** Pass `total_bytes` and the block list into `maybe_warn_prompt_budget` (step 1) — it stays silent at `ok` and emits a color-gated advisory to stderr only at `warn`/`high`, and returns the `PromptBudget`. Then project that budget to plain values and call `record_prompt_budget` (step 2) once, with:
  - `repo_root` (the function already takes it), `plan_slug=slug_from_filename(plan_path)` (already imported), `phase="plan-audit"`,
  - `total_bytes`, `advisory=<budget.level>`, and the optional tuning primitives (`estimated_tokens`, `context_window`, `headroom_ratio`) plus the block list as `[[name, n], ...]`.
  Do the domain-object→primitives projection at this call site — `record_prompt_budget` takes only ints/strings/lists and never imports the `PromptBudget` type (step 2's leaf rule).

- **Constraints and gotchas that are not free to vary:**
  - **Do not confuse `budget_report` with the prompt budget.** `audit_plan_until_stable` already has a `budget_report: Optional[dict]` param — that is the audit-pass *coverage* budget (BACKLOG #60c: `budget_limited` / `passes_used` / `cap`), unrelated to prompt-token budget. Name the new local `prompt_budget` (or similar) and do not touch `budget_report`.
  - **Fire exactly once.** The hook goes before the `while passes < cap:` loop, so it runs once regardless of how many passes execute. Do not place it inside the loop.
  - **Advisory-only.** The hook must not change `audit_plan_until_stable`'s return value (the unioned `list[Recommendation]`) or its exit path — same best-effort discipline as telemetry (`record_prompt_budget` already swallows all errors; `maybe_warn_prompt_budget` must not raise into this loop).
  - **Module-top imports stay cycle-free.** `plan_tool.prompt_budget` imports only stdlib + `plan_tool.style`, and `plan_tool.telemetry` imports nothing first-party, so neither creates a cycle with `review.py`. Import at module top (not body-local) so the test spy target `plan_tool.review.maybe_warn_prompt_budget` / `plan_tool.review.record_prompt_budget` is reachable.
  - **Base-prompt approximation is accepted.** Measuring the empty-carried base prompt slightly under-counts later passes that accumulate carried findings, but that block is bounded and step 1's estimate rounds tokens up, so the advisory still errs toward firing. Per-pass re-measurement is deferred (see Deferred).

## Tests

Add to `tests/test_review.py` (spy by monkeypatching the module-level names on `plan_tool.review`; drive `audit_plan_until_stable` directly with a fake invoker that returns a well-formed two-section audit response so passes run). All new tests must be green before this step is done.

- `test_audit_budget_warns_once_before_passes` — a large plan body/detail bundle drives `maybe_warn_prompt_budget` to emit a `warn`/`high` advisory; assert it appears on stderr exactly once.
- `test_audit_budget_records_one_prompt_budget_event` — spy on `plan_tool.review.record_prompt_budget`; assert called once with `phase="plan-audit"`, `total_bytes > 0`, an `advisory` level, and `plan_slug == slug_from_filename(plan_path)`.
- `test_audit_budget_fires_once_per_run_not_per_pass` — with `max_passes=3` and an invoker returning new findings each pass, assert the `maybe_warn_prompt_budget` / `record_prompt_budget` spies are each called exactly once (not three times).
- `test_audit_budget_skipped_when_no_invoker` — `invoker=None` → neither spy is called.
- `test_audit_budget_skipped_when_no_body` — a plan whose `render_plan_audit_prompt` returns `None` (no body) → neither spy is called.
- `test_audit_budget_does_not_change_return` — the unioned findings list and the function's completion are identical with the advisory firing vs. stubbed to a no-op.
- `test_audit_budget_silent_at_ok_level` — a small prompt emits nothing on stderr (leaf stays silent at `ok`) while telemetry still records.
- `test_plan_audit_budget_blocks_names_major_blocks` — `_plan_audit_budget_blocks` returns entries for `plan body`, `detail bundle`, and `detail-bundle status`; assert the block sum may be less than the full rendered prompt's byte count (breakdown need not sum to total).
- Existing `TestCheckPlanAudit` and the `audit_plan_until_stable` union/dry-round tests stay green — the advisory changes no existing behavior.

## Acceptance criteria

- `plan_tool/review.py` imports `maybe_warn_prompt_budget` (from `plan_tool.prompt_budget`) and `record_prompt_budget` (from `plan_tool.telemetry`) at module top.
- `audit_plan_until_stable` calls `maybe_warn_prompt_budget` and `record_prompt_budget` exactly once per run, before the `while passes < cap:` loop, and only when `invoker is not None` and the base rendered prompt is not `None`.
- With `max_passes=3` and a productive invoker, `record_prompt_budget` is called once, not three times.
- With `invoker=None`, or a plan with no body, neither the warn nor the record fires.
- `_plan_audit_budget_blocks` returns a non-empty list naming `plan body`, `detail bundle`, and `detail-bundle status`, computed via the same formatters `render_plan_audit_prompt` uses.
- The recorded event carries `phase="plan-audit"` and `plan_slug=slug_from_filename(plan_path)`.
- The advisory never changes `audit_plan_until_stable`'s returned findings list or its exit code; `budget_report` behavior is unchanged.
- The full suite (`uv run pytest tests/ -q`) is green.

## References

- [Anthropic — Token counting](https://docs.anthropic.com/en/docs/build-with-claude/token-counting) — how Claude counts prompt tokens; grounds the byte/token heuristic the advisory reuses from step 1.
- [Anthropic — Models overview (context windows)](https://docs.anthropic.com/en/docs/about-claude/models/overview) — per-model context-window sizes behind the default window and headroom thresholds.
- [Python — io.IOBase.isatty / sys streams](https://docs.python.org/3/library/io.html#io.IOBase.isatty) — TTY detection behind the color-gated advisory, so the stderr warning prints plain on a pipe.

## Deferred

- **Per-model context-window resolution** — this step lets the leaf fall back to step 1's `DEFAULT_CONTEXT_WINDOW`; passing an actual per-model window from `plan_tool/model_specs.py:ModelSpec.context_window` is left to the model-specs-aware wiring step.
- **Per-pass re-measurement of the growing carried-findings block** — the base (empty-carried) prompt is the representative measurement; re-measuring each pass is deferred to avoid advisory fatigue and is not worth the bounded delta.
- **Per-pass backstop nag on the audit loop — accepted residual (BACKLOG #99).** This step fires its named-block advisory **once per audit run** (before the pass loop). But each of the up-to-`AUDIT_DEFAULT_MAX_PASSES` passes sends through `check_plan_audit → shell_review_invoker → shell.claude_invoke`, so step 7's total-bytes backstop fires **once per pass** — N advisory lines + N blockless `shell-backstop` telemetry records per audit run, re-introducing exactly the per-pass nag this step's once-per-run design avoids for its own advisory. This plan **accepts** that; note that a naive per-invoke suppression mark could **not** fix it anyway — the audit sends N times, so one mark set before the loop would only cover pass 1. A correct fix needs per-pass scoping and is filed as **BACKLOG #99**, not attempted here.
- **Any change to `check_plan_audit`'s retry loop or the `budget_report` audit-pass coverage budget** — both stay untouched here.
- **Outcome-linkage to real `CONTEXT_OVERFLOW` failures** — BACKLOG #72's later phase, unchanged by this step.
