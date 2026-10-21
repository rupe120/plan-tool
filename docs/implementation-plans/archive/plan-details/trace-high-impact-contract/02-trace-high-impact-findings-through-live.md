> **Auto-archived**: this plan was swept on 2026-08-03 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 2 — Trace high-impact findings through the live continuation paths

## Summary

Add deterministic trace coverage for how an advisory `Recommendation` with `impact="high"` behaves at today’s continuation gates. Extend `tests/cli/test_completeness_cmd.py`, `tests/test_cli.py`, and `tests/test_review.py` without changing production behavior. The key decision is to test each path using its real input collection, rather than assuming every severity check receives conceptual audit findings. On green, the tests show which live paths can observe the candidate from step 1 and which still stop under the severity-only rule.

## Table of Contents

- [Summary](#summary) — The test-only outcome and green-state result.
- [Table of Contents](#table-of-contents) — Links to each section in this detail.
- [Why](#why) — Why continuation reachability needs direct evidence.
- [Input](#input) — The parsed recommendation and continuation contracts under test.
- [Files (creates vs edits)](#files-creates-vs-edits) — The three existing test files to extend.
- [Implementation](#implementation) — The live-path trace and its constraints.
- [Tests](#tests) — Deterministic cases that establish the evidence.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [Deferred](#deferred) — Work intentionally left for the later scope decision.

## Why

Step 1 establishes that `impact="high"` can coexist with advisory `nit` or `info` severity. That alone does not prove a future augment rule has an effect: `plan_tool/cli/completeness_cmd.py:_run_iterate_convergence_loop`, `plan_tool/cli/reconcile.py:_iterate_reconcile_loop`, and `plan_tool/review.py:audit_plan_until_stable` read different recommendation collections and can stop for different reasons. These tests must show the real current reachability before step 3 rewrites the stalled #152 scope.

## Input

- **Step 1 outcome:** Use the parser-supported advisory, high-impact shapes established by step 1. Do not recreate or alter the parser contract in this step.

- **Recommendation contract:** Build fixtures through `plan_tool/review.py:Recommendation` and the supported audit or reconcile extraction paths so `severity`, `impact`, and `complexity` match live values.

- **Continuation rule:** Treat `plan_tool/convergence.py:is_blocking` and `plan_tool/convergence.py:should_continue` as the unchanged severity-only baseline.

- **Path-specific collections:** Keep conceptual audit findings distinct from the deterministic and self-consistency findings returned by `plan_tool/cli/completeness_cmd.py:_run_iterate_convergence_loop`’s `_open_findings_now` helper.

## Files (creates vs edits)

- **New files:** None.

- **Existing files (edits only):**
  - `tests/cli/test_completeness_cmd.py` — Add focused coverage showing the report gate remains severity-only and that conceptual high-impact advisory findings are not part of the completeness loop’s live open set.
  - `tests/test_cli.py` — Extend the reconcile-loop fixtures to trace high-impact advisory findings through the initial, ordinary post-walk, and merge-continue continuation updates.
  - `tests/test_review.py` — Extend `TestAuditPlanUntilStable` coverage with parsed high-impact advisory audit findings and the resulting low-yield decision.

## Implementation

- **Foundational logic:** Trace whether a parsed high-impact advisory finding reaches a live continuation decision.

- **Use real producer paths:** Build high-impact advisory findings from supported Claude-style audit or reconcile text where the path normally parses them. Do not hand-wave from a manually constructed object when the test is intended to prove parser-to-gate reachability.

- **Keep completeness scoped to its real inputs:** In `tests/cli/test_completeness_cmd.py`, extend coverage around `plan_tool/cli/completeness_cmd.py:_run_iterate_convergence_loop` and `_completeness_has_blocking_findings`. Show that a conceptual audit finding can be preserved for reporting while the loop’s `_open_findings_now` collection remains deterministic and self-consistency findings only. A high-impact advisory conceptual finding must not be presented as an observable completeness-loop continuation case when that collection cannot contain it.

- **Trace reconcile at every continuation update:** In `tests/test_cli.py`, use the existing `TestIterateReconcileLoopTriage` fixtures and nearby `_iterate_reconcile_loop` coverage to exercise the recommendation list used at loop entry and after a normal or merge-continue iteration. Keep triage inputs explicit: a candidate deferred by `plan_tool/review.py:partition_findings_for_triage` cannot prove the later continuation update. Assert the current severity-only outcome, including the `no_blocking_findings` stop where applicable.

- **Trace audit materiality through parsed findings:** In `tests/test_review.py:TestAuditPlanUntilStable`, feed audit output containing a parser-supported high-impact advisory finding. Assert that `plan_tool/review.py:audit_plan_until_stable` still treats it as non-material through its `material_new` calculation and follows the existing low-yield behavior. This is the live path where the candidate is both parsed and consumed by a continuation-related decision.

- **Preserve current policy:** Do not add `is_blocking_impact`, change `plan_tool/convergence.py:is_blocking`, alter `Recommendation`, or change parser prompts. The tests document the current boundary for step 3’s evidence-based re-scope.

- **Do not broaden the gate audit:** `plan_tool/cli/completeness_cmd.py:_completeness_has_blocking_findings`, its self-consistency manual-fix checks, and apply triage remain severity- or triage-based controls. They are controls for comparison, not targets for a new impact rule in this step.

## Tests

- `test_high_impact_advisory_audit_finding_is_reported_but_not_in_completeness_open_set` — proves the completeness loop cannot observe a conceptual high-impact advisory finding as a live continuation input.

- `test_completeness_report_gate_keeps_high_impact_nit_advisory` — proves `_completeness_has_blocking_findings` remains severity-only for the report and `--fail-on-findings` contract.

- `test_reconcile_initial_high_impact_advisory_stops_before_next_iteration` — proves the initial `plan_tool/cli/reconcile.py:_iterate_reconcile_loop` continuation check currently reaches `no_blocking_findings`.

- `test_reconcile_post_walk_high_impact_advisory_stops_at_next_continuation_check` — proves the ordinary post-walk continuation update remains severity-only.

- `test_reconcile_merge_continue_high_impact_advisory_keeps_the_same_severity_only_result` — proves each merge-continue state refresh uses the same current rule without claiming a separate impact path.

- `test_high_impact_nit_audit_findings_confirm_low_yield` — proves `plan_tool/review.py:audit_plan_until_stable` parses the candidate and still classifies it as non-material under the current rule.

### Verification (non-code step)

- Run the focused test selections for `tests/cli/test_completeness_cmd.py`, `tests/test_cli.py`, and `tests/test_review.py`.

- Confirm no production file changes are included in the step diff.

- Confirm every claimed reachable or unreachable path is backed by a test fixture that uses that path’s real recommendation collection.

## Acceptance criteria

- `tests/cli/test_completeness_cmd.py` proves that high-impact advisory conceptual findings remain outside `_run_iterate_convergence_loop`’s live open-findings collection.

- `tests/cli/test_completeness_cmd.py` proves a high-impact `nit` or `info` finding does not change `_completeness_has_blocking_findings`.

- `tests/test_cli.py` proves the reconcile initial, ordinary post-walk, and merge-continue continuation paths currently retain severity-only behavior for a reachable high-impact advisory finding.

- `tests/test_review.py` proves `audit_plan_until_stable` parses a high-impact advisory audit finding and still takes its existing low-yield path.

- The step changes only `tests/cli/test_completeness_cmd.py`, `tests/test_cli.py`, and `tests/test_review.py`.

## Deferred

- **Impact-aware predicate and call-site changes** — Step 3 re-scopes the stalled #152 plan from the evidence produced here; this step does not implement production behavior.

- **New impact emission or collection plumbing** — Keep separate from this trace if a desired continuation path cannot receive the candidate today.

- **Impact-only demotion** — Remains blocked on the later calibration work; this trace covers only the current severity-only behavior.
