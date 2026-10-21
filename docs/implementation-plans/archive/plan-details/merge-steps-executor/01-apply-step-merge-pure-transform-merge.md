> **Auto-archived**: this plan was swept on 2026-06-19 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 1 — Add `_apply_step_merge` pure transform + merge renumber map to `create.py`

## Summary

Add `_apply_step_merge(steps, merge_ids, merged)` to `plan_tool/create.py`, placed beside the existing `_apply_step_split`, as the structural inverse: it folds a contiguous, dependency-connected set of step ids into one merged step, renumbers the surviving steps to contiguous `1..N`, rewires every edge, and validates the result by constructing a dry-run `Plan` (raising `CreateError` on a malformed graph, never mutating its input). The load-bearing decision is to build an explicit `old_id → new_id` renumber `dict` from a single position-walk — not a positional closed-form like split's inline `remap` closure — because a merge set has multiple removal points that all collapse to one survivor id, which no single-pivot formula can express correctly. On green, calling `_apply_step_merge` on a clean contiguous chain returns a renumbered list whose merged step carries the union of the set's external `depends_on` (internal edges dropped), and a non-adjacent (gapped) or disjoint (unconnected) set raises `CreateError` with the input untouched — while an internally-branching but undirected-connected set (fork/join among members) is connected and collapses legally (run-state safety is not this transform's concern — it has no run-state knowledge; the non-PENDING run-state gate is step 2's `_merge_is_safe`). This step ships **only** the pure transform + its unit tests; the `merge_steps` orchestrator, `MergeResult`, detail-file combination/migration, and the CLI all land in later steps.

## Table of Contents

