> **Auto-archived**: this plan was swept on 2026-06-01 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 5 — Route `claude_errors` / `lessons` / `shell` library diagnostics through `style.tool()`/`warn()` and pin each with a `*StyleOutput` test class

## Summary

Replace the hand-rolled `print(f"plan-tool: …" / "warning: …", file=…)` diagnostic heads in `plan_tool/claude_errors.py`, `plan_tool/lessons.py`, and `plan_tool/shell.py` with `plan_tool/style.py`'s `tool()` and `warn()` helpers, finishing the consolidation that steps 1–4 carried through `review.py`, `detail.py`, `auto_reconcile.py`, `change_collision.py`, `iteration_lock.py`, and `jira.py`. These three are the shared cross-command library layer — every subcommand reaches them — so they were the last holdouts still bypassing the centralized color/stream gate. The load-bearing constraint: plain-mode output stays **byte-identical**, so each f-string drops only its literal `plan-tool: ` / `warning: ` head and passes the remainder verbatim as the helper's `body`; `tool()` handles `plan-tool:` heads (including the one `plan-tool: warning:` line, whose `warning:` stays a body sub-tag), `warn()` handles bare `warning:` heads. On green, a new `*StyleOutput` test class per module asserts that byte-identity and prefix-only ANSI under `PLAN_TOOL_FORCE_COLOR`, with the `\r`-rewriting countdown ticker in `wait_until_epoch` left raw.

## Table of Contents

