> **Auto-archived**: this plan was swept on 2026-08-18 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 6 — Extract final concept persistence and shorten generate_detail to its phase map

## Summary

Extract the final run-grade concept persistence tail from `plan_tool/detail.py:generate_detail` into one private same-file phase, and extend `tests/test_detail.py` to pin its boundary. Keep `generate_detail` as the unchanged public entry: each invocation ends with persistence after that invocation's two post-loop handlers. Preserve the existing full-tree versus decision-record behavior, dry-run behavior, result ordering, recursive re-entry save timing, and recovery result when concept saving fails. On green, the final persistence phase sees the settled result list for its invocation and `generate_detail` reads as a short phase map.

## Table of Contents

- [Summary](#summary) — Reviewer overview of the final extraction.
- [Table of Contents](#table-of-contents) — Links to each section in this detail.
- [Why](#why) — Why final persistence needs its own owner.
- [Input](#input) — Result and concept-record contracts the phase consumes.
- [Files (creates vs edits)](#files-creates-vs-edits) — Files changed by this refactor.
- [Implementation](#implementation) — Required persistence boundary and preserved behavior.
- [Tests](#tests) — Focused regression coverage for phase order and record handling.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Relevant language and test references.
- [Applicable guardrails](#applicable-guardrails) — Plan boundaries that constrain this step.
- [Deferred](#deferred) — Related work left outside this extraction.

## Why

After step 5, `plan_tool/detail.py:generate_detail` still owns the final concept-record update inline even though authoring, Phase B, and Trigger 2 have each finished. That makes it too easy to move persistence ahead of a result rebuild or to save from an intermediate result list. Giving the tail one owner completes the intended outer phase map while keeping concept-record policy unchanged.

## Input

- **Step 5 result handoff:** step 5 completes Phase B and Trigger 2, then supplies their final `list[DetailResult]`; persistence must consume that settled sequence rather than any lifecycle-only or pre-split results.

- **Result contract:** `plan_tool/detail.py:DetailResult` identifies successful writes with `written` and carries each step’s `DetailDeferral` values. Only final successful results contribute replacement links or new flat deferrals.

- **Concept-record contract:** `plan_tool/concept_tree.py:ConceptTree`, `RECORD_KIND_FULL_TREE`, and `RECORD_KIND_DECISION` select the legacy-link or flat-record policy. `plan_tool/concept_tree.py:save_concepts` remains the single atomic publisher.

- **Fingerprint contract:** `plan_tool/review_persistence.py:compute_plan_fingerprint` must see the final detail bundle before a persisted record receives its provenance fingerprint.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `plan_tool/detail.py` — extract final concept persistence into a private same-file phase and make `generate_detail` call it after Trigger 2.
  - `tests/test_detail.py` — add or retarget focused tests for final-phase ordering, record-kind handling, dry runs, and persistence failures.

## Implementation

- **Foundational logic:** persist final written run-grade deferrals exactly once per `generate_detail` invocation after that invocation's post-loop result handling finishes.

- **Keep `plan_tool/detail.py:generate_detail` as the public coordinator.** Preserve its signature, return type, error behavior, and Jira-grade bypass. After the phases supplied by steps 1–5, call one private final-persistence phase and return its `DetailResult` sequence.

- **Use an explicit handoff.** Pass the final results, `dry_run`, `plan_path`, loaded `ConceptTree`, and candidate buckets to the persistence phase. Return the possibly downgraded results instead of changing them through hidden closure state.

- **Run persistence last for its invocation.** Phase B and Trigger 2 may recursively author details and rebuild result attribution after a split. The outer persistence phase must run only after both outer handlers finish, so it sees their final result ordering and no intermediate result list.

- **Keep nested persistence where it is.** Phase B and Trigger 2 deliberately re-enter `generate_detail` by explicit id. Each nested invocation reaches this phase after its own lifecycle and post-loop work before control returns to the enclosing handler; preserve that existing timing rather than batching nested saves at the outer tail. A nested save failure remains in that child result and must survive the enclosing handler's result rebuild before the outer final persistence sees the combined results.

- **Preserve the full-tree branch.** For `RECORD_KIND_FULL_TREE`, use `plan_tool/detail.py:_replace_detail_deferrals` to clear links only for final successful writes. Keep fresh flat deferrals out of the legacy record, retain the existing warning for each unrecordable proposal, and refresh the record fingerprint before publishing.

- **Preserve the flat branch.** When final successful results contain deferrals and the record is absent or is a decision record, keep `plan_tool/detail.py:_record_flat_deferrals` as the owner of creating or extending the unreviewed flat record. It must retain its existing duplicate and approved-decision behavior.

- **Keep no-op and recovery behavior.** A dry run must not publish a concept record. A fingerprint failure must return the results without a new persistence attempt. Route save failures through `plan_tool/detail.py:_persist_concepts_or_mark_failed` so on-disk detail remains recoverable but the returned successful writes are not reported as fully complete.

- **Leave external callers unchanged.** `plan_tool/cli/authoring.py:cmd_detail`, `plan_tool/cli/review_actions.py:_dispatch_detail`, `plan_tool/bench.py:_run_detail`, and recursive calls in `plan_tool/detail.py:generate_detail` keep using the same public API.

## Tests

### Tests for this step

- `test_final_persistence_runs_after_phase_b_and_trigger_2` — records the phase order and proves persistence receives Trigger 2’s final rebuilt results.

- `test_recursive_phase_b_and_trigger_2_reentry_keep_per_invocation_persistence` — parameterize both handlers, record nested and outer saves, and prove each nested call persists before its enclosing handler resumes while the outer call persists after both outer handlers.
- `test_legacy_record_deferral_warns_not_dropped` — retargets the existing legacy-record case to prove links clear for successful writes, new flat deferrals remain unrecorded, and the warning remains visible.
- `test_concurrent_deferrals_save_once_in_step_order` — proves final persistence performs one flat-record save in final step order after concurrent authoring.
- `test_dry_run_reports_include_regeneration_without_writes` — proves dry-run output and existing concept bytes remain unchanged because final persistence does not run.
- `test_failed_regeneration_retains_link_and_old_body` — proves a non-written result cannot clear its prior legacy deferral link.
- `test_concept_persistence_failure_marks_written_results_for_recovery` — forces `plan_tool/concept_tree.py:save_concepts` to fail and asserts the detail file remains present while returned results report persistence failure.

Every listed test must be green before this step is complete.

## Acceptance criteria

- Each `plan_tool/detail.py:generate_detail` invocation ends its run-grade path with one named final-persistence phase after its own Phase B and Trigger 2 work; recursive split recovery retains its existing nested phase before the enclosing handler resumes.
- The persistence phase receives the post-handler `DetailResult` list, not an earlier lifecycle result list.
- A full-tree record clears links only for final successful writes, remains a full-tree record, and warns instead of recording new flat deferrals.
- An absent or decision-record concept store receives final deferrals once, in final result order, without replacing an existing approved decision.
- Dry runs do not change concept-record bytes.
- A concept-save failure leaves the detail artifact available for recovery and returns results that do not falsely report complete success.
- `tests/test_detail.py` passes with its existing assertions retained.

## References

- [Python 3.13 Execution Model](https://docs.python.org/3.13/reference/executionmodel.html) — Read for explicit argument passing and function-local state during extraction.
- [Python dataclasses](https://docs.python.org/3.13/library/dataclasses.html) — Read for preserving immutable result records when persistence changes their completion status.
- [pytest Monkeypatching Guide](https://docs.pytest.org/en/stable/how-to/monkeypatch.html) — Read for replacing phase seams and `save_concepts` in focused regression tests.
- [pytest Assertion and Exception Testing](https://docs.pytest.org/en/stable/how-to/assert.html) — Read for assertions around final ordering and failure recovery.

## Applicable guardrails

- **Phase-map goal — the plan’s `## Plan intent`.** Limit this work to naming the final persistence phase so the public entry remains a short, ordered coordinator.

- **Final-tail ownership — the plan’s step 6 intent.** Run the legacy-versus-flat persistence rules only after that invocation's authoring and post-loop work has produced its final result set, while retaining the public entry's existing recursive invocation behavior.

- **Refactor boundary — the plan’s `## Out of scope`.** Keep observable behavior and the public surface unchanged, and preserve the separate Phase B and Trigger 2 policies.

## Deferred

- **Cross-command concept-persistence consolidation** — `plan_tool/create.py:_persist_or_clear_concepts` and `plan_tool/concept_tree.py:save_concepts` serve different command-level recovery rules; any shared policy refactor needs separate scope.
