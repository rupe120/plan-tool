> **Auto-archived**: this plan was swept on 2026-08-18 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

---
title: Decompose Generate Detail Phases
intent: '`plan_tool/detail.py:generate_detail` becomes a short top-level sequence
  of same-file, named phase functions while preserving its public signature and all
  observable behavior. Its outer map is parse and dispatch, run-grade setup and lifecycle,
  ordered post-loop handlers, then persistence; its per-step convergence loop stays
  one reviewable inner function.'
status: completed
priority: medium
enforce_step_tests: true
steps:
- id: 1
  title: Characterize generate_detail's exact signature and extract parse to Jira
    or run-grade dispatch
  intent: The public entry retains its exact callable contract, validates modes, parses
    once, and routes Jira authoring directly to its existing lane before any run-grade
    concept, pointer, orphan, checkpoint, or artifact work begins.
  files:
  - plan_tool/detail.py
  - tests/test_detail.py
  complexity: high
  change_type: refactor
  detail: docs/implementation-plans/plan-details/decompose-generate-detail-phases/01-characterize-generate-detail-exact.md
  status: done
- id: 2
  title: Extract run-grade setup after the Jira fork, preserving its preparation order
  intent: Only the run-grade branch prepares concepts, selected steps, orphan adoption,
    checkpoints, cached bodies, and invocation counts before it hands ready state
    to authoring.
  files:
  - plan_tool/detail.py
  - tests/test_detail.py
  complexity: high
  change_type: refactor
  depends_on:
  - 1
  depends_on_notes:
    1: Establishes the parse-and-dispatch boundary that selects whether run-grade
      setup runs at all.
  detail: docs/implementation-plans/plan-details/decompose-generate-detail-phases/02-extract-run-grade-setup-after-jira-fork.md
  status: done
- id: 3
  title: Extract the run-grade authoring lifecycle and its per-step convergence helper
  intent: The lifecycle preserves serial and concurrent authoring selection, resume,
    invocation accounting, writes, and logging; its dense per-step audit/apply/re-audit
    work has one owner and returns results plus structural state to post-loop handling.
  files:
  - plan_tool/detail.py
  - tests/test_detail.py
  complexity: high
  change_type: refactor
  depends_on:
  - 2
  depends_on_notes:
    2: Supplies the parsed plan and run-grade state that the lifecycle consumes.
  detail: docs/implementation-plans/plan-details/decompose-generate-detail-phases/03-extract-run-grade-authoring-lifecycle.md
  status: done
- id: 4
  title: Extract Phase B as the first post-loop split handler
  intent: After authoring, Phase B owns its mixed-step policy and completes before
    Trigger 2 begins; it consumes in-loop structural state only through the existing
    exclusion handoff, without merging the two handlers' policies.
  files:
  - plan_tool/detail.py
  - tests/test_detail.py
  complexity: high
  change_type: refactor
  depends_on:
  - 3
  depends_on_notes:
    3: Returns authored results, mixed-step state, and the in-loop structural handoff.
  detail: docs/implementation-plans/plan-details/decompose-generate-detail-phases/04-extract-phase-first-post-loop-split.md
  status: done
- id: 5
  title: Extract Trigger 2 as the second post-loop split handler
  intent: Trigger 2 runs only after Phase B and owns the lifecycle-returned in-loop
    structural state and its distinct re-entry policy; it does not collapse into Phase
    B merely because both handlers may revise post-loop results.
  files:
  - plan_tool/detail.py
  - tests/test_detail.py
  complexity: medium
  change_type: refactor
  depends_on:
  - 4
  depends_on_notes:
    4: Establishes the required first post-loop handler and leaves Trigger 2's policy
      distinct.
  detail: docs/implementation-plans/plan-details/decompose-generate-detail-phases/05-extract-trigger-second-post-loop-split.md
  status: done
