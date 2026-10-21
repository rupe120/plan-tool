> **Auto-archived**: this plan was swept on 2026-08-18 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

---
title: Decompose Create Plan Phases
intent: '`plan_tool/create.py:create_plan` becomes the same-file phase sequence prepare
  → publish → converge → finalize while preserving its exact public signature and
  all observable behavior. Its dense convergence `while True` loop becomes one reviewable
  named function, not a new abstraction or a behavior change.'
status: completed
priority: medium
enforce_step_tests: true
steps:
- id: 1
  title: Characterize create_plan's exact signature and loop contracts, then move
    its convergence loop into one explicit-state function
  intent: Tests first pin every public parameter's name, kind, order, default, and
    annotation plus `create_plan`'s return annotation alongside the direct-call and
    write-path contracts. Retarget only the parse-revert source inspection to the
    new convergence owner; leave the initial-only rationale-forwarding guard on `create_plan`
    until step 2 moves its preparation code. The dense drift, triage, apply, re-derivation,
    and stopping sequence becomes reviewable with an explicit terminal outcome for
    normal stops and stage failure.
  files:
  - plan_tool/create.py
  - tests/test_create.py
  complexity: high
  change_type: refactor
  detail: docs/implementation-plans/plan-details/decompose-create-plan-phases/01-characterize-create-plan-exact.md
  status: done
- id: 2
  title: Move create_plan setup, authoring, and its initial-only rationale guard into
    named functions, keeping checkpoint overwrites and backend-call order unchanged
  intent: Named handoffs make path, seed, step, concept, intent, reference, and body
    preparation understandable before publication. This step retargets the rationale
    source guard from `create_plan` to `_prepare_create_plan` without changing its
    one-in-prepare, none-in-convergence predicate. A multi-plan distillation result
    exits from preparation with its split proposal and bypasses the normal later phases.
  files:
  - plan_tool/create.py
  - tests/test_create.py
  complexity: high
  change_type: refactor
  depends_on:
  - 1
  depends_on_notes:
    1: Supplies the protected convergence-loop boundary that surrounding orchestration
      must preserve.
  detail: docs/implementation-plans/plan-details/decompose-create-plan-phases/02-move-create-plan-setup-authoring-its.md
  status: done
- id: 3
  title: Move create_plan publication into named functions, keeping collision archival
    and manifest removal, write_new_plan and concept rollback, detail renames, and
    manifest append unchanged
  intent: Publication becomes an explicit handoff that leaves the on-disk plan_path
    as the source for body and concept consumers.
  files:
  - plan_tool/create.py
  - tests/test_create.py
  complexity: high
  change_type: refactor
  depends_on:
  - 2
  depends_on_notes:
    2: Supplies the prepared plan, concepts, references, and body state consumed by
      publication.
  detail: docs/implementation-plans/plan-details/decompose-create-plan-phases/03-move-create-plan-publication-named.md
  status: done
- id: 4
  title: Move create_plan finalization into named functions and pin its prepare →
    publish → converge → finalize sequence, keeping clean-run checkpoint deletion,
    failed-run retention, post-loop plan and concept sync, and sidecar clearing unchanged
  intent: On the normal plan-producing path, create_plan delegates in its fixed four-phase
    order while final consumers apply the convergence terminal outcome and keep their
    existing original-plan or on-disk-plan source.
  files:
  - plan_tool/create.py
  - tests/test_create.py
  complexity: medium
  change_type: refactor
  depends_on:
  - 3
  depends_on_notes:
    3: Provides the published plan_path and concept state that only its existing on-disk
      consumers re-read during finalization.
  detail: docs/implementation-plans/plan-details/decompose-create-plan-phases/04-move-create-plan-finalization-named.md
  status: done
---
# Decompose Create Plan Phases

## Overview

Refactor the normal plan-producing path in `plan_tool/create.py:create_plan` into the short, named, same-file phase sequence **prepare → publish → converge → finalize** so its orchestration and dense convergence loop are easier to review. Preserve its exact public signature, including the return annotation, observable behavior, error conditions, phase ordering, inputs, outputs, and side effects. A multi-plan distillation proposal remains a preparation-only return and bypasses the other three phases. Keep the outer convergence loop intact as one named function with explicit input and return state rather than introducing a new abstraction.

## Problem statement

`plan_tool/create.py:create_plan` contains dense orchestration and a `while True` convergence loop whose phase boundaries are difficult to review. Naming its normal **prepare → publish → converge → finalize** phases makes the flow clearer while retaining the direct-call contract covered by `tests/test_create.py` and avoiding any behavior change. A multi-plan distillation proposal remains an early preparation exit, so it does not pretend to publish or converge a plan that does not exist.