- [Why](#why) — what's missing and why the executor needs a transform first
- [Files (creates vs edits)](#files-creates-vs-edits) — the two files this step touches
- [Implementation](#implementation) — the `_apply_step_merge` transform, renumber map, and validation
- [Tests](#tests) — unit cases in `tests/test_create.py` and the green-before-done gate
- [Acceptance criteria](#acceptance-criteria) — checkable behaviors on green
- [References](#references) — stdlib/test docs relevant to this transform
- [Deferred](#deferred) — orchestrator, detail handling, CLI, and decision logic left to later steps

## Why

Splitting a step has a full engine (`create._apply_step_split` → `detail.split_step` → `cli/authoring.py:cmd_split`); merging has nothing. An over-decomposed plan — a trivial refactor step feeding one feature step, or two adjacent steps touching the same files — cannot be folded back. This step builds the lowest layer of the missing inverse: the pure list→list transform that does the structural folding and renumbering. Everything above it (the orchestrator, detail-file combination, the `plan-tool merge` command) depends on this transform existing and being correct first (steps 2–4, `depends_on: 1`). Keeping the transform pure and I/O-free — exactly as `_apply_step_split` is — means it is exhaustively unit-testable without a wizard, a TTY, or a Claude invoker.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/create.py` — add `_apply_step_merge` immediately after `_apply_step_split` (and after `_reproposal_is_skippable`). No other symbol changes; no new module-level imports (the dry-run `Plan` / `PydanticValidationError` / `CreateError` / `_summarize_step_graph_error` it reuses are already imported and defined in this module).
  - `tests/test_create.py` — add a `TestApplyStepMerge` class; extend the `from plan_tool.create import (...)` block that precedes `TestApplyStepSplit` (the one at line 9449, not the top-of-file block) to import `_apply_step_merge`, keeping it co-located with the sibling's import.

## Implementation

### `plan_tool/create.py` — `_apply_step_merge`

**Signature.** `def _apply_step_merge(steps: list[Step], merge_ids: list[int], merged: Step) -> list[Step]:`

- `steps` — the current full step list (ids already contiguous `1..N`, as plans maintain).
- `merge_ids` — the ids to fold together (≥2, contiguous, dependency-connected).
- `merged` — the caller-assembled combined `Step` (title, `files`, `creates`, `change_type`, `complexity`, etc.). The transform **sets only its `id` and `depends_on` deterministically** and inherits all other fields from this argument — the exact mirror of how `_apply_step_split` trusts the proposer for content but sets `depends_on` itself (`create.py` `_propose_step_split` docstring: "depends_on are *not* trusted here").

**Cite the sibling for shape only, re-derive the body.** `_apply_step_split` is the signature/validation-tail template (early `CreateError` on a bad target, position-walk renumber, `model_copy(update={"id":…, "depends_on":…})`, dry-run `Plan` construction wrapped in `try/except PydanticValidationError → CreateError(_summarize_step_graph_error(exc))`). The **logic** is re-derived: a merge collapses N nodes into one and can produce failure modes a split structurally cannot — duplicate inbound edges, dropped internal edges, and genuine cycles.

**Validation, in order (all raise `CreateError`, input never mutated):**

1. **≥2 ids.** `len(set(merge_ids)) < 2` → `CreateError("merge requires at least two step ids")`.
2. **All ids exist.** Any id in `merge_ids` not present in `{s.id for s in steps}` → `CreateError(f"merge target step {missing} not found")` (mirror split's not-found guard).
3. **Contiguous.** Let `lo, hi = min, max` of the set. Reject unless the sorted unique ids equal `list(range(lo, hi + 1))` → `CreateError("merge set must be a contiguous run of step ids (no gaps)")`. This is the "non-adjacent" rejection from the plan's Out-of-scope.
4. **Dependency-connected (the implementable reading of "form a dependency chain").** Treat the `depends_on` edges **among set members only** as **undirected** and require the set to be one connected component: BFS/DFS from `lo` over member-to-member edges (both directions), assert every member is reached, else `CreateError("merge set is not dependency-connected (disjoint) — cannot fold unambiguously")`. An internally-branching but connected set (fork/join among members) reaches every member and is accepted.
   - **Load-bearing decision — undirected connectivity, not directed "each depends on an earlier member".** The plan's "form a dependency chain" admits several predicates; the directed "every member depends on a lower member" reading would falsely reject a legal **reverse** edge (a lower-id member depending on a higher-id member within the set), which the collapse handles fine. Pick the soundest (undirected-connectivity) reading. A stricter true-chain / topological-linearity check is **Deferred**.

**Renumber map — explicit dict from one position-walk (not a closed-form closure):**

- Walk `steps` in order, assigning new ids `1..N`. The first time a member of `merge_ids` is encountered, allocate the survivor's new id (`merged_new_id`) and map **every** member to it; non-members get the next sequential id:
  ```
  renumber: dict[int, int] = {}
  next_id = 0
  merged_new_id: Optional[int] = None
  for s in steps:
      if s.id in merge_set:
          if merged_new_id is None:
              next_id += 1
              merged_new_id = next_id
          renumber[s.id] = merged_new_id
      else:
          next_id += 1
          renumber[s.id] = next_id
  ```
- **Why a dict, not a negated `remap` closure.** `_apply_step_split`'s inline `remap` (`old_id < target_id → same; == → terminal; > → +shift`) is valid only because a split inserts at **one** contiguous position with **one** uniform shift. A merge has several removal points that all fold to a single survivor id; no positional closed-form stays correct across them. The explicit `old→new` dict is the single source of truth and makes "every member maps to the survivor" directly expressible. Because the set is contiguous and ids start contiguous, this yields `merged_new_id == lo`, steps `< lo` unchanged, and steps `> hi` shifted **down by `eliminated = hi - lo`** (i.e. `len(set) - 1`).

**Build the rewired list:**

- Emit non-member steps via `s.model_copy(update={"id": renumber[s.id], "depends_on": _remap_external(s.depends_on)})`.
- Emit the single merged step **at the survivor's position** (the first member encountered) via `merged.model_copy(update={"id": merged_new_id, "depends_on": <merged external union>})`.
- `_remap_external(deps)` for a **non-member**: map each `d` through `renumber`, then **dedup preserving order** (`list(dict.fromkeys(...))`). Dedup is mandatory here and is the merge-only concern split never has: a step that depended on **two** members now has both edges collapse to `merged_new_id`, and `Plan._validate_graph` does not itself reject duplicate `depends_on` entries — leaving the dup is silent churn. (Dependents of **any** merged member therefore repoint to the one merged id.)
- **Merged step's `depends_on`:** union over **all members** of `{renumber[d] for d in member.depends_on if d not in merge_set}` — drop **internal** edges (a member depending on another member), remap and dedup the rest. `sorted(set(...))` or `dict.fromkeys` over the externals.

**Degenerate-output reasoning (guard only what the arithmetic doesn't preclude):**

- **Self-loop — no guard needed, prove it.** Internal edges (the only intra-set self-loop source) are dropped. For an external dep `d` on the merged step: `d < lo` ⇒ `renumber[d] = d < lo = merged_new_id`; `d > hi` ⇒ `renumber[d] = d - eliminated ≥ (hi+1) - (hi-lo) = lo+1 > merged_new_id`. So no external dep remaps to `merged_new_id`; a self-loop is structurally impossible. State this inline; add **no** self-loop guard.
- **Cycle / dangling — rely on the dry-run `Plan`, do NOT add a parallel graphlib check.** Unlike a split, a merge **can** close a cycle (e.g. an external step depends on one member while another member depends on that external step — folding makes `merged → X` and `X → merged`). Cycle and dangling-ref detection is already single-sourced in the `Plan` `model_validator` / `Plan._check_cycles` (`plan_tool/schema.py`). Construct the dry-run `Plan(title="dry-run", status=PlanStatus.PLANNING, priority=Priority.LOW, steps=rewired)` exactly as `_apply_step_split` does, catch `PydanticValidationError`, and raise `CreateError(f"merge produced an invalid step graph: {_summarize_step_graph_error(exc)}")`. The plan's References list `graphlib` (`TopologicalSorter`/`CycleError`) as *considered*; it is **rejected** — adding it would duplicate the validator the schema already owns.

**Purity / non-mutation.** Build a fresh `rewired: list[Step]` from `model_copy`; never mutate `steps` or any element in place, and never mutate `merged`. On any `CreateError` raised above, the caller's `steps` and `merged` are byte-identical to the inputs.

## Tests

All cases live in a new `class TestApplyStepMerge` in `tests/test_create.py`, driving `_apply_step_merge` directly with hand-built `Step`/`list[Step]` fixtures (no `create_plan`, no invoker, no TTY — the autouse `_disable_step3_todo_check` fixture is irrelevant to these). Use a small helper to build a contiguous chain of `Step`s with explicit `depends_on`.

- `test_folds_contiguous_chain_to_one` — merging `{2,3}` in a 4-step chain returns 3 steps with ids `1,2,3`, the merged step at id `2`.
- `test_renumbers_downstream_ids_down_by_eliminated` — steps after the region have ids decreased by `len(set)-1` (merge `{2,3}` ⇒ old step 4 becomes id 3).
- `test_merged_depends_on_is_external_union_internal_dropped` — merged step's `depends_on` is the remapped union of members' **external** deps; an edge between two members does not appear.
- `test_dependent_repoints_to_merged_id` — a step that depended on a merged member now depends on the single merged id.
- `test_collapsed_dependent_edges_deduped` — a step depending on **both** merged members has exactly one `depends_on` entry (the merged id) after the transform.
- `test_accepts_legal_reverse_intra_set_edge` — a lower-id member depending on a higher-id member within the set is connected and is accepted (guards the undirected-connectivity reading).
- `test_inherits_merged_step_content` — `merged`'s `title`/`files`/`creates`/`change_type` survive unchanged; only `id` and `depends_on` are set by the transform.
- `test_rejects_fewer_than_two_ids` — `merge_ids=[2]` raises `CreateError`.
- `test_rejects_unknown_id` — an id absent from `steps` raises `CreateError`.
- `test_rejects_non_contiguous_set` — `{2,4}` raises `CreateError` and the input list is unchanged.
- `test_rejects_fork_join_disjoint_set` — a contiguous-but-unconnected set raises `CreateError`.
- `test_raises_on_cycle_via_dry_run` — a set whose collapse closes a cycle raises `CreateError` (message threaded through `_summarize_step_graph_error`).
- `test_never_emits_self_loop` — the merged step's `depends_on` never contains its own id.
- `test_does_not_mutate_input_on_success` — `steps`/`merged` are unchanged (compare a pre-call deep snapshot) after a successful merge.
- `test_does_not_mutate_input_on_error` — same snapshot equality holds after a `CreateError` (non-contiguous case).

### Test-creation order (feature step)

This is a **feature** step (new behavior). Write each `TestApplyStepMerge` case **with** `_apply_step_merge` itself. Green-before-done gate: every new case above must pass (`uv run pytest tests/test_create.py::TestApplyStepMerge -q`) and the existing `tests/test_create.py` suite must stay green before this step is complete.

## Acceptance criteria

- `_apply_step_merge` exists in `plan_tool/create.py` immediately after `_apply_step_split`, with signature `(steps: list[Step], merge_ids: list[int], merged: Step) -> list[Step]`.
- Merging a contiguous, dependency-connected set returns a list with ids contiguous `1..N`, the merged step at the survivor (lowest) position.
- The merged step's `depends_on` equals the remapped, deduped union of the set's **external** deps; intra-set edges are dropped.
- Every step that depended on any merged member depends on the single merged id, with no duplicate edge.
- Ids after the merged region decrease by `len(set) - 1`.
- `merge_ids` with fewer than two ids, a non-contiguous set, a disjoint (unconnected) set, or an unknown id each raise `CreateError`; an internally-branching but connected set (fork/join among members) collapses legally.
- A set whose collapse would create a cycle or dangling edge raises `CreateError` sourced from the dry-run `Plan` validation (no `graphlib` is imported or used).
- The merged step never depends on itself.
- The input `steps` list and `merged` step are unmodified after both a successful call and a `CreateError`.
- `uv run pytest tests/test_create.py -q` is green, including the new `TestApplyStepMerge` class.

## References

- [graphlib — Python documentation](https://docs.python.org/3/library/graphlib.html) — Read to confirm what `_apply_step_merge` is *not* adding: cycle detection stays in `Plan._check_cycles`; `graphlib` is considered-but-rejected here to avoid a parallel validator.
- [dataclasses — Python documentation](https://docs.python.org/3/library/dataclasses.html) — Background for the pure list→list transform style; the `Step`/`Plan` models are Pydantic, but the immutability discipline (build new objects, never mutate inputs) is the same.
- [How to use temporary directories and files in tests — pytest](https://docs.pytest.org/en/stable/how-to/tmp_path.html) — The hermetic unit-test pattern the project relies on; these transform tests need no `tmp_path` (no I/O), but it documents the surrounding convention.

## Deferred

- `merge_steps` orchestrator, `_merge_is_safe`, `_confirm_merge`, `_migrate_downstream_details_after_merge`, and `MergeResult` — step 2 (`detail.py`), `depends_on: 1`.
- Combining/re-authoring the merged detail file through the seven-section gate and removing folded-away detail files — step 2.
- `plan-tool merge` CLI command + `--steps`/`--title` parsing and subparser registration — step 3 (`cli/authoring.py`).
- `PLAN_FORMAT.md` / `RUNBOOK.md` / `docs/cli` documentation — steps 3–4.
- A stricter true-chain (topological-linearity) merge predicate beyond undirected connectivity — left as a follow-up; the connectivity reading is sufficient for the cases the granularity advisor emits.
- Wiring `granularity-merge` findings to auto-invoke the executor — recommend-only, per the plan's Out-of-scope.
