> **Auto-archived**: this plan was swept on 2026-07-08 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 2 — Stamp `target_signature` onto directive findings before they are saved

## Summary

Wires step 1's building blocks into the save path. Adds two helpers in `plan_tool/review_walk.py`: `directive_target_ids(rec)`, which returns the step ids a directive-carrying finding targets (or `None`), and `stamp_target_signatures(plan, recs)`, which walks a rec list and sets `target_signature` on every directive-carrying rec using step 1's `compute_target_signature`. It then calls the stamp pass right before each `save_review` in the five in-scope modules so a re-ground, pairwise-merge, or `granularity-split` MIXED-STEP finding lands on disk carrying the signature of its own target steps. The key decision: recover target ids through **one shared function** that steps 3 and 4's guards will reuse, so the ids hashed at stamp time and recomputed at guard time can never diverge. On green, a directive finding saved by `reconcile-plan` or the completeness lane carries a non-empty `target_signature`; every non-directive rec keeps `target_signature=None`.

## Table of Contents

- [Why](#why) — the guard needs a per-directive signal on disk before it can be precise
- [Input](#input) — what step 1 produces and the directive shapes this step reads
- [Files (creates vs edits)](#files-creates-vs-edits) — the two helpers plus the five save-site wirings
- [Implementation](#implementation) — the recovery helper, the stamp pass, and the save-site calls
- [Tests](#tests) — helper and recovery unit cases in `tests/test_review_walk.py`
- [Acceptance criteria](#acceptance-criteria) — observable results on green
- [References](#references) — stdlib docs for `replace` and the hash
- [Deferred](#deferred) — the guard rewrite, the split guard, and no-signal call sites

## Why

Step 3 rewrites the stale-directive guard (`_saved_directive_is_stale` in `plan_tool/cli/review_actions.py`) to compare each directive's own target steps instead of the whole plan — but it can only do that if the saved finding already carries the signature of the steps it targeted when it was computed. Nothing stamps that signature today. This step fills the gap: it runs a single post-audit stamp pass at every place a directive finding can be persisted, so the signature is on disk by the time a later walk reads it. Without this step the field added in step 1 stays `None` on every saved rec and the guard has nothing to compare, so it would keep falling back to the coarse whole-plan check the plan set out to replace.

## Input

- **Step 1 produces the field and the hash helper.** `Recommendation.target_signature: Optional[str] = None` (`plan_tool/review.py`, the frozen `Recommendation` dataclass) and `compute_target_signature(plan, target_ids) -> str` (`plan_tool/review_walk.py`). This step only sets the field and calls the helper; it does not redefine either.
- **Persistence round-trips the field for free.** `plan_tool/review_persistence.py` serializes recs with `asdict(r)` in both `save_review` and `update_annotation` and rebuilds with `Recommendation(**r)` in `load_review`, so a stamped signature survives save/load with no plumbing here. Do **not** edit `review_persistence.py` — step 1 already confirmed and documented this contract.
- **The three directive shapes this step reads:**
  - **Re-ground** — `review.py:_reground_already_built_recommendation`: `source="granularity-merge"`, `step_id=None`, target ids inside the `→ reground steps: …` marker, recovered by `review.parse_merge_action`.
  - **Pairwise merge** — `granularity.py:_merge_rec`: `source="granularity-merge"`, `step_id` set, target ids inside the `→ merge steps: …` marker (the gapped advisory carries no marker).
  - **`granularity-split` MIXED-STEP** — `granularity.py:parse_mixed_step_findings`: `source="granularity-split"`, `severity="medium"`, single `step_id`; its target set is `(rec.step_id,)`.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/review_walk.py` — add `directive_target_ids(rec) -> Optional[tuple[int, ...]]` and `stamp_target_signatures(plan, recs) -> list[Recommendation]`. Add `replace` to the existing `from dataclasses import …` line.
  - `plan_tool/cli/review_cmd.py` — in `cmd_review`, stamp `result.recommendations` against the freshly parsed `plan` before the `save_review` call (the site that persists `review_plan_full`'s recs — the one lane that emits re-ground / pairwise-merge findings today).
  - `plan_tool/cli/reconcile.py` — call the stamp pass before `save_review` in `_save_and_walk_reconcile`, `_save_and_walk_run_reconcile`, and the `_iterate_reconcile_loop` detail-reconcile save. Each already has the parsed `Plan` in scope (`plan` / `scope_plan`).
  - `plan_tool/cli/review_actions.py` — the `save_review` in `_dispatch_detail_reconcile` (≈250, the interactive walk's dispatched detail-reconcile save). Its recs are `source="detail-reconcile"` (no directive → `directive_target_ids` returns `None` → stamp is a **no-op today**), but wire it anyway for the **same future-proofing rationale as the reconcile-lane sites**: any future producer that emits a directive into this lane gets stamped automatically instead of silently saving an unstamped directive that then hits the coarse-fallback over-fire. This is the 7th and final `save_review` site — with it, all directive-carrying save paths stamp uniformly.
  - `plan_tool/completeness_report.py` — in `write_completeness_report`, stamp `recommendations` before the `save_review` call (this is the site that persists the `medium` `granularity-split` rec that rides `smell_recs` into the sidecar).
  - `plan_tool/auto_reconcile.py` — call the stamp pass before `save_review` in `run_auto_reconcile_on_drift`, using the already-parsed `_parsed_plan`.
  - `tests/test_review_walk.py` — unit tests for both new helpers.

## Implementation

**Add one shared target-id recovery — `directive_target_ids(rec)`.**
- Return the ordered step ids a directive-carrying rec targets, or `None` when the rec carries no directive.
- Recover in this order:
  - Merge / re-ground: if `merge_remedy_target(rec)` (the existing wrapper over `review.parse_merge_action`) returns a `MergeAction`, return its `.step_ids`. This covers both the re-ground finding (`step_id=None`) and the contiguous pairwise merge.
  - Split: else if `rec.source == GRANULARITY_SPLIT_SOURCE` and `rec.severity == "medium"` and `rec.step_id is not None`, return `(rec.step_id,)`.
  - Otherwise return `None`.
- **Why a shared recovery, not inline logic:** steps 3 and 4's guards must recompute the signature over the *same* ids this step hashed. If the stamp and the guard each recover ids their own way they can drift, and equality silently breaks. Putting the recovery in one function both sides call removes that risk. `review_walk.py` is the right home — it already holds `merge_remedy_target` / `split_escalation_target`, and `plan_tool/cli/review_actions.py` (steps 3/4) already imports `review_walk`, so the guard can call it without a new import edge. Naming the function so steps 3/4 reuse it is the point; **do not** re-derive ids in the guard.
- **Do not gate on `extra_apply_sources` here.** `split_escalation_target` folds in the caller opt-in because it decides *dispatch*; `directive_target_ids` answers a different question — "what does this directive target" — which is dispatch-independent. Key on `source` + `severity` + `step_id` only, so a `medium` split is always stampable regardless of which lane saved it.
- **Mirror the guard's precision — stamp only what a guard recomputes.** Step 3 guards merge / re-ground; step 4 guards the `medium` split. So skip the `info` deterministic split recs and the gapped merge advisory (no marker → `parse_merge_action` returns `None`). Stamping them would be harmless but pointless — no guard ever reads their signature.

**Add the stamp pass — `stamp_target_signatures(plan, recs)`.**
- Return a **new list**: `Recommendation` is a frozen dataclass, so build stamped recs with `dataclasses.replace(rec, target_signature=compute_target_signature(plan, ids))`.
- For each rec: `ids = directive_target_ids(rec)`; if `ids` is not `None`, append the replaced rec; else append the original rec unchanged (same object). Non-directive recs pass through untouched.
- Keep it a pure function of `(plan, recs)` — no I/O, no invoker, no Claude. It only reshapes a list, so it needs no seam and stays a cheap leaf beside `compute_target_signature`.
- **The ids must reach `compute_target_signature` in the form step 1 canonicalizes.** Step 1's helper sorts and dedupes its `target_ids` before hashing, and `parse_merge_action` already returns sorted ids, so pass the recovered tuple straight through — do not re-sort or re-shape it here, or you risk a subtle mismatch with the guard.

**Wire the stamp pass at each save site.**
- At every `save_review` call in the in-scope modules, replace the recs argument with `stamp_target_signatures(plan, recs)` (or assign to a local first for readability). Each site already parses or holds the `Plan`:
  - `plan_tool/cli/review_cmd.py:cmd_review` — the block that parses `plan = parse_plan(path)` right before `save_review`; stamp `result.recommendations` there. This is the site that matters most today; it is the only lane that emits re-ground and pairwise-merge findings.
  - `plan_tool/cli/reconcile.py` — `_save_and_walk_reconcile` (has `plan = parse_plan(plan_path)`), `_save_and_walk_run_reconcile` (same), and the `_iterate_reconcile_loop` detail-reconcile save (reuse the already-parsed `scope_plan`).
  - `plan_tool/completeness_report.py:write_completeness_report` — parse the plan from the `plan_path` param (the module already imports `parse_plan`) inside the `if recommendations is not None:` branch, stamp, then pass the stamped list to `save_review`.
  - `plan_tool/auto_reconcile.py:run_auto_reconcile_on_drift` — reuse `_parsed_plan`; but `_parsed_plan` is assigned only inside the `try`, so on a `ParseError`/`ValidationError` it is *unbound*, not merely unset — a naive `if _parsed_plan is not None:` guard would raise `UnboundLocalError` and break the best-effort contract. Initialize `_parsed_plan = None` before the `try` (or track availability with a separate flag), then guard the stamp on the plan being available and fall back to the unstamped recs rather than raising.
- **The reconcile-lane and auto-reconcile sites are no-ops today** — their recs come from `extract_reconcile_recommendations` / `extract_run_reconcile_recommendations` (`source` = reconcile / detail-reconcile / run-reconcile), which carry no directive marker, so `directive_target_ids` returns `None` for all of them. Wire them anyway so the "stamp before save" rule holds uniformly: any future producer that emits a directive into these lanes gets stamped automatically instead of silently saving an unstamped directive. Say this in the code with a one-line comment; don't leave a reader wondering why a no-op call is there.
- **Stamp into a local; don't try to mutate `result`.** `review_plan_full`'s result object may itself be frozen, and the stamp returns new rec objects regardless. Feed the stamped list to `save_review`'s `recommendations=` argument and leave the source list alone.

## Tests

All new tests live in `tests/test_review_walk.py`. Build a small `Plan` the way `tests/test_granularity.py:_plan` does (construct `schema.Plan` with a few `schema.Step`s); reuse or extend the existing `_rec` factory for directive-shaped recs. Stub nothing — these helpers are pure and never touch a backend.

### Test-creation order (feature step)

This is a **feature** step. Add these unit tests with the implementation; every one must be green before the step is done.

- `test_directive_target_ids_reground` — a re-ground rec (`granularity-merge`, `→ reground steps: 3, 4`, `step_id=None`) recovers `(3, 4)`.
- `test_directive_target_ids_pairwise_merge` — a contiguous merge rec (`granularity-merge`, `→ merge steps: 2, 3`, `step_id` set) recovers `(2, 3)`.
- `test_directive_target_ids_medium_split` — a `medium` `granularity-split` rec with `step_id=5` recovers `(5,)`.
- `test_directive_target_ids_none_for_non_directive` — a `deps` / `file-check` / `claude` rec recovers `None`.
- `test_directive_target_ids_none_for_info_split` — an `info` `granularity-split` rec recovers `None` (severity gate holds).
- `test_directive_target_ids_none_for_gapped_merge_advisory` — a `granularity-merge` rec with no marker recovers `None`.
- `test_stamp_sets_signature_on_each_directive_shape` — stamping a list with a re-ground, a pairwise merge, and a `medium` split sets each rec's `target_signature` to `compute_target_signature(plan, ids)` for that rec's ids.
- `test_stamp_leaves_non_directive_recs_unchanged` — a non-directive rec comes back with `target_signature=None` and as the same object (identity check).
- `test_stamp_returns_new_recs_and_does_not_mutate_input` — the input recs still have `target_signature=None` after stamping (frozen-dataclass / `replace` behavior).
- `test_stamped_signature_recomputes_equal_when_titles_unchanged` — stamp, then recompute `compute_target_signature(same_plan, ids)`; equal (the guard's "not stale" path).
- `test_stamped_signature_recomputes_unequal_after_target_title_change` — change a target step's title, recompute; not equal (the guard's "stale" path this step enables).
- `test_stamp_survives_save_and_load` — a stamped rec written by `save_review` and read by `load_review` keeps its `target_signature` (a light confirmation; the persistence contract itself is step 1's).

The save-site wiring is exercised end-to-end by steps 3 and 4's guard tests in `tests/cli/test_review_actions.py` (a stamped rec is exactly their input), so step 2 does not add CLI-level wiring tests.

## Acceptance criteria

- `directive_target_ids` returns the correct id tuple for re-ground, pairwise-merge, and `medium` `granularity-split` recs, and `None` for every other rec (non-directive, `info` split, gapped merge advisory).
- `stamp_target_signatures(plan, recs)` returns a list where each directive-carrying rec has `target_signature == compute_target_signature(plan, directive_target_ids(rec))` and every other rec is unchanged with `target_signature=None`.
- The input rec list is not mutated (frozen-dataclass `replace` semantics); non-directive recs are returned as the same objects.
- A directive finding saved by `plan-tool reconcile-plan` (re-ground / pairwise merge) and a `medium` `granularity-split` finding saved by the completeness lane both carry a non-empty `target_signature` on disk.
- Recomputing the signature over the same plan equals the stamped value; recomputing after a target step's title changes does not.
- All new tests in `tests/test_review_walk.py` pass; the existing `tests/test_review_walk.py` and `tests/test_data_contract.py` suites stay green.

## References

- [dataclasses — `replace()`](https://docs.python.org/3/library/dataclasses.html#dataclasses.replace) — building a new frozen `Recommendation` with `target_signature` set without mutating the original.
- `plan_tool/review_walk.py:compute_target_signature` — step 1's helper this step calls to hash each directive's ordered target ids; the stamp must not redefine it.
- `plan_tool/review.py:parse_merge_action` / `merge_remedy_target` — the directive-marker recovery `directive_target_ids` reuses to pull re-ground / pairwise-merge target ids.

## Deferred

- **The guard rewrite** (`_saved_directive_is_stale` in `plan_tool/cli/review_actions.py`) — step 3 reads the stamped signature and compares; this step only writes it. Step 3 reuses `directive_target_ids` to recover the same ids.
- **The `granularity-split` escalation guard** — step 4 adds the precise pre-dispatch check on the split path, also reusing `directive_target_ids`.
- **`convergence_cmd.py:classify_report_staleness`** — a separate, parallel staleness surface keyed on convergence-history `plan_fingerprint`; not the shared review-sidecar contract, left untouched (see the plan's Out-of-scope).
- **Call sites that pass no saved signal** (reconcile-lane builders, detail-reconcile sub-builder, `completeness_cmd`) keep their current "no signal → never gate" behavior; the stamp is wired but is a no-op there until a directive-emitting producer feeds those lanes.
- **`review_persistence.py` edits** — none needed; `asdict` / `Recommendation(**r)` round-trips the field, verified in step 1.
