# Step 6 — Prepare create publication as one artifact bundle

## Summary

This step restructures `plan_tool/create.py:create_plan` so one prepared value describes the complete initial create publication before its existing filesystem calls begin. The bundle covers the final plan content, reviewed concept state, collision replacements, manifest changes, and any inherited detail-directory move, while leaving the current publication order and failure behavior unchanged. `tests/test_create.py` first characterizes the signed, unsigned, collision, validation-failure, and partial-failure paths. On green, create produces the same files, result fields, warnings, and errors, but step 7 can hand one complete request to the concept publication authority.

## Table of Contents

- [Summary](#summary) — The result and boundaries of the refactor.
- [Why](#why) — Why create needs one preparation boundary.
- [Input](#input) — Contracts supplied by dependency steps and existing create state.
- [Files (creates vs edits)](#files-creates-vs-edits) — The source and test files changed by this step.
- [Implementation](#implementation) — The bundle boundary, existing execution tail, and invariants.
- [Tests](#tests) — Characterization coverage required before restructuring.
- [Acceptance criteria](#acceptance-criteria) — Observable proof that behavior remains unchanged.
- [References](#references) — Primary documentation relevant to deterministic bytes and test seams.
- [Deferred](#deferred) — Publication and recovery changes owned by later steps.

## Why

`plan_tool/create.py:create_plan` currently discovers publication inputs while it is already mutating the repository: it archives collisions, removes old manifest entries, writes and reparses the plan, moves inherited details, publishes signed or unsigned concepts through different paths, and finally updates the manifest. That interleaving makes it hard for step 7 to replace the sequence with one transaction without also rewriting create’s authoring logic. This step introduces a write-free preparation boundary so the complete create operation has one shape, while deliberately preserving the existing execution and failure semantics until the publication authority takes ownership.

## Input

- **Step 5 reviewed state:** Step 5 produces resumable create concept state and the terminal-driven signed-versus-unsigned review result. This step consumes that reviewed `plan_tool/concept_tree.py:ConceptTree` and the reviewed `plan_tool/schema.py:Step` values without changing approval rules, resume compatibility, or per-selection persistence.
- **Step 2 publication contract:** Step 2 provides the typed signed and unsigned concept publication intents in `plan_tool/concept_sync.py`. The create bundle must carry the appropriate intent as data; it must not duplicate intent validation or concept-tree preparation in `plan_tool/create.py`.
- **Rendered plan inputs:** `plan_tool/create.py:_render_plan_body`, `plan_tool/create.py:write_new_plan`, and `plan_tool/create.py:predict_plan_path` define the current body precedence, serialized plan shape, and destination path. Prepared plan content must match the bytes the existing write path produces.
- **Collision inputs:** `plan_tool/create.py:find_collisions`, `plan_tool/create.py:_decide_replace_collisions`, `plan_tool/create.py:_archive_targets`, and `plan_tool/create.py:resolve_existing_plan_details` supply the already-decided sources and destinations. Preparation must not repeat prompts or choose a different archive generation.
- **Result contract:** `plan_tool/create.py:CreateResult` remains the caller-facing result. Its archive pairs, removed manifest entries, inherited-detail outcome, manifest status, advisories, and iteration failure fields must retain their current meanings.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `plan_tool/create.py` — add a write-free representation and preparation boundary for the initial create publication, then have `create_plan` execute the current publication tail from that prepared value.
  - `tests/test_create.py` — add characterization tests for bundle contents, successful signed and unsigned creates, operation order, validation exits, collision replacement, inherited details, manifest behavior, and current failure states.

## Implementation

The foundational logic is: **prepare one complete create-publication description without changing live repository state**.

- **Separate authoring from publication preparation.** Keep prompts, Claude calls, step and gate review, concept review, reference gathering, body synthesis, and the placeholder check in `plan_tool/create.py:create_plan`. Once those stages have settled the plan, concept tree, destination, collision choice, provenance, and manifest path, pass them through one write-free preparation boundary.

- **Use one immutable bundle shape.** The exact private type name is up to the implementer, but one value should carry everything the initial publication tail needs:
  - the prospective path from `plan_tool/create.py:predict_plan_path`;
  - the validated `Plan` and exact rendered plan content;
  - the reviewed concept tree and the signed or unsigned intent supplied by step 2;
  - collision sources and their paired archive destinations;
  - old manifest entries to remove and the new entry to add;
  - the optional inherited detail directory and its intended destination;
  - enough operation metadata to populate `plan_tool/create.py:CreateResult`.

- **Prepare exact plan bytes once.** Extract the write-free rendering part of `plan_tool/create.py:write_new_plan` so preparation and the existing writer share one serializer path. The prepared bytes must preserve `plan_tool/create.py:_render_plan_body` precedence, the priority-prefixed filename, frontmatter formatting, body text, trailing newline behavior, and parse validation. Do not add a second hand-built Markdown serializer.

- **Keep preparation free of live mutations.** Preparing the bundle must not call `plan_tool/create.py:archive_existing_source`, `plan_tool/create.py:remove_from_manifest`, `plan_tool/create.py:write_new_plan`, `plan_tool/create.py:rename_plan_details_to_slug`, `plan_tool/concept_sync.py:synchronize_concepts`, `plan_tool/concept_tree.py:save_concepts`, or `plan_tool/create.py:append_to_manifest`. It may inspect required source state, calculate destinations, render bytes, and validate typed intents.

- **Retain the existing execution tail for this step.** After preparation, adapt the current code to consume the bundle and invoke the same mutation helpers in the same order:
  1. archive approved collisions and remove their manifest entries;
  2. write and reparse the new plan;
  3. move inherited plan details when applicable;
  4. use the current signed or unsigned concept path;
  5. append the new manifest entry.
  
  This order is intentionally temporary. Changing it, adding rollback, staging all targets, or rejecting the operation before the first mutation would be feature behavior owned by step 7.

- **Preserve signed and unsigned differences.** Signed review must still use `plan_tool/concept_sync.py:synchronize_concepts`; unsigned proposals must still preserve independently authored scope prose and follow the persistence behavior supplied by step 5. The bundle makes the difference explicit but does not merge the two execution branches in this refactor.

- **Preserve collision target pairing.** Use the decisions already made by `plan_tool/create.py:_archive_targets`. A plan and its `plan-details/<slug>/` directory must retain the same archive generation, replacement notices, sorted child handling, and `CreateResult.replaced_archives` reporting.

- **Preserve inherited-detail outcomes.** `plan_tool/create.py:resolve_existing_plan_details` and `plan_tool/create.py:rename_plan_details_to_slug` currently distinguish no source, no-op, successful move, target collision, and filesystem failure. Bundle preparation may identify the proposed move, but execution must continue to populate `CreateResult.plan_details_renamed_to` and `CreateResult.plan_details_skip_reason` exactly as it does now.

- **Keep early exits outside publication.** The multi-plan result from `plan_tool/create.py:propose_distilled_seed_from_claude`, rejected collisions from `plan_tool/create.py:_decide_replace_collisions`, invalid output directories, invalid lessons paths, and `plan_tool/create.py:_find_placeholder_body_sections` failures must return or raise before a publication bundle is executed.

- **Extract an isolated candidate-workspace seam without changing behavior yet.** Characterize the post-write convergence loop’s reads, writes, path assumptions, and final concept refresh, then make its candidate-plan root/path injectable so step 7 can run it against a private staged workspace. In this refactor, production still supplies the live published path and retains the existing order and outcomes; the new seam is write-free during bundle preparation and must not claim iteration has already run.

- **Keep result reporting derived from actual execution.** Prepared destinations are intentions, not proof that an archive or move succeeded. Populate `CreateResult.replaced_archives`, `CreateResult.replaced_skipped`, `CreateResult.replaced_manifest_entries`, `CreateResult.plan_details_renamed_to`, and `CreateResult.manifest_updated` from the existing helpers’ real outcomes.

- **Reject a broader transaction abstraction.** Do not introduce a general repository transaction layer in `plan_tool/create.py`. Step 3 owns the all-or-recoverable concept publication coordinator, while this step only gives create one complete input shape that step 7 can submit to it.

## Tests

- `test_prepare_create_publication_is_write_free` — preparing a signed or unsigned bundle leaves the plan, manifest, archive directory, final concept sidecar, and inherited detail paths unchanged.
- `test_prepare_create_publication_carries_exact_rendered_plan` — the prepared path and plan content match `plan_tool/create.py:write_new_plan` output for the same plan and body inputs.
- `test_create_plan_signed_publication_behavior_is_unchanged` — signed create writes matching step ownership and concept state, reparses successfully, and returns the existing `CreateResult` values.
- `test_create_plan_unsigned_publication_behavior_is_unchanged` — unsigned create preserves scope prose, persists unsigned concept state, and registers the plan once.
- `test_create_plan_collision_operation_order_is_unchanged` — collision archival and old-manifest removal still occur before the plan, concept, and new-manifest operations in the current order.
- `test_create_plan_collision_result_metadata_is_unchanged` — archive pairs, skipped paths, and removed manifest entries remain based on actual helper outcomes.
- `test_create_plan_inherited_details_result_is_unchanged` — successful, no-op, and skipped detail moves retain their current destination and reason fields.
- `test_create_plan_placeholder_failure_executes_no_bundle` — a live `plan_tool/create.py:_find_placeholder_body_sections` rejection performs no archive, plan, detail, concept, or manifest mutation.
- `test_create_plan_post_write_reparse_failure_state_is_unchanged` — a reparse failure raises the same `CreateError` and leaves the same current filesystem and checkpoint state.
- `test_create_plan_concept_failure_state_is_unchanged` — a signed concept rejection raises the same error and preserves the current plan, sidecar, archive, and manifest outcomes for this refactor.
- `test_create_plan_manifest_failure_state_is_unchanged` — malformed manifest handling and any mutations completed before that failure remain characterized for step 7 to replace.
- `test_create_plan_iteration_still_runs_after_initial_bundle` — enabled iteration sees the published plan, retains its existing rewrite behavior, and performs the same final concept refresh.
- `test_create_iteration_candidate_path_is_injectable` — the extracted iteration runner can target an isolated candidate root while the production refactor path still supplies the current live plan.

### Test-creation order (refactor step)

Write the characterization tests before changing `plan_tool/create.py`. Start with the existing success paths in `tests/test_create.py:TestCreatePlanBlankSkeleton`, `tests/test_create.py:TestCreatePlanReplaceOnCollision`, `tests/test_create.py:TestCreatePlanReusesPlanDetails`, and `tests/test_create.py:TestCreatePlanConceptIntegration`; pin exact plan content, concept state, manifest contents, archive results, and `CreateResult` fields. Then add failure characterization for no-write validation exits, post-write reparse failure, concept publication failure, inherited-detail skip, and manifest failure, including the exact paths and bytes left behind by the current sequence. Finally, pin the call order and the post-write iteration boundary with injected helpers. These same characterization tests must pass unchanged after the restructuring; any intentional rollback or ordering improvement belongs to step 7 and may update them there.

## Acceptance criteria

- Preparing the initial create publication performs no writes, moves, deletes, manifest edits, or final-sidecar publication.
- The prepared destination equals `plan_tool/create.py:predict_plan_path` for the selected output directory, slug, and priority.
- The prepared plan content matches the content produced by `plan_tool/create.py:write_new_plan` for the same inputs and reparses as the same `Plan`.
- Signed and unsigned creates produce the same plan, concept, and manifest results as before this refactor.
- Collision replacement retains the current archive names, paired plan/detail generations, replacement notices, manifest removals, and `CreateResult` reporting.
- Inherited detail moves retain the current success, no-op, and skip behavior.
- Placeholder, reparse, concept, and manifest failures retain their characterized exception and filesystem states.
- The convergence runner accepts an explicit candidate plan/root; production behavior and the final concept refresh remain unchanged until step 7 moves that runner into private staging.
- All new and existing focused tests in `tests/test_create.py` pass without modifying the characterization assertions after implementation.

## References

- [Python hashlib — Secure hashes and message digests](https://docs.python.org/3/library/hashlib.html) — Use the byte-oriented SHA-256 contract when checking that prepared plan content and concept provenance refer to the same final bytes.
- [Pydantic — Unions and discriminated unions](https://pydantic.dev/docs/validation/latest/concepts/unions/#discriminated-unions) — Read this alongside the typed publication intents from step 2 so create carries one valid signed or unsigned request shape.
- [pytest — Monkeypatching functions and environments](https://docs.pytest.org/en/stable/how-to/monkeypatch.html) — Use injected mutation helpers to prove preparation is write-free and to pin the current execution order and failure seams.

## Deferred

- All-or-recoverable create publication — step 7 replaces the temporary sequential executor with the step 3 publication authority and changes the characterized partial-failure states.
- Durable journal, staging, restart recovery, rollback verification, and uncertain-path reporting — owned by steps 3 and 7; this refactor must not implement a second coordinator in `plan_tool/create.py`.
- Direct-write removal for signed and unsigned create finalization — step 7 routes both intents through the public authority.
- Post-iteration transactional concept refresh — step 7 owns replacing the remaining `plan_tool/create.py:create_plan` calls to `plan_tool/concept_sync.py:synchronize_concepts` or `plan_tool/concept_tree.py:save_concepts`.
- Detail publication preparation in `plan_tool/detail.py:generate_detail` — step 8 performs the matching refactor for detail authoring.
- Scope-out publication in `plan_tool/scope_out.py:apply_narrow` — step 11 moves that operation to the common authority without expanding this step’s file set.
- Shared consolidation of archive or manifest mutation helpers — reconcile should decide whether reuse is warranted after create, detail, and scope-out all use the publication authority.
