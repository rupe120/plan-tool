> **Auto-archived**: this plan was swept on 2026-08-18 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 1 — Apply the refactor boundary rule across create proposal paths

## Summary

Update the combined proposal prompt and the create-owned context for the split
foundational-logic sweep. Both state that a behavior-preserving refactor step
represents an observable execution boundary, not merely repeated inner logic.
Keep the existing proposal response, type review, generic sweep merge,
checkpoints, and detail sweep unchanged.

## Table of Contents

- [Summary](#summary) — Changed proposal guidance and preserved behavior.
- [Why](#why) — The authoring problem this step fixes.
- [Input](#input) — Proposal paths this step uses.
- [Files (creates vs edits)](#files-creates-vs-edits) — Changed files.
- [Implementation](#implementation) — Prompt and context requirements.
- [Tests](#tests) — Prompt-contract coverage.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Prompt and pytest guidance.
- [Applicable guardrails](#applicable-guardrails) — Scope limits.
- [Deferred](#deferred) — Work outside this step.

## Why

`plan_tool/create.py:_render_from_prompt()` can treat different control-flow
shapes or repeated shared logic as enough reason to create separate refactor
phases. A guard, selector, rebuild, callback, or fixture belongs in the detail
for its observable owner unless it independently owns an observable handoff,
ordering, or bypass contract. The combined and split proposal prompts need the
same selection rule without changing how create processes their responses.

## Input

- **Combined proposal arm:** `plan_tool/create.py:_render_from_prompt()`
  renders the numbered Stage 2 and Stage 3 guidance plus the inline
  foundational-logic item.
- **Split proposal arm:** `plan_tool/create.py:_render_sweep_context()` passes
  create-specific context to the existing foundational-logic sweep after the
  initial proposal is parsed.
- **Existing processing stays authoritative:** Create's current type review,
  generic sweep parse and merge, checkpoint, and resume behavior are not part
  of this change. Canned prompt tests prove wording and context, not a model's
  future choice or a new enforcement path.

## Files (creates vs edits)

- **New files:** None.

- **Existing files (edits only):**
  - `plan_tool/create.py` — Add the boundary rule to the two proposal-prompt
    surfaces create owns.
  - `tests/test_create.py` — Pin the shared wording, ordering, and preserved
    response shape.

## Implementation

- **Keep the existing prompt ordering.** In
  `plan_tool/create.py:_render_from_prompt()`, retain the Stage 2 type-purity
  instruction before Stage 3. Stage 3 tells a refactor candidate to select a
  distinct observable execution boundary before it treats repeated inner logic
  as a phase. Feature guidance remains the existing one-concern rule.

- **Select observable boundaries, not repetition.** A refactor step can name
  a dispatch, lifecycle, ordered tail, terminal outcome, or another
  independently observable contract. A guard, accumulator, selector, rebuild,
  callback, or fixture stays with its owner even when it appears in several
  places. Promote it only when it independently owns an observable handoff,
  ordering, or bypass contract.

- **Keep the no-map fallback conservative.** When the available code does not
  ground a public-entry-to-terminal path for a refactor candidate, retain the
  existing one-concern guidance. Do not invent an outer boundary or a phase
  count, and do not promote a repeated inner mechanism solely because it
  repeats.

- **Bind the combined foundational item to the rule.** Update
  `plan_tool/create.py:_PROPOSAL_FOUNDATIONAL_ITEM` so its existing option to
  suggest shared logic as a separate refactor step is available only for an
  eligible observable boundary or independently observable contract. Preserve
  its current item number and response shapes.

- **Give the split sweep the same create-owned guidance.** Add a concise rule
  to `plan_tool/create.py:_render_sweep_context()` that applies the same
  boundary-versus-mechanic selection to a separate-refactor suggestion. Do not
  modify the shared sweep prompt, its response schema, or its merge behavior;
  detail receives no new context and retains its current behavior.

- **Do not add enforcement mechanics.** Do not reorder type review, reject or
  remap sweep results, insert a step into an existing dependency graph, renumber
  plan IDs, rewrite dependency notes, or change checkpoint/cache behavior. This
  step communicates the selection rule through existing proposal surfaces.

## Tests

### Tests for this step

- `test_refactor_boundary_rule_survives_both_proposal_arms` — verifies the
  Stage 2 instruction precedes Stage 3, both prompt arms carry the same
  boundary rule, feature guidance remains one concern, and no proposal field is
  added.
- `test_refactor_prompt_keeps_inner_mechanics_in_detail_without_observable_contract`
  — verifies repeated guards, selectors, rebuilds, callbacks, and fixtures are
  not standalone phases solely because they repeat.
- `test_refactor_prompt_uses_one_concern_fallback_when_no_outer_map_is_grounded`
  — verifies the prompt does not invent a boundary or phase count for a partial
  trace.
- `test_combined_foundational_item_requires_an_eligible_boundary` — verifies
  `_PROPOSAL_FOUNDATIONAL_ITEM` states the same rule as Stage 3 without a new
  response shape.
- `test_split_sweep_context_carries_create_boundary_guidance` — verifies
  `_render_sweep_context()` gives the split sweep the same selection rule while
  leaving the current type review, merge, checkpoint, and detail behavior out
  of the contract.
- `test_prompt_item_numbering_has_no_gaps` — extends the existing two-arm
  assertion to confirm the added guidance preserves item continuity and the
  response shape.

Every listed test and affected existing create tests must be green before this
step is complete.

## Acceptance criteria

- Both create proposal arms state that refactor decomposition selects observable
  execution boundaries before repeated inner mechanics, without changing
  proposal JSON keys or item numbering.
- Stage 2's existing type-purity instruction remains before Stage 3, and
  feature guidance remains the existing one-concern rule.
- A repeated inner mechanism remains detail work unless it independently owns
  an observable handoff, ordering, or bypass contract.
- A refactor candidate without a grounded outer map retains the existing
  one-concern guidance and does not invent a boundary or phase count.
- The split sweep receives the create-owned selection rule while type review,
  generic sweep merge, checkpoint behavior, and detail behavior remain
  unchanged.
- `tests/test_create.py` passes with the new prompt-contract coverage.

## References

- [Claude Prompting Best Practices](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices) — Use for concise prompt constraints and response preservation.
- [Define Success Criteria and Build Evaluations](https://docs.claude.com/en/docs/test-and-evaluate/develop-tests) — Use for observable prompt-contract outcomes and their limits.
- [pytest Test Parametrization](https://docs.pytest.org/en/stable/how-to/parametrize.html) — Use for the equivalent combined and split prompt assertions.

## Applicable guardrails

- **The plan's “## Plan intent”, observable-boundary rule:** Change proposal
  guidance so refactor plans stay at observable execution boundaries and leave
  inner mechanics to detail.
- **The plan's “## Out of scope”, existing processing:** Do not add a response
  carrier, merge policy, graph rewrite, ID policy, checkpoint change, or detail
  sweep change.
- **The plan's “## Out of scope”, feature behavior:** Keep the existing
  type-purity and one-concern guidance for feature work.

## Deferred

- **Deterministic enforcement of the selection rule** — Keep type-review
  ordering, sweep merge policy, dependency graph changes, ID policy, and
  checkpoint behavior outside this prompt-guidance change.
- **Detail sweep changes** — Preserve `plan_tool/detail.py`'s current behavior.