## Architecture

On the normal plan-producing path, keep `create_plan` as four same-file phase calls in this exact order: `_prepare_create_plan`, `_publish_create_plan`, `_converge_create_plan`, and `_finalize_create_plan`. Preparation owns slug/output-dir resolution, metadata prompt, seed distillation, step resolution, change-type review, plan assembly, concept bootstrap/merge, intent offer, reference proposal, body synthesis, and the TODO gate. When distillation returns a multi-plan proposal, preparation returns `CreateResult(plan_path=None, split_proposal=...)` directly and `create_plan` bypasses publication, convergence, finalization, manifest mutation, and plan writing. Publication owns collision archival, write/reparse, plan-details rename, fingerprint/concept sync, and manifest append. Convergence owns the post-write loop and returns its terminal outcome to finalization. Finalization owns outcome-dependent checkpoint handling, the path-issue advisory, post-loop concept sync, and the pending-decision advisory. Pass shared state explicitly between phases rather than introducing closures, except for convergence-loop-local state wholly owned by the extracted loop.

Extract the outer convergence loop as one named function with explicit input and terminal outcome, while keeping its drift check, triage, apply, re-derivation, and checkpoint sequencing in their current order. Its normal outcomes (including converged, marginal, budget, drift, and parse-halt stops) carry no `stage_failure`; finalization discards the create checkpoints and the final result carries `iteration_stage_failure=None`. An unparseable or invalid step re-proposal is a stage failure: after patching a non-empty `refs_proposal` and preserving an empty or missing proposal, convergence returns its failure reason; finalization retains checkpoints and returns it through `CreateResult.iteration_stage_failure`. An uncaught exception propagates without manufacturing a normal result or running the success cleanup. Step 1 moves the parse-revert source inspection to `_converge_create_plan` while retaining the rationale-forwarding guard on `create_plan`. Step 2 moves that guard with the preparation code: `_prepare_create_plan` contains the one initial `rationales_out=step_rationales` call and `_converge_create_plan` contains none. After publication, concept synchronization and pending-decision checks re-parse `plan_path` because `apply_finding` can mutate the file directly, while `advise_path_issues` keeps its existing original in-memory `plan` input.

The extracted loop calls `write_plan`, never `write_new_plan`, because `write_new_plan` would rebuild the body and discard sections written by an earlier `apply_finding`; preserve that distinction in a terse docstring on the loop-owning function. Resolve `references` once before the loop and retain the per-iteration `refs_proposal` as a separate value.

`create_plan` continues to delegate individual backend calls to existing named helpers. This refactor names only the orchestration connecting those calls and does not change the dependency surface or any normal, split-proposal, stage-failure, or uncaught-error exit contract.

## Input

The refactor consumes the existing `plan_tool/create.py:create_plan` public signature and observable direct-call contract. Step 1 records an `inspect.signature(create_plan)` characterization that pins every parameter's name, kind, order, default, and annotation plus the function's return annotation before extraction. It preserves the existing orchestration state contracts around `references`, non-empty `refs_proposal`, `apply_finding`, `write_plan`, and `write_new_plan`. It also preserves the post-loop source split: `advise_path_issues` receives the original in-memory plan, while concept synchronization and pending-decision checks re-parse `plan_path`.

## References

