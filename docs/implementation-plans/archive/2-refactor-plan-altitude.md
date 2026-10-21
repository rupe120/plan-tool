> **Auto-archived**: this plan was swept on 2026-08-18 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

---
title: Refactor Plan Altitude
intent: '`plan-tool create` proposes behavior-preserving refactor plans at their observable
  execution boundaries, while grounded Architecture prose keeps inner mechanics in
  detail unless they own an observable contract.'
status: completed
priority: medium
enforce_step_tests: true
steps:
- id: 1
  title: Apply the refactor boundary rule across create proposal paths
  intent: Create's proposal guidance selects observable execution boundaries before
    it turns a repeated inner mechanism into a refactor phase.
  files:
  - plan_tool/create.py
  - tests/test_create.py
  complexity: low
  change_type: feature
  detail: docs/implementation-plans/plan-details/refactor-plan-altitude/01-apply-refactor-boundary-rule-across.md
  status: done
- id: 2
  title: Keep synthesized Architecture from promoting inner mechanics and close BACKLOG
  intent: Grounded Architecture prose preserves stated observable contracts and feature
    outcomes without inventing a refactor map from source mechanics.
  files:
  - plan_tool/prompts/synthesize-body.md
  - tests/test_create.py
  - BACKLOG.md
  complexity: low
  change_type: feature
  depends_on:
  - 1
  depends_on_notes:
    1: Supplies the boundary-versus-mechanic selection rule that synthesized Architecture
      must preserve in source-grounded prose.
  detail: docs/implementation-plans/plan-details/refactor-plan-altitude/02-keep-synthesized-architecture-promoting.md
  status: done
---
# Refactor Plan Altitude

## Overview

This plan teaches `plan-tool create` to organize behavior-preserving refactor
proposals around grounded outer execution boundaries before considering inner
control-flow mechanics. It changes Stage 3 and the existing create guidance
that can turn shared logic into a separate plan step, plus the existing
`plan_tool/prompts/synthesize-body.md` instruction while keeping the public
`create` command, proposal JSON shape, numbered items, `Step` schema,
checkpoints, and create lifecycle unchanged. Inner guards, accumulators,
selectors, rebuilds, callbacks, and fixtures remain detail content unless they
independently own an observable cross-boundary handoff, ordering, or bypass
contract. Crossing an outer boundary alone records the mechanic under its
owners; it does not create another phase. The proposal prompt retains its
existing Stage 2 type-purity instruction before the Stage 3 boundary
instruction: it tells a mixed candidate to separate refactor and feature work,
then tells a refactor candidate how to select a boundary while the feature
guidance stays one concern. This is proposal guidance, not a reordering of the
existing reviewer or sweep lifecycle. When a refactor candidate has no grounded
public-entry-to-terminal map, it retains the existing one-concern guidance; it
does not invent an outer boundary or a phase count. That fallback keeps the
same inner-mechanic exception: a repeated guard does not become a phase solely
because it repeats; it must itself own an observable cross-boundary handoff,
ordering, or bypass contract.

## Problem statement

The current proposal prompt asks for one concern per step and treats different
control-flow shapes as a split signal without first establishing plan altitude.
As a result, refactor proposals can promote guards, accumulators, selection
predicates, result rebuilding, callback placement, or test fixtures into plan
phases even when they belong to one outer lifecycle. Bare-plan audits then
spend effort separating plan contracts from implementation detail instead of
evaluating the selected design.

## Architecture

For a behavior-preserving refactor candidate, the proposal pass follows the
grounded execution path from public entry through terminal persistence or return
and identifies its outer map before emitting steps. A plan step represents a
distinct live boundary: mutually exclusive dispatch, a shared lifecycle, an
ordered post-loop handler, or a terminal persistence/cleanup tail. Its existing
title and one-line `intent` name the boundary and why it exists; no new
owner/handoff field or response key is introduced.

