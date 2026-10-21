> **Auto-archived**: this plan was swept on 2026-07-04 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 4 — Add split-safety as two separate signals (split-safe and scope-out-blocked)

## Summary

Adds the split-safety run-state gate to `plan_tool/split_criteria.py`, the piece step 3 deliberately left out. Split-safety is surfaced as **two independent per-step signals** — `split-safe` (can this step be re-split in place right now?) and `scope-out-blocked` (would carving this step out at plan scope be refused right now?) — because they read different conditions and can disagree. Both reuse the actuators' own gates: `split-safe` reads `plan_tool/split_safety.py:split_is_safe`, `scope-out-blocked` reads `plan_tool/scope_out.py:compute_narrow`'s blocker list. The key decision: render these as a **run-state gate** ("splittable now?"), never with the fires? polarity — a step that can't be split because a started downstream step blocks it is a healthy default for an in-flight plan, not a decomposition defect. On green, `evaluate_split_criteria(...)` returns both signals per step in a separate gate field of the breakdown, the breakdown renderer prints them in their own "run-state gates" section, and the catalog carries two descriptors (`split-safe`, `scope-out-blocked`) in place of step 2's single `split-safety` entry.

## Table of Contents

- [Summary](#summary) — what the step adds and the observable result on green
- [Why](#why) — the run-state gate step 3 deferred, and why it is two signals
- [Files (creates vs edits)](#files-creates-vs-edits) — the two files this step edits
- [Implementation](#implementation) — the two signals, the deciders to reuse, the render polarity, and the cross-step reconcile
- [Tests](#tests) — unit tests in tests/test_split_criteria.py for both signals and the render wording
- [Acceptance criteria](#acceptance-criteria) — checkable behaviors on green
- [Deferred](#deferred) — telemetry/drift (step 5), CLI (step 6), and the deciders' own refactor

## Why

Step 3 lands the per-plan evaluator for the fires?-style criteria across all three altitudes but explicitly skips split-safety (`test_evaluate_omits_split_safety`), and step 2 ships a single placeholder `split-safety` catalog entry the legend describes but nothing evaluates. Split-safety is different in kind from every other criterion: it is not a shape defect that "fires," it is a **run-state gate** that answers "given where this plan is in its run, is a split available right now?" A developer reading a breakdown needs that answer to know which structural remedy they can actually reach today. It is two signals, not one, because a step-altitude re-split and a plan-scope scope-out check different graph conditions — a step with no started downstream work is split-safe, yet still scope-out-blocked if another step depends on it. Collapsing them into one gate would hide which remedy is open.

## Files (creates vs edits)

This step's frontmatter declares no `files:`. The two paths below are the files the whole feature is built in (step 2 creates them); step 4 extends them. No new file is introduced.

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/split_criteria.py`
    - Replace step 2's single `split-safety` catalog descriptor with **two** descriptors, `split-safe` and `scope-out-blocked` (both altitude 3, `deterministic=True`).
    - Extend `evaluate_split_criteria` to compute both signals per step and return them in a new gate field on `PlanCriteriaBreakdown`.
    - Add a small frozen gate record (suggest `SplitSafetyGate`).
    - Render the gates in `render_plan_breakdown` as a distinct run-state section.
    - Update `render_split_criteria` (the legend) so it names both signals where step 2 named one.
  - `tests/test_split_criteria.py` — add the gate tests below, and retarget the step 2/step 3 tests that assumed a single `split-safety` id and a deferred gate (named under Implementation).

## Implementation

**Foundational logic: compute per-step run-state split-safety as two independent read-only signals by reusing the actuators' own gates — write no new detection.** Same rule step 3 followed for the fires? criteria: orchestrate and map, never re-implement a predicate. Grep confirms the two deciders that own this logic:

- **`split-safe`** → `plan_tool/split_safety.py:split_is_safe(plan, target_id)`, which returns `(safe, blocking_ids)`. It flags every step whose id is `>= target_id` and whose `status` is not `PENDING` (a `DONE`/`CURRENT` step carries id-keyed run state a renumber would orphan). This is the same gate `plan_tool/launcher.py:escalate_to_split` consults (see its `EscalateResult` `outcome="unsafe"` arm).
- **`scope-out-blocked`** → `plan_tool/scope_out.py:compute_narrow(plan, *, carved_id, plan_path, repo_root, source_frontmatter_hash)`, whose `.blockers` list is non-empty when a carve would be refused. Its `NarrowBlocker.kind` values are `downstream-orphan`, `inbound-dependent`, `non-canonical-numbering`, `step-missing`, `empty-plan`. `compute_narrow` is pure (its docstring: no plan/detail mutation; the only filesystem touch is testing whether a detail file exists), so it is safe to call from a read-only diagnostic.

**Why two signals, concretely.** `split_is_safe` blocks on a non-`PENDING` step at or after the target. `compute_narrow` blocks on a non-`PENDING` step strictly *after* the carved step (`downstream-orphan`) **plus** any step that `depends_on` the carved step (`inbound-dependent`) **plus** non-canonical numbering. So a step can be `split-safe=True` and `scope-out-blocked=True` at the same time (it has an inbound dependent but no started downstream work). Keeping them separate is the whole point of the step — make the two tests below prove they can disagree.

**Import the light decider at module top; keep the heavy one body-local — this is the key design decision.** `split_safety.split_is_safe` lives in a `schema`-only leaf (backlog #86 relocated it out of `detail.py` for exactly this reuse), so import it at the **top** of `plan_tool/split_criteria.py` — it drags no orchestrator. `scope_out.compute_narrow` / `compute_frontmatter_hash` are the opposite: `plan_tool/scope_out.py` imports `plan_tool/detail.py`, which pulls in the orchestrator layer (`launcher`, `review`, `granularity`, …), so importing them at the top would drag that whole layer into a module that steps 2–3 keep as a light leaf (so anyone importing it for the catalog or legend pays nothing). Import those two **inside `evaluate_split_criteria`'s body**, the codebase's standard move for keeping a module's import edges light (mirrors the body-local imports in `plan_tool/cli/review_actions.py`). The catalog and legend stay reachable without loading any orchestrator; the heavy import happens only when the per-plan evaluator actually runs.

- **Rejected alternative:** re-implement the two predicates locally so the leaf stays pure at every level. Rejected because these gates must agree with what `escalate_to_split` and `scope_out_step` actually refuse at apply time — a re-typed predicate would drift from the actuator and report "splittable" where the tool would decline (or the reverse). The re-derive-locally pattern in this codebase is reserved for trivial path helpers (the detail-bundle path), not correctness-sensitive deciders.

**Extend the evaluator signature to add `repo_root`.** `compute_narrow` needs `repo_root` and a `source_frontmatter_hash` (from `scope_out.compute_frontmatter_hash(plan_path)`). Step 3 kept the signature at `evaluate_split_criteria(plan, *, plan_path)`; step 4 adds `repo_root: Path`. The CLI call site is step 6, but step 3's ~13 tests already call the two-arg `evaluate_split_criteria(plan, plan_path=...)` form — a newly-required `repo_root` makes each raise `TypeError`. So either give `repo_root` a default (e.g. `repo_root: Path | None = None`, resolving to `plan_path`'s repo root when omitted) or retarget those step 3 test call sites to pass `repo_root` (list them in the Cross-step reconcile below). Do not land the new required arg without one of these, or step 3's green-before-done gate (`enforce_step_tests: true`) blocks step 4. Compute the frontmatter hash once and pass it into each per-step `compute_narrow` call.

**Return the gates in a separate field, not as `CriterionResult` rows.** Add a frozen `SplitSafetyGate` (suggest fields: `step_id: int`, `split_safe: bool`, `split_blocking: tuple[int, ...]`, `scope_out_blocked: bool`, `scope_out_blocker_kinds: tuple[str, ...]`, and a one-line `reason: str`) and carry a `gates: tuple[SplitSafetyGate, ...]` on `PlanCriteriaBreakdown`. Keep them out of the `CriterionResult` tuple so the fires?-vs-gate distinction is structural, not just visual — this also lets step 5 serialize the fires? criteria into telemetry while excluding the gates from the drift diff (step 5 owns that; step 4 only keeps them separable). `SplitSafetyGate` and `PlanCriteriaBreakdown` stay in-memory records — nothing is serialized here, so `DATA_CONTRACT.md` / `tests/test_data_contract.py` are untouched.

**Render as a run-state gate, never fires?.** In `render_plan_breakdown`, print the gates in their own section (suggest a "Run-state gates (splittable now?)" header) below the fires? criteria. Use "splittable now?" / "can't split now" / "scope-out blocked" wording. Do not reuse the "a shape defect is present" phrasing. Suggested per-step reasons:
- split-safe true → "splittable now — no started or finished step at or after it"
- split-safe false → "can't split now — started/finished downstream step(s) {ids} block renumbering"
- scope-out clear → "scope-out clear — carve would renumber cleanly"
- scope-out blocked → "scope-out blocked — {blocker kinds}"

Keep the renderer pure (`list[str]` + `"\n".join`) and TTY-aware via `plan_tool/style.py`, matching step 2's legend and step 3's breakdown.

**Update the legend for two signals.** `render_split_criteria` currently describes one `split-safety` line (unpinned prose per step 2). Change it to describe both `split-safe` and `scope-out-blocked` in a sentence each. Their rules live in function bodies with no single backing constant, so they stay **unpinned prose** — do not invent a drift-guard number for them, and do not restructure `split_is_safe` or `compute_narrow` to make them renderable.

**Cross-step reconcile — split step 2's single entry, retarget its tests.** Step 2 ships one `split-safety` catalog id (its `test_catalog_has_merge_and_split_safety_ids` and `test_control_flow_criteria_present_but_unpinned`). Step 4 replaces that id with `split-safe` and `scope-out-blocked`. Retarget:
- step 2's `test_catalog_has_merge_and_split_safety_ids` → assert both `split-safe` and `scope-out-blocked` ids exist (altitude 3, `deterministic=True`) and that no lone `split-safety` id remains.
- step 2's `test_control_flow_criteria_present_but_unpinned` → assert the legend names both signals as prose.
- step 3's `test_evaluate_omits_split_safety` → superseded; split-safety is now evaluated. Replace it with the gate tests below.
- step 3's `evaluate_split_criteria` test call sites (~13 tests calling the two-arg `evaluate_split_criteria(plan, plan_path=...)` form) → if `repo_root` lands as a required arg rather than a defaulted one, pass `repo_root` in each so they don't raise `TypeError` under `enforce_step_tests: true`.

**Constraints and gotchas:**
- **No Claude anywhere.** `split_is_safe` and `compute_narrow` take no invoker; the autouse conftest backend gate must never fire in these tests.
- **Read-only.** `compute_narrow` mutates nothing; never call `apply_narrow`, `scope_out_step`, or `escalate_to_split` from here.
- **Parked steps stay safe.** A `scope: deferred` / `wont_do` step is still `PENDING` status, so `split_is_safe` already treats it as clean — no special handling.
- **Per-step cost is fine at plan sizes.** Calling `compute_narrow` once per step is O(N²) over steps; plans are small (typically < 20 steps), so this is acceptable. Compute the frontmatter hash once, outside the per-step loop.
- **The gates are not in the criterion-id set.** Step 3's invariant "every `CriterionResult.criterion_id` is in `SPLIT_CRITERIA`" applies to the fires? criteria only; gate results are a separate structure and are exempt.

## Tests

All in `tests/test_split_criteria.py` (unit, no Claude). Enumerate:

- `test_split_safe_true_when_all_steps_pending` — a plan with only `PENDING` steps → every step's `split_safe` is True, `split_blocking` empty.
- `test_split_safe_false_when_downstream_started` — a plan with a `DONE`/`CURRENT` step at or after a target → that step's `split_safe` is False and `split_blocking` names the offending ids (matches `split_safety.split_is_safe`).
- `test_scope_out_blocked_on_inbound_dependent` — a step another step `depends_on` → `scope_out_blocked` True with an `inbound-dependent` kind.
- `test_scope_out_blocked_on_downstream_orphan` — a non-`PENDING` step after the carved step → `scope_out_blocked` True with a `downstream-orphan` kind.
- `test_split_safe_and_scope_out_are_independent` — a plan where a step is `split_safe=True` but `scope_out_blocked=True` (inbound dependent, no started downstream) → proves the two signals disagree.
- `test_gates_match_the_real_deciders` — for a fixture, each gate's `split_safe` equals `split_safety.split_is_safe(plan, step.id)[0]` and `scope_out_blocked` equals `bool(compute_narrow(...).blockers)`.
- `test_evaluate_split_safety_calls_no_claude` — a fake invoker passed anywhere is never called; the backend gate never fires.
- `test_catalog_has_split_safe_and_scope_out_blocked_ids` — `SPLIT_CRITERIA` contains both new ids (altitude 3, `deterministic=True`) and no lone `split-safety` id (retargets step 2's test).
- `test_legend_names_both_split_safety_signals` — the legend text names both `split-safe` and `scope-out-blocked` as unpinned prose (retargets step 2's control-flow test).
- `test_evaluate_now_covers_split_safety` — the breakdown's `gates` field is populated (supersedes step 3's `test_evaluate_omits_split_safety`).
- `test_render_breakdown_uses_splittable_wording` — the gate section reads "splittable now?" / "can't split now" / "scope-out blocked" and never "fires".
- `test_render_breakdown_gates_separate_from_fires` — gates render in their own section, not among the `CriterionResult` rows.

### Test-creation order (feature step)

This is a **feature** step — new behavior. Add each test alongside the code it covers: compute `split-safe`, then its two tests; compute `scope-out-blocked`, then its blocker-kind tests; add the render section, then the wording tests. Every new test in `tests/test_split_criteria.py` must be green, and the retargeted step 2/step 3 tests must be updated (not left asserting the old single id / deferral), before this step is done.

## Acceptance criteria

- `evaluate_split_criteria(plan, plan_path=..., repo_root=...)` returns a `PlanCriteriaBreakdown` whose `gates` holds one `SplitSafetyGate` per step.
- Each gate's `split_safe` equals `split_safety.split_is_safe(plan, step.id)[0]`, and its `split_blocking` equals that call's blocking ids.
- Each gate's `scope_out_blocked` is True exactly when `scope_out.compute_narrow(...)` returns a non-empty `.blockers`, and `scope_out_blocker_kinds` lists those kinds.
- A fixture exists where a step is `split_safe=True` and `scope_out_blocked=True` at once (the two signals are independent).
- `SPLIT_CRITERIA` contains `split-safe` and `scope-out-blocked` (altitude 3, `deterministic=True`) and no `split-safety` id.
- `render_plan_breakdown` prints the gates in a distinct run-state section using "splittable now?"-style wording and never the word "fires".
- The evaluator calls no invoker and mutates nothing; `plan_tool/split_criteria.py` has no module-top import of `plan_tool.detail` or `plan_tool.scope_out` (they are imported inside `evaluate_split_criteria`).
- `uv run pytest tests/test_split_criteria.py -q` is green, including the retargeted step 2/step 3 tests.

## Deferred

- **Fingerprint-tagged telemetry and the drift diff** — step 5. It records the breakdown via step 1's `record_plan_criteria_breakdown` and **excludes** the split-safety gates from the drift note (their input is run state, which `compute_plan_fingerprint` does not hash). Step 4 only keeps the gates in a separate field so step 5 can exclude them; it writes no telemetry and imports neither `telemetry.py` nor `review_persistence`.
- **The `plan-tool split-criteria` CLI handler** — step 6 (`plan_tool/cli/split_criteria_cmd.py`), which passes `repo_root` and calls this step's evaluator + renderer.
- **Making `split_is_safe` / `compute_narrow` declarative** so their predicates could be pinned from this read-only surface — a `BACKLOG.md` criteria-metadata-catalog item, not a detail-time change. This step renders them as unpinned prose and touches no decider.
