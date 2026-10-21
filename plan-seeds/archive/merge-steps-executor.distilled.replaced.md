> **Replaced**: this file has been superseded by `docs/implementation-plans/2-merge-steps-executor.md`.
> Preserved here for history; do not edit.

## Overview

Build a **merge executor** — the structural inverse of the split engine — that folds a contiguous set of plan steps into one. Adds `_apply_step_merge` (a pure transform beside `_apply_step_split` in `create.py`), a `merge_steps` orchestrator beside `split_step` in `detail.py`, and a `plan-tool merge` CLI command beside `split` in `cli/authoring.py`. Reuses split's discipline invariant-for-invariant so the two operations are symmetric. This is the **executor only**: the decision of whether to merge comes from the granularity advisor (`step-granularity-advisor.md`), which emits `granularity-merge` findings — this gives those findings something to act on, mirroring how `escalate-structural-findings-to-split.md` executes `granularity-split`.

## Problem statement

Splitting a step has a full engine; merging two has nothing. A plan can be over-decomposed — a trivial refactor step feeding one feature step, or two adjacent steps touching the same files — and today there is no way to fold them back. This seed builds the missing structural inverse so an over-decomposed plan can be recombined.

## Architecture

**Mirror the split engine, invariant for invariant.** Split's pure transform `create._apply_step_split` (`create.py:3193`) splices replacements in for one step, renumbers to contiguous `1..N`, and rewires edges. The merge transform `_apply_step_merge` is its inverse, folding a **contiguous set** of step ids into one:

| Split (`_apply_step_split`) | Merge (`_apply_step_merge`) |
| --- | --- |
| 1 step → N replacements | N steps → 1 merged step |
| Ids stay contiguous `1..N` | Ids stay contiguous `1..N` |
| First replacement inherits target's `depends_on` | Merged step's `depends_on` = **union of the set's external deps**, remapped; edges *internal* to the set drop |
| Replacements chain refactor→feature | (no internal chain — they collapse) |
| Dependents of target repoint to the *terminal* replacement | Dependents of **any** merged step repoint to the single merged id |
| Edges after insertion shift **down** by `len-1` | Edges after the region shift **up** by `len-1` |
| Validated by constructing a dry-run `Plan`; raises `CreateError`, never mutates input | Same — pure list→list, dry-run `Plan` validation, raises on cycle/dangling |

Constraint: require the merged set to be **contiguous ids that form a dependency chain** (so the collapse is unambiguous and can't create a cycle). Reject non-adjacent or fork/join sets with a clear `CreateError` rather than guessing.

**Safety gate — `_merge_is_safe`.** Mirror `detail._split_is_safe`: refuse to merge if **any** step in the set has already run or started — you must not restructure completed work. (Split guards on downstream-started; merge guards on the merged set itself, since the merge rewrites those very steps.) Honors the non-PENDING run-state gate already established for split.

**Detail-file handling (the asymmetry to get right).** Split *creates and authors* new detail files; merge must *combine* them: concatenate the seven-section bodies of the merged steps and re-author/re-audit the result into a single valid detail file (reuse the `detail` authoring + seven-section gate) — don't naively staple, the merged step needs one coherent Implementation/Tests/etc. Steps after the merged region renumber (shift **up** by `len-1`); rename their detail files via the mirror of `detail._migrate_downstream_details_after_split`. Remove the now-vanished detail files for the folded-away ids.

**CLI — `plan-tool merge`.** Mirror `cmd_split` (`cli/authoring.py:1359`) and register beside `split`:

```
plan-tool merge <name> --steps 3 --steps 4 [--title "Merged title"] \
    [--no-detail] [--no-completeness] [--iterate] [--dry-run]
```

`--steps` repeated (≥2 ids), validate contiguity + chain before any I/O; `--title` optional (default = derive from the merged set's titles). Like `cmd_split`: renumber + rewire, combine + re-author detail, then — unless `--no-detail` / `--no-completeness` — loop the conceptual completeness audit, applying blocking findings to convergence under `--iterate`. Offer `reconcile-plan` as the follow-up next-step (the merged step may describe unbuilt work; merge makes no plan-vs-code claim). Returns a `MergeResult` mirroring `SplitResult` (`detail.py`).

**Acyclic layering.** Put `_apply_step_merge` beside `_apply_step_split` in `create.py`; the `merge_steps` orchestrator beside `split_step` in `detail.py`; the command in `cli/authoring.py`. No new import cycles.

## Out of scope

- The *decision* of when to merge — that's the granularity advisor (`step-granularity-advisor.md`), which emits the `granularity-merge` findings this executor acts on.
- Auto-merging in the convergence loop unattended — recommend-only there, like split.
- Non-adjacent / fork-join merges — explicitly rejected with `CreateError`, not handled.

## Risks

- **Collapsing a set could create a dependency cycle or dangling edge.** Severity: correctness. Mitigation: `_apply_step_merge` validates by constructing a dry-run `Plan` and raises `CreateError` on a malformed graph, never mutating its input list.
- **Merging steps that have already run/started would restructure completed work.** Severity: data loss. Mitigation: `_merge_is_safe` (mirror of `detail._split_is_safe`, honoring the non-PENDING run-state gate) runs before any mutation; operator confirmation via `_confirm_merge` (mirror of `_confirm_split`) at a TTY.
- **Naively stapling N detail bodies yields an incoherent detail file.** Severity: quality. Mitigation: concatenate the seven-section bodies and re-author/re-audit through the `detail` authoring + seven-section gate so the merged step has one coherent Implementation/Tests/etc.
- **Ambiguous (non-adjacent or fork/join) merge sets.** Severity: correctness. Mitigation: reject with a clear `CreateError` rather than guessing the collapse.

## Acceptance criteria

- `plan-tool merge <name> --steps 3 --steps 4` folds the contiguous chain into a single step and renumbers remaining ids to contiguous `1..N`.
- `--steps` requires ≥2 ids; contiguity + chain are validated before any I/O.
- Merging a non-adjacent or fork/join set raises `CreateError` and mutates nothing.
- A merge whose set contains any non-PENDING (run/started) step is refused by `_merge_is_safe` before any mutation.
- `_apply_step_merge` is a pure list→list transform: it validates via a dry-run `Plan`, raises `CreateError` on cycle/dangling edge, and never mutates its input list.
- After merge, the merged step's `depends_on` equals the union of the set's external deps (remapped), internal edges drop, dependents of any merged step repoint to the single merged id, and edges after the region shift up by `len-1`.
- Detail files for folded-away ids are removed and downstream detail files are renamed via the mirror of `detail._migrate_downstream_details_after_split`.
- The combined detail file is re-authored/re-audited and passes the seven-section gate.
- `plan-tool merge` returns a `MergeResult` mirroring `SplitResult`.
- Unless `--no-detail` / `--no-completeness` is passed, the completeness audit loops and applies blocking findings to convergence under `--iterate`.
- The command's exit code reflects completion, not findings (exit-code convention).
- No new import cycles are introduced (`backend.py`/`create.py`/`detail.py`/`cli/authoring.py` layering stays acyclic).
- `docs/cli/` (drift-guarded) and the split-documented sections of `PLAN_FORMAT.md` / `RUNBOOK.md` are updated to cover `merge`.