When a leaf refactor or partial trace has no single grounded path between a
public entry and terminal boundary, Stage 3 retains the existing one-concern
decomposition instead of inventing an outer map. The fallback is not an
exception to the prompt's type-purity instruction: Stage 2 asks a mixed
candidate to split before Stage 3 applies either the grounded-boundary rule or
this one-concern fallback to a stated refactor candidate. The fallback retains
the inner-mechanic exception: a repeated guard still needs an observable
cross-boundary handoff, ordering, or bypass contract before it becomes a phase.

An inner guard, accumulator, selection predicate, result reconstruction,
callback, or fixture remains within its outer boundary's detail even when it
appears at more than one boundary. It becomes plan-level only when it itself
owns an independently observable cross-boundary handoff, ordering, or bypass
contract; a repeated implementation detail is not a phase. This is a selection
rule, not a phase-count target. Stage 3 narrows its existing cross-cutting
invariant rule for refactor candidates to that observable-contract case. The
same guidance reaches both create prompt arms: the combined arm's existing
foundational-logic item and the create-owned context for the split sweep may
suggest a separate refactor step only for the same observable-boundary or
independently observable-contract case. Repeated inner logic remains with its
owner. Existing type review, generic sweep parsing and merge behavior,
checkpoint behavior, and detail's per-step sweep remain unchanged. Step detail
selects concise prompt/context wording and tests; it does not introduce a merge
policy, graph rewrite, ID policy, or checkpoint contract.

The body-synthesis prompt does not receive reviewed refactor/feature legs and
does not infer them from a step graph. Instead it applies one source-grounded
rule to every seed: retain its stated observable behavior and outer ownership,
ordering, bypass, and terminal contracts, but do not elevate a guard, predicate,
accumulator, rebuild, callback, or fixture merely because the source names it.
For a refactor source this keeps Architecture at the outer-boundary altitude,
including an independent boundary with no `depends_on` edge. For a mixed source
it preserves the stated feature outcome and any supported contract without
flattening them into a refactor map or inventing inner mechanics. It does not
refresh an already written plan. Existing `--no-synthesize-body`,
canonical-input, checkpoint, detail foundational-sweep, detail, and convergence
behavior therefore remain unchanged. Detail authoring owns exact recursive
selections, data-rebuild mechanics, callback scope, and fixture shape.

`docs/PROMPT_AB_TESTING.md` changes only if its Stage 3 description would
otherwise become stale.

## References

