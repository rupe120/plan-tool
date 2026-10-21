# Step 10 — Extract scope-out publication preparation

## Summary

This step refactors `plan_tool/scope_out.py` so one write-free prepared value describes every artifact needed for an approved scope-out operation. The prepared value covers the narrowed plan, concept update, forward seed, detail renames, and detail archives, while the existing execution path keeps its current seed-first order, rollback behavior, exceptions, and result fields. `tests/test_scope_out.py` first characterizes success, refusal, stale-state checks, operation order, and partial-failure states. On green, scope-out behaves the same, but step 11 can submit one complete artifact bundle to the publication authority.

## Table of Contents

- [Summary](#summary) — The refactor and its observable result.
- [Why](#why) — Why scope-out needs one preparation boundary.
- [Input](#input) — Existing scope-out and dependency-step contracts.
- [Files (creates vs edits)](#files-creates-vs-edits) — The source and test files changed by this step.
- [Implementation](#implementation) — The prepared bundle, temporary executor, and invariants.
- [Tests](#tests) — Characterization and focused refactor coverage.
- [Acceptance criteria](#acceptance-criteria) — Observable proof that behavior remains unchanged.
- [References](#references) — Primary references for hashes and test seams.
- [Deferred](#deferred) — Transactional behavior owned by step 11.

## Why

`plan_tool/scope_out.py:scope_out_step` currently renders and writes the forward seed itself, while `plan_tool/scope_out.py:apply_narrow` separately discovers archive order, moves detail files, writes the narrowed plan, fingerprints and saves the concept record, and restores failures through a local journal. The inputs for one publication are therefore spread across orchestration and mutation code, which would force step 11 to change preparation and recovery behavior at the same time. This step extracts a complete, write-free publication description while preserving the existing seed-first execution and failure states.

## Input

- **Step 3 outcome:** Step 3 provides the validated, all-or-recoverable publication contract that step 11 will consume. Shape the scope-out bundle so it can be translated to that contract without adding staging, recovery, or authority calls in this refactor.
- **Graph preview:** `plan_tool/scope_out.py:NarrowPreview` remains the source of the narrowed `Plan`, renumbering, detail renames, detail archive sources, cursor, plan status, blockers, source plan path, and source frontmatter hash.
- **Concept preparation:** `plan_tool/scope_out.py:_prepare_concept_narrow_update` supplies the original concept snapshot, prepared concept state, and original sidecar text. Preserve its ownerless-concept rule from `plan_tool/scope_out.py:ownerless_carved_concept_ids` and its validation timing before the opt-in gate.
- **Seed rendering:** `plan_tool/scope_out.py:render_carved_seed` and `plan_tool/scope_out.py:render_carved_region_seed` define the exact forward-seed text. `plan_tool/scope_out.py:_carved_seed_path` and `plan_tool/scope_out.py:_carved_region_seed_path` define collision-safe targets.
- **Public results:** `plan_tool/scope_out.py:NarrowResult` and `plan_tool/scope_out.py:ScopeOutResult` keep their current meanings. Prepared destinations are not committed results until the existing executor completes them.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `plan_tool/scope_out.py` — add the write-free scope-out publication bundle and preparation boundary, then make the current seed-first publication tail consume it without changing behavior.
  - `tests/test_scope_out.py` — add characterization tests for bundle contents, preparation side effects, operation order, stale-state refusal, success results, and current rollback and partial-failure states.

## Implementation

The foundational logic is: **prepare one complete scope-out publication description without changing live repository state**.

- **Keep policy in `plan_tool/scope_out.py:scope_out_step`.** Preserve reparsing, `compute_frontmatter_hash`, `compute_narrow`, blocker mapping, concept validation, the `allow_scope_out` gate, and the `yes → non-TTY → interactive` confirmation rule. Preparation must not prompt or decide whether a carve is allowed.

- **Preserve concept-validation timing.** Continue preparing or validating concept changes after the blocker gate and before the opt-in gate. A refactor must not turn an unusable concept record into a successful recommendation or delay an existing refusal until after confirmation.

- **Build the publication bundle only for the apply branch.** After confirmation, call one write-free preparation boundary with the parsed plan, carved steps, `NarrowPreview`, repository root, and prepared concept update. This keeps recommend-only and declined paths from reading detail bodies or choosing a forward-seed target earlier than they do now.

- **Use one immutable bundle shape.** The exact private type and helper names are up to the implementer. One value should carry:
  - the source plan path, source frontmatter hash, and original plan text needed by the current stale check and restoration path;
  - the complete narrowed `Plan` from `plan_tool/scope_out.py:NarrowPreview.narrowed_plan`;
  - the concept preparation result or an explicit absence for plans with no applicable concept record;
  - the forward-seed target and exact rendered text;
  - every downstream detail rename as an ordered source and destination pair;
  - every carved-detail archive action, including enough information to preserve the existing destination naming and collision rules;
  - the renumbering, new cursor, final plan status, and result metadata needed to construct `NarrowResult` and `ScopeOutResult`.

- **Prepare exact seed text once.** Move the apply-branch assembly around `plan_tool/scope_out.py:_resolve_upstream_context`, `plan_tool/scope_out.py:_resolve_carved_detail_path`, `plan_tool/scope_out.py:render_carved_seed`, and `plan_tool/scope_out.py:render_carved_region_seed` behind the new preparation boundary. Preserve single-step and region rendering, missing-detail warnings, external prerequisite mapping, authored concept-ID order, and collision-safe seed naming.

- **Keep preparation write-free.** It may read the plan, concept sidecar, and referenced detail files; render content; validate state; and calculate target paths. It must not call `Path.write_text`, `Path.rename`, `plan_tool/scope_out.py:_archive_file_strict`, `plan_tool/parser.py:write_plan`, concept persistence, or create directories.

- **Keep operation ordering explicit.** Preserve the current rule in `plan_tool/scope_out.py:apply_narrow`: archive carved details that occupy rename destinations first, perform downstream renames in ascending source order, archive the remaining carved details, write the plan, then save the concept record. The forward seed remains the first live write in `plan_tool/scope_out.py:scope_out_step`.

- **Preserve archive behavior exactly.** Separate destination selection from the strict move in `plan_tool/scope_out.py:_archive_file_strict`, allowing preparation to carry explicit source and target paths while execution retains the current UTC suffixing, collision handling, move verification, and `NarrowResult.archived` ordering. Characterize what HEAD does when a fallback target is occupied and keep that outcome unchanged here; any stronger collision refusal belongs to step 11.

- **Retain a temporary local executor.** Adapt the existing scope-out tail to consume the prepared bundle and perform the same writes, moves, calls to `plan_tool/scope_out.py:_rollback`, plan restoration, provenance refresh, and concept restoration. This executor is temporary preparation for step 11; it must not call the step 3 authority yet.

- **Keep compare-and-swap checks at execution time.** `plan_tool/scope_out.py:apply_narrow` must still reject a changed plan frontmatter or concept sidecar before the first narrow mutation. Preparing a bundle is not proof that its source snapshots remain current.

- **Preserve the current seed failure boundary.** A seed write failure must prevent all narrow mutations. A failure after the seed write must still leave the seed on disk while the existing narrow rollback restores its covered plan, detail, and concept changes. Step 11 intentionally changes this partial state.

- **Keep direct `apply_narrow` callers compatible.** Tests and library callers currently pass a `NarrowPreview` plus optional concept preparation. The refactor may add an internal adapter or prepared-input path, but it should not remove the existing callable contract in this step unless every checked-in caller remains source-compatible.

- **Keep results tied to completed work.** Populate `NarrowResult.archived`, `NarrowResult.migrated`, and `ScopeOutResult.seed_path` from operations that actually completed. Do not report a prepared target as committed merely because it appears in the bundle.

- **Do not extract a general transaction framework.** The bundle describes scope-out artifacts only. Step 3 owns the shared publication coordinator, and step 11 owns translating this bundle into that authority’s scope-out request.

## Tests

- `test_prepare_scope_out_publication_is_write_free` — preparation leaves the plan, seed directory, concept sidecar, active details, and archive directory unchanged.
- `test_prepared_scope_out_publication_contains_complete_artifact_set` — the bundle contains the source snapshots, narrowed plan, seed target and text, concept update, detail renames, and archive actions.
- `test_prepared_single_step_seed_matches_existing_renderer` — prepared text and target match `plan_tool/scope_out.py:render_carved_seed` and `plan_tool/scope_out.py:_carved_seed_path`.
- `test_prepared_region_seed_matches_existing_renderer` — prepared text and target match `plan_tool/scope_out.py:render_carved_region_seed` and `plan_tool/scope_out.py:_carved_region_seed_path`.
- `test_prepared_publication_preserves_detail_operation_order` — carved slots needed by downstream renames are archived first, renames stay ordered, and remaining archives follow them.
- `test_scope_out_apply_result_is_unchanged_after_extraction` — a successful carve returns the same `ScopeOutResult` and `NarrowResult` fields and produces the same plan, seed, detail, and concept state.
- `test_scope_out_recommend_only_does_not_prepare_apply_artifacts` — a non-applied recommendation writes nothing and does not read carved detail bodies or choose a seed target.
- `test_scope_out_concept_validation_still_precedes_opt_in` — an unusable required concept record raises before prompting or writing even when publication preparation is separated.
- `test_apply_narrow_stale_plan_refusal_is_unchanged` — changed frontmatter stops before any detail, plan, or concept mutation.
- `test_apply_narrow_stale_concept_refusal_is_unchanged` — changed sidecar text or plan fingerprint stops before any narrow mutation.
- `test_seed_write_failure_still_prevents_narrow` — failure publishing the seed leaves the plan, concepts, and details untouched.
- `test_narrow_failure_still_leaves_seed_and_restores_plan` — failure after the seed write preserves the current orphan-seed behavior and restores the narrow’s covered artifacts.
- `test_concept_save_failure_state_is_unchanged` — the plan and sidecar return to their original contents while the already-written seed remains.
- `test_detail_archive_failure_state_is_unchanged` — completed detail moves are rolled back, the plan stays unchanged, and no false result is returned.
- `test_multi_step_archive_and_rename_results_are_unchanged` — region carving preserves archive count, migration order, freed-slot behavior, and result paths.

### Test-creation order (refactor step)

Write the characterization tests before changing `plan_tool/scope_out.py`. Start with the existing cases around `tests/test_scope_out.py:test_applied_writes_seed_then_narrows`, `tests/test_scope_out.py:test_successful_apply_persists_narrow_and_deferrals`, `tests/test_scope_out.py:test_apply_archives_carved_detail_before_downstream_rename_into_same_path`, and `tests/test_scope_out.py:test_apply_multi_id_frees_carved_slots_before_downstream_renames`; pin artifact contents, result fields, and operation order. Then characterize blocker, opt-in, confirmation, stale-plan, stale-concept, seed-failure, archive-failure, plan-write-failure, and concept-save-failure paths, including the exact files that remain or are restored. Add the write-free bundle assertions only after those current behaviors are pinned. The same characterization tests must stay green and unmodified after restructuring; changed rollback or seed semantics belong to step 11.

## Acceptance criteria

- Preparing a scope-out publication performs no writes, renames, archives, deletes, or directory creation.
- One prepared value contains the narrowed plan, concept update or explicit absence, forward-seed target and text, all detail renames, all carved-detail archive actions, and the source snapshots needed for execution checks.
- Prepared single-step and region seed text matches the existing renderer output for the same inputs.
- Blocked, recommend-only, declined, and stale paths retain their current return or exception behavior and perform no live publication.
- Successful single-step and region carves produce the same plan graph, cursor, status, seed content, detail layout, concept decisions, and result fields as before the refactor.
- Detail operations retain the current archive-first-when-needed, ordered-rename, remaining-archive sequence.
- A seed write failure leaves every narrow artifact unchanged.
- A failure after the seed write retains the current seed and restores the plan, detail files, and concept sidecar according to the existing local rollback behavior.
- `plan_tool/scope_out.py:apply_narrow` remains compatible with its checked-in direct callers.
- All existing and new focused tests in `tests/test_scope_out.py` pass without changing the characterization assertions after implementation.

## References

- [Python hashlib — Secure hashes and message digests](https://docs.python.org/3/library/hashlib.html) — Preserve the existing source-hash and fingerprint comparisons when separating preparation from execution.
- [pytest — Monkeypatching functions and environments](https://docs.pytest.org/en/stable/how-to/monkeypatch.html) — Use injected write, archive, and concept-save failures to pin operation order and restoration behavior.

## Deferred

- Transactional scope-out publication — step 11 submits the prepared bundle through the step 3 authority and removes the temporary local executor.
- Forward-seed rollback — step 11 changes the current orphan-seed failure state by including the seed in the recoverable publication.
- Durable journaling, restart recovery, rollback verification, and uncertain-path reporting — step 11 consumes these capabilities from step 3 rather than adding another coordinator to `plan_tool/scope_out.py`.
- CLI result mapping — step 11 updates `plan_tool/cli/scope_out_cmd.py:render_scope_out_result` and `plan_tool/cli/convergence_cmd.py:_actuate_scope_out` for restored-failure and rollback-failed outcomes.
- Removal of direct concept publication from `plan_tool/scope_out.py:apply_narrow` — step 11 replaces the temporary call path with the shared authority.
- Shared archive or confirmation helpers — reconcile should decide whether consolidation is useful; this refactor keeps scope-out’s existing local behavior.
