> **Auto-archived**: this plan was swept on 2026-08-18 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 2 — Keep synthesized Architecture from promoting inner mechanics and close BACKLOG

## Summary

Update `plan_tool/prompts/synthesize-body.md` so synthesized Architecture prose retains supported observable contracts and feature outcomes without turning source-level mechanics into a refactor map. Add prompt-contract coverage in `tests/test_create.py` around `plan_tool/create.py:propose_body_sections()`. Retire the open `BACKLOG.md` #291 item once both this prompt rule and step 1’s proposal rule are covered, while retaining the replay provenance that #290 needs. On green, fresh body synthesis keeps inner guards, predicates, rebuilds, callbacks, and fixtures in detail unless the evidence gives them their own observable contract.

## Table of Contents

- [Summary](#summary) — Reviewer overview of the prompt, test, and backlog changes.
- [Table of Contents](#table-of-contents) — Links to each section in this detail.
- [Why](#why) — The source-grounding problem this step fixes.
- [Input](#input) — Existing synthesis and prompt-output contracts this step reads.
- [Files (creates vs edits)](#files-creates-vs-edits) — Files changed by this step.
- [Implementation](#implementation) — Required Architecture-synthesis behavior and preserved contracts.
- [Tests](#tests) — Prompt-contract coverage for the new rule.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Prompt and pytest guidance.
- [Applicable guardrails](#applicable-guardrails) — Plan boundaries that limit this work.
- [Deferred](#deferred) — Related work left outside this step.

## Why

`plan_tool/prompts/synthesize-body.md` currently asks Architecture to derive a design from the seed and bounded code evidence, but it does not say which level of detail belongs there. That leaves source excerpts free to turn a guard, selector, rebuild, callback, or fixture into plan architecture even when the evidence only supports an outer ownership, ordering, bypass, or terminal contract. Step 1 supplies the rule for proposing refactor steps; this step makes the later body-synthesis pass preserve that rule without changing the generated plan’s shape.

## Input

- **Synthesis template contract:** `plan_tool/create.py:_render_synthesis_prompt()` loads `plan_tool/prompts/synthesize-body.md`, and `plan_tool/create.py:propose_body_sections()` validates its eight canonical JSON keys plus recognized optional keys. Keep this output shape unchanged.
- **Grounding inputs:** `plan_tool/create.py:propose_body_sections()` supplies the seed, fetched reference documentation, bounded Architecture code excerpts, resolved code citations, and dependency-cohesion notes. The prompt may use only those inputs.
- **Step 1 outcome:** Step 1 supplies the observable-boundary rule for refactor proposal paths. This prompt consumes that rule as a prose-selection boundary; it does not receive or infer reviewed refactor and feature legs.
- **Cache behavior:** `plan_tool/create.py:_body_sections_input_hash()` deliberately keys cached synthesis on its grounding inputs rather than the prompt template. Keep checkpoint and resume behavior unchanged; the new prompt applies when synthesis runs.

## Files (creates vs edits)

- **New files:** None.

- **Existing files (edits only):**
  - `plan_tool/prompts/synthesize-body.md` — Add Architecture-specific guidance that keeps grounded observable contracts and feature outcomes while leaving unsupported inner mechanics to detail.
  - `tests/test_create.py` — Add prompt-contract tests beside `TestProposeBodySectionsFromClaude` and extend existing grounding coverage where needed.
  - `BACKLOG.md` — Retire the completed #291 entry while retaining #290’s replay provenance.

## Implementation

- **Keep Architecture at the observable contract level.** In `plan_tool/prompts/synthesize-body.md:## Field rules`, add a clear Architecture rule: retain source- or local-code-supported outer ownership, ordering, bypass, terminal, and independent-boundary claims. Do not promote a guard, predicate, accumulator, rebuild, callback, or fixture merely because an excerpt names it.

- **Do not infer a refactor map.** `plan_tool/create.py:propose_body_sections()` receives source and grounding evidence, not the reviewed type-pure legs from step 1. The prompt must not manufacture a phase map, use a `depends_on` edge as proof of an ownership boundary, or treat every conditional branch as an independent boundary.

- **Keep stated feature outcomes visible.** For ordinary feature and mixed seeds, preserve the supported feature result and any observable contract it needs. Do not flatten that outcome into a refactor narrative just because the seed also mentions restructuring.

- **Preserve independent contracts.** Keep a supported outer boundary when it has no dependency edge. The rule removes unsupported inner-mechanic promotion; it must not hide a distinct observable handoff, ordering, bypass, or terminal contract.

- **Keep existing synthesis safeguards unchanged.** Retain the source-only evidence boundary, resolved Architecture citation requirement, seed/code conflict and ambiguity callouts, JSON key set, canonical-seed skip, `--no-synthesize-body` behavior, and checkpoint rules. No change is needed to `plan_tool/create.py:_render_synthesis_prompt()` or `plan_tool/create.py:propose_body_sections()` beyond loading the revised template.

- **Close the completed backlog item without destroying provenance.** Once step 1’s proposal-path work and this prompt contract are green, retire #291’s open backlog entry using the project’s established convention. Keep the #290 references that identify the two-stage replay and fixture commitments that informed its own audit-policy work.

## Tests

### Tests for this step

- `test_synthesis_prompt_keeps_architecture_at_contract_level` — parameterizes refactor, feature, and mixed source seeds and asserts the rendered prompt preserves supported outer contracts and feature outcomes without promoting listed inner mechanics.
- `test_synthesis_prompt_does_not_infer_a_refactor_map_from_grounding` — asserts the prompt does not turn source excerpts or dependency-cohesion notes into phase boundaries, while preserving an independently observable boundary.
- `test_prompt_carries_local_code_context_and_conflict_rule` — extend the existing test to retain bounded-evidence, required-citation, and conflict-callout instructions alongside the new Architecture rule.

Every listed test and the affected existing `tests/test_create.py` synthesis tests must be green before this step is complete.

## Acceptance criteria

- A fresh `propose_body_sections()` prompt directs Architecture synthesis to preserve supported observable ownership, ordering, bypass, terminal, and feature-outcome claims.
- The prompt explicitly leaves named inner mechanics to detail unless the available evidence establishes an independent observable contract.
- The prompt does not infer a refactor map, dependency graph, or phase count from source mechanics or dependency-cohesion notes.
- Existing Architecture citation, conflict, ambiguity, JSON-shape, canonical-skip, opt-out, and checkpoint behavior remains unchanged.
- The listed `tests/test_create.py` cases pass.
- #291’s open backlog entry is retired using the project’s established convention, while #290 retains the replay provenance required by its audit-policy work.

## References

- [Claude Prompting Best Practices](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices) — Use for concise, source-grounded prompt instructions.
- [Define Success Criteria and Build Evaluations](https://docs.claude.com/en/docs/test-and-evaluate/develop-tests) — Use for observable prompt-contract outcomes and their limits.
- [pytest Test Parametrization](https://docs.pytest.org/en/stable/how-to/parametrize.html) — Use to cover refactor, feature, and mixed seed cases with one contract test.

## Applicable guardrails

- **The plan’s “## Plan intent”, observable-boundary planning rule:** Limit this prompt change to keeping Architecture prose at the same observable-contract level as the proposal rule.
- **The plan’s “## Step intent”, grounded Architecture prose:** Preserve supported behavior and feature outcomes without inventing a source-derived refactor structure.
- **The plan’s “## Out of scope”, response and workflow ownership:** Do not add schema fields, alter canonical-input or checkpoint behavior, change detail generation, or change feature decomposition rules.

## Deferred

- **New per-step contract carriers** — Keep this response-schema decision with #268.
- **Bare-audit level-of-detail policy** — Keep the audit counterpart with #290.
- **`plan_tool/prompts/distill-seed.md` changes** — Leave the separate seed-only reorganization pass unchanged; it does not receive this synthesis pass’s bounded local-code evidence.