- [Claude Prompting Best Practices](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices) — Covers clear, grounded instructions, examples, and output-format control for revising Stage 3 and source-grounded body synthesis.
- [Define Success Criteria and Build Evaluations](https://docs.claude.com/en/docs/test-and-evaluate/develop-tests) — Covers task-specific success criteria and evaluation design for refactor decomposition behavior.
- [pytest Test Parametrization](https://docs.pytest.org/en/stable/how-to/parametrize.html) — Documents pytest parametrization for pinning the same Stage 3 contract in both A/B arms.
- [pytest Monkeypatching](https://docs.pytest.org/en/stable/how-to/monkeypatch.html) — Documents pytest's monkeypatch fixture for substituting canned model responses and isolating prompt-driven tests.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

- Adding contract fields, criterion links, graph provenance, or other response-schema changes; #268 owns that carrier decision.
- Changing detail's foundational-logic sweep behavior, detail generation,
  completeness-audit findings, convergence predicates, checkpoint policy, or
  the detail-grounded audit bar; #290 owns the bare-audit counterpart.
- Changing generic sweep parsing or merge behavior, reviewer ordering, plan-ID
  assignment, dependency rewrites, or cache keys to enforce this guidance.
- Rewriting existing plans, changing canonical-input behavior, mandating a particular number of phases, or treating every conditional branch as an independent plan step.
- Changing decomposition rules for feature work beyond the existing type-purity and one-concern guidance.

## Risks

- The rule can over-merge genuinely separate observable boundaries. Retain independent dispatch, ordering, and bypass contracts at plan altitude; a boundary must own an observable contract, not merely a convenient code fragment.
- A partial trace can lack a grounded outer boundary. Preserve the existing
  one-concern rule for that refactor leg rather than inventing a public entry,
  terminal tail, or phase count; its repeated inner mechanics still require an
  observable contract before becoming a phase.
- Existing create guidance can suggest shared logic as a separate refactor
  step. State the same observable-boundary rule in both prompt arms without
  turning it into merge enforcement or changing detail behavior.
- Added prompt prose can dilute existing grounding and type-purity instructions. Keep it concise, test both prompt arms, and preserve their response shape and numbering.
- A synthetic test can prove wording without proving useful decomposition. Use a grounded canned refactor proposal and record a fresh bare-plan audit as qualitative evidence, not as a new gate.
- A source can mix refactoring with new behavior or lack evidence for an outer
  Architecture claim. The synthesis instruction preserves its stated feature
  outcome and only source- or local-code-supported contracts, leaving
  unsupported mechanics for detail rather than inventing a map.

## Testing

- In `tests/test_create.py`, pin the Stage 2 type-purity instruction before the
  Stage 3 boundary instruction, the boundary-versus-inner-mechanic rule, and
  the no-grounded-map fallback in both proposal-prompt arms. Confirm proposal
  JSON shape and item numbering remain unchanged. A partial trace with a
  repeated guard remains one concern unless that guard owns an observable
  cross-boundary contract.
- Pin the cross-path selection property: shared logic becomes a separate
  refactor suggestion only for an eligible outer boundary or independently
  observable contract; repeated inner logic remains with its owner. Confirm
  the split sweep receives that create-owned guidance while existing merge,
  checkpoint, type-review, and detail-sweep behavior stay unchanged.
- Pin the body-synthesis prompt language: a source-supported refactor Architecture retains outer ownership, ordering, bypass, and terminal claims, including the independent boundary, without promoting inner mechanics. Pin ordinary feature and mixed refactor-plus-feature seeds to prove their stated feature outcomes remain intact and no reviewed-type graph or invented refactor map is required.
- Preserve the existing `--no-synthesize-body`, canonical-input, checkpoint,
  sweep merge, detail-sweep, detail, and convergence tests; this plan does not
  add a graph handoff, final refresh, cache invalidation path, or enforcement
  policy.
- Run focused create tests and the repository suite. Create one fresh refactor plan and record its bare-plan audit disposition as qualitative evidence, not as a pass/fail requirement.

**Per-step test strategy** (derived from each step's `change_type`):

- step 1 (feature) — tests covering the behavior this step changes; green before completion.
- step 2 (feature) — tests covering the behavior this step changes; green before completion.

## Acceptance criteria

- Both proposal prompt arms instruct refactor decomposition to select outer
  execution boundaries before inner control-flow mechanics, without adding a
  numbered item or proposal JSON field. Stage 2's existing type-purity
  instruction remains before Stage 3's boundary instruction; refactor
  candidates receive the grounded-boundary rule or the existing one-concern
  fallback, and feature guidance retains the one-concern rule. Existing create
  guidance states that same rule before it suggests shared logic as a separate
  refactor step.
- A refactor plan step names a distinct observable boundary and why it exists.
  A guard, selector, rebuild, callback, or fixture remains detail even when it
  crosses owners or repeats in a partial trace, unless it independently owns an
  observable cross-boundary handoff, ordering, or bypass contract.
- `plan_tool/prompts/synthesize-body.md` preserves source- or local-code-
  supported observable behavior and outer ownership, ordering, bypass, and
  terminal contracts, including an independent boundary that has no dependency
  edge. Feature outcomes remain stated in ordinary and mixed seeds; fixture and
  exact mechanism design remain for detail authoring.
- Existing response-shape, `--no-synthesize-body`, canonical-input,
  checkpoint, sweep merge, detail-sweep, detail, and convergence guarantees
  remain intact.
- Tests cover the cross-path prompt contract and a boundary-versus-mechanic
  example, and `BACKLOG.md` #291 is removed or updated when implementation
  ships.

## Deferred

- New per-step contract carriers remain #268.
- Bare-audit altitude policy remains #290.
- Any deterministic structural-decomposition gate remains deferred until measured examples justify it.