- id: 6
  title: Extract final concept persistence and shorten generate_detail to its phase
    map
  intent: The entry reads as one fixed outer sequence while the final persistence
    tail retains its legacy-versus-flat concept-record rules after that invocation's
    authoring and post-loop work finishes, including the existing per-invocation persistence
    of recursive split recovery.
  files:
  - plan_tool/detail.py
  - tests/test_detail.py
  complexity: medium
  change_type: refactor
  depends_on:
  - 5
  depends_on_notes:
    5: Completes both split-resolution paths and supplies their final result set to
      concept persistence.
  detail: docs/implementation-plans/plan-details/decompose-generate-detail-phases/06-extract-final-concept-persistence.md
  status: done
---
# Decompose Generate Detail Phases

## Overview

`plan_tool/detail.py:generate_detail` becomes a short top-level sequence of same-file, named phase functions while preserving its public signature and all observable behavior. Its outer map is parse and dispatch, run-grade setup and lifecycle, Phase B then Trigger 2, then concept persistence. The dense per-step convergence loop remains one reviewable inner function, while its detailed recursion and result-rebuild mechanics remain owned by the later detail bundle.

## Problem statement

`plan_tool/detail.py:generate_detail` contains several real orchestration boundaries that are not exposed as named functions: its parsed-plan Jira/run-grade fork, the run-grade lifecycle, two ordered post-loop handlers, and persistence. The refactor names those boundaries without changing behavior, keeps the dense convergence mechanics together, and prevents Phase B and Trigger 2 from being merged or reordered.

## Architecture

`generate_detail` remains the public entry point and becomes a short sequence of same-file phase functions. It validates mode combinations and parses the plan once, then immediately routes a Jira-grade invocation to `_generate_jira_detail`. That branch precedes all run-grade concept-record work, detail-pointer writes, orphan adoption, checkpoint scanning, and run-grade artifact work. Only the run-grade branch enters setup.

Run-grade setup prepares the concept, target, orphan, checkpoint, cached-body, and invocation state needed by authoring. The lifecycle then selects the existing concurrent dispatch or serial authoring path. Its serial path owns one dense quality-convergence helper, which keeps its audit/apply/re-audit ordering together and returns results plus the structural handoff needed after the loop. `_generate_jira_detail` and `_generate_detail_concurrent` remain existing extracted forks; shared state crosses new boundaries explicitly rather than through new closures.

The post-loop handlers are separate and ordered: Phase B always completes before Trigger 2 begins. Phase B consumes the mixed-step path and reads the in-loop structural handoff only to avoid acting on a target it no longer owns. Trigger 2 consumes the structural handoff returned by the lifecycle. Their recursive selection, result reconstruction, and callback mechanics are detail-level contracts, but no extraction may merge, reorder, or give one handler the other's policy.

Each `generate_detail` invocation reaches final concept persistence only after its own authoring and both post-loop handlers. The outer invocation's final persistence therefore remains after its outer Phase B and Trigger 2 handlers, while their explicit-id recursive calls retain their own existing persistence boundary before the enclosing handler resumes. The legacy-versus-flat record fork, nested save-failure result handling, and every phase's existing inputs, outputs, side effects, ordering, and error-raising conditions remain unchanged.

## References

