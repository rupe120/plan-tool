> **Auto-archived**: this plan was swept on 2026-06-01 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 2 — De-duplicate the report against the interactive walk in `cmd_review`

## Summary

- Thread a single keyword-only `walk_will_run: bool = False` parameter through `assemble_report` (`plan_tool/review.py`), forwarded from `review_plan_full` / `review_plan`. It captures one fact: *will the interactive walk follow this report?*
- When `walk_will_run` is `True`, `assemble_report` does **two** things so each deterministic finding's detail appears exactly once (in the walk), not twice or three times:
  1. **Omit** the `### Suggested actions` block (the walk presents the same per-recommendation actions interactively).
  2. **Slim** the `### Per-step status` `WARN` lines to finding *counts* (e.g. `- Step 3 (pending)  WARN — 2 findings`) instead of the joined issue detail; the per-step OK/WARN map stays as the at-a-glance overview, but the finding *detail* moves solely to the walk. The `> hint:` low-confidence legend is also dropped in this mode (there are no inline `hint:` detail lines left for it to explain).
- When `walk_will_run` is `False` (the default, and every non-interactive run), the report is unchanged byte-for-byte: full `### Suggested actions` block and full `WARN` detail are retained, because those readers have no walk and the report is their only actionable summary.
- Compute the value in `cmd_review` (`plan_tool/cli.py`) from a single-sourced walk-environment predicate and pass `walk_will_run=_review_walk_environment_allows(args)` into the review call.
- The semantic review and the severity banner (Step 3) render in **both** modes. **No new CLI flag** — `walk_will_run` is an internal parameter threaded from the command into the report builder.

## Table of Contents