- [Python 3.13 Language Reference — Function definitions](https://docs.python.org/3.13/reference/compound_stmts.html#function-definitions) — Defines function signatures, keyword-only parameters, annotations, decorators, and default-value semantics relevant to preserving create_plan's exact contract.
- [Python 3.13 inspect — Inspect live objects](https://docs.python.org/3.13/library/inspect.html#inspect.signature) — Documents inspect.signature and Signature objects for characterizing the public callable signature before and after extraction.
- [pytest — How to monkeypatch/mock modules and environments](https://docs.pytest.org/en/stable/how-to/monkeypatch.html) — Explains how to replace same-module helpers and dependencies safely while testing phase handoffs, side effects, and failure paths.
- [Python 3.13 unittest.mock — Where to patch](https://docs.python.org/3.13/library/unittest.mock.html#where-to-patch) — Explains patching names where the code under test resolves them, which is essential when extracting orchestration into same-file phase functions.
- [Python 3.13 unittest.mock — Tracking order of calls](https://docs.python.org/3.13/library/unittest.mock-examples.html#tracking-order-of-calls-and-less-verbose-call-assertions) — Shows how to record and assert cross-mock call order for characterization tests that pin phase and convergence-loop sequencing.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

- Changing `create_plan`'s signature, behavior, error conditions, checkpoint semantics, normal-path prepare → publish → converge → finalize ordering, split-proposal bypass, or convergence terminal outcomes; this work is organization-only.
- Unifying the create convergence loop with `generate_detail`'s per-step loop; a shared implementation requires separately scoped follow-up work.
- Decomposing `generate_detail`; `plan-seeds/decompose-generate-detail-phases.md` owns that independent refactor.
- Refactoring `plan_tool/cli/run_cmd.py:cmd_run`; that is a separate concern.

## Risks

- **High — convergence-loop reordering:** plan mutation, drift, or checkpoint behavior can change. Mitigation: keep the loop intact as one extracted function and preserve its current sequence.
- **High — public-signature drift:** changing the dense direct-call contract can break `tests/test_create.py`. Mitigation: Step 1 adds the exact `inspect.signature` characterization, including the return annotation, before extraction and keeps it green throughout.
- **High — exit-contract drift:** a split proposal, a stage failure, or an uncaught exception can be mistaken for a normal finalized plan. Mitigation: preserve their separate result, References, and checkpoint rules and characterize both the normal phase sequence and each bypass/failure exit.
- **Medium — incomplete phase state:** missing state can change the post-loop source split or reference behavior. Mitigation: pass shared state explicitly and characterize any stated invariant that lacks an existing test before extraction.
- **Medium — location-sensitive test drift:** two current source inspections name `create_plan` even though their contracts belong to extracted phases. Mitigation: Step 1 moves the parse-revert inspection with convergence; step 2 moves the initial-only rationale-forwarding inspection with preparation, retaining both predicates unchanged.

## Testing

Use `tests/test_create.py` as the primary regression suite. Before moving the loop in step 1, add the exact public-signature characterization, including the return annotation, and targeted coverage for load-bearing ordering or state invariants that lack a pin, including the non-empty References replacement and post-loop source split. Characterize the convergence terminal outcome end to end: parameterize normal-stop coverage over converged, marginal, budget, drift, parse-halt, deferred-only, and retry-blocked exits, asserting each leaves `iteration_stage_failure=None` and discards create checkpoint shards. Keep a separate stage-failure case that patches only non-empty References, retains checkpoints, and returns its failure reason; uncaught errors must propagate without success cleanup. Step 1 moves the parse-revert inspection to `_converge_create_plan` while retaining the rationale inspection on `create_plan`; step 2 then proves `_prepare_create_plan` has one `rationales_out=step_rationales` call and `_converge_create_plan` has none. In step 4, add structural characterizations that the normal path delegates to `_prepare_create_plan`, `_publish_create_plan`, `_converge_create_plan`, and `_finalize_create_plan` in that order, while a multi-plan distillation proposal returns from preparation and calls none of the later phases. Keep all behavior assertions unchanged, then run the suite and the repository test suite required by the affected modules.

**Per-step test strategy** (derived from each step's `change_type`):

- step 1 (refactor) — tests covering the behavior this step changes; green before completion.
- step 2 (refactor) — tests covering the behavior this step changes; green before completion.
- step 3 (refactor) — tests covering the behavior this step changes; green before completion.
- step 4 (refactor) — tests covering the behavior this step changes; green before completion.

## Acceptance criteria

- On its normal plan-producing path, `plan_tool/create.py:create_plan` delegates in the fixed prepare → publish → converge → finalize order to named, same-file phase functions, and its outer convergence loop is one named function; a multi-plan distillation proposal exits from preparation without calling the later phases.
- `create_plan` retains its exact public signature and observable behavior; a characterization test compares every parameter's name, kind, order, default, and annotation plus the return annotation through `inspect.signature`.
- `write_plan` rather than `write_new_plan` is preserved, as is the post-loop source split: concept synchronization and pending-decision checks re-parse `plan_path`, while `advise_path_issues` receives the original plan.
- `references` and `refs_proposal` are preserved: only a non-empty proposal replaces References, regardless of step re-proposal failure; `[]` and `None` preserve the existing section.
- Every declared normal terminal path—converged, marginal, budget, drift, parse halt, deferred-only, and retry-blocked—discards checkpoints and returns `iteration_stage_failure=None`; an invalid or unparseable step re-proposal returns its failure, retains checkpoints, and has already patched a non-empty References proposal; uncaught errors propagate without the success cleanup.
- `tests/test_create.py` passes without weakening behavior assertions: step 1 moves its parse-revert source guard with convergence, and step 2 moves its initial-only rationale-forwarding guard with preparation.

## Deferred

- Decompose `generate_detail` under `plan-seeds/decompose-generate-detail-phases.md`; it is an independent refactor.
- Consider a shared implementation for the two convergence loops in separately scoped follow-up work.
- Decompose `plan_tool/cli/run_cmd.py:cmd_run` in separately scoped follow-up work.
