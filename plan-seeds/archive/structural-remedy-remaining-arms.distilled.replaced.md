> **Replaced**: this file has been superseded by `docs/implementation-plans/2-structural-remedy-convenience-arms.md`.
> Preserved here for history; do not edit.

## Overview

This plan finishes three small, deterministic gated-mutation convenience arms that sit on top of the already-shipped structural-remedy vocabulary (the altitude × disposition model, `scope_out_step`, reconcile's re-ground finding, the merge/re-ground auto-bridges, and the `review_walk.py` dispatcher consolidation). Arm 1 extends `scope-out` from a single `--step N` to a contiguous `N..M` range carve and lets the `convergence` multi-region focus actuate it; Arm 2 adds per-remedy `--merge` / `--reground` walk flags that narrow the current enable-all `--apply-structural`; Arm 3 adds a `create --from-existing` re-baseline disposition to `reground_bridge` alongside its existing mark-done. Every arm is deterministic (no `invoker=` seam, like `scope_out_step` and `reground_bridge`), so there is no backend to neutralize. When the work ships it must reconcile BACKLOG #70, marking these three arms shipped while leaving the code-reveals-a-split producer as the one remaining arm.

## Problem statement

BACKLOG #70's structural-remedy vocabulary is mostly shipped, but three convenience arms on top of it are missing. `scope-out` carves exactly one `--step N`, so an over-packed contiguous region must be carved step-by-step and the `convergence` `FORK_SCOPE_OUT` multi-region focus can only render as prose today instead of actuating. The review/reconcile walk exposes a single `--apply-structural` that enables all structural remedies at once, so an operator cannot opt into merge without also enabling re-ground (and vice versa). And `reground_bridge` only marks an already-built set `done` — the human-authored `create --from-existing` re-baseline disposition (re-decompose from current code) is unbuilt, so there is no seed-first analog to scope-out's carve on the re-ground side.

## Architecture

Each arm extends a shipped, deterministic executor/dispatcher without restructuring it.

Arm 1 generalizes `compute_narrow`/`apply_narrow` in `plan_tool/scope_out.py` from a single `carved_id` to an ordered id set/range: one forward-seed for the whole carved region (reusing `render_carved_seed`'s done-context prose over the set), one atomic drop-renumber + `depends_on` repair covering all carved ids, and detail migrate/archive for each, preserving the seed-first atomicity contract and all-or-nothing rollback. The CLI (`plan_tool/cli/scope_out_cmd.py`) gains a range form (e.g. `--through M` alongside `--step N`, carving the inclusive `N..M` region) with single-step as the default and deterministic rejection of non-contiguous / out-of-order ranges. Blocker/run-state semantics carry over per step in the region (a worked carved step is captured as done-context, never refused). `convergence` (`plan_tool/convergence_diagnosis.py` + `cli/convergence_cmd.py`) prints the runnable range form when `FORK_SCOPE_OUT` resolves a multi-region focus, and `--apply-scope-out` actuates it.

Arm 2 adds per-remedy opt-in flags wired through the existing `_dispatch_merge_remedy` / `_dispatch_reground_remedy` gates in `plan_tool/cli/review_actions.py`: `--merge` enables only the `granularity-merge` merge dispatch and `--reground` only the re-ground dispatch. The per-remedy flag and `--apply-structural` are OR-ed for that remedy's `allow_*` gate; `--apply-structural` remains the enable-all superset, and everything else (stale-directive guard, `--include-info`, confirm, recommend-only default) is unchanged.

Arm 3 adds a second disposition to `plan_tool/reground.py`'s `reground_bridge`: emit a human-authored `create --from-existing` re-baseline seed for the flagged already-built steps, modeled on `scope_out.py`'s seed-first shape and reusing the same done-context renderer scope-out/annotate use. A disposition selector keeps `mark-done` the default and makes the re-baseline arm an explicit opt-in flag on the re-ground actuator / walk (mirroring `--apply`), deterministic, seed-first, with the same apply-or-recommend gate order as today.

## Out of scope

- **Code-reveals-a-split detection producer** — the fourth remaining #70 arm (a reconcile finding that reveals a step which must split) is a new detection with its own design and belongs in a sibling plan; do not build a producer here, and leave it listed as remaining in #70.
- **Re-architecting the shipped executors/bridges** — these arms extend `scope_out.py` / `review_actions.py` / `reground.py`; they do not restructure them. The `review_walk.py` dispatcher consolidation is already shipped — reuse it, don't refactor it.

## Testing

All arms are deterministic (no backend spawn), so tests are unit tests over the executors/dispatchers plus one CLI-integration test per new flag, including the deterministic refusal paths (non-contiguous / out-of-order ranges). Follow the project's unit-first convention (`tests/X.py` mirrors `plan_tool/X.py`), reserving `@pytest.mark.integration` for the CLI-entry-point exercises that drive `main([...])` for the new flags.

## Acceptance criteria

- `plan-tool scope-out <name> --step N --through M --apply` carves the contiguous `N..M` region into one forward-seed and narrows the plan atomically (rollback on any failure); single-`--step` behavior is unchanged.
- `plan-tool convergence <name> --apply-scope-out` actuates a multi-region `FORK_SCOPE_OUT` focus via the range carve.
- `--merge` and `--reground` each enable only their own remedy in the walk; `--apply-structural` still enables all; recommend-only remains the default.
- The re-ground actuator can, under an explicit opt-in, emit a `create --from-existing` re-baseline seed for the flagged already-built steps instead of (or in addition to) marking them done; mark-done stays the default.
- All arms are deterministic (no backend spawn); unit + CLI-integration tests cover each, including the deterministic refusal paths.
- `BACKLOG.md` #70 is reconciled: the three arms marked shipped (named, with the plan slug and new CLI flags), the code-reveals-a-split producer left as the remaining arm, and #70 not deleted.
