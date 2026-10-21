> **Auto-archived**: this plan was swept on 2026-08-18 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 3 — Serialize roadmap and seed-state writers, pre-invalidate seed state, and atomically publish one gate-valid artifact candidate

## Summary

Add `plan_tool/roadmap_revision_publish.py` as the owner of the per-roadmap writer guard, conservative seed-state invalidation, and one-artifact candidate publication path. Update the existing roadmap and seed mutation owners to acquire one shared guard before reading their mutable baseline and to pass its token through nested calls. Expose that same guard for step 4’s local runner to acquire before preflight. Make `plan_tool/roadmap_seed_state.py:write_seed_state` flush and `fsync` a validated temporary sidecar before replacing it. Green means a local revision can invalidate tracked seeds before backend work, validate and atomically replace only its selected artifact, and never let participating writers race on the same roadmap.

## Table of Contents

- [Summary](#summary) — The step’s outcome and main publication decision.
- [Table of Contents](#table-of-contents) — Links to each section.
- [Why](#why) — The mutable-baseline and false-current-state problem.
- [Input](#input) — Existing stage, gate, candidate, and sidecar contracts.
- [Files (creates vs edits)](#files-creates-vs-edits) — New publisher files and current mutation owners.
- [Implementation](#implementation) — Guard ownership, invalidation ordering, and candidate publication rules.
- [Tests](#tests) — Locking, durability, and no-write failure coverage.
- [Acceptance criteria](#acceptance-criteria) — Observable publication and serialization behavior.
- [References](#references) — The single-path replacement contract.
- [Applicable guardrails](#applicable-guardrails) — Plan boundaries that constrain this writer step.
- [Deferred](#deferred) — Later command work and separate lock consolidation.

## Why

Current roadmap artifact and seed-state writers can read a baseline, then another participating command can replace that baseline before the first command writes. `plan_tool/roadmap.py:_invalidate_roadmap_seeds` also invalidates only after broad-stage writes, which cannot protect a failed local revision from leaving an older seed represented as current. This step creates the shared publication boundary that lets step 4 make one local backend request without racing a broad run, seed promotion, or seed refresh.

## Input

- **Step 2 candidate:** Step 2 returns one typed, in-memory candidate that differs only at the selected target row and selected feedback row. This step must serialize, re-parse, gate, and publish that value; it must not reimplement the operation parser or merger.

- **Stage contract:** `plan_tool/roadmap.py:RoadmapStage` and `plan_tool/roadmap.py:STAGES` provide the canonical artifact path, parser, renderer, and gate set. Keep the candidate on the selected stage’s existing contract instead of introducing another artifact mapping.

- **Gate envelope:** `plan_tool/roadmap.py:_build_envelope` and `plan_tool/roadmap_gates.py:ArtifactEnvelope` establish the normal upstream context. Local validation must include only the selected candidate and its normal read-only upstream artifacts, with no same-artifact predecessor.

- **Seed lifecycle:** `plan_tool/roadmap_seed_state.py:load_seed_state`, `write_seed_state`, and `has_invalidated_seed` own the validated `seed-state.json` shape. Preserve each entry’s path, digest, and publication flag while changing only its lifecycle status.

- **Create confirmation:** `plan_tool/cli/authoring.py:_confirm_invalidated_roadmap_seed` reads the sidecar to protect `create` from consuming stale seeds. It remains a read-only, lock-free consumer of the persisted invalidation state.

## Files (creates vs edits)

- **New files:**
  - `plan_tool/roadmap_revision_publish.py` — Per-roadmap cross-process writer guard, token ownership, seed-state pre-invalidation, candidate validation, and atomic one-path publication.
  - `tests/test_roadmap_revision_publish.py` — Focused lock, invalidation, validation, and publication tests.

- **Existing files (edits only):**
  - `plan_tool/roadmap.py` — Put `run_roadmap`, `apply_roadmap_seeds`, `accept_roadmap_seed`, `materialize_plan_seed`, and `refresh_roadmap_seeds` under the shared guard; pass its token through `plan_tool/roadmap.py:_apply_roadmap_seeds` and `materialize_and_diff_one_plan`.
  - `tests/test_roadmap.py` — Cover public owner acquisition, nested token forwarding, and preservation of existing broad-stage and seed workflows.
  - `plan_tool/roadmap_seed_state.py` — Make `write_seed_state` flush its validated temporary sidecar before its atomic replacement while retaining its stdlib-only leaf boundary.
  - `tests/test_roadmap_seed_state.py` — Cover durable sidecar-write ordering and continued stale-seed discovery.
  - `plan_tool/cli/roadmap_cmd.py` — Make `_cmd_roadmap_materialize` acquire the outer writer guard before reading the plans artifact or classifications, then pass its token through the batch.
  - `tests/cli/test_roadmap_cmd.py` — Pin guard acquisition before the materialize command’s baseline reads and token forwarding through its selected rows.
  - `plan_tool/cli/authoring.py` — Keep `_confirm_invalidated_roadmap_seed` explicitly outside the writer-owner set so `create` continues to use the persisted stale-state confirmation path without acquiring a writer token.

## Implementation

- **Foundational logic:** Add one per-roadmap, cross-process writer guard that owns a mutable roadmap baseline from its first protected read through every return, exception, and interruption path. Expose an entry point that step 4 can acquire before local preflight. Use an opaque token for nested calls so the outer owner stays non-reentrant and nested helpers never acquire a second guard.

- **Scope the guard by roadmap, not repository.** A writer for one roadmap must block a second participating writer for that same roadmap while allowing a different roadmap to proceed. Do not reuse `plan_tool/repo_lock.py:repo_mutation_lock`: its repository-wide refusal behavior is a different contract.

- **Acquire before baseline reads.** Update `plan_tool/roadmap.py:run_roadmap`, `apply_roadmap_seeds`, `accept_roadmap_seed`, `materialize_plan_seed`, and `refresh_roadmap_seeds` to hold the guard before they read a canonical artifact, draft or promoted seed, or seed-state sidecar. Keep it through all success and failure paths.

- **Make the later local runner an owner.** Step 4 must acquire this guard before it reads the selected artifact for preflight or any seed-state baseline and retain the token through invalidation, candidate validation, and publication. The publisher accepts that outer token; it must not acquire a second lock after preflight.

- **Preserve nested ownership.** Keep `plan_tool/roadmap.py:_apply_roadmap_seeds` and `materialize_and_diff_one_plan` as nested reuse paths. Their callers must pass the existing token onward, including from `plan_tool/cli/roadmap_cmd.py:_cmd_roadmap_materialize` through each selected materialization, rather than acquiring once per row.

- **Do not broaden the owner set.** Leave `plan_tool/cli/authoring.py:_confirm_invalidated_roadmap_seed`, read-only roadmap views, and direct filesystem edits outside this guard. The guard coordinates participating writers; it does not claim to serialize unrelated readers or out-of-protocol changes.

- **Invalidate before backend work.** Provide a publisher-owned operation that loads the current sidecar, changes every extant entry to the existing raw `invalidated` status, and completes its atomic sidecar write before step 4 can construct backend context. Preserve the draft-seed path, digest, and `published` value; do not classify, regenerate, promote, or overwrite draft seed prose.

- **Use the narrow sidecar fsync seam.** Update `plan_tool/roadmap_seed_state.py:write_seed_state` to flush and `fsync` its temporary JSON file before `os.replace`, while retaining validation, same-directory replacement, and temporary-file cleanup. Do not add a destination-directory `fsync`, a power-loss publication guarantee, or recovery behavior: this seam only ensures the temporary sidecar content is synced before the local flow continues.

- **Validate before publishing.** Have `plan_tool/roadmap_revision_publish.py` render the step-2 candidate through the selected `RoadmapStage` renderer, parse those rendered bytes again through the matching parser, and run the selected stage’s existing gates over the normal upstream envelope. Do not supply a predecessor: broad re-entry continuity gates must stay inactive for this local path.

- **Publish only the validated candidate.** Replace exactly the selected stage artifact after parsing and gates succeed, using one same-filesystem atomic replacement. Keep all canonical artifacts unchanged on render, parse, gate, or write failure; a prior successful invalidation remains invalidated.

- **Keep the current broad path intact.** Continue to use `plan_tool/roadmap.py:_write_artifact` for broad-stage output and preserve its existing stage retry and overwrite behavior. The local publisher is a separate one-artifact path, not a rewrite of `--from-stage`.

- **Reject a multi-file transaction alternative.** Do not stage or roll back the artifact together with the sidecar. The required safety property is conservative seed invalidation followed by one atomic artifact replacement, not atomic visibility across those two paths.

## Tests

### Tests for this step

- `test_writer_guard_blocks_a_second_process_for_the_same_roadmap` — `tests/test_roadmap_revision_publish.py` proves a second participating writer cannot enter until the first releases its per-roadmap guard.

- `test_writer_guard_does_not_block_a_different_roadmap` — `tests/test_roadmap_revision_publish.py` proves the guard is not repository-wide.

- `test_nested_writer_receives_the_outer_token_without_reacquiring` — `tests/test_roadmap_revision_publish.py` proves nested publication and seed helpers reuse the owner’s token.

- `test_preinvalidate_marks_every_extant_entry_without_touching_seed_files` — `tests/test_roadmap_revision_publish.py` proves paths, digests, publication flags, draft bytes, and promoted bytes remain unchanged while every tracked entry becomes invalidated.

- `test_preinvalidate_flushes_the_sidecar_before_continuation` — `tests/test_roadmap_revision_publish.py` proves a state-write failure stops the caller before candidate publication can continue.

- `test_publish_renders_reparses_and_gates_the_candidate_without_a_predecessor` — `tests/test_roadmap_revision_publish.py` proves validation uses canonical rendered bytes, normal upstream context, and no same-artifact predecessor.

- `test_publish_replaces_only_the_selected_gate_valid_artifact` — `tests/test_roadmap_revision_publish.py` proves one valid candidate atomically changes its selected path and leaves sibling artifacts unchanged.

- `test_publish_gate_or_parse_failure_leaves_the_artifact_unchanged` — `tests/test_roadmap_revision_publish.py` proves no artifact write occurs for an invalid candidate while invalidated seed state remains conservative.

- `test_write_seed_state_fsyncs_before_replace` — `tests/test_roadmap_seed_state.py` proves `write_seed_state` flushes its temporary sidecar before replacing the destination.

- `test_invalidated_seed_confirmation_remains_a_lock_free_read` — `tests/test_roadmap_seed_state.py` proves `plan_tool/cli/authoring.py:_confirm_invalidated_roadmap_seed` still requires confirmation from the persisted invalidated state without joining the writer-owner set.

- `test_public_roadmap_mutation_owners_hold_the_guard_for_their_baseline` — `tests/test_roadmap.py` covers `run_roadmap`, seed application, seed acceptance, direct materialization, and refresh ownership.

- `test_local_runner_can_hold_the_publisher_guard_before_preflight` — `tests/test_roadmap_revision_publish.py` proves the exported guard can be acquired before any local artifact read and passed to invalidation and publication without a nested reacquire. Step 4 composes the interleaving test with a broad or seed writer.

- `test_materialize_command_acquires_the_guard_before_loading_its_batch` — `tests/cli/test_roadmap_cmd.py` proves `_cmd_roadmap_materialize` owns the batch lock before its initial artifact and classification reads.

Every listed test must be green before this step is complete.

## Acceptance criteria

- A participating writer acquires one per-roadmap guard before its first protected baseline read and releases it on every exit path.

- Step 4’s local runner uses the same guard before local preflight and passes its outer token to the publisher, so it cannot construct a candidate from a baseline another participating writer can replace.

- `plan_tool/roadmap.py:_apply_roadmap_seeds` and `materialize_and_diff_one_plan` reuse an owner-supplied token rather than reacquiring the guard.

- A local revision can mark every existing seed-state entry invalidated, flush and `fsync` its temporary sidecar before atomic replacement, and complete that write before step 4 invokes a backend. It does not promise destination-directory persistence after power loss.

- Seed invalidation preserves tracked entry metadata and never writes draft or promoted seed content.

- A candidate is rendered, re-parsed, and clears the selected stage’s existing gates with normal upstream artifacts and no predecessor before its artifact path changes.

- A successful local publication atomically replaces one selected artifact path; a rejected or failed publication changes no canonical artifact.

- `tests/test_roadmap_revision_publish.py`, `tests/test_roadmap.py`, `tests/test_roadmap_seed_state.py`, and `tests/cli/test_roadmap_cmd.py` pass.

## References

- [Python os.replace](https://docs.python.org/3.13/library/os.html#os.replace) — Use its same-filesystem replacement guarantee for the validated single-artifact publication path.

## Applicable guardrails

- **The plan’s “## Plan intent”, conservative seed invalidation:** Persist stale lifecycle state before later local-revision work and never treat an unsuccessful revision as refreshing a seed.

- **The plan’s “## Step intent”, mutable-baseline protection:** Coordinate every named participating writer around one stable roadmap baseline, including nested seed paths.

- **The plan’s “## Overview”, bounded local revision:** Limit publication to the selected canonical artifact after its existing validation contract passes.

- **The plan’s “## Out of scope”, publication and recovery behavior:** Do not add a checkpoint, recovery record, multi-file transaction, or altered broad-reentry behavior.

- **The plan’s “## Out of scope”, roadmap-derived seed work:** Do not generate, promote, refresh, or overwrite seed prose while invalidating lifecycle state.

- **The plan’s “## Out of scope”, reader and external-writer guarantees:** Do not promise a reader snapshot or coordination with filesystem writes outside this protocol.

## Deferred

- `plan_tool/roadmap_revision_run.py` and `plan_tool/prompts/roadmap-feedback-revision.md` — Step 4 owns the exclusive command, backend invocation, and terminal run-log outcomes that call this publisher.

- Consolidating the new per-roadmap guard with `plan_tool/repo_lock.py:repo_mutation_lock` or `plan_tool/telemetry.py:_acquire_append_lock` — Their scope and failure behavior differ; share an implementation only through a separately scoped refactor.

- Multi-artifact publication, crash recovery, and reader snapshots — These require a broader transaction design outside this plan’s local revision boundary.
