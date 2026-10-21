> **Auto-archived**: this plan was swept on 2026-06-01 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 3 — Route the run / reconcile-loop diagnostics in `auto_reconcile.py`, `change_collision.py`, and `iteration_lock.py` through `style.tool()` and pin each with a `*StyleOutput` test class

## Summary

- Replace every hand-rolled `print("plan-tool: …", file=…)` diagnostic head in `plan_tool/auto_reconcile.py`, `plan_tool/change_collision.py`, and `plan_tool/iteration_lock.py` with `plan_tool/style.py`'s `tool()` helper, finishing the consolidation that steps 1 (`review.py`) and 2 (`detail.py`) carried through the other subcommands.
- All converted lines carry the `plan-tool:` prefix only — none use a `warning:`/`error:` style level, so `tool()` is the sole helper imported.
- The load-bearing constraint: plain-mode output stays **byte-identical**, so each f-string drops only its literal `plan-tool: ` head and passes the remainder verbatim as `tool()`'s `body`; the uppercase `WARNING:` sub-tag inside the drift-warning lines stays in the body (it is a domain sub-tag, not `tool()`'s `level` vocabulary).
- On green, three new test classes — including a brand-new `tests/test_auto_reconcile.py` — assert that byte-identity in plain mode and prefix-only ANSI under `PLAN_TOOL_FORCE_COLOR`, and assert that subordinate continuation lines (bullets, blank lines, merge-command examples, `Drifted files:`) stay raw.

## Table of Contents

