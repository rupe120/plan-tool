> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 5 — Verify safe create boundaries and partial-publication recovery

## Summary

Add cross-boundary regression coverage in `tests/test_create.py`, `tests/test_distill.py`, and `tests/cli/test_authoring_cmds.py`. The tests must distinguish before-first-write failures, retained pre-manifest artifacts, unexpected failures in the registered finalization tail, and the existing iteration-incomplete completion result. The key rule is that any created artifact remains on disk for an explicit recovery choice; it must never trigger automatic deletion, archival, replacement, or cross-target risk-decision reuse. Explicit registration adopts a parse-valid pre-manifest artifact and ends that create retry; a registered finalization error is already canonical but incomplete. On green, the test suite proves which retained plans can be adopted, which must be repaired or removed before retrying, and which need manual completion after registration.

## Table of Contents

- [Summary](#summary) — Reviewer-level outcome and recovery rule.
- [Table of Contents](#table-of-contents) — Links to each section.
- [Why](#why) — Why the create and CLI boundaries need end-to-end coverage.
- [Input](#input) — Upstream declaration, publication, and recovery contracts.
- [Files (creates vs edits)](#files-creates-vs-edits) — Test files changed by this step.
- [Implementation](#implementation) — Boundary matrix and test approach.
- [Tests](#tests) — Named regression cases and non-code verification.
- [Acceptance criteria](#acceptance-criteria) — Observable safety and recovery outcomes.
- [References](#references) — Typed-plan and YAML validation references.
- [Applicable guardrails](#applicable-guardrails) — Scope limits that keep this test-only step narrow.
- [Deferred](#deferred) — Recovery work outside this test step.

## Why

Step 2, step 3, and step 4 each protect one part of create, but only a cross-boundary test can prove that a final declaration reaches the published plan without weakening existing collision, manifest, split, or source-archive safety. `plan_tool/create.py:_prepare_create_plan` has pre-write gates, while `plan_tool/create.py:_publish_create_plan` can fail after `write_new_plan` and `plan_tool/cli/authoring.py:cmd_create` performs source archival only after a normal result. This step locks down the difference so a retained plan is visible and recoverable instead of being silently changed by a retry.

## Input

- **Step 2 classification boundary:** Step 2 supplies the single-plan proposal routes and preserves `plan_tool/create.py:DistillOutcome` split as a no-plan exit.
- **Step 3 declaration and checkpoint boundary:** Step 3 attaches the final risk declaration to the in-memory `plan_tool/schema.py:Plan` before `plan_tool/create.py:_publish_create_plan`, retains pre-manifest checkpoints for explicit recovery, bounds checkpoint reuse to the full predicted target, and preserves branch ownership after a retained-artifact error.
- **Step 4 completion boundary:** Step 4 makes `plan_tool/cli/authoring.py:cmd_create` read the persisted plan for its saved-tier summary before the normal source and distilled-artifact archival tail.
- **Existing publication and recovery surfaces:** `plan_tool/create.py:write_new_plan`, `plan_tool/create.py:append_to_manifest`, and `plan_tool/parser.py:parse_plan` determine whether an artifact exists and is parse-valid. `plan_tool/cli/manifest.py:cmd_register` is the existing explicit adoption path for a parse-valid unregistered plan.

## Files (creates vs edits)

- **New files:** None.

- **Existing files (edits only):**
  - `tests/test_create.py` — Add direct create-flow tests for pre-write isolation, retained post-write plans, retry refusal, and saved declaration bytes.
  - `tests/test_distill.py` — Extend seed and split coverage to prove failure paths do not archive a source or turn a split proposal into a partial plan.
  - `tests/cli/test_authoring_cmds.py` — Add command-level assertions for the retained-artifact failure report, skipped success tail, and explicit registration of a valid retained plan.

## Implementation

- **Foundational logic:** Classify before-first-write, retained pre-manifest, registered-finalization-error, and iteration-incomplete outcomes, then require the matching recovery or completion behavior.

- **Keep the test boundary wide enough.** Exercise `plan_tool/create.py:create_plan` across `plan_tool/create.py:_prepare_create_plan`, `plan_tool/create.py:_publish_create_plan`, and `plan_tool/create.py:_finalize_create_plan`; unit tests for the classifier and decision resolver alone cannot prove the publication ordering.

- **Preserve decision-gate isolation.** Model a step 3 decision-checkpoint durability failure before replacement archival and before `PreparedCreatePlan` reaches `_publish_create_plan`. Assert that no plan path is written, the manifest is unchanged, and an existing collision or `--from-existing` source is not archived or rewritten. Do not extend this no-side-effect claim to an explicitly authorized replacement or conversion once its existing source-archive operation begins.

- **Cover the first-write boundary.** Model a `write_new_plan` failure after its initial stub write but before its final plan write. The predicted target must remain on disk, be deliberately non-structured and therefore rejected by the existing registration command, and receive the same repair-or-remove guidance and collision-safe retry behavior as later retained artifacts. When the failure follows an explicitly authorized replacement or conversion, preserve the existing source-archive outcome rather than attempting a rollback.

- **Cover interruption at the same boundary.** Model `KeyboardInterrupt` before the first target write and after the initial stub or complete target write. Before a target exists, preserve the current exit-130 and branch-rollback behavior. Once it exists, assert the command exits 130 after reporting the same valid/invalid or registered recovery state used by modeled failures, leaves success-only archival unreachable, and preserves a disambiguated branch binding for the operator.

- **Treat successful validation and manifest publication as separate states.** Model a failure after successful `write_new_plan` and `parse_plan`, including concept synchronization before or during `append_to_manifest`. The retained file must contain the exact risk declaration selected by step 3, remain outside the manifest, and be reported as a parse-valid artifact whose explicit registration adopts it and ends the create retry without claiming tail completion; no pre-manifest path deletes the created target.

- **Keep registered-finalization failure distinct from adoption.** Model required concept-synchronization failure after `append_to_manifest`. The retained plan is already registered, so the failure report must identify an incomplete tail and never offer `register`; the operator owns any remaining concept repair. Separately model the existing `iteration_stage_failure` result as a completed create whose current summary, source archival, and continuation behavior remain unchanged.

- **Keep completion confirmation advisory.** Model `parse_plan(CreateResult.plan_path)` failure in step 4’s summary path. It must warn without changing the completed create outcome, archiving tail, or preserved branch binding; it is not a registered-finalization error.

- **Preserve branch ownership after an artifact exists.** Drive retained pre-manifest and registered-finalization artifacts, including postwrite interrupts, through the branch-aware `cmd_create` path. Assert that each remains bound to and leaves the operator on the selected disambiguated branch; a decision-gate failure or pre-write interruption with no target artifact still clears the temporary binding and restores the invoking branch.

- **Keep invalid retained artifacts distinct.** Model both an in-function final-write failure and the existing post-write reparse failure at `plan_tool/create.py:_publish_create_plan`. Each path must remain on disk and outside the manifest, but the failure report must identify it as invalid and direct the operator to repair or remove it rather than adopt it.

- **Prove retries do not decide recovery.** Re-run create against a retained unregistered plan without an explicit operator action. Assert that the collision path refuses to overwrite or archive the artifact and preserves its contents. Separately, drive `--from-existing` with that exact artifact and assert that its normal source-archive behavior is an explicit conversion into a replacement plan, not a retry. Do not use `replace_on_collision=True` in either regression: that escape hatch is outside the safe default recovery path.

- **Cover the CLI success boundary.** Drive `plan_tool/cli/authoring.py:cmd_create` through `plan_tool.cli.main(...)` with a created-artifact failure. Assert that its error output includes the retained path and recovery state, while the normal saved-tier summary, source archival, and distilled-artifact archival do not run.

- **Keep split handling unchanged.** Extend the existing `tests/test_distill.py:TestCreatePlanDistillThreading` and `TestCmdCreateDistillCli` coverage so a split proposal neither resolves a final risk declaration nor writes, registers, archives, or reports a partial plan. This is a safety assertion around the existing split boundary, not a change to split behavior.

- **Use the existing adoption command, not a new recovery API.** For every parse-valid pre-manifest retained plan, drive `plan_tool/cli/manifest.py:cmd_register` through `main(...)` and assert it can add the unchanged file to the manifest as explicit operator adoption. A same-target default collision must stop before it reuses the recovered attempt’s proposal or decision; a distinct predicted target and an explicitly authorized replacement both start with fresh risk state. For an interrupted stub or other invalid retained plan, assert the same command rejects it. Keep the pre-existing parser-specific register coverage intact.

## Tests

- `test_risk_checkpoint_failure_has_no_replacement_side_effects` — A decision-checkpoint write failure leaves plan writing, manifest mutation, collision archival, and source archival unreachable.
- `test_write_new_plan_partial_is_retained_unregistered_and_requires_repair` — A failure during final plan writing retains the deliberately non-structured target, reports repair guidance, and prevents registration.
- `test_postwrite_interrupt_is_retained_reported_and_branch_bound` — A Ctrl-C after a stub or complete target write exits 130 with matching recovery guidance and preserves the artifact binding; a pre-write Ctrl-C still restores the invocation branch.
- `test_valid_postwrite_partial_is_retained_unregistered_with_saved_declaration` — A failure after validation retains the exact persisted tier and rationale, leaves no manifest entry, and reports the artifact as valid.
- `test_pre_manifest_concept_sync_failure_retains_valid_artifact` — A concept-synchronization failure before manifest publication retains the parse-valid artifact and offers explicit adoption.
- `test_invalid_postwrite_partial_is_retained_unregistered_and_requires_repair` — A failed post-write reparse retains the plan path, reports invalid status, and prevents registration.
- `test_retry_refuses_to_overwrite_or_archive_retained_partial_without_explicit_recovery` — A default retry preserves a retained partial plan and points to explicit recovery rather than changing it.
- `test_from_existing_retained_partial_is_explicit_conversion_not_retry` — Naming a retained artifact as `--from-existing` exercises the documented conversion path and archives it only as the explicitly supplied source.
- `test_valid_retained_partial_can_be_registered_explicitly` — `main(...)` registers an unchanged valid retained plan through the existing `register` command.
- `test_registered_finalization_error_is_reported_without_adoption` — A concept-synchronization failure after manifest publication retains the registered plan, reports incomplete tail work, and does not offer adoption.
- `test_iteration_incomplete_remains_completed_registered_create` — An iteration-stage failure retains its existing completed-create summary, source archival, and continuation behavior.
- `test_branch_aware_retained_artifact_keeps_its_binding` — Retained pre-manifest and registered-finalization-error artifacts stay on their selected branch, while a decision-gate error restores the invocation branch.
- `test_risk_checkpoint_identity_prevents_cross_target_or_replacement_replay` — A same-target default collision stops before consuming risk state, while a priority- or directory-changed target or an explicit replacement resolves a fresh proposal and decision.
- `test_counter_signalled_seed_cannot_publish_low_when_model_omits_signal` — A full create with otherwise valid low evidence but any named-consumer, contract, migration, auth/authz, external, schema, API, or runtime-surface source counter-signal records `standard`; step 3 cannot persist the model’s low proposal.
- `test_distilled_single_registered_finalization_error_leaves_source_unarchived` — An unexpected finalization error after manifest publication keeps the original seed in place and creates no source or distilled-artifact archive.
- `test_split_proposal_bypasses_risk_resolution_publication_and_archival` — A split exits without a plan, declaration summary, manifest mutation, or source archive.
- `test_main_create_reports_registered_finalization_error_and_skips_success_tail` — The create command reports the registered retained path and recovery state without printing a success summary or running archival.
- `test_main_create_summary_read_failure_warns_and_completes` — A completion-summary read failure warns without changing success, branch binding, or source archival.
- `test_main_create_missing_saved_declaration_warns_and_completes` — A parse-valid legacy declaration omission warns without rendering a tier or changing success, branch binding, or source archival.

### Verification (non-code step)

This step has `change_type: non-code`, so the test-authoring gate for production feature or refactor steps does not apply. Verify the changed test artifacts with:

1. `uv run pytest tests/test_create.py tests/test_distill.py tests/cli/test_authoring_cmds.py -q`
2. `uv run pytest tests/ -q -n auto`
3. A review of captured output showing that valid and invalid retained artifacts receive different recovery guidance.
4. A review of the test fixtures confirming no case uses automatic deletion or overwrite as recovery, while explicit replacement and conversion retain their existing source-archive contract.

## Acceptance criteria

- A decision-checkpoint durability failure writes no new plan, changes no manifest entry, and leaves collision and source files unchanged.
- A partial artifact from a failure during final plan writing retains its path, stays unregistered, and is rejected by `register` until repaired.
- An interrupt before a target write exits 130 with the existing rollback; an interrupt after a target exists exits 130 while retaining, reporting, and preserving its recovery branch binding.
- A parse-valid pre-manifest partial retains its saved `risk_profile` and `risk_profile_rationale`, stays unregistered, and reports that explicit registration adopts it and ends the create retry without claiming tail completion.
- A pre-manifest concept-synchronization failure retains its created artifact and reports the same explicit recovery state; it never deletes that artifact automatically.
- An unexpected finalization error after manifest publication retains the registered plan and reports incomplete tail work without offering adoption; the existing iteration-incomplete result remains a completed registered create.
- Risk checkpoints never cross a full predicted target or an explicit replacement: a same-target default collision stops before reuse, while a priority- or directory-changed target or explicit replacement resolves fresh risk state.
- Any named-consumer, contract, migration, auth/authz, external, schema, API, or runtime-surface counter-signal in the selected seed prevents a low declaration even when the model’s response supplies all affirmative excerpts and omits that signal.
- A branch-aware retained artifact stays on its selected branch; only a no-artifact error or interruption before a target exists restores the invoking branch.
- An invalid later partial retains its path, stays unregistered, and is rejected by `register` until repaired.
- A normal retry does not overwrite, archive, or delete a retained partial artifact; `--from-existing` is separately tested as an explicit conversion that may archive its named source.
- An unexpected finalization error after manifest publication does not print the saved-tier success summary or archive the source or distilled artifact.
- A saved-tier confirmation read failure warns without changing a completed create’s success, branch ownership, or archival tail.
- A parse-valid plan with no saved declaration warns without rendering a tier, inferred fallback, or altered success tail.
- A split proposal remains a no-plan exit with no declaration resolution, manifest update, or source archive.
- `uv run pytest tests/test_create.py tests/test_distill.py tests/cli/test_authoring_cmds.py -q` and the plan test command pass.

## References

- [Models | Pydantic Docshttps: — Use for the typed-plan validation that separates valid from invalid retained artifacts.
- [PyYAML Documentationhttps: — Use for the YAML frontmatter parsing path exercised by retained-plan validation.

## Applicable guardrails

- **The plan’s “## Plan intent”, operator-owned signal:** Preserve the saved declaration through every retained-artifact case; tests must not treat a classifier proposal as the recoverable decision.
- **The plan’s “## Step intent”, manual post-write recovery:** Assert retained artifacts and explicit recovery guidance without adding a rollback or transaction mechanism.
- **The plan’s “## Out of scope”, non-TTY model acceptance:** Keep silent-path coverage on the explicit standard behavior from earlier steps; do not introduce model acceptance through a retry fixture.
- **The plan’s “## Out of scope”, existing-plan and split behavior:** Test existing split and registration boundaries without migrating plans or changing split, annotate, or scope-out behavior.
- **The plan’s “## Scope contract”, allowed behavior changes:** Limit this step to regression coverage for the permitted retained-artifact failure report and existing create surfaces.

## Deferred

- Automatic publication rollback or transaction support — BACKLOG #126 owns a broader recovery mechanism; this step only proves manual recovery remains safe.
- General publication transactions — the pre-manifest versus registered-tail recovery states preserve the existing manifest boundary rather than adding a transaction (BACKLOG #126).
- Downstream risk-tier consumption — The sibling risk-profile-2 work owns detail, audit, and apply behavior.
