> **Replaced**: this file has been superseded by `docs/implementation-plans/2-decompose-create-plan-phases.md`.
> Preserved here for history; do not edit.

## Overview

Refactor `plan_tool/create.py:create_plan` into a short top-level sequence of named, same-file phase functions so its orchestration and dense convergence loop are easier to review. Preserve its public signature, observable behavior, error conditions, checkpoint semantics, phase ordering, inputs, outputs, and side effects. Keep the outer convergence loop intact as one named function with explicit input and return state rather than introducing a new abstraction.

## Problem statement

`plan_tool/create.py:create_plan` contains dense orchestration and a `while True` convergence loop whose phase boundaries are difficult to review. Naming its existing phases makes the flow clearer while retaining the direct-call contract covered by `tests/test_create.py` and avoiding any behavior change.

## Architecture

Keep `create_plan` as a short sequence of same-file functions in `plan_tool/create.py`. Extract the existing pre-loop handoffs for slug/output-dir resolution, metadata prompt, seed distillation, step resolution, change-type review, plan assembly, concept bootstrap/merge, intent offer, reference proposal, body synthesis, TODO gate, collision archival, write/reparse, plan-details rename, fingerprint/concept sync, and manifest append. Extract the post-loop checkpoint cleanup, path-issue advisory, post-loop concept sync, and pending-decision advisory. Pass shared state explicitly between phases rather than introducing closures, except for convergence-loop-local state wholly owned by the extracted loop.

Extract the outer convergence loop as one named function with explicit input and return state, while keeping its drift check, triage, apply, re-derivation, and checkpoint sequencing in their current order. After the write phase, `plan_path` remains the single source of truth, and later phases re-parse from disk because `apply_finding` can mutate the file directly.

The extracted loop calls `write_plan`, never `write_new_plan`, because `write_new_plan` would rebuild the body and discard sections written by an earlier `apply_finding`; preserve that distinction in a terse docstring on the loop-owning function. Resolve `references` once before the loop, retain the per-iteration `refs_proposal` as a separate value, and apply the loop's References patch even when that iteration's step re-proposal fails.

`create_plan` continues to delegate individual backend calls to existing named helpers. This refactor names only the orchestration connecting those calls and does not change the dependency surface.

## Out of scope

- Changing `create_plan`'s signature, behavior, error conditions, checkpoint semantics, or ordering constraints; this work is organization-only.
- Unifying the create convergence loop with `generate_detail`'s per-step loop; a shared implementation requires separately scoped follow-up work.
- Decomposing `generate_detail`; `plan-seeds/decompose-generate-detail-phases.md` owns that independent refactor.
- Refactoring `plan_tool/cli/run_cmd.py:cmd_run`; that is a separate concern.

## Risks

- **High — convergence-loop reordering:** plan mutation, drift, or checkpoint behavior can change. Mitigation: keep the loop intact as one extracted function and preserve its current sequence.
- **High — public-signature drift:** changing the dense direct-call contract can break `tests/test_create.py`. Mitigation: retain the signature exactly.
- **Medium — incomplete phase state:** missing state can change post-write reparse or reference behavior. Mitigation: pass shared state explicitly and characterize any stated invariant that lacks an existing test before extraction.

## Testing

Use `tests/test_create.py` as the primary regression suite. Before extraction, add targeted characterization coverage only for load-bearing ordering or state invariants that lack a pin, including the unconditional References patch. Keep existing assertions unchanged, then run the unchanged existing suite and the repository test suite required by the affected modules.

## Acceptance criteria

- `plan_tool/create.py:create_plan` is a short top-level sequence of named, same-file phase functions, and its outer convergence loop is one named function.
- `create_plan` retains its exact public signature and observable behavior.
- Post-write use of `plan_path` as the source of truth and the use of `write_plan` rather than `write_new_plan` are preserved.
- `references`, `refs_proposal`, and the unconditional References-patch behavior are preserved and characterized where necessary.
- `tests/test_create.py` passes without weakening existing assertions.

## Deferred

- Decompose `generate_detail` under `plan-seeds/decompose-generate-detail-phases.md`; it is an independent refactor.
- Consider a shared implementation for the two convergence loops in separately scoped follow-up work.
- Decompose `plan_tool/cli/run_cmd.py:cmd_run` in separately scoped follow-up work.

## Input

The refactor consumes the existing `plan_tool/create.py:create_plan` public signature and observable direct-call contract, as covered by `tests/test_create.py`. It also preserves the existing orchestration state contracts around `plan_path`, `references`, `refs_proposal`, `apply_finding`, `write_plan`, and `write_new_plan`; characterization coverage is added only where a stated load-bearing rule is not already pinned.
