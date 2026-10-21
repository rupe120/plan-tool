> **Replaced**: this file has been superseded by `docs/implementation-plans/2-detail-authoring-quality.md`.
> Preserved here for history; do not edit.

# Plan seed: detail-authoring quality - conceptual altitude + concept-thread wording consistency

This file is a `plan-tool create` input, not an implementation plan. Use it via:

```bash
plan-tool create --from-existing plan-seeds/detail-authoring-quality.md --iterate
```

## Overview

Backlog #83 asks for detail-authoring quality rules that keep plan detail at the right conceptual altitude while preserving recurring concept threads as stable wording.

The implementation should add documentation plus advisory audit signals. It must not auto-strip detail, auto-rename concepts, or turn these judgment calls into blocking lint.

## Problem Statement

Detail prose can become falsely authoritative when it over-specifies mechanical choices that belong to the executor, current code, or a ticket. Examples include exact identifiers, magic constants, API literals, full config/IAM snippets, full pseudo-code, or exhaustive test rosters. Those details rot quickly and can distract from the durable decision the step actually needs to preserve.

The opposite failure is terminology drift. When a recurring concept appears across steps or stages, trimming detail often rewords it into near-synonyms. That makes a shared concept harder to follow, harder to reimplement consistently, and harder for later audits to detect deterministically.

These rules are intentionally in tension: reduce brittle mechanics, but do not fracture the phrase that anchors a concept thread.

## Design Requirements

### Detail Format Documentation

Update `DETAIL_FORMAT.md` to document both rules.

Add a keep/cut table for conceptual altitude:

- Keep durable plan detail: design decisions, constraints, landmines, traps, cross-step contracts, correctness cruxes, rejected alternatives, accepted residual-risk rationale, and explicit invariants.
- Demote mechanical detail: exact identifiers, magic constants, API literals, complete configuration/IAM snippets, full pseudo-code, full test rosters, and spelled-out assertions.
- Mechanical details may remain as `e.g.` examples, placeholders, executor notes, or ticket notes when they help orient the implementer.
- Specific detail is still allowed when the specificity is itself the invariant, constraint, or contract.

Add a concept-thread wording rule:

- If a recurring concept spans multiple steps or stages, pick one distinctive phrase and reuse that exact phrase.
- Altitude trimming must not replace the canonical phrase with synonyms.
- Do not force a shared phrase onto genuinely distinct concepts.

### Detail-Quality Audit

Extend the detail-quality audit prompt/builders to add an advisory conceptual-altitude signal.

The signal should flag prose that reads like mandatory implementation mechanics rather than durable plan detail, especially:

- pseudo-code-shaped prose
- exact identifiers or API literals presented as required design
- magic constants presented without rationale
- full config/IAM snippets
- over-specified test rosters or assertion lists

The recommendation should be to demote the mechanical detail to an `e.g.` example, executor note, or ticket note. It should not recommend deletion when the detail might encode a constraint, landmine, rejected alternative, or correctness rationale.

The audit must preserve the existing read-existing-step-first stance: when revising detail, compare against the current step detail before trimming so a weaker source plan cannot erase a hard-won decision.

### Completeness Audit

Extend the plan/detail completeness audit with a concept-thread wording consistency dimension.

The check should detect when the same recurring concept appears across plan steps or detail files under divergent wording. It should recommend choosing and reusing a canonical distinctive phrase.

Detection should be deterministic and conservative:

- Prefer declared concept threads, repeated distinctive tokens, anchors, or clearly shared phrases.
- Avoid fuzzy synonym matching as the primary basis for a finding.
- Do not merge genuinely distinct concepts just because their wording is semantically related.

Findings are advisory only. The completeness audit should never auto-rename phrases or block execution solely on this dimension.

### Feature Thread And Convergence Reporting Interconnection

Make the relationship to feature threading explicit in the final plan.

