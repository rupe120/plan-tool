> **Replaced**: this file has been superseded by `docs/implementation-plans/2-completeness-cli-layering.md`.
> Preserved here for history; do not edit.

## Overview

Restore the thin CLI handler contract for `plan_tool/cli/completeness_cmd.py` by moving `_run_iterate_convergence_loop` (~1086 lines) and the non-CLI logic chunks inside `cmd_completeness_apply` (~559 lines) into `plan_tool/cli/completeness_phases.py`, which already functions as the de facto orchestrator for this command's supporting logic. After the move, `completeness_cmd.py` holds only argument validation, dispatch, and terminal-output/exit-code mapping, calling into the extracted functions with zero behavior change. This is a pure code-motion refactor: no flag, output, exit code, or check/apply/report behavior changes, and observable behavior (terminal output, return codes, files written, run-log contents) must be identical before and after.

## Problem statement

`plan_tool/cli/completeness_cmd.py` currently embeds two large orchestration blocks that don't belong in a CLI handler: `_run_iterate_convergence_loop` (~1086 lines, covering setup/lock acquisition, the up-front conceptual audit, the per-finding `while True` dispatch loop, and teardown) and roughly 559 lines of non-CLI logic inside `cmd_completeness_apply` (saved-audit resolution and freshness/revision-currency checks, source ranking/`--anchor` narrowing, and the walk-orchestration engine). This violates the project's CLI layering convention, under which handler modules stay thin — argument validation, dispatch, and terminal-output/exit-code mapping — while the real orchestration logic lives in top-level orchestrator modules. `completeness_phases.py` already serves that role for this command's other supporting logic, with 30+ top-level functions past line 2181, so the same "orchestration logic filed under `cli/`" pattern these two functions exhibit is otherwise absent from this module today.

## Architecture

Move `_run_iterate_convergence_loop`'s full body into `completeness_phases.py` as a named function preserving its existing signature/return contract (`_IterateOutcome`, already defined there at line 102); `completeness_cmd.py` calls it unchanged. Extract `cmd_completeness_apply`'s three identifiable logic chunks into named functions in the same module: saved-audit resolution + freshness/revision-currency checks (~lines 247–364), source ranking / `--anchor` narrowing (~lines 377–402), and the walk-orchestration engine (build `WalkState`, `RunLogWriter`, carried-resolution history, `action_fn` closures, call `walk_recommendations`) (~lines 509–724). `cmd_completeness_apply` retains the genuinely CLI-shaped front and back — arg validation, the clean-tree/`--commit` precheck, printed advisories, and exit-code mapping — and becomes a short sequence of calls into the extracted functions.

Every piece of load-bearing state threaded through today must be preserved exactly, by reference rather than by copy: `ConvergenceState`, the drift-detection iteration-lock context manager (released on every early-return path, including halts), `ScopeGuardBuffer` (accumulated across iterations, flushed once at the end), `_carried_resolution` / `applied_fingerprints`, `run_logger` phase bracketing, `WalkState`, and `saved.recommendations`'s in-place, order-sensitive narrowing (the walker persists annotations keyed by `rec.id`).

`_run_iterate_convergence_loop` and `cmd_completeness_apply`'s extracted logic stay as separate named functions rather than being folded together, even where the extracted shapes end up looking structurally similar — they serve different commands (`completeness-audit --iterate` vs. `completeness-apply`) with different state contracts. No file other than `completeness_phases.py` and `completeness_cmd.py` changes shape as part of this move.

## Out of scope

- `completeness_phases.py` physically moving out of `plan_tool/cli/` to sit beside `completeness_report.py` as a first-class top-level orchestrator — it already functions as the landing spot for this command's logic regardless of its own package location; relocating the file is a separate, larger reorganization question, named as a candidate follow-up in this plan's docs rather than acted on.
- `plan_tool/cli/run_cmd.py:cmd_run` (505 lines) — re-verified against current HEAD, it is not a CLI-layering violation like the two functions above: every phase inside it needs `argparse.Namespace` access, terminal output, or exit-code mapping, and its one real execution step (`run_step`) is already correctly factored into `launcher.py`. Its size is a decompose-in-place problem, not a relocation problem, and belongs to a future, separate, much-lower-risk effort.
- Any change to what `completeness-audit --iterate` or `completeness-apply` actually check, apply, or report — this is a pure code-motion refactor.
- Restructuring `tests/cli/COVERAGE_BASELINE.md`'s format — update its `cmd_completeness_apply` row only if its own convention requires an entry for the newly-named extracted functions.

## Risks

- `_run_iterate_convergence_loop` has no caller outside `completeness_cmd.py` in production code, but `tests/cli/test_completeness_cmd.py` calls it directly (not only through `cmd_completeness`) — its import path changes, and those call sites need updating to the new location, not rewritten to test something different.
- `cmd_completeness_apply`'s three chunks are threaded through by mutable, order-sensitive state (`WalkState`, `_carried_resolution`, `saved.recommendations` narrowed in place). Extracting them risks accidentally copying state instead of sharing a reference, or reordering a read/write that currently depends on being interleaved with the surrounding CLI code. Mitigation: trace each piece of state named under Architecture through the extraction and confirm the same object identity is threaded, not a copy.

## Testing

`tests/cli/test_completeness_cmd.py` already covers both functions, including calling `_run_iterate_convergence_loop` directly — these tests are the primary behavior-preservation proof and must pass with only import-path updates, no assertion changes. Add unit-level characterization coverage for the three newly named `cmd_completeness_apply` extraction targets only if doing so doesn't require inventing new test infrastructure; exercising them through the existing full-`cmd_completeness_apply` tests is sufficient to prove the refactor, so isolated unit tests are a nice-to-have, not a requirement.

## Acceptance criteria

- `_run_iterate_convergence_loop` and `cmd_completeness_apply`'s three logic chunks live in `plan_tool/cli/completeness_phases.py`; `plan_tool/cli/completeness_cmd.py`'s versions are thin callers.
- Full test suite green with no assertion changes beyond import-path updates in `tests/cli/test_completeness_cmd.py`.
- No CLI-facing behavior (flags, output, exit codes) changed.

## Deferred

- `completeness_phases.py`'s own location within the `cli/` package — named as a related finding but explicitly not part of this plan's scope; file separately if worth pursuing.
- `cmd_run`'s internal decomposition — named as a related finding but explicitly not part of this plan's scope; file separately if worth pursuing.
