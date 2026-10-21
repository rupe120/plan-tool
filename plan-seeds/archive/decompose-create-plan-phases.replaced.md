> **Replaced**: this file has been superseded by `docs/implementation-plans/2-decompose-create-plan-phases.md`.
> Preserved here for history; do not edit.

# Seed: decompose `create_plan` into named phase functions

## Outcome

`plan_tool/create.py:create_plan` becomes a short top-level sequence of
same-file, named phase functions while preserving its public signature and all
observable behavior. Its dense convergence `while True` loop becomes one
reviewable named function, not a new abstraction or a behavior change.

## In scope

- Extract the pre-loop orchestration at the natural handoffs already visible in
  `create_plan`: slug/output-dir resolution, metadata prompt, seed distillation,
  step resolution, change-type review, plan assembly, concept bootstrap/merge,
  intent offer, reference proposal, body synthesis, TODO gate, collision
  archival, write/reparse, plan-details rename, fingerprint/concept sync, and
  manifest append.
- Extract the post-loop cleanup and advisory work: checkpoint cleanup,
  path-issue advisory, post-loop concept sync, and pending-decision advisory.
- Extract the outer convergence loop as one named function with explicit input
  and return state. Keep its dense body intact: drift check, triage, apply,
  re-derivation, and checkpoint sequencing remain in their current order.
- Add characterization coverage only where a load-bearing ordering/state rule
  below lacks a test before the extraction begins.

## Out of scope

- Changing `create_plan`'s signature, behavior, error conditions, checkpoint
  semantics, or any ordering constraint.
- Unifying the create convergence loop with `generate_detail`'s per-step loop.
- Decomposing `generate_detail`; the companion
  `plan-seeds/decompose-generate-detail-phases.md` seed owns that independent
  refactor.
- Refactoring `plan_tool/cli/run_cmd.py:cmd_run`.

## Allowed behavior changes

None. Every phase preserves its existing inputs, outputs, side effects,
ordering relative to its neighbors, and error-raising conditions.

## Allowed reorganization

Split only `create_plan`'s body into named functions in `plan_tool/create.py`.
Pass shared state explicitly between phases rather than using new closures,
except for convergence-loop-local state that remains wholly owned by the
extracted loop.

## Architecture

`create_plan` already delegates individual backend calls to named helpers. This
refactor names the orchestration that connects those calls without changing its
dependency surface.

- After the write phase, `plan_path` stays the single source of truth. Later
  phases re-parse from disk because `apply_finding` can mutate the file
  directly.
- The extracted loop calls `write_plan`, never `write_new_plan`; the latter
  would rebuild the body and discard sections an earlier `apply_finding` wrote.
  Preserve this distinction in a terse docstring at the loop's owning function.
- `references` is resolved once before the loop. The per-iteration
  `refs_proposal` remains a separate value and must not replace it.
- The loop applies its References patch even if that iteration's step
  re-proposal fails.

## Risks

- High: reordering the convergence loop can alter plan mutation, drift, or
  checkpoint behavior. Keep it as one extracted function.
- High: changing the public signature breaks the dense direct-call contract in
  `tests/test_create.py`; retain it exactly.
- Medium: passing state incompletely between phases can alter post-write
  reparse or reference behavior; pin any currently untested rule first.

## Testing

`tests/test_create.py` remains the primary regression suite. Add targeted
characterization tests only for stated invariants that lack a pin, including
the unconditional References patch, then run the unchanged existing suite and
the repository test suite required by the affected modules.

## Acceptance criteria

- `create_plan` is a short top-level sequence of named same-file phase
  functions, and its outer convergence loop is one named function.
- Its public signature and observable behavior are unchanged.
- The post-write `plan_path`, `write_plan`, references, and unconditional
  References-patch rules are preserved and characterized where necessary.
- `tests/test_create.py` passes without weakening existing assertions.

## Deferred

- The independent `generate_detail` phase extraction belongs to
  `plan-seeds/decompose-generate-detail-phases.md`.
- A shared implementation for the two convergence loops and a `cmd_run`
  decomposition require separately scoped follow-up work.
