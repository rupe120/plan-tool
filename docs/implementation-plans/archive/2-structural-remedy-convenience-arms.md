> **Auto-archived**: this plan was swept on 2026-07-09 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

---
title: Structural Remedy Convenience Arms
status: completed
priority: medium
enforce_step_tests: true
steps:
- id: 1
  title: Generalize the scope-out narrow to carve an ordered set of step ids instead
    of a single id
  files:
  - plan_tool/scope_out.py
  - tests/test_scope_out.py
  complexity: medium
  change_type: refactor
  detail: docs/implementation-plans/plan-details/structural-remedy-convenience-arms/01-generalize-scope-out-narrow-carve.md
  status: done
- id: 2
  title: Add a contiguous N..M range carve to scope-out with a --through flag
  files:
  - plan_tool/scope_out.py
  - plan_tool/cli/scope_out_cmd.py
  - docs/cli/scope-out.md
  - tests/test_scope_out.py
  creates:
  - tests/cli/test_scope_out_cmd.py
  complexity: high
  change_type: feature
  depends_on:
  - 1
  detail: docs/implementation-plans/plan-details/structural-remedy-convenience-arms/02-contiguous-range-carve-scope-out.md
  status: done
- id: 3
  title: Make convergence actuate a multi-region FORK_SCOPE_OUT as a range carve
  files:
  - plan_tool/convergence_diagnosis.py
  - plan_tool/cli/convergence_cmd.py
  - tests/test_convergence_diagnosis.py
  - tests/cli/test_convergence_cmd.py
  complexity: high
  change_type: feature
  depends_on:
  - 2
  detail: docs/implementation-plans/plan-details/structural-remedy-convenience-arms/03-make-convergence-actuate-multi-region.md
  status: done
- id: 4
  title: Add per-remedy --merge and --reground opt-in flags to the reconcile walk
  files:
  - plan_tool/cli/review_actions.py
  - plan_tool/cli/review_cmd.py
  - docs/cli/reconcile-plan.md
  - docs/cli/reconcile-plan-walk.md
  - tests/cli/test_review_actions.py
  complexity: medium
  change_type: feature
  detail: docs/implementation-plans/plan-details/structural-remedy-convenience-arms/04-per-remedy-merge-reground-opt-flags.md
  status: done
- id: 5
  title: Add a create --from-existing re-baseline disposition to reground_bridge
  files:
  - plan_tool/reground.py
  - tests/test_reground.py
  complexity: high
  change_type: feature
  detail: docs/implementation-plans/plan-details/structural-remedy-convenience-arms/05-create-existing-re-baseline-disposition.md
  status: done
- id: 6
  title: Wire the re-ground re-baseline disposition through the walk with an opt-in
    flag
  files:
  - plan_tool/cli/review_actions.py
  - plan_tool/cli/review_cmd.py
  - docs/cli/reconcile-plan.md
  - docs/cli/reconcile-plan-walk.md
  - tests/cli/test_review_actions.py
  complexity: medium
  change_type: feature
  depends_on:
  - 5
  detail: docs/implementation-plans/plan-details/structural-remedy-convenience-arms/06-wire-re-ground-re-baseline-disposition.md
  status: done
- id: 7
  title: 'Reconcile BACKLOG #70 and refresh the structural-remedy docs for the three
    shipped arms'
  files:
  - BACKLOG.md
  - CLAUDE.md
  - RUNBOOK.md
  complexity: medium
  change_type: non-code
  depends_on:
  - 2
  - 3
  - 4
  - 6
  detail: docs/implementation-plans/plan-details/structural-remedy-convenience-arms/07-reconcile-backlog-70-refresh-structural.md
  status: done
---
# Structural Remedy Convenience Arms

## Overview