- [Python 3.13 Execution Model](https://docs.python.org/3.13/reference/executionmodel.html) — Defines name binding, local and free variables, and execution frames relevant when extracting orchestration code into functions.
- [Python inspect.signature API](https://docs.python.org/3.13/library/inspect.html#inspect.signature) — Documents callable signature introspection for pinning generate_detail's parameters, defaults, and keyword-only contract.
- [Python dataclasses](https://docs.python.org/3.13/library/dataclasses.html) — Covers explicit state-carrier classes, frozen instances, fields, and replacement semantics useful for phase handoffs.
- [Python concurrent.futures](https://docs.python.org/3.13/library/concurrent.futures.html) — Specifies ThreadPoolExecutor, Future, and as_completed behavior needed to preserve the existing concurrent detail path.
- [pytest Monkeypatching Guide](https://docs.pytest.org/en/stable/how-to/monkeypatch.html) — Explains safe function and module-attribute patching for regression tests around newly extracted same-file phases.
- [pytest Assertion and Exception Testing](https://docs.pytest.org/en/stable/how-to/assert.html) — Documents assertions and pytest.raises for characterizing unchanged results, ordering, and error conditions.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

- Changing `generate_detail`'s signature, behavior, error conditions, `resume`/`force` semantics, or checkpoint behavior; this work is limited to reorganization.
- Merging the Trigger 2 and Phase B structural-split mechanisms; their distinct policies and accumulators remain separate.
- Unifying the detail per-step loop with `create_plan`'s outer apply loop; that shared implementation requires separately scoped follow-up work.
- Decomposing `create_plan`; the companion `plan-seeds/decompose-create-plan-phases.md` seed owns that independent refactor.
- Refactoring `plan_tool/cli/run_cmd.py:cmd_run`; a `cmd_run` decomposition requires separately scoped follow-up work.

## Risks

- **High — dispatch or ordering drift:** moving the Jira fork after run-grade setup, or swapping Phase B and Trigger 2, changes which work runs and in which order. Preserve both boundaries explicitly and characterize them before extraction.
- **High — public-contract drift:** changing `generate_detail`'s signature or its terminal behavior has a broad direct-call blast radius. Characterize the public signature and retain existing behavior tests.
- **High — split-policy collapse:** merging Phase B and Trigger 2 can give one handler authority over the other's state. Preserve their distinct handoffs and policies; detail files choose the mechanics that prove that preservation.
- **Medium — incomplete run-grade handoff:** setup, lifecycle, and persistence can lose state at a newly named boundary. Pass state explicitly and retain current error and result behavior.

## Testing

`tests/test_detail.py` remains the primary regression suite. Characterize the exact public signature and add coverage only where a load-bearing outer contract lacks an existing pin: Jira dispatch bypasses run-grade setup, Phase B completes before Trigger 2 when both handlers act, and recursive split recovery retains its per-invocation persistence timing. Per-step detail files select the fixtures and assertions for recursive selection, result reconstruction, callback scope, and convergence-loop internals. Keep existing assertions unchanged, then run the unchanged existing suite and the repository suite required by the affected modules.

**Per-step test strategy** (derived from each step's `change_type`):

- step 1 (refactor) — tests covering the behavior this step changes; green before completion.
- step 2 (refactor) — tests covering the behavior this step changes; green before completion.
- step 3 (refactor) — tests covering the behavior this step changes; green before completion.
- step 4 (refactor) — tests covering the behavior this step changes; green before completion.
- step 5 (refactor) — tests covering the behavior this step changes; green before completion.
- step 6 (refactor) — tests covering the behavior this step changes; green before completion.

## Acceptance criteria

- `generate_detail` is a short top-level sequence of named same-file phase functions: parse and dispatch, run-grade setup and lifecycle, Phase B, Trigger 2, then persistence; its per-step convergence loop is one named inner function.
- `generate_detail` retains its exact public signature and observable behavior, with an `inspect.signature` characterization of every parameter and the return annotation.
- A Jira-grade invocation routes from parsed plan to its existing lane before run-grade concept, pointer, orphan, checkpoint, or artifact work; characterization coverage pins that bypass.
- Run-grade setup and lifecycle preserve their current results, errors, serial/concurrent selection, and explicit handoff to the post-loop phases.
- Phase B completes before Trigger 2; their policies remain separate and characterization coverage exercises that ordering when both handlers act.
- Each invocation's final concept persistence retains its legacy-versus-flat fork after that invocation's authoring and post-loop work; recursive split recovery retains its existing nested save timing and failure results.
- `tests/test_detail.py` passes without weakening existing assertions.

## Deferred

- The independent `create_plan` phase extraction remains in `plan-seeds/decompose-create-plan-phases.md` because it is a separate refactor.
- A shared implementation for the two convergence loops remains separately scoped follow-up work.
- A `cmd_run` decomposition remains separately scoped follow-up work.
