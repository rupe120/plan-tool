> **Auto-archived**: this plan was swept on 2026-07-04 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 3 — Add the deterministic criteria evaluator and breakdown renderer (altitudes 1-3)

## Summary

Adds the per-plan half of `plan_tool/split_criteria.py`: an evaluator that runs the tool's existing deterministic split detectors against one plan and maps each result back to a step-2 catalog id, plus a renderer that prints the per-criterion breakdown (fires?/which steps/severity/one-line reason). The evaluator writes **no new detection logic** — it orchestrates `granularity.assess_granularity` at `stage="detail"` (altitude 2, including the `mixed-step` findings lifted from each step's detail body) and the `convergence_diagnosis` fork chain (altitude 3), and surfaces the `distill_thresholds` values as altitude-1 reference (the distill split decision itself is Claude-judged upstream on the seed, so it is marked not-evaluated). It runs **no Claude**: every detector is called with `invoker=None`. On green, `evaluate_split_criteria(plan, plan_path=...)` returns a breakdown whose result ids are exactly the step-2 catalog ids, and `render_plan_breakdown(...)` prints it plain when color is off. This step deliberately **omits** the split-safety run-state gate (step 4) and all telemetry/fingerprint/drift work (step 5).

## Table of Contents

- [Summary](#summary) — what the step adds and the observable result on green
- [Why](#why) — the missing per-plan surface this step fills, and what it defers
- [Files (creates vs edits)](#files-creates-vs-edits) — the two files this step edits (both created in step 2)
- [Implementation](#implementation) — the detector→criterion mapping per altitude, the breakdown renderer, and the constraints
- [Tests](#tests) — unit tests in tests/test_split_criteria.py covering each altitude's mapping
- [Acceptance criteria](#acceptance-criteria) — checkable behaviors on green
- [References](#references) — the pytest-marker background for this step's tests
- [Deferred](#deferred) — split-safety (step 4), telemetry + drift (step 5), CLI (step 6)

## Why

The tool decides how to split work at three altitudes, but every criterion only fires *inside* another command, and step 2 built only the plan-independent legend. Nothing yet answers "why is *this* plan shaped this way?" This step lands the per-plan surface: it runs the deterministic criteria that already exist against a given plan and maps each result onto the step-2 catalog. It is scoped narrowly on purpose — the plan was re-decomposed so that the split-safety run-state gate is step 4 and the fingerprint-tagged telemetry plus the drift diff are step 5. Landing the plain evaluator first keeps the detector→criterion mapping reviewable on its own, matching how `plan-tool convergence` leans on `convergence_diagnosis` behind a thin CLI. Step 1 delivers the `record_plan_criteria_breakdown` recorder, but **step 5**, not this step, is its caller; step 3 records nothing.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/split_criteria.py` — add the evaluator (`evaluate_split_criteria`), the per-plan breakdown renderer (`render_plan_breakdown`), and the small result records (`CriterionResult` / `PlanCriteriaBreakdown`). The step-2 catalog (`SPLIT_CRITERIA`, `SplitCriterion`) and legend renderer (`render_split_criteria`) keep their shape; per-plan mode reads the same catalog.
  - `tests/test_split_criteria.py` — add unit tests for the detector→criterion mapping across the three altitudes and the per-plan renderer.

**Note on file scope:** this step's frontmatter declares no `files:`. Both paths above are added here because the step cannot land without them — they are the two files step 2 creates and this step extends. No new file is introduced.

## Implementation

**Foundational logic: orchestrate the existing detectors and map each result back to a step-2 catalog id — write no new detection.** The evaluator is pure orchestration plus mapping. It must not copy, re-implement, or refactor any predicate in `plan_tool/granularity.py`, `plan_tool/convergence_diagnosis.py`, or `plan_tool/distill_thresholds.py`. The same detection logic lives in those modules today; call their public functions and map the output onto catalog ids. The three-altitude → owning-module map:

- **Altitude 2 (decompose into steps)** → `plan_tool/granularity.py:assess_granularity`, called `stage="detail"`, `evidence=GranularityEvidence(detail_bodies=…)`, `invoker=None`.
- **Altitude 3 (conditionally split one step)** → `plan_tool/convergence_diagnosis.py`: `load_report_history(plan_path)` → `diagnose_convergence(history)` → `classify_fork(diagnosis)`.
- **Altitude 1 (plan too big → many plans)** → `plan_tool/distill_thresholds.py` values, surfaced as reference only (the distill split decision is Claude-judged on the seed).

**Return a small in-memory breakdown record.** One way: a frozen `PlanCriteriaBreakdown` holding `plan_slug` and a tuple of `CriterionResult`. Each `CriterionResult` carries the catalog `criterion_id`, its `altitude`, `fired: bool`, `evaluated: bool` (False only for the Claude-judged altitude-1 distill row), `severity: Optional[str]`, `step_ids: tuple[int, ...]`, and a one-line `reason: str`. Keep both records **in-memory only** — they are never serialized here, so `DATA_CONTRACT.md` and `tests/test_data_contract.py` stay untouched (step 5 serializes a *primitive* projection into the telemetry context, not these dataclasses).

**Signature — keep it minimal; let step 5 extend it.** Recommend `evaluate_split_criteria(plan: Plan, *, plan_path: Path) -> PlanCriteriaBreakdown`. Everything this step needs is reachable from `plan` and `plan_path`: altitude 3 reads `load_report_history(plan_path)`, and the detail bodies live under `plan_path.parent`. Do **not** add `repo_root` or a telemetry seam now — the telemetry write and its `repo_root` are step 5's concern, and pre-adding them here would be dead until then.

**Altitude 2 — map granularity recs to catalog ids by their predicate key.**
- Call `assess_granularity(plan, stage="detail", evidence=GranularityEvidence(detail_bodies=bodies), invoker=None)`. `stage="detail"` runs the deterministic split+merge battery **and** lifts the prose `mixed-step` findings from `evidence.detail_bodies` via `parse_mixed_step_findings` — a regex parse, no Claude (confirmed: `assess_granularity` never calls the invoker).
- Populate `bodies: dict[int, str]` by reading each step's canonical detail file. Re-derive the bundle path locally — `plan_path.parent / "plan-details" / <plan-slug> / f"{step.id:02d}-*.md"` — and read the first match, keyed by `step.id`. This mirrors how `plan_tool/review_persistence.py:compute_plan_fingerprint` re-derives the same bundle path rather than importing `plan_tool/detail.py:derive_detail_path`; importing `detail.py` would pull a heavy orchestrator into this leaf. A missing detail file contributes nothing (an empty `bodies` just yields no `mixed-step` findings).
- Map each returned `Recommendation`:
  - `source == granularity.GRANULARITY_SPLIT_SOURCE` → `granularity.split_predicate_key(rec)` returns the criterion key for **all four** split ids — `mixed-verbs` / `two-clauses` / `multi-area` for the deterministic predicates, and the literal `mixed-step` (`SPLIT_PREDICATE_MIXED_STEP`) for a prose mixed-step rec — and the catalog criterion whose id equals that key is the match. `split_predicate_key` returns `None` only for a non-split rec (`rec.source != GRANULARITY_SPLIT_SOURCE` or `rec.step_id is None`), which the outer split-source guard already excludes; do **not** treat a `None` key as the `mixed-step` criterion.
  - `source == granularity.GRANULARITY_MERGE_SOURCE` → the catalog merge criterion.
- **Reuse `granularity.split_predicate_key` — never re-derive the id.** That helper re-hashes `_make_rec_id(...)` per candidate key to recover the predicate; a criterion's key is not readable off `rec.id` directly. Do not re-implement the hashing.
- **Surface `mixed-step` deterministically** per the plan's Architecture section: per-plan mode lifts already-recorded MIXED-STEP findings from the detail bundle, so `mixed-step` is evaluated here (fired when a recorded finding exists), not marked Claude-judged. The **only** criterion *emitted in the breakdown* with `evaluated=False` is the altitude-1 distill split; the split-safety gate is a distinct case — not emitted here at all (deferred to step 4, asserted by `test_evaluate_omits_split_safety`), so it is not a second `evaluated=False` row. **Reconcile step 2's actually-shipped catalog entry — confirm before flipping, don't assume.** Step 2 is authored but not yet merged, so read its shipped `mixed-step` catalog entry in `plan_tool/split_criteria.py` before editing. `deterministic` there means "the per-plan evaluator can evaluate it without Claude"; against HEAD the `stage="detail"` path calls `parse_mixed_step_findings` (a pure regex over `## Structural findings`) and never touches the invoker, so `mixed-step` must be `deterministic=True`. If step 2 already ships it that way with a no-invoker reason, no reconciliation is needed. If it still ships `deterministic=False` with a reason claiming the lift needs an invoker, that reason is wrong against HEAD — flip the flag to `True`, correct the reason to the no-invoker fact, and retarget the pinning test `test_mixed_step_criterion_marked_non_deterministic` (rename it to assert `deterministic=True`) plus any AC or catalog docstring asserting non-determinism, so the legend and the per-plan breakdown agree that `mixed-step` is deterministically evaluated. Leaving the two steps' catalog and breakdown disagreeing re-triggers this finding on the next audit.

**Altitude 3 — chain the convergence detectors; treat empty history as not-fired.**
- Run `load_report_history(plan_path)` → `diagnose_convergence(history)` → `classify_fork(diagnosis)`.
- The fork arm names the criterion: `ForkRecommendation.fork` is one of `convergence_diagnosis.FORK_LOCALIZED` / `FORK_SCOPE_OUT` / `FORK_STRUCTURAL` / `FORK_NONE`. The matching catalog criterion **fires** when `fork != FORK_NONE`; `classify_fork` only returns a real arm on a `VERDICT_SPINNING` diagnosis, so a non-`FORK_NONE` arm already implies spinning. The other two altitude-3 criteria are present but not fired.
- Read step ids from `ForkRecommendation.step_focus` (set on `FORK_LOCALIZED` / `FORK_SCOPE_OUT`, else `None`). Derive severity from the driving `ForkRecommendation.regions` (their `last_severity`).
- **Never raise on a valid-but-empty input.** When `diagnosis.verdict` is `VERDICT_NO_HISTORY` or `VERDICT_INSUFFICIENT_HISTORY`, mark all three altitude-3 criteria not-fired with a short reason ("not enough saved audit runs to diagnose spin"). These are normal verdicts, not errors.

**Altitude 1 — reference values, not a fired evaluation.** The distill *split* decision runs on the create-time **seed** before any plan file exists, and it is Claude-judged, so per-plan mode cannot re-run it. Emit the altitude-1 criterion with `evaluated=False`, `fired=False`, and a reason that names the thresholds `distill_thresholds.DISTILL_SKIP_BELOW_BYTES` and `DISTILL_ADVISE_ABOVE_BYTES` as reference values gating the seed — do **not** compare the authored plan file's own bytes against them (an authored plan's bytes are not the seed the threshold judges). This seed-gating semantics is authoritative and confirmed by `distill_thresholds.py`'s docstring; it supersedes any earlier design (and the captured project lesson) that prescribed comparing `plan_path.stat().st_size` against `DISTILL_*` on the authored plan. Step 2 already ships this criterion as `deterministic=False`, so step 3 consumes that entry as-is — no reconciliation needed.

**The breakdown renderer.** `render_plan_breakdown(breakdown: PlanCriteriaBreakdown, *, color: bool = False) -> str`. Build a `list[str]` and `"\n".join` it, the same pure shape as `plan_tool/convergence_diagnosis.py:render_diagnosis` and step 2's `render_split_criteria`. Per criterion print: fires?/which steps/severity/the one-line reason. Color via `plan_tool/style.py` when `color=True`, plain (no ANSI) when `False` — the same coloring approach step 2's legend uses, so the two render modes stay consistent. Spend no Claude, mutate nothing.

**Constraints and gotchas:**
- **No Claude anywhere.** Every detector call passes `invoker=None`. The autouse conftest real-backend gate must never fire in these tests.
- **No telemetry, no fingerprint, no drift diff here.** Do not import `plan_tool/telemetry.py` or `review_persistence.compute_plan_fingerprint` in this step — those are step 5. Keeping them out preserves the narrow review surface.
- **No split-safety gate here.** Do not call the `escalate_to_split` / `split_safety.split_is_safe` / `scope_out` blockers — step 4 adds those as two run-state signals with distinct "splittable now?" wording. This step's breakdown covers only the fires?-style criteria.
- **Cycle safety.** `plan_tool/split_criteria.py` imports `granularity`, `convergence_diagnosis`, `distill_thresholds`, `schema`, and `style`; none import it back. Do not import `create.py` or `detail.py`.
- **Every mapped rec must land on a known catalog id.** The mapping is exhaustive over the deterministic detector output — a rec that maps to no criterion is a bug the tests must catch.

## Tests

All in `tests/test_split_criteria.py` (unit, no Claude). Enumerate:

- `test_evaluate_maps_mixed_verbs_split_to_catalog_id` — a plan with a step title carrying both a refactor and a feature verb → the `mixed-verbs` criterion fires with that step id.
- `test_evaluate_maps_conjoined_clauses_and_multi_area` — plans that trip `two-clauses` and `multi-area` map to those catalog ids.
- `test_evaluate_maps_merge_source_to_merge_criterion` — a plan tripping a merge signal → the merge criterion fires.
- `test_evaluate_surfaces_mixed_step_from_detail_bodies` — a step whose detail file carries a `## Structural findings` MIXED-STEP block → the `mixed-step` criterion fires, and the invoker is never called.
- `test_evaluate_no_detail_bodies_mixed_step_not_fired` — no detail files on disk → `mixed-step` present but not fired; no raise.
- `test_evaluate_altitude3_spinning_fires_fork_arm` — a saved report history that yields a spinning verdict with a localized fork → the `localized` criterion fires with the focus step id; the other fork criteria do not fire.
- `test_evaluate_no_history_marks_altitude3_not_fired` — empty history → all three altitude-3 criteria not-fired with a reason; does not raise.
- `test_evaluate_altitude1_marked_not_evaluated` — the altitude-1 distill criterion has `evaluated=False`, `fired=False`, and a reason naming the two distill thresholds as reference values.
- `test_evaluate_every_result_id_is_a_catalog_id` — every `CriterionResult.criterion_id` is present in `SPLIT_CRITERIA`.
- `test_evaluate_records_no_telemetry` — running the evaluator writes no `.plan-tool/telemetry/decisions.jsonl` (recording is step 5).
- `test_evaluate_omits_split_safety` — the step-3 breakdown does not evaluate the split-safety criterion (deferred to step 4).
- `test_render_plan_breakdown_lists_each_criterion` — the rendered breakdown names each evaluated criterion with its fires?/steps/reason.
- `test_render_plan_breakdown_plain_when_color_off` — `render_plan_breakdown(..., color=False)` contains no ANSI escapes; `color=True` does.

### Test-creation order (feature step)

This is a **feature** step — new behavior. Add each test alongside the evaluator/renderer code it covers: write the altitude's mapping, then the test asserting the detector output lands on the right catalog id. Every new test in `tests/test_split_criteria.py` must be green before this step is done.

## Acceptance criteria

- `evaluate_split_criteria(plan, plan_path=...)` returns a `PlanCriteriaBreakdown` whose every `CriterionResult.criterion_id` is a member of `SPLIT_CRITERIA`.
- Altitude-2 granularity findings map by predicate key: `mixed-verbs` / `two-clauses` / `multi-area` via `granularity.split_predicate_key`, a keyless split rec → `mixed-step`, a merge rec → the merge criterion.
- `mixed-step` fires from a recorded MIXED-STEP block in a step's detail body, with the invoker never called.
- Altitude-3 uses `load_report_history` → `diagnose_convergence` → `classify_fork`; the matching fork criterion fires only when `fork != FORK_NONE`, and an empty/insufficient history marks the altitude-3 criteria not-fired without raising.
- The altitude-1 distill criterion is `evaluated=False` / `fired=False` with a reason naming `DISTILL_SKIP_BELOW_BYTES` and `DISTILL_ADVISE_ABOVE_BYTES`.
- `render_plan_breakdown(breakdown, color=False)` returns a non-empty string with no ANSI escapes; `color=True` includes them.
- The evaluator writes no telemetry file and evaluates no split-safety gate (those land in steps 5 and 4).
- `plan_tool/split_criteria.py` imports no orchestrator (`create.py`, `detail.py`) and does not import `telemetry.py`.
- `uv run pytest tests/test_split_criteria.py -q` is green.

## References

- [How to mark test functions with attributes (pytest docs)](https://docs.pytest.org/en/stable/how-to/mark.html) — this step's tests are plain unit tests (unmarked); the `main([...])` integration drive lands with the CLI in step 6.

## Deferred

- **The split-safety run-state gate** (split-safe / scope-out-blocked, rendered "splittable now?" rather than fires?) — step 4; this step evaluates only the fires?-style criteria.
- **Fingerprint-tagged telemetry and the drift diff** — step 5 calls step 1's `record_plan_criteria_breakdown` with `compute_plan_fingerprint(plan_path)` and renders the drift note. This step imports neither `telemetry.py` nor `review_persistence`.
- **The `plan-tool split-criteria` CLI handler** — step 6 (`plan_tool/cli/split_criteria_cmd.py`), modeled on `plan_tool/cli/convergence_cmd.py`; the per-plan mode calls this step's `evaluate_split_criteria` + `render_plan_breakdown`.
- **`DATA_CONTRACT.md` / `tests/test_data_contract.py`** — `CriterionResult` / `PlanCriteriaBreakdown` are in-memory records, never serialized here, so the persisted-schema contract is unaffected (step 5's telemetry serializes a primitive projection, not these dataclasses).
- **Making the deciders declarative** so a control-flow predicate could be pinned from this surface — a `BACKLOG.md` criteria-metadata-catalog item, not a detail-time change.
