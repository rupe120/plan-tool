> **Replaced**: this file has been superseded by `docs/implementation-plans/2-refactor-plan-altitude.md`.
> Preserved here for history; do not edit.

## Overview

This plan teaches `plan-tool create` to organize behavior-preserving refactor plans around grounded outer execution boundaries before considering inner control-flow mechanics. It updates Stage 3 of `plan_tool/create.py:_render_from_prompt` and `plan_tool/prompts/synthesize-body.md` while keeping the public `create` command, proposal JSON shape, numbered items, and `Step` schema unchanged. Inner guards, accumulators, selectors, rebuilds, callbacks, and fixtures remain detail content unless they cross an outer boundary or independently own an observable contract.

## Problem statement

The current proposal prompt asks for one concern per step and treats different control-flow shapes as a split signal without first establishing plan altitude. As a result, refactor proposals can promote guards, accumulators, selection predicates, result rebuilding, callback placement, or test fixtures into plan phases even when they belong to one outer lifecycle. Bare-plan audits then spend effort separating plan contracts from implementation detail instead of evaluating the selected design.

## Architecture

For a behavior-preserving refactor, the proposal pass follows the grounded execution path from the public entry through terminal persistence or return and identifies the outer map before emitting steps. A plan step represents a distinct live boundary—mutually exclusive dispatch, a shared lifecycle, an ordered post-loop handler, or a terminal persistence/cleanup tail—and names its owner, handoff, and preserved observable behavior.

An inner guard, accumulator, selection predicate, result reconstruction, callback, or fixture remains within that phase's detail unless it crosses an outer boundary or independently changes an observable contract. This rule selects boundaries rather than prescribing a phase count, so small but independently observable ordering or bypass contracts remain plan-level.

The rule stays within the existing Stage 3 block of `plan_tool/create.py:_render_from_prompt` and applies to both combined and split foundational-logic prompt arms without moving production control flow. `plan_tool/prompts/synthesize-body.md` applies the same boundary: Architecture records only grounded outer ordering, bypass, ownership, and terminal contracts, while detail authoring owns exact recursive selections, data-rebuild mechanics, callback scope, and fixture shape. `docs/PROMPT_AB_TESTING.md` changes only if its Stage 3 description would otherwise become stale.

## Out of scope

- Adding contract fields, criterion links, or other response-schema changes; #268 owns that carrier decision.
- Altering detail generation, completeness-audit findings, convergence predicates, or the detail-grounded audit bar; #290 owns the bare-audit counterpart.
- Rewriting existing plans, mandating a particular number of phases, or treating every conditional branch as an independent plan step.
- Changing decomposition rules for feature work beyond the existing type-purity and one-concern guidance.

## Risks

- The prompt can over-merge genuinely separate observable boundaries. Severity is not specified in the seed. Require each boundary to name its owner, handoff, and preserved behavior, while retaining independent dispatch, ordering, and bypass contracts at plan altitude.
- Additional prose can dilute existing grounding and type-purity constraints. Severity is not specified in the seed. Keep the addition concise and pin it in both A/B arms.
- A synthetic test can prove wording without proving useful decomposition. Severity is not specified in the seed. Include a grounded canned refactor proposal and inspect a fresh bare-plan audit as qualitative evidence without making that audit a new gate.

## Testing

- In `tests/test_create.py`, pin the outer-boundary versus inner-mechanic rule in both proposal-prompt arms and confirm that proposal JSON shape and item numbering remain unchanged.
- In `tests/test_create.py`, use a canned grounded refactor proposal containing a public dispatch, shared lifecycle, ordered post-loop handlers, and a terminal tail. Assert that plan-level steps describe those boundaries and that a selector, rebuild, callback, or fixture does not become an independent phase unless it owns an observable contract.
- Pin the `plan_tool/prompts/synthesize-body.md` language that limits refactor Architecture to grounded outer ordering, bypass, ownership, and terminal contracts.
- Run the focused create tests and the repository suite.
- Create one fresh refactor plan and record its bare-plan audit disposition as qualitative evidence, not as a pass/fail requirement.

## Acceptance criteria

- Both proposal prompt arms instruct refactor decomposition to select outer execution boundaries before inner control-flow mechanics, without adding a numbered item or proposal JSON field.
- A plan-level refactor step names its owner, handoff, and preserved observable contract; an inner mechanic alone does not qualify as a phase.
- `plan_tool/prompts/synthesize-body.md` preserves only grounded outer ordering, bypass, ownership, and terminal contracts for refactors, leaving fixture and exact mechanism design to detail authoring.
- Existing type-purity, code-grounding, foundational-logic, and response-shape prompt guarantees remain intact in both A/B arms.
- `tests/test_create.py` covers the prompt contract and a boundary-versus-mechanic example.
- `BACKLOG.md` #291 is removed or updated when implementation ships so it does not describe shipped behavior.

## Deferred

- New per-step contract carriers remain #268.
- Bare-audit altitude policy remains #290.
- Any behavior requiring a deterministic structural-decomposition gate remains deferred until measured examples justify it.