This plan finishes three small, deterministic gated-mutation convenience arms that sit on top of the already-shipped structural-remedy vocabulary (the altitude × disposition model, `scope_out_step`, reconcile's re-ground finding, the merge/re-ground auto-bridges, and the `review_walk.py` dispatcher consolidation). Arm 1 extends `scope-out` from a single `--step N` to a contiguous `N..M` range carve and adds a range-carve `FORK_SCOPE_OUT` arm to `convergence` sitting between the single-step scope-out and the whole-plan `FORK_STRUCTURAL` re-seed a multi-region spin currently falls to; Arm 2 adds per-remedy `--merge` / `--reground` walk flags that narrow the current enable-all `--apply-structural`; Arm 3 adds a `create --from-existing` re-baseline disposition to `reground_bridge` alongside its existing mark-done. Every arm is deterministic (no `invoker=` seam, like `scope_out_step` and `reground_bridge`), so there is no backend to neutralize. When the work ships it reconciles BACKLOG #70, marking these three arms shipped while leaving the code-reveals-a-split producer as the one remaining arm.

## Problem statement

BACKLOG #70's structural-remedy vocabulary is mostly shipped, but three convenience arms on top of it are missing. `scope-out` carves exactly one `--step N`, so an over-packed contiguous region must be carved step-by-step, and `convergence` emits a `FORK_SCOPE_OUT` only when every recurring region resolves to one and the same step — a multi-region spin across several distinct steps falls straight to the whole-plan `FORK_STRUCTURAL` re-seed today, with no contiguous-range scope-out arm between them. The review/reconcile walk exposes a single `--apply-structural` that enables all structural remedies at once, so an operator cannot opt into merge without also enabling re-ground (and vice versa). And `reground_bridge` only marks an already-built set `done` — the human-authored `create --from-existing` re-baseline disposition (re-decompose from current code) is unbuilt, so there is no seed-first analog to scope-out's carve on the re-ground side.

## Architecture

Each arm extends a shipped, deterministic executor/dispatcher without restructuring it.

Arm 1 generalizes `compute_narrow`/`apply_narrow` in `plan_tool/scope_out.py` from a single `carved_id` to an ordered id set/range: one forward-seed for the whole carved region (rendered by a sibling region renderer that reuses the shared block helpers — `_scope_block` / `_done_context_block` / `_upstream_block` — over the set, not `render_carved_seed` itself, which stays the single-step path), one atomic drop-renumber + `depends_on` repair covering all carved ids, and detail migrate/archive for each, preserving the seed-first atomicity contract and all-or-nothing rollback. The CLI (`plan_tool/cli/scope_out_cmd.py`) gains a range form (e.g. `--through M` alongside `--step N`, carving the inclusive `N..M` region) with single-step as the default and deterministic rejection of out-of-order ranges (`M < N`). Blocker/run-state semantics carry over per step in the region (a worked carved step is captured as done-context, never refused). `convergence` (`plan_tool/convergence_diagnosis.py` + `cli/convergence_cmd.py`) prints the runnable range form when `FORK_SCOPE_OUT` resolves a multi-region focus, and `--apply-scope-out` actuates it.

Arm 2 adds per-remedy opt-in flags wired through the existing `_dispatch_merge_remedy` / `_dispatch_reground_remedy` gates in `plan_tool/cli/review_actions.py`: `--merge` enables only the `granularity-merge` merge dispatch and `--reground` only the re-ground dispatch. The per-remedy flag and `--apply-structural` are OR-ed for that remedy's `allow_*` gate; `--apply-structural` remains the enable-all superset, and everything else (stale-directive guard, `--include-info`, confirm, recommend-only default) is unchanged.

Arm 3 adds a second disposition to `plan_tool/reground.py`'s `reground_bridge`: emit a human-authored `create --from-existing` re-baseline seed for the flagged already-built steps, modeled on `scope_out.py`'s seed-first shape. `reground.py` is a leaf pinned to `locator`/`parser`/`schema`, and `scope_out.py:render_carved_seed` transitively imports `plan_tool.detail`, so re-ground cannot share that renderer — it writes a mirrored `render_rebaseline_seed` that reproduces the done-context seed vocabulary scope-out/annotate use, with `create --from-existing` round-trip consumability tests as the anti-divergence guard. A disposition selector keeps `mark-done` the default and makes the re-baseline arm an explicit opt-in flag on the re-ground actuator / walk (mirroring `--apply`), deterministic, seed-first, with the same apply-or-recommend gate order as today.

## References

- [argparse — Parser for command-line options, arguments and subcommands (Python 3 docs)](https://docs.python.org/3/library/argparse.html) — Official reference for adding the new `--through`, `--merge`, and `--reground` flags and wiring subparsers, needed when extending the scope-out/convergence/review-walk CLI surfaces.
- [How to mark test functions with attributes (pytest)](https://docs.pytest.org/en/stable/how-to/mark.html) — Documents `@pytest.mark.integration` and custom markers, which the plan requires to gate the CLI-entry-point integration tests apart from the unit-first suite.
- [How to use temporary directories and files in tests (pytest)](https://docs.pytest.org/en/stable/how-to/tmp_path.html) — Reference for the `tmp_path` fixture used to keep the executor/dispatcher tests hermetic when exercising seed-file writes and plan-narrow rollback.
- [os.replace — atomic file operations (Python 3 os module)](https://docs.python.org/3/library/os.html#os.replace) — Primary reference for atomic rename semantics an implementer needs to preserve the seed-first, all-or-nothing rollback contract in `compute_narrow`/`apply_narrow` and detail migrate/archive.
- [git-worktree — Manage multiple working trees](https://git-scm.com/docs/git-worktree) — Authoritative git reference for the worktree add/remove/prune primitives the tool provisions plans into, relevant to isolated deterministic mutation and clean-tree gating.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

- **Code-reveals-a-split detection producer** — the fourth remaining #70 arm (a reconcile finding that reveals a step which must split) is a new detection with its own design and belongs in a sibling plan; do not build a producer here, and leave it listed as remaining in #70.
- **Re-architecting the shipped executors/bridges** — these arms extend `scope_out.py` / `review_actions.py` / `reground.py`; they do not restructure them. The `review_walk.py` dispatcher consolidation is already shipped — reuse it, don't refactor it.

## Risks

- **Range-carve rollback is not atomic across the seed write, drop-renumber, and detail migrate/archive** — a mid-carve failure could leave a written seed with a partially-narrowed plan or orphaned detail files. High severity (corrupts a live plan). Mitigated by preserving `scope_out.py`'s seed-first, all-or-nothing rollback contract and extending it to cover every id in the region as one transaction; residual gap if a filesystem error strikes between the atomic rename and detail archive.
- **`depends_on` repair miscomputes across a multi-id carve** — dropping several steps at once can leave dangling or mis-renumbered `depends_on` edges if the repair is written for single-id removal. Medium severity. Mitigated by covering all carved ids in one repair pass and pinning step 1's characterization tests before the change; unresolved risk where a carved region straddles a step both depended on by and depending on kept steps.
- **Out-of-order `--through` ranges carve the wrong steps** — a permissive range parser could accept an `N..M` with `M < N`. Medium severity. Mitigated by deterministic rejection of out-of-order ranges with a clear error, covered by refusal-path tests.
- **Per-remedy `--merge` / `--reground` flags widen the mutation surface** — narrowing `--apply-structural` into independent opt-ins risks enabling a remedy while skipping its stale-directive guard. Low severity (gates unchanged). Mitigated by OR-ing each per-remedy flag with `--apply-structural` for that remedy's `allow_*` gate only and leaving the stale-directive guard, confirm, and recommend-only default intact.
- **Re-ground re-baseline seed diverges from scope-out's seed shape** — `reground.py`'s leaf import boundary forecloses sharing `scope_out.py`'s renderer, so its mirrored `render_rebaseline_seed` could drift and produce a `create --from-existing` seed the next `create` can't consume. Medium severity. Mitigated by mirroring the scope-out/annotate done-context seed vocabulary and pinning `create --from-existing` round-trip consumability tests as the anti-divergence guard, keeping `mark-done` the default with the re-baseline arm an explicit opt-in.
- **BACKLOG #70 reconciliation half-lands** — marking three arms shipped while mis-stating the remaining code-reveals-a-split arm would leave #70 internally inconsistent. Low severity. Mitigated by step 7's acceptance criterion requiring the three arms named with plan slug + CLI flags, the remaining arm left listed, and #70 not deleted.

## Testing

All arms are deterministic (no backend spawn), so tests are unit tests over the executors/dispatchers plus one CLI-integration test per new flag, including the deterministic refusal path (out-of-order ranges). Follow the project's unit-first convention (`tests/test_X.py` mirrors `plan_tool/X.py`), reserving `@pytest.mark.integration` for the CLI-entry-point exercises that drive `main([...])` for the new flags. Existing `scope_out.py`, `review_actions.py`, and `reground.py` suites must still pass unchanged for the single-step, enable-all, and mark-done default paths.

**Per-step test strategy** (derived from each step's `change_type`):

- step 1 (refactor) — characterization tests pinned before the change; pass unchanged after.
- step 2 (feature) — unit tests added with the implementation; green before completion.
- step 3 (feature) — unit tests added with the implementation; green before completion.
- step 4 (feature) — unit tests added with the implementation; green before completion.
- step 5 (feature) — unit tests added with the implementation; green before completion.
- step 6 (feature) — unit tests added with the implementation; green before completion.
- step 7 (non-code) — verification appropriate to the artifacts; no test-ordering directive.

## Acceptance criteria

- `plan-tool scope-out <name> --step N --through M --apply` carves the contiguous `N..M` region into one forward-seed and narrows the plan atomically (rollback on any failure); single-`--step` behavior is unchanged.
- `plan-tool convergence <name> --apply-scope-out` actuates a multi-region `FORK_SCOPE_OUT` focus via the range carve.
- `--merge` and `--reground` each enable only their own remedy in the walk; `--apply-structural` still enables all; recommend-only remains the default.
- The re-ground actuator can, under an explicit opt-in, emit a `create --from-existing` re-baseline seed for the flagged already-built steps in addition to marking them done; mark-done stays the default.
- All arms are deterministic (no backend spawn); unit + CLI-integration tests cover each, including the deterministic refusal paths.
- `BACKLOG.md` #70 is reconciled: the three arms marked shipped (named, with the plan slug and new CLI flags), the code-reveals-a-split producer left as the remaining arm, and #70 not deleted.

## Deferred

- **Disjoint (non-contiguous) region carve** — `compute_narrow`/`apply_narrow` generalize to an ordered id set, but the CLI and `convergence` actuate only the contiguous `N..M` case (`--through` derives its region as `range(N, M+1)`, so it is always contiguous); exposing a disjoint (non-contiguous) carve is deferred until a caller needs it.
- **Auto-selecting the re-ground re-baseline disposition** — Arm 3 keeps `mark-done` the default and makes re-baseline an explicit opt-in; letting convergence/reconcile signals choose the re-baseline disposition automatically is deferred (needs its own heuristic).
- **Seed-only re-ground re-baseline (skip mark-done)** — Arm 3 ships the "in addition to marking them done" reading only (mark-done always runs alongside the emitted seed); the seed-only variant that re-baselines *instead of* marking the flagged steps done is deferred.
