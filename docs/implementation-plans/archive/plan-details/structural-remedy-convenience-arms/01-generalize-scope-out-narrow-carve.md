> **Auto-archived**: this plan was swept on 2026-07-09 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 1 — Generalize the scope-out narrow to carve an ordered set of step ids

## Summary

Widen the deterministic scope-out narrow in `plan_tool/scope_out.py` so `compute_narrow` / `apply_narrow` can drop an ordered set of carved step ids in one atomic transaction, not just a single id. The renumber shift map, `depends_on` repair, blocker detection, run-cursor recompute, feature prune, and the detail migrate/archive all generalize from "one dropped id" to "a set of dropped ids." The key design decision: keep the existing single-id entry points working byte-for-byte — `compute_narrow` still accepts `carved_id=N`, and `scope_out_step` is untouched — so every current caller (`split_criteria.py`, the CLI via `scope_out_step`, `convergence`) sees identical behavior. On green, carving a single id produces the same preview/result and on-disk outcome as today, and a new plural entry (`carved_ids`) can drop a multi-step region that step 2 will expose through the CLI.

## Table of Contents

- [Why](#why) — what this refactor unblocks and why it's behavior-preserving
- [Files (creates vs edits)](#files-creates-vs-edits) — the two in-scope files
- [Implementation](#implementation) — the set-based narrow, the back-compat entry, and the invariants that must hold
- [Tests](#tests) — characterization pins plus new multi-id coverage
- [Test-creation order (refactor step)](#test-creation-order-refactor-step) — pin single-id behavior first, keep it green after
- [Acceptance criteria](#acceptance-criteria) — checkable outcomes
- [References](#references) — pytest/os docs relevant to this step
- [Deferred](#deferred) — what this step intentionally leaves alone

## Why

`scope-out` today carves exactly one step. `compute_narrow` takes a scalar `carved_id`, and `NarrowPreview` / `NarrowResult` carry a scalar carved id and a single archived detail path. To carve a contiguous over-packed region (step 2's `--through` flag) or actuate a multi-region `FORK_SCOPE_OUT` (step 3), the narrow itself must be able to drop several ids at once and keep the plan graph correct: shift the survivors, repair every `depends_on` edge, migrate/archive every carved and shifted detail file, and roll all of it back on any failure. This step does that generalization at the narrow layer only. It is behavior-preserving because the single-id path stays the canonical special case — the CLI, `split_criteria.py`, and `convergence` keep carving one id and see no change — so step 2 can build the range form on a solid, already-generalized narrow.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/scope_out.py` — generalize `compute_narrow`, `apply_narrow`, `_blocked_preview`, and the two internal dataclasses (`NarrowPreview`, `NarrowResult`) from a scalar carved id to an ordered set; leave `scope_out_step`, `render_carved_seed`, and the seed helpers untouched.
  - `tests/test_scope_out.py` — add multi-id characterization/coverage tests; adapt the few existing tests that read the scalar archive fields to the new list shape (behavior asserted stays the same).

## Implementation

**Core behavior change: the narrow drops a set of ids, not one.** The foundational logic is the old→new id shift map (`old_to_new` in `compute_narrow`) and the `depends_on` repair that reads it. Generalize both from "shift down by one past a single `carved_id`" to "shift down by the count of carved ids below this id."

- **Keep a single source for the shift map.** Today `compute_narrow` builds one `old_to_new` map and reuses it for both the step renumber and the `depends_on` remap. Preserve that — for each survivor `s`, `new_id = s.id - (number of carved ids strictly less than s.id)`. For the single-id case this is exactly `s.id if s.id < carved else s.id - 1`. Do not derive the shift in two places.

- **Back-compat entry is the load-bearing constraint.** `compute_narrow` must keep accepting `carved_id: int` so `plan_tool/split_criteria.py` (its `compute_narrow(plan, carved_id=step.id, ...)` call, out of this step's scope) and every existing `carved_id=`-keyword test stay unchanged. One way: add `carved_ids: Sequence[int] | None = None` as the new canonical parameter and keep `carved_id: int | None = None`, require exactly one, and normalize to a sorted, de-duplicated list (a small `_normalize_carved_ids` helper). The alternative — renaming the parameter to `carved_ids` and updating `split_criteria.py`'s call — pulls an out-of-scope file into this step and breaks the "pass unchanged" gate for those tests, so prefer the back-compat form.

- **`scope_out_step` needs no edit.** It already calls `compute_narrow(plan, carved_id=carved_id, ...)`; with `carved_id` still accepted, it keeps carving one id. `ScopeOutResult.carved_id` stays a scalar `int` because `plan_tool/cli/scope_out_cmd.py` reads `result.carved_id`. Leave `render_carved_seed`, `_resolve_upstream_context`, `_resolve_carved_detail_path`, `_carved_seed_path`, and `_confirm_scope_out` alone — the region seed and the `scope_out_step` range form are step 2's job.

- **Generalize the two internal dataclasses to lists.** No external caller reads these fields, only in-scope tests:
  - `NarrowPreview.carved_id: int` → `carved_ids: list[int]`; `NarrowPreview.archive_detail: Path | None` → `archive_details: list[Path]` (one entry per carved id that had a detail file; empty when none did).
  - `NarrowResult.carved_id: int` → `carved_ids: list[int]`; `NarrowResult.archived: Path | None` → `archived: list[Path]`.
  - Keep `NarrowResult.renumber` and `NarrowResult.new_current_id` exactly as they are — `plan_tool/cli/scope_out_cmd.py` reads `result.narrow.renumber` and `result.narrow.new_current_id`.

- **Generalize the blocker detectors over the set** (`compute_narrow`'s blocker block and `_blocked_preview`). Each keeps its `NarrowBlocker.kind` string so downstream mapping (`_outcome_for_blockers`, step 3) is unchanged:
  - **step-missing** — any carved id not in the plan (list the missing ids in the message).
  - **non-canonical-numbering** — unchanged whole-plan check (`ids != canonical`).
  - **inbound-dependent** — a *kept* step whose `depends_on` names any carved id (a carved-on-carved edge is fine, both drop). `step_ids` = the offending kept ids.
  - **downstream-orphan** — a *kept* non-`PENDING` step that shifts, i.e. at least one carved id is below its id. For single-id this reduces to `s.id > carved_id and status != PENDING`.
  - **empty-plan** — no `COMMITTED` survivor remains after the drop (unchanged; keyed on committed survivors, not raw count).

- **`depends_on` repair over the set** — for each survivor, map every dep through `old_to_new` (a dep on a carved id is impossible here — that was the inbound-dependent blocker), drop the self-edge, and de-duplicate, exactly as today. It already works for any subset once `old_to_new` is the set-based map.

- **Cursor + status recompute barely change.** Re-establish the run cursor only when a carved step is the sole `CURRENT` one — generalize the trigger from "the carved step is CURRENT" to "any carved id's step is CURRENT" (schema guarantees ≤1 current, so at most one carved step is). The promotion rule (first `COMMITTED` `PENDING` survivor whose deps are all `DONE`), the top-level status recompute, and the feature-registry prune (`surviving_tags` from the new steps) are unchanged — they already key on survivors.

- **`apply_narrow` archives every carved detail and applies every rename under one journal.** Today it archives one `archive_detail` and, via `carved_is_rename_dest`, archives it *before* the downstream renames when its path is also a rename destination. Generalize the ordering to the set:
  - Split `preview.archive_details` into those whose path is a downstream rename destination (archive these **first**, freeing the slot) and the rest (archive **after** the renames).
  - Keep the existing rename order (ascending old id) and the `dst.exists()` collision refusal per rename, so each source frees its destination before the next move needs it.
  - The LIFO journal and `_rollback` already generalize — they just carry more `("rename", …)` / `("restore", …)` entries. Preserve the all-or-nothing guarantee: on any failure, roll back every op so disk is restored.
  - `apply_narrow`'s pre-flight refusals stay: non-empty `blockers`, `narrowed_plan is None`, and the stale-frontmatter-hash check via `compute_frontmatter_hash`.

- **Constraints that are not free to vary:**
  - The single-id path must stay behavior-identical — same `NarrowPreview` graph math, same on-disk narrowed plan, same archived file, same rollback.
  - `carved_id=` must remain a valid keyword on `compute_narrow`.
  - `ScopeOutResult.carved_id`, `NarrowResult.renumber`, and `NarrowResult.new_current_id` keep their names and types (read by `scope_out_cmd.py`).
  - The narrow accepts any subset of ids (contiguous or not) — do **not** add a contiguity check here; rejecting out-of-order ranges is step 2's CLI concern.
  - `NarrowPreview.narrowed_plan` stays the fully re-validated `Plan` (built via `plan.model_copy(...).model_dump()` → `Plan.model_validate`).

A sibling drop-renumber + `depends_on`-repair implementation lives in `plan_tool/detail.py` (`merge_steps`, which delegates to `_apply_step_merge` defined in `plan_tool/create.py`; an inline comment at this module's dep-repair loop already cites it for rename hygiene). It solves a different operation (merge, not carve), so consolidating the two into one shared renumber primitive is a separate refactor — out of scope here (see Deferred).

## Tests

All tests live in `tests/test_scope_out.py`. Existing single-id tests are the characterization pins; new tests cover the set generalization.

New multi-id preview-math tests:
- `test_multi_id_renumber_shifts_by_count_below` — carving `{2,3}` from a 5-step plan renumbers `4→2`, `5→3`.
- `test_multi_id_disjoint_carve_shifts_each_survivor_by_count_below` — carving the disjoint set `{2,4}` from a 5-step plan shifts survivor `3→2` (one carved id below) and `5→3` (two below), and repairs a kept `depends_on` edge through that same per-survivor map, locking the "any subset (contiguous or not)" contract.
- `test_multi_id_depends_on_remapped_across_gap` — a kept step depending on a kept step across the carved gap gets its `depends_on` remapped through the set-based shift map.
- `test_multi_id_carved_on_carved_edge_is_not_inbound` — a carved step depending on another carved step is not an inbound-dependent blocker.
- `test_multi_id_inbound_from_kept_step_is_blocker` — a kept step depending on a carved id blocks with `inbound-dependent`, listing the kept id.
- `test_multi_id_downstream_non_pending_is_blocker` — a shifted non-`PENDING` kept step blocks with `downstream-orphan`.
- `test_multi_id_step_missing_lists_all_absent` — a set containing an absent id blocks with `step-missing`.
- `test_multi_id_empty_plan_when_no_committed_survivor` — carving all committed steps blocks with `empty-plan`.
- `test_multi_id_cursor_reestablished_when_a_carved_step_is_current` — dropping a set that includes the sole `CURRENT` step promotes the first runnable committed pending survivor.
- `test_multi_id_preview_is_deterministic` — repeated calls on an unordered input set produce equal previews (ordered/de-duped).

New multi-id apply tests:
- `test_apply_multi_id_narrows_plan_on_disk` — carving `{2,3}` leaves the expected renumbered steps, titles, and repaired deps on disk.
- `test_apply_multi_id_archives_every_carved_detail` — each carved id's detail lands in `archive/`; `result.archived` lists all of them.
- `test_apply_multi_id_frees_carved_slots_before_downstream_renames` — a downstream detail renaming into a freed carved slot succeeds because the carved detail is archived first.
- `test_apply_multi_id_rolls_back_on_failure` — a mid-apply failure restores every carved detail, every rename, and the plan file.

Back-compat test:
- `test_compute_narrow_accepts_carved_id_keyword` — `carved_id=N` still returns a preview equal to `carved_ids=[N]`.

### Test-creation order (refactor step)

This is a **refactor** step (behavior-preserving for the single-id path). Write/confirm the characterization tests **first**, before touching `plan_tool/scope_out.py`, and keep them green and unmodified after:

- The single-id preview-math tests already in the file pin the current behavior and must pass unchanged: `test_renumber_shifts_only_downstream`, `test_non_canonical_numbering_is_a_blocker`, `test_depends_on_remapped_through_drop`, `test_inbound_dependent_is_a_blocker`, `test_downstream_non_pending_is_a_blocker`, `test_carving_only_survivor_is_empty_plan_blocker`, `test_missing_step_is_a_blocker`, the cursor/status tests, `test_narrow_prunes_unimplemented_feature_from_registry`, and `test_preview_is_deterministic`. None of these read a scalar carved-id or archive field, so they survive the field generalization untouched.
- The on-disk apply/rollback behavioral pins must also pass unchanged: `test_apply_narrows_plan_on_disk`, `test_apply_migrates_downstream_detail_files`, `test_apply_migrates_downstream_canonical_detail_without_pointer`, `test_apply_raises_and_rolls_back_on_downstream_detail_destination_collision`, `test_apply_refuses_when_blockers_present`, `test_apply_refuses_stale_preview_when_plan_frontmatter_changed`, `test_apply_rolls_back_on_failure`, and all the `scope_out_step` orchestrator tests — they assert disk state, not dataclass field shape.

Pass-unchanged gate: those behavioral characterization tests stay green, unmodified, after the restructuring. The only existing tests that change are the ones that read the scalar archive fields — `test_carved_detail_path_matches_narrow_archive` (reads `preview.archive_detail`), `test_apply_archives_carved_detail`, `test_apply_archives_carved_detail_before_downstream_rename_into_same_path`, `test_apply_archives_noncanonical_carved_detail_pointer`, and any that touch `result.archived`. These adapt to the list shape (e.g. `result.archived[0]`, `resolved in preview.archive_details`) while asserting the identical archive behavior — a mechanical field-access change, not a rewritten pin.

## Acceptance criteria

- `compute_narrow(plan, carved_ids=[2, 3], plan_path=..., repo_root=..., source_frontmatter_hash=...)` on a contiguous-numbered plan returns a `NarrowPreview` whose `renumber` shifts each survivor down by the count of carved ids below it and whose `depends_on` edges are repaired through that same map.
- `compute_narrow(plan, carved_id=2, ...)` still works and returns a preview equal to `carved_ids=[2]`.
- Carving a set that includes an id absent from the plan yields a `step-missing` blocker; a kept step depending on a carved id yields `inbound-dependent`; a shifted non-`PENDING` kept step yields `downstream-orphan`; no committed survivor yields `empty-plan`.
- `apply_narrow` on a valid multi-id preview archives every carved detail into `archive/`, migrates every shifted detail file, writes the narrowed plan, and — on any mid-apply failure — rolls back so the plan file and all detail files match their pre-narrow state.
- `NarrowResult.archived` is a `list[Path]` of the archived carved details; `NarrowResult.renumber` and `NarrowResult.new_current_id` keep their existing names and types.
- All existing behavioral characterization tests in `tests/test_scope_out.py` pass unchanged; `plan_tool/split_criteria.py` and `plan_tool/cli/scope_out_cmd.py` compile and behave identically for single-id carves.
- `uv run pytest tests/test_scope_out.py -q` passes.

## References

- `plan_tool/scope_out.py:compute_narrow` / `apply_narrow` — the single-id narrow this step generalizes to a set; the shift-map math, blocker block, and LIFO journal / rollback are the surfaces to widen.
- `plan_tool/scope_out.py:_blocked_preview` and `_archive_file_strict` — the blocker-preview constructor to generalize over the id set, and the archiver whose renames use `Path.rename()` (not `os.replace`), so extend the seed-first, all-or-nothing rollback around `Path.rename()` semantics.
- `plan_tool/detail.py:merge_steps` → `plan_tool/create.py:_apply_step_merge` — the sibling drop-renumber + `depends_on`-repair for the merge operation; the reference implementation to mirror for correctness and the consolidation target left deferred here.

## Deferred

- **CLI `--through` range form and `scope_out_step` range wiring** — exposing the multi-id narrow through the CLI, widening `scope_out_step`, and rendering one region seed via `render_carved_seed` is step 2's job; this step only generalizes the narrow.
- **Out-of-order range rejection** — the narrow accepts any subset; deterministically rejecting out-of-order ranges belongs to step 2's CLI parser (`--through` derives `range(N, M+1)`, so a non-contiguous region can't arise).
- **Consolidating drop-renumber with `plan_tool/detail.py`'s merge renumber** — `merge_steps` (in `detail.py`) and `_apply_step_merge` (in `plan_tool/create.py`) implement a parallel renumber+`depends_on`-repair for a different operation (merge); folding both into one shared primitive is a separate refactor, left for reconcile.
- **Multi-region seed prose** — reusing `render_carved_seed`'s done-context over a whole carved region (one seed for the set) is Arm 1's step-2 concern, since `scope_out_step` stays single-id here.
