> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 6 — Set versioned per-route checkpoints and artifact handling for direct, normalized, split, and refused outcomes

## Summary

Make the selected file-backed route control checkpoint cleanup and source-artifact handling in `plan_tool/create.py` and `plan_tool/cli/authoring.py`. Keep the lifecycle rules in one route-owned decision point, with CLI-only archival occurring only after the route reaches its permitted terminal state. Version direct-assessment and preparation cache inputs by their actual prompt and result contracts, while preserving the shared checkpoint file format. On green, direct, normalized, split, and refused outcomes have distinct, testable retention behavior.

## Table of Contents

- [Summary](#summary) — Reviewer overview of the lifecycle change.
- [Table of Contents](#table-of-contents) — Links to each section in this detail.
- [Why](#why) — The producer-driven lifecycle this step replaces.
- [Input](#input) — Upstream route results and existing persistence contracts.
- [Files (creates vs edits)](#files-creates-vs-edits) — Files changed by this step.
- [Implementation](#implementation) — Route-owned checkpoint and artifact rules.
- [Tests](#tests) — Lifecycle cases that must be green.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Persistence and test references.
- [Applicable guardrails](#applicable-guardrails) — Scope limits for this step.
- [Deferred](#deferred) — Work left to later documentation or shared-contract changes.

## Why

`plan_tool/create.py:propose_distilled_seed_from_claude`, `plan_tool/create.py:_finalize_create_plan`, and `plan_tool/cli/authoring.py:cmd_create` currently make cache and archive choices from the distill producer and publication state. Steps 2, 3, and 5 instead make `direct`, `normalized`, `split`, and `refused` explicit outcomes, so lifecycle decisions must follow that route rather than the presence of `CreateResult.distilled_seed` or `CreateResult.plan_path`. Without that boundary, an incomplete normalized create can archive the source needed for recovery, or a cached response can survive a parser-contract change.

## Input

- **Step 2 direct outcome:** Consume the raw-only direct assessment and its `direct`, split, or refused result. Direct has no normalized payload.

- **Step 3 preparation outcome:** Consume its closed normalized, split, or refused preparation result. A refused result remains terminal and must not become raw-source fallback input.

- **Step 5 public result:** Read the explicit selected route from `plan_tool/create.py:CreateResult`. Do not infer it from `CreateResult.plan_path`, `CreateResult.split_proposal`, or `CreateResult.distilled_seed`. A direct library result remains non-destructive; only `cmd_create` consumes the route to archive a supplied source or normalized sibling.

- **Existing persistence seams:** Reuse `plan_tool/checkpoint.py:checkpoint_path`, `load_if_valid`, `save_checkpoint`, and `discard_checkpoint`, plus `plan_tool/create.py:archive_existing_source` and `ArchiveResult`. Keep the shared checkpoint schema unchanged.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `plan_tool/create.py` — add route-owned checkpoint versioning, cached-result validation, cleanup, and safe normalized-artifact handling.
  - `plan_tool/cli/authoring.py` — make post-publication source and normalized-artifact archival follow the selected route and finalization state.
  - `tests/test_distill.py` — cover route cache keys, cache validation, cleanup, retention, and library-level outcomes.
  - `tests/cli/test_authoring_cmds.py` — cover CLI archive timing, no-plan outcomes, and normalized incomplete recovery.

## Implementation

- **Foundational logic:** Select checkpoint retention and artifact handling from the explicit terminal route.

- **Keep one lifecycle authority.** Add a small route-owned lifecycle value or helper near `plan_tool/create.py:CreateResult` and `plan_tool/create.py:_finalize_create_plan`. It must receive the selected route, source identity, finalization state, and optional normalized payload explicitly. Do not duplicate route inference in `plan_tool/create.py:create_plan` and `plan_tool/cli/authoring.py:cmd_create`.

- **Separate route ownership from destructive ownership.** `create_plan` owns route selection, route-result validation, and checkpoint cleanup, but never calls `archive_existing_source` or writes a normalized sibling for a public file-backed caller. `cmd_create` owns every raw/provenance/normalized artifact write and archive call. It may act only after the lifecycle helper returns a clean CLI archival eligibility decision; iteration-incomplete, split, and refused never qualify.

- **Apply the selected lifecycle.**

  | Result | Required lifecycle |
  |---|---|
  | Input-syntax or References-preflight refusal | Write no route checkpoint or normalized artifact, retain the source, and keep the existing no-selected-route, no-run-record exit. |
  | `direct` | After clean publication and finalization, `cmd_create` archives the raw source chain only; discard direct-assessment and stale preparation checkpoints; never write a normalized artifact. A library caller retains its source. |
  | `normalized`, clean finalization | After clean publication and finalization, `cmd_create` archives the raw source chain and normalized artifact; discard the successful preparation checkpoint. A library caller retains its source and receives no normalized sibling write. |
  | `normalized`, iteration incomplete | Keep the registered plan, raw source, preparation checkpoint, and convergence checkpoints; do not emit or archive a normalized artifact; retain the existing in-place `plan-tool completeness-audit <slug> --iterate` recovery path. |
  | `split` | Write no plan or manifest entry; retain the source, the existing split worksheet behavior, and the versioned route result for retry; roll back any collision-created branch binding; do not create a normalized artifact. |
  | `refused` | Write no plan or manifest entry; retain the source; discard the route result checkpoint; roll back any collision-created branch binding; create no normalized artifact and remove only invocation-owned transient files. |

- **Version each route result by its contract.** Update the input hash used by the preparation path rooted at `plan_tool/create.py:propose_distilled_seed_from_claude` so it includes the raw source, rendered preparation prompt or stable prompt digest, and a local result-contract revision. Give direct assessment a separate route discriminator and contract revision. A direct cache must never be parsed as a preparation cache, and a prompt or result-shape change must invalidate old route output without changing `plan_tool/checkpoint.py:CHECKPOINT_SCHEMA_VERSION`.

- **Parse cache hits as fresh responses.** A matching hash only permits reuse. Send cached text through the same parsing and validation path that accepts a new model response. An invalid cached preparation response is discarded and takes step 3's single repair call; its invalid repair returns `refused`. An invalid cached direct assessment is discarded and returns its existing no-repair refused result. Neither path restores raw passthrough or retries indefinitely.

- **Cover early no-plan exits.** `plan_tool/create.py:_prepare_create_plan` returns no-plan `CreateResult` values before `plan_tool/create.py:_finalize_create_plan` runs. Ensure split retention and refused cleanup happen on those exits as well as in the published-plan finalization path. When `plan_tool/cli/authoring.py:_create_branch_collision_gate` has created an invocation-local branch binding, both no-plan routes call its existing rollback seam before emitting their outcome; restore the invocation's prior binding without deleting a branch the operator may need to inspect.

- **Separate clean completion from recovery.** `plan_tool/create.py:_finalize_create_plan` currently keeps checkpoints when `iteration_stage_failure` is set, while `plan_tool/cli/authoring.py:cmd_create` runs source archival in the common success tail. Make the route and incomplete-state check happen before that archival work. A normal success may archive only after finalization succeeds; an incomplete normalized route must leave the source and checkpoints available for the existing plan, not for a second create invocation.

- **Make normalized artifacts route-owned.** Replace the generic `CreateResult.distilled_seed` archival branch in `plan_tool/cli/authoring.py:cmd_create` with a normalized-route branch. Materialize the normalized sibling only after clean publication, then archive it through `plan_tool/create.py:archive_existing_source`. Direct, split, refused, and every public `create_plan` route must never create that sibling.

- **Keep the source chain together.** Retain `CreateResult.provenance` handling for successful direct and normalized routes, including an original seed that the supplied canonical source points to. Split and refused outcomes must not archive either source in that chain.

- **Avoid partial archives.** Use the existing durable write support in `plan_tool/fileio.py:durable_write_text` for new raw or normalized archive-file writes before removing the source. Preserve `plan_tool/create.py:archive_existing_source`’s public signature and `ArchiveResult` behavior because `plan_tool/cli/annotate_cmd.py` also calls it. A failed archive may leave the original source in place or report a recoverable skip, but it must not expose partial normalized content.

- **Keep reporting ownership unchanged.** Continue using the active logger’s `checkpoint_hit`, `checkpoint_save`, and `checkpoint_discard` methods. Step 5 owns selected-route reporting and exit codes, so this step must not add a second route-reporting channel.

## Tests

### Tests for this step

- `tests/test_distill.py::test_route_checkpoint_key_changes_with_prompt_or_result_contract` — the same raw source cannot reuse preparation output after its prompt or result contract changes.

- `tests/test_distill.py::test_direct_assessment_checkpoint_cannot_satisfy_preparation` — direct and preparation results use distinct cache identities and parsing contracts.

- `tests/test_distill.py::test_invalid_cached_preparation_response_is_discarded_and_repaired_once` — a matching invalid preparation cache entry is discarded, takes one repair invocation, and returns its repaired normalized/split result or refused outcome without raw fallback.

- `tests/test_distill.py::test_invalid_cached_direct_assessment_is_discarded_and_refused` — a matching invalid direct-assessment cache entry is discarded and returns the selected no-repair refused outcome.

- `tests/test_distill.py::test_direct_success_archives_raw_source_only_and_discards_route_checkpoints` — a completed direct route keeps no normalized artifact and clears its direct and stale preparation state.

- `tests/test_distill.py::test_normalized_clean_success_archives_raw_and_normalized_artifacts_after_finalization` — normalized archival occurs only after finalization succeeds and clears its preparation checkpoint.

- `tests/test_distill.py::test_normalized_iteration_incomplete_retains_source_and_checkpoints` — an incomplete normalized route keeps its registered plan, source, route checkpoint, and convergence checkpoints without creating a normalized archive artifact.

- `tests/test_distill.py::test_split_retains_versioned_result_without_plan_or_manifest` — split preserves reusable route output while writing neither a plan nor a manifest entry.

- `tests/test_distill.py::test_refused_route_discards_only_its_checkpoint_and_keeps_source` — refusal leaves the source recoverable, creates no normalized artifact, and does not remove pre-existing files.

- `tests/test_distill.py::test_file_backed_library_routes_never_archive_or_write_normalized_siblings` — direct and normalized public `create_plan` calls expose their route while leaving the caller-owned source and sibling path untouched.

- `tests/cli/test_authoring_cmds.py::test_cmd_create_split_rolls_back_branch_collision_before_worksheet` — a split after collision handling restores the original branch binding before its worksheet and no-plan result are emitted.

- `tests/cli/test_authoring_cmds.py::test_cmd_create_refused_rolls_back_branch_collision_before_exit` — a post-preflight refusal after collision handling restores the original branch binding while retaining the source and reporting exit 2.

- `tests/cli/test_authoring_cmds.py::test_cmd_create_direct_archives_provenance_source_chain_only_after_clean_completion` — direct archives the supplied source chain only after successful completion and never creates a normalized sibling.

- `tests/cli/test_authoring_cmds.py::test_cmd_create_normalized_archives_source_chain_and_normalized_artifact` — normalized clean completion archives both route-owned artifacts and retains existing archive notices.

- `tests/cli/test_authoring_cmds.py::test_iteration_incomplete_still_runs_completed_create_tail` — update the existing common-tail test so a normalized iteration-incomplete route retains its source and prints the in-place recovery command instead of archiving the source.

- `tests/cli/test_authoring_cmds.py::test_cmd_create_split_and_refused_leave_no_normalized_artifact` — both no-plan outcomes retain their source and avoid normalized-artifact creation while preserving step 5’s route and branch behavior.

- `tests/cli/test_authoring_cmds.py::test_cmd_create_normalized_archive_failure_never_exposes_partial_artifact` — a failed normalized archive leaves either a complete recoverable artifact or its original source, never partial text.

Every listed test must be green before this step is complete.

## Acceptance criteria

- File-backed lifecycle behavior is selected from the explicit route result, never from nullable artifact fields.
- `create_plan` applies route and checkpoint policy without destructive source or normalized-artifact writes; `cmd_create` alone archives a clean eligible source chain.

- Direct clean completion archives only its raw source chain, removes route-relevant checkpoints, and creates no normalized artifact.

- Normalized clean completion archives its raw source chain and normalized artifact only after finalization succeeds.

- A normalized iteration-incomplete result retains its registered plan, raw source, preparation checkpoint, and convergence checkpoints; it emits no normalized archive artifact and names the in-place recovery command.

- Split writes no plan or manifest entry, retains its source and reusable versioned result, and creates no normalized artifact.

- Refused writes no plan or manifest entry, retains its source, creates no normalized artifact, and leaves no reusable route checkpoint.

- Split and refused both roll back an invocation-local collision-created branch binding before their no-plan outcome is surfaced, without deleting a branch.

- Route checkpoint reuse validates cached text through the active result parser, a prompt or result-contract revision invalidates older output, and cached preparation invalidity receives the same one repair call as fresh invalidity.

- `uv run pytest tests/test_distill.py tests/cli/test_authoring_cmds.py -q` passes.

## References

- [Python `os` module — `os.replace` and file descriptor operationshttps: — Use for atomic replacement and durability around route checkpoints and archive files.

- [Python `enum` — Support for enumerationshttps: — Use for the closed route vocabulary at the lifecycle boundary.

- [pytest temporary directorieshttps: — Use for hermetic checkpoint, archive, and interrupted-write cases.

## Applicable guardrails

- **The plan’s “## Plan intent”, supplied-source authority** — preserve supplied source material on every no-plan or incomplete route; lifecycle handling must not silently discard it.

- **The plan’s “## Step intent”, route-owned lifecycle** — select the lifecycle table before changing checkpoint or archive helpers, rather than letting producer-specific fields decide retention.

- **The plan’s “## Out of scope”, split boundary** — retain `SplitProposal` and its visible no-plan workflow; do not create another split command or convert a split into a single plan.

- **The plan’s “## Out of scope”, authoring-contract boundary** — limit this work to route persistence and artifact timing; do not change step, References-research, or body-synthesis contracts beyond their selected route.

- **The plan’s “## Out of scope”, canonical-heading scope** — do not add heading aliases or broaden source validation while implementing lifecycle handling.

## Deferred

- Operator-facing ingestion and resume documentation — step 7 owns the maintained documentation sweep after the route lifecycle ships.

- Shared checkpoint-schema migration — route-specific revisions must stay local to create; changing `plan_tool/checkpoint.py`’s generic schema requires separate work.
