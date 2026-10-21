> **Auto-archived**: this plan was swept on 2026-06-01 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 1 — Route review.py library diagnostics through `style.tool()` and pin their output with `TestReviewStyleOutput`

## Summary

Replace the four hand-rolled `print("plan-tool: …", file=…)` diagnostic emitters in `plan_tool/review.py` with calls to `plan_tool/style.py`'s `tool()` helper, so every library-level line shares one owner for prefix wording, color gating, and target stream. The sites are `emit_triage_summary` (deferred-triage header), `check_criteria_fulfillment` (skip / success / zero lines via `_log_skip` and the two summary prints), `check_plan_audit` (skip via `_log_skip` + the correctness/completeness summary), and the lesson-extraction `except` branch in `review_plan_full`. The load-bearing constraint: plain-mode output must stay **byte-identical** to today's `plan-tool: …` strings, so each f-string drops only its literal `plan-tool: ` head and passes the remainder verbatim as `tool()`'s `body`. On green, a new `TestReviewStyleOutput` class in `tests/test_review.py` asserts that byte-identity in plain mode and that only the `plan-tool:` tag carries ANSI under `PLAN_TOOL_FORCE_COLOR`.

## Table of Contents

- [Why](#why) — what's inconsistent about review.py's diagnostics today
- [Files (creates vs edits)](#files-creates-vs-edits) — the two files touched
- [Implementation](#implementation) — per-site conversion and the new test class
- [Tests](#tests) — cases in `TestReviewStyleOutput`
- [Acceptance criteria](#acceptance-criteria) — checkable behaviors on green
- [References](#references) — color/SGR/stream docs consulted
- [Deferred](#deferred) — sites and helpers intentionally left alone

## Why

- **`review.py` is the last subcommand still hand-rolling its `plan-tool:` diagnostics.** `create.py`, `launcher.py`, and `cli.py` already import from `plan_tool/style.py`; `review.py` has no `style` import and emits raw `print(f"plan-tool: …", file=out)` calls. That means review's lines don't pick up the centralized color gate, and any future wording/color change must be made in two places.
- **One owner for prefix + color + stream is the project's stated direction.** `plan_tool/style.py`'s module docstring and the `tool()` helper exist precisely so `plan-tool:` looks the same regardless of which subcommand emitted it. Routing review's lines through `tool()` finishes that consolidation.
- **The risk is silent wording drift.** These strings are grepped by CI operators (the comments at each site say so). The byte-identity test locks the plain-mode output so the refactor is provably behavior-preserving.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/review.py` — add `from plan_tool.style import tool` to the import block; convert the four diagnostic sites named below.
  - `tests/test_review.py` — add `import io`, `from plan_tool import style`, extend the `from plan_tool.review import (...)` block with `Recommendation`, `emit_triage_summary`, `check_criteria_fulfillment`, `check_plan_audit`, `triage_reason`, and `extract_and_append_review_lessons` (the symbols the new class calls or monkeypatches), extend the existing `from plan_tool.progress import ProgressReporter, StepHandle` line with `NullReporter` (which lives in `plan_tool/progress.py`, not `review.py`), and add a `TestReviewStyleOutput` class.

## Implementation

### `plan_tool/review.py`

- **Add the import.** Insert `from plan_tool.style import tool` alongside the existing `from plan_tool.X import …` block (the cluster ending with `from plan_tool.schema import Plan, Step, StepStatus`). Match the sibling convention: `launcher.py` uses `from plan_tool.style import warn`, `create.py` uses `from plan_tool.style import …, tool, warn`. Import only `tool` — see Deferred for why `warn()` is not used here.

- **`emit_triage_summary` — deferred-triage header.** Replace the `print(f"plan-tool: deferring {len(deferred)} finding(s) by triage …", file=out)` call with `tool(f"deferring {len(deferred)} finding(s) by triage ({iteration_label}). Apply manually if the complexity is worth the impact -- the iteration loop will short-circuit if these are the only findings remaining:", stream=out)`. Strip only the leading `plan-tool: ` literal; keep the rest of the wording (including the `--`) exact.
  - **Leave the per-finding bullet loop untouched** — `print(f"  - {rec.id}: {rec.title} [{triage_reason(rec)}]", file=out)` carries no `plan-tool:` prefix; it is a subordinate continuation line, not a diagnostic head.
  - The lazy `import sys` and `out = file if file is not None else sys.stderr` stay; pass that `out` as `stream=`.

- **`check_criteria_fulfillment` — skip / success / zero lines.** Three conversions, all keeping the `criteria-fulfillment:` sub-tag inside the body (it is part of the wording, **not** a `tool()` `level=`):
  - Inner `_log_skip(reason)`: `tool(f"criteria-fulfillment: skipped ({reason})", stream=out)`. This covers all skip variants (no-invoker, no-criteria-section, no-DONE-files, invoker-raised, invoker-nonzero) since they all route through `_log_skip`.
  - Success summary (the `if attributed:` branch): `tool(f"criteria-fulfillment: {len(attributed)} finding(s) raised", stream=out)`.
  - Zero summary (the `else:` branch): `tool("criteria-fulfillment: 0 findings (plan's acceptance criteria appear met by the code)", stream=out)`.

- **`check_plan_audit` — skip + summary.** Two conversions:
  - Inner `_log_skip(reason)`: `tool(f"plan-audit: skipped ({reason})", stream=out)`.
  - Final summary print: `tool(f"plan-audit: {n_corr} correctness + {n_comp} completeness finding(s)", stream=out)`.

- **`review_plan_full` — lesson-extraction error.** In the `except Exception as exc:` branch guarding `extract_and_append_review_lessons`, replace `print(f"plan-tool: lesson extraction failed ({exc}); review report is unaffected", file=sys.stderr)` with `tool(f"lesson extraction failed ({exc}); review report is unaffected", stream=sys.stderr)`.
  - **Do not add `level="error"`.** That would emit `plan-tool: error: lesson extraction failed …`, breaking the byte-identity the test pins. The existing comment ("Errors keep the `plan-tool:` prefix so they stand out") is satisfied by the dimmed `plan-tool:` tag alone.
  - **Leave the adjacent success line** (`print(f"        captured {n_general} general + {n_project} project lesson(s) from review", file=sys.stderr)`) **unchanged** — it is an indented, prefix-less status line that intentionally nests under the step header, not a `plan-tool:` diagnostic.

- **Design note — why `tool()` and not `warn()` for any cited site.** Every line in scope carries the `plan-tool:` source namespace. `style.tool(body)` with no `level` emits exactly `plan-tool: <body>` (dim tag in color mode), so it is the byte-identity-preserving mapping. `style.warn(body)` emits `warning: <body>` — a different prefix — and would change all seven strings. The sub-tags `criteria-fulfillment:` and `plan-audit:` are domain labels, not the helper's `level=` vocabulary (`warning`/`error`/`note`/`info`), so they belong in `body`.

### `tests/test_review.py`

- **Add a `TestReviewStyleOutput` class** that injects an `io.StringIO` (plain) or sets `PLAN_TOOL_FORCE_COLOR` (color) and asserts on captured output. The three skip/header surfaces accept a stream kwarg directly:
  - `emit_triage_summary(deferred, iteration_label=…, file=buf)`
  - `check_criteria_fulfillment(plan, plan_path, repo_root=…, invoker=None, log_file=buf)` → hits `_log_skip("no invoker configured")`
  - `check_plan_audit(plan, plan_path, repo_root=…, invoker=None, log_file=buf)` → hits `_log_skip("no invoker configured")`
- **Build a `deferred` fixture** for `emit_triage_summary`: a one-element `list[Recommendation]` constructed with all required positional fields (`id`, `source`, `severity`, `step_id`, `title`, `body`; `suggested_action` defaults to `None`), using a known `id` and `title`. Assert the header line plus the `  - <id>: <title> [<reason>]` bullet, deriving the reason via `triage_reason(rec)` so the test doesn't hardcode triage internals.
- **Color assertions** assert the same shape as `tests/test_style.py:TestDiagnosticHelpers.test_tool_colored_tag_and_level`, but trigger color differently: that control enables color via a `_TTY()` StringIO (`isatty()→True`), whereas here set `PLAN_TOOL_FORCE_COLOR` via `monkeypatch.setenv` (checked first in `color_enabled`, `style.py:33`, so it works on a plain `StringIO`). Then assert the output starts with `style.DIM + "plan-tool:" + style.RESET + " "` and that the body substring (e.g. `plan-audit: skipped (no invoker configured)`) appears with no surrounding escapes.
- **Lesson-extraction line** is the one site that hardcodes `sys.stderr` rather than taking a stream kwarg. The `except` branch (`review.py:3571`) is only reachable when the gate at `review.py:3545-3550` holds — `extract_lessons` truthy, `invoker is not None`, `claude_stdout_for_recs is not None`, and `recommendations` non-empty — so the test must satisfy all four. Drive `review_plan_full` with `extract_lessons=True` and a non-None `invoker` whose `(0, stdout)` return supplies a non-empty `claude_stdout_for_recs` and a findings-producing plan fixture yields a non-empty `recommendations` (both derived internally, not kwargs), and `monkeypatch` `extract_and_append_review_lessons` to raise; capture the `plan-tool:`-prefixed stderr line via `capsys`. **Inject `reporter=NullReporter()`** (per the `review.py:3473-3474` convention): a non-None `invoker` returning `(0, non-empty)` otherwise makes `review_plan_full` build a `StderrReporter` (`review.py:3477-3479`) that emits `[1/1] Claude semantic review`/`done in …` to stderr, which would defeat any exact-match assertion on the captured stream. Do **not** substitute "assert the rendered body against the legacy literal" — that exercises `style.tool` directly and wouldn't prove review's call site routes through it. Note in the test why this site differs from the other three (it hardcodes `sys.stderr` instead of accepting a stream kwarg).

## Tests

In `tests/test_review.py`, class `TestReviewStyleOutput`:

- `test_triage_summary_plain_byte_identical` — `emit_triage_summary` to a `StringIO` emits the exact legacy `plan-tool: deferring 1 finding(s) by triage (…)…:` header plus the `  - <id>: <title> [<reason>]` bullet.
- `test_criteria_fulfillment_skip_plain` — `check_criteria_fulfillment(invoker=None, log_file=buf)` writes exactly `plan-tool: criteria-fulfillment: skipped (no invoker configured)\n`.
- `test_plan_audit_skip_plain` — `check_plan_audit(invoker=None, log_file=buf)` writes exactly `plan-tool: plan-audit: skipped (no invoker configured)\n`.
- `test_triage_summary_color_prefix_only` — under `PLAN_TOOL_FORCE_COLOR`, the line starts with `DIM + "plan-tool:" + RESET` and the body carries no escapes.
- `test_plan_audit_skip_color_prefix_only` — same prefix-only-color assertion for the `plan-audit:` skip line.
- `test_lesson_extraction_error_plain` — drive `review_plan_full` with the gate inputs the `except` branch requires (`review.py:3545-3550`: `extract_lessons=True`, non-None `invoker`, non-None `claude_stdout_for_recs`, non-empty `recommendations`), inject `reporter=NullReporter()` so the `StderrReporter` progress lines (`review.py:3477-3479`) don't pollute the stream, and `monkeypatch` `extract_and_append_review_lessons` to raise; assert `capsys` captures exactly `plan-tool: lesson extraction failed (<exc>); review report is unaffected\n` on stderr.

The existing `tests/test_style.py:TestDiagnosticHelpers` cases (`test_tool_plain_no_level`, `test_tool_colored_tag_and_level`) remain the control for `style.tool()` itself; `TestReviewStyleOutput` proves review's call sites feed it the right body.

## Acceptance criteria

- `plan_tool/review.py` imports `tool` from `plan_tool.style` and contains no remaining `print(` call whose first argument begins with the literal `plan-tool:`.
- `emit_triage_summary(..., file=buf)`, `check_criteria_fulfillment(..., invoker=None, log_file=buf)`, and `check_plan_audit(..., invoker=None, log_file=buf)` each produce plain-mode output byte-for-byte equal to the pre-refactor strings.
- With `PLAN_TOOL_FORCE_COLOR` set, every converted line is `\033[2mplan-tool:\033[0m ` followed by the unstyled body.
- No converted call passes `level=`; the `criteria-fulfillment:` / `plan-audit:` sub-tags remain in the body.
- `pytest tests/test_review.py tests/test_style.py` passes, including the new `TestReviewStyleOutput`.

## References

- [NO_COLOR standard](https://no-color.org/) — the convention `style.color_enabled` honors; confirms why `NO_COLOR` must beat a real TTY but `PLAN_TOOL_FORCE_COLOR` overrides both.
- [ECMA-48: Control Functions for Coded Character Sets](https://ecma-international.org/publications-and-standards/standards/ecma-48/) — SGR parameters behind `DIM` (`\033[2m`) and `RESET` (`\033[0m`) asserted in the color tests.
- [sys — `sys.stdout` / `sys.stderr` (Python docs)](https://docs.python.org/3/library/sys.html#sys.stdout) — reference for the default stderr destination `tool()` writes to and the `isatty()` TTY check the gate falls back on.

## Deferred

- **`warn()` / `error()` conversions** — out of scope; every cited line uses the `plan-tool:` namespace, so all map to `tool()`. Converting any to `warn()`/`error()` would change the prefix and break byte-identity.
- **The deferred-triage `  - …` bullet lines and the `        captured … lesson(s)` success line** — left as raw `print`; they are prefix-less continuation/status lines, not `plan-tool:` diagnostics.
- **The five other `check_file_existence` call-site consumers** (`create.py`, `launcher.py:preflight_step_paths`, `cli.py`) — this step changes only how review's diagnostics are *printed*, not classification semantics, so the cross-subcommand test fan-out noted in the path-classification lesson does not apply here.
- **Routing `review.py`'s stdout report bodies through `style`** — `assemble_report` and the rendered markdown are a separate output surface handled by other steps in this plan.