- [Why](#why) — the same findings printed statically, then re-presented by the walk
- [Files (creates vs edits)](#files-creates-vs-edits) — the edited files and their changes
- [Implementation](#implementation) — the `walk_will_run` param, the block omission, the WARN-line slimming, the walk-environment predicate, and the zero-recs subsumption
- [Tests](#tests) — unit gating for both behaviors, the predicate, and the CLI include/omit cases
- [Acceptance criteria](#acceptance-criteria) — checkable behaviors on green
- [References](#references) — argparse/TTY docs relevant to this step
- [Deferred](#deferred) — saved-review reuse path and the no-new-flag decision

## Why

- `cmd_review` prints `result.report` (per-step status block + the trailing `### Suggested actions` block) and then, when the environment permits, immediately drives `walk_recommendations` over the same findings. The `### Suggested actions` block and the walk derive from the same per-step iteration (`assemble_report` builds `suggestions`; `extract_recommendations` builds the parallel `Recommendation` list), so an interactive user sees every action twice — once as static markdown, once as the live prompt.
- The per-step `WARN` lines compound it: each restates the same finding detail a *third* time (status `WARN` line → suggested-actions bullet → walk item). Dropping only the suggested-actions block still leaves the finding detail in both the `WARN` line and the walk. Slimming the `WARN` lines to counts when the walk follows is what reduces deterministic-finding detail to a true 1× and fully satisfies the problem statement's "two-to-three times" complaint.
- The fix scopes both reductions to exactly the runs where a walk follows. When no walk follows (`--no-walk`, `--no-save`/`--dry-run`, non-interactive CI/pipe), the report is the reader's only actionable surface, so the full block and full `WARN` detail must stay.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/review.py` — add keyword-only `walk_will_run: bool = False` to `assemble_report`; when `True`, gate off the `### Suggested actions` block, slim the per-step `WARN` detail to a finding count, and drop the `> hint:` legend. Thread the same param through `review_plan_full` (forward to `assemble_report`) and the `review_plan` back-compat wrapper (forward to `review_plan_full`).
  - `plan_tool/cli.py` — add a `_review_walk_environment_allows(args)` predicate, single-source the existing walk gate in `cmd_review` through it, and pass `walk_will_run=_review_walk_environment_allows(args)` into the `review_plan_full` call.
  - `tests/test_review.py` — add gating unit tests for both behaviors plus the predicate and CLI include/omit cases.

## Implementation

### `plan_tool/review.py` — `assemble_report`

- **Add a keyword-only param** `walk_will_run: bool = False` to the existing `*`-separated signature. Default `False` keeps every direct `assemble_report` caller in `tests/test_review.py` (e.g. `TestAssembleReport.test_ok_and_warn_lines`, `test_missing_parent_diagnostic_uses_relative_paths`) byte-identical, since `False` means "no walk → full report".
- **Block gating.** At the trailing `if suggestions:` branch that appends `"### Suggested actions"`, change the condition to `if suggestions and not walk_will_run:`. Leave the `suggestions` accumulation and the `seen` de-dup loop untouched; only the section header + bullets are suppressed.
- **WARN-line slimming.** In the per-step status loop, the `WARN` branch currently sets `detail = "; ".join(issues)`. When `walk_will_run` is `True`, set `detail = f"{len(issues)} finding{'s' if len(issues) != 1 else ''}"` instead. The `verdict = "WARN"` and the `- Step {id} ({status})  {verdict} — {detail}` line shape are unchanged — only the detail string collapses to a count. OK lines are never touched (they carry no finding detail).
- **Hint legend.** The `any_heuristic` `> hint:` note explains the inline `hint:` symbol/file detail. When `walk_will_run` is `True` those inline details are gone (folded into the count), so guard the legend append with `if any_heuristic and not walk_will_run:`.
- **Do not touch** the `_render_completeness_section` block, the path-style section, or the `### Claude's semantic review` / severity-banner sections — the at-a-glance map header, completeness, semantic review, and banner all render in both modes.

### `plan_tool/review.py` — `review_plan_full` and `review_plan`

- **`review_plan_full`:** add keyword-only `walk_will_run: bool = False`; pass it through to the `assemble_report(...)` call alongside the existing keyword arguments. The early `if dry_run:` return (which yields the prompt as `report`) precedes `assemble_report`, so the flag is a no-op on dry-run — note that in the param's one-line doc.
- **`review_plan` wrapper:** add the same param with default `False` and forward it to `review_plan_full`, mirroring how the wrapper already forwards `no_heuristic` / `allow_missing_parent` / `extract_lessons`. Default `False` preserves the str-returning contract for `test_review_plan_str_wrapper_still_works` and the many `review_plan(...)` call sites.

### `plan_tool/cli.py` — `cmd_review` and the walk predicate

- **Add a module-level helper** near `cmd_review`:
  - `_review_walk_environment_allows(args) -> bool` returns `not args.no_walk and not args.no_save and not args.dry_run and (args.yes or sys.stdin.isatty())`.
  - This is the **environment portion** of the walk decision — everything knowable before `review_plan_full` runs. It deliberately excludes `saved_path is not None` and `result.recommendations`, which are only known after the call.
- **Single-source the existing walk gate.** Replace the inline boolean at the `if (not args.no_walk and saved_path is not None and result.recommendations and (args.yes or sys.stdin.isatty())):` site with `if _review_walk_environment_allows(args) and saved_path is not None and result.recommendations:`. `saved_path is not None` already implies `not args.no_save and not args.dry_run`, so the combined condition is unchanged in behavior — it just reuses the predicate.
- **Pass the flag into the review call.** In the `review_plan_full(...)` invocation in `cmd_review`, add `walk_will_run=_review_walk_environment_allows(args)`. So:
  - Walk-environment allowed → `result.report` omits the block and slims the `WARN` lines (the walk will present the detail, unless recs turn out empty — see next bullet).
  - Walk-environment disallowed → `result.report` keeps the full block and full `WARN` detail.
- **Zero-recommendations subsumption (load-bearing):** when the environment allows the walk but `result.recommendations` is empty, the walk is still skipped at the gate — yet `walk_will_run` was `True`. This is harmless for **both** behaviors: every `suggestions` entry and every per-step `WARN` issue originates from a finding that also produces a `Recommendation` (file-check, missing-on-DONE, heuristic, dep), so an empty recommendation set means an empty `suggestions` list **and** no `WARN` lines — nothing to omit or slim under either flag value. Note this in a code comment at the predicate so a future reader doesn't add a redundant `result.recommendations`-aware re-render.
- **Saved artifact follows the printed report.** `save_review(..., report_md=result.report, ...)` persists whatever `result.report` holds, so the saved markdown carries the slimmed/omitted form exactly when the printed output does. Consistent: a saved review is meant to be re-walked via `cmd_review_walk`, which presents the detail interactively.

## Tests

Add to `tests/test_review.py`.

- `test_assemble_report_walk_mode_omits_block_and_slims_warn` — call `assemble_report(..., walk_will_run=True)` on the `_write_review_fixture` plan; assert `"### Suggested actions"` is absent, the step-3 WARN line reads as a count (e.g. `WARN — 1 finding`) with the missing-parent path detail **absent** from the status block, while `"### Per-step status"`, `"### Claude's semantic review"`, and the severity banner are all still present.
- `test_assemble_report_default_keeps_block_and_warn_detail` — same fixture, default call; assert the `### Suggested actions` block, its `plan-tool run review-test --mode reconcile --step 4` bullet, and the full `WARN —`-with-path detail are all present (guards the default-`False` byte-identical contract; complements existing `test_ok_and_warn_lines`).
- `test_warn_count_singular_plural` — a step with exactly one issue renders `1 finding`; a step with two renders `2 findings` under `walk_will_run=True`.
- `test_hint_legend_dropped_in_walk_mode` — on the heuristic-tripping fixture, `walk_will_run=True` omits the `> hint:` legend (and the inline `hint:` detail); the default keeps both.
- `test_review_walk_environment_allows_predicate` — table over fake `argparse.Namespace` values: `--no-walk` → False; `--no-save` → False; `--dry-run` → False; non-TTY and not `-y` → False; `-y` set → True; TTY True (monkeypatch `sys.stdin.isatty`) → True.
- `test_review_plan_full_threads_walk_will_run` — invoke `review_plan_full(..., walk_will_run=True, invoker=None)` on a plan with a missing-parent file; assert `result.report` omits `### Suggested actions` and slims the WARN line, but still lists the per-step WARN (as a count) and a non-empty `result.recommendations`.
- `test_cmd_review_no_walk_keeps_full_report` — in `TestCmdReviewSaveByDefault`, run `main([..., "review", "review-test", "--no-walk"])` (non-TTY harness, `invoker=None`); assert stdout contains `### Suggested actions` and the full WARN detail, and the walk did not run.
- `test_cmd_review_walk_run_slims_report` — drive the walk: monkeypatch `sys.stdin.isatty` → True (or pass `-y`) with `invoker=None`, stub `walk_recommendations` to a no-op spy at `plan_tool.cli.walk_recommendations` (the name `cmd_review` calls, bound via the `cli.py:138` import — patching `plan_tool.review_walk.walk_recommendations` would not intercept the call); assert the spy was called and the printed `result.report` excludes `### Suggested actions` and shows the count-form WARN while retaining `### Per-step status`.
- Keep the existing `TestAssembleReport` cases unmodified as the default-behavior control — they pin that the block and full WARN detail still render on the bare call.

## Acceptance criteria

- `assemble_report(..., walk_will_run=True)` returns a report with **no** `### Suggested actions` header, per-step `WARN` lines collapsed to a finding count (no inline issue/path detail), and no `> hint:` legend — while `### Per-step status`, `### Claude's semantic review`, and the severity banner remain intact.
- `assemble_report(...)` with the param omitted (or `walk_will_run=False`) is byte-identical to its pre-change output (all current `TestAssembleReport` tests pass unmodified).
- `_review_walk_environment_allows(args)` returns `False` for any of `--no-walk`, `--no-save`, `--dry-run`, or (non-TTY and not `-y`); `True` otherwise.
- `plan-tool review <name> --no-walk` prints `### Suggested actions` and full `WARN` detail; an interactive `plan-tool review <name>` that proceeds to the walk prints neither (block omitted, WARN lines as counts).
- No new argument appears in the `review` subparser; `argparse` for `review` is unchanged.
- `tests/test_review.py` passes in full; per the project lesson on shared primitives, also run `tests/test_launcher.py` and create's tests if any classification path is touched — this step touches none, so no cross-suite impact is expected (state that explicitly if the suite is green).

## References

- [argparse — Parser for command-line options, arguments and subcommands (Python docs)](https://docs.python.org/3/library/argparse.html) — Confirms the `review` subparser needs no change; the gating is an internal `Namespace`-derived predicate, not a new flag.
- [io.IOBase.isatty / sys.stdin (Python docs)](https://docs.python.org/3/library/io.html#io.IOBase.isatty) — Semantics of the TTY check that gates the walk and, transitively, the block + WARN slimming; monkeypatched in the predicate tests.
- [pytest — monkeypatch fixture](https://docs.pytest.org/en/stable/how-to/monkeypatch.html) — Patching `sys.stdin.isatty` and stubbing `walk_recommendations` for the CLI include/omit tests.

## Deferred

- **Reuse-saved-review path (`_prompt_reuse_saved_review` branch in `cmd_review`)** — unchanged. It never calls `review_plan_full`; it loads a saved report and walks it. Its block/WARN form was already decided at the original save time. No edit here.
- **`cmd_review_all` / `run --mode <review>` paths** — out of scope. They do not call `review_plan_full` with this CLI walk gate, so they keep current behavior.
- **A `--report`/`-v` "always show the full report" flag** — this step's decision is explicitly *no new flag*; the block + WARN form are purely walk-decision-derived. Track a flag only if users later need the full report alongside the walk.
- **`README.md` documentation** — dropped from this step's footprint. With no new user-facing flag and the block/WARN form derived entirely from the existing walk decision, there is no new surface to document; the behavior change is internal output shaping. Add a note only if user-facing docs later describe the review output shape in detail.
- **Deriving the block/WARN strings from `Recommendation` objects in the CLI** — not done; both stay inside `assemble_report` (their natural producer) and are gated, avoiding a second formatter that could drift from the report's wording.
