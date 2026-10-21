# Step 6 — Bound and deduplicate include-triggered detail regeneration

## Summary

Bound include-triggered regeneration in `plan_tool/detail.py:generate_detail` to one authoring slot per affected step and the existing `_MAX_INVOKE_ATTEMPTS` limit per slot. Build one ordered regeneration cohort from approved included concepts, share it across serial and concurrent authoring, and prevent recursive authoring from rediscovering the same triggers during the call. Treat every required regeneration as a precondition for publication through the prerequisite publication contract. On green, duplicate links cannot cause duplicate backend calls, and any unresolved response leaves the prior details, pointers, archives, and concept record unchanged.

## Table of Contents

- [Summary](#summary) — The bounded regeneration behavior and observable result.
- [Why](#why) — Why the current partial implementation can still repeat work or publish an incomplete update.
- [Input](#input) — The concept metadata and dependency-step contracts consumed here.
- [Files (creates vs edits)](#files-creates-vs-edits) — The two existing files changed by this step.
- [Implementation](#implementation) — Target collection, attempt bounds, publication gating, and failure reporting.
- [Tests](#tests) — Serial, concurrent, recursive, failure, and no-write cases.
- [Acceptance criteria](#acceptance-criteria) — Checks that prove regeneration is bounded and recoverable.
- [Deferred](#deferred) — Lifecycle transformations and publication mechanics owned elsewhere.

## Why

`plan_tool/detail.py:_included_deferral_step_ids` already returns a set, and `generate_detail` adds affected steps without duplicating an explicitly selected step, so basic deduplication is partly present. `tests/test_detail.py:TestStructuredDetailDeferrals` also covers one include transition, one failed replacement, dry-run, and ordered concurrent saves. The remaining boundary is incomplete: trigger identity is discarded, serial and concurrent paths do not prove the same one-call limit, recursive `generate_detail` calls can rediscover links that remain durable until publication, and exhausted parsing reports only a generic failure. The command needs one bounded include cohort whose unresolved candidates stop publication and preserve the complete last known-good generation.

## Input

- **Include-trigger metadata:** `plan_tool/detail.py:_concept_deferral_step_ids` reads the compact `detail_deferral_step_ids` list from `plan_tool/concept_tree.py:ConceptNode`. Only concepts with `review_state == "approved"` and `decision == "include"` may trigger regeneration.
- **Current routing rule:** `plan_tool/detail.py:_included_deferral_step_ids` filters links to step IDs present in the parsed `Plan`. Preserve that invalid-link tolerance; structural remapping is not part of this step.
- **Step 3 outcome:** consume strict `parse_structured_detail_response` validation. A contradictory or malformed response returns `None` and must remain on the bounded retry path.
- **Step 4 outcome:** every fresh or resumed authoring result uses the structured envelope. Do not restore a Markdown-only fallback for include-triggered work.
- **Step 5 outcome:** replacement failure restores the prior active detail. This step extends the no-change guarantee across the whole include-triggered cohort.
- **Prerequisite publication outcome:** consume the prepared-detail and recoverable publication contracts from `concept-remediation-1-publication-transactions` steps 8 and 9. Workers prepare validated artifacts; the serial parent decides whether the complete cohort is eligible for one publication request.

## Files (creates vs edits)

- **New files:**

  - None.

- **Existing files (edits only):**

  - `plan_tool/detail.py` — retain trigger-to-concept context, deduplicate and order the regeneration cohort, enforce a call-scoped attempt limit, gate publication on complete preparation, and report unresolved candidates.
  - `tests/test_detail.py` — add serial, concurrent, recursive, multi-concept, exhaustion, publication-failure, dry-run, and command-result coverage.

## Implementation

The foundational logic is **one bounded authoring slot per distinct include-affected step, followed by publication only when the full required cohort is valid**.

- **Keep trigger context until the result is final.** Replace or supplement `plan_tool/detail.py:_included_deferral_step_ids` with a write-free collection that associates each affected step ID with the approved included concept IDs that caused it. Deduplicate both step IDs and concept IDs while preserving plan step order and concept-tree order.

- **Build one target list.** In `plan_tool/detail.py:generate_detail`, merge the operator-selected targets with the include-triggered cohort by step ID. A step selected explicitly and referenced by several included concepts must still appear once.

- **Bound authoring per step.** Give each distinct affected step one call to `plan_tool/detail.py:_author_step_detail`. Its backend work remains capped by `_MAX_INVOKE_ATTEMPTS`; do not add an outer retry loop that starts a second authoring slot after exhaustion.

- **Carry call-scoped regeneration state through recursion.** The recursive `generate_detail` calls used after structural split handling must not reload and enqueue the same include-triggered cohort again during the parent call. One reasonable approach is a private call-state object containing the initially discovered triggers and attempted step IDs. Keep this internal so the public `generate_detail` result remains `list[DetailResult]`.

- **Use the same cohort for both execution modes.** Pass the deduplicated ordered targets into the serial loop and `plan_tool/detail.py:_generate_detail_concurrent`. Worker completion order must not affect dispatch count, final result order, or the prepared publication request.

- **Do not reuse checkpoints for forced include refreshes.** Keep the existing `regeneration_step_ids` behavior that bypasses cached bodies for include-triggered steps. A checkpoint created before the include decision cannot prove that the new decision was incorporated.

- **Require complete preparation before publication.** When include triggers are present, the serial parent must receive a valid prepared outcome for every required affected step before submitting the cohort through the prerequisite publication authority. A parse failure, contradictory deferral, preparation failure, or raised command-level authoring error must prevent publication of the newly prepared cohort.

- **Preserve the full prior generation on failure.** Before a successful publication, do not replace active detail bytes, update `step.detail`, move an old file into an archive, remove deferral links, discard checkpoints, or run success-only callbacks. A recoverable publication failure must restore the prior details, pointers, archive state, and concept record exactly.

- **Report unresolved candidates clearly.** On exhausted parsing or another non-publishable prepared outcome, identify the affected step and the included concept IDs that triggered it in the returned failure reason or existing reporting surface. State that regeneration was not published and that the existing deferral links remain available for retry. Do not turn the failure into another automatic regeneration pass.

- **Remove links only after verified publication.** Let the prerequisite publication request apply the ordered deferral replacement for successfully regenerated steps. Never clear `detail_deferral_step_ids` merely because a step was dispatched or produced an intermediate body.

- **Keep unrelated siblings unchanged.** A targeted call may add include-affected steps to its work set, but it must not regenerate other completed steps. Failure in the required cohort must not alter an unrelated sibling’s active detail, pointer, or archive.

- **Preserve dry-run behavior.** Dry-run may render one prompt per deduplicated target and explain why an include-triggered step was added, but it must not invoke the backend, consume an attempt, publish, archive, update pointers, or change concept metadata.

- **Keep malformed routing data fail-soft.** Continue ignoring missing, non-integral, duplicate, and no-longer-present step IDs when collecting triggers. This step bounds valid routing; it does not invent an owner or target from titles.

## Tests

Tests in `tests/test_detail.py`:

- `test_include_regeneration_deduplicates_multiple_concepts_for_one_step` — several included concepts linked to one step produce one authoring slot and one ordered result.
- `test_include_regeneration_deduplicates_explicit_and_triggered_target` — an explicitly selected affected step is invoked once.
- `test_include_regeneration_orders_distinct_steps_by_plan_order` — duplicate and out-of-order metadata still yield one deterministic cohort.
- `test_include_regeneration_is_bounded_by_max_invoke_attempts` — repeated contradictory responses stop after `_MAX_INVOKE_ATTEMPTS` for each affected step.
- `test_include_regeneration_does_not_rediscover_triggers_in_recursive_authoring` — nested `generate_detail` work does not enqueue an already attempted include cohort again.
- `test_include_regeneration_bypasses_matching_checkpoint` — an affected step invokes fresh authoring instead of accepting a pre-decision cached body.
- `test_serial_include_regeneration_invokes_each_affected_step_once` — serial execution has one worker call per distinct affected step.
- `test_concurrent_include_regeneration_invokes_each_affected_step_once` — `jobs > 1` has the same dispatch membership and ordered results as serial execution.
- `test_include_regeneration_contradiction_reports_step_and_concepts` — exhaustion names the affected step and triggering concept IDs and explains that publication did not occur.
- `test_include_regeneration_failure_preserves_complete_prior_generation` — a failed required sibling leaves every active detail, plan pointer, archive path, checkpoint, and concept artifact unchanged.
- `test_include_regeneration_publishes_complete_cohort_once` — all valid prepared outcomes enter one ordered publication request and clear only their obsolete links after verified success.
- `test_include_regeneration_publication_failure_restores_complete_prior_generation` — a recoverable publisher failure restores all prior artifact bytes and retains the trigger links.
- `test_include_regeneration_rollback_failure_reports_uncertain_paths` — an unverified restoration returns not-written results with the publisher’s complete uncertainty report.
- `test_include_regeneration_preserves_unrelated_siblings` — completed steps outside the selected and triggered sets are neither authored nor changed.
- `test_include_regeneration_dry_run_is_deduplicated_and_read_only` — dry-run emits one prompt per affected step and changes no durable or checkpoint state.
- `test_invalid_or_removed_trigger_step_ids_are_not_dispatched` — malformed and unknown routing values cannot create an authoring target.

### Test-creation order (feature step)

1. Add multi-concept and explicit-target deduplication tests.
2. Add deterministic target-order and invalid-link tests.
3. Add the exact `_MAX_INVOKE_ATTEMPTS` exhaustion test.
4. Add serial and concurrent once-per-step dispatch tests.
5. Add recursive rediscovery and checkpoint-bypass tests.
6. Add complete-cohort success and unresolved-candidate reporting tests.
7. Add prior-generation preservation tests for authoring and recoverable publication failures.
8. Add rollback-failure, unrelated-sibling, and dry-run tests.

Every new test in `tests/test_detail.py` must be green before this step is considered finished.

## Acceptance criteria

- One `generate_detail` call invokes `plan_tool/detail.py:_author_step_detail` at most once per distinct include-affected step.
- One affected step receives no more than `_MAX_INVOKE_ATTEMPTS` backend calls, including contradictory structured responses.
- Multiple included concepts and an explicit `step_id` cannot duplicate a target.
- Serial and concurrent modes use the same ordered affected-step set and produce the same publication membership.
- Recursive authoring during the call does not rediscover and requeue an already attempted include trigger.
- Include-triggered steps do not resume from checkpoints created before the include refresh.
- A publication request is made only after every required affected step has a valid prepared outcome.
- Successful regeneration publishes the complete ordered cohort once and removes obsolete links only after verification.
- Exhausted or contradictory authoring reports the affected step and triggering concept IDs without starting another regeneration pass.
- Authoring failure, command-level failure, dry-run, and recoverable publication failure preserve all prior active detail bytes, plan pointers, archive state, checkpoints, and concept bytes.
- A rollback failure reports every uncertain path and does not claim either generation was written successfully.
- Unrelated sibling details are neither invoked nor changed.
- All existing and new tests in `tests/test_detail.py` pass.

## Deferred

- Split, merge, scope-out, and re-ground remapping of `detail_deferral_step_ids` — stable lifecycle accounting belongs to `concept-remediation-3-ownership-lifecycle-accounting`.
- Publication-authority implementation and direct-writer removal — `concept-remediation-1-publication-transactions` owns the prepared-write and recoverable publication mechanisms consumed here.
- Semantic review of whether prose fully explains an included concept — this step validates the structured authoring contract and bounded orchestration; it does not add another model judgment.
- Repair of malformed or dangling deferral links — this step ignores unsafe routing values rather than guessing a replacement owner.
