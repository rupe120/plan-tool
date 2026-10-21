> **Auto-archived**: this plan was swept on 2026-06-01 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 2 — Route `detail.py`'s `plan-tool:`/`warning:` diagnostics through `style.tool()`/`style.warn()` and pin them with `TestDetailStyleOutput`

## Summary

Replace the eight hand-rolled `print("plan-tool: …" / "warning: …", file=sys.stderr)` diagnostic heads in `plan_tool/detail.py` with calls to `plan_tool/style.py`'s `tool()` and `warn()` helpers, so `detail`'s library-level lines share one owner for prefix wording, color gating, and target stream. The seven `plan-tool:` heads (checkpoint save + the two discard sites, archived-previous, archived-orphan, iteration-halt, lesson-extraction error) route through `tool()`; the one `warning:` head (detail-body-mentions) routes through `warn()`; the `_repo_relative` out-of-tree `warning:` is converted too so no hand-rolled diagnostic remains in the file. The load-bearing constraint: plain-mode output stays **byte-identical** to today's strings — each multi-fragment f-string drops only its literal `plan-tool: ` / `warning: ` head and passes the remainder verbatim as the helper's `body`. On green, a new `TestDetailStyleOutput` class in `tests/test_detail.py` asserts that byte-identity (capsys, plain mode) and prefix-only ANSI under `PLAN_TOOL_FORCE_COLOR`.

## Table of Contents

