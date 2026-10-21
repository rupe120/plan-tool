> **Auto-archived**: this plan was swept on 2026-06-24 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 2 — Emit a code-grounded re-ground finding (`granularity-merge`) on a ≥2-already-built-step set in the reconcile lane

## Summary

- Adds one **plan-wide re-ground finding** to `plan_tool/reconcile`'s output (`plan_tool/review.py`) that fires only when `heuristic_already_done` flags **≥2 distinct steps** as already-built in the code.
- The finding is sourced as **`granularity-merge`** (the literal reused from `plan_tool/granularity.py:GRANULARITY_MERGE_SOURCE`, not imported — the import would cycle), so it is non-apply-eligible and routes to the `triage_reason` non-apply-eligible branch (made producer-neutral merge/re-ground-aware here), never the split bridge.
- The emit is gated to the reconcile lane via a new keyword-only `reconcile_lane` flag on `review.py:extract_recommendations`; `review_plan_full` passes `reconcile_lane=True`, while the shared completeness/run-gate fan-out (`collect_deterministic_findings`) leaves the default `False` and already passes `heuristic_hits=[]`.
- The finding carries its **own re-ground/re-baseline remedy text** in `body` + `suggested_action`, and step 2 adds a `granularity-merge` arm to `triage_reason`, because the non-apply-eligible triage branch otherwise emits a concrete *wrong* remedy (`fix the path / run plan-tool detail / author lessons`) that misdirects the skip rollup away from re-baselining.
- On green: `plan-tool reconcile-plan` on a plan whose code already defines ≥2 distinct steps' title symbols surfaces one advisory `granularity-merge` recommendation (and tallies it in the `Findings:` banner) on top of the existing per-step `heuristic` hits; one already-built step keeps only the existing plain hit; the exit code stays 0.

## Table of Contents

