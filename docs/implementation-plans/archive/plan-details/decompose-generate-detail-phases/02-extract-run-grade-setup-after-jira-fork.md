> **Auto-archived**: this plan was swept on 2026-08-18 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 2 — Extract run-grade setup after the Jira fork, preserving its preparation order

## Summary

Refactor `plan_tool/detail.py:generate_detail` so a named same-file run-grade setup phase prepares the state that authoring needs after step 1 selects the run-grade lane. Keep `plan_tool/detail.py:generate_detail` as the public entry and preserve the existing setup order, including concept loading, target selection, orphan adoption, checkpoint scanning, and invocation accounting. Update `tests/test_detail.py` with direct coverage for the setup handoff and its order. On green, Jira authoring still bypasses this phase, while run-grade calls retain their current results, writes, skips, and progress totals.

## Table of Contents

- [Summary](#summary) — Reviewer overview of the setup extraction.
- [Table of Contents](#table-of-contents) — Links to each section in this detail.
- [Why](#why) — Why run-grade preparation needs one named owner.
- [Input](#input) — State and contracts the setup phase receives and returns.
- [Files (creates vs edits)](#files-creates-vs-edits) — Files changed by this refactor.
- [Implementation](#implementation) — Required preparation boundary and ordering rules.
- [Tests](#tests) — Focused regression coverage for the extracted phase.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Primary references for the extraction and tests.
- [Applicable guardrails](#applicable-guardrails) — Plan boundaries that limit this step.
- [Deferred](#deferred) — Later lifecycle and post-loop work.

## Why

`plan_tool/detail.py:generate_detail` currently holds run-grade-only preparation beside later authoring and post-loop work, so the data and side effects needed before authoring are difficult to review as one boundary. Naming this phase makes the Jira fork from step 1 meaningful: only run-grade calls prepare concepts, pointers, checkpoints, and fresh-invocation counts. The extraction must preserve the current order because later work relies on adopted pointers before checkpoint decisions and on pre-scanned cached bodies before reporting invocation totals.

## Input

- **Step 1 handoff:** step 1 supplies the parsed `Plan` and sends only non-Jira calls into this phase. Do not parse the plan again or select the grade again here.

- **Run-grade inputs:** retain the existing `plan_path`, parsed `Plan`, `repo_root`, selection and mode arguments, invocation dependencies, reporter, prompt function, and run logger from `plan_tool/detail.py:generate_detail`.

- **Concept and deferral state:** preserve the relationship among `plan_tool/review_persistence.py:compute_plan_fingerprint`, `plan_tool/concept_tree.py:load_concepts`, `plan_tool/detail.py:_included_deferral_step_ids`, `plan_tool/detail.py:derive_candidate_buckets`, and the deferral-envelope requirement.

- **Checkpoint state:** preserve `plan_tool/checkpoint.py:load_if_valid`, `plan_tool/detail.py:_detail_step_input_hash`, and `plan_tool/detail.py:_DETAIL_CHECKPOINT_NAME` as the source of cached run-grade bodies and fresh-invocation accounting.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `plan_tool/detail.py` — extract run-grade preparation into a named same-file phase and pass its prepared state explicitly to the later lifecycle.
  - `tests/test_detail.py` — add focused setup-order and handoff coverage, while retargeting the Jira-bypass test from step 1 to the new setup boundary.

## Implementation

- **Foundational logic:** prepare all and only the run-grade authoring state in its current prerequisite order.

- **Keep the public entry thin.** `plan_tool/detail.py:generate_detail` keeps its public signature and step 1’s parsed-plan dispatch. On the non-Jira result of that dispatch, call one private same-file setup phase; do not change callers in `plan_tool/cli/authoring.py:cmd_detail`, `plan_tool/cli/review_actions.py:_dispatch_detail`, `plan_tool/bench.py:_run_detail`, or the re-export in `plan_tool/__init__.py`.

- **Use an explicit handoff.** Introduce a self-descriptive private setup helper, such as `_prepare_run_grade_detail`, and return the values later authoring needs through an explicit private state carrier. Keep it same-file and focused; do not add a generic orchestration framework or use a closure to retain hidden setup state.

- **Start from the parsed `Plan`.** The setup phase receives the one `Plan` parsed by step 1. It must not call `plan_tool/parser.py:parse_plan` again, alter parse-error behavior, or send Jira work through run-grade preparation.

- **Preserve concept preparation first.** Keep the best-effort `compute_plan_fingerprint` call, current empty-fingerprint fallback, `load_concepts` error behavior, and `_included_deferral_step_ids` calculation before target selection. Derive candidate body-section buckets and the deferral-envelope requirement from that same plan state before any authoring path consumes them.

- **Preserve target preparation next.** Resolve an explicit `step_id` through `Plan.step_by_id`, retain its existing `DetailError` conversion, then add required regeneration steps and restore step-id order. Do not let the extracted phase drop an included regeneration step or change the selected-step order.

- **Adopt before checkpoints.** Keep `find_unreferenced_detail_for_step` and `update_step_detail_field` after the final target list and before checkpoint scanning. Preserve the existing `force` and `dry_run` exclusions, warning behavior, and in-memory `Step.detail` update so later skip logic sees an adopted canonical detail file.

- **Normalize authoring dependencies before scanning.** Retain the existing `StderrReporter` and built-in input defaults before the lifecycle begins. The returned handoff must give both serial and concurrent authoring paths the same normalized dependencies.

- **Preserve checkpoint and invocation accounting.** Scan run-grade checkpoints after orphan adoption with the current `force`, regeneration, and `resume` exclusions. Keep structured-response validation when a deferral envelope is required, checkpoint-hit logging, and the existing fresh-work predicate. Compute `invoke_total` from fresh run-grade targets, force it to zero for dry runs, and begin the invocation index at zero.

- **Leave lifecycle ownership for step 3.** Do not move serial-versus-concurrent selection, calls to `plan_tool/detail.py:_generate_detail_concurrent`, per-step authoring through `plan_tool/detail.py:_author_step_detail`, or post-loop accumulators into setup. The setup phase hands ready state forward; it does not begin authoring.

- **Do not consolidate grade-specific preparation.** `plan_tool/detail.py:_generate_jira_detail` retains its Jira-only target, checkpoint, and artifact setup. Its distinct checkpoint namespace and its rule not to touch `Step.detail` remain separate from this run-grade extraction.

## Tests

### Tests for this step

- `test_jira_dispatch_bypasses_run_grade_setup` — retarget step 1’s dispatch spy to the extracted setup helper and assert a Jira-grade call never enters it.

- `test_prepare_run_grade_detail_preserves_preparation_order` — use scoped spies to assert concept loading, candidate-bucket setup, target selection, orphan adoption, and checkpoint scanning remain in their current order before authoring can begin.

- `test_prepare_run_grade_detail_preserves_regeneration_and_checkpoint_accounting` — assert included regeneration targets bypass stale cache and existing-detail skips, while cached bodies reduce the fresh invocation total and dry-run reports zero invocations.

- `TestGenerateDetailAdoptsOrphan.test_adopts_canonical_orphan_without_invoking` — retain the end-to-end proof that adoption restores the pointer and prevents an unnecessary authoring call.

- `TestGenerateDetailResume.test_resumed_step_counter_excludes_resumed_from_denominator` — retain the reporter assertion that cached steps do not inflate the fresh-invocation denominator.

Every listed test must be green before this step is complete.

## Acceptance criteria

- `plan_tool/detail.py:generate_detail` enters a named run-grade setup phase only after step 1’s Jira dispatch point.

- The setup handoff carries the parsed plan, concept and deferral state, ordered target steps, normalized authoring dependencies, plan slug, cached checkpoints, fresh invocation total, and initial invocation index.

- Concept loading, candidate-bucket derivation, target expansion, orphan adoption, checkpoint scanning, and invocation counting occur in the same order as before the extraction.

- A run-grade call still adopts an unreferenced canonical detail file before authoring, except under the existing `force` and `dry_run` conditions.

- Cached run-grade bodies still reduce the reporter denominator, while dry runs still have an invocation total of zero.

- A Jira-grade call does not invoke run-grade setup.

- `tests/test_detail.py` passes without weakening existing assertions.

## References

- [Python 3.13 Execution Model](https://docs.python.org/3.13/reference/executionmodel.html) — Review local binding and explicit state transfer when moving orchestration into a helper.

- [Python dataclasses](https://docs.python.org/3.13/library/dataclasses.html) — Use a small explicit state carrier if one is needed for the phase handoff.

- [pytest Monkeypatching Guide](https://docs.pytest.org/en/stable/how-to/monkeypatch.html) — Use scoped spies to characterize the preserved setup order.

- [pytest Assertion and Exception Testing](https://docs.pytest.org/en/stable/how-to/assert.html) — Assert preserved errors, ordering, and unchanged invocation totals.

## Applicable guardrails

- **The plan’s “## Plan intent”, named phase map:** limit this step to run-grade setup and its explicit handoff; leave lifecycle, post-loop handlers, and persistence with their owning steps.

- **The plan’s “## Step intent”, run-grade-only preparation:** ensure Jira calls bypass concepts, pointer work, orphan adoption, run-grade checkpoints, cached bodies, and invocation accounting.

- **The plan’s “## Out of scope”, behavior preservation:** do not change `generate_detail`’s signature, errors, `resume` or `force` behavior, checkpoint behavior, or observable authoring results.

- **The plan’s “## Out of scope”, separate structural mechanisms:** do not merge or redesign the convergence loop, Phase B, Trigger 2, `create_plan`, or `plan_tool/cli/run_cmd.py:cmd_run`.

## Deferred

- Run-grade authoring lifecycle and concurrent-versus-serial selection — step 3 owns these paths after setup receives its explicit handoff.

- Per-step convergence, split handling, and concept persistence — later steps own these separate outer-phase boundaries.

- Consolidating run-grade and Jira-grade preparation — the grade-specific artifact and checkpoint contracts remain deliberately separate.