- [Why](#why) — what's inconsistent about detail.py's diagnostics today
- [Files (creates vs edits)](#files-creates-vs-edits) — the two files touched
- [Implementation](#implementation) — per-site conversion and the new test class
- [Tests](#tests) — cases in `TestDetailStyleOutput`
- [Acceptance criteria](#acceptance-criteria) — checkable behaviors on green
- [References](#references) — color/SGR/stream docs consulted
- [Deferred](#deferred) — sites intentionally left as raw prints

## Why

- **`detail.py` still hand-rolls every `plan-tool:`/`warning:` diagnostic.** It emits raw `print(f"plan-tool: …", file=sys.stderr)` and `print(f"warning: …", file=sys.stderr)` and has no `from plan_tool.style import …` line, so its lines miss the centralized `NO_COLOR` / `PLAN_TOOL_FORCE_COLOR` / TTY gate, and wording must be maintained in two places. (Once step 1 lands, `review.py` routes through `style.tool()` the same way.)
- **One owner for prefix + color + stream is the project's stated direction.** `plan_tool/style.py` exists precisely so `plan-tool:` and `warning:` look the same regardless of which subcommand emits them; `create.py`, `launcher.py`, and `cli.py` already import from it.
- **The risk is silent wording drift.** These strings are scanned by operators reading run logs. The byte-identity test locks plain-mode output so the refactor is provably presentation-only.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/detail.py` — add `from plan_tool.style import tool, warn` to the import block; convert the eight diagnostic heads named below (seven `tool()`, one `warn()`) inside `generate_detail`, plus the one `warn()` site in `_repo_relative`.
  - `tests/test_detail.py` — add `from plan_tool import style`, ensure `_repo_relative` is importable from `plan_tool.detail`, and add a `TestDetailStyleOutput` class.

## Implementation

### `plan_tool/detail.py`

- **Add the import.** Insert `from plan_tool.style import tool, warn` alongside the existing `from plan_tool.X import …` cluster (the block that already imports `from plan_tool.progress import ProgressReporter, StderrReporter` and `from plan_tool.schema import Plan, Step`). Match the sibling convention — `create.py` uses `from plan_tool.style import …, tool, warn`.

- **Byte-identity rule for every conversion.** Each target is a multi-fragment f-string whose first fragment begins with the literal `plan-tool: ` or `warning: `. Collapse the fragments into one `body` string, dropping **only** that literal head, and preserve every inter-fragment trailing space exactly (the existing literals carry the joining spaces — e.g. `"… {ckpt_path} "` + `"({exc}); …"`). The helpers re-add the head, so plain-mode bytes are unchanged. All target sites currently pass `file=sys.stderr`; both `tool()` and `warn()` default `stream` to `sys.stderr`, so omit the kwarg — the destination is preserved.

- **Seven `plan-tool:` heads → `tool(body)` (no `level=`)** — all inside `generate_detail`:
  - **declined-resume discard failure** — the `except OSError` in the `_confirm_resume`-declined branch (`failed to discard declined checkpoint …; next run may re-prompt against the same stale body`) → `tool(f"failed to discard declined checkpoint {ckpt_path} ({exc}); next run may re-prompt against the same stale body")`.
  - **checkpoint save failure** — the `except OSError` after `save_checkpoint(...)` (`failed to save checkpoint …; resume on next run will not be available for step {step.id}`) → `tool(...)`.
  - **durable-write discard failure** — the `except OSError` after the post-write `discard_checkpoint(ckpt_path)` (`failed to discard checkpoint …; next run may waste a hash-match read`) → `tool(...)`.
  - **archived-previous-detail** — the `if archived_prior is not None:` branch (`archived previous detail to {archived_prior}`) → `tool(f"archived previous detail to {archived_prior}")`.
  - **archived-orphan-detail** — the `for dest in archived:` loop (`archived orphan detail to {dest}`) → `tool(f"archived orphan detail to {dest}")`.
  - **iteration-halt** — the `if not open_apply:` → `if open_deferred:` branch in the convergence `while` loop (`detail iteration halting -- all {len(open_deferred)} remaining finding(s) for step {step.id} are triaged-deferred. Apply manually or pass --no-triage to force-apply.`) → `tool(...)`.
  - **lesson-extraction error** — the `except Exception` after `extract_and_append_detail_lessons(...)` (`lesson extraction failed for step {step.id} ({exc}); detail file is unaffected`) → `tool(...)`. **Do NOT pass `level="error"`** — `tool()` with a level emits `plan-tool: error: …`, breaking byte-identity. The leading domain words stay in `body`; the level taxonomy is separate from the message (the in-code comment at this site says errors "keep the `plan-tool:` prefix" — that is exactly `tool()` with no level).

- **One `warning:` head → `warn(body)`** — inside `generate_detail`:
  - **detail-body-mentions** — the `if mentioned * 2 < len(declared):` branch (`step {step.id} detail body mentions {mentioned} of {len(declared)} declared files; missing: {', '.join(missing)}`) → `warn(f"step {step.id} detail body mentions {mentioned} of {len(declared)} declared files; missing: {', '.join(missing)}")`. `warn()` emits `warning: <body>` — byte-identical.

- **One `warning:` head beyond the enumerated cluster → `warn(body)`** — in `_repo_relative`:
  - **out-of-tree detail path** — the `except ValueError` (`detail path {path} is not under repo root {repo_root}; storing absolute path in step.detail`) → `warn(f"detail path {path} is not under repo root {repo_root}; storing absolute path in step.detail")`. Convert this so no hand-rolled `warning:`/`plan-tool:` line survives in the file; it is the same pattern, same default stream, byte-identical. Called out explicitly because it sits outside the step title's enumerated list.

### `tests/test_detail.py`

- **Add `TestDetailStyleOutput`** following `tests/test_style.py:TestDiagnosticHelpers` for the color assertions and the existing `test_save_checkpoint_oserror_is_swallowed_with_warning` for the capsys-driven trigger pattern.
- **Capture strategy is capsys, not StringIO.** Every converted site inside `generate_detail` hardcodes the stderr destination through the helper's default — there is no stream kwarg threaded through `generate_detail` — so drive the real branch with monkeypatch/fixtures and read `capsys.readouterr().err`. The `_repo_relative` site is a pure function and is tested by a direct call (no `generate_detail`).
- **Reuse `_write_orchestrator_plan` / `_detail_path_for` / `_GOOD_BODY`** from the existing orchestrator fixtures. For the body-mentions case, build a step whose `files:` has ≥2 entries none of which appear in the body, so `mentioned * 2 < len(declared)` fires.
- **Plain mode is the capsys default** (captured streams are non-TTY, `PLAN_TOOL_FORCE_COLOR`/`NO_COLOR` unset) → assert the exact legacy line. **Color mode** sets `monkeypatch.setenv("PLAN_TOOL_FORCE_COLOR", "1")` and asserts the line starts with `style.DIM + "plan-tool:" + style.RESET + " "` (for `tool()` sites) or `style.BOLD_YELLOW + "warning:" + style.RESET + " "` (for `warn()` sites), body carrying no surrounding escapes.
- **Lesson-extraction-error test overrides the autouse `_stub_lessons_extraction`** by re-monkeypatching `detail_module.extract_and_append_detail_lessons` to raise, and calls `generate_detail(..., extract_lessons=True)`.

## Tests

All in `tests/test_detail.py`, class `TestDetailStyleOutput`:

- `test_save_checkpoint_failure_plain` — monkeypatch `detail.save_checkpoint`→`OSError`; stderr contains exact line `plan-tool: failed to save checkpoint <path> (disk full); resume on next run will not be available for step 1`.
- `test_save_checkpoint_failure_color_prefix_only` — same trigger + `PLAN_TOOL_FORCE_COLOR`; line starts `style.DIM + "plan-tool:" + style.RESET + " "`, body has no escapes.
- `test_declined_resume_discard_failure_plain` — seed a valid checkpoint, decline via `prompt_fn`, monkeypatch `detail.discard_checkpoint`→`OSError`; asserts `plan-tool: failed to discard declined checkpoint …; next run may re-prompt against the same stale body`.
- `test_durable_write_discard_failure_plain` — no seeded/declined checkpoint; monkeypatch `detail.discard_checkpoint`→`OSError` so only the post-write discard fires; asserts `plan-tool: failed to discard checkpoint …; next run may waste a hash-match read`.
- `test_archived_previous_detail_plain` — pre-write a file at the canonical output path, run with `force=True`; asserts `plan-tool: archived previous detail to <archive-path>`.
- `test_archived_orphan_detail_plain` — pre-create a sibling `NN-*.md` with a different slug under the step's detail dir; asserts `plan-tool: archived orphan detail to <dest>`.
- `test_detail_body_mentions_warning_plain` — step with ≥2 declared files unmentioned in the body; asserts `warning: step <id> detail body mentions <m> of <n> declared files; missing: …`.
- `test_detail_body_mentions_warning_color_prefix_only` — same + `PLAN_TOOL_FORCE_COLOR`; line starts `style.BOLD_YELLOW + "warning:" + style.RESET + " "`.
- `test_lesson_extraction_error_plain` — re-monkeypatch `extract_and_append_detail_lessons`→raise, `extract_lessons=True`; asserts `plan-tool: lesson extraction failed for step <id> (…); detail file is unaffected`.
- `test_lesson_extraction_error_no_error_level` — same trigger; asserts the captured line does **not** contain `error:` (guards against a future `level="error"` regression that would break byte-identity).
- `test_iteration_halt_plain` — `budget=IterativeBudget(enabled=True, …)` with a small cap; stub `collect_detail_quality_findings` (module-level at `detail.py:451`, so patch `detail.collect_detail_quality_findings`) to return deferred-only findings, and stub `partition_findings_for_triage` on `plan_tool.review.partition_findings_for_triage` (it is imported lazily inside the convergence loop at `detail.py:1536`, so patching `detail.partition_findings_for_triage` won't take effect) so `open_apply` is empty and `open_deferred` non-empty; asserts `plan-tool: detail iteration halting -- all <k> remaining finding(s) for step <id> are triaged-deferred. Apply manually or pass --no-triage to force-apply.`. (Heaviest setup; the only site requiring the convergence loop.)
- `test_repo_relative_out_of_tree_warning_plain` — call `_repo_relative(Path("/elsewhere/x.md"), repo_root=tmp_path)` directly; asserts return equals `str(Path("/elsewhere/x.md").resolve())` and stderr line is `warning: detail path /elsewhere/x.md is not under repo root <tmp_path>; storing absolute path in step.detail` — the message interpolates the un-resolved `repo_root`, so the expected `<tmp_path>` is `tmp_path` as passed, not `tmp_path.resolve()`.
- `test_repo_relative_out_of_tree_warning_color_prefix_only` — same + `PLAN_TOOL_FORCE_COLOR`; line starts `style.BOLD_YELLOW + "warning:" + style.RESET + " "`.

## Acceptance criteria

- `plan_tool/detail.py` contains `from plan_tool.style import tool, warn` and zero remaining string-literal prefixes `"plan-tool: ` or `"warning: ` (grep on those literals returns 0, down from 9 at HEAD, since `style.py` now owns the literal).
- In plain mode every converted line is byte-identical to its pre-refactor string (captured `capsys.readouterr().err` equals the legacy line including the trailing newline).
- Under `PLAN_TOOL_FORCE_COLOR`, only the prefix tag carries ANSI: `tool()` lines start with `\033[2mplan-tool:\033[0m ` and `warn()` lines start with `\033[1;33mwarning:\033[0m `; the body contains no escape sequences.
- The lesson-extraction error line never contains `error:` (no `level=` passed).
- All target sites still write to `sys.stderr` (the helpers' default), so stdout is unchanged.
- `TestDetailStyleOutput` passes; the pre-existing `test_save_checkpoint_oserror_is_swallowed_with_warning` still passes (its `"failed to save checkpoint" in err` / `"step 1" in err` substring assertions hold under the converted line).

## References

- [NO_COLOR standard](https://no-color.org/) — the `NO_COLOR` convention `style.color_enabled()` honors when gating ANSI off.
- [XTerm Control Sequences (invisible-island, Thomas Dickey)](https://invisible-island.net/xterm/ctlseqs/ctlseqs.html) — catalog of SGR escapes underlying `DIM`/`BOLD_YELLOW`/`RESET` asserted in the color tests.
- [ECMA-48: Control Functions for Coded Character Sets](https://ecma-international.org/publications-and-standards/standards/ecma-48/) — primary standard for the SGR parameters (dim, bold, foreground color, reset) emitted by the helpers.
- [sys — stdout/stderr (Python docs)](https://docs.python.org/3/library/sys.html#sys.stdout) — reference for the stderr stream and `isatty()`-based TTY detection that decides where formatted diagnostics go.

## Deferred

- **Indented continuation/status lines stay raw `print(...)`** — `  step {id}: response failed parse (attempt …)`, `        detail-quality: starting convergence loop …`, the `detail iteration loop stopped …` bar banner, `        detail-quality: converged (0 findings …)`, and `        captured {n} general + {n} project lesson(s)`. These have no namespace prefix by design; routing them through `tool()` would prepend a spurious `plan-tool:` and break their visual nesting.
- **`style.note()` / `level=`-carrying variants** — not used; every converted line maps to the bare `tool()` or `warn()` form to preserve byte-identity.
- **CLI/integration wiring of `--iterate`** — the iteration-halt line is reachable only with `budget.enabled=True`, wired by the later plan step; this step's test forces it via a constructed `IterativeBudget` and stubbed collectors rather than the CLI flag.
