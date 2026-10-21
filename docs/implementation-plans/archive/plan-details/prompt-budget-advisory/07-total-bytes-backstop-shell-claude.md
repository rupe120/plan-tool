> **Auto-archived**: this plan was swept on 2026-07-07 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 7 — Add the total-bytes backstop in `shell.claude_invoke`

## Summary

Add a pre-send, total-bytes prompt-budget check inside `plan_tool/shell.py:claude_invoke` so callers that pass **no** named blocks — `jira`, `lessons`, `annotate` — still get a headroom warning before the call spends. The check reuses the step-1 leaf (`maybe_warn_prompt_budget`) and records one step-2 telemetry event tagged `phase="shell-backstop"`, `plan_slug=""`. The backstop **always fires** on the real-send path. Because `claude_invoke` is the single batch seam every backend flows through (via `get_active_backend()`), the named-block senders (`detail`/`create`/`audit`) also reach it — so a named-block send emits the backstop advisory (and a `shell-backstop` telemetry event) in addition to its own. That double-fire is an **accepted residual** of this plan; suppressing it is deferred to **BACKLOG #99** (it needs per-pass scoping for the audit loop and a per-invoke correlation id for #72 dedup — out of scope here). On green, a large no-blocks prompt warns once on stderr and records once, the backstop never changes the `(rc, stdout)` return or raises, and the missing-executable fast-path is unchanged. Edits land only in `plan_tool/shell.py` and `tests/test_shell.py`.

## Table of Contents

