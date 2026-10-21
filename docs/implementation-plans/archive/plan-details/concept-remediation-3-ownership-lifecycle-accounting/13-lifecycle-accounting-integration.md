# Step 13 — Add lifecycle accounting integration coverage

## Summary

Add test-only integration coverage for ownership accounting across create restoration, split, merge, re-ground, scope-out, include-triggered regeneration, and completeness reporting. The seven existing test suites will share one lifecycle scenario and add focused command checks around it. The central design decision is to use dependency-owned production validators and exact persisted-state assertions instead of creating a second accounting rule in test helpers. On green, the suite proves that every successful transition conserves exact ownership or approved non-delivery accounting, while refused and failed transitions preserve the prior state.

## Table of Contents

- [Summary](#summary) — Overview of the integration coverage and expected result.
- [Why](#why) — Why the existing isolated tests do not prove lifecycle conservation.
- [Input](#input) — Dependency outcomes and persisted contracts exercised by the tests.
- [Files (creates vs edits)](#files-creates-vs-edits) — Test files changed by this step.
- [Implementation](#implementation) — The lifecycle matrix, shared oracle, and failure rules.
- [Tests](#tests) — Cases covering each transition and the complete sequence.
- [Acceptance criteria](#acceptance-criteria) — Observable conditions for completion.
- [References](#references) — Primary pytest guidance for the test matrix.
- [Deferred](#deferred) — Production and documentation work outside this test-only step.

## Why

The repository already has isolated ownership checks in `tests/test_create.py:TestCreatePlanConceptIntegration`, `tests/test_detail.py:TestStructuredDetailDeferrals`, `tests/test_detail.py:TestMergeSteps`, `tests/test_reground.py` re-baseline cases, and `tests/test_scope_out.py` scope-out cases. Those tests do not carry one signed accounting state through all supported transformations, and several existing scope-out expectations predate step 8’s rule that unattended execution cannot approve a new non-delivery record. This step closes that gap by proving conservation after every transition and by checking that a failure cannot be hidden by title matching, unsigned state, or a later successful operation.

## Input

- **Step 4 outcome:** consume the verified `plan_tool/detail.py:generate_detail()` publication result in which replacement detail output and accounting changes become durable together.
- **Step 5 outcome:** use `plan_tool/review.py:check_concept_coverage()` and the completeness command’s self-consistency result as the production accounting oracle.
- **Step 6 outcome:** exercise the exact ownership and non-delivery preview produced by `plan_tool/detail.py:split_step()`.
- **Step 7 outcome:** exercise the remapped accounting produced by `plan_tool/detail.py:merge_steps()`.
- **Step 8 outcome:** exercise reviewed scope-out publication through `plan_tool/scope_out.py:scope_out_step()`, including unattended refusal.
- **Step 11 outcome:** consume create’s explicit restoration review for both re-baseline and carved seed envelopes. Steps 9 and 10 own those producer formats through this dependency.
- **Persisted-state boundary:** inspect the parsed plan, current concept record, detail files, and generated seeds after each operation. Tests must not infer accounting from plan prose or concept titles.
- **Test-only limit:** this step may expose a missing dependency behavior but cannot repair production code. A failing lifecycle assertion is routed to the step that owns that behavior.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `tests/test_create.py` — cover exact seed restoration, explicit review, shared ownership, and rejection of stale, dropped, invented, ambiguous, or title-inferred mappings.
  - `tests/test_detail.py` — add the main lifecycle conservation sequence and failure checkpoints around split, merge, and include-triggered regeneration.
  - `tests/test_reground.py` — prove the machine-readable re-baseline output can be restored by create without losing or combining ownership.
  - `tests/test_scope_out.py` — prove carved accounting can be restored and update legacy unattended expectations to require reviewed non-delivery accounting.
  - `tests/cli/test_completeness_cmd.py` — verify valid final accounting is clear while invalid, contradictory, unsigned, or dangling accounting remains blocking and non-apply-eligible.
  - `tests/cli/test_authoring_cmds.py` — verify create, split, merge, and detail command paths expose the dependency-owned outcomes without bypassing review or success gates.
  - `tests/cli/test_scope_out_cmd.py` — replace automatic `--apply -y` approval expectations with interactive approval and unattended refusal coverage.

## Implementation

The foundational logic is a **lifecycle conservation assertion: after every successful transition, each reviewed concept has an exact committed or done owner, or one valid approved structured non-delivery record; every refused or failed transition preserves the prior durable accounting.**

- **Build one representative lifecycle fixture.** Include a sole-owned concept, a shared concept, an approved `defer` record, an approved `wont_do` record, and a concept that later returns to `include` through detail regeneration. Give at least two concepts similar titles but different stable IDs so title inference would produce the wrong result.

- **Keep identity exact.** At each checkpoint, compare stable concept IDs, record IDs, dispositions, approval state, artifact references, and any dependency-owned routing links. Preserve authored ordering where the production contract promises it, but do not impose exclusive ownership on shared concepts.

- **Use the production policy as the oracle.** Run `plan_tool/review.py:check_concept_coverage()` after each successful transition and assert it reports no accounting defect. Pair that with direct persisted-state assertions so an accidental weakening of the checker cannot make the integration test pass.

- **Exercise the lifecycle in order.** One integration scenario in `tests/test_detail.py` should begin with step 11’s reviewed create restoration, apply the step 6 split, apply the step 7 merge, consume a re-baseline restoration, perform a reviewed final-owner scope-out, transition the deferred concept back to `include`, regenerate its detail, and finish with the step 5 completeness check.

- **Use real orchestration functions with controlled boundaries.** Drive `plan_tool/create.py:create_plan()`, `plan_tool/detail.py:split_step()`, `plan_tool/detail.py:merge_steps()`, `plan_tool/reground.py:reground_bridge()`, `plan_tool/scope_out.py:scope_out_step()`, and `plan_tool/detail.py:generate_detail()` with temporary files and injected deterministic invokers or prompts. Do not invoke a real backend, network service, editor, or stdin.

- **Keep command coverage focused.** Use `plan_tool.cli.app:main()` in the CLI suites to verify argument routing, exit status, operator prompts, and rendered outcomes. Do not duplicate the entire domain lifecycle through every command; the main sequence belongs at the domain orchestration level.

- **Check every transition, not only the final state.** A later merge or completeness pass must not hide an earlier dropped ID or dangling record. Capture and validate plan and concept state immediately after create, split, merge, re-ground restoration, scope-out, and regeneration.

- **Pin preview-to-apply agreement.** For split and merge, prepare equivalent fixtures for dry-run and apply, then compare their exact ownership and non-delivery projections. Dry-run must leave plan, concept, detail, and seed bytes unchanged.

- **Test failed operations from durable snapshots.** Before each injected failure, save the plan text, concept sidecar, detail bytes, and relevant seed listing. Assert the operation either leaves them unchanged or matches the dependency-owned recoverable outcome; never accept a partially updated accounting generation.

- **Preserve approval boundaries.** Interactive review may approve a restored or scope-out non-delivery record. `yes=True`, non-TTY execution, malformed restoration input, or an ambiguous mapping must not create approval or satisfy completeness.

- **Prove no title inference.** Change titles between source and replacement steps, and include a misleading near-match. Restoration must follow exact structured identity or remain unsigned/refused.

- **Update superseded characterizations.** In particular, replace `tests/cli/test_scope_out_cmd.py:TestScopeOutThroughCLI.test_apply_yes_defers_last_owned_concept` and matching `tests/test_scope_out.py` expectations with the step 8 unattended-refusal contract. Keep shared-owner unattended scope-out coverage because that path creates no new approval.

- **Do not add a test-only accounting implementation.** Small fixture builders may construct dependency-owned models, but they must not decide whether accounting is valid. Duplicating the predicate would let production and tests drift together unnoticed.

## Tests

- `test_create_restores_exact_seed_accounting_after_explicit_review` in `tests/test_create.py` — reviewed restoration preserves sole, shared, and non-delivery identities exactly.
- `test_create_restoration_never_uses_title_inference` in `tests/test_create.py` — similar or changed titles cannot choose an ownership mapping.
- `test_create_rejects_invalid_seed_accounting_matrix` in `tests/test_create.py` — stale fingerprints, dropped IDs, invented IDs, contradictions, and ambiguous mappings remain refused or unsigned.
- `test_create_unattended_restoration_cannot_approve_accounting` in `tests/test_create.py` — `yes=True` and non-TTY execution cannot create reviewed restoration state.
- `test_lifecycle_accounting_is_conserved_after_every_transition` in `tests/test_detail.py` — create, split, merge, re-ground restoration, scope-out, include regeneration, and completeness each retain valid exact accounting.
- `test_lifecycle_failure_preserves_last_valid_generation` in `tests/test_detail.py` — injected split, merge, and regeneration failures cannot partially update plan, detail, or concept state.
- `test_split_and_merge_preview_match_applied_accounting` in `tests/test_detail.py` — dry-run projections equal persisted results and dry-run writes nothing.
- `test_include_regeneration_removes_non_delivery_only_after_durable_detail` in `tests/test_detail.py` — the approved record remains until replacement detail publication succeeds.
- `test_rebaseline_accounting_round_trips_through_create_review` in `tests/test_reground.py` — the step 9 envelope restores exact per-step and shared ownership through step 11.
- `test_rebaseline_round_trip_preserves_non_delivery_records` in `tests/test_reground.py` — dispositions, record identity, approval, and artifact provenance survive restoration unchanged.
- `test_carved_accounting_round_trips_without_title_inference` in `tests/test_scope_out.py` — the step 10 envelope restores carved ownership from exact structured data.
- `test_scope_out_then_include_regeneration_conserves_accounting` in `tests/test_scope_out.py` — reviewed final-owner deferral is later replaced only by durable delivery.
- `test_scope_out_unattended_final_owner_transition_writes_nothing` in `tests/test_scope_out.py` — unattended execution cannot publish unsigned non-delivery accounting.
- `test_completeness_is_clear_after_full_lifecycle` in `tests/cli/test_completeness_cmd.py` — the final valid state produces no lifecycle-accounting finding.
- `test_completeness_blocks_invalid_accounting_matrix` in `tests/cli/test_completeness_cmd.py` — missing, dangling, contradictory, unsigned, and invalid non-delivery states remain blocking.
- `test_lifecycle_accounting_findings_are_not_apply_dispatched` in `tests/cli/test_completeness_cmd.py` — structural accounting findings remain outside prose-apply dispatch.
- `test_authoring_commands_preserve_review_and_publication_outcomes` in `tests/cli/test_authoring_cmds.py` — create, split, merge, and detail commands retain the domain result and success/failure status.
- `test_detail_command_does_not_report_success_for_failed_accounting_publication` in `tests/cli/test_authoring_cmds.py` — failed or uncertain publication suppresses the success-only tail.
- `TestScopeOutThroughCLI.test_apply_interactive_publishes_approved_non_delivery_record` in `tests/cli/test_scope_out_cmd.py` — interactive scope-out publishes reviewed accounting.
- `TestScopeOutThroughCLI.test_apply_yes_refuses_when_non_delivery_review_is_required` in `tests/cli/test_scope_out_cmd.py` — `--apply -y` leaves all artifacts unchanged and prints the resumable interactive command.
- `TestScopeOutThroughCLI.test_apply_yes_keeps_shared_concept_included` in `tests/cli/test_scope_out_cmd.py` — unattended scope-out remains valid when a committed owner survives.

### Verification (non-code step)

- Run the seven focused suites together and confirm every lifecycle test passes without a real backend or network call.
- Run the full pytest suite and confirm existing create, detail, split, merge, re-ground, scope-out, and completeness behavior remains green.
- Confirm the working diff for this step contains only the seven declared test files and no changes under `plan_tool/`.
- Confirm the focused tests exercise both serial and concurrent detail authoring where step 4 exposes both paths.
- Confirm every expected refusal checks persisted bytes, not only return values or output text.
- Confirm no test helper reimplements the accounting-validity predicate or matches concepts by title.

## Acceptance criteria

- One deterministic integration scenario executes create restoration, split, merge, re-ground restoration, scope-out, include-triggered regeneration, and completeness in sequence.
- The scenario checks exact persisted accounting immediately after every successful transition.
- Every reviewed concept has an exact committed or done owner, or one valid approved non-delivery record, at every successful checkpoint.
- Shared ownership remains present on every intended owner through split, merge, and restoration.
- No title or body match is used to restore ownership or non-delivery accounting.
- Stale, dropped, invented, contradictory, or ambiguous restoration input is refused or remains unsigned.
- Unattended execution cannot approve restored or scope-out non-delivery accounting.
- Failed split, merge, scope-out, or regeneration operations do not leave a partially updated accounting generation.
- Split and merge dry-run accounting matches applied accounting while changing no artifact.
- Final valid accounting produces no completeness finding; invalid accounting remains blocking and is not sent to prose apply.
- All seven focused test files and the full test suite pass.
- This step changes no production or documentation file.

## References

- [pytest: How to Parametrize Fixtures and Test Functions](https://docs.pytest.org/en/stable/how-to/parametrize.html) — Use parametrization for the invalid restoration, failure-stage, approval-state, and lifecycle-operation matrices.

## Deferred

- **Production fixes exposed by this matrix** — return each failure to the dependency step that owns the missing behavior; this test-only step must not edit `plan_tool/`.
- **Operator documentation and backlog reconciliation** — step 13 documents the verified lifecycle and closes the tracking work.
- **Additional lifecycle operations** — operations outside create, split, merge, re-ground, scope-out, regeneration, and completeness need separate plan scope.
