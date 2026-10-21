# Step 2 — Keep an incomplete audit's blocking ids in the verdict's close list

<!-- plan-tool:detail-format-version: 1 -->

## Summary

This step makes `finalize_completeness_run` build the blocking verdict from the ids the stage bar computes over the saved findings even when the audit is budget-limited or unqualified. Today `plan_tool/cli/completeness_phases.py:_conceptual_bar_from_audit_recs` returns `()` whenever `audit_incomplete` is true, so a budget-limited audit that already found HIGH correctness gaps reaches the verdict with an empty id set. The key decision is that the gate's ids and the verdict's ids are two separate values: the gate keeps `()` on an incomplete audit, so `has_blocking_findings`, `--fail-on-findings`, and exit codes stay as they are. The verdict gets the computed ids. On green, an incomplete verdict names the gaps to close and still offers no stage, and the `--json` payload is unchanged.

## Table of Contents

- [Why](#why) — what the empty id set hides today
- [Input](#input) — the facts and consumers the change reads
- [Files (creates vs edits)](#files-creates-vs-edits) — footprint
- [Implementation](#implementation) — separating verdict ids from gate ids
- [Tests](#tests) — cases and the green gate
- [Acceptance criteria](#acceptance-criteria) — observable results
- [Applicable guardrails](#applicable-guardrails) — fences that bind this step
- [Deferred](#deferred) — work left out

## Why

`_conceptual_bar_from_audit_recs` short-circuits to `((), True)` when coverage is `budget_limited` or fails `audit_coverage_qualifies_sample`. That empty tuple then feeds both the finalize gate and `blocking_verdict_from_gate`. A budget-limited run that already holds HIGH `plan-correctness` findings therefore produces an `incomplete` verdict whose `blocking_ids` is empty. Readers (`next_step_gaps`, `_reaudit_command`) see `blocking_count == 0` and list the real gaps as advisory, so the operator is not told what to close. The gate must keep treating an incomplete audit as non-blocking, so only the verdict's copy of the ids changes.

## Input

- **`_conceptual_bar_from_audit_recs`** in `plan_tool/cli/completeness_phases.py` returns `(ids, audit_incomplete)`; `ids` is `()` when incomplete.
- **`compute_conceptual_bar_blocking_ids`** (same file, re-imported by `plan_tool/cli/completeness_cmd.py`) is the pure stage-bar computation over `recs`. It needs no coverage input.
- **Consumers of the returned ids** at HEAD, each of which must keep the gate meaning:
  - the iterate loop's call in `_run_iterate_convergence_loop` (feeds `_remap_iterate_stop_for_conceptual_bar`, which already also checks `audit_incomplete`);
  - `finalize_completeness_run`'s call (feeds `_completeness_has_blocking_findings`, `classify_qualified_audit_result`, and `blocking_verdict_from_gate`);
  - `_completeness_has_blocking_findings`'s `conceptual_bar_blocking_ids` argument.
- **`blocking_verdict_from_gate`** in `plan_tool/completeness_report.py` already keeps whatever ids it is handed on an `incomplete` verdict; it needs no change.
- Step 1 owns `_verdict_untrusted_cause` and the `stale-revision` cause. This step only changes which ids reach the verdict.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/cli/completeness_phases.py` — expose the stage-bar ids for an incomplete audit without changing the gate pair `_conceptual_bar_from_audit_recs` returns.
  - `plan_tool/cli/completeness_cmd.py` — in `finalize_completeness_run`, pass the verdict ids (not the gate ids) to `blocking_verdict_from_gate`.
  - `plan_tool/completeness_report.py` — only if a reader needs a change to name retained ids on an incomplete verdict; likely none, confirm by test.
  - `tests/cli/test_completeness_cmd.py` — finalize cases for the budget-limited and unqualified paths.
  - `tests/test_completeness_report.py` — reader cases over an incomplete verdict that carries ids.

## Implementation

- **Keep two values.** The gate ids stay `()` on an incomplete audit. The verdict ids are `compute_conceptual_bar_blocking_ids(audit_recs, audit_stage=...)` whenever recs exist, complete or not. One way: compute the verdict ids in `finalize_completeness_run` right after `_conceptual_bar_from_audit_recs`, falling back to the gate ids when the audit is complete (they are equal then).
- **Rejected alternative:** change `_conceptual_bar_from_audit_recs` to always return the ids and make each caller zero them. That touches the iterate loop and the gate path, and one missed caller turns `--fail-on-findings` on for budget-limited runs.
- **Gate inputs must not change.** `_completeness_has_blocking_findings`, `classify_qualified_audit_result`, and `_completeness_finalize_is_clean` keep receiving the gate ids. `has_blocking_findings` in `--json` and the exit code must be byte-for-byte the same.
- **No stage offered.** An incomplete verdict still fails `is_completed_empty_set`, so `_verdict_offers_stage` stays false even with ids. Do not add a second predicate.
- **Stale revision (step 1).** A stale-revision result keeps its ids on the verdict, but step 1's reader rule applies: it gets the fresh-audit answer and its saved gaps are not offered as text to close. This step must not override that.
- **Deterministic findings** already flow through `blocking_deterministic` unfiltered; no change.
- **Iterate loop call site:** leave as is. Its ids only gate stop-reason remapping, which already requires `not audit_incomplete`.

## Tests

- `test_budget_limited_audit_keeps_blocking_ids_on_incomplete_verdict` (`tests/cli/test_completeness_cmd.py`) — a budget-limited sample with a HIGH correctness rec yields an `incomplete` verdict whose `blocking_ids` contains that id.
- `test_incomplete_audit_does_not_flip_has_blocking_findings` — the same run reports `has_blocking_findings` false and exit 0 under `--fail-on-findings`; pins that only the verdict changed, not the gate.
- `test_unqualified_audit_keeps_ids_and_offers_no_stage` — a non-conforming coverage sample keeps ids and offers no stage.
- `test_complete_audit_gate_and_verdict_ids_agree` — on a qualified sample the two id sets are equal.
- `test_conceptual_bar_pair_still_returns_empty_ids_when_incomplete` — pins that `_conceptual_bar_from_audit_recs` itself keeps the gate meaning.
- `test_next_step_gaps_lists_incomplete_verdict_ids_as_close` (`tests/test_completeness_report.py`) — a verdict with ids and an untrusted cause puts those recs in `close_correctness`, not advisory.
- `test_reaudit_command_counts_retained_ids_for_incomplete_verdict` — the description leads with the blocking count.

### Tests for this step

The cases above are the full roster. Every one must be green before the step is finished. Run `uv run pytest tests/cli/test_completeness_cmd.py tests/test_completeness_report.py -q`, then the full suite with `-n auto` to catch sibling tests that pinned the old empty-id behavior.

## Acceptance criteria

- A budget-limited audit with a HIGH correctness finding yields a verdict with `state == "incomplete"` and that id in `blocking_ids`.
- The same run's `--json` `has_blocking_findings`, `--fail-on-findings` result, and exit code equal their values at HEAD.
- `_verdict_offers_stage` is false for every incomplete verdict, with or without ids.
- `next_step_gaps` lists those ids' recs as gaps to close on a current revision.
- `_conceptual_bar_from_audit_recs` still returns `((), True)` for an incomplete sample.
- The full suite passes.

## Applicable guardrails

- The plan's "## Out of scope", finalize gate's external contract: this step must not change `--json` `has_blocking_findings`, `--fail-on-findings`, or exit codes, and must not touch `is_blocking_finding` or `is_blocking_impact`.
- The plan's "## Out of scope", blocking predicate split: no second predicate for incomplete audits; the existing stage-bar function is reused.
- The plan's step intent: every consumer of the returned ids stays enumerated above and keeps the non-blocking gate meaning.

## Deferred

- Cause classification and the `stale-revision` reader text — owned by step 1.
- Any change to what counts as blocking or to qualification rules — outside this plan's fence.
- Collapsing the gate ids and verdict ids into one return value — a wider refactor than this step's acceptance criteria need.
