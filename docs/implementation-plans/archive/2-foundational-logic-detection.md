> **Auto-archived**: this plan was swept on 2026-06-11 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

---
title: Foundational Logic Detection
status: completed
priority: medium
steps:
- id: 1
  title: Extend create's step-list proposal prompt (`_render_from_prompt`) to instruct
    identifying the plan's foundational logic and surfacing other app locations that
    share it
  files:
  - plan_tool/create.py
  - tests/test_create.py
  complexity: low
  change_type: feature
  detail: docs/implementation-plans/plan-details/foundational-logic-detection/01-extend-create-step-list-proposal-prompt.md
  status: done
- id: 2
  title: Extend detail's prompt template `## Codebase audit` to instruct identifying
    the step's foundational logic and surfacing other app locations that share it
  files:
  - plan_tool/prompts/detail.md
  - tests/test_detail.py
  complexity: low
  change_type: feature
  detail: docs/implementation-plans/plan-details/foundational-logic-detection/02-extend-detail-prompt-template-codebase.md
  status: done
---
# Foundational Logic Detection

## Overview

Extend the `create` and `detail` processes so they identify the foundational logic involved in a plan and look for other places in the application that might need to be updated or consolidated to prevent side effects. The mechanism should be a generic identification of application foundational logic, not tied to any one concept.

## Problem statement

A recent change caused an error in this plan tool because the root-of-project path calculation was implemented in multiple places at once; changing one place left the others inconsistent. Today `create` and `detail` do not identify the foundational logic a plan touches, nor do they surface the other locations that share that logic and would need to be updated or consolidated together. The project-root path duplication is only a conceptual example of this broader class of side-effect bug.

## Architecture

Add a generic identification of application foundational logic to the `create` and `detail` processes. Rather than targeting a specific concept (such as project-root resolution), the identification should generically recognize foundational logic involved in a plan and then scan for other places in the application that implement or depend on the same logic, flagging them as candidates for update or consolidation to prevent side effects. Consolidation may be operationalized as a dedicated refactor/consolidation step that dedups the shared logic into one source, not only as in-place updates to each location — but this minting route holds cleanly only for logic discovered at `create` time. Only `create` can mint such a consolidation step; `detail` (Step 2) authors a single step's body and may add shared locations to the step it details (its `files:` / `## Files (creates vs edits)`), but cannot add new steps, so when its detection names a shared location that needs a new consolidation step, it records that find in the step's `## Deferred` for a human to act on by re-running `create` — neither `detail` nor `reconcile` can mint the step. For a shared location first discovered at `detail` time the consolidation need therefore terminates as `## Deferred` prose with no automatic minting route (reconcile enforcement is itself deferred — see Deferred), pending a human re-running `create`.

## References

This plan is prompt-only and does not implement structural detection; the `ast`/`difflib`/`tokenize`/tree-sitter links below are **background for the deferred structural approach** (see Deferred), not the mechanism this plan uses.

- [ast — Abstract Syntax Trees (Python Standard Library)](https://docs.python.org/3/library/ast.html) — Background for the deferred structural approach: parsing and walking Python source into ASTs to identify foundational logic constructs (functions, calls, assignments). Not used by this prompt-only plan.
- [difflib — Helpers for computing deltas (Python Standard Library)](https://docs.python.org/3/library/difflib.html) — Background for the deferred structural approach: sequence-comparison and similarity-ratio utilities for detecting near-duplicate code blocks across files. Not used by this prompt-only plan.
- [tokenize — Tokenizer for Python source (Python Standard Library)](https://docs.python.org/3/library/tokenize.html) — Background for the deferred structural approach: lexical tokenization for normalizing source into token streams when matching structurally identical logic. Not used by this prompt-only plan.
- [Tree-sitter — Incremental parsing and queries](https://tree-sitter.github.io/tree-sitter/) — Background for the deferred structural approach: language-agnostic parsing and S-expression queries for locating recurring syntactic patterns. Not used by this prompt-only plan.
- [Anthropic — Tool use (function calling) overview](https://docs.anthropic.com/en/docs/build-with-claude/tool-use/overview) — Reference for how the create/detail processes drive Claude with tools and structured outputs to scan the codebase and surface shared-logic candidates for consolidation.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

- The specific root-of-project path calculation cited in the seed — it is only a conceptual example of duplicated foundational logic, not the work this plan targets.

## Risks

- **Prompt-driven detection is non-deterministic.** Foundational-logic identification rides on Claude's response to the `create`/`detail` prompts, so the same plan can surface different (or no) shared locations across runs. Severity: medium. Mitigation: gate the response shape and assert on structure rather than exact matches in tests; recall is not guaranteed.
- **False positives flag unrelated code.** A generic "same foundational logic" scan can over-match incidental similarity, nudging implementers to touch locations that don't actually share the logic. Severity: medium. Mitigation: frame surfaced locations as candidates for review, not mandatory edits; precision tuning is an unresolved gap.
- **Missed duplications give false confidence.** If detection silently finds nothing, authors may assume no shared logic exists when duplicates are simply unrecognized — the exact side-effect bug this plan targets. Severity: high. Mitigation: none beyond best-effort prompting; completeness is not provable.
- **Prompt expansion can regress existing output.** Adding the foundational-logic instruction to the `create` step-list and `detail` audit prompts risks diluting or degrading their current behavior. Severity: low. Mitigation: existing prompt-gate tests (`test_create.py`, `test_detail.py`) catch structural regressions.
- **The instruction is authored twice with no shared source.** The foundational-logic guidance lives independently in `plan_tool/create.py:_render_from_prompt` and `plan_tool/prompts/detail.md`, so wording in one can drift from the other — the same duplicated-foundational-logic class this plan targets. Severity: low. Mitigation: a cross-surface test asserts both rendered prompts contain a canonical foundational-logic keyphrase (`"foundational logic"`), failing if either surface drops or rewords the anchor term so drift is caught rather than silent; a single shared source string remains out of scope.

## Testing

**Per-step test strategy** (derived from each step's `change_type`):

- step 1 (feature) — unit tests added with the implementation; green before completion.
- step 2 (feature) — unit tests added with the implementation; green before completion.

## Acceptance criteria

These are prompt-content guarantees, verified by asserting the rendered prompt text — not behavioral guarantees that detection fires, which non-determinism makes unprovable (see Risks).

- The `create` prompt instructs identification of the foundational logic involved in a plan.
- The `detail` prompt instructs identification of the foundational logic involved in a plan.
- Both prompts instruct surfacing other places in the application that share that foundational logic and may need to be updated or consolidated to prevent side effects.
- The instruction is generic (not specific to project-root path calculation).

## Deferred

- Structural (AST/tree-sitter/difflib) detection of shared logic — this plan uses prompt-driven identification only; structural matching is a larger, separate effort.
- Precision tuning to reduce false positives — the "same foundational logic" scan can over-match; tightening it is an unresolved gap noted in Risks.
- Detection-completeness guarantees — silently missed duplications stay possible; making coverage provable is out of reach for prompt-driven detection.
- The `reconcile` prompt surface — it is a separate prompt not extended here. The create-from-existing step path is already covered: `--from-existing` proposes steps via `propose_steps_from_claude` → `_render_from_prompt` (which Step 1 edits) or the deterministic `extract_steps_from_canonical` (no prompt); the synthesis surface (`_render_synthesis_prompt` / `prompts/synthesize-body.md`) produces body sections only and excludes the `Steps` section by design.
