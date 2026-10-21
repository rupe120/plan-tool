# Step 9 — Publish detail files and deferrals together

## Summary

This step changes `plan_tool/detail.py:generate_detail` so concept-backed detail generation publishes the prepared detail files, plan pointers, archive moves, and concept deferral links through the publication authority delivered by step 3. It consumes the write-free authoring results from step 8 and keeps successful results in deterministic step order. The key design decision is to submit one publication request for the successful prepared subset instead of writing detail files first and saving deferrals afterward. On green, publication either verifies the complete new generation, restores the prior generation, or reports every path whose state is uncertain.

## Table of Contents

- [Summary](#summary) — The transaction boundary and observable result.
- [Why](#why) — Why separate detail and deferral writes leave mixed state.
- [Input](#input) — Contracts consumed from dependency steps and current detail parsing.
- [Files (creates vs edits)](#files-creates-vs-edits) — The source and test files changed here.
- [Implementation](#implementation) — Publication assembly, ordering, failure mapping, and side-effect rules.
- [Tests](#tests) — Feature coverage for success, recovery, concurrency, and failure.
- [Acceptance criteria](#acceptance-criteria) — Checks that prove the publication boundary works.
- [References](#references) — Test guidance used for controlled failure seams.
- [Deferred](#deferred) — Related work that remains outside this step.

## Why

`plan_tool/detail.py:generate_detail` currently writes each Markdown file, updates its `step.detail` pointer, and only later calls `plan_tool/concept_tree.py:save_concepts` for the combined deferral replacement. A failure in that tail can leave new detail text and plan pointers paired with old deferral links, while a plan-update failure can leave an unreferenced detail file that requires manual cleanup. Step 8 separates authoring from persistence, and step 3 supplies the recoverable publication boundary, so this step can remove that mixed-generation window without changing detail parsing or deferral policy.

## Input

- **Step 3 publication authority.** Use the typed, all-or-recoverable publication entry point produced by step 3. This step must consume its success, restored-failure, and rollback-failed outcomes without duplicating its staging, journal, durability, recovery, or lock validation.
- **Step 8 prepared writes.** Consume the write-free detail outcomes produced by step 8. Do not move file writes back into `plan_tool/detail.py:_author_step_detail` or `plan_tool/detail.py:_generate_detail_concurrent`.
- **Structured response contract.** Preserve `plan_tool/detail.py:parse_structured_detail_response`, `plan_tool/detail.py:ParsedDetailResponse`, and `plan_tool/detail.py:DetailDeferral`. The transport envelope stays out of the Markdown file, and invalid or unauthorized concept IDs remain an authoring failure rather than a publication request.
- **Result contract.** Preserve `plan_tool/detail.py:DetailResult` as the operator-facing per-step result. A result may claim `written=True` only after the publication authority verifies the committed generation.
- **Legacy plans.** Plans without a concept record cannot publish concept deferrals. Keep their existing detail-only behavior unless step 3 provides an explicit intent for that shape; do not create an empty concept record here.
- **Lock availability.** This step assumes step 3 exposes an entry point that `plan_tool/detail.py:generate_detail` can call without reacquiring the repository’s non-reentrant mutation lock. Reconcile the plan before implementation if that dependency outcome is not available.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `plan_tool/detail.py` — assemble the successful prepared detail outcomes into one concept publication request, remove direct concept-backed detail and deferral writes, map publication outcomes into `DetailResult`, and move post-publication side effects behind verified success.
  - `tests/test_detail.py` — replace direct-save expectations with transaction-level success, recovery, rollback-failure, ordering, checkpoint, archive, and callback coverage.

## Implementation

The foundational logic is **one publication request commits the successful prepared detail subset, its plan pointers, and its ordered deferral replacement as one verified generation**.

- **Publish once per authoring boundary.** In `plan_tool/detail.py:generate_detail`, collect the successful prepared outcomes from both the serial path and `plan_tool/detail.py:_generate_detail_concurrent`. Submit them in final step order after authoring has completed. Recursive generation after a structural split may form a separate boundary, but workers must never publish independently.

- **Publish only successful preparations.** Exclude parse failures, declined replacements, dry-run results, and other non-written outcomes from the request. Their old detail files, plan pointers, and deferral links must remain unchanged. A batch may therefore publish the successfully prepared subset even when another step failed before publication.

- **Build one target generation.** Starting from the current publication snapshot, apply every successful `step.detail` pointer to one candidate plan, include the corresponding prepared Markdown bytes, and use the shared deferral preparation delivered by step 1 to replace links in deterministic step order. Preserve unrelated concept metadata and old links for excluded steps.

- **Keep the original and candidate roles separate.** Pass the durable pre-publication plan and concept snapshots as compare-and-swap inputs. Pass the rendered plan, prepared detail bytes, archive operations, and prepared concept tree as targets. Never compare current durable state with the edited candidate.

- **Use final detail bytes for the fingerprint.** Populate step 2’s artifact contract with every written/replaced/removed detail candidate plus compare-and-swap snapshots of unchanged ordered details. The step-3 coordinator must fingerprint the exact candidate plan bytes together with that final ordered set and recheck unchanged inputs immediately before commit. Do not call `plan_tool/review_persistence.py:compute_plan_fingerprint` against a partially published filesystem or stamp a fingerprint after commit.

- **Include replacement moves in the request.** When regeneration replaces an existing canonical detail or makes same-step siblings obsolete, represent the moves currently associated with `plan_tool/detail.py:_archive_existing_detail` and `plan_tool/detail.py:_archive_orphan_details` as publication artifacts. Do not archive before the transaction is ready or run a second best-effort archive sweep after success for the same paths.

- **Remove concept-backed direct writers.** The concept-backed path in `plan_tool/detail.py:generate_detail` must not call `plan_tool/detail.py:update_step_detail_field` once per prepared step and must not call `plan_tool/concept_tree.py:save_concepts` in its final deferral tail. Keep `update_step_detail_field` only where legacy, concept-free behavior still requires it.

- **Cover adopted details.** The `plan_tool/detail.py:find_unreferenced_detail_for_step` path also changes a plan pointer. When a concept record is present, include that pointer in the same candidate plan or publish it through the step 3 authority before treating it as durable; a direct pointer update would make the loaded concept fingerprint stale.

- **Map publication outcomes honestly.**
  - On verified success, return `written=True` for every published prepared result.
  - On a restored publication failure, return those results as not written with a shared reason stating that the original generation was restored.
  - On rollback failure, return them as not written and include the complete uncertain-path report supplied by step 3. Do not claim that the old or new generation won.
  - Preserve authoring failures and skips already present in the result list.

- **Delay success-only side effects.** Discard a successful step’s checkpoint, emit its written-success scenario, and run lesson extraction only after publication succeeds. A restored or uncertain publication failure must retain the checkpoint so the prepared response can be resumed.

- **Keep reporting deterministic.** Preserve final step ordering across serial and concurrent authoring regardless of worker completion order. All prepared successes in one publication attempt must receive the same publication outcome classification.

- **Respect the commit callback boundary.** Never call `commit_step` before the whole publication succeeds. For a multi-step publication, avoid repeated callbacks whose first `git add -A` would sweep every sibling artifact into one step’s commit; leave the operation to the existing residual batch commit behavior unless a later plan explicitly adds transaction-aware commit grouping. A single-step publication may retain the current callback after verified success.

- **Do not broaden policy.** Preserve `plan_tool/detail.py:parse_structured_detail_response` ownership, signed-deferral validation, included-concept regeneration, and `detail_deferral_step_ids` replacement rules. This step changes when those accepted changes become durable, not which deferrals are valid.

## Tests

- `test_detail_publication_commits_files_plan_and_deferrals_together` — a valid prepared detail publishes its Markdown, `step.detail` pointer, and deferral link in one verified request.
- `test_detail_publication_uses_final_plan_and_detail_bytes_for_fingerprint` — the saved concept fingerprint matches the exact published plan and ordered detail contents.
- `test_detail_publication_replaces_and_removes_links_in_step_order` — add, replace, and include-transition removal preserve unrelated metadata and deterministic ordering.
- `test_detail_publication_excludes_failed_authoring_and_retains_its_old_state` — an unparseable step is absent from the request while successful siblings publish and its old link and body remain.
- `test_concurrent_detail_publication_submits_one_ordered_request` — `jobs > 1` produces one request in step order regardless of worker completion order.
- `test_detail_publication_failure_restores_every_artifact` — a failure at each detail, plan, archive, or concept replacement restores prior bytes and prior absence.
- `test_detail_publication_rollback_failure_reports_all_uncertain_paths` — every prepared success is marked not written and carries the coordinator’s complete uncertainty report.
- `test_detail_publication_refuses_stale_plan_or_concept_snapshot` — a compare-and-swap mismatch changes no detail, pointer, archive, or deferral state.
- `test_detail_publication_does_not_use_direct_concept_writers` — the concept-backed path succeeds when `update_step_detail_field` and `save_concepts` are patched to fail if called.
- `test_adopted_detail_pointer_publishes_with_concept_fingerprint` — adopting an existing canonical detail does not leave the concept record stale.
- `test_detail_checkpoint_discard_waits_for_verified_publication` — success discards the checkpoint, while restored and rollback-failed outcomes retain it.
- `test_detail_success_side_effects_do_not_run_after_publication_failure` — lesson extraction, written-success scenario capture, and `commit_step` stay silent after failure.
- `test_single_step_commit_callback_runs_after_publication_success` — a single-step callback observes the fully published generation and fires once.
- `test_multi_step_publication_uses_residual_commit_path` — a batch does not invoke per-step callbacks that could misattribute sibling artifacts.
- `test_dry_run_builds_no_publication_request` — dry-run returns prompts and leaves every plan, detail, archive, checkpoint, and concept artifact unchanged.
- `test_legacy_plan_without_concept_record_keeps_detail_only_behavior` — a plan with no concept sidecar still writes and points to its detail without creating concept state.

### Test-creation order (feature step)

1. Add the one-request success test and final-byte fingerprint test.
2. Add ordered add, replacement, removal, and failed-authoring-subset tests.
3. Add serial-versus-concurrent request-shape tests.
4. Add stale-snapshot and injected publication-failure restoration tests.
5. Add rollback-failed result and uncertain-path tests.
6. Add direct-writer exclusion, adopted-detail, archive, and checkpoint-order tests.
7. Add lesson, scenario, and commit-callback ordering tests.
8. Add dry-run and concept-free legacy regression tests.

Every new test in `tests/test_detail.py` must be green before this step is considered finished.

## Acceptance criteria

- A concept-backed `plan_tool/detail.py:generate_detail` call submits at most one publication request for its successful prepared subset.
- The request contains the final plan pointers, prepared Markdown bytes, required detail archive moves, and one deterministic deferral replacement.
- A `DetailResult` reports `written=True` only after the publication authority verifies every target.
- A caught publication failure restores all original detail, plan, archive, and concept states and marks every prepared result not written.
- A rollback failure marks every prepared result not written and reports exactly the uncertain paths returned by the publication authority.
- Failed or skipped authoring outcomes retain their prior detail files, plan pointers, and deferral links.
- Concurrent authoring produces the same ordered publication request and durable result as serial authoring.
- The published concept fingerprint identifies the exact final plan and ordered detail bytes.
- Concept-backed publication does not call `plan_tool/concept_tree.py:save_concepts` or perform per-step plan-pointer writes.
- Checkpoints and success-only callbacks remain untouched until publication succeeds.
- Dry-run performs no publication or filesystem mutation.
- Plans without a concept record keep their existing detail-only behavior and do not gain an empty sidecar.
- All existing and new tests in `tests/test_detail.py` pass.

## References

- [pytest — Monkeypatching functions and environments](https://docs.pytest.org/en/stable/how-to/monkeypatch.html) — Use injected publication and side-effect seams to test restoration, rollback failure, and ordering without changing production filesystem behavior.

## Deferred

- Repository lock-token plumbing — if step 3 cannot expose a publication entry point usable under the lock already held by `plan_tool/cli/app.py:main`, reconcile must add the owning CLI and context files to a separate step; do not reacquire the non-reentrant lock inside `plan_tool/detail.py:generate_detail`.
- Split, merge, and re-ground deferral transformation policy — the plan explicitly leaves those algorithms unchanged; this step publishes only the valid prepared outcomes they produce.
- Transaction-aware per-step Git commits — a multi-step publication is one durable generation, so splitting it into separately attributed commits needs its own CLI and repository-history design.
- General repository transactions — the step 3 coordinator remains limited to declared concept publication intents and artifacts.
