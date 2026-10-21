> **Auto-archived**: this plan was swept on 2026-08-18 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 1 — Characterize create_plan’s exact signature and extract its convergence loop

## Summary

Lock `plan_tool/create.py:create_plan`’s public callable contract in `tests/test_create.py` before moving its post-write convergence loop. Extract that loop into the same-file private `_converge_create_plan` function with explicit inputs and a terminal outcome that distinguishes normal stops from step re-proposal failure. Keep `create_plan` as the direct public entry point and preserve its existing write, manifest, drift, triage, and checkpoint behavior. On green, callers see the same result and side effects while the convergence logic has one reviewable owner.

## Table of Contents

- [Summary](#summary) — The change and its visible result.
- [Table of Contents](#table-of-contents) — Links to each section.
- [Why](#why) — Why the convergence boundary needs a named owner.
- [Input](#input) — Existing callable and loop contracts this step preserves.
- [Files (creates vs edits)](#files-creates-vs-edits) — The two files this step changes.
- [Implementation](#implementation) — The extraction boundary and required invariants.
- [Tests](#tests) — Characterization and regression coverage.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Primary documentation for signature and mock behavior.
- [Applicable guardrails](#applicable-guardrails) — Scope limits from the plan.
- [Deferred](#deferred) — Work intentionally left to later steps.

## Why

`plan_tool/create.py:create_plan` currently owns a dense post-write loop that combines convergence state, drift checks, triage, applies, re-proposals, and terminal handling. That makes the loop hard to review independently while `plan_tool/cli/authoring.py:cmd_create` and `plan_tool/bench.py:_run_proposal` call it directly and the package re-exports it. Characterizing the public boundary first lets this refactor improve the internal shape without changing callers’ behavior.

## Input

- **Public callable contract:** `plan_tool/create.py:create_plan` is decorated with `spawn_cwd_from_repo_root` and returns `CreateResult`. Its only positional-or-keyword parameter is `slug: str`; every following parameter is keyword-only.

- **Exact keyword-only order:** preserve `repo_root: Path`, `output_dir_override: Optional[Path] = None`, `manifest_path: Optional[Path] = None`, `from_description: Optional[str] = None`, `from_existing_path: Optional[Path] = None`, `seed_body: Optional[str] = None`, `input_fn: InputFn = input`, `claude_invoker: ClaudeInvoker = shell_claude_invoker`, `concept_invoker: ClaudeInvoker = shell_concept_invoker`, `foundational_invoker: Optional[ClaudeInvoker] = None`, `capture_scenarios: bool = False`, `arm: Optional[str] = None`, `replace_on_collision: Optional[bool] = None`, `yes: bool = False`, `resume: bool = True`, `budget: IterativeBudget = IterativeBudget(enabled=False)`, `allow_drift: bool = False`, `auto_reconcile_on_drift: bool = True`, `collision_sidecar: bool = True`, `triage: bool = True`, `include_info: bool = False`, `synthesize_body: bool = True`, `offer_intents: bool = True`, `allow_placeholder_body: bool = False`, `fetch_docs: bool = True`, `distill: bool = False`, `skip_prose_reproposal: bool = True`, and `run_logger: Optional[RunLoggerLike] = None`.

- **Loop state contract:** `plan_tool/convergence.py:ConvergenceState`, `IterativeBudget`, `should_continue`, `touch`, and `record_iteration` define the iteration count, finding sets, and stop reasons. Preserve their existing use rather than creating another convergence model.

- **Persistence contract:** `plan_tool/create.py:write_new_plan` performs the initial write, while the loop uses `plan_tool/parser.py:write_plan` for re-proposal merges so body sections written by `apply_finding` survive. `plan_tool/review.py:collect_deterministic_findings` re-derives the next finding set from `plan_path`.

## Files (creates vs edits)

- **New files:** none.

- **Existing files (edits only):**
  - `plan_tool/create.py` — add `_converge_create_plan`, move only the post-write convergence setup and loop into it, and have `create_plan` receive its terminal outcome.
  - `tests/test_create.py` — add the exact `inspect.signature` characterization and retarget the parse-revert source guard while preserving existing direct-call, write-path, and iteration behavior tests.

## Implementation

- **Foundational logic:** move the post-write create convergence orchestration into `plan_tool/create.py:_converge_create_plan` without changing its decisions or side effects.

- **Characterize the public surface first:** add a test using `inspect.signature(plan_tool.create.create_plan)` that compares every parameter’s name, kind, order, default, and stored annotation, plus the return annotation. Compare parameter records rather than only rendering the signature as text, and compare callable defaults using the real imported objects so function-address formatting cannot make the test brittle.

- **Keep `create_plan` public and direct:** retain `plan_tool/create.py:create_plan`, its `spawn_cwd_from_repo_root` decorator, and its callable shape. `plan_tool/cli/authoring.py:cmd_create` and `plan_tool/bench.py:_run_proposal` remain zero-diff callers in this step.

- **Extract one same-file owner:** move the code beginning with the post-manifest `ConvergenceState` and initial deterministic findings through the `iteration_session` loop into `_converge_create_plan`. Pass the loop’s inputs explicitly, including the published `plan_path`, repository and proposal inputs, iteration options, logger, and plan fingerprint. Do not introduce a reusable framework, a shared loop with `plan_tool/detail.py:generate_detail`, or a closure that hides phase state.

- **Return the existing outcome distinction:** `_converge_create_plan` returns the stage-failure reason for an unparseable or invalid `propose_steps_from_claude` result and the normal no-failure outcome for converged, budget-limited, drift-halted, parse-halted, deferred-only, or retry-blocked stops. Let the existing code after the loop continue to decide checkpoint cleanup and populate `CreateResult.iteration_stage_failure`.

- **Preserve loop order:** retain the current order of `should_continue`, triage, duplicate-apply suppression, pre-apply drift handling, `apply_finding`, parse-revert handling, post-apply drift handling, deferred-only short-circuiting, prose-only re-proposal skipping, step/reference re-proposal, plan merge, reference patch, and deterministic re-derivation. An uncaught helper exception must still propagate instead of becoming a normal terminal result.

- **Keep the write distinction explicit:** give `_converge_create_plan` a terse docstring stating that it uses `plan_tool/parser.py:write_plan`, never `plan_tool/create.py:write_new_plan`, when it updates re-proposed steps. The former preserves the current prose body; the latter rebuilds it from initial source state.

- **Keep References behavior unchanged:** after each re-proposal, a non-empty `refs_proposal` still patches the on-disk References body even when the step proposal failed. `None` and `[]` still leave the existing section unchanged.

- **Preserve module-local test seams:** `tests/test_create.py:TestCreatePlanIterationLoop` and `tests/test_create.py:TestCreatePlanDriftHalt` patch helpers on `plan_tool.create`. The extracted function must continue to resolve `apply_finding`, `collect_deterministic_findings`, and related helpers from that module so those fakes still intercept the real call sites.

- **Stage source guards with their owners:** update `tests/test_create.py:TestCreatePlanDriftHalt.test_iterate_loop_reverts_parse_broken_apply` to inspect `_converge_create_plan`, where `revert_apply_if_parse_broken` and the parse-halt branch will live. Leave `tests/test_create.py:TestRationalesOut.test_convergence_call_omits_rationales_out` inspecting `create_plan` in this step: it must still find exactly the initial `rationales_out=step_rationales` forwarding call until step 2 moves preparation.

## Tests

### Tests for this step

- `test_create_plan_signature_is_exact` — compares the full `inspect.signature` parameter sequence, kinds, defaults, annotations, and `CreateResult` return annotation.
- `TestCreatePlanBlankSkeleton.test_happy_path` — keeps the direct-call contract: injected input creates the expected plan and one repo-relative manifest entry.
- `TestCreateOffersMissingIntents.test_intents_ride_the_single_initial_plan_write` — keeps the initial write path as one `write_plan` call carrying the accepted intent.
- `TestCreatePlanIterationLoop.test_create_plan_iterates_until_converged` — keeps normal convergence behavior, deterministic re-derivation, and the expected re-proposal count.
- `TestCreatePlanIterationLoop.test_iteration_step_failure_aborts_with_failure_signal` — keeps the distinct stage-failure result and failure banner rather than reporting a normal stop.
- `TestCreatePlanReferencesIteration.test_iteration_references_patched_despite_step_failure` — proves a non-empty iteration References proposal lands before the terminal stage-failure outcome.
- `TestCreatePlanDriftHalt.test_iterate_loop_reverts_parse_broken_apply` — inspects `_converge_create_plan` for the parse-revert call and parse-halt path.
- `TestRationalesOut.test_convergence_call_omits_rationales_out` — continues to inspect `create_plan` and finds exactly one initial rationale-forwarding call.

Every listed test must be green before this step is complete.

## Acceptance criteria

- `inspect.signature(plan_tool.create.create_plan)` matches the full current parameter contract and `CreateResult` return annotation.
- `plan_tool/create.py:_converge_create_plan` is the sole owner of the extracted post-write `while True` convergence loop.
- Normal convergence exits return no stage-failure outcome, allowing the existing caller path to discard checkpoints and return `CreateResult.iteration_stage_failure is None`.
- An invalid or unparseable iteration step proposal returns its failure reason after a non-empty References proposal is patched, and existing checkpoint-retention behavior remains intact.
- Iteration re-proposals use `plan_tool/parser.py:write_plan` rather than `plan_tool/create.py:write_new_plan`.
- The parse-revert source guard inspects `_converge_create_plan`; the rationale-forwarding source guard remains on `create_plan`.
- `tests/test_create.py` passes without weakening existing behavior assertions.

## References

- [Python 3.13 Language Reference — Function definitions](https://docs.python.org/3.13/reference/compound_stmts.html#function-definitions) — Verify keyword-only parameters, annotations, defaults, and decorators.
- [Python 3.13 inspect — Inspect live objects](https://docs.python.org/3.13/library/inspect.html#inspect.signature) — Use `Signature` and `Parameter` fields for the public-contract test.
- [pytest — How to monkeypatch/mock modules and environments](https://docs.pytest.org/en/stable/how-to/monkeypatch.html) — Keep the existing module-local helper seams working after extraction.
- [Python 3.13 unittest.mock — Where to patch](https://docs.python.org/3.13/library/unittest.mock.html#where-to-patch) — Patch helpers where `_converge_create_plan` resolves them.
- [Python 3.13 unittest.mock — Tracking order of calls](https://docs.python.org/3.13/library/unittest.mock-examples.html#tracking-order-of-calls-and-less-verbose-call-assertions) — Record ordering if a focused handoff test needs to prove loop sequencing.

## Applicable guardrails

- **The plan’s “## Plan intent”, same-file phase sequence:** keep this as a same-file organization refactor. This step names only the convergence owner and does not preempt the later preparation, publication, or finalization extractions.

- **The plan’s “## Step intent”, source-guard staging:** move the parse-revert inspection with the convergence code, but retain the rationale-forwarding inspection on `plan_tool/create.py:create_plan` until its preparation owner exists.

- **The plan’s “## Out of scope”, behavior preservation:** do not change the public signature, caller behavior, terminal outcomes, split-proposal path, checkpoint policy, or loop-sharing boundary.

## Deferred

- Preparation extraction — step 2 owns moving setup and the rationale-forwarding guard into its preparation phase.
- Publication and finalization extraction — later plan steps own the write, manifest, checkpoint-cleanup, and advisory phase boundaries.
- `plan_tool/detail.py:generate_detail` convergence sharing — requires separately scoped follow-up work.
- `plan_tool/cli/run_cmd.py:cmd_run` refactoring — remains outside this plan’s create-flow work.
