> **Auto-archived**: this plan was swept on 2026-07-07 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

---
title: Merge Bridge
status: completed
priority: medium
enforce_step_tests: true
steps:
- id: 1
  title: Add merge directives to existing granularity merge findings
  files:
  - plan_tool/granularity.py
  - tests/test_granularity.py
  - tests/test_review.py
  complexity: medium
  change_type: feature
  detail: docs/implementation-plans/plan-details/merge-bridge/01-merge-directives-existing-granularity.md
  status: done
- id: 2
  title: Surface pairwise merge findings in saved reconcile recommendations
  files:
  - plan_tool/review.py
  - tests/test_review.py
  complexity: medium
  change_type: feature
  depends_on:
  - 1
  detail: docs/implementation-plans/plan-details/merge-bridge/02-surface-pairwise-merge-findings-saved.md
  status: done
- id: 3
  title: Add merge_bridge around merge_steps
  files:
  - plan_tool/detail.py
  - tests/test_detail.py
  complexity: high
  change_type: feature
  detail: docs/implementation-plans/plan-details/merge-bridge/03-merge-bridge-around-merge-steps.md
  status: done
- id: 4
  title: Route merge directives to merge_bridge in the review walk
  files:
  - plan_tool/review_walk.py
  - plan_tool/cli/review_actions.py
  - tests/cli/test_review_actions.py
  - tests/test_review_walk.py
  complexity: high
  change_type: feature
  depends_on:
  - 1
  - 3
  detail: docs/implementation-plans/plan-details/merge-bridge/04-route-merge-directives-merge-bridge.md
  status: done
- id: 5
  title: Block stale merge directives after a plan fingerprint change
  files:
  - plan_tool/cli/review_actions.py
  - tests/cli/test_review_actions.py
  complexity: medium
  change_type: feature
  depends_on:
  - 4
  detail: docs/implementation-plans/plan-details/merge-bridge/05-block-stale-merge-directives-after-plan.md
  status: done
- id: 6
  title: Update merge bridge docs and --apply-structural help
  files:
  - plan_tool/cli/review_cmd.py
  - BACKLOG.md
  - CLAUDE.md
  - RUNBOOK.md
  - docs/cli/reconcile-plan.md
  - docs/cli/reconcile-plan-walk.md
  complexity: low
  change_type: feature
  enforce_test_authoring: false
  depends_on:
  - 4
  - 5
  detail: docs/implementation-plans/plan-details/merge-bridge/06-update-merge-bridge-docs-apply.md
  status: done
---
# Merge Bridge

## Overview

Finish the deferred merge arm of the structural-remedy auto-bridge work by adding a walk-surfaced pairwise `granularity-merge` producer and wiring it to a gated `merge_bridge`. The bridge must be reachable from `reconcile-plan-walk` / `review-walk`, but remain recommend-only unless the operator explicitly opts in and confirms in a TTY prompt. The implementation must preserve the existing scope-out and re-ground bridges, reuse `merge_steps` and existing merge safety checks, and prevent stale saved directives from mutating the wrong steps after merge renumbering.

## Problem statement

`granularity.py` can already identify adjacent fragmented dependent steps and emit a `granularity-merge` recommendation through `_merge_rec`, but that signal is not available to the interactive apply walk driven by `reconcile-plan-walk` / `review-walk`. Existing surfaces such as create-side change-type review, detail split-criteria output, and completeness advisory smells can report advice, but they do not feed `saved.recommendations` in the reconcile/review walk.

As a result, a gated `merge_bridge` would be dead production code without a real walk producer. The user-visible gap is that the tool can recognize that two steps should probably merge, and `plan-tool merge` can perform the mutation, but the operator cannot review/apply that remedy from the same structural walk used for the completed scope-out and re-ground auto-bridges.

## Architecture

Add a producer that emits `merge`-kind `granularity-merge` findings into the saved recommendation walk. The recommendation must carry structured member ids so dispatch can recover the intended pair without reparsing prose, and it must preserve whether the signal is non-contiguous so gapped pairs stay recommend-only instead of being widened to `lo..hi`.

Implement the deferred gated merge primitive from `docs/implementation-plans/plan-details/auto-bridge-structural-remedies/02-gated-merge-bridge-that-wraps-merge.md` near the existing merge primitives in `plan_tool/detail.py`. The bridge should add a frozen result type, reuse `_merge_is_safe`, `_confirm_merge`, and `merge_steps`, forward the detail-authoring invoker seam and `merge_steps` passthroughs, and convert malformed merge sets into walk-safe recommended/invalid results instead of leaking `DetailError`. A frozen dataclass is appropriate for the result shape because Python dataclasses can generate initialization and comparison methods from annotated fields, and `frozen=True` prevents assignment to fields after creation.

Extend the recommendation action shape so merge and re-ground dispatch are distinct even though both have historical ties to `granularity-merge`. Dispatch should use structured action/remedy data or a stable suggested-action format, not the source literal alone.

