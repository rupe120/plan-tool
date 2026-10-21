> **Auto-archived**: this plan was swept on 2026-08-18 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 4 — Extract create-plan finalization and pin phase order

## Summary

Refactor `plan_tool/create.py:create_plan` so the normal plan-producing path ends in a named same-file finalization phase. The change affects `plan_tool/create.py` and its focused coverage in `tests/test_create.py`. Keep `create_plan` as the public entry point and make its normal flow explicit: prepare, publish, converge, then finalize. On green, callers receive the same `CreateResult`, checkpoint behavior, plan synchronization, concept state, and warnings.

## Table of Contents

- [Summary](#summary) — The refactor and its visible result.
- [Table of Contents](#table-of-contents) — Links to each section.
- [Why](#why) — Why the post-loop work needs one owner.
- [Input](#input) — The phase handoffs and persisted state this step consumes.
- [Files (creates vs edits)](#files-creates-vs-edits) — Files changed by this step.
- [Implementation](#implementation) — Finalization ownership, ordering, and invariants.
- [Tests](#tests) — Focused sequencing and regression coverage.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Documentation for safe same-file extraction and tests.
- [Applicable guardrails](#applicable-guardrails) — Plan boundaries that constrain this refactor.
- [Deferred](#deferred) — Related work outside this step.

## Why

`plan_tool/create.py:create_plan` currently keeps checkpoint cleanup, post-loop validation, concept work, user-facing pending-decision reporting, and `CreateResult` construction beside the convergence loop. That makes it hard to see which terminal state owns each action and easy to move cleanup or synchronization across the wrong boundary while extracting earlier phases.

## Input

- **Dependency handoffs:** step 1 supplies the named convergence owner, step 2 supplies prepared normal-path state, and step 3 supplies published on-disk state. Consume their explicit handoffs rather than reconstructing values from local variables.

- **Terminal result contract:** preserve `plan_tool/create.py:CreateResult`, including `iteration_stage_failure`, manifest metadata, collision archive metadata, provenance, and detail-rename fields.

- **Persisted state:** finalization reads the published `plan_path`, `plan_tool/checkpoint.py:checkpoint_dir`, and the concept sidecar addressed by `plan_tool/concept_tree.py:concepts_path`.

## Files (creates vs edits)

- **New files:** none.

- **Existing files (edits only):**
  - `plan_tool/create.py` — add the same-file finalization owner and reduce `create_plan` to the fixed phase orchestration on the normal path.
  - `tests/test_create.py` — add phase-order coverage and keep checkpoint, concept, and result-contract regression tests aligned with the extracted owner.

## Implementation

- **Foundational logic:** finish one published create run from its convergence terminal outcome without changing any durable artifacts or caller-visible result.

- **Add a finalization owner:** introduce a private same-file function such as `plan_tool/create.py:_finalize_create_plan`. Give it the published state, convergence terminal outcome, original proposed `Plan`, concept state, and result metadata it needs. One way is to pass a small explicit handoff object; do not make finalization depend on closure-captured state or re-run earlier phases.

- **Pin the normal sequence:** after step 2’s preparation and step 3’s publication, `plan_tool/create.py:create_plan` must call the convergence owner and then finalization exactly once. The multi-plan split remains a preparation exit and bypasses publication, convergence, and finalization.

- **Keep failures outside the normal finalization path:** do not use a broad `finally` that deletes checkpoints after an exception from preparation, publication, or convergence. Existing write and parse failures must still leave resumable checkpoints behind.

- **Keep checkpoint disposition unchanged:** finalization owns the existing `plan_tool/checkpoint.py:checkpoint_dir` sweep and `discard_checkpoint` calls. Each normal terminal path—converged, marginal, budget, drift, parse halt, deferred-only, and retry-blocked—reaches finalization without an iteration-stage failure, removes the existing create checkpoint families, and preserves their success run-log events. A terminal `CreateResult.iteration_stage_failure` retains those checkpoints so a rerun can resume; it does not become a clean finish.

- **Keep plan sources distinct:** call `plan_tool/create.py:advise_path_issues` with the original prepared `Plan`, as it does today. Post-loop concept synchronization and pending-decision reporting must instead read the final on-disk plan with `plan_tool/parser.py:parse_plan`, so they see convergence edits.

- **Keep post-loop concept behavior unchanged:** for an iterated signed concept scope, retain the existing `plan_tool/concept_sync.py:synchronize_concepts` call against the final parsed plan and its source text, including its failure behavior. For an iterated unsigned scope, retain the final parse and `plan_tool/create.py:_persist_or_clear_concepts` call with the existing safe-to-clear predicate.

- **Preserve sidecar rules:** do not simplify an empty concept record into unconditional deletion. `plan_tool/create.py:_persist_or_clear_concepts` must still save non-empty records, clear only safe empty records, and warn rather than fail on an unlink error.

- **Return the existing result:** construct `CreateResult` after all finalization work with the same values, including the convergence stage-failure reason. `plan_tool/cli/authoring.py:cmd_create` and `plan_tool/bench.py:_run_proposal` remain unchanged callers.

- **Leave the parallel detail flow alone:** `plan_tool/detail.py:generate_detail` has independent checkpoint and convergence behavior. Do not merge it into this extraction.

## Tests

### Tests for this step

- `test_create_plan_runs_prepare_publish_converge_finalize_in_order` — the normal path calls the four phase owners in order and passes the convergence terminal outcome to finalization.

- `test_create_plan_split_proposal_bypasses_later_phases` — a preparation split returns its existing result without publishing, converging, or finalizing.

- `test_finalize_create_plan_discards_checkpoints_for_normal_terminal_outcome` — finalization removes the existing create checkpoint files and keeps success discard logging whenever its terminal outcome has no iteration-stage failure.

- `test_create_plan_normal_terminal_paths_discard_checkpoints` — parameterize the end-to-end paths for converged, marginal, budget, pre- or post-apply drift, parse halt, deferred-only, and retry-blocked stops. Each must reach finalization with `iteration_stage_failure is None` and leave no create checkpoint shards; keep the separate stage-failure retention case below.

- `test_finalize_create_plan_retains_checkpoints_after_iteration_stage_failure` — an iteration-stage failure reaches finalization but leaves checkpoints available for resume.

- `TestCreatePlanResume.test_create_plan_keeps_checkpoints_when_write_fails` — an exception before a terminal convergence outcome still bypasses cleanup.

- `test_finalize_create_plan_uses_original_plan_for_advice_and_disk_plan_for_concepts` — path advice receives the original plan while `synchronize_concepts` and pending-concept coverage read the post-loop file.

- `TestCreatePlanConceptIntegration.test_undeferred_create_writes_no_concept_record` — the iterated unsigned path still writes no empty sidecar.

- `TestPersistOrClearConcepts.test_empty_result_clears_sidecar_when_safe` — a safe empty record removes the sidecar.

- `TestPersistOrClearConcepts.test_empty_result_leaves_sidecar_when_not_safe` — an unsafe empty record retains the existing sidecar.

Every listed test, plus `uv run pytest tests/test_create.py -q`, must be green before this step is complete.

## Acceptance criteria

- `plan_tool/create.py:create_plan` keeps its existing public signature and normal-path result contract.

- The normal plan-producing path executes preparation, publication, convergence, and finalization in that order.

- Every normal terminal path reaches finalization with `iteration_stage_failure is None`, removes the same create checkpoint families, and emits the same successful checkpoint-discard events.

- An iteration-stage failure returns the existing failure signal while retaining resumable checkpoints.

- Exceptions before a terminal outcome do not trigger cleanup.

- Post-loop advice uses the original plan, while post-loop concept synchronization and coverage use the final plan on disk.

- `_persist_or_clear_concepts` retains its existing save, safe-clear, unsafe-retain, and warning behavior.

- `tests/test_create.py` passes with the phase-order and finalization regression coverage in place.

## References

- [Python 3.13 Language Reference — Function definitions](https://docs.python.org/3.13/reference/compound_stmts.html#function-definitions) — Preserve the decorated public function and its keyword-only contract while extracting private helpers.
- [Python 3.13 inspect — Inspect live objects](https://docs.python.org/3.13/library/inspect.html#inspect.signature) — Characterize `create_plan`’s public signature before and after the refactor.
- [pytest — monkeypatch](https://docs.pytest.org/en/stable/how-to/monkeypatch.html) — Replace same-module phase owners safely in ordering and handoff tests.
- [Python 3.13 unittest.mock — Tracking order of calls](https://docs.python.org/3.13/library/unittest.mock-examples.html#tracking-order-of-calls-and-less-verbose-call-assertions) — Record the required phase sequence without coupling tests to implementation details.

## Applicable guardrails

- **Plan intent, phase sequence** — keep `plan_tool/create.py:create_plan` as the same-file phase orchestrator and preserve its public behavior.

- **Step intent, terminal consumers** — finalization must apply the convergence outcome while preserving each consumer’s current original-plan or on-disk-plan input.

- **Plan’s “## Out of scope”, extraction boundary** — do not change create behavior, convergence outcomes, split handling, or unrelated create and run flows.

## Deferred

- `plan_tool/detail.py:generate_detail` convergence and checkpoint finalization — keep its independent flow outside this create-only refactor.