Feature IDs are the authoritative ownership thread: the plan-level `features:` registry names capabilities, and `step.features` tags say which steps implement those capabilities. Concept-thread wording is not a substitute for that structure.

Concept-thread wording should support feature-level convergence reporting by giving recurring audit findings stable prose anchors. When a recurring concept belongs to a feature, the audit should preserve the canonical phrase in the finding title, body, or anchor so convergence can group the repeated issue deterministically and report it as the same concept recurring within or across the related feature steps.

The intended reporting shape is: feature ID for ownership, canonical concept phrase for finding identity, convergence region for repeated unresolved evidence. Do not infer feature ownership from prose alone, and do not collapse multiple feature IDs merely because they share a concept phrase.

## Step Decomposition Guidance

1. Document the two authoring rules in `DETAIL_FORMAT.md`.
2. Add the conceptual-altitude signal to the detail-quality audit prompt/builders and tests.
3. Add the concept-thread wording consistency dimension to the completeness audit prompt/rendering and tests.
4. Clarify how stable concept wording feeds convergence reporting without replacing the plan's feature registry or step feature tags.
5. Add regression fixtures that cover both failures together: brittle mechanical detail demoted to examples, and recurring concept wording kept stable across steps.

Keep the first step small enough that it can land independently if needed. The prompt/audit work can follow as separate steps because it needs examples and regression tests.

## Suggested Touch Points

- `DETAIL_FORMAT.md`
- `plan_tool/detail.py`
- `plan_tool/prompts/detail-quality.md`
- `plan_tool/prompts/criteria-fulfillment.md`
- `plan_tool/prompts/plan-audit.md`
- `plan_tool/convergence_diagnosis.py`
- `plan_tool/review.py`
- `tests/test_detail.py`
- `tests/test_review.py`

The final plan should inspect the repository before committing to exact file names. The list above is orientation, not a mandate.

## Out Of Scope

- Auto-stripping or rewriting detail prose.
- Hard lint failures for conceptual-altitude judgments.
- Automatic concept renaming across plan/detail files.
- Fuzzy semantic duplicate detection as the core concept-thread mechanism.
- Inferring feature ownership from prose-only concept phrases.
- Changing executor behavior, ticket generation, or implementation code unrelated to audit prompts/docs.

## Risks And Constraints

- Over-aggressive altitude findings can strip load-bearing detail. Mitigation: keep findings advisory, ask for demotion rather than deletion, and preserve constraints, rejected alternatives, and accepted-residual rationale.
- A source plan may be weaker than existing step detail. Mitigation: require read-existing-step-first behavior before any detail trim recommendation.
- Concept consistency can collapse distinct concepts into one phrase. Mitigation: anchor on declared threads or distinctive repeated wording, not broad semantic similarity.
- Concept wording can be confused with feature ownership. Mitigation: keep feature IDs authoritative for ownership and use concept phrases only as finding identity/reporting anchors.
- Prompt changes can become noisy. Mitigation: use narrow examples and explicit negative cases in tests.

## Acceptance Criteria

- `DETAIL_FORMAT.md` includes a conceptual-altitude keep/cut table and a one-distinctive-phrase concept-thread rule.
- Detail-quality audit output can flag over-prescriptive mechanical prose and recommend demoting it to `e.g.` examples or executor/ticket notes.
- Detail-quality audit does not flag load-bearing constraints, landmines, rejected alternatives, or correctness rationale merely because they are specific.
- Completeness audit output can flag divergent wording for the same recurring concept and recommend a canonical phrase.
- Concept-thread findings are based on declared/shared distinctive wording rather than broad fuzzy synonym matching.
- The plan explains that feature IDs own capability threading, while canonical concept phrases stabilize convergence finding identity and reporting.
- No audit auto-applies text changes, auto-renames concepts, or blocks execution solely because of these findings.
- Tests cover positive and negative examples for both conceptual altitude and concept-thread wording consistency.
