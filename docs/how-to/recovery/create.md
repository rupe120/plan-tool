# `create` resume & recovery

This document covers recovery specific to `plan-tool create`, including the
file-backed route lifecycle. The shared checkpoint, crash, and iteration
mechanics remain in [`RESUME_FLOW.md`](README.md); the operator route is
in [`CREATE_FROM_EXISTING_FLOW.md`](../pipeline/create-from-existing.md). The detailed
route/lifecycle table is in
[`CREATE_SEED_INGESTION_CONTRACT.md`](../../reference/contracts/seed-ingestion.md).

## TL;DR

- Checkpoints memoize successful authoring work; they are not plan-state
  snapshots.
- File-backed preflight refusals create neither a run record nor a routing
  checkpoint.
- Selected routes own their own routing-result retention. A re-run can reuse
  a retained split result, but a normalized iteration-incomplete plan continues
  in place with completeness audit rather than another create invocation.
- A published target remains available after an interruption or late failure;
  create does not discard a durable plan to resume a model call.

## What resumes on a re-run

The ordinary authoring calls continue to use their input-hashed checkpoints:

| Work | Checkpoint family | Reuse rule |
| --- | --- | --- |
| Direct raw-source split assessment | `create-direct-assessment*.json` | Reuse only while its direct route remains retained. |
| Non-direct preparation | `create-distill-seed*.json` | Reuse a valid preparation result; a malformed cached result gets the same bounded repair path as a fresh result. |
| Initial steps, references, reference docs, and body work | `create-initial-steps*.json`, `create-references*.json`, `create-reference-docs*.json`, `create-body-sections*.json` | Reuse matching successful work under the existing hash and `--no-resume` rules. |
| Iteration re-proposals | `create-*-iterN.json` | Save completed responses but do not replay them as a substitute for the edited plan. |

The selected source is always `seed_body` when present, otherwise
`from_description`; an empty `seed_body` remains selected. An unmatched fence
or a missing, duplicate, empty, or placeholder `## References` section refuses
before any row above is read or written.

## When checkpoints are kept vs swept

Route-owned retention applies after preflight. This is a route summary, not a
second lifecycle contract; use the ingestion contract for the authoritative
publication and archival table.

| Result | Checkpoint disposition | Source and recovery boundary |
| --- | --- | --- |
| Preflight refusal | None | Raw source stays available; fix the input and start a new invocation. |
| Direct, clean publication | Discard completed routing and authoring checkpoints. | `cmd_create` archives the raw source chain only after finalization; library callers retain their source. |
| Normalized, clean publication | Discard completed preparation and authoring checkpoints. | `cmd_create` archives the raw source chain and normalized artifact only after finalization. |
| Normalized, iteration incomplete | Retain preparation and continuation checkpoints. | Keep the raw source and emit no normalized archive artifact. Run `plan-tool completeness-audit <slug> --iterate` on the registered plan; do not retry through its source path. |
| Split | Retain the versioned split result for retry. | Keep raw source and any worksheet for carving; no plan or manifest publishes. |
| Post-preflight refused | Remove the terminal direct-assessment or preparation result. | Keep raw source; no plan, manifest, or normalized artifact publishes. |

Split and refused outcomes roll back a collision-created branch binding because
they publish no plan. The normal crash and target-retention rules remain
separate: a target that has already published stays available for repair.

## Target-write recovery boundary

Create saves its decision work before an authorized replacement archive or the
initial target write. After a target exists, interruption or a late error keeps
that target. A parse-valid unregistered target may be explicitly adopted; a
registered plan remains the canonical recovery target and is repaired in
place. This rule applies independently of the file-backed source archive,
which `cmd_create` performs only for the clean routes named above.

## Why a normalized incomplete result is not re-created

An iteration-incomplete normalized result has already published a registered
plan. Re-running `create` would re-enter collision handling and rebuild from
the source rather than continue the recorded plan. Use
`plan-tool completeness-audit <slug> --iterate` to finish its outstanding
authoring work in place.

## Source map

| Concern | Owner |
| --- | --- |
| Route lifecycle | `plan_tool/create.py` (`file_backed_route_lifecycle`, `_apply_file_backed_checkpoint_lifecycle`, `_finalize_create_plan`) |
| CLI route handling and source archival | `plan_tool/cli/authoring.py:cmd_create` |
| Checkpoint primitive and shared recovery | `plan_tool/checkpoint.py`; [`RESUME_FLOW.md`](README.md) |
| Route recovery fixtures | `tests/test_create.py`, `tests/test_distill.py`, `tests/cli/test_authoring_cmds.py` |