- [Why](#why) — what's inconsistent about these three modules' diagnostics today
- [Files (creates vs edits)](#files-creates-vs-edits) — one new test file, five edits
- [Implementation](#implementation) — per-site conversion in each module and the new test classes
- [Tests](#tests) — cases in the three `*StyleOutput` classes
- [Acceptance criteria](#acceptance-criteria) — checkable behaviors on green
- [References](#references) — color/SGR/stream docs consulted
- [Deferred](#deferred) — sites and helpers intentionally left raw

## Why

- **These three modules are the last library surfaces still hand-rolling `plan-tool:` diagnostics.** After steps 1–2 routed `review.py` and `detail.py` through `style.tool()`, `auto_reconcile.py`, `change_collision.py`, and `iteration_lock.py` remain on raw `print(f"plan-tool: …", file=out)`. None imports `plan_tool.style`, so their lines miss the centralized `NO_COLOR` / `PLAN_TOOL_FORCE_COLOR` / TTY gate, and any future wording or color change must be made in two places.
- **`plan_tool/style.py` is the single owner of the `plan-tool:` namespace** (`tool(body, stream=…)` with no level renders exactly `plan-tool: <body>`, dim tag under color). The project's stated direction is one owner for prefix + color + stream; these three modules are the remaining holdouts.
- **The risk is silent wording drift.** These strings are read by operators in run logs and during drift halts. A `StringIO`/capsys byte-equality test locks plain-mode output so the refactor is provably presentation-only.

## Files (creates vs edits)

- **New files:**
  - `tests/test_auto_reconcile.py` — module's first test file; holds `TestAutoReconcileStyleOutput` (and only that, for this step).
- **Existing files (edits only):**
  - `plan_tool/auto_reconcile.py` — add `from plan_tool.style import tool`; convert the eight `plan-tool:` heads in `run_auto_reconcile_on_drift`.
  - `plan_tool/change_collision.py` — add `from plan_tool.style import tool`; convert the `plan-tool:` heads in `save_collision_sidecars`, `emit_collision_summary`, and `prompt_user_to_merge`; leave the summary's continuation lines and the interactive prompt string raw.
  - `plan_tool/iteration_lock.py` — add `from plan_tool.style import tool`; convert the `plan-tool:` heads in `acquire_lock`, `emit_drift_warning`, `emit_drift_halt_warning`, and the `_handler` closure inside `_make_sigint_release_handler`; leave the `Drifted files:` label and the `  - …` bullets raw.
  - `tests/test_change_collision.py` — add `from plan_tool import style`; add `TestChangeCollisionStyleOutput`.
  - `tests/test_iteration_lock.py` — add `from plan_tool import style`; add `TestIterationLockStyleOutput`.

## Implementation

### Shared byte-identity rule (all three modules)

- **Each converted head is `print(f"plan-tool: <rest>", file=<stream>)` → `tool(f"<rest>", stream=<stream>)`.** Drop only the literal `plan-tool: ` head; `tool()` re-adds it. Preserve every inter-fragment space inside the existing f-strings exactly.
- **Never pass `level=`.** Every line here is a bare `plan-tool:` head. The uppercase `WARNING:` that opens the drift-warning bodies is a domain sub-tag living *inside* the message — passing `level="warning"` would emit `plan-tool: warning:` (lowercase, extra colon) and break byte-identity. Keep `WARNING:` in the `body` string.
- **Route only prefixed heads; leave subordinate lines as raw `print`.** Continuation bullets (`  - …`), blank lines, the `Example merge commands…` block, and the `Drifted files:` label have no namespace prefix; passing them through `tool()` would prepend a spurious tag and break their visual nesting.
- **`tool()` defaults `stream=sys.stderr`.** Sites that resolve `out = file if file is not None else sys.stderr` must pass `stream=out`. Sites that hardcode `file=sys.stderr` may omit `stream` (default matches) — pass it explicitly for grep-ability.

### `plan_tool/auto_reconcile.py`

- **Add the import.** Insert `from plan_tool.style import tool` after the stdlib block (`import sys` / `from pathlib import Path` / `from typing import Optional`). Keep it at module top — `tool` is cheap stdlib-only; only the `launcher`/`review`/`review_persistence` imports stay lazy inside the function.
- **Amend the module docstring invariant.** The docstring states `stdlib-only at the public-API boundary; first-party imports happen lazily inside :func:`run_auto_reconcile_on_drift``. Adding the top-level `style` import falsifies it — update that sentence to carve out `plan_tool.style` (cheap, stdlib-only) as the one eagerly-imported first-party module while the `launcher`/`review`/`review_persistence` imports stay lazy.
- **Convert all eight heads in `run_auto_reconcile_on_drift`, each `print(…, file=out)` → `tool(…, stream=out)`:**
  - the **no-mapped-files skip** (`auto-reconcile skipped: no drifted file maps …`) on the `if not buckets:` early return,
  - the **running-auto-reconcile banner** (`running auto-reconcile on {len(buckets)} affected step(s) …`),
  - the **launcher-error** branch (`auto-reconcile on step {step_id}: launcher error ({exc}); skipping`) in the `except LauncherError` block,
  - the **claude-exited-nonzero** branch (`… claude exited {result.exit_code}; skipping …`),
  - the **save-failed** branch (`… {len(recs)} finding(s) raised but save failed ({exc}) …`) in the `except OSError` block,
  - the **save-succeeded** line (`… {len(recs)} finding(s) raised (saved to {saved_path})`),
  - the **unmapped-files note** (`auto-reconcile skipped {len(unmapped)} drifted file(s) …`),
  - the **walk-hint** (`walk findings interactively with \`plan-tool review-walk {plan_slug}\``).
- **No control-flow changes.** Return value (`total_findings`) and all branch conditions are untouched; this is presentation-ownership only.

### `plan_tool/change_collision.py`

- **Add the import.** Insert `from plan_tool.style import tool` after `import sys` and the `dataclasses`/`pathlib`/`typing` block.
- **Amend the module docstring invariant.** The docstring states `Module dependencies: stdlib only at the public-API boundary.`. Adding the top-level `style` import falsifies it — update that sentence to note `plan_tool.style` as the lone first-party dependency (for diagnostic styling) while the module still imports no `plan_tool.launcher`.
- **`save_collision_sidecars` — convert all six heads** (`print(…, file=out)` → `tool(…, stream=out)`): the **read-failed** (`collision-sidecar read failed for {original}: …`), the **restore-after-delete failed** (`failed to restore {original} after apply_finding deleted it …`), the **allocation-failed** (`collision-sidecar allocation failed for {original}: …`), the **write-failed** (`collision-sidecar write failed for {sidecar}: …`), the **restore-after-write failed** (`failed to restore {original} after writing sidecar …`), and the **SIGINT-mid-save** notice (`caught SIGINT mid-collision-save; …`) in the `except KeyboardInterrupt` block.
- **`emit_collision_summary` — convert the one head, leave the rest raw.** Route the multi-fragment **summary header** (`drift collision -- saved claude's plan/detail edits to {len(sidecars)} sidecar file(s). …`) through `tool(…, stream=out)`. Leave **raw** `print`s: the `  - {_rel(s.original)}  ⇄  {_rel(s.sidecar)}` pair bullets, the blank `print("", file=out)`, the `Example merge commands (pick any tool):` label, and the three `code --diff` / `vimdiff` / `meld` example lines — none carries the `plan-tool:` prefix.
- **`prompt_user_to_merge` — convert the four `print` heads, leave the input prompt raw.** Route through `tool(…, stream=out)`: the **headless-skip** (`skipping merge pause (non-interactive); …`), the **EOF-abort** (`merge prompt aborted via EOF; …`), the **declined** (`merge prompt declined; …`), and the **acknowledged** (`merge acknowledged; continuing iteration …`) lines. **Do not touch** the `input_fn("\nplan-tool: merge the sidecar file(s) above, then press Enter …> ")` argument — it is a prompt passed to `input_fn`, not a `print`, and `tool()` cannot produce a return value or the trailing `> ` (see Deferred).

### `plan_tool/iteration_lock.py`

- **Add the import.** Insert `from plan_tool.style import tool` after the stdlib block; this is the module's first first-party import beyond `Path`, so place it in its own line group below `from pathlib import Path`.
- **Amend the module docstring invariant.** The docstring states `Pure file I/O + signal handling. No claude shell-out, no first-party `plan_tool.*` imports beyond `Path``. Adding the top-level `style` import falsifies it — update that sentence to allow `plan_tool.style` (for diagnostic styling) alongside `Path` while still asserting no claude shell-out.
- **`acquire_lock` — convert the lockfile-clearing notice.** The `print(f"plan-tool: clearing existing iteration lockfile at {lock_path} (was: …). Mutual-exclusion checks are disabled; …", file=sys.stderr)` inside `if existing is not None:` becomes `tool(f"clearing existing iteration lockfile at {lock_path} …", stream=sys.stderr)`. The function threads no `file=` kwarg, so the test captures this via capsys.
- **`emit_drift_warning` — convert the head, keep `WARNING:` in the body, leave bullets raw.** The opener `print(f"plan-tool: WARNING: {len(drifted_list)} watched file(s) changed during the {loop_name} iteration loop. …", file=out)` becomes `tool(f"WARNING: {len(drifted_list)} watched file(s) changed during the {loop_name} iteration loop. …", stream=out)`. Leave the `  - {line}` bullets and the `  - ... and {N} more` overflow line as raw `print`.
- **`emit_drift_halt_warning` — convert the two openers and the trailer, leave label + bullets raw.** Both `opener` strings (the `phase == "before"` and the `"during"` branches, each beginning `plan-tool: WARNING: drift detected on …`) build a string then `print(opener, file=out)`. Convert that to `tool(opener, stream=out)` and strip the literal `plan-tool: ` head from each `opener` assignment (keep `WARNING:` in the body). Convert the trailing `print("plan-tool: pass --allow-drift to opt back into the legacy warn-but-proceed behavior.", file=out)` → `tool("pass --allow-drift …", stream=out)`. Leave the `Drifted files:` label and the `  - …` bullets raw.
- **`_make_sigint_release_handler` → `_handler` — convert the SIGINT notice, preserving its leading newline.** The current `print("\nplan-tool: caught SIGINT; releasing iteration lock and exiting.", file=out)` (inside `if not lock.released:`) carries a leading `\n` *before* the prefix, which `tool()` cannot emit (it always writes `plan-tool:` first). Split into two calls to keep byte-identity and route the head through the helper: `print("", file=out)` then `tool("caught SIGINT; releasing iteration lock and exiting.", stream=out)`. The blank `print` emits the leading `\n`; `tool()` emits `plan-tool: caught SIGINT…\n`; concatenated bytes equal the original `\nplan-tool: …\n`.

### New + extended test classes

- **`tests/test_auto_reconcile.py` (new file).** Module header docstring in the sibling style (`"""Tests for plan_tool.auto_reconcile. …"""`); imports `io`, `from pathlib import Path`, `pytest`, `from plan_tool import style`, and `from plan_tool.auto_reconcile import run_auto_reconcile_on_drift`. The function exposes a `file=` seam, so most paths capture via `io.StringIO`. The no-mapped-files skip path returns before any first-party import and needs no stubbing. The run-loop heads require stubbing the lazily-imported callables — monkeypatch `plan_tool.launcher.run_step`, `plan_tool.launcher.LauncherError`, `plan_tool.review.extract_reconcile_recommendations`, and `plan_tool.review_persistence.save_review` (the function imports them at call time, so patching the source modules takes effect). Provide a tiny fake result object with `exit_code` and `stdout` attributes.
- **`tests/test_change_collision.py` — add `TestChangeCollisionStyleOutput`.** Add `from plan_tool import style` to the imports (the module already imports `io` and the `change_collision` symbols). Every target function exposes a `file=` seam, so drive each with `io.StringIO`; `prompt_user_to_merge` also takes `input_fn` / `isatty_fn` for headless vs. interactive control.
- **`tests/test_iteration_lock.py` — add `TestIterationLockStyleOutput`.** Add `import io` and `from plan_tool import style` and ensure `emit_drift_warning`, `emit_drift_halt_warning`, and `_make_sigint_release_handler` are importable from `plan_tool.iteration_lock`. `emit_drift_warning` / `emit_drift_halt_warning` take `file=`; the `acquire_lock` clearing notice is captured via capsys (no kwarg); the SIGINT notice is reached by building the handler with `file=buf` and calling `_handler(signum=2, frame=None)` inside `pytest.raises(KeyboardInterrupt)`.
- **Color-assertion template:** mirror the prefix-shape assertion in `tests/test_style.py:TestDiagnosticHelpers.test_tool_colored_tag_and_level` and the `PLAN_TOOL_FORCE_COLOR`-via-`monkeypatch.setenv` mechanism in `tests/test_style.py:TestColorEnabled.test_force_color_wins_over_non_tty` — set `PLAN_TOOL_FORCE_COLOR` via `monkeypatch.setenv`, and assert the output starts with `style.DIM + "plan-tool:" + style.RESET + " "` with the body (including any `WARNING:` sub-tag) carrying no surrounding escapes. `io.StringIO` is non-TTY, so `PLAN_TOOL_FORCE_COLOR` is required to force color; for capsys-captured sites set the env var and assert the same prefix sentinel.

## Tests

### `tests/test_auto_reconcile.py` — `TestAutoReconcileStyleOutput`

- `test_skip_no_mapped_files_plain` — empty `file_to_step` ⇒ buffer equals `"plan-tool: auto-reconcile skipped: no drifted file maps to a plan step (run \`plan-tool detail <slug> --reconcile --step N\` manually to investigate)\n"`.
- `test_running_banner_plain` — one mapped drifted file + stubbed `run_step`/`extract_reconcile_recommendations`/`save_review` ⇒ buffer contains the byte-exact `plan-tool: running auto-reconcile on 1 affected step(s) …` banner.
- `test_launcher_error_plain` — stub `run_step` to raise `LauncherError` ⇒ buffer contains `plan-tool: auto-reconcile on step {id}: launcher error (…); skipping`.
- `test_claude_nonzero_plain` — stub `run_step` returning `exit_code=1` ⇒ buffer contains `plan-tool: auto-reconcile on step {id} ("{title}"): claude exited 1; skipping …`.
- `test_save_failed_plain` — stub `save_review` to raise `OSError` ⇒ buffer contains `… {N} finding(s) raised but save failed (…); see claude stdout above …`.
- `test_save_succeeded_plain` — happy path ⇒ buffer contains `… {N} finding(s) raised (saved to {path})` and the trailing `plan-tool: walk findings interactively with \`plan-tool review-walk {slug}\``.
- `test_unmapped_note_plain` — one mapped + one unmapped drifted path ⇒ buffer contains `plan-tool: auto-reconcile skipped 1 drifted file(s) outside any step.files declaration`.
- `test_skip_line_color_prefix_only` — `PLAN_TOOL_FORCE_COLOR` set ⇒ no-buckets line starts with `DIM + "plan-tool:" + RESET + " "`, body unescaped.

### `tests/test_change_collision.py` — `TestChangeCollisionStyleOutput`

- `test_summary_header_plain` — `emit_collision_summary` with one sidecar ⇒ first line equals the byte-exact `plan-tool: drift collision -- saved claude's plan/detail edits to 1 sidecar file(s). …` header.
- `test_summary_continuation_lines_have_no_prefix` — same call ⇒ the `  - … ⇄ …` pair line, the `Example merge commands (pick any tool):` label, and the `code --diff` / `vimdiff` / `meld` lines contain no `plan-tool:` substring.
- `test_prompt_headless_skip_plain` — `prompt_user_to_merge(..., isatty_fn=lambda: False)` ⇒ buffer equals `"plan-tool: skipping merge pause (non-interactive); halting iteration. Re-run after merging the sidecar file(s) above.\n"` and returns `False`.
- `test_prompt_eof_abort_plain` — `input_fn` raises `EOFError`, `isatty_fn=lambda: True` ⇒ buffer contains `plan-tool: merge prompt aborted via EOF; …`.
- `test_prompt_declined_plain` — `input_fn` returns `"n"` ⇒ buffer contains `plan-tool: merge prompt declined; …`.
- `test_prompt_acknowledged_plain` — `input_fn` returns `""` ⇒ buffer contains `plan-tool: merge acknowledged; continuing iteration with the merged state.` and returns `True`.
- `test_save_write_failed_plain` — monkeypatch the sidecar `write_text` to raise `OSError` so the changed-file branch hits the write-failed head ⇒ buffer contains `plan-tool: collision-sidecar write failed for {sidecar}: …`.
- `test_summary_header_color_prefix_only` — `PLAN_TOOL_FORCE_COLOR` set ⇒ header starts with `DIM + "plan-tool:" + RESET + " "`.

### `tests/test_iteration_lock.py` — `TestIterationLockStyleOutput`

- `test_drift_warning_head_plain` — `emit_drift_warning([Path("a.py")], repo_root=tmp_path, loop_name="reconcile", file=buf)` ⇒ first line equals byte-exact `plan-tool: WARNING: 1 watched file(s) changed during the reconcile iteration loop. …` (uppercase `WARNING:` preserved in body).
- `test_drift_warning_bullets_have_no_prefix` — same call ⇒ the `  - a.py` bullet has no `plan-tool:` substring.
- `test_drift_halt_before_plain` — `emit_drift_halt_warning(..., phase="before", finding_id="F1", file=buf)` ⇒ opener equals byte-exact `plan-tool: WARNING: drift detected on 1 watched file(s) BEFORE applying finding F1. …`.
- `test_drift_halt_during_plain` — `phase="during"` ⇒ opener equals the byte-exact `… DURING apply of finding F1. That apply's edits to plan/detail were KEPT …` line.
- `test_drift_halt_trailer_and_label` — same call ⇒ buffer contains the raw `Drifted files:` label (no prefix) and the `plan-tool: pass --allow-drift to opt back into the legacy warn-but-proceed behavior.` trailer head.
- `test_acquire_clearing_notice_plain` — acquire once, then acquire again against the existing lockfile ⇒ `capsys.readouterr().err` contains `plan-tool: clearing existing iteration lockfile at {path} (was: …`.
- `test_sigint_notice_preserves_leading_newline` — build handler via `_make_sigint_release_handler(lock, repo_root=tmp_path, loop_name="run", file=buf)`, call `_handler(2, None)` inside `pytest.raises(KeyboardInterrupt)` with `lock.released` false ⇒ buffer contains `"\nplan-tool: caught SIGINT; releasing iteration lock and exiting.\n"`.
- `test_drift_warning_head_color_prefix_only` — `PLAN_TOOL_FORCE_COLOR` set ⇒ head starts with `DIM + "plan-tool:" + RESET + " "` and the `WARNING:` sub-tag in the body carries no escapes.

## Acceptance criteria

- `grep -n '"plan-tool:' plan_tool/auto_reconcile.py plan_tool/change_collision.py plan_tool/iteration_lock.py` drops from 8/11/5 matches at HEAD to 0/0/0 — no hand-rolled `plan-tool:` head remains in any of the three modules. Note: the 0/0/0 result for `change_collision.py` and `iteration_lock.py` depends on the retained `input_fn` merge prompt (`"\nplan-tool: merge …`) and the split SIGINT notice both beginning with `"\n`, so neither matches the `"plan-tool:` literal — do not "normalize" either string to start with `"plan-tool:` or the zero-match criterion breaks silently.
- Each of the three modules contains exactly one `from plan_tool.style import tool` line and no `warn`/`error`/`info`/`note`/`level=` usage.
- The interactive `input_fn(…)` prompt string in `change_collision.py:prompt_user_to_merge` still contains its literal `plan-tool: merge the sidecar file(s) above …> ` text unchanged (it is not routed through `tool()`).
- The raw continuation lines stay raw: `emit_collision_summary`'s `⇄` bullets / `Example merge commands` block, and `emit_drift_warning` / `emit_drift_halt_warning`'s `  - …` bullets and `Drifted files:` label produce no `plan-tool:` prefix.
- `tests/test_auto_reconcile.py` exists and `TestAutoReconcileStyleOutput`, `TestChangeCollisionStyleOutput`, and `TestIterationLockStyleOutput` all pass.
- All byte-identity cases assert plain-mode output equal to the pre-refactor strings (including the uppercase `WARNING:` sub-tags and the leading `\n` on the SIGINT notice).
- Color cases assert each converted head starts with `style.DIM + "plan-tool:" + style.RESET + " "` under `PLAN_TOOL_FORCE_COLOR`, with the body unescaped.
- `pytest tests/test_auto_reconcile.py tests/test_change_collision.py tests/test_iteration_lock.py tests/test_style.py` is green.

## References

- [NO_COLOR standard](https://no-color.org/) — the `NO_COLOR` convention `style.color_enabled` honors; relevant because the converted lines now inherit that gate.
- [XTerm Control Sequences (invisible-island, Thomas Dickey)](https://invisible-island.net/xterm/ctlseqs/ctlseqs.html) — catalog of the SGR escapes (`DIM`=`\033[2m`, `RESET`=`\033[0m`) the color-mode assertions check for.
- [ECMA-48: Control Functions for Coded Character Sets](https://ecma-international.org/publications-and-standards/standards/ecma-48/) — primary standard for the SGR parameters (dim, reset) emitted by `style.tool()`.
- [sys — System-specific parameters and functions (Python docs)](https://docs.python.org/3/library/sys.html#sys.stderr) — reference for the `sys.stderr` default stream and the `isatty()` TTY check that decides color.

## Deferred

- **The interactive merge prompt in `prompt_user_to_merge`** — left as a raw `input_fn("\nplan-tool: merge …> ")` argument. It is an input prompt, not a diagnostic `print`; `tool()` cannot return the user's response or emit the trailing `> ` continuation, and its leading `\n` precedes the prefix. Wording stays under `change_collision.py`'s ownership for now.
- **`warn()` / `error()` routing** — not used in this step. Every converted line is a bare `plan-tool:` head; the uppercase `WARNING:` inside the drift-warning bodies is a domain sub-tag, not `tool()`'s `level` vocabulary. Introducing `level="warning"` would rewrite those bytes and is explicitly out of scope.
- **Iteration entry-point integration (`cmd_completeness`, `_iterate_reconcile_loop`, `create_plan`, `generate_detail`)** — their wiring of these helpers is covered by sibling integration tests in `tests/test_cli.py` / `tests/test_create.py` / `tests/test_detail.py`; this step pins only the library-level emitters in the three modules.
- **The `--allow-drift` / `--no-collision-sidecar` flag plumbing** — flag parsing and dispatch are owned elsewhere; this step changes only how the diagnostic lines are formatted, not when they fire.
