> **Auto-archived**: this plan was swept on 2026-08-18 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 3 — Extract create_plan publication into a same-file phase

## Summary

Refactor `plan_tool/create.py:create_plan` so its initial durable writes and manifest work live in a named same-file publication phase. Keep collision replacement, initial plan writing and reparsing, plan-details renaming, concept synchronization and rollback, and manifest append in their current order. Pass the published on-disk state back explicitly for later convergence and finalization. On green, callers observe the same paths, manifest contents, rollback behavior, and `CreateResult` metadata.

## Table of Contents

- [Summary](#summary) — The publication extraction and its visible result.
- [Table of Contents](#table-of-contents) — Links to each section.
- [Why](#why) — Why publication needs its own boundary.
- [Input](#input) — The prepared state and persistence contracts publication consumes.
- [Files (creates vs edits)](#files-creates-vs-edits) — The production and test files involved.
- [Implementation](#implementation) — The publication boundary, ordering, and preserved failure behavior.
- [Tests](#tests) — Focused regression coverage for publication effects.
- [Acceptance criteria](#acceptance-criteria) — Observable checks for the extracted phase.
- [References](#references) — Python and test-mocking guidance for the extraction.
- [Applicable guardrails](#applicable-guardrails) — Plan boundaries that constrain this refactor.
- [Deferred](#deferred) — Work left to later phases or separate refactors.

## Why

`plan_tool/create.py:create_plan` currently mixes durable publication with preparation, convergence, and post-loop work. The initial write has strict ordering rules: collision artifacts and stale manifest entries move first, the written file becomes the source for reparsing and concept work, and the manifest changes only after a usable plan exists. A named publication phase makes that contract reviewable without changing what users receive.

## Input

- **Step 2 preparation handoff:** consume the normal prepared state from step 2, including the proposed `Plan`, collision decision and entries, manifest path, body inputs, provenance, concept state, and result metadata. Its split result remains an early return and never enters publication.

- **Initial write contract:** `plan_tool/create.py:write_new_plan` creates the initial plan, and `plan_tool/parser.py:parse_plan` must validate the bytes written to `plan_path` before later consumers use them.

- **Concept contract:** `plan_tool/concept_sync.py:synchronize_concepts`, `plan_tool/concept_tree.py:concepts_path`, and `plan_tool/create.py:_persist_or_clear_concepts` define the signed and unsigned concept-publication paths.

- **Publication result:** later convergence and finalization need the published `plan_path`, current concept state and fingerprint, manifest result, detail-rename result, and collision archive metadata without recomputing or guessing them.

## Files (creates vs edits)

- **New files:** none.

- **Existing files (edits only):**
  - `plan_tool/create.py` — add the same-file publication owner, move the existing initial publication block into it, and return its published state explicitly.
  - `tests/test_create.py` — add focused publication-handoff coverage and keep the existing collision, reparse, rename, and concept-rollback tests aligned with the extracted owner.

## Implementation

- **Foundational logic:** publish one prepared plan and its initial concept state in the existing order, then hand the on-disk result to later phases.

- **Use a private same-file publication owner:** introduce `plan_tool/create.py:_publish_create_plan` for the normal prepared path. Return a clear private handoff rather than relying on closure-captured state; it must carry the `plan_path` and every value later convergence or finalization needs.

- **Keep collision replacement first:** when preparation selected replacement, preserve the loop over collisions using `plan_tool/create.py:predict_plan_path`, `plan_tool/create.py:archive_existing_source`, and `plan_tool/create.py:remove_from_manifest`. Keep archive pairs, skipped reasons, and removed manifest entries in their current order for `CreateResult`.

- **Keep the initial write and reparse together:** call `plan_tool/create.py:write_new_plan` with the current references, seed sections, synthesized sections, and supplied guardrails, then reparse through `plan_tool/parser.py:parse_plan`. Preserve the existing `CreateError` on a failed post-write reparse and do not append the new manifest entry on that path.

- **Use the written file as the publication source:** resolve and rename provenance-backed detail directories only after the first successful reparse, through `plan_tool/create.py:resolve_existing_plan_details` and `plan_tool/create.py:rename_plan_details_to_slug`. Preserve no-op and skip results rather than turning a rename collision or filesystem failure into a create failure.

- **Preserve concept-publication order:** compute the initial fingerprint after the initial write and detail-rename work. For signed scope, call `plan_tool/concept_sync.py:synchronize_concepts` against the parsed on-disk plan, reparse its resulting bytes, and retain its fingerprint on the copied concept tree. For unsigned scope, preserve the existing `plan_tool/create.py:_persist_or_clear_concepts` conditions and safe-to-clear rule.

- **Keep rollback narrow:** on failed initial signed concept synchronization, remove only the create-owned plan and concept sidecar using `plan_tool/concept_tree.py:concepts_path`, leave the manifest untouched, and raise the existing `CreateError`. Do not add a broader transaction or change prior collision-archive behavior.

- **Append the new manifest entry last:** retain `plan_tool/create.py:append_to_manifest` after successful concept publication. Preserve its Boolean result so `CreateResult.manifest_updated` remains unchanged.

- **Keep helpers and callers stable:** `plan_tool/cli/authoring.py:cmd_create` and `plan_tool/bench.py:_run_proposal` continue calling the unchanged public entry point, while the package continues to re-export it. Keep test seams resolving through `plan_tool.create` so existing monkeypatches still intercept publication helpers.

- **Do not generalize publication in this step:** `plan_tool/concept_sync.py:synchronize_concepts` is a related durable-write operation with its own rollback contract. Reuse it as the existing dependency; do not merge it with create orchestration or introduce a shared framework.

## Tests

### Tests for this step

- `TestCreatePlanPublication.test_publish_create_plan_preserves_collision_to_manifest_order` — records the collision archive, stale manifest removal, initial write, reparse, optional rename or concept work, and manifest append order on the replacement path.
- `TestCreatePlanReplaceOnCollision.test_replace_via_kwarg_archives_existing` — keeps archived plan and detail artifacts, stale-entry removal, replacement metadata, and the new manifest entry unchanged.
- `TestCreatePlanPostWriteReparse.test_post_write_reparse_failure_raises` — proves invalid initial bytes raise `CreateError` before the new plan reaches the manifest.
- `TestCreatePlanReusesPlanDetails.test_plan_details_renamed_to_new_slug` — proves a provenance-backed detail bundle moves after successful initial publication and is reported through `CreateResult`.
- `TestCreatePlanReusesPlanDetails.test_plan_details_skip_surfaces_reason` — proves a detail-target collision leaves both directories intact while the new plan still publishes.
- `TestCreatePlanConceptIntegration.test_core_sync_failure_leaves_no_plan_or_manifest` — proves failed signed concept synchronization removes the new plan and concept sidecar without appending the manifest.

Every listed test must be green before this step is complete.

## Acceptance criteria

- `plan_tool/create.py:_publish_create_plan` owns the normal-path collision replacement, initial write and reparse, detail rename, initial concept publication, and manifest append work.
- Collision replacement still archives each selected source, removes only listed stale manifest entries, and reports the same archive and removal metadata in `CreateResult`.
- The first `plan_tool/parser.py:parse_plan` runs after `plan_tool/create.py:write_new_plan` and before detail rename, concept work, or new manifest append.
- A post-write parse failure raises the existing create error and does not add the new plan to the manifest.
- A failed initial signed concept synchronization removes the new plan and its concept sidecar, leaves the manifest untouched, and preserves the existing error result.
- Detail rename success, no-op, and skip behavior remain unchanged.
- `plan_tool/create.py:append_to_manifest` still runs only after the plan’s initial concept state is publishable and its Boolean result still feeds `CreateResult.manifest_updated`.
- `tests/test_create.py` passes without weakening existing behavior assertions.

## References

- [Python 3.13 Language Reference — Function definitions](https://docs.python.org/3.13/reference/compound_stmts.html#function-definitions) — Preserve the public entry point while adding private same-file phase functions.
- [pytest — How to monkeypatch/mock modules and environments](https://docs.pytest.org/en/stable/how-to/monkeypatch.html) — Keep publication helpers patchable at their module-local lookup sites.
- [Python 3.13 unittest.mock — Where to patch](https://docs.python.org/3.13/library/unittest.mock.html#where-to-patch) — Patch helpers where the extracted publication owner resolves them.
- [Python 3.13 unittest.mock — Tracking order of calls](https://docs.python.org/3.13/library/unittest.mock-examples.html#tracking-order-of-calls-and-less-verbose-call-assertions) — Record the publication sequence in focused handoff coverage.

## Applicable guardrails

- **The plan’s “## Plan intent”, same-file phase sequence:** keep publication as a private same-file boundary and leave `plan_tool/create.py:create_plan` as the public direct entry point.

- **The plan’s “## Step intent”, on-disk publication handoff:** make the successful written `plan_path` the source for publication-time body and concept consumers.

- **The plan’s “## Out of scope”, behavior preservation:** do not change signatures, errors, checkpoints, normal results, split-proposal handling, or convergence terminal outcomes.

## Deferred

- Finalization extraction and the full phase-order characterization — step 4 owns checkpoint cleanup, post-loop concept synchronization, pending-decision reporting, and the complete normal-path sequence.
- Shared create/detail convergence infrastructure — requires separately scoped follow-up work.
- Refactoring `plan_tool/cli/run_cmd.py:cmd_run` — remains outside this create-flow plan.