- [Summary](#summary) — what the step adds and the green result
- [Why](#why) — the missing advisory home for reconcile's strongest code-centric signal
- [Files (creates vs edits)](#files-creates-vs-edits) — the two in-scope files, both edits
- [Implementation](#implementation) — the source constant, the re-ground builder, the `reconcile_lane` gate, the `triage_reason` merge/re-ground arm, the `review_plan_full` wiring
- [Tests](#tests) — builder, source-classification, gating, and reconcile-lane integration cases
- [Acceptance criteria](#acceptance-criteria) — checkable behaviors
- [References](#references) — the plan-level docs relevant to this step
- [Deferred](#deferred) — the actuating bridge and report-body rendering left out

## Why

- `reconcile` judges a plan **code-centrically**, and its strongest unique signal — that the code already implements multiple plan steps — currently has no advisory home. `review.py:heuristic_already_done` flags non-done steps whose files already define the symbols their titles imply, and `review.py:_heuristic_recommendation` emits one per-step `source="heuristic"` hint, but nothing reads across those hits to say "this whole set is already built; the plan's decomposition is stale — re-ground it." This step adds that cross-step finding.
- The remedy is **re-ground**, not blindly `merge`: `heuristic_already_done` can flag non-adjacent or non-`PENDING` steps, while `plan_tool/launcher.py:merge_steps` needs a contiguous all-`PENDING` run. The finding therefore recommends re-baselining the set (mark done / re-decompose), naming `merge` only as a conditional.
- This is **detection + recommendation only** (the plan's *always surface the more-correct plan* principle): the finding is advisory, non-apply-eligible, and never flips an exit code; the actuating bridge is explicitly out of scope.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/review.py` — add the `_GRANULARITY_MERGE_SOURCE` literal beside `STRUCTURAL_SOURCES`; add the `_reground_already_built_recommendation` builder beside `_heuristic_recommendation`; add a keyword-only `reconcile_lane: bool = False` parameter to `extract_recommendations` plus the gated plan-wide emit; add a producer-neutral `granularity-merge` merge/re-ground arm to `triage_reason`; pass `reconcile_lane=True` from `review_plan_full`'s `extract_recommendations` call.
  - `tests/test_review.py` — add builder, source-classification, gating, and reconcile-lane integration cases; extend the import block with the new symbols and the `granularity` literal.

## Implementation

### `plan_tool/review.py`

**Foundational logic of this step:** a deterministic cross-step predicate — *count distinct already-built `step_id`s among the heuristic hits; when ≥2, emit one plan-wide `granularity-merge` re-ground finding* — gated to the reconcile lane. This rule is new and unique to this module; no other file reads `heuristic_already_done` hits as a set or emits a `granularity-merge` finding. The deterministic `granularity-merge` detectors in `plan_tool/granularity.py` (`_merge_signal_identical_file_sets`, `_merge_signal_trivial_refactor_feeding_one_feature`) read only plan structure and never touch code — this finding is the **code-grounded** sibling and shares only the source-token string with them, not the detectors.

- **Add the source-token constant** beside `STRUCTURAL_SOURCES`:
  - `_GRANULARITY_MERGE_SOURCE = "granularity-merge"`.
  - Comment it exactly like the `"granularity-split"` literal duplicated inside `STRUCTURAL_SOURCES`: the value is copied from `plan_tool/granularity.py:GRANULARITY_MERGE_SOURCE`, **not imported**, because `granularity` imports `review` (for `Recommendation` / `_make_rec_id`), so the reverse import would cycle. A test pins the two equal so a future rename is caught.
  - Do **not** add `_GRANULARITY_MERGE_SOURCE` to `STRUCTURAL_SOURCES` or `APPLY_ELIGIBLE_SOURCES`. Leaving it out of both is what makes `is_structural()` and `is_apply_eligible()` return `False`, so the finding takes the `if not is_apply_eligible(rec)` arm of `triage_reason` — which this step makes merge/re-ground-aware with producer-neutral wording (see the triage-branch edit below) so the skip rollup names the merge/re-baseline remedy instead of the generic path/detail/lessons misdirection. Adding it to `STRUCTURAL_SOURCES` would flip `is_structural()` True and route the apply walk through `_dispatch_structural_escalation → escalate_to_split` with a "split this step" message — the inverse of a re-baseline.

- **Add the builder** `_reground_already_built_recommendation(heuristic_hits, *, plan_name) -> Optional[Recommendation]` beside `_heuristic_recommendation`:
  - Compute `step_ids = sorted({hit.step_id for hit in heuristic_hits})` — **count distinct step ids, not raw hits**, because `heuristic_already_done` appends one `HeuristicHit` per (step, file) so a single step can produce several hits.
  - Return `None` when `len(step_ids) < 2`. One already-built step stays the existing plain per-step `heuristic` hit.
  - Build the id with `_make_rec_id(None, _GRANULARITY_MERGE_SOURCE, fingerprint)` where `fingerprint = "reground-already-built:" + ",".join(str(i) for i in step_ids)`. Deriving the fingerprint from the sorted distinct-step set keeps the id **stable** across re-runs on an unchanged set and **changes** it when the flagged set changes.
  - Use `step_id=None` — the finding is plan-wide (it spans a set of steps), matching the `step_id=None` convention `_path_style_recommendation` and `_claude_recommendations` already use for plan-wide findings.
  - Use `severity=_HEURISTIC_HIT_SEV` (`"info"`) — advisory, matching both the per-step heuristic family it is derived from and `granularity.py`'s `_GRANULARITY_SEV` for `granularity-merge` recs. `"info"` also means the interactive walk skips it by default (`skip_info`), consistent with the per-step hits.
  - **Carry the re-ground remedy in the finding's own message** (the non-apply-eligible triage branch otherwise emits a wrong, misdirecting remedy — see the triage-branch edit below):
    - `title` — name the count and the action, e.g. `f"Re-ground: steps {…} appear already-built in code — re-baseline the plan against HEAD"`.
    - `body` — state that ≥2 distinct steps (list the ids) have title symbols already present in their files per `heuristic_already_done`, so the plan's decomposition is stale relative to the code; note this is a low-confidence heuristic that can false-positive on superficial symbol overlap (per the plan's Risks), so confirm before re-baselining.
    - `suggested_action` — the re-ground remedy: mark the already-built steps `done` / re-baseline the set against HEAD; if (and only if) the flagged steps form a contiguous all-`PENDING` run, `plan-tool merge` them, otherwise re-decompose via `plan-tool create <slug> --from-existing <seed.md>`. Frame it as re-ground, not an unconditional merge.

- **Gate the emit to the reconcile lane** in `extract_recommendations`:
  - Add a keyword-only parameter `reconcile_lane: bool = False` (place it among the existing keyword-only params). The default `False` keeps every current caller unchanged, including `collect_deterministic_findings`, which already passes `heuristic_hits=[]`.
  - After the per-step correctness loop (section 2, the loop that emits `_heuristic_recommendation` per hit) and before the plan-wide completeness section, append:
    - emit only when `reconcile_lane and step_filter is None`, then call `_reground_already_built_recommendation(heuristic_hits, plan_name=plan_name)` and append a non-`None` result.
  - The `step_filter is None` guard mirrors section 3's plan-wide gate: a single-step reconcile (`--step N`) is scoped to one step, so a plan-wide ≥2-step finding must not fire there even though `review_plan_full` still hands the full hit list to `extract_recommendations`.
  - **Keep the docstring iteration-order list honest:** `extract_recommendations`' docstring enumerates the load-bearing walk order (`1. plan-wide correctness … 5. claude`). The new plan-wide reconcile-lane emit lands between section 2 (per-step correctness) and section 3 (plan-wide completeness), so add it to that numbered list (e.g. `2a. plan-wide re-ground (reconcile lane only)`) — leaving the docstring stale would mis-describe the walk order it documents.

- **Wire the reconcile lane** in `review_plan_full`:
  - Pass `reconcile_lane=True` to the `extract_recommendations` call inside `review_plan_full` (the one that already passes `heuristic_hits=hits`). This is the only call site that feeds real hits and is the reconcile-plan surface (`cli/review_cmd.py:cmd_review` and `bench.py` both reach reconcile through it).
  - Do **not** pass `reconcile_lane` anywhere else. `collect_deterministic_findings` (the create / detail / run-gate / completeness fan-out) keeps the default `False`, so the finding can never reach `apply_finding` or a non-reconcile report.
  - No change to `assemble_report`: `review_plan_full` already passes the `recommendations` list (now including the re-ground finding) to `assemble_report`, so `_render_severity_banner` tallies it in the `Findings:` histogram automatically.

- **Add a producer-neutral merge/re-ground-aware arm to `triage_reason`** (decision 3(c)): the non-apply-eligible branch currently returns `"{source}: structural diagnostic — not auto-fixable by an apply pass; resolve directly (fix the path / run plan-tool detail / author lessons)"` for *every* non-apply-eligible source, which is the **wrong** remedy for `granularity-merge` and misdirects the skip rollup away from merge/re-baseline decisions. Before that generic return, add a guard `if rec.source == _GRANULARITY_MERGE_SOURCE:` that returns a source-token-neutral reason covering both producers, e.g. `"granularity-merge: merge/re-ground advisory — inspect the finding; merge a contiguous all-PENDING run or re-baseline / mark done / re-decompose an already-built set"`. Key on `rec.source` only; do **not** touch `STRUCTURAL_SOURCES` / `APPLY_ELIGIBLE_SOURCES` / `is_structural` / `is_apply_eligible`, so the rec still reaches this branch unchanged. Because `granularity.py:_merge_rec` and reconcile's re-ground finding share this source, the triage text must not say `code already implements this set` unconditionally.

- **No edits to** `STRUCTURAL_SOURCES`, `APPLY_ELIGIBLE_SOURCES`, `AUDIT_FIX_SOURCES`, `is_structural`, `is_apply_eligible`, or `heuristic_already_done`. The finding rides the existing non-apply-eligible routing; only `triage_reason`'s message for the shared `granularity-merge` source changes to producer-neutral merge/re-ground wording. `heuristic_already_done` already supplies the hits.

## Tests

All cases live in `tests/test_review.py` (mirrors `plan_tool/review.py`). Extend the import block with `_reground_already_built_recommendation`, `_GRANULARITY_MERGE_SOURCE`, `is_apply_eligible`, `is_structural`, `APPLY_ELIGIBLE_SOURCES`, `STRUCTURAL_SOURCES`, and `from plan_tool.granularity import GRANULARITY_MERGE_SOURCE`.

### Test-creation order (feature step)

This is a **feature** step — new behavior. Add every test below **with** the implementation; all must be green before the step is done.

- **Builder — none below threshold:**
  - `test_reground_builder_returns_none_for_no_hits` — empty hit list → `None`.
  - `test_reground_builder_returns_none_for_single_step` — multiple `HeuristicHit`s but one distinct `step_id` → `None` (distinct-count, not raw-count).
- **Builder — fires at threshold:**
  - `test_reground_builder_emits_for_two_distinct_steps` — hits on steps 3 and 4 → a `Recommendation` with `source == "granularity-merge"`, `severity == "info"`, `step_id is None`, both step ids named in `body`, and a re-baseline/`merge`-if-contiguous `suggested_action`.
  - `test_reground_builder_counts_distinct_not_raw` — several hits per step across two steps still yields exactly one rec naming both steps.
- **Builder — id stability:**
  - `test_reground_id_stable_for_same_set` — same distinct-step set → identical `id` across two calls.
  - `test_reground_id_changes_when_set_changes` — adding a third already-built step changes the `id`.
- **Source classification / routing:**
  - `test_granularity_merge_not_apply_eligible` — `is_apply_eligible(rec)` is `False`; `_GRANULARITY_MERGE_SOURCE not in APPLY_ELIGIBLE_SOURCES`.
  - `test_granularity_merge_not_structural` — `is_structural(rec)` is `False`; `_GRANULARITY_MERGE_SOURCE not in STRUCTURAL_SOURCES`.
  - `test_granularity_merge_triage_reason_names_merge_or_reground` — `triage_reason(rec)` returns the producer-neutral merge/re-ground reason (names merge and re-baseline / mark done), not the `granularity-split` / `structural-split` split-bridge message and **not** the generic "fix the path / run plan-tool detail / author lessons" misdirection.
  - `test_granularity_merge_literal_matches_granularity_module` — `_GRANULARITY_MERGE_SOURCE == GRANULARITY_MERGE_SOURCE` (pins the duplicated literal against the cycle).
- **`extract_recommendations` gating:**
  - `test_extract_emits_reground_in_reconcile_lane` — `reconcile_lane=True`, `step_filter=None`, hits on ≥2 distinct steps → exactly one `granularity-merge` rec in the output.
  - `test_extract_omits_reground_by_default` — same hits, `reconcile_lane` unset (default `False`) → no `granularity-merge` rec (the completeness/run-gate path).
  - `test_extract_omits_reground_under_step_filter` — `reconcile_lane=True` but `step_filter` set → no `granularity-merge` rec.
  - `test_extract_omits_reground_for_single_already_built_step` — `reconcile_lane=True`, one distinct step → no `granularity-merge` rec (the plain heuristic hit still appears).
- **Reconcile-lane integration (`review_plan_full`, `invoker=None`):**
  - `test_review_plan_full_surfaces_reground_finding` — add a fixture (model on `_REVIEW_PLAN` / `_write_review_fixture`) with **two** pending, non-done steps whose on-disk files already define their title symbols, so `heuristic_already_done` flags both; assert `result.recommendations` contains one `granularity-merge` re-ground rec and the report's `Findings:` banner tally includes it.
  - `test_collect_deterministic_findings_omits_reground` — `collect_deterministic_findings` over the same fixture emits **no** `granularity-merge` rec (it passes `heuristic_hits=[]` and `reconcile_lane` defaults `False`).

**Green-before-done gate:** every test above must pass (`uv run pytest tests/test_review.py -q`) before the step is complete.

## Acceptance criteria

- `_reground_already_built_recommendation([], plan_name=…)` returns `None`; hits on one distinct step return `None`; hits on ≥2 distinct steps return a `Recommendation` with `source == "granularity-merge"`, `severity == "info"`, `step_id is None`.
- The returned rec's `id` is stable for an unchanged distinct-step set and differs when the set changes.
- `_GRANULARITY_MERGE_SOURCE == plan_tool.granularity.GRANULARITY_MERGE_SOURCE`, and the literal is in neither `APPLY_ELIGIBLE_SOURCES` nor `STRUCTURAL_SOURCES`; `is_apply_eligible` and `is_structural` are both `False` for the rec, and `triage_reason` returns a producer-neutral merge/re-ground reason (names merge and re-baseline, not the generic path/detail/lessons misdirection).
- `extract_recommendations(..., reconcile_lane=True, step_filter=None)` with ≥2 distinct already-built steps yields exactly one `granularity-merge` rec; the same call with `reconcile_lane=False`, with a non-`None` `step_filter`, or with one distinct step yields none.
- `review_plan_full` on a plan with ≥2 already-built non-done steps surfaces the re-ground finding in `result.recommendations` and tallies it in the report banner; `collect_deterministic_findings` over the same plan surfaces none.
- `plan-tool reconcile-plan` exits 0 in all cases (the finding never flips the exit code); `STRUCTURAL_SOURCES`, `APPLY_ELIGIBLE_SOURCES`, and `heuristic_already_done` are unchanged; `triage_reason` changes only by adding the producer-neutral `granularity-merge` merge/re-ground arm.

## References

- `plan_tool/review.py` — `heuristic_already_done` / `_heuristic_recommendation` (the code signal this builds on), `extract_recommendations`, `review_plan_full`, `STRUCTURAL_SOURCES` / `APPLY_ELIGIBLE_SOURCES` / `triage_reason` (the non-apply-eligible routing the finding rides, with a new producer-neutral merge/re-ground arm), `_make_rec_id` (stable-id helper).
- `plan_tool/granularity.py` — `GRANULARITY_MERGE_SOURCE` (the literal reused here) and its deterministic plan-structure-only merge detectors (the structure-grounded sibling, not reused); both excluded from `APPLY_ELIGIBLE_SOURCES`.
- `BACKLOG.md` #67 (give `reconcile` a code-grounded structural-decomposition check) and #70 (model the structural remedies as one split/merge axis) — the advisory arms this step ships; trimmed to the advisory/actuator split in step 3.
- `MISSION.md` — the *always surface the more-correct plan* principle (detection unconditional, mutation gated) this finding obeys.

## Deferred

- **An automatic bridge from the re-ground finding to an actuating command** — kept recommend-only (operator hand-runs `plan-tool merge` on a contiguous all-`PENDING` run, or re-decomposes via `create --from-existing`), mirroring `granularity-merge`; a wired actuator may return in a follow-up plan.
- **A dedicated report-body section rendering the re-ground finding's prose** — left out; the finding surfaces via `result.recommendations` (walk + saved sidecar) and the `Findings:` severity banner, with no new `assemble_report` section. Adding one is a report-formatting change for a later step.
- **Reusing the literal by importing it from `granularity.py`** — blocked by the `granularity → review` import cycle; the duplicated literal plus its pin test is the standing pattern (same as `"granularity-split"` inside `STRUCTURAL_SOURCES`). Consolidating the two structural-remedy source literals into one shared, cycle-free home is a behavior-preserving refactor for reconcile.
