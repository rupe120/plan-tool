# Step 5 — Publish detail accounting changes only after regeneration is durable

## Summary

This step makes `plan_tool/detail.py:generate_detail` publish include-triggered detail regeneration and its accounting change as one durable generation. It consumes the non-delivery contract from step 2, the reviewed transition behavior from step 3, and the existing concept publication authority rather than adding another writer. `tests/test_detail.py` covers serial, concurrent, partial-failure, restored-failure, and uncertain-publication cases; `tests/cli/test_authoring_cmds.py` verifies the command reports those outcomes honestly. On green, resolved non-delivery accounting disappears only when the replacement detail and plan pointer are verified durable.

## Table of Contents

- [Summary](#summary) — Overview of the durability rule and observable result.
- [Why](#why) — Why accounting must not move ahead of its replacement artifact.
- [Input](#input) — Dependency contracts and existing publication results consumed here.
- [Files (creates vs edits)](#files-creates-vs-edits) — Scoped production and test changes.
- [Implementation](#implementation) — Required ordering, failure behavior, and integration points.
- [Tests](#tests) — Feature coverage for publication and command outcomes.
- [Acceptance criteria](#acceptance-criteria) — Observable checks that define completion.
- [References](#references) — Authoritative test guidance relevant to the failure matrix.
- [Deferred](#deferred) — Other lifecycle transformations owned by later steps.

## Why

An `include` transition can require a detail to be regenerated before its old non-delivery accounting is no longer true. Removing that accounting during review or saving it separately after a detail write creates a window where the concept claims delivery without a durable replacement, or where new detail bytes coexist with old accounting. `plan_tool/detail.py:generate_detail` already distinguishes successful and failed authoring and has serial tails for both ordinary and concurrent generation, but this step must connect the new records from steps 2 and 3 to the existing recoverable publication boundary. The result must preserve the prior accounting on every failed or restored regeneration and report uncertainty instead of guessing when rollback cannot be verified.

## Input

- **Step 2 outcome:** consume the durable non-delivery record and its shared, write-free accounting preparation helpers. Do not reintroduce `ConceptNode.source_metadata["detail_deferral_step_ids"]` parsing or define another persisted record shape in `plan_tool/detail.py`.
- **Step 3 outcome:** consume the reviewed transition state that identifies an `include` change whose prior non-delivery record remains pending until replacement detail is durable. Do not repeat the operator-review or approval rules in this step.
- **Prepared detail contract:** use the write-free successful outcome carried between `plan_tool/detail.py:_author_step_detail`, `plan_tool/detail.py:_generate_detail_concurrent`, and `plan_tool/detail.py:generate_detail`. Invalid responses, declined replacements, and dry runs provide no publishable replacement.
- **Publication contract:** use the existing all-or-recoverable concept publication authority. Preserve its verified-success, restored-failure, and rollback-failed distinctions, including its complete uncertain-path report.
- **Result contract:** `plan_tool/detail.py:DetailResult.written` may be true only after the corresponding detail, plan pointer, and accounting candidate are verified as the committed generation.
- **CLI contract:** `plan_tool/cli/authoring.py:cmd_detail` derives exit status, summary output, completeness follow-up, and commit behavior from `DetailResult`; this step tests that boundary without editing the CLI module.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `plan_tool/detail.py` — carry pending accounting transitions through authoring, include them in the existing publication request, and map publication outcomes to per-step results without a direct accounting save.
  - `tests/test_detail.py` — add the serial, concurrent, partial-authoring, publication-failure, rollback-uncertainty, checkpoint, and dry-run coverage for the new records.
  - `tests/cli/test_authoring_cmds.py` — verify `cmd_detail` returns failure and suppresses success-only follow-up when publication is restored or uncertain.

## Implementation

The foundational logic is: **remove resolved non-delivery accounting only in the same verified publication that makes its replacement detail durable.**

- **Keep the old record until publication succeeds.** In `plan_tool/detail.py:generate_detail`, treat the persisted concept record loaded for the run as the original compare-and-swap snapshot. An `include` transition may select a step for regeneration, but it must not mutate or publish that original record before a valid replacement detail is ready.

- **Use the dependency-owned accounting preparation.** After authoring completes, pass the successful prepared outcomes to the helper delivered by step 2 to build the candidate accounting state. The candidate should remove or replace only records tied to successfully prepared details and preserve unrelated records exactly. Do not infer accounting from titles, Markdown text, or mutable step numbers when the dependency contract provides stable record or artifact identity.

- **Publish the replacement as one generation.** Add the candidate accounting change to the publication request already assembled by `plan_tool/detail.py:generate_detail`. The same request must contain the prepared detail bytes, the resulting `step.detail` pointer, any required active-detail replacement operation, and the candidate concept record. Do not restore the old pattern represented at HEAD by the final direct `save_concepts` tail or by per-step `update_step_detail_field` calls on concept-backed runs.

- **Update both authoring paths at their shared serial boundary.** The ordinary `generate_detail` loop and `_generate_detail_concurrent` produce prepared outcomes differently, but accounting preparation and publication must happen once after either path has finished. Concurrent workers must never update the shared concept record, and worker completion order must not affect record ordering or the final request.

- **Publish only the successful subset.** A parse failure, detail preparation failure, declined replacement, or skipped step must retain its previous detail, pointer, and non-delivery record. Successful siblings may form the publication subset in deterministic plan-step order if the existing authority supports that established behavior.

- **Handle verified success explicitly.** Only after the publication authority verifies every target may `generate_detail` return `DetailResult(written=True)` for those prepared steps. At that point the new detail and plan pointer are durable, and the old non-delivery record may be absent from the committed concept record.

- **Handle restored failure explicitly.** If publication fails and the authority verifies restoration, mark every prepared member of that request not written and state that the prior generation was restored. The old non-delivery accounting, prior detail, and prior pointer must remain the durable state.

- **Handle rollback failure without guessing.** If the authority cannot verify restoration, mark every prepared member not written and carry its uncertain paths in the failure reason or structured result surface already supplied by the publication contract. Do not claim that the old accounting remains or that the new detail won.

- **Preserve recovery state.** Keep authoring checkpoints and suppress success-only lesson extraction, scenario emission, and `commit_step` callbacks until verified publication. This maintains the existing prepared-response recovery path when accounting publication does not complete.

- **Keep `DetailResult` authoritative for the CLI.** Ensure failed and uncertain publication outcomes have a non-idempotent `skipped_reason`, so `plan_tool/cli/authoring.py:cmd_detail` returns a nonzero status. The command must not run its completeness tail, next-step success guidance, grounding update, or commit path for a failed publication.

- **Keep dry-run read-only.** A dry run may show that an include transition would regenerate a detail, but it must not prepare or submit a publication request and must leave detail, plan, concept, checkpoint, and archive bytes unchanged.

- **Do not add another transaction layer.** The rejected alternative is a detail-specific save-and-rollback sequence in `plan_tool/detail.py`. It would duplicate the publication authority and could disagree with its stale-state, recovery, durability, and uncertainty rules.

## Tests

- `test_include_regeneration_publishes_detail_pointer_and_accounting_together` in `tests/test_detail.py` — verified success commits the replacement detail, its plan pointer, and removal of the resolved non-delivery record in one request.
- `test_failed_include_authoring_retains_prior_accounting_and_detail` in `tests/test_detail.py` — an invalid or failed response leaves the old detail, pointer, and record unchanged.
- `test_include_publication_restored_failure_retains_prior_generation` in `tests/test_detail.py` — a caught publication failure restored by the authority reports not written and preserves every original artifact.
- `test_include_publication_rollback_failure_reports_uncertain_paths` in `tests/test_detail.py` — an unverified rollback reports every uncertain path and does not claim either generation is durable.
- `test_mixed_authoring_updates_accounting_only_for_successful_steps` in `tests/test_detail.py` — successful siblings publish in step order while failed steps retain their old records.
- `test_concurrent_include_regeneration_submits_one_ordered_publication` in `tests/test_detail.py` — `jobs > 1` produces one serial publication request independent of worker completion order.
- `test_concept_backed_detail_does_not_call_direct_accounting_writers` in `tests/test_detail.py` — the transaction path succeeds when legacy direct plan and concept writers are patched to fail if called.
- `test_include_publication_failure_retains_checkpoint_and_success_side_effects` in `tests/test_detail.py` — failed publication keeps recovery data and emits no success-only callbacks.
- `test_include_dry_run_changes_no_artifact` in `tests/test_detail.py` — dry-run reports intended regeneration without a publication request or filesystem change.
- `test_cmd_detail_returns_one_for_restored_publication_failure` in `tests/cli/test_authoring_cmds.py` — a restored publication failure is summarized as failed and returns exit status 1.
- `test_cmd_detail_reports_uncertain_publication_and_skips_success_tail` in `tests/cli/test_authoring_cmds.py` — uncertain paths reach command output while completeness, next-step, grounding, and commit success paths remain silent.
- `test_cmd_detail_verified_publication_keeps_success_behavior` in `tests/cli/test_authoring_cmds.py` — verified publication still reports written output and permits the existing success tail.

### Test-creation order (feature step)

1. Add the successful include-regeneration publication test and the failed-authoring retention test with the implementation.
2. Add restored-failure and rollback-failed publication tests.
3. Add mixed-success and concurrent-order tests.
4. Add direct-writer exclusion, checkpoint, and success-side-effect tests.
5. Add the dry-run regression test.
6. Add the three `cmd_detail` result-routing tests in `tests/cli/test_authoring_cmds.py`.

Every new test must be green before this step is considered finished.

## Acceptance criteria

- An include-triggered regeneration removes its prior non-delivery record only in the verified publication that commits the replacement detail and `step.detail` pointer.
- Failed or skipped authoring leaves the affected step’s prior detail, pointer, and accounting unchanged.
- A restored publication failure returns `DetailResult.written=False` and preserves the full prior generation.
- A rollback-failed publication returns `DetailResult.written=False` and reports all uncertain paths without claiming a durable winner.
- Serial and concurrent authoring submit the same successful subset in deterministic step order.
- Concept-backed detail publication does not directly call `save_concepts` or perform per-step plan-pointer publication outside the existing authority.
- Checkpoints and success-only callbacks are released only after verified publication.
- Dry-run submits no publication request and changes no persisted artifact.
- `plan_tool/cli/authoring.py:cmd_detail` returns status 1 for restored or uncertain publication failures and skips its success-only tail.
- Focused tests in `tests/test_detail.py` and `tests/cli/test_authoring_cmds.py` pass.

## References

- [pytest: How to Parametrize Fixtures and Test Functions](https://docs.pytest.org/en/stable/how-to/parametrize.html) — Use parametrized failure injection to cover each publication stage and its restored or uncertain outcome.

## Deferred

- Split and merge accounting transformation — later lifecycle steps map durable non-delivery records across structural step changes.
- Blocking completeness policy — step 5 decides how missing, contradictory, unsigned, and dangling accounting affects findings.
- Scope-out publication — the scope-out lifecycle step owns final-owner loss and its reviewed non-delivery publication.
- Re-ground and seed restoration — later steps carry and restore accounting through their machine-readable envelopes.
- Transaction-aware per-step Git attribution — one multi-step publication is one durable generation; changing commit grouping needs separate CLI and repository-history design.