- [Why](#why) — what's inconsistent about these three modules' diagnostics today
- [Files (creates vs edits)](#files-creates-vs-edits) — six files, all edits
- [Implementation](#implementation) — per-site conversion in each module and the new test classes
- [Tests](#tests) — cases in the three `*StyleOutput` classes
- [Acceptance criteria](#acceptance-criteria) — checkable behaviors on green
- [References](#references) — color/SGR/stream docs consulted
- [Deferred](#deferred) — sites and helpers intentionally left raw

## Why

- **These three modules are the shared library layer still hand-rolling diagnostics.** After steps 1–4 routed all six subcommand-level modules through `style`, `claude_errors.py`, `lessons.py`, and `shell.py` remain on raw `print(f"plan-tool: …" / "warning: …", file=…)`. None imports `plan_tool.style`, so their lines miss the centralized `NO_COLOR` / `PLAN_TOOL_FORCE_COLOR` / TTY gate, and any future wording or color change must be made in two places.
- **They are the highest-fan-out surfaces.** `shell.claude_invoke` is called by `create`, `review`, `jira`, `detail`, and `run`; `claude_errors.wait_until_epoch` fires on every rate-limit retry; `lessons` is read/written by `review` and `detail`. A consolidated prefix here means the rate-limit countdown and the lessons-migration notice look identical regardless of which subcommand triggered them.
- **The risk is silent wording drift.** These strings are scanned by operators reading run logs during quota waits and migrations, and `tests/test_shell.py:test_invoke_returns_127_when_claude_not_on_path` already greps `"not found on PATH"` in captured stderr. A `StringIO`/capsys byte-equality test locks plain-mode output so the refactor is provably presentation-only.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/claude_errors.py` — add `from plan_tool.style import tool`; convert the three `plan-tool:` `print()` heads in `wait_until_epoch` (waiting-notice, wait-cancelled, wait-complete, wait-interrupted — four heads); leave the `\r` countdown-ticker `stream.write` raw.
  - `plan_tool/lessons.py` — add `from plan_tool.style import tool, warn`; convert the four `plan-tool:` heads in `_migrate_general_lessons_from_legacy` (two) and `_append_citation_jsonl` (one) and `find_lesson_equivalences` (one checkpoint-save), plus the one bare `warning:` head in `find_lesson_equivalences`.
  - `plan_tool/shell.py` — add `from plan_tool.style import tool, warn`; convert the five `plan-tool:` heads in `claude_invoke` and the three bare `warning:` heads (PATH guard + non-zero-rc tail in `claude_invoke`, plus the sink-raised head in `_emit_call_end`).
  - `tests/test_claude_errors.py` — add `from plan_tool import style`; add a `TestClaudeErrorsStyleOutput` class.
  - `tests/test_lessons.py` — add `from plan_tool import style`; extend the `from plan_tool.lessons import (…)` block with `_migrate_general_lessons_from_legacy`, `_append_citation_jsonl`, and `LessonEntry` (already imported); add a `TestLessonsStyleOutput` class.
  - `tests/test_shell.py` — add `from plan_tool import style`; add a `TestShellStyleOutput` class.

## Implementation

### Shared byte-identity rule (all three modules)

- **Drop only the literal head, keep everything else verbatim.** Each target's first fragment begins with the literal `plan-tool: ` or `warning: `. Collapse the f-string fragments into one `body`, dropping only that head; the helper re-adds it. Preserve every inter-fragment trailing space and any embedded `\n` inside the body exactly.
- **`tool()` for `plan-tool:` heads, `warn()` for bare `warning:` heads.** Map each prefix word to its own helper — collapsing both onto one silently rewrites the other family. Do **not** pass `level=` for any site: no converted line uses `style`'s level vocabulary as its leading word.
- **Leading-whitespace-before-prefix sites split.** `tool()`/`warn()` emit the tag as the first bytes, so a `"\nplan-tool: …"` literal cannot be reproduced by passing `"\n…"` as the body. Emit the leading newline separately with `print("", file=stream)` then route the prefixed remainder through the helper; assert the concatenated bytes equal the original (`"\nplan-tool: …\n"`).
- **Match each site's existing stream.** `claude_errors` sites write to the injectable `stream` local — pass `stream=stream`. `lessons` and `shell` sites hardcode `sys.stderr` — rely on the helpers' `stream=sys.stderr` default (omit the kwarg).

### `plan_tool/claude_errors.py`

- **Add the import.** Insert `from plan_tool.style import tool` after the stdlib imports (the block ending with `from typing import Callable, Optional`). Import only `tool` — every converted line here is `plan-tool:`-prefixed.
- **`wait_until_epoch` — the waiting notice.** The `print(f"\nplan-tool: waiting until {reset_display} for claude quota ({remaining}s). Press Ctrl+C to abort.", file=stream)` head carries a leading `\n`. Convert to `print("", file=stream)` followed by `tool(f"waiting until {reset_display} for claude quota ({remaining}s). Press Ctrl+C to abort.", stream=stream)`.
- **`wait_until_epoch` — the cancel-check notice.** `print("\nplan-tool: wait cancelled.", file=stream)` (inside the `cancel_check()` branch) → `print("", file=stream)` + `tool("wait cancelled.", stream=stream)`.
- **`wait_until_epoch` — the completion notice.** `print("plan-tool: wait complete, retrying.", file=stream)` has no leading newline → `tool("wait complete, retrying.", stream=stream)`.
- **`wait_until_epoch` — the `KeyboardInterrupt` notice.** `print("\nplan-tool: wait interrupted.", file=stream)` → `print("", file=stream)` + `tool("wait interrupted.", stream=stream)`. Leave the subsequent `signal.signal(...)` re-install untouched.
- **Leave the `\r` countdown ticker raw.** The per-tick `stream.write(f"\rplan-tool: {hrs:02d}:{mins:02d}:{secs:02d} remaining   ")` + `stream.flush()` is a carriage-return-rewritten progress line, not a terminated diagnostic head — `tool()` always prints a newline-terminated line and cannot reproduce the in-place `\r` rewrite. Keep it (and the `stream.write("\r" + " " * 60 + "\r")` clear) as raw `stream.write`. See Deferred.

### `plan_tool/lessons.py`

- **Add the import.** Insert `from plan_tool.style import tool, warn` into the first-party `from plan_tool.X import …` cluster (the block with `from plan_tool.renderer import prompts_dir` and `from plan_tool.shell import claude_invoke`). Both helpers are needed — this module mixes `plan-tool:` and bare `warning:` heads.
- **`_migrate_general_lessons_from_legacy` — the migration-failure notice.** The `print(f"plan-tool: warning: legacy-general-lessons migration failed …", file=sys.stderr)` head is a `plan-tool:` line with an embedded `warning:` **domain sub-tag**. Route it through `tool()` with the sub-tag kept in the body: `tool(f"warning: legacy-general-lessons migration failed ({type(exc).__name__}: {exc}); leaving {legacy_dir} in place. Retry on next run.")`. **Do not** use `tool(..., level="warning")` — in plain mode both are byte-identical, but `level=` colors the `warning:` span BOLD_YELLOW under `PLAN_TOOL_FORCE_COLOR`, whereas the established convention keeps only the `plan-tool:` tag dimmed and leaves domain sub-tags plain. This is the one load-bearing routing decision in the step.
- **`_migrate_general_lessons_from_legacy` — the migrated-count notice.** `print(f"plan-tool: migrated {len(copied)} general-lessons artifact(s) from {legacy_dir} to {new_dir}", file=sys.stderr)` → `tool(f"migrated {len(copied)} general-lessons artifact(s) from {legacy_dir} to {new_dir}")`.
- **`_append_citation_jsonl` — the sidecar-write-failure notice.** `print(f"plan-tool: failed to append citation sidecar {path} ({exc}); the bullet is still written, only the audit-trail record was lost", file=sys.stderr)` → `tool(f"failed to append citation sidecar {path} ({exc}); the bullet is still written, only the audit-trail record was lost")`.
- **`find_lesson_equivalences` — the unparseable-response warning.** `print("warning: equivalence response was unparseable; treating as no findings", file=sys.stderr)` is a bare `warning:` head → `warn("equivalence response was unparseable; treating as no findings")`.
- **`find_lesson_equivalences` — the checkpoint-save-failure notice.** `print(f"plan-tool: failed to save equivalence checkpoint {ckpt_path} ({exc}); resume on next run will not be available for this call", file=sys.stderr)` → `tool(f"failed to save equivalence checkpoint {ckpt_path} ({exc}); resume on next run will not be available for this call")`.

### `plan_tool/shell.py`

- **Add the import.** Insert `from plan_tool.style import tool, warn` after the `from plan_tool.claude_errors import (…)` block (before `from plan_tool.run_log import (…)`). Both helpers are needed.
- **`claude_invoke` — PATH guard (`warning:`).** `print("warning: \`claude\` executable not found on PATH", file=sys.stderr)` → `warn("\`claude\` executable not found on PATH")`. The `"not found on PATH"` substring survives, so `test_invoke_returns_127_when_claude_not_on_path` still passes.
- **`claude_invoke` — non-zero-rc stderr tail (`warning:`).** `print(f"warning: claude exited with code {rc}; stderr:\n{stderr_tail}", file=sys.stderr)` → `warn(f"claude exited with code {rc}; stderr:\n{stderr_tail}")`. The embedded `\n{stderr_tail}` stays in the body; `warn()` re-adds only the leading `warning: `.
- **`claude_invoke` — rate-limit already-retried head.** `print(f"plan-tool: {format_user_hint(failure)} (already retried once)", file=sys.stderr)` → `tool(f"{format_user_hint(failure)} (already retried once)")`.
- **`claude_invoke` — no-reset-time fallback head.** `print("plan-tool: no reset time in claude output; waiting {…}s as fallback", file=sys.stderr)` → `tool("no reset time in claude output; " f"waiting {DEFAULT_RATE_LIMIT_FALLBACK_SECONDS}s as fallback")`, preserving the two-fragment join exactly.
- **`claude_invoke` — rate-limit hint head (the `else` branch).** `print(f"plan-tool: {format_user_hint(failure)}", file=sys.stderr)` → `tool(f"{format_user_hint(failure)}")`.
- **`claude_invoke` — transient-retry head.** `print(f"plan-tool: {format_user_hint(failure)}; retry {transient_attempts + 1}/{max_transient_retries - 1} in {delay:.0f}s", file=sys.stderr)` → `tool(...)` with the same three-fragment body verbatim.
- **`claude_invoke` — terminal-failure head.** The final `print(f"plan-tool: {format_user_hint(failure)}", file=sys.stderr)` (covering CONTEXT_OVERFLOW / UNKNOWN_NONZERO / rate-limit-with-wait-disabled / transient-exhausted) → `tool(f"{format_user_hint(failure)}")`. Two `plan-tool: {format_user_hint(failure)}` sites now read identically — that is correct; both are the same diagnostic shape.
- **`_emit_call_end` — sink-raised head (`warning:`).** `print(f"warning: run-log sink raised {type(exc).__name__}: {exc}; claude call result is unaffected", file=sys.stderr)` → `warn(f"run-log sink raised {type(exc).__name__}: {exc}; claude call result is unaffected")`.

### New test classes

- **`tests/test_claude_errors.py:TestClaudeErrorsStyleOutput`** — `wait_until_epoch` already accepts an injectable `stream=` (see existing `test_wait_until_epoch_*`), so use `io.StringIO()` for plain-mode byte checks and a TTY-faking StringIO subclass (mirror `tests/test_style.py:_TTY`) plus `monkeypatch.setenv("PLAN_TOOL_FORCE_COLOR", "1")` for color checks. Drive the completion notice via an immediate-past target (returns after `wait complete`), the interrupt notice via a `clock`/`sleep` seam that raises `KeyboardInterrupt`, and the cancel notice via `cancel_check=lambda: True`.
- **`tests/test_lessons.py:TestLessonsStyleOutput`** — all three `lessons` sites hardcode `sys.stderr`, so capture via `capsys.readouterr().err`. The autouse HOME-redirection fixture (`conftest.py:_isolate_known_roots_cache`, which pins `Path.home()`) keeps the migration paths under a temp dir. Drive the migration-failure notice by monkeypatching the breadcrumb/`write_text` to raise `OSError`; the citation-failure notice by pointing `_append_citation_jsonl` at an unwritable path or monkeypatching `Path.open` to raise; the equivalence sites via `find_lesson_equivalences` with an injected invoker returning unparseable text (warning) and a checkpoint path whose `save_checkpoint` raises `OSError`.
- **`tests/test_shell.py:TestShellStyleOutput`** — function-style module; add the class alongside the existing functions. All `shell` sites hardcode `sys.stderr` → capsys. Reuse the `_fake_run_factory` + `monkeypatch.setattr(shell.shutil, "which", …)` seams already in the file to drive each branch (missing-exe, non-zero rc, rate-limit, transient, terminal).

## Tests

`tests/test_claude_errors.py` — `TestClaudeErrorsStyleOutput`:
- `test_waiting_notice_plain` — leading blank line then `plan-tool: waiting until …` head; asserts the `"\nplan-tool: waiting until "` prefix bytes.
- `test_wait_complete_plain` — `stream.getvalue()` ends with `"plan-tool: wait complete, retrying.\n"`.
- `test_wait_cancelled_plain` — cancel-check path emits `"\nplan-tool: wait cancelled.\n"`.
- `test_wait_interrupted_plain` — `KeyboardInterrupt` path emits `"\nplan-tool: wait interrupted.\n"`.
- `test_countdown_ticker_stays_raw` — the per-tick line still begins `"\rplan-tool: "` with no ANSI even under `PLAN_TOOL_FORCE_COLOR` (proves the ticker was not routed through `tool()`).
- `test_wait_complete_color_prefix_only` — under forced color, output contains `style.DIM + "plan-tool:" + style.RESET + " "` and the body carries no escapes.

`tests/test_lessons.py` — `TestLessonsStyleOutput`:
- `test_migration_failure_plain` — `capsys.err` equals `"plan-tool: warning: legacy-general-lessons migration failed (…); leaving … in place. Retry on next run.\n"` with no standalone `warning:`-led line (sub-tag stays in body).
- `test_migration_success_plain` — `"plan-tool: migrated N general-lessons artifact(s) from … to …\n"`.
- `test_citation_failure_plain` — `"plan-tool: failed to append citation sidecar … ; the bullet is still written…\n"`.
- `test_equivalence_unparseable_warns_plain` — `"warning: equivalence response was unparseable; treating as no findings\n"`.
- `test_equivalence_checkpoint_failure_plain` — `"plan-tool: failed to save equivalence checkpoint … ; resume on next run…\n"`.
- `test_migration_failure_color_prefix_only` — forced color: only `plan-tool:` is DIM-wrapped; the `warning:` sub-tag and body stay plain.

`tests/test_shell.py` — `TestShellStyleOutput`:
- `test_missing_exe_warn_plain` — `"warning: \`claude\` executable not found on PATH\n"` (and `"not found on PATH"` substring preserved).
- `test_nonzero_rc_warn_plain` — `"warning: claude exited with code {rc}; stderr:\n{tail}\n"`.
- `test_rate_limit_hint_tool_plain` — rate-limit branch emits a `"plan-tool: …"` head.
- `test_no_reset_fallback_tool_plain` — `"plan-tool: no reset time in claude output; waiting {N}s as fallback\n"`.
- `test_transient_retry_tool_plain` — `"plan-tool: …; retry 1/{…} in {…}s\n"`.
- `test_terminal_failure_tool_plain` — UNKNOWN_NONZERO branch emits a `"plan-tool: …"` head and returns `(rc, stdout)`.
- `test_sink_raised_warn_plain` — `"warning: run-log sink raised …; claude call result is unaffected\n"`.
- `test_missing_exe_warn_color_prefix_only` — forced color: `style.BOLD_YELLOW + "warning:" + style.RESET` prefix, plain body.

## Acceptance criteria

- `rg "print\(f?\"(plan-tool|warning):" plan_tool/claude_errors.py plan_tool/lessons.py plan_tool/shell.py` returns zero matches (the `\r` countdown `stream.write` is not a `print` and is exempt).
- `rg "from plan_tool.style import" plan_tool/claude_errors.py plan_tool/lessons.py plan_tool/shell.py` shows `tool` in all three, and `warn` in `lessons.py` and `shell.py`.
- The countdown ticker still writes `"\rplan-tool: HH:MM:SS remaining   "` raw — no `tool()` call in the per-tick loop body of `wait_until_epoch`.
- `pytest tests/test_claude_errors.py tests/test_lessons.py tests/test_shell.py` passes, including the three new `*StyleOutput` classes and the pre-existing `test_invoke_returns_127_when_claude_not_on_path`.
- No `level=` argument is passed at any converted site (`rg "tool\(.*level=" plan_tool/{claude_errors,lessons,shell}.py` → zero).
- Plain-mode byte output for every converted site equals its pre-change string (asserted by the new tests).

## References

- [NO_COLOR standard](https://no-color.org/) — the `NO_COLOR` convention `style.color_enabled` honors when gating ANSI on or off; relevant because these diagnostics now inherit that gate.
- [XTerm Control Sequences (invisible-island, Thomas Dickey)](https://invisible-island.net/xterm/ctlseqs/ctlseqs.html) — catalog of SGR and the carriage-return (`\r`) cursor behavior the `wait_until_epoch` countdown ticker relies on, explaining why it cannot route through `tool()`.
- [ECMA-48: Control Functions for Coded Character Sets](https://ecma-international.org/publications-and-standards/standards/ecma-48/) — specifies the DIM/BOLD/color SGR parameters emitted by `style.paint`, asserted in the color-mode tests.
- [sys — stdout/stderr (Python docs)](https://docs.python.org/3/library/sys.html#sys.stdout) — confirms the `sys.stderr` default the helpers fall back to, matching each converted site's original destination.

## Deferred

- **The `\r` countdown ticker in `wait_until_epoch`** — `stream.write(f"\rplan-tool: {hrs:02d}:{mins:02d}:{secs:02d} remaining   ")` and the `stream.write("\r" + " " * 60 + "\r")` clear stay raw. They are carriage-return-rewritten progress lines, not newline-terminated diagnostic heads; `tool()` cannot reproduce in-place rewriting. Any future progress-styling helper would own this, not `tool()`.
- **`format_user_hint`'s docstring example** (`print(format_user_hint(...))`) — a docstring illustration, not an emit site; left unchanged.
- **`--output-format json` envelope swap** — the deferred follow-up that lands token/cache/cost capture in `ClaudeCallEnd`; orthogonal to prefix consolidation and out of scope here.
- **Pruning duplicate `tool(f"{format_user_hint(failure)}")` sites in `claude_invoke`** — the rate-limit-hint and terminal-failure heads render identically but guard different branches; collapsing them is a control-flow change, not a presentation refactor.
