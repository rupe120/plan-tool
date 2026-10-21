> **Replaced**: this file has been superseded by `docs/implementation-plans/2-decompose-generate-detail-phases.md`.
> Preserved here for history; do not edit.

## Overview

`plan_tool/detail.py:generate_detail` becomes a short top-level sequence of same-file, named phase functions while preserving its public signature and all observable behavior. Pre-loop setup, the per-step convergence loop, and post-loop split resolution become reviewable phases. Phase B and Trigger 2 share only their existing `written_keys`/`min_split` result-rebuild shape; their policies, accumulators, ordering, and recursive re-entry remain distinct.

## Problem statement

`plan_tool/detail.py:generate_detail` contains orchestration phases that are not exposed as named functions, making its ordering-sensitive per-step convergence loop and structural-split paths difficult to review independently. The refactor names those phases without changing behavior, while keeping the dense per-step loop together and preventing the two distinct split mechanisms from being accidentally merged.

## Architecture

`generate_detail` remains the public entry point and becomes a short sequence of same-file phase functions. Named pre-loop phases handle jobs/guard validation, plan parsing, concept loading, target-step resolution, orphan-detail adoption, checkpoint pre-scan, and invoke-target setup. Shared state passes explicitly between phases rather than through new closures, except for state naturally owned for the lifetime of the extracted per-step loop.

The per-step inner convergence loop becomes one named function. Its dense ordering, local ownership, recursive re-entry behavior, and access to the pre-scan's `invoke_total` and `invoke_idx` correction remain intact. `_generate_jira_detail` and `_generate_detail_concurrent` remain existing extracted forks, with only the call-site changes required by the surrounding extraction.

Phase B and Trigger 2 remain separate structural-split mechanisms. `mixed_steps`, `structural_seen`, `structural_split_ids`, and `inloop_structural_recs` remain four separately named accumulators. Phase B continues to process ids high-to-low so an earlier split cannot renumber a target not yet processed, while Trigger 2 recursive re-entry continues to pass `resume=False` because split-half steps have no checkpoint to probe. The two paths share only a helper for rebuilding results from `written_keys` and `min_split`.

The final concept-persistence branch retains its legacy-versus-flat fork, including the legacy full-tree refusal of new flat deferrals. Every extracted phase preserves its existing inputs, outputs, side effects, ordering relative to neighboring phases, and error-raising conditions.

## Out of scope

- Changing `generate_detail`'s signature, behavior, error conditions, `resume`/`force` semantics, or checkpoint behavior; this work is limited to reorganization.
- Merging the Trigger 2 and Phase B structural-split mechanisms; their distinct policies and accumulators remain separate.
- Unifying the detail per-step loop with `create_plan`'s outer apply loop; that shared implementation requires separately scoped follow-up work.
- Decomposing `create_plan`; the companion `plan-seeds/decompose-create-plan-phases.md` seed owns that independent refactor.
- Refactoring `plan_tool/cli/run_cmd.py:cmd_run`; a `cmd_run` decomposition requires separately scoped follow-up work.

## Risks

- **High — per-step ordering or recursive re-entry changes:** extracting the ordering-sensitive loop can alter behavior; mitigate this by keeping it as one function with its dense ordering and local ownership intact.
- **High — public signature changes:** changing `generate_detail` breaks the dense direct-call contract in `tests/test_detail.py`; retain the signature exactly.
- **High — structural-split policy collapse:** merging Phase B and Trigger 2 can lose a distinct accumulator or caller-specific policy; preserve the four separately named accumulators and share only result-rebuild mechanics.
- **Medium — incomplete state handoff:** missing state can break resume accounting or final concept persistence; pin currently untested stated rules before moving code.

## Testing

`tests/test_detail.py` remains the primary regression suite. Add targeted characterization coverage only where a stated load-bearing ordering or state invariant lacks an existing pin before extraction begins, including resume accounting and legacy-versus-flat concept persistence where necessary. Keep existing assertions unchanged, then run the unchanged existing suite and the repository test suite required by the affected modules.

## Acceptance criteria

- `generate_detail` is a short top-level sequence of named same-file phase functions, and its per-step convergence loop is one named function.
- `generate_detail` retains its public signature and observable behavior.
- Phase B and Trigger 2 preserve their separate accumulators, order, and recursive `resume=False` behavior while sharing only safe `written_keys`/`min_split` result-rebuild mechanics.
- Resume accounting and the legacy-versus-flat concept-persistence fork remain unchanged and receive characterization coverage where an existing pin is absent.
- `tests/test_detail.py` passes without weakening existing assertions.

## Deferred

- The independent `create_plan` phase extraction remains in `plan-seeds/decompose-create-plan-phases.md` because it is a separate refactor.
- A shared implementation for the two convergence loops remains separately scoped follow-up work.
- A `cmd_run` decomposition remains separately scoped follow-up work.
