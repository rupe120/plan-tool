# Step 2 — Add a high-impact structural stop reason

## Summary

Add a structural-stop signal for a high-impact finding that recurs without shrinking across the existing convergence window. `plan_tool/convergence_diagnosis.py` remains the single owner of recurrence and fork selection, while `plan_tool/convergence.py` exposes the new `"structural"` stop reason through `should_continue()`. Carry the persisted `Recommendation.impact` value into the diagnosis model so the rule can distinguish high-impact seams from ordinary recurring findings. On green, the read-only `plan-tool convergence` command keeps its current verdict and recommendation behavior, while steps 3 and 4 can use the new stop contract in live loops.

## Table of Contents

- [Summary](#summary) — The feature, ownership split, and green result.
- [Table of Contents](#table-of-contents) — Links to each section in this detail.
- [Why](#why) — Why a recurring high-impact seam needs a distinct stop signal.
- [Input](#input) — The saved and live history contracts this rule consumes.
- [Files (creates vs edits)](#files-creates-vs-edits) — Existing modules and tests in scope.
- [Implementation](#implementation) — The structural-stop rule, model changes, and invariants.
- [Tests](#tests) — Unit and command-level coverage to add.
- [Acceptance criteria](#acceptance-criteria) — Observable finished behavior.
- [References](#references) — Relevant standard-library and test-isolation documentation.
- [Deferred](#deferred) — Work reserved for later steps.

## Why

`plan_tool/convergence.py:should_continue()` can currently stop for local loop conditions such as marginal overlap or stalled counts, but it cannot tell that the same high-impact seam has recurred across saved audit history. `plan_tool/convergence_diagnosis.py:diagnose_convergence()` already owns the recurrence, no-shrinkage, and `classify_fork()` rules needed to make that judgment. Add a narrow bridge between those two layers so live callers can stop before spending another pass on a seam that needs the existing structural recommendation, without creating a second recurrence heuristic.

## Input

- **Step 1 live history:** Step 1 provides the diagnosis-owned operation that combines saved completeness history with the current live completeness snapshot. This step’s structural-stop predicate must work against that normalized `ReportHistory`, including its count-once checkpoint rule.

- **Persisted recommendations:** `plan_tool/convergence_diagnosis.py:_snapshot_from_saved_review()` and `_finding_from_recommendation()` receive `Recommendation` values loaded through `plan_tool/review_persistence.py:load_review()`. Preserve the persisted `impact` value in the normalized finding model; absent impact remains non-high-impact.

- **Existing diagnosis contract:** `plan_tool/convergence_diagnosis.py:diagnose_convergence()` determines whether a series is `VERDICT_SPINNING`, and `classify_fork()` selects `FORK_LOCALIZED`, `FORK_SCOPE_OUT`, `FORK_STRUCTURAL`, or `FORK_NONE`. Reuse those results rather than matching titles, anchors, or run counts again.

- **Existing blocking rule:** `plan_tool/convergence.py:is_blocking_impact()` remains the definition of high-impact blocking. The new history-based rule is an additional structural stop, not a replacement for severity- and impact-based continuation.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `plan_tool/convergence.py` — add the stable `"structural"` result to `should_continue()` and the `ConvergenceState` input needed to request that stop.
  - `plan_tool/convergence_diagnosis.py` — retain normalized finding impact and expose the diagnosis-owned predicate that identifies a recurring high-impact structural seam.
  - `tests/test_convergence.py` — cover the new `should_continue()` reason and its ordering against existing stop reasons.
  - `tests/test_convergence_diagnosis.py` — cover high-impact recurrence qualification and non-qualifying controls.
  - `tests/cli/test_convergence_cmd.py` — keep read-only convergence-command coverage proving its existing printed diagnosis remains intact.

## Implementation

- **Foundational logic: high-impact recurring-region structural-stop predicate.** Add one diagnosis-owned predicate with a clear public name, such as `has_high_impact_structural_stop(diagnosis)`, that returns true only when the diagnosis contains a spinning recurring region backed by high-impact evidence. It must consume `diagnose_convergence()` output and `classify_fork()` as needed; do not re-run region matching, windowing, or count-shrink checks outside `plan_tool/convergence_diagnosis.py`.

- **Carry impact through the diagnosis model.** Extend `plan_tool/convergence_diagnosis.py:RunFinding` with an optional impact field and populate it in `_finding_from_recommendation()`. Give the new field a compatibility-safe default where test fixtures construct `RunFinding` directly. Keep `RunFinding` limited to persisted recommendation data; do not add apply verdicts, resolved flags, or new saved-report schema fields.

- **Require both signals and make the candidate reachable.** A high-impact finding by itself must not trigger the structural stop. A spinning diagnosis without high-impact evidence must not trigger it either. For this structural-stop predicate only, use `is_blocking_impact(f)` and admit report-eligible high-impact findings even when their source is not in `APPLY_ELIGIBLE_SOURCES`, so a persisted `plan-completeness` high-impact `nit`/`info` can form the region. Existing diagnostic verdicts retain their severity-plus-source eligibility unchanged. The predicate still requires recurrence/no-shrinkage and high impact on that region.

- **Expose one stable stop code.** Add `"structural"` as a new reason returned by `plan_tool/convergence.py:should_continue()`. Model the signal on `ConvergenceState` as an explicit caller-supplied fact, with a default that preserves every current caller’s behavior. Document the new code alongside the existing stable reason strings.

- **Preserve stop ordering.** Keep all existing `should_continue()` reason strings and their behavior unchanged. The structural reason should win only when the caller has supplied the structural signal and the loop would otherwise continue; natural terminal states such as disabled iteration, convergence, iteration limits, deadline stops, advisory-only findings, marginal progress, and no-progress must retain their established outcomes.

- **Keep diagnosis independent of loop state.** `plan_tool/convergence_diagnosis.py` may depend on `plan_tool.convergence.py:is_blocking()` as it does today, but `plan_tool/convergence.py` must not import diagnosis types or report-loading code. The caller in steps 3 and 4 will translate the diagnosis predicate into `ConvergenceState` before calling `should_continue()`.

- **Keep fork choice unchanged.** `classify_fork()` remains the source of the eventual `FORK_LOCALIZED`, `FORK_SCOPE_OUT`, or `FORK_STRUCTURAL` recommendation. This step identifies when to stop; steps 3 and 4 own rendering the recommend-only command in their respective loops.

- **Keep the read-only command unchanged.** `plan_tool/cli/convergence_cmd.py` is outside this step’s edit footprint. Its existing use of `load_report_history()`, `diagnose_convergence()`, `classify_fork()`, and `render_diagnosis()` should continue to print the same diagnosis for equivalent saved history.

## Tests

- `test_should_continue_returns_structural_when_requested` — an otherwise-continuing state with the structural signal stops and returns `"structural"`.

- `test_structural_stop_does_not_override_existing_terminal_reason` — each existing earlier stop condition retains its current reason when the structural signal is also set.

- `test_recurring_high_impact_region_requests_structural_stop` — a normalized history with a high-impact finding recurring in a spinning region qualifies for the diagnosis predicate.

- `test_nonrecurring_high_impact_finding_does_not_request_structural_stop` — a single or shrinking high-impact finding leaves the predicate false.

- `test_spinning_low_or_missing_impact_region_does_not_request_structural_stop` — recurrence alone does not promote ordinary findings into a structural stop.

- `test_high_impact_on_unrelated_region_does_not_request_structural_stop` — high impact outside the recurring spinning evidence does not qualify the stop.

- `test_structural_spinning_emits_reseed` — retain the command-level regression coverage that a cross-step spinning history still prints the existing structural re-seed recommendation and exits zero.

### Test-creation order (feature step)

1. `test_recurring_high_impact_region_requests_structural_stop` — add the diagnosis-level positive case with the normalized persisted impact value.

2. `test_nonrecurring_high_impact_finding_does_not_request_structural_stop`, `test_spinning_low_or_missing_impact_region_does_not_request_structural_stop`, and `test_high_impact_on_unrelated_region_does_not_request_structural_stop` — add controls that keep the predicate narrow.

3. `test_should_continue_returns_structural_when_requested` and `test_structural_stop_does_not_override_existing_terminal_reason` — add the convergence-core contract after the diagnosis signal exists.

4. `test_structural_spinning_emits_reseed` — run the existing CLI regression scenario to confirm the read-only command remains unchanged.

Every new test must be green before this step is considered finished.

## Acceptance criteria

- `RunFinding` preserves a saved recommendation’s optional `impact` value without requiring a new report schema.

- The diagnosis-owned structural-stop predicate is true for a high-impact finding in an existing spinning, non-shrinking recurring region.

- The predicate is false for a non-recurring high-impact finding, a recurring finding with missing or non-high impact, and high impact outside the recurring region.

- `should_continue()` returns `(False, "structural")` only when its caller supplies the structural signal and no existing higher-priority stop reason applies.

- Every pre-existing `should_continue()` reason string continues to return under its current conditions.

- `classify_fork()` remains the only source of localized, scope-out, and structural recommendation selection.

- `tests/test_convergence.py`, `tests/test_convergence_diagnosis.py`, and `tests/cli/test_convergence_cmd.py` pass.

## References

- [Python dataclasses — Python 3.13 documentation](https://docs.python.org/3.13/library/dataclasses.html) — Reference for evolving `RunFinding` and `ConvergenceState` defaults without breaking direct construction in tests.

- [pytest monkeypatch documentation](https://docs.pytest.org/en/stable/how-to/monkeypatch.html) — Reference for isolating saved-history and command-path tests.

- [pytest capturing output documentation](https://docs.pytest.org/en/stable/how-to/capture-stdout-stderr.html) — Reference for preserving assertions on the read-only convergence command output.

## Deferred

- Live completeness-loop integration and recommendation rendering — steps 3 and 4 consume this stop contract in `plan_tool/cli/completeness_cmd.py` and `plan_tool/cli/reconcile.py`.

- Recurrence-window and threshold tuning — retain the current `WINDOW_SIZE` and `RECURRENCE_TOLERANCE` behavior owned by `plan_tool/convergence_diagnosis.py`.

- Automatic splitting or scope-out from a live loop — recommendation rendering remains non-mutating; existing mutation gates stay outside this step.
