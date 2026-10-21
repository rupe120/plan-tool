> **Replaced**: this file has been superseded by `docs/implementation-plans/2-refactor-plan-altitude.md`.
> Preserved here for history; do not edit.

# Seed: give `create` an outer-boundary altitude rule for refactor plans

## Source backlog entry

`BACKLOG.md` #291. Completion removes or updates that entry; do not leave it
describing shipped behavior.

## Outcome

`plan-tool create` produces refactor plans whose steps and Architecture first
describe the real outer execution boundaries in the grounded code. Inner
mechanics remain implementation/detail content unless they independently own
an observable contract.

## In scope

- Amend Stage 3 of `plan_tool/create.py:_render_from_prompt` without adding a
  new numbered proposal item or JSON response field. The rule applies in both
  the combined and split foundational-logic prompt arms.
- Update `plan_tool/prompts/synthesize-body.md` so a grounded refactor
  Architecture records load-bearing outer ownership, bypass, and ordering
  contracts, but does not promote supported inner mechanics into plan-level
  phases.
- Add prompt-contract and canned-proposal tests in `tests/test_create.py`.
  Update `docs/PROMPT_AB_TESTING.md` only if its Stage 3 description would
  otherwise become stale.
- Reconcile `BACKLOG.md` #291 when the work completes.

## Problem statement

The current proposal prompt asks for one concern per step and names different
control-flow shapes as a split signal. It does not first establish the plan's
altitude. A refactor proposal can consequently turn guards, accumulators,
selection predicates, result rebuilding, callback placement, or test fixtures
into plan phases even when those mechanics belong to one outer lifecycle.
Later bare-plan audit work then spends its attention distinguishing plan
contracts from implementation detail instead of evaluating the selected design.

## Architecture

For a behavior-preserving refactor, the proposal pass reads the grounded
execution path from the public entry to its terminal persistence/return and
identifies its outer map before it emits steps. An outer phase earns a plan step
when it owns a distinct live boundary: a mutually exclusive dispatch, a shared
lifecycle, an ordered post-loop handler, or a terminal persistence/cleanup
tail. It must name its handoff and the observable behavior that remains
preserved.

An inner guard, accumulator, selection predicate, result reconstruction,
callback, or fixture stays under that phase's detail unless it crosses one of
those outer boundaries or independently changes an observable contract. This
is a selection rule, not a required phase count: a real independently
observable ordering or bypass contract remains plan-level even when its code
is small.

The body-synthesis prompt applies the same boundary: Architecture states only
grounded outer ordering, bypass, ownership, and terminal contracts. Detail
authoring later owns exact recursive selections, data-rebuild mechanics,
callback scope, and fixture shape. The change keeps the existing proposal JSON
shape, existing numbered items, and `Step` schema unchanged.

## Out of scope

- Adding contract fields, criterion links, or other response-schema changes;
  #268 owns that carrier decision.
- Altering detail generation, completeness-audit findings, convergence
  predicates, or the detail-grounded audit bar; #290 owns the bare-audit
  counterpart.
- Rewriting existing plans, mandating a particular number of phases, or
  treating every conditional branch as an independent plan step.
- Changing decomposition rules for feature work beyond the existing
  type-purity and one-concern guidance.

## Allowed behavior changes

New refactor plans may group inner mechanics under an outer phase, resulting in
different step titles, intents, dependency edges, and Architecture prose. The
public `create` command, its proposal response shape, and plan schema remain
unchanged.

## Allowed reorganization

Keep the step-proposal rule within the existing Stage 3 block rather than
adding another hand-numbered prompt item. No production control flow moves.

## Risks

- The prompt can over-merge genuinely separate observable boundaries. Counter
  this by requiring a boundary to name its owner, handoff, and preserved
  behavior, and by explicitly retaining independent dispatch, ordering, and
  bypass contracts at plan altitude.
- Additional prose can dilute existing grounding and type-purity constraints.
  Keep the addition concise and pin it in both A/B arms.
- A synthetic test can prove wording without proving useful decomposition.
  Include a grounded canned refactor proposal and inspect a fresh bare-plan
  audit as qualitative evidence; do not turn that audit into a new gate.

## Testing

- Pin the outer-boundary versus inner-mechanic rule in both proposal-prompt
  arms and confirm the proposal JSON shape and item numbering stay unchanged.
- Use a canned grounded refactor proposal that contains a public dispatch,
  shared lifecycle, ordered post-loop handlers, and a terminal tail. Assert
  that its plan-level steps describe those boundaries and that a selector,
  rebuild, callback, or fixture does not become an independent phase unless
  it owns its own observable contract.
- Pin body-synthesis language that limits refactor Architecture to grounded
  outer ordering, bypass, ownership, and terminal contracts.
- Run the focused create tests and the repository suite. Create one fresh
  refactor plan and record its bare-plan audit disposition as evidence, not as
  a pass/fail requirement.

## Acceptance criteria

- Both proposal prompt arms instruct refactor decomposition to select outer
  execution boundaries before inner control-flow mechanics, without a new
  numbered item or proposal JSON field.
- A plan-level refactor step names its owner, handoff, and preserved observable
  contract; an inner mechanic alone does not qualify as a phase.
- Body synthesis preserves only grounded outer ordering, bypass, ownership,
  and terminal contracts for refactors, leaving fixture and exact mechanism
  design for detail authoring.
- Existing type-purity, code-grounding, foundational-logic, and response-shape
  prompt guarantees remain intact in both A/B arms.
- Tests cover the prompt contract and a boundary-versus-mechanic example, and
  `BACKLOG.md` #291 is reconciled when implementation ships.

## Deferred

New per-step contract carriers remain #268. Bare-audit altitude policy remains
#290. Any behavior that requires a deterministic structural-decomposition gate
is deferred until measured examples justify it.
