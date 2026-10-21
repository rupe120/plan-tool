> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 6 — Set versioned per-route checkpoints and artifact handling for direct, normalized, split, and refused outcomes

## Summary

Make route lifecycle explicit in `plan_tool/create.py` and
`plan_tool/cli/authoring.py`. Route selection from steps 2, 3, and 5 must
decide checkpoint retention, raw-source archival, normalized-artifact handling,
and no-plan cleanup. Keep archival after clean finalization, retain the
source/checkpoints needed for normalized iteration-incomplete recovery, and keep
rejected or split source material recoverable. On green, each file-backed
terminal route has one testable artifact and checkpoint outcome.

## Table of Contents

- [Summary](#summary) — Reviewer overview of the lifecycle change.
- [Table of Contents](#table-of-contents) — Links to every section in this detail.
- [Why](#why) — The unclear lifecycle boundary this step closes.
- [Input](#input) — Upstream route and existing persistence contracts.
- [Files (creates vs edits)](#files-creates-vs-edits) — Files this step changes.
- [Implementation](#implementation) — Route-owned checkpoint and artifact rules.
- [Tests](#tests) — Focused lifecycle coverage.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Persistence and test references.
- [Applicable guardrails](#applicable-guardrails) — Plan boundaries for this step.
- [Deferred](#deferred) — Work left to later documentation and broader policy work.

## Why

`plan_tool/create.py:propose_distilled_seed_from_claude`, `plan_tool/create.py:_finalize_create_plan`, and `plan_tool/cli/authoring.py:cmd_create` each own part of the old distill lifecycle, so cache cleanup and archival follow producer-specific fields rather than the selected route. Once steps 2 and 3 distinguish direct, normalized, split, and refused outcomes, that behavior can archive an artifact that does not belong to the route or retain a response that no longer matches its parser contract. The lifecycle table in the plan must become the one decision point before route-specific checkpoints or archives are changed.

## Input

- **Step 2 direct outcome:** Consume the direct route and its raw-only split assessment. Direct has no normalized payload.
- **Step 3 preparation outcome:** Consume its closed `normalized`, `split`, and `refused` result. Refusal remains terminal and must not become reusable raw fallback input.
- **Step 5 public route handoff:** Read the selected route from `plan_tool/create.py:CreateResult`; do not infer it from `plan_path`, `split_proposal`, or `distilled_seed`.
- **Existing checkpoint contract:** Reuse `plan_tool/checkpoint.py:checkpoint_path`, `load_if_valid`, `save_checkpoint`, and `discard_checkpoint`. Keep the generic checkpoint schema unchanged.
- **Existing archive contract:** Preserve `plan_tool/create.py:archive_existing_source`, `ArchiveResult`, replacement notices, paired detail-bundle handling, and numbered archive generations.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `plan_tool/create.py` — version route-specific checkpoint inputs, validate cached route results, and apply route-specific cleanup after terminal create handling.
  - `plan_tool/cli/authoring.py` — replace producer-field archive decisions with selected-route lifecycle handling after completed publication.
  - `tests/test_distill.py` — cover checkpoint versioning, retention, discard, and library-level terminal outcomes.
  - `tests/cli/test_authoring_cmds.py` — cover CLI archival timing and all no-plan artifact outcomes.

## Implementation

- **Foundational logic:** Dispatch checkpoint and artifact lifecycle from the closed selected route.

- **Use the route as the sole lifecycle selector.** Add a small route-owned lifecycle seam near `plan_tool/create.py:CreateResult` and `plan_tool/create.py:_finalize_create_plan`, or an equivalent local boundary. It must receive the route, source identity, and optional normalized payload explicitly.

- **Apply the selected lifecycle table.**

  | Route | Required lifecycle |
  |---|---|
  | References preflight refusal | Read and write no routing checkpoint; leave the source unchanged; create no normalized artifact. |
  | `direct` | Publish the plan and manifest, then archive the raw source chain only; create no normalized artifact; discard direct-assessment and stale preparation checkpoints. |
| `normalized`, clean finalization | Publish the plan and manifest, then archive both the raw source chain and the emitted normalized artifact; discard the successful preparation checkpoint. |
| `normalized`, iteration incomplete | Keep the already-published registered plan, raw source, preparation checkpoint, and convergence checkpoints; write or archive no normalized artifact. Direct the operator to `plan-tool completeness-audit <slug> --iterate`, which resumes the existing plan in place and consumes no source path. |
| `split` | Write no plan or manifest entry; retain the raw source and any worksheet from `plan_tool/cli/authoring.py:_emit_split_proposal`; retain the versioned split result for retry; roll back any collision-created branch binding. |
  | `refused` | Write no plan or manifest entry; retain the raw source; write no normalized artifact; remove only a transient artifact created by this invocation; discard the direct-assessment or preparation result. |

- **Version route checkpoints by their actual contract.** The preparation checkpoint input must include the raw source, the rendered preparation prompt or a stable digest of it, and a local result-contract revision. Give direct assessment its own route discriminator and contract revision so a direct checkpoint cannot be read as preparation output. Do not change `plan_tool/checkpoint.py:CHECKPOINT_SCHEMA_VERSION`, which applies to unrelated checkpoint users.

- **Validate a cache hit through the same parser.** A matching hash permits reuse but does not make cached model text trusted. Route cached responses through the same result parsing and validation as a fresh response; an invalid cached response must reach the route’s refusal/discard path, not raw passthrough.

- **Separate clean finalization from iteration-incomplete recovery.** Run
  success cleanup and archival only after create_plan returns a clean finalized
  result, not merely after initial publication writes a target. When
  iteration_stage_failure is set, retain the registered plan, raw source,
  preparation result, and convergence checkpoints; emit no normalized sibling
  or archive. The retry is plan-tool completeness-audit <slug> --iterate
  against the existing plan, not a second create invocation and not a path to
  the retained source.

- **Make normalized archival route-owned.** Replace `plan_tool/cli/authoring.py:cmd_create`’s generic `result.distilled_seed` archive branch with an explicit `normalized` branch. Materialize the normalized artifact only after publication, then archive it through the existing archive contract. Direct, split, and refused routes must never create that sibling artifact.

- **Keep the provenance source chain together.** Retain `cmd_create`’s existing `CreateResult.provenance` handling for published direct and normalized routes. It must remain after successful publication and must not run for split or refused results.

- **Avoid partial durable artifacts.** Use the existing atomic/durable write helpers in `plan_tool/fileio.py` for any new normalized-artifact write, and strengthen the target-write path in `plan_tool/create.py:archive_existing_source` if needed so an interrupted archive never presents a partly written raw or normalized archive file. Preserve its public result shape and callers such as `plan_tool/cli/annotate_cmd.py` and `plan_tool/sweep.py`.

- **Keep reporting ownership unchanged.** Step 5 owns route output, exit codes, and the route observation. Continue emitting checkpoint hit, save, and discard events through the active run logger’s existing checkpoint methods; do not add a second route-reporting channel.

## Tests

Every test below must be green before this step is complete.

### Tests for this step

- `tests/test_distill.py::test_preparation_checkpoint_changes_when_prompt_or_result_contract_changes` — the same raw source cannot reuse a preparation result after either contract input changes.
- `tests/test_distill.py::test_direct_checkpoint_uses_its_own_route_contract` — a direct assessment checkpoint cannot satisfy preparation reuse.
- `tests/test_distill.py::test_cached_invalid_route_result_is_refused_and_discarded` — a matching but invalid cached response never becomes raw fallback input.
- `tests/test_distill.py::test_direct_success_discards_direct_and_stale_preparation_checkpoints` — direct publication clears both route-relevant checkpoint kinds and exposes no normalized payload.
- `tests/test_distill.py::test_normalized_success_discards_preparation_checkpoint_after_finalization` — normalized cleanup happens only after complete successful finalization.
- `tests/test_distill.py::test_normalized_iteration_incomplete_retains_source_and_checkpoints` — an incomplete normalized result keeps its raw source and route/convergence checkpoints without a normalized archive artifact.
- `tests/test_distill.py::test_split_retains_versioned_result_for_retry_without_plan_or_manifest` — split keeps its reusable result while writing neither durable plan output.
- `tests/test_distill.py::test_refused_result_discards_route_checkpoint_and_creates_no_normalized_artifact` — refused input leaves its raw source recoverable and no reusable route state.
- `tests/cli/test_authoring_cmds.py::test_cmd_create_direct_archives_raw_source_only_after_completed_publication` — direct archives the source only after the completed success path and never writes a normalized sibling.
- `tests/cli/test_authoring_cmds.py::test_cmd_create_normalized_archives_raw_and_normalized_artifacts_after_publication` — normalized output archives both artifacts only after plan and manifest publication.
- `tests/cli/test_authoring_cmds.py::test_cmd_create_normalized_iteration_incomplete_prints_in_place_resume` — the incomplete route prints the completeness-audit command for the registered slug and does not suggest rerunning create from a source path.
- `tests/cli/test_authoring_cmds.py::test_cmd_create_split_retains_source_worksheet_and_checkpoint` — split preserves the source and worksheet, retains its checkpoint, and writes no plan or manifest entry.
- `tests/cli/test_authoring_cmds.py::test_cmd_create_refused_retains_source_and_removes_invocation_transient_artifact` — refused routes leave no plan, manifest, normalized artifact, or reusable checkpoint.
- `tests/cli/test_authoring_cmds.py::test_cmd_create_archive_write_never_exposes_partial_normalized_artifact` — an archive write failure leaves a complete prior artifact or no new artifact, never partial text.

## Acceptance criteria

- File-backed route lifecycle is selected from the explicit route result, never from nullable artifact fields.
- Direct publishes then archives only its raw source chain, clears route-relevant checkpoints, and creates no normalized artifact.
- Normalized publishes then archives its raw source chain and normalized artifact, and its checkpoint hash changes when its prompt or result contract changes.
- A normalized iteration-incomplete route retains its registered plan, raw
  source, and route/convergence checkpoints, emits no normalized archive
  artifact, and names the in-place completeness-audit recovery command.
- Split writes no plan or manifest entry and retains its source, worksheet, and versioned split result for retry.
- Refused writes no plan or manifest entry, retains its source, creates no normalized artifact, and leaves no reusable route checkpoint.
- References preflight remains the no-checkpoint, no-run-record refusal exception.
- Route checkpoint reuse validates cached text through the active result contract.
- `tests/test_distill.py` and `tests/cli/test_authoring_cmds.py` lifecycle cases are green.

## References

- [Python `os` module — `os.replace` and file descriptor operations](https://docs.python.org/3/library/os.html#os.replace) — Use for atomic replacement and durability requirements around checkpoint and archive publication.
- [pytest temporary directories](https://docs.pytest.org/en/stable/how-to/tmp_path.html) — Use for hermetic checkpoint, archive, and interrupted-write cases.
- [Python `enum` — Support for enumerations](https://docs.python.org/3/library/enum.html) — Use for maintaining the closed route vocabulary at the lifecycle boundary.

## Applicable guardrails

- **The plan’s “## Plan intent”** — preserve supplied source authority and make preparation routes visible; lifecycle handling must not silently replace or discard a source on a no-plan route.
- **The plan’s “## Step intent”** — use the selected lifecycle table before changing helpers or archive calls; do not let individual producer branches decide retention.
- **The plan’s “## Out of scope”, route boundaries** — do not add a broader heading audit, replace `SplitProposal`, change unrelated authoring contracts, or rewrite historical artifacts.
- **The plan’s “## Out of scope”, canonical-heading scope** — do not add heading aliases or alter the exact-heading policy while implementing persistence.

## Deferred

- Operator-facing lifecycle and resume documentation — step 7 owns the ingestion, resume, CLI, seed-format, arc, and backlog updates.
- Generic checkpoint-schema migration — route contract revisions belong in this focused create lifecycle; changing the shared checkpoint format needs separate work.
