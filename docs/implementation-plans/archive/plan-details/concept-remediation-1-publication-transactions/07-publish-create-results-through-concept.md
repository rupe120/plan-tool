# Step 7 — Publish create results through the concept authority

## Summary

This step routes `plan_tool/create.py:create_plan` through the typed, all-or-recoverable concept publication authority delivered by steps 2 and 3. It submits the final artifact bundle prepared by step 6, using distinct signed-decision and unsigned-proposal intents. The authority becomes the only publication path for the plan, concept record, manifest update, collision archives, detail-directory moves, and create-resume promotion. On green, create returns only after the whole bundle is verified, while failure restores the original state or reports every path whose state is uncertain.

## Table of Contents

- [Summary](#summary) — The create publication change and its observable result.
- [Why](#why) — Why create’s separate writers cannot provide safe recovery.
- [Input](#input) — The dependency-owned contracts and create state consumed here.
- [Files (creates vs edits)](#files-creates-vs-edits) — The source and test files changed by this step.
- [Implementation](#implementation) — Intent selection, authority handoff, result mapping, and required invariants.
- [Tests](#tests) — Focused cases for signed, unsigned, successful, and failed publication.
- [Acceptance criteria](#acceptance-criteria) — Observable proof that create uses one recoverable publication path.
- [References](#references) — Test guidance relevant to the orchestration seams.
- [Deferred](#deferred) — Publication work owned by other steps or requiring plan reconciliation.

## Why

`plan_tool/create.py:create_plan` currently performs collision archival, manifest removal, plan writing, detail-directory movement, concept synchronization or direct `save_concepts`, and manifest addition as separate live mutations. Its signed failure cleanup removes only the new plan and sidecar, while failures after an archive, detail move, manifest edit, or convergence update can leave a mixed state that the caller cannot restore reliably. Steps 3 and 6 provide the missing boundaries: one authority can now publish the complete prepared create bundle and preserve exact recovery information instead of asking create to coordinate several independent writers.

## Input

- **Step 2 output:** use the typed signed-decision and unsigned-proposal publication intents from `plan_tool/concept_sync.py`. Do not duplicate their approval, ownership, scope-prose, or concept-reference validation in `plan_tool/create.py`.
- **Step 3 output:** use the public all-or-recoverable publication entry point and its distinct success, conflict, invalid-state, restored-failure, and rollback-failed results. Preserve its uncertain-path set without re-deriving it.
- **Step 6 output:** begin from the write-free create artifact bundle and the injectable convergence runner. The bundle is materialized only in a private transaction candidate workspace, where any enabled iteration settles the final plan/detail generation before live publication.
- `plan_tool/create.py:_review_create_concepts` remains the source of the reviewed tree and explicit `Step.concept_ids` ownership accepted during interactive review.
- `plan_tool/create.py:CreateResult` remains the successful caller-facing result. Its `manifest_updated`, `plan_details_renamed_to`, `plan_details_skip_reason`, `replaced_archives`, `replaced_skipped`, and `replaced_manifest_entries` values must describe committed publication results, not planned or partially completed operations.
- `plan_tool/create.py:create_plan` must still preserve its pre-publication no-write exits, including collision refusal, invalid review state, placeholder rejection, and failed preparation.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `plan_tool/create.py` — replace create’s direct publication sequence with signed or unsigned intent construction, one authority call over step 6’s artifact bundle, and accurate result-to-`CreateError` mapping.
  - `tests/test_create.py` — add orchestration and integration coverage for successful publication, full restoration, rollback uncertainty, signed and unsigned intent selection, resume promotion, and removal of direct publication calls from `create_plan`.

## Implementation

The foundational logic is: **publish one final create bundle through exactly one typed authority request, or leave the original repository state recoverable**.

- **Choose the intent from review state.** In `plan_tool/create.py:create_plan`, use a signed-decision intent when the reviewed `ConceptTree` contains operator-approved decisions. Use an unsigned-proposal intent for `--yes`, non-TTY, and other unsigned outcomes. Do not infer the intent from backend injection, `input_fn` identity, or whether enrichment returned usable JSON.

- **Preserve signed ownership.** For a signed request, submit the reviewed tree and the settled plan produced from `reviewed_steps`. Keep the `Step.concept_ids` links assigned by `plan_tool/create.py:_review_create_concepts`; do not rebuild ownership from titles or from a single `source_metadata["step_id"]` value.

- **Keep unsigned proposals unsigned.** The unsigned request may publish proposed concepts, but it must not create approval or sign-off metadata. It must preserve the prepared plan’s existing `Deferred` and `Out of scope` prose rather than treating proposed decisions as scope authority.

- **Run convergence in a complete isolated repository snapshot.** Ask the step-3 authority to allocate/validate transaction staging, then create a disposable full-repository snapshot or equivalent isolated overlay with its own repository root and working directory. It must contain the production files, manifest, and configuration that `plan_tool.launcher:apply_finding` and deterministic validation resolve through `repo_root`, while placing the provisional plan and detail bundle at their canonical paths inside that snapshot. Invoke step 6’s extracted convergence runner with the snapshot root as both its process working directory and repository root; never pass the live repository root with staged detail paths. After iteration, reject any snapshot diff outside the allowlisted provisional plan/detail artifacts, copy only those settled candidate bytes back into transaction staging, reparse and revalidate them, rebuild the typed artifact actions and fingerprint inputs, and only then begin the single live commit. The incumbent plan, sidecar, manifest, archives, production files, and detail directory remain untouched during iteration.

- **Publish only the settled bundle.** Call the live commit entry point once after candidate iteration has finished. Do not publish an initial live plan and then use a second `synchronize_concepts` or `save_concepts` call to repair its fingerprint.

- **Use one publication call.** The request must include every operation represented by step 6’s bundle: the final plan and concept record, manifest replacement, collision archive changes, plan-details move, and create-resume promotion or cleanup. `plan_tool/create.py:create_plan` must not perform any of those live mutations before or after the authority call.

- **Remove direct concept publication from the create flow.** Both current `plan_tool/create.py:create_plan` branches that call `plan_tool/concept_sync.py:synchronize_concepts`, and both signed and unsigned post-iteration branches, must move to the new authority. The `create_plan` orchestration must also stop calling `plan_tool/concept_tree.py:save_concepts` directly.

- **Remove partial cleanup as a transaction substitute.** Delete the create-local failure path that unlinks `concepts_path(plan_path)` and the new plan after synchronization rejection. The authority’s restored-failure and rollback-failed results now describe the whole bundle; local two-file cleanup would hide or worsen recovery state.

- **Do not use legacy live-write helpers from `create_plan`.** `plan_tool/create.py:write_new_plan`, `archive_existing_source`, `rename_plan_details_to_slug`, `append_to_manifest`, and `remove_from_manifest` may remain as compatibility or preparation helpers where step 6 leaves them, but `create_plan` must not use them to mutate final targets outside the authority. Avoid deleting or changing their public behavior unless step 6 has already established that as part of its refactor.

- **Return only verified results.** Build `CreateResult` after the authority reports success. Populate its archive, manifest, and detail-move fields from the committed operation result or the already-prepared bundle as confirmed by that result; do not report an archive or manifest edit that recovery later reversed.

- **Map ordinary failures accurately.**
  - Reject conflict and invalid-state results with `CreateError` before returning a `CreateResult`.
  - Report a restored publication failure as failed create work whose original state was restored.
  - Report a rollback-failed result as an uncertain repository state and include every uncertain path returned by the authority.
  - Never describe rollback failure as “no files were changed,” and never replace the authority’s path set with only the first failed operation.

- **Keep resume state retryable.** Step 5’s compatible unsigned resume record must be promoted to the final concept sidecar only as part of successful publication. A validation failure or restored publication failure must leave compatible resume progress available for a retry and must not expose it at `plan_tool/concept_tree.py:concepts_path` as finalized state.

- **Preserve early no-write behavior.** Failures before the authority call must leave the incumbent plan, its `plan-details` directory, its concept record, archive targets, and the manifest unchanged. This includes `plan_tool/create.py:_find_placeholder_body_sections`, concept-review errors, bundle validation, and collision decisions that decline replacement.

- **Respect the repository lock contract.** Use the step-3 command-facing entry point appropriate for an already locked mutating command. Do not acquire `plan_tool/repo_lock.py:repo_mutation_lock` again inside `create_plan`; the lock is non-reentrant. Direct library calls should use the step-3 wrapper intended for callers that do not already own the lock.

- **Keep authority tests at the caller boundary.** Inject or monkeypatch the step-3 publication entry point in `tests/test_create.py` to test request selection and result mapping. Do not reproduce journal, `fsync`, replacement-order, or recovery algorithms here; those remain covered by `tests/test_concept_sync.py` under step 3.

## Tests

- `tests/test_create.py:test_create_submits_signed_bundle_to_publication_authority` — an interactive approved review produces one signed request containing the final plan, reviewed tree, ownership links, and complete step-6 artifact bundle.
- `tests/test_create.py:test_create_submits_unsigned_bundle_for_unattended_review` — `--yes` and non-TTY review produce an unsigned request with no approval or sign-off metadata.
- `tests/test_create.py:test_create_calls_publication_authority_once_after_iteration` — enabled iteration finishes before one publication call, with no later synchronization or sidecar save.
- `tests/test_create.py:test_create_iteration_mutates_only_transaction_candidate` — enabled iteration rewrites the private candidate plan/details while the incumbent plan, sidecar, manifest, archive, and detail paths retain their original bytes.
- `tests/test_create.py:test_create_iteration_uses_complete_isolated_repo_root` — the convergence runner resolves declared production files from the disposable snapshot, uses that snapshot for both cwd and `repo_root`, and rejects an iteration diff outside the provisional plan/detail allowlist.
- `tests/test_create.py:test_create_revalidates_settled_candidate_before_commit` — iteration output is reparsed, its typed artifact set and final fingerprint are rebuilt, and invalid output stops before live mutation.
- `tests/test_create.py:test_create_success_returns_only_committed_artifact_results` — `CreateResult` reports the verified plan path, manifest update, archives, detail move, and removed manifest entries from the successful bundle.
- `tests/test_create.py:test_create_signed_success_publishes_matching_plan_and_concept_fingerprint` — the committed plan contains the accepted `concept_ids`, and the final concept record identifies the exact published plan generation.
- `tests/test_create.py:test_create_unsigned_success_preserves_scope_prose` — unsigned publication retains prepared `Deferred` and `Out of scope` bodies and persists only unsigned proposals.
- `tests/test_create.py:test_create_conflict_writes_nothing` — an authority conflict returns `CreateError` without publishing the plan, sidecar, manifest, archives, or detail move.
- `tests/test_create.py:test_create_restored_failure_restores_full_original_bundle` — failure after live publication begins restores original bytes and existence for the incumbent plan, concept record, manifest, archive targets, and detail directory.
- `tests/test_create.py:test_create_rollback_failure_reports_every_uncertain_path` — the raised error contains the authority’s complete uncertain-path set and does not claim successful restoration.
- `tests/test_create.py:test_create_failure_keeps_compatible_resume_state` — rejected or restored publication leaves step 5’s compatible review progress available and does not promote it to the final sidecar.
- `tests/test_create.py:test_create_success_promotes_resume_only_inside_publication` — successful publication installs the finalized concept record and removes or completes the resume artifact as one committed bundle.
- `tests/test_create.py:test_create_plan_has_no_legacy_concept_publication_calls` — the `create_plan` path does not call `synchronize_concepts`, `save_concepts`, or raw `concepts_path` cleanup.
- `tests/test_create.py:test_create_preparation_failure_does_not_call_publication` — placeholder, invalid-review, and bundle-preparation failures leave the authority uncalled and all durable state unchanged.
- `tests/test_create.py:test_create_does_not_reacquire_repo_mutation_lock` — command-owned publication uses the step-3 locked-caller contract without nested lock acquisition.

### Test-creation order (feature step)

1. Add signed-versus-unsigned request tests and the once-only authority-call test.
2. Add successful bundle publication tests for plan, concept fingerprint, manifest, archives, details, and `CreateResult`.
3. Add conflict and pre-publication no-write tests.
4. Add restored-failure coverage comparing every original artifact’s bytes and existence.
5. Add rollback-failed reporting with more than one uncertain path.
6. Add resume promotion and retry-preservation tests.
7. Add the source-boundary and no-nested-lock tests.

Every new test in `tests/test_create.py` must be green before this step is considered finished.

## Acceptance criteria

- Interactive approved create review submits one signed-decision publication intent.
- `--yes` and non-TTY create review submit an unsigned-proposal publication intent and do not create approval metadata.
- `create_plan` performs exactly one live publication commit for a completed create, including when iteration is enabled; all iteration happens in a complete authority-owned isolated repository snapshot first, with only allowlisted settled plan/detail bytes imported into staging.
- The request covers the final plan, concept record, manifest mutation, collision archives, plan-details move, and resume-state promotion prepared by step 6.
- `create_plan` returns `CreateResult` only after the authority verifies successful publication.
- A successful signed create publishes accepted `Step.concept_ids` and a concept fingerprint matching the exact final plan generation.
- A successful unsigned create preserves `Deferred` and `Out of scope` prose and publishes no signed decisions.
- A conflict, invalid request, or preparation failure leaves all live artifacts unchanged.
- A recoverable failure restores the original contents and existence of every artifact in the bundle.
- A rollback-failed result raises `CreateError` containing every uncertain path returned by the authority.
- Failed publication does not promote resume state to `plan_tool/concept_tree.py:concepts_path`; compatible resume progress remains available after a restored failure.
- `plan_tool/create.py:create_plan` no longer calls `synchronize_concepts`, `save_concepts`, or direct concept-sidecar cleanup.
- `create_plan` does not reacquire the repository mutation lock held by mutating CLI dispatch.
- All focused tests in `tests/test_create.py` pass.

## References

- [pytest — Monkeypatching functions and environments](https://docs.pytest.org/en/stable/how-to/monkeypatch.html) — Use an injected publication authority and controlled result variants to test create orchestration without duplicating coordinator internals.

## Deferred

- Typed publication intents and validation — step 2 owns these contracts in `plan_tool/concept_sync.py`.
- Durable staging, journals, restart recovery, final-byte verification, restoration, and uncertain-path calculation — step 3 owns the common publication authority.
- Create review resume format and terminal-driven approval — step 5 owns those contracts in `plan_tool/concept_tree.py` and `plan_tool/create.py`.
- Write-free create artifact preparation — step 6 owns the final bundle and preserves existing create behavior before this publication change.
- Direct-write enforcement across all production callers — step 12 owns the repository-wide source check.
- CLI mutation-lock handoff — this step relies on the step-3 command-facing contract and the existing lock around `plan_tool/cli/app.py:main`; if the implemented authority requires a new token parameter through `plan_tool/cli/app.py` or `plan_tool/cli/authoring.py`, reconcile the plan’s file ownership before implementation instead of reacquiring the lock in `plan_tool/create.py`.
- Detail and scope-out publication migration — steps 9 and 11 move those callers to the same authority.
- General repository transactions — the authority remains limited to concept-related publication artifacts and intents.
