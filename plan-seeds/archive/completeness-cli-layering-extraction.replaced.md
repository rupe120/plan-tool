> **Replaced**: this file has been superseded by `docs/implementation-plans/2-completeness-cli-layering.md`.
> Preserved here for history; do not edit.

# Seed: extract CLI-embedded orchestration logic out of completeness_cmd.py

## Outcome

Restore the "thin CLI handler" contract for `plan_tool/cli/completeness_cmd.py`:
`_run_iterate_convergence_loop` (~1086 lines) and the non-CLI logic chunks inside
`cmd_completeness_apply` (~559 lines) move to `plan_tool/cli/completeness_phases.py`
— already the de facto orchestrator for this command's supporting logic — leaving
`completeness_cmd.py` holding only argument validation, dispatch, and
terminal-output/exit-code mapping, with zero behavior change.

## In scope

- Move `_run_iterate_convergence_loop`'s full body (setup/lock acquisition, the
  up-front conceptual audit, the per-finding `while True` dispatch loop, teardown)
  into `completeness_phases.py` as a named function with the same signature/return
  contract (`_IterateOutcome`, already defined there at line 102).
  `completeness_cmd.py` calls it, unchanged in behavior.
- Extract `cmd_completeness_apply`'s three identifiable logic chunks into named
  functions in `completeness_phases.py`:
  - saved-audit resolution + freshness/revision-currency checks (~lines 247–364)
  - source ranking / `--anchor` narrowing (~lines 377–402)
  - the walk-orchestration engine (build `WalkState`, `RunLogWriter`, carried-
    resolution history, `action_fn` closures, call `walk_recommendations`)
    (~lines 509–724)
  `cmd_completeness_apply` keeps arg validation, the clean-tree/`--commit`
  precheck, printed advisories, and exit-code mapping — the genuinely CLI-shaped
  front and back — and becomes a short sequence of calls into the extracted
  functions.
- Preserve every piece of load-bearing state exactly as threaded today:
  `ConvergenceState`, the drift-detection iteration-lock context manager
  (released on every early-return path, including halts), `ScopeGuardBuffer`
  (accumulated across iterations, flushed once at the end), `_carried_resolution`
  / `applied_fingerprints`, `run_logger` phase bracketing, `WalkState`, and
  `saved.recommendations`'s in-place narrowing (order-sensitive — the walker
  persists annotations keyed by `rec.id`).

## Out of scope

- `completeness_phases.py` physically moving out of `plan_tool/cli/` to sit beside
  `completeness_report.py` as a first-class top-level orchestrator. It already
  functions as the landing spot for this command's logic regardless of its own
  package location — it has 30+ top-level functions past line 2181 today, the
  same "orchestration logic filed under `cli/`" pattern this seed's target
  exhibits. Relocating the file is a separate, larger reorganization question;
  name it as a candidate follow-up in the plan's docs, do not act on it.
- `plan_tool/cli/run_cmd.py:cmd_run` (505 lines). Re-verified against current
  HEAD: it is not a CLI-layering violation like the two functions above — every
  phase inside it needs `argparse.Namespace` access, terminal output, or
  exit-code mapping, and its one real execution step (`run_step`) is already
  correctly factored into `launcher.py`. Its size is a decompose-in-place
  problem, not a relocation problem, and belongs to a future, separate,
  much-lower-risk effort.
- Any change to what `completeness-audit --iterate` or `completeness-apply`
  actually check, apply, or report. This is a pure code-motion refactor.
- Restructuring `tests/cli/COVERAGE_BASELINE.md`'s format. Update its
  `cmd_completeness_apply` row only if its own convention requires an entry for
  the newly-named extracted functions.

## Allowed behavior changes

None. This is a structural extraction; observable behavior (terminal output,
return codes, files written, run-log contents) must be identical before and
after.

## Allowed reorganization

Move the two functions' bodies (and `cmd_completeness_apply`'s three chunks)
into `completeness_phases.py`, named and exported for `completeness_cmd.py` to
call. No other file may change shape. Do not fold `_run_iterate_convergence_loop`
and `cmd_completeness_apply`'s extracted logic into one shared function — they
serve different commands (`completeness-audit --iterate` vs. `completeness-apply`)
with different state contracts; keep them as separate named functions even where
they end up looking structurally similar.

## Risks

- `_run_iterate_convergence_loop` has no caller outside `completeness_cmd.py` in
  production code, but `tests/cli/test_completeness_cmd.py` calls it directly
  (not only through `cmd_completeness`) — its import path changes, and those call
  sites need updating to the new location, not rewritten to test something
  different.
- `cmd_completeness_apply`'s three chunks are threaded through by mutable,
  order-sensitive state (`WalkState`, `_carried_resolution`, `saved.recommendations`
  narrowed in place). Extracting them risks accidentally copying state instead of
  sharing a reference, or reordering a read/write that currently depends on being
  interleaved with the surrounding CLI code. Trace each piece of state named in
  "In scope" through the extraction and confirm the same object identity is
  threaded, not a copy.

## Testing

`tests/cli/test_completeness_cmd.py` already covers both functions (including
calling `_run_iterate_convergence_loop` directly); these tests are the primary
behavior-preservation proof and must pass with only import-path updates, no
assertion changes. Add unit-level characterization coverage for the three newly
named `cmd_completeness_apply` extraction targets only if doing so doesn't
require inventing new test infrastructure — exercising them through the existing
full-`cmd_completeness_apply` tests is sufficient to prove the refactor;
isolated unit tests are a nice-to-have, not a requirement.

## Acceptance criteria

- `_run_iterate_convergence_loop` and `cmd_completeness_apply`'s three logic
  chunks live in `completeness_phases.py`; `completeness_cmd.py`'s versions are
  thin callers.
- Full test suite green with no assertion changes beyond import-path updates in
  `tests/cli/test_completeness_cmd.py`.
- No CLI-facing behavior (flags, output, exit codes) changed.

## Deferred

`completeness_phases.py`'s own location in the `cli/` package, and `cmd_run`'s
internal decomposition, are named above as related findings but explicitly not
part of this seed's scope — file them separately if worth pursuing.
