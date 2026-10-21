# Step 3 — Add an impact-recurrence classifier that spots a still-open high-impact seam across three passes

## Summary

Add `plan_tool/impact_recurrence.py`, a new cycle-free leaf that reads an already-loaded report history and answers one question: has the same still-open, explicitly high-impact region shown up in the newest three consecutive compatible passes without shrinking? The module owns its own eligibility rule (explicit `impact=high` with real provenance) and its own strict 3-of-3 consecutive window, while reusing the region-matching, focus, trajectory, and resolution helpers `plan_tool/convergence_diagnosis.py` exposes in step 1 — it changes nothing about `recurring_regions`, `diagnose_convergence`, or `classify_fork`. The entry point takes a `ReportHistory` (or its runs) as an argument and never reads disk, so the live loops in steps 6 and 7 can pass a history that includes the current in-memory pass. On green, `classify_impact_recurrence(...)` returns a frozen result that either says "no trigger, here's why the evidence fell short" or names one recurring high-impact seam with the outcome token `recurring_high_impact_seam`. Step 4 turns that result into a recommendation and rendered text; this step ships the classifier and its tests only.

## Table of Contents

- [Summary](#summary) — what the step adds and what it returns on green.
- [Why](#why) — the gap between the severity diagnosis and a recurring high-impact seam.
- [Input](#input) — the history contract this classifier reads, owned by steps 1 and 2.
- [Files (creates vs edits)](#files-creates-vs-edits) — the two new files; no existing file changes.
- [Implementation](#implementation) — the eligibility rule, the strict window, the result type, and the constraints that are not free to vary.
- [Tests](#tests) — the table-driven cases in `tests/test_impact_recurrence.py`.
- [Acceptance criteria](#acceptance-criteria) — checkable behaviors.
- [References](#references) — the docs worth reading for this step.
- [Deferred](#deferred) — what this step deliberately leaves to steps 4–7.

## Why

`plan_tool/convergence_diagnosis.py` already decides whether a plan's audit/apply loop is spinning, but it does so from severity and decomposition evidence: `recurring_regions` scopes every run to `APPLY_ELIGIBLE_SOURCES` plus `is_blocking(severity)` before it groups anything. A high-impact finding that normalizes to advisory `nit` or `info` never enters that scoping, so the one signal BACKLOG #158 cares about — the same consequential seam being rediscovered pass after pass — is invisible to it. The live completeness and reconcile loops therefore keep spending another Claude pass on a seam that another pass will not close, and they exit reporting success. This step adds the missing classifier as its own module so the existing severity verdicts stay exactly as they are and the two signals can be reported side by side.

## Input

The classifier consumes the normalized saved-history model in `plan_tool/convergence_diagnosis.py`, not raw sidecar JSON:

- **`ReportHistory` / `RunSnapshot` / `RunFinding`** — the whole contract. `RunSnapshot` carries `kind`, `step_id`, `created_at`, `plan_fingerprint`, `code_fingerprint`, `code_fingerprint_present`, `findings`, and the raw `annotations` map keyed by finding id.
- **The impact fields on `RunFinding`** — step 2 produces them: each finding's impact plus the provenance that separates an explicitly recorded value from a legacy row that never had one. Read whatever names step 2 lands; do not re-derive impact from severity, and do not re-parse `Recommendation`.
- **The shared helpers made public by step 1** — region matching, step focus, trailing-window arithmetic, no-shrinkage, newest-run resolution/decline checks, and region focus resolution. Use the public names step 1 exports; do not reach into a private helper.
- **Verification limit** — impact provenance only exists on rows written after step 2 ships, so on a real repo the classifier is inert until three new passes accumulate. All coverage in this step is against synthetic in-memory histories.

## Files (creates vs edits)

- **New files:**
  - `plan_tool/impact_recurrence.py` — the classifier module: eligibility rule, impact-region grouping, the strict consecutive window, and the frozen result type.
  - `tests/test_impact_recurrence.py` — unit tests for the trigger and every near-miss.
- **Existing files (edits only):** none. Step 1 owns the `convergence_diagnosis.py` helper visibility change and step 2 owns the `RunFinding` impact fields; this step consumes both and edits neither.

## Implementation

**What must be true when this step is done:** calling one public function with a history returns a frozen result that reports either no trigger (with a machine-readable reason the evidence fell short) or exactly one recurring high-impact seam, and nothing in `plan_tool/convergence_diagnosis.py` behaves differently than it does today.

- **Own the eligibility rule; do not reuse `recurring_regions`.** That function is the key design decision. `recurring_regions` filters to `APPLY_ELIGIBLE_SOURCES` + `is_blocking(severity)`, which drops advisory-severity high-impact findings — the exact candidates. Widening it is out of scope per the plan and would change the severity verdict for every plan. Build a parallel grouping pass in the new module that scopes each run to findings whose impact is explicitly `high` with real provenance, then groups them with step 1's public matching helper so both classifiers agree on what "the same region" means.
- **Reuse matching, not scoping.** The tiered match (step focus → anchor → fuzzy title) and the focus key are shared behavior; forking them would let the two classifiers disagree about region identity and would make the two verdicts hard to read together. Import them; don't re-implement.
- **The window is strict, not M-of-N.** `diagnose_convergence` deliberately tolerates one missed run (`RECURRENCE_TOLERANCE`). This classifier must not: the region has to appear in **each of** the newest three consecutive compatible passes. Define the pass count as a module constant (e.g. `IMPACT_WINDOW_PASSES = 3`) with a comment saying it is a fixed constant, not an operator flag.
- **Define "compatible" explicitly, and keep `plan_fingerprint` out of it.** Compatible passes are consecutive newest runs in the same series — reuse `series_key` / `series_label`, so a `detail-reconcile` series for step 5 is never compared against step 7's. Also require the impact evidence to be usable in each pass (post-step-2 rows). Do **not** break the streak on a changing `plan_fingerprint`: `completeness-apply` edits the plan on nearly every pass, so a plan-fingerprint-stable requirement would make the stop unreachable. Code movement is a different matter — a code fingerprint change between consecutive passes means the evidence is no longer comparable, and `_code_drifted_since_prior` in `plan_tool/convergence_diagnosis.py` is the precedent for the same-kind, `code_fingerprint_present`-gated compare. Recommended: treat a code-fingerprint change between two passes in the window as breaking the streak, and gate that check on `code_fingerprint_present` so an uncomputed map is never read as drift.
- **No shrinkage uses the region's own sampled counts.** Reuse step 1's public trajectory test rather than comparing raw endpoints, so `3,3,3` and `2,3,3` read no-shrink and `3,2,1` reads shrink. Feed it the counts for the runs inside the window only.
- **Still-open is checked on the newest pass only.** The seam must not be resolved or deliberately declined in the newest pass; the annotation rules for that already exist in `convergence_diagnosis.py` (`applied` or a decline-close both count as no-longer-open in a single run). Use the public form step 1 exposes.
- **Insufficient evidence is not a trigger.** Missing impact, legacy/unknown provenance, a row that cannot be correlated into a region, or fewer than three compatible passes all mean "continue normally". Carry the reason on the result (a small set of stable strings, e.g. `insufficient-passes`, `no-explicit-impact`, `shrinking`, `resolved-in-newest`, `no-recurring-region`) so steps 6 and 7 can log why the stop did not fire without re-deriving it.
- **Take the history as an argument; never load it.** The completeness loop diagnoses *before* the final sidecar is written, so at decision time disk history is missing the current pass. The public entry point signature should be roughly `classify_impact_recurrence(history: ReportHistory, *, window: int = IMPACT_WINDOW_PASSES) -> ImpactRecurrenceResult`, with `window` as a test seam the way `diagnose_convergence(..., window=...)` already is. Callers assemble the history, including any in-memory current run.
- **Result type.** A frozen dataclass — the module convention (`RegionTrend`, `SeriesDiagnosis`, `ConvergenceDiagnosis` are all `@dataclass(frozen=True)`). It carries whether the stop triggered, the outcome token, the reason when it did not trigger, and, when it did, the series key/label, resolved step focus, title/anchor, run indices, per-pass open counts, and the first/last/max severities that step 4 uses to choose an honest recommendation. Define the outcome token `recurring_high_impact_seam` as a module constant here since steps 4–7 all key on it; do not inline the literal downstream.
- **Constraints that are not free to vary:**
  - The module is a **leaf**: it may import `plan_tool.convergence_diagnosis` (and through it `review`, `review_persistence`, `convergence`, `locator`), but must never import `plan_tool.cli` and must not be imported *by* `convergence_diagnosis.py`, or the leaf ordering breaks.
  - **Read-only and deterministic** — no plan mutation, no file writes, no `invoker=` seam, no Claude. Same shape as `plan-tool convergence`'s no-Claude path.
  - **Do not touch `convergence.is_blocking_impact`.** The classifier computes its own high-impact predicate from `RunFinding`; the calibrated demotion policy in `plan_tool/convergence.py` stays scoped to the reconcile/audit-materiality callers it has today.
  - **At most one seam per result.** When several regions qualify, pick one deterministically (recommended: the one with the highest last-pass open count, ties broken by focus key) so the rendered output in step 4 is stable across runs.
- **Rejected alternative:** adding an `impact` mode flag to `recurring_regions` / `diagnose_convergence`. It reads as less code, but it puts two eligibility rules and two window rules inside one function whose current semantics the plan requires to stay unchanged, and it makes the severity verdict's behavior depend on a flag every caller has to get right.

## Tests

All cases live in `tests/test_impact_recurrence.py` and build `RunSnapshot` / `RunFinding` objects in memory (no `tmp_path`, no sidecar round-trip — persistence is steps 1–2's coverage). A small local builder for a synthetic history keeps the table-driven cases readable, and `window=` is passed explicitly where a case needs fewer than three passes.

- `test_triggers_on_three_consecutive_high_impact_passes_without_shrinkage` — a region present with explicit `impact=high` in all three newest passes, counts flat, open in the newest → triggered with the `recurring_high_impact_seam` token.
- `test_two_passes_do_not_trigger` — same seam in only the two newest passes → not triggered, reason `insufficient-passes`.
- `test_gap_in_the_middle_pass_does_not_trigger` — present, absent, present → not triggered; pins that the M-of-N tolerance in `diagnose_convergence` does **not** apply here.
- `test_shrinking_region_does_not_trigger` — open counts `3,2,1` across the window → not triggered, reason `shrinking`.
- `test_resolved_in_newest_pass_does_not_trigger` — newest pass annotates the finding `applied` → not triggered, reason `resolved-in-newest`.
- `test_declined_seam_does_not_trigger` — newest pass carries a deliberate decline-close annotation → not triggered.
- `test_missing_impact_does_not_trigger` — findings recur three passes with no impact recorded → not triggered, reason `no-explicit-impact`.
- `test_legacy_unknown_provenance_does_not_trigger` — impact present but provenance says legacy/unknown → not triggered; pins that legacy rows are insufficient evidence, not a trigger.
- `test_medium_impact_does_not_trigger` — recurring `impact=medium` seam → not triggered; pins that only explicit `high` qualifies.
- `test_severity_is_not_a_proxy_for_impact` — a recurring `high` *severity* region with no impact recorded does not trigger, while a recurring advisory-severity `impact=high` region does; the one case that proves this classifier is not the severity classifier.
- `test_regions_in_different_series_do_not_combine` — the same title under `detail-reconcile` step 5 and step 7 → not triggered.
- `test_code_fingerprint_change_breaks_the_streak` — three passes but the code fingerprint moves between two of them → not triggered.
- `test_uncomputed_code_fingerprint_is_not_drift` — `code_fingerprint_present` false on a pass → the streak survives.
- `test_plan_fingerprint_change_does_not_break_the_streak` — every pass has a different `plan_fingerprint` (the normal apply-loop shape) → still triggers.
- `test_result_carries_seam_focus_and_counts` — a triggered result exposes the step focus, series label, per-pass open counts, and title step 4 needs.
- `test_result_is_deterministic_with_multiple_qualifying_regions` — two qualifying seams → one is selected, and repeated calls select the same one.
- `test_empty_history_returns_untriggered` — no runs → not triggered, no exception.
- `test_severity_diagnosis_is_unchanged_for_the_same_history` — run `diagnose_convergence` over a history that trips the impact classifier and assert its verdict matches the same history's verdict computed without any impact fields set; pins the "existing semantics unchanged" acceptance criterion.

### Test-creation order (feature step)

This is a **feature** step. Write the tests above alongside the implementation, not after it — start with the trigger case and each near-miss so the eligibility rule is pinned before the window logic is tuned. Green-before-done gate: every test in `tests/test_impact_recurrence.py` must pass (`uv run pytest tests/test_impact_recurrence.py -q`), and the full suite must stay green, before this step is considered finished.

## Acceptance criteria

- `plan_tool/impact_recurrence.py` exists and exposes a public `classify_impact_recurrence` entry point that takes a history and returns a frozen result object.
- The module defines the `recurring_high_impact_seam` outcome token and the three-pass constant as module-level names.
- `python -c "import plan_tool.impact_recurrence"` succeeds, and `grep -n "plan_tool.cli" plan_tool/impact_recurrence.py` returns nothing.
- The classifier triggers for a synthetic history where one region carries explicit `impact=high` in the newest three consecutive same-series passes, has not shrunk, and is unresolved in the newest pass.
- The classifier does not trigger, and reports a reason, for each of: two passes, a gap in the window, shrinking counts, resolved-in-newest, declined, missing impact, legacy/unknown provenance, non-`high` impact, and cross-series regions.
- `diagnose_convergence`, `recurring_regions`, and `classify_fork` return the same verdicts as today for the same histories (pinned by `test_severity_diagnosis_is_unchanged_for_the_same_history` and the unchanged `tests/test_convergence_diagnosis.py` suite).
- `uv run pytest tests/test_impact_recurrence.py tests/test_convergence_diagnosis.py -q` is green.
- The module performs no writes and no backend calls: the autouse backend gate in `tests/conftest.py` stays satisfied with no `@pytest.mark.allow_real_claude` opt-out anywhere in the new test file.

## References

- [Python `dataclasses` — Data Classes](https://docs.python.org/3/library/dataclasses.html) — `frozen=True` and `field` semantics for the new result type, matching the frozen records already in `plan_tool/convergence_diagnosis.py`.
- [pytest — How to parametrize fixtures and test functions](https://docs.pytest.org/en/stable/how-to/parametrize.html) — the cleanest way to write the table of consecutive-pass sequences and their near-miss variants.

## Deferred

- **The recommend-only next action and rendered output** — step 4 owns them; this step returns structured data only.
- **The `structural_stop` reason in `should_continue`** — step 5 owns it in `plan_tool/convergence.py`.
- **Wiring the classifier into the live completeness and reconcile loops** — steps 6 and 7, including where in each loop the check runs.
- **Reading history off disk** — the classifier takes a history argument; the loops decide how to assemble it, including the in-memory current pass.
- **Fuzzy identity matching for a seam whose region identity drifts across passes** — recurrence keys on the shared matcher's stable identity; a drifting seam resets the streak. Tracked as a plan-level Deferred item.
- **Measured region-size shrinkage** — "no shrinkage" stays inferred from per-pass open counts; a real size metric needs a new persisted field.
- **Backfilling impact provenance onto rows written before step 2** — the stop is inert until three new passes accumulate.
- **An operator flag for the three-pass threshold** — it stays a module constant so the stop stays explainable.
