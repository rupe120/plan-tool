> **Replaced**: this file has been superseded by `docs/implementation-plans/2-merge-bridge.md`.
> Preserved here for history; do not edit.

## Overview

Finish the deferred merge arm of the structural-remedy auto-bridge work by adding a walk-surfaced pairwise `granularity-merge` producer and wiring it to a gated `merge_bridge`. The bridge must be reachable from `reconcile-plan-walk` / `review-walk`, but remain recommend-only unless the operator explicitly opts in and confirms or uses `-y`. The implementation must preserve the existing scope-out and re-ground bridges, reuse `merge_steps` and existing merge safety checks, and prevent stale saved directives from mutating the wrong steps after merge renumbering.

## Problem statement

`granularity.py` can already identify adjacent fragmented dependent steps and emit a `granularity-merge` recommendation through `_merge_rec`, but that signal is not available to the interactive apply walk driven by `reconcile-plan-walk` / `review-walk`. Existing surfaces such as create-side change-type review, detail split-criteria output, and completeness advisory smells can report advice, but they do not feed `saved.recommendations` in the reconcile/review walk.

As a result, a gated `merge_bridge` would be dead production code without a real walk producer. The user-visible gap is that the tool can recognize that two steps should probably merge, and `plan-tool merge` can perform the mutation, but the operator cannot review/apply that remedy from the same structural walk used for the completed scope-out and re-ground auto-bridges.

## Architecture

Add a producer that emits `merge`-kind `granularity-merge` findings into the saved recommendation walk. The recommendation must carry structured member ids so dispatch can recover the intended pair without reparsing prose, and it must preserve whether the signal is non-contiguous so gapped pairs stay recommend-only instead of being widened to `lo..hi`.

Implement the deferred gated merge primitive from `docs/implementation-plans/plan-details/auto-bridge-structural-remedies/02-gated-merge-bridge-that-wraps-merge.md` near the existing merge primitives in `plan_tool/detail.py`. The bridge should add a frozen result type, reuse `_merge_is_safe`, `_confirm_merge`, and `merge_steps`, forward the detail-authoring invoker seam and `merge_steps` passthroughs, and convert malformed merge sets into walk-safe recommended/invalid results instead of leaking `DetailError`.

Extend the recommendation action shape so merge and re-ground dispatch are distinct even though both have historical ties to `granularity-merge`. Dispatch should use structured action/remedy data or a stable suggested-action format, not the source literal alone.

Wire the reconcile/review structural walk gate, including `--apply-structural`, so merge-kind findings dispatch to `merge_bridge`. Every unattended, non-TTY, no-opt-in, declined, unsafe, invalid, or gapped path must recommend only. After a successful applied merge, the walk must either halt on the first applied merge or use a plan-stability key / fingerprint guard so later saved directives cannot act on shifted step ids.

## Out of scope

- Do not rebuild the completed scope-out bridge; `convergence --apply-scope-out` already exists and is outside this follow-up.
- Do not rebuild the completed re-ground mark-done bridge; `reground.py`, `mark_steps_done`, and the re-ground walk dispatch already exist except for any shared structural-walk gate extension needed to recognize merge.
- Do not add auto re-baseline via `create --from-existing`; re-ground re-baseline remains human-authored unless the create pass scopes a separate justified step.
- Do not make merge apply by default; merge remains explicit opt-in and confirm-gated.
- Do not widen gapped merge pairs to contiguous ranges automatically; gapped pairs require manual operator judgment.
- Do not make `granularity-merge` apply-eligible globally without the structural gate; this is an explicit walk actuation path, not a broad recommendation semantics change.
- Do not add a new merge algorithm or a new structural primitive; reuse the existing merge implementation.

## Risks

- Dead bridge risk: high severity. Building the bridge without the producer repeats the reason `docs/implementation-plans/2-auto-bridge-structural-remedies.md` deferred this work; mitigation is to make the walk-surfaced producer the first-class requirement.
- Wrong-step mutation after renumber: high severity. `merge_steps` changes step ids, so continuing to apply saved directives can mutate shifted steps; mitigation is halt-on-first-applied-merge or a plan-stability key / fingerprint guard.
- Merge vs re-ground confusion: high severity. Both remedies have historical ties to `granularity-merge`; mitigation is dispatch by remedy/action shape rather than the literal source string alone.
- Over-application: medium severity. Pairwise merge advice can be lower-confidence than a structural correctness finding; mitigation is explicit opt-in plus confirmation.
- Claude spend in apply path: medium severity. Merge re-authors detail; mitigation is to forward the invoker seam and keep every non-applied path no-Claude.

## Testing

Add unit coverage for the producer, recommendation shape, bridge gate matrix, dispatch parsing, gapped pair handling, and stale-directive/renumber protection.

Test files named by the seed:
- `tests/test_granularity.py`: cover the walk-surfaced pairwise merge producer and stable merge suggested-action / structured member id data.
- `tests/test_review.py`: cover saved recommendation persistence and review-side parsing for merge-kind findings.
- `tests/test_detail.py`: cover the gated `merge_bridge` result type and gate matrix for recommend-only, applied, unsafe, invalid, malformed, mixed-scope, non-canonical, unknown-id, fewer-than-two-id, and non-contiguous cases.
- `tests/cli/test_review_actions.py`: cover reconcile/review walk dispatch to merge, including opt-in, confirmation, no-opt-in, non-TTY, declined, unsafe, invalid, and stale-directive behavior.

Existing suites that must still pass: `tests/test_granularity.py`, `tests/test_review.py`, `tests/test_detail.py`, and `tests/cli/test_review_actions.py`. Cross-module wiring through `plan_tool/review_walk.py`, `plan_tool/cli/review_actions.py`, `plan_tool/cli/parser.py`, and `plan_tool/cli/reconcile.py` should be verified at the CLI/action-dispatch tier because a unit test on only the producer or bridge would miss routing mistakes.

## Acceptance criteria

- A pairwise merge finding can be produced into the saved recommendation walk from a real plan shape, not only from a synthetic unit-test recommendation.
- `reconcile-plan-walk` / `review-walk` can dispatch a merge-kind finding to the merge bridge.
- With no opt-in, non-TTY, declined confirm, unsafe state, invalid ids, or a gapped pair, the walk recommends only and mutates nothing.
- With opt-in plus confirm or `-y` plus safe contiguous member ids, the walk applies the merge through `merge_steps`.
- Applied merge invalidates or halts subsequent directive-carrying findings so renumbering cannot make later saved recommendations mutate the wrong steps.
- Re-ground findings still route to `reground_bridge`, never to merge.
- Scope-out and re-ground behavior remain unchanged.
- Tests cover producer, bridge gate matrix, dispatch, gapped pair handling, and stale-directive/renumber protection.
- Operator docs describe that merge is opt-in and confirm-gated, that gapped pairs are recommend-only and require manual judgment, and the stale-directive behavior after an applied merge.