Wire the reconcile/review structural walk gate, including `--apply-structural`, so merge-kind findings dispatch to `merge_bridge`. Pairwise merge findings may keep their producer severity of `info`, but a parseable `merge` directive must make them visible to the targeted structural walk by default; operators must not need `--include-info` in addition to `--apply-structural` to reach the merge bridge. Every unattended, non-TTY, no-opt-in, declined, unsafe, invalid, or gapped path must recommend only. After a successful applied merge, the walk must either halt on the first applied merge or use a plan-stability key / fingerprint guard so later saved directives cannot act on shifted step ids.

## References

- [dataclasses — Data Classes](https://docs.python.org/3/library/dataclasses.html) — Covers frozen dataclass result types and structured immutable objects for bridge return values.
- [argparse — Parser for Command-Line Options](https://docs.python.org/3/library/argparse.html) — Documents CLI option parsing needed for flags like structural apply opt-in and confirmation behavior.
- [typing — Support for Type Hints](https://docs.python.org/3/library/typing.html) — Defines Python typing primitives useful for structured recommendation and dispatch data shapes.
- [unittest.mock — Mock Object Library](https://docs.python.org/3/library/unittest.mock.html) — Covers mocks and patching for testing merge dispatch, confirmations, and invoker seams.
- [pytest Monkeypatch Guide](https://docs.pytest.org/en/stable/how-to/monkeypatch.html) — Explains pytest monkeypatching for isolating CLI behavior, TTY state, confirmations, and side effects.
- [Claude Messages API Reference](https://platform.claude.com/docs/en/api/messages) — Documents Anthropic message invocation semantics relevant to preserving the existing detail-authoring invoker seam.

## Steps

See the `steps:` block in the frontmatter.

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
- `tests/test_review.py`: cover saved recommendation persistence and review-side aggregation for merge-kind findings.
- `tests/test_detail.py`: cover the gated `merge_bridge` result type and gate matrix for recommend-only, applied, unsafe, invalid, malformed, mixed-scope, non-canonical, unknown-id, fewer-than-two-id, and non-contiguous cases.
- `tests/test_review_walk.py`: cover directive-bearing merge findings staying visible under the default info filter.
- `tests/cli/test_review_actions.py`: cover reconcile/review walk dispatch to merge, including default visibility without `--include-info`, opt-in, confirmation, no-opt-in, non-TTY, declined, unsafe, invalid, and stale-directive behavior.

Existing suites that must still pass: `tests/test_granularity.py`, `tests/test_review.py`, `tests/test_detail.py`, `tests/test_review_walk.py`, and `tests/cli/test_review_actions.py`. Cross-module wiring through `plan_tool/review_walk.py`, `plan_tool/cli/review_actions.py`, `plan_tool/cli/parser.py`, and `plan_tool/cli/reconcile.py` should be verified at the CLI/action-dispatch tier because a unit test on only the producer or bridge would miss routing mistakes.

**Per-step test strategy** (derived from each step's `change_type`):

- step 1 (feature) — unit tests added with the implementation; green before completion.
- step 2 (feature) — unit tests added with the implementation; green before completion.
- step 3 (feature) — unit tests added with the implementation; green before completion.
- step 4 (feature) — unit tests added with the implementation; green before completion.
- step 5 (feature) — unit tests added with the implementation; green before completion.
- step 6 (feature) — unit tests added with the implementation; green before completion.

## Acceptance criteria

- A pairwise merge finding can be produced into the saved recommendation walk from a real plan shape, not only from a synthetic unit-test recommendation.
- `reconcile-plan-walk` / `review-walk` can dispatch an info-level merge-kind finding to the merge bridge without requiring `--include-info`.
- With no opt-in, `-y` / apply-all, non-TTY, declined confirm, unsafe state, invalid ids, or a gapped pair, the walk recommends only and mutates nothing.
- With opt-in plus TTY confirmation and safe contiguous member ids, the walk applies the merge through `merge_steps`.
- Applied merge invalidates or halts subsequent directive-carrying findings so renumbering cannot make later saved recommendations mutate the wrong steps.
- Re-ground findings still route to `reground_bridge`, never to merge.
- Scope-out and re-ground behavior remain unchanged.
- Tests cover producer, bridge gate matrix, dispatch, gapped pair handling, and stale-directive/renumber protection.
- Operator docs and `BACKLOG.md` describe that merge is opt-in and confirm-gated, that gapped pairs are recommend-only and require manual judgment, and the stale-directive behavior after an applied merge.
- `BACKLOG.md` is updated to reflect the implemented merge-bridge follow-up and any remaining deferred work.

## Deferred

- Broader automatic merge eligibility outside the structural walk: postpone until the merge bridge has production evidence because global apply semantics need separate safety review.
- Automatic handling for gapped merge pairs: defer until there is a justified merge-range model because non-contiguous pairs require operator judgment in this plan.
- Re-baseline automation after re-ground or merge mutations: leave for a separate plan because this bridge only applies the saved structural directive and preserves human-authored follow-up.