- [Why](#why) — the gap this closes at the generic shell seam.
- [Files (creates vs edits)](#files-creates-vs-edits) — the two files this step edits.
- [Implementation](#implementation) — the backstop placement, the canonical byte measure, and the constraints.
- [Tests](#tests) — the unit cases and the green-before-done gate.
- [Acceptance criteria](#acceptance-criteria) — checkable behaviors on green.
- [References](#references) — the token-counting and context-window docs that ground the heuristic.
- [Deferred](#deferred) — double-fire suppression (#99), caller-phase enrichment, per-model window, and the streaming run path.

## Why

`plan_tool/shell.py:claude_invoke` is the single batch seam every non-streaming Claude call funnels through: `create` (via `create.py:shell_claude_invoker`), `review`/audit (via `review.py:shell_review_invoker`), `detail` (via `detail.py:shell_detail_invoker`), `jira` (via `jira.py:shell_jira_invoker`), plus two direct callers — `plan_tool/lessons.py` (`phase="lessons_equivalence"`) and `plan_tool/annotate.py`. Steps 3–6 wire the named-block advisory into `create`, `detail`, and `audit`, but `jira`, `lessons`, and `annotate` get **no** budget check at all — they can build an overflowing prompt and only learn it after the call fails (`plan_tool/claude_errors.py:ClaudeFailureKind.CONTEXT_OVERFLOW`). This step lands the generic total-bytes backstop at that seam so every batch caller gets a pre-send headroom check. The same seam also carries the calls that *did* run a named-block check, so those emit the backstop advisory too — an accepted double-fire this plan does not suppress (deferred to **BACKLOG #99**; see Deferred).

## Files (creates vs edits)

- **New files:** none.

- **Existing files (edits only):**
  - `plan_tool/shell.py`:
    - Add module-top imports of `maybe_warn_prompt_budget` (from `plan_tool.prompt_budget`, step 1) and `record_prompt_budget` (from `plan_tool.telemetry`, step 2), beside the existing `from plan_tool.style import tool, warn` import. Both are leaves (`prompt_budget` imports only stdlib + `plan_tool.style`; `telemetry` imports nothing first-party), so neither creates an import cycle with `shell.py`.
    - In `claude_invoke`, add the backstop on the real-send path: when the executable is present, run `maybe_warn_prompt_budget` + `record_prompt_budget` once, before the retry loop.
  - `tests/test_shell.py`:
    - Extend the autouse fixture (`_clear_sink_between_tests`) to neutralize the real recorder so existing tests stay hermetic (see Tests).
    - Add the backstop unit cases below.

## Implementation

**What changes: `claude_invoke` runs one pre-send total-bytes budget check on every real send.**

- **Place the backstop on the real-send path in `claude_invoke`, before the retry loop.** The ordering that must hold:
  1. **Keep the missing-executable fast-path unchanged.** When the binary isn't on PATH, return `(EXEC_NOT_FOUND_EXIT, "")` as today — do **not** warn or record, since nothing is sent (preserves `test_invoke_returns_127_when_claude_not_on_path` and `test_invoke_does_not_emit_on_missing_executable`).
  2. **Run the backstop only when the binary is present**, once, before the `while True:` loop. It fires per `claude_invoke` call, not per retry.

- **Measure the total with the path's canonical batch measure — not a fresh `len(prompt.encode())`.** Use `backend.batch_transport(prompt).prompt_bytes` (`plan_tool/backend.py:PromptTransport.prompt_bytes`). That is the exact value `_run_once` returns and `_emit_call_end` logs as `prompt_bytes`, so the advisory and the run-log agree on one number. For argv-carried backends (`claude`) it equals `len(prompt.encode("utf-8"))`; for a stdin-carried backend it measures the stdin payload — the correct total in both cases. Reuse the `backend` object already fetched at the top of `claude_invoke` rather than re-calling `get_active_backend()`.

- **Emit the advisory through the step-1 leaf.** Call `maybe_warn_prompt_budget(total_bytes, context_window=None, blocks=(), surface=<label>, remedies=<generic>)`:
  - `context_window=None` → the leaf falls back to `DEFAULT_CONTEXT_WINDOW`. The shell seam has no per-model window; passing `None` is deliberate (see Deferred).
  - `blocks=()` — the backstop is **total-bytes only**; it has no structured per-block breakdown (that is what the named-block wiring steps provide).
  - `surface` — a short label identifying the backstop (one way: `"claude prompt (backstop)"`).
  - `remedies` — a couple of generic runnable hints (e.g. narrow scope with a smaller `--step`, or split a large seed/plan), kept short.
  - The leaf stays silent at `ok`, warns at `warn`/`high`, is `color_enabled`-gated, and never raises. It returns the `PromptBudget` so the recorder can read the verdict.

- **Record one telemetry event from the returned budget.** Call `record_prompt_budget(repo_root, plan_slug="", phase="shell-backstop", total_bytes=total_bytes, advisory=budget.level, estimated_tokens=budget.estimated_tokens, context_window=budget.context_window, headroom_ratio=budget.headroom_ratio)`:
  - `repo_root` = `get_active_spawn_cwd() or Path.cwd()` — the tree the backend is spawned against.
  - `plan_slug=""` — the shell seam has no resolved plan; step 2 documents `""` as the backstop's slug.
  - `phase="shell-backstop"` — the fixed phase step 2 names for this seam, so backstop records are distinguishable from named-block records in the distribution.
  - Record at **every level** (including `ok`), matching the wiring steps' every-send recording; the recorder is a dumb passthrough that does not filter.

- **The whole backstop must be best-effort.** An advisory must never break the call it observes (same discipline as `_emit_call_end`'s swallow and `telemetry.py`'s guard). `maybe_warn_prompt_budget` never raises and `record_prompt_budget` swallows all errors, but wrap the backstop block in a defensive `try/except` that swallows and warns, so even an unexpected failure (e.g. from `batch_transport`) can't perturb the `(rc, stdout)` result.

- **Accepted double-fire with the named-block senders.** The same `maybe_warn_prompt_budget` + `record_prompt_budget` pair runs at the named-block sites in `plan_tool/detail.py:_author_step_detail` (step 3), `plan_tool/create.py`'s three `propose_*` senders (step 4), and `plan_tool/review.py:audit_plan_until_stable` (step 5). Those calls funnel through `claude_invoke`, so they also hit this backstop — one extra advisory line and one blockless `shell-backstop` telemetry record per named-block send. This plan **accepts** that; a correct suppressor is non-trivial (the audit loop sends N times per run, so a single per-invoke mark can't cover it, and #72 needs a per-invoke correlation id to dedupe the two records) and is filed as **BACKLOG #99**. The run path (`plan_tool/launcher.py:run_step`, step 6) uses the **streaming** invoker, not `claude_invoke`, so it never reaches this backstop.

## Tests

All cases live in `tests/test_shell.py`, using the existing `_fake_run_factory` and `monkeypatch` of `shell.shutil.which` / `shell.subprocess.run`. This is a **feature** step: write these unit tests alongside the implementation, and every one must be green before the step is done.

Fixture changes (in the autouse `_clear_sink_between_tests`, so every test stays hermetic):

- Neutralize `shell.record_prompt_budget` to a no-op (or a captured list) by default, so existing shell tests that run `claude_invoke` with the binary present don't write telemetry into the repo's `.plan-tool/telemetry/`. Backstop-recording tests install their own spy, which wins over the fixture default.

Backstop cases:

- `test_backstop_checks_budget_on_real_send` — with the binary present, `claude_invoke` calls a spied `shell.maybe_warn_prompt_budget` once, with `total_bytes` equal to `backend.batch_transport(prompt).prompt_bytes` and a non-empty `surface`.
- `test_backstop_records_telemetry_on_real_send` — a spied `shell.record_prompt_budget` is called once with `plan_slug=""`, `phase="shell-backstop"`, and `advisory` equal to the returned budget level.
- `test_backstop_reuses_backend_prompt_bytes` — with a stdin-carried transport backend, the `total_bytes` passed to the check equals `PromptTransport.prompt_bytes` (the stdin payload), not the argv-derived length.
- `test_backstop_fires_once_per_call_not_per_retry` — with a transient failure forcing a retry, the `maybe_warn` / `record` spies are each called once, not once per attempt.
- `test_backstop_skipped_on_missing_executable` — with `which` returning `None`, the return is `(EXEC_NOT_FOUND_EXIT, "")`, the `maybe_warn` and `record` spies are not called, and no `ClaudeCallEnd` is emitted (unchanged fast-path).
- `test_backstop_silent_at_ok_still_records` — a small prompt (level `ok`) writes nothing to stderr but still records one event with `advisory="ok"`.
- `test_backstop_warns_on_large_prompt` — a genuinely large prompt (enough to cross the `warn` headroom threshold against `DEFAULT_CONTEXT_WINDOW`) writes a `warning:` line to stderr.
- `test_backstop_never_breaks_invoke` — with `shell.maybe_warn_prompt_budget` monkeypatched to raise, `claude_invoke` still returns the normal `(0, stdout)` (best-effort swallow).
- `test_backstop_does_not_touch_sink` — with a sink installed, exactly one `ClaudeCallEnd` is recorded (the send); the backstop adds no sink event.

Green-before-done gate: `uv run pytest tests/test_shell.py -q` passes, and the full suite (`uv run pytest tests/ -q`) stays green.

## Acceptance criteria

- With the binary present, `claude_invoke` calls `maybe_warn_prompt_budget` once with `total_bytes == backend.batch_transport(prompt).prompt_bytes` and records one `record_prompt_budget` event with `plan_slug=""` and `phase="shell-backstop"`, before the retry loop.
- The backstop fires once per `claude_invoke` call, not once per retry attempt.
- On a missing executable, `claude_invoke` still returns `(127, "")`, emits no `ClaudeCallEnd`, and runs no backstop warn/record.
- The backstop never changes the `(rc, stdout)` return and never raises — a raising `maybe_warn_prompt_budget` still yields a normal invoke result.
- The advisory is `color_enabled`-gated (plain on a non-TTY) and silent at `ok`; a large no-blocks prompt writes a `warning:` line to stderr.
- `plan_tool/shell.py` imports `maybe_warn_prompt_budget` and `record_prompt_budget` at module top with no import cycle.
- `uv run pytest tests/test_shell.py -q` passes and the full suite stays green.

## References

- [Anthropic — Token counting](https://docs.anthropic.com/en/docs/build-with-claude/token-counting) — how Claude counts prompt tokens; grounds the byte→token heuristic the backstop reuses from step 1.
- [Anthropic — Models overview (context windows)](https://docs.anthropic.com/en/docs/about-claude/models/overview) — per-model window sizes, the basis for the `DEFAULT_CONTEXT_WINDOW` the backstop falls back to when it passes `context_window=None`.

## Deferred

- **Double-warn / double-telemetry suppression on the shared seam** — a named-block send also hits this backstop, emitting one extra advisory line and one blockless `shell-backstop` telemetry record. Suppressing it correctly needs per-pass scoping for the audit loop (which sends N times per run) plus a per-invoke correlation id so #72 can dedupe the backstop record against its named-phase record — real design filed as **BACKLOG #99**. This plan accepts the double-fire.
- **Enriching the recorded `phase` with the caller's identity** — the backstop records the fixed `phase="shell-backstop"`; folding in `claude_invoke`'s `phase` argument (e.g. `"lessons_equivalence"`) for finer telemetry is a later refinement.
- **Per-model context window at the shell seam** — the backstop passes `context_window=None` and uses the default window; resolving a real per-backend window is plan-level Deferred.
- **A per-block breakdown at the backstop** — total-bytes only by design; structured blocks come only from the named-block wiring steps.
- **Covering the streaming run path** — `plan_tool/launcher.py:run_step` uses the streaming invoker, not `claude_invoke`, so it is outside this backstop; step 6 already covers it with its own named-block check.
