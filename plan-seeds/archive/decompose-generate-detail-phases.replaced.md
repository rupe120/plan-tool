> **Replaced**: this file has been superseded by `docs/implementation-plans/2-decompose-generate-detail-phases.md`.
> Preserved here for history; do not edit.

# Seed: decompose `generate_detail` into named phase functions

## Outcome

`plan_tool/detail.py:generate_detail` becomes a short top-level sequence of
same-file, named phase functions while preserving its public signature and all
observable behavior. Its per-step convergence loop becomes one reviewable
named function, and its two split-resolution paths share only their existing
result-rebuild shape without merging their distinct policies.

## In scope

- Extract named pre-loop setup phases for jobs/guard validation, plan parsing,
  concept loading, target-step resolution, orphan-detail adoption, checkpoint
  pre-scan, and invoke-target setup.
- Extract the per-step inner convergence loop as one named function. Keep its
  dense ordering and local ownership intact rather than sub-decomposing it.
- Extract the Phase B and trigger-2 post-loop split-resolution blocks. Share a
  helper for their `written_keys`/`min_split` result rebuild while preserving
  each caller's ordering and recursive re-entry rules.
- Leave `_generate_jira_detail` and `_generate_detail_concurrent` as existing
  extracted forks, changing their call sites only as the surrounding phase
  extraction requires.
- Add characterization coverage only where a load-bearing ordering/state rule
  below lacks a test before the extraction begins.

## Out of scope

- Changing `generate_detail`'s signature, behavior, error conditions,
  `resume`/`force` semantics, or checkpoint behavior.
- Merging the Trigger 2 and Phase B structural-split mechanisms.
- Unifying the detail per-step loop with `create_plan`'s outer apply loop.
- Decomposing `create_plan`; the companion
  `plan-seeds/decompose-create-plan-phases.md` seed owns that independent
  refactor.
- Refactoring `plan_tool/cli/run_cmd.py:cmd_run`.

## Allowed behavior changes

None. Every phase preserves its existing inputs, outputs, side effects,
ordering relative to its neighbors, and error-raising conditions.

## Allowed reorganization

Split only `generate_detail`'s body into named functions in
`plan_tool/detail.py`. Pass shared state explicitly between phases rather than
using new closures, except for state naturally owned for the lifetime of the
extracted per-step loop.

## Architecture

`generate_detail` already delegates backend round-trips to named helpers. This
refactor names the orchestration around them and keeps the two existing
structural-split policies distinct.

- `mixed_steps`, `structural_seen`, `structural_split_ids`, and
  `inloop_structural_recs` remain four separately named accumulators. They
  belong to two different split mechanisms and must not be collapsed.
- Phase B processes ids high-to-low so an earlier split cannot renumber a
  target not yet processed. Trigger 2's recursive re-entry continues to pass
  `resume=False` because split-half steps have no checkpoint to probe.
- The pre-scan's `invoke_total` and `invoke_idx` correction remains reachable
  from the per-step loop when a TTY user declines resume.
- The final concept-persistence branch retains its legacy-versus-flat fork,
  including the legacy full-tree refusal of new flat deferrals.

## Risks

- High: the per-step loop is ordering-sensitive and can be re-entered
  recursively. Keep it as one extracted function.
- High: changing the public signature breaks the dense direct-call contract in
  `tests/test_detail.py`; retain it exactly.
- High: merging the two split mechanisms loses a distinct accumulator or
  caller-specific policy.
- Medium: an incomplete state handoff can break resume accounting or final
  concept persistence; pin currently untested rules before moving code.

## Testing

`tests/test_detail.py` remains the primary regression suite. Add targeted
characterization tests only for stated invariants that lack a pin, then run the
unchanged existing suite and the repository test suite required by the
affected modules.

## Acceptance criteria

- `generate_detail` is a short top-level sequence of named same-file phase
  functions, and its per-step convergence loop is one named function.
- Its public signature and observable behavior are unchanged.
- Phase B and Trigger 2 preserve their separate accumulators, order, and
  recursive `resume=False` behavior while sharing only safe result rebuild
  mechanics.
- Resume accounting and legacy-versus-flat concept persistence are preserved
  and characterized where necessary.
- `tests/test_detail.py` passes without weakening existing assertions.

## Deferred

- The independent `create_plan` phase extraction belongs to
  `plan-seeds/decompose-create-plan-phases.md`.
- A shared implementation for the two convergence loops and a `cmd_run`
  decomposition require separately scoped follow-up work.
