> **Replaced**: this file has been superseded by `docs/implementation-plans/2-structural-remedy-convenience-arms.md`.
> Preserved here for history; do not edit.

# Plan seed: structural-remedy vocabulary — the remaining gated-mutation convenience arms

Builds BACKLOG **#70** ("Structural-remedy vocabulary: remaining convenience
arms"). The core vocabulary is **shipped** — the altitude × disposition model,
the `scope-out` executor, reconcile's re-ground finding, the merge/re-ground
auto-bridges, the dispatcher consolidation in `review_walk.py`, and the
completeness-apply split bridge. This plan finishes **three** small
gated-mutation convenience arms that sit on top of that shipped surface. It does
**not** build the fourth remaining arm (the code-reveals-a-split *detection*
producer) — that is a new detection with its own design and is deferred to a
sibling plan (see Out of scope).

Every arm here is **deterministic** (no `invoker=` seam — like `scope_out_step`
and `reground_bridge`, both halves are pure), so there is no backend to
neutralize; tests are unit tests over the executors/dispatchers plus a CLI
integration test per new flag.

## Shipped foundation each arm extends

- **scope-out executor** (`plan_tool/scope_out.py`): `scope_out_step` is the
  apply-or-recommend orchestrator; `compute_narrow`/`apply_narrow` do the
  drop-renumber + `depends_on` repair + detail migrate/archive (all-or-nothing
  with rollback); `render_carved_seed` renders the `create --from-existing`
  forward-seed. CLI: `plan-tool scope-out <name> --step N [--apply] [-y]`
  (`plan_tool/cli/scope_out_cmd.py`). **Single step only today.**
- **convergence diagnostic** (`plan_tool/convergence_diagnosis.py` +
  `cli/convergence_cmd.py`): `FORK_SCOPE_OUT` carries a single `step_focus`;
  a multi-region focus renders as **prose only** today.
- **structural walk dispatch** (`plan_tool/cli/review_actions.py` +
  `plan_tool/review_walk.py`): `_dispatch_merge_remedy` (→ `detail.merge_bridge`)
  and `_dispatch_reground_remedy` (→ `reground.reground_bridge`) are both gated
  by the **one shared** `--apply-structural` (with `--include-info`) flag, routed
  by directive kind (`MERGE_ACTION_MERGE` vs `MERGE_ACTION_REGROUND`).
- **re-ground bridge** (`plan_tool/reground.py`): `reground_bridge` does
  **mark-done only** — the `PENDING → DONE` re-baseline of a set of already-built
  steps. The human-authored `create --from-existing` re-baseline disposition is
  **unbuilt**.

## The three arms

### Arm 1 — Multi-step / multi-region carve

`scope-out` carves exactly one `--step N`. Extend it to carve a **contiguous
step range** (and let the `convergence` multi-region focus, which renders
prose-only today, actuate).

- CLI: add a range form to `plan-tool scope-out` (e.g. `--through M` alongside
  `--step N`, carving the inclusive `N..M` region), keeping single-step behavior
  the default. Reject non-contiguous / out-of-order ranges deterministically.
- Executor: generalize `compute_narrow`/`apply_narrow` from a single `carved_id`
  to an ordered id **set/range** — one seed for the whole carved region (reuse
  `render_carved_seed`'s done-context prose over the set), one atomic
  drop-renumber + `depends_on` repair covering all carved ids, and detail
  migrate/archive for each. Preserve the seed-first atomicity contract and the
  all-or-nothing rollback.
- Blocker/run-state semantics carry over per step in the region (a worked carved
  step is allowed, captured as done-context — never refused).
- convergence: when `FORK_SCOPE_OUT` resolves a multi-region focus, print the
  runnable range form and let `--apply-scope-out` actuate it.

### Arm 2 — Per-remedy `--merge` / `--reground` walk flags

Today one shared `--apply-structural` enables **all** structural remedies in the
review/reconcile walk. Add per-remedy opt-in flags so an operator can enable one
without the others:

- `--merge` enables only the `granularity-merge` **merge** dispatch; `--reground`
  enables only the re-ground dispatch. `--apply-structural` remains the
  enable-all shorthand (a superset; the per-remedy flags are a narrowing).
- Wire them through the existing `_dispatch_merge_remedy` /
  `_dispatch_reground_remedy` gates in `review_actions.py` — the per-remedy flag
  and `--apply-structural` are OR-ed for that remedy's `allow_*` gate; everything
  else (stale-directive guard, `--include-info`, confirm) is unchanged.
- Keep the recommend-only default when no relevant flag is set.

### Arm 3 — Re-ground `create --from-existing` re-baseline arm

`reground_bridge` currently only marks the already-built set `done`. Add the
**second disposition**: emit a human-authored `create --from-existing`
**re-baseline seed** for the flagged already-built steps (re-decompose from the
current code), the re-ground analog of scope-out's seed-first carve.

- Model on `scope_out.py`'s seed-first shape: render a forward-seed capturing the
  already-built steps as done-context prose (reuse the same done-context
  renderer scope-out/annotate use), so the next `create` re-plans from a clean
  baseline grounded in what shipped.
- Disposition selector: keep `mark-done` the default; the re-baseline arm is an
  explicit opt-in (a flag on the re-ground actuator / walk, mirroring `--apply`).
- Deterministic (no `invoker=`), seed-first atomicity, same apply-or-recommend
  gate order as `reground_bridge` today.

## Out of scope

- **Code-reveals-a-split detection producer** — the fourth remaining #70 arm (a
  reconcile finding that reveals a step which *must* split). It is a new
  detection with its own design and belongs in a **sibling plan**; do not build a
  producer here. Leave it listed as remaining in #70.
- **Re-architecting the shipped executors/bridges** — these arms *extend*
  `scope_out.py` / `review_actions.py` / `reground.py`; they do not restructure
  them. The dispatcher consolidation (`review_walk.py`) is already shipped —
  reuse it, don't refactor it.

## Backlog reconciliation (carry forward — required)

This plan is derived from **BACKLOG #70**. Its final docs/status step must update
`BACKLOG.md`'s #70 entry when the work ships: move these three arms from
"Remaining (convenience)" to shipped (name them, with the plan slug and the new
CLI flags), and **keep the code-reveals-a-split producer listed as the one
remaining #70 arm**. Do not delete #70 (it still has the deferred producer arm).
Update the acceptance criteria and the final step to include this bookkeeping.

## Acceptance criteria (high level; the plan refines these)

- `plan-tool scope-out <name> --step N --through M --apply` carves the contiguous
  `N..M` region into one forward-seed and narrows the plan atomically (rollback
  on any failure); single-`--step` behavior is unchanged.
- `plan-tool convergence <name> --apply-scope-out` actuates a multi-region
  `FORK_SCOPE_OUT` focus via the range carve.
- `--merge` and `--reground` each enable only their own remedy in the walk;
  `--apply-structural` still enables all; recommend-only remains the default.
- The re-ground actuator can, under an explicit opt-in, emit a
  `create --from-existing` re-baseline seed for the flagged already-built steps
  instead of (or in addition to) marking them done; mark-done stays the default.
- All arms are deterministic (no backend spawn); unit + CLI-integration tests
  cover each, including the deterministic refusal paths.
- `BACKLOG.md` #70 is reconciled: the three arms marked shipped, the
  code-reveals-a-split producer left as the remaining arm.
