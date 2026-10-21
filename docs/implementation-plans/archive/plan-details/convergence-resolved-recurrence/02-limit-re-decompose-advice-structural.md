> **Auto-archived**: this plan was swept on 2026-08-05 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 2 — Limit re-decompose advice to structural findings

## Summary

Restrict convergence recurrence to persisted medium-or-higher findings that the existing source taxonomy identifies as structural. Update `plan_tool/convergence_diagnosis.py` as the decision point, then align the altitude-3 criteria text in `plan_tool/split_criteria.py`, the convergence architecture description, and Step 1's saved-sidecar fixture. The key decision is to reuse `plan_tool/review.py:STRUCTURAL_SOURCES` for current sources while reading legacy `detail-purity` history as its folded `granularity-split` successor, rather than treating apply eligibility as evidence that a plan must be re-decomposed. On green, recurring claim or premise findings remain visible through their normal audit surfaces but cannot produce re-split, scope-out, or re-seed advice; unresolved structural evidence still can.

## Table of Contents

- [Summary](#summary) — Reviewer overview of the change and its result.
- [Table of Contents](#table-of-contents) — Links to each section in this detail.
- [Why](#why) — The current mismatch between finding routing and structural remedies.
- [Input](#input) — Persisted finding fields and source taxonomy this step reads.
- [Files (creates vs edits)](#files-creates-vs-edits) — Files changed by this step.
- [Implementation](#implementation) — Required source boundary and preserved behavior.
- [Tests](#tests) — Regression coverage for structural-only recurrence.
- [Acceptance criteria](#acceptance-criteria) — Observable completion conditions.
- [References](#references) — Primary documentation for preserved data and test contracts.
- [Applicable guardrails](#applicable-guardrails) — Plan boundaries that constrain the change.
- [Deferred](#deferred) — Related work outside this step.

## Why

`plan_tool/convergence_diagnosis.py:recurring_regions` currently treats `APPLY_ELIGIBLE_SOURCES` as the recurrence scope. That allows recurring plan-correctness or other claim/premise findings to reach `classify_fork()` and, for cross-step evidence, produce the destructive `FORK_STRUCTURAL` re-seed command, while the structural sources in `plan_tool/review.py:STRUCTURAL_SOURCES` are excluded. Re-decomposition is only justified by repeated structural evidence, so the diagnostic must separate that evidence from ordinary audit findings without hiding those findings from their normal resolution paths.

## Input

- **Persisted source classification:** The existing reader retains each saved recommendation's source classification. Use that value; do not add sidecar fields or infer categories from prose.

- **Canonical taxonomy:** `plan_tool/review.py:STRUCTURAL_SOURCES` is the existing definition of sources whose remedy is structural. Keep its membership owned there and consume it from the convergence leaf.

- **Legacy compatibility:** Saved v1 `detail-purity` findings predate its fold into `granularity-split`. Read that persisted label as structural recurrence evidence in the convergence leaf only; do not rewrite sidecars or add it back to the current canonical taxonomy.

- **Currentness rule:** Step 1 supplies the series-local newest-run recurrence rule. Apply this step’s source boundary before that rule is evaluated; do not change its matching, tolerance, or latest-run behavior.

- **Separate advisory path:** `_latest_blocking_findings()` intentionally reads critical and high findings without a source filter. Preserve it so nonstructural findings can still warn the operator on a non-spinning diagnosis.

## Files (creates vs edits)

- **New files:** None.

- **Existing files (edits only):**
  - `plan_tool/convergence_diagnosis.py` — Scope region construction and downstream recurrence to structural medium-or-higher findings, while preserving persisted-history and diagnosis interfaces.
  - `plan_tool/split_criteria.py` — Make the altitude-3 structural criterion and its rendered reason describe the structural-evidence boundary that now drives it.
  - `plan_tool/telemetry_analysis.py` — Match structural split-decision sidecars without importing the recurrence severity threshold.
  - `docs/ARCHITECTURE.md` — Update the `## Convergence diagnostic` description to state that re-decomposition guidance is based on recurring structural findings.
  - `tests/test_convergence_diagnosis.py` — Cover excluded nonstructural recurrence, retained structural recurrence, and preserved nonstructural advisories.
  - `tests/test_split_criteria.py` — Cover the per-plan altitude-3 result and legend wording after the source boundary changes.
  - `tests/cli/test_convergence_cmd.py` — Update Step 1's saved-sidecar fixture from apply-eligible to structural evidence and retain the absence-from-latest regression.
  - `tests/test_telemetry_analysis.py` — Keep structural split-decision sidecars structural after the shared region scope changes.

## Implementation

- **Foundational logic:** Let only recurring medium-or-higher structural findings supply a convergence re-decomposition recommendation.

- **Put the source boundary in region construction.** Update `plan_tool/convergence_diagnosis.py:recurring_regions` so the existing severity gate is paired with `plan_tool/review.py:STRUCTURAL_SOURCES`, not `APPLY_ELIGIBLE_SOURCES`. One suitable approach is to import the canonical set alongside the existing `Recommendation` import; `plan_tool/convergence_diagnosis.py` already depends on `plan_tool/review.py`, so this does not add a new layer or cycle.

- **Do not duplicate the classification later.** Keep `_series_verdict()`, `diagnose_convergence()`, `classify_fork()`, and `render_diagnosis()` operating on the already scoped `RegionTrend` values. This keeps one source-of-truth boundary and makes a nonstructural recurrence converge rather than remain “spinning” with an empty or misleading remedy.

- **Keep structural evidence eligible.** Both current members of `STRUCTURAL_SOURCES` must remain eligible when they meet `plan_tool/convergence.py:is_blocking`. Do not promote informational structural hints into recurrence evidence; the existing medium-or-higher threshold still applies.

- **Bridge only at history read time.** Pair current `STRUCTURAL_SOURCES` with a private legacy `detail-purity` alias while `recurring_regions()` builds trends. Keep the legacy label in the resulting history/model for accurate provenance, and do not add it to `STRUCTURAL_SOURCES`, `APPLY_ELIGIBLE_SOURCES`, or saved JSON.

- **Preserve Step 1’s currentness behavior.** The source filter must compose with the newest-run requirement, `RECURRENCE_TOLERANCE`, `_matches()`, sticky decline closure, and `_no_shrinkage()` without changing their contracts.

- **Keep ordinary findings actionable elsewhere.** Do not change `_latest_blocking_findings()` or use the recurrence filter to suppress nonstructural critical or high findings from the run-readiness advisory. This step removes destructive decomposition advice, not the underlying audit finding.

- **Keep the criteria projection thin.** `plan_tool/split_criteria.py:evaluate_split_criteria` and `_altitude3_result()` should continue to project `classify_fork()` rather than reimplement source selection. Update `SPLIT_CRITERIA` and `_FORK_FIRED_REASON` so the legend and per-plan result explain that `FORK_STRUCTURAL` is structural recurrence, not generic cross-step audit churn.

- **Keep public and persisted shapes unchanged.** Do not alter `RunFinding`, `RunSnapshot`, `RegionTrend`, `ConvergenceDiagnosis`, saved-review JSON, or command wiring. The existing `plan_tool/cli/convergence_cmd.py` load → diagnose → render path should inherit the corrected result.

- **Finish the CLI boundary transition.** Change Step 1's `test_missing_latest_finding_converges_without_redecompose_command` and `test_applied_latest_finding_converges_without_redecompose_command` fixtures from medium `plan-correctness` to medium `granularity-split` evidence as this source gate lands. Keep their empty and applied newest-run states so the tests continue to prove the combined final behavior; retain an existing structural positive-spinning CLI control.

- **Make the positive CLI control explicit.** Update `test_structural_spinning_emits_reseed` to save `granularity-split` evidence in every persisted run and keep its `spinning` plus `plan-tool create` assertions. This test proves the source boundary retains a runnable structural recommendation, rather than only proving the empty-latest negative case.

- **Keep split-decision telemetry structural, not recurrence-gated.** Reuse convergence diagnosis's structural-source and matching contracts in `telemetry_analysis`, but do not use its medium-or-higher recurrence filter: the live `code-reveals-split` signal is structural `info`. Treat a matching post-transition claim/premise finding as absence of the structural split signal. Update the telemetry fixture and persisted smoke recommendation to mirror that live severity.

## Tests

Green-before-done: every test below, plus the existing convergence diagnosis and split-criteria suites, must pass.

### Tests for this step

- `tests/test_convergence_diagnosis.py:test_scope_keeps_structural_medium_plus_findings` — Structural sources at medium or above create regions, while plan-correctness, Claude, and other nonstructural findings do not.

- `tests/test_convergence_diagnosis.py:test_legacy_detail_purity_recurrence_remains_structural` — A persisted medium `detail-purity` series remains spinning after the source fold, with its original source retained for provenance.

- `tests/test_convergence_diagnosis.py:test_nonstructural_recurrence_converges_without_redecompose_advice` — Repeated nonstructural findings across a full window produce no spinning fork and render no split, scope-out, or re-seed command.

- `tests/test_convergence_diagnosis.py:test_structural_recurrence_still_emits_reseed_advice` — Repeated unresolved structural findings with cross-step structural evidence still reach `FORK_STRUCTURAL` and render the re-seed command.

- `tests/test_convergence_diagnosis.py:test_latest_blocking_keeps_nonstructural_source` — A nonstructural critical or high finding remains in the non-spinning run-readiness advisory.

- `tests/test_split_criteria.py:test_evaluate_altitude3_spinning_fires_fork_arm` — Update the saved-history fixture to use structural evidence and retain the expected altitude-3 fork result.

- `tests/test_split_criteria.py:test_evaluate_altitude3_ignores_nonstructural_saved_recurrence` — Repeated nonstructural saved findings leave every convergence fork criterion unfired.

- `tests/test_split_criteria.py:test_legend_structural_fork_mentions_structural_recurrence` — The structural re-seed criterion’s user-facing description matches the new source boundary.

- `tests/cli/test_convergence_cmd.py:test_missing_latest_finding_converges_without_redecompose_command` and `test_applied_latest_finding_converges_without_redecompose_command` — Update both persisted-sidecar fixtures to structural evidence while retaining their non-spinning command assertions.

- `tests/cli/test_convergence_cmd.py:test_structural_spinning_emits_reseed` — Persist a full current structural recurrence and retain the re-seed command assertion.

- `tests/test_telemetry_analysis.py:test_code_reveals_split_transition_is_acted_on` and its related sidecar cases — Continue proving structural split-decision telemetry resolution with structural evidence.

- `tests/test_telemetry_analysis.py:test_code_reveals_split_ignores_nonstructural_post_transition_finding` — A claim/premise finding on the same step after transition does not make the structural split signal recur.

## Acceptance criteria

- `recurring_regions()` creates recurrence regions only for findings whose source is in `plan_tool/review.py:STRUCTURAL_SOURCES` and whose severity passes `is_blocking()`.

- A full recurrence window of medium-or-higher `plan-correctness` or other nonstructural findings produces a non-spinning diagnosis and no re-decomposition command.

- A persisted medium-or-higher `detail-purity` recurrence remains structural evidence after the source fold, without changing the current source taxonomy or sidecar format.

- A full recurrence window of unresolved structural findings still produces the appropriate localized, scope-out, or structural fork under the existing focus and severity rules.

- Cross-step unresolved structural recurrence can still produce `FORK_STRUCTURAL` and its `plan-tool create ... --from-existing` recommendation.

- A nonstructural critical or high finding remains visible through `latest_blocking` on a non-spinning diagnosis.

- `evaluate_split_criteria()` reflects the corrected convergence result without a second source-classification implementation.

- The saved-sidecar absent/latest and applied/latest CLI regressions use structural evidence after this source gate lands, and an existing CLI positive control still proves structural recurrence can spin.

- Structural split-decision telemetry uses structural sidecar evidence at its live info severity, preserving transition, still-open, and reversion assertions without treating a nonstructural post-transition finding as recurrence.

- `RunFinding`, `RunSnapshot`, saved-review JSON, `diagnose_convergence()`, `classify_fork()`, and `render_diagnosis()` keep their current interfaces.

## References

- [dataclasses — Data Classes](https://docs.python.org/3/library/dataclasses.html) — Preserve the frozen diagnosis-model interfaces while changing recurrence scope.

- [json — JSON encoder and decoder](https://docs.python.org/3/library/json.html) — Preserve compatibility with persisted saved-review records.

- [pytest tmp_path fixture API](https://docs.pytest.org/en/stable/reference/reference.html#tmp-path) — Build isolated saved-sidecar histories for recurrence regressions.

## Applicable guardrails

- **The plan’s “## Plan intent”, structural recurrence:** Keep genuine structural recurrence detectable while removing only unsupported destructive advice.

- **The plan’s “## Step intent”, remedy selection:** Limit this step to the source boundary for re-decomposition guidance; retain structural guidance when its evidence remains unresolved.

- **The plan’s “## Out of scope”, persisted-history compatibility:** Derive the decision from existing saved finding fields and do not change the review sidecar schema.

- **The plan’s “## Out of scope”, finding-category boundaries:** Reuse `STRUCTURAL_SOURCES` as-is; do not redefine structural, claim, or premise categories in this step.

- **The plan’s “## Out of scope”, decomposition workflow boundary:** Do not change split, scope-out, re-seed execution, CLI flags, or confirmation behavior.

## Deferred

- Changes to `plan_tool/review.py:STRUCTURAL_SOURCES` membership — source taxonomy is an existing cross-surface contract and needs a separate plan-level decision. The read-time `detail-purity` bridge preserves legacy history without changing that membership.

- Broader changes to cross-run matching, severity thresholds, or persisted review fields — this step only changes which existing sources may justify a structural remedy.
