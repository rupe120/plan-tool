> **Auto-archived**: this plan was swept on 2026-08-18 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 2 — Extract create-plan preparation and initial authoring

## Summary

Refactor `plan_tool/create.py:create_plan` so a same-file `_prepare_create_plan` phase owns its existing setup and first-pass authoring work. Keep publication, the convergence owner supplied by step 1, and finalization in their current locations for later steps. Preserve every initial backend call, checkpoint input, pre-write guard, and early split exit. On green, callers receive the same `CreateResult` and side effects, while preparation has one reviewable owner.

## Table of Contents

- [Summary](#summary) — The refactor’s result.
- [Table of Contents](#table-of-contents) — Links to each section.
- [Why](#why) — Why preparation needs a named boundary.
- [Input](#input) — Contracts and upstream work this step uses.
- [Files (creates vs edits)](#files-creates-vs-edits) — Files changed for the extraction and guard.
- [Implementation](#implementation) — Preparation boundary and preserved behavior.
- [Tests](#tests) — Focused coverage for source ownership and unchanged flow.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Python and pytest references for safe extraction.
- [Applicable guardrails](#applicable-guardrails) — Plan boundaries that apply here.
- [Deferred](#deferred) — Later phase extractions.

## Why

`plan_tool/create.py:create_plan` currently mixes input setup, seed handling, first-pass authoring, and later on-disk phases in one long function. Extracting preparation makes the handoff to publication understandable without changing how a plan is proposed, reviewed, synthesized, or rejected. It also places the initial-only rationale forwarding rule beside the only proposal call that may use it.

## Input

- **Step 1 handoff:** step 1 introduces the protected convergence owner. This step must pass it the state it already needs without moving convergence behavior back into preparation.

- **Public entry point:** preserve `plan_tool/create.py:create_plan`, its `spawn_cwd_from_repo_root` decorator, exact signature, and `CreateResult` return contract. `plan_tool/cli/authoring.py:cmd_create` and `plan_tool/bench.py:_run_proposal` remain unchanged direct callers, and the package-level re-export remains unchanged.

- **Preparation state:** `Plan`, `ConceptTree`, `Reference`, body-section inputs, collision decisions, and result metadata must remain available to the later publication and finalization work through an explicit same-file handoff.

## Files (creates vs edits)

- **New files:** none.

- **Existing files (edits only):**
  - `plan_tool/create.py` — extract setup and first-pass authoring into `_prepare_create_plan` and any small same-file support needed for its explicit result.
  - `tests/test_create.py` — retarget `TestRationalesOut` to the preparation owner and add focused rationale-flow coverage.

## Implementation

- **Foundational logic:** preparation owns all pre-publication state, and only the initial `propose_steps_from_claude` call receives `rationales_out=step_rationales`.

- **Create an explicit preparation handoff:** move the work from `create_plan` through the TODO-body gate into `plan_tool/create.py:_prepare_create_plan`. Return the normal prepared state explicitly for the later publication code; one way is a private same-file result object carrying the prepared plan, collision context, concepts, references, body inputs, and result metadata.

- **Keep the split as a preparation exit:** when `propose_distilled_seed_from_claude` returns a multi-plan split, `_prepare_create_plan` must return the current `CreateResult` shape with no `plan_path`. It must bypass initial step, reference, and body authoring, plus later writing and manifest work.

- **Preserve setup behavior:** keep `validate_slug`, silent `--yes` input handling, output-directory validation, manifest selection, collision discovery, replacement choice, metadata prompting, spell-check reporting, provenance loading, and seed-source resolution in their current order.

- **Preserve authoring order:** retain the existing conditional sequence of distillation, initial step resolution, `_review_step_change_types`, `_seed_initial_step_status`, `Plan` assembly, concept bootstrap and review, `_offer_missing_intents`, `propose_references_from_claude`, reference fetching, and `propose_body_sections`. Conditional skips must remain skips, not reordered calls.

- **Keep helper-owned checkpoints intact:** continue passing the current slug, output directory, repository root, resume setting, input function, and run logger to `propose_distilled_seed_from_claude`, `propose_steps_from_claude`, `_review_step_change_types`, `_offer_missing_intents`, `propose_references_from_claude`, `_fetch_reference_docs_block`, and `propose_body_sections`. Do not move checkpoint cleanup into preparation.

- **Move the rationale guard with authoring:** the initial non-canonical step proposal in `_prepare_create_plan` contains exactly one `rationales_out=step_rationales` forwarding call. Step 1’s `plan_tool/create.py:_converge_create_plan` contains none.

- **Keep the pre-write rejection before publication:** preserve `_render_plan_body` and `_find_placeholder_body_sections` as the TODO gate before collision archival, `write_new_plan`, and `append_to_manifest`. Keep the existing `budget.enabled` and `allow_placeholder_body` conditions.

- **Avoid a generic orchestration framework:** use same-file functions and explicit values rather than closures or a reusable pipeline abstraction. Step 3 owns publication extraction; this step must not move `archive_existing_source`, `write_new_plan`, `append_to_manifest`, or post-write concept synchronization.

## Tests

### Tests for this step

- `TestRationalesOut.test_prepare_call_owns_initial_rationales_out` — inspects `_prepare_create_plan` for exactly one initial rationale forwarding call and `_converge_create_plan` for none.

- `TestRationalesOut.test_initial_proposal_rationales_reach_step_review` — proves rationales captured by the first `propose_steps_from_claude` call still reach `_review_step_change_types`.

- `TestCmdCreateRunLog.test_phase_pairs_for_propose_steps_and_propose_references` — preserves first-pass phase order for steps, intents, references, fetched documentation, and body synthesis.

- `TestCreatePlanResume.test_create_plan_replace_on_collision_with_valid_checkpoint_overwrites` — preserves the collision-replacement path while cached initial authoring results remain usable.

- `TestCreatePlanDistillThreading.test_split_short_circuits` in `tests/test_distill.py` — preserves the preparation-only multi-plan split result with no later authoring or plan write.

Every listed test must be green before this step is complete.

## Acceptance criteria

- `plan_tool/create.py:_prepare_create_plan` owns setup, distillation, initial authoring, and the pre-write TODO gate.

- A multi-plan distillation result returns the existing split `CreateResult` before publication or convergence work starts.

- The initial `propose_steps_from_claude` call forwards `rationales_out=step_rationales` exactly once from `_prepare_create_plan`, and `plan_tool/create.py:_converge_create_plan` forwards it zero times.

- Initial backend-call order, run-log phase order, and checkpoint overwrite behavior remain unchanged.

- The TODO-body rejection still occurs before collision archival, plan writing, or manifest mutation.

- `plan_tool/create.py:create_plan` retains its public signature and existing callers remain unchanged.

## References

- [Python 3.13 Language Reference — Function definitions](https://docs.python.org/3.13/reference/compound_stmts.html#function-definitions) — Preserve the public function’s signature, decorators, defaults, and annotations.

- [pytest — How to monkeypatch/mock modules and environments](https://docs.pytest.org/en/stable/how-to/monkeypatch.html) — Keep same-module helper seams usable through the extraction.

- [Python 3.13 unittest.mock — Where to patch](https://docs.python.org/3.13/library/unittest.mock.html#where-to-patch) — Patch preparation dependencies where the extracted function resolves them.

- [Python 3.13 unittest.mock — Tracking order of calls](https://docs.python.org/3.13/library/unittest.mock-examples.html#tracking-order-of-calls-and-less-verbose-call-assertions) — Record first-pass call order if focused coverage needs it.

## Applicable guardrails

- **The plan’s “Plan intent”, phase sequence:** keep preparation as a same-file phase boundary and preserve the direct public entry point.

- **The plan’s “Step intent”, preparation ownership:** move the initial-only rationale guard with preparation and preserve the split-proposal exit.

- **The plan’s “Out of scope”, behavior preservation:** do not change signatures, errors, checkpoints, normal results, or convergence outcomes.

## Deferred

- Publication extraction — step 3 owns collision archival, initial write, manifest changes, and publication-time concept work.

- Finalization extraction — step 4 owns checkpoint cleanup, post-loop consumers, and the completed phase sequence.

- Shared create/detail convergence infrastructure — requires separately scoped follow-up work.
