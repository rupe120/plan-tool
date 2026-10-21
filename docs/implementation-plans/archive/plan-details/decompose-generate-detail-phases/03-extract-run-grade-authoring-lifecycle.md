> **Auto-archived**: this plan was swept on 2026-08-18 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 3 — Extract the run-grade authoring lifecycle and its per-step convergence helper

## Summary

Extract the run-grade authoring portion of `plan_tool/detail.py:generate_detail` into one named same-file lifecycle phase. Keep serial and concurrent selection, resume handling, writes, checkpoints, progress, run logging, and result ordering unchanged. Give the serial detail-quality audit/apply/re-audit loop one private owner that returns its clean and structural outcomes to the lifecycle. On green, `generate_detail` delegates prepared run-grade state to the lifecycle, while later post-loop handlers receive the same results and structural handoff they receive today.

## Table of Contents

- [Summary](#summary) — Reviewer overview of the extracted lifecycle and convergence boundary.
- [Table of Contents](#table-of-contents) — Links to every section in this detail.
- [Why](#why) — Why authoring and convergence need named owners.
- [Input](#input) — Prepared state and helper contracts the lifecycle consumes.
- [Files (creates vs edits)](#files-creates-vs-edits) — Files changed by this refactor.
- [Implementation](#implementation) — Lifecycle and convergence rules that must remain unchanged.
- [Tests](#tests) — Focused regression coverage for the new boundaries.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Primary references for state transfer, concurrency, and tests.
- [Applicable guardrails](#applicable-guardrails) — Plan boundaries that constrain this extraction.
- [Deferred](#deferred) — Later phase work left outside this step.

## Why

`plan_tool/detail.py:generate_detail` currently combines run-grade path selection, serial per-step work, concurrent dispatch, and a dense convergence loop in one public function. Existing helpers such as `plan_tool/detail.py:_author_step_detail` and `plan_tool/detail.py:_generate_detail_concurrent` already separate worker concerns, but the lifecycle and its audit/apply/re-audit work have no named owner. Extracting those boundaries makes the state passed to later split handlers reviewable without changing authoring behavior.

## Input

- **Step 2 handoff:** consume the parsed `Plan`, ordered targets, cached checkpoints, invocation counters, concept and deferral state, normalized reporter and prompt dependencies, and plan slug prepared by step 2. Do not parse the plan again or repeat setup work.

- **Authoring outcome:** preserve `plan_tool/detail.py:_author_step_detail` and its `_StepAuthoringOutcome` contract. The lifecycle remains responsible for its deferred plan-pointer update and serial follow-up work.

- **Concurrent path:** preserve `plan_tool/detail.py:_generate_detail_concurrent` as the existing concurrent authoring collaborator. Its ordered `DetailResult` and mixed-step output remain lifecycle inputs, not a new parallel implementation.

- **Convergence controls:** retain `plan_tool/detail.py:_scaled_detail_budget_for_step`, `plan_tool/convergence.py:ConvergenceState`, `plan_tool/convergence.py:should_continue`, `plan_tool/convergence.py:record_iteration`, and `plan_tool/convergence.py:touch` as the current loop contract.

- **Structural deduplication:** initialize `structural_seen` once for the whole serial run-grade lifecycle and pass that same `set[str]` to every per-step convergence call. It records structural recommendation ids already escalated in this invocation; a helper-local set would re-escalate the same plan-scoped finding on a later step.

- **Structural handoff:** carry mixed-step findings and the Trigger 2 state needed by later handlers explicitly. The lifecycle must not hide that state in a closure or perform post-loop policy itself.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `plan_tool/detail.py` — extract the run-grade lifecycle and its serial convergence helper into named same-file private phases with explicit inputs and outputs.
  - `tests/test_detail.py` — add lifecycle-boundary coverage and retarget existing authoring, convergence, structural, and logging tests to the extracted owners.

## Implementation

- **Foundational logic:** author each prepared run-grade step, then, when enabled, audit, apply, and re-audit its detail until the existing loop stops.

- **Keep the public entry as the coordinator.** `plan_tool/detail.py:generate_detail` keeps step 1’s parse-and-dispatch result and step 2’s prepared run-grade handoff. It calls one private lifecycle phase rather than retaining the authoring loop inline.

- **Use explicit lifecycle results.** One way is a small private result carrier, modeled on `plan_tool/detail.py:_StepAuthoringOutcome`, that returns `list[DetailResult]`, mixed-step findings, in-loop split identifiers, and recommend-only structural findings. Do not add a generic framework or rely on captured local state.

- **Select one existing authoring path.** Preserve the current `jobs`, fresh-target, and `dry_run` decision that chooses either `plan_tool/detail.py:_generate_detail_concurrent` or serial authoring. Keep the existing guards that prevent concurrent authoring from entering iteration or split behavior.

- **Preserve serial authoring order.** The lifecycle’s serial path keeps existing-detail confirmation, prompt rendering, dry-run return, resume confirmation, invocation-total adjustment, and `plan_tool/detail.py:_author_step_detail` invocation in their current order.

- **Keep durable-write follow-up in the lifecycle.** After a successful serial outcome, retain `plan_tool/detail.py:update_step_detail_field`, the in-memory `Step.detail` update, checkpoint discard, orphan archival, reporter completion, scenario capture, lesson capture, result creation, and per-step commit rules in their current relative order.

- **Keep run-log pairing complete.** Preserve `phase_start` before authoring and the `phase_end` `finally` behavior for success, cached work, parse or write failures, frontmatter failures, and structural split exits.

- **Extract the convergence loop as one unit.** Give the serial audit/apply/re-audit block one private helper, such as `_converge_run_grade_step_detail`. It receives explicit step, plan, budget, logging, drift, triage, and structural inputs, including the lifecycle-owned `structural_seen` set, then returns whether the detail is clean and whether an in-loop split changed control flow.

- **Preserve fresh detail-quality scans.** The helper keeps `plan_tool/detail.py:_cached_purity_findings` on its write-through authoring mode for both initial and re-audit scans. Do not turn the loop into a cache-only audit.

- **Preserve convergence and safety behavior.** Keep triage partitioning, finding deduplication, lifecycle-wide structural recommendation deduplication, budget stop reasons, pre- and post-apply drift handling, `plan_tool/launcher.py:revert_apply_if_parse_broken`, and the durable written result on non-clean loop exits.

- **Return Trigger 2 state without absorbing its policy.** Keep the `BLOCKED-STRUCTURAL` sequence of restoring the pre-apply snapshot, deduplicating the finding, and calling `plan_tool/launcher.py:escalate_to_split`. Return applied-split and recommend-only outcomes to the lifecycle for later handlers; do not move Phase B or Trigger 2 result rebuilding into this step.

## Tests

### Tests for this step

- `test_run_grade_lifecycle_selects_concurrent_or_serial_authoring` — assert the prepared lifecycle uses exactly one existing authoring path and preserves ordered results.

- `test_run_grade_lifecycle_preserves_serial_resume_and_durable_follow_up` — assert a serial resumed or invoked step retains invocation accounting, pointer update, checkpoint cleanup, and written-result behavior.

- `TestGenerateDetailConcurrent.test_jobs_one_matches_serial` — retain the public-path proof that explicit serial authoring matches the default path.

- `TestGenerateDetailIterationLoop.test_disabled_budget_skips_iteration_loop` — retarget to the convergence helper and assert the disabled budget makes no audit or apply call.

- `TestGenerateDetailIterationLoop.test_iterates_until_converged` — retarget to assert one finding is audited, applied once, re-audited, and reported clean.

- `TestInLoopStructuralEscalation.test_reverts_before_escalate` — assert the convergence helper restores a partial apply before it calls the split bridge.

- `TestInLoopStructuralEscalation.test_applied_split_breaks_all_loops` — assert an applied in-loop split stops remaining serial authoring and returns structural state for post-loop handling.

- `test_structural_seen_is_lifecycle_wide_across_two_steps` — present the same structural recommendation id while two different serial steps converge and assert that it reaches `plan_tool/launcher.py:escalate_to_split` once, without suppressing either step's ordinary convergence work.

- `TestGenerateDetailRunLogPhases.test_phase_end_error_on_frontmatter_update_failure` — retain the phase-end error record after the lifecycle extraction.

Every listed test must be green before this step is complete.

## Acceptance criteria

- `plan_tool/detail.py:generate_detail` passes step 2’s prepared run-grade state to one named lifecycle phase.

- The lifecycle returns ordered `DetailResult` values, mixed-step findings, and in-loop structural state through an explicit handoff.

- A prepared run-grade invocation still chooses the existing concurrent path only under its current conditions; otherwise it follows serial authoring.

- Serial authoring retains current resume, invocation-count, pointer, checkpoint, orphan, progress, run-log, scenario, lesson, and commit behavior.

- The named convergence helper remains a no-op with a disabled budget and performs fresh audit/apply/re-audit work with an enabled budget.

- Structural recommendation ids remain deduplicated across the full serial lifecycle, not only across repeated scans of one step.

- A `BLOCKED-STRUCTURAL` apply restores its snapshot before escalation and returns its structural outcome without running post-loop split policy.

- `tests/test_detail.py` passes without weakening existing assertions.

## References

- [Python 3.13 Execution Model](https://docs.python.org/3.13/reference/executionmodel.html) — Review local binding and explicit state transfer when extracting orchestration.

- [Python dataclasses](https://docs.python.org/3.13/library/dataclasses.html) — Use a small explicit private result carrier when it clarifies phase handoff.

- [Python concurrent.futures](https://docs.python.org/3.13/library/concurrent.futures.html) — Preserve the existing executor and future behavior in the concurrent authoring path.

- [pytest Monkeypatching Guide](https://docs.pytest.org/en/stable/how-to/monkeypatch.html) — Use scoped spies to characterize phase selection and helper handoff.

- [pytest Assertion and Exception Testing](https://docs.pytest.org/en/stable/how-to/assert.html) — Assert unchanged results, ordering, and error behavior.

## Applicable guardrails

- **The plan’s “## Plan intent”, named phase map:** keep this extraction private and same-file so the public entry continues toward the planned phase sequence.

- **The plan’s “## Step intent”, lifecycle and convergence boundary:** preserve serial and concurrent authoring behavior while giving the dense per-step loop one owner.

- **The plan’s “## Out of scope”, behavior preservation:** do not change the public callable contract, error behavior, resume or force behavior, checkpoint behavior, or observable authoring results.

- **The plan’s “## Out of scope”, separate structural mechanisms:** return structural handoff data without merging Phase B, Trigger 2, or the detail loop with another orchestration surface.

## Deferred

- Phase B extraction — step 4 owns its separate post-loop policy and consumes this lifecycle’s returned handoff.

- Trigger 2 extraction — step 5 owns its separate post-loop re-entry and result-rebuild policy.

- Final concept persistence and the finished public phase map — step 6 owns the final tail.

- Shared convergence code with `plan_tool/create.py:create_plan` — the plan’s separately scoped follow-up owns any cross-command abstraction.
