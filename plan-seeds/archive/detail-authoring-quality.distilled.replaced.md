> **Replaced**: this file has been superseded by `docs/implementation-plans/2-detail-authoring-quality.md`.
> Preserved here for history; do not edit.

## Overview

This plan adds detail-authoring quality guidance and advisory audit signals for two related rules: keep plan detail at the right conceptual altitude, and preserve stable wording for recurring concept threads. It documents what detail should be kept, demoted, or preserved, then updates detail-quality and completeness audits to surface non-blocking findings. The implementation must not auto-strip detail, auto-rename concepts, infer feature ownership from prose, or turn these judgment calls into blocking lint.

## Problem statement

Plan detail can become falsely authoritative when it over-specifies mechanical choices that belong to the executor, current code, or a ticket, such as exact identifiers, magic constants, API literals, full config/IAM snippets, full pseudo-code, or exhaustive test rosters. At the same time, trimming those mechanics can introduce terminology drift when a recurring concept is reworded into near-synonyms across steps or stages. The missing behavior is a documented authoring standard plus conservative advisory audits that reduce brittle mechanics without fracturing the phrase that anchors a concept thread.

## Architecture

`DETAIL_FORMAT.md` should become the source of truth for both authoring rules. It should include a keep/cut table for conceptual altitude, explain that mechanical details may remain as `e.g.` examples, placeholders, executor notes, or ticket notes, and state that specificity is still allowed when it is itself the invariant, constraint, or contract.

The detail-quality audit prompt/builders should add an advisory conceptual-altitude signal. The signal should flag prose that reads like mandatory implementation mechanics, while preserving the existing read-existing-step-first stance so weaker source plans cannot erase hard-won existing step detail.

The plan/detail completeness audit should add a conservative concept-thread wording consistency dimension. Detection should prefer declared concept threads, repeated distinctive tokens, anchors, or clearly shared phrases, and should avoid fuzzy synonym matching as the primary basis for findings.

Feature IDs remain the authoritative ownership thread through the plan-level `features:` registry and `step.features` tags. Canonical concept phrases only support finding identity and convergence reporting: feature ID for ownership, canonical concept phrase for finding identity, and convergence region for repeated unresolved evidence.

## Out of scope

- Auto-stripping or rewriting detail prose: findings must remain advisory rather than applying edits.
- Hard lint failures for conceptual-altitude judgments: these calls depend on authoring judgment and should not block execution.
- Automatic concept renaming across plan/detail files: audits can recommend a canonical phrase but must not rewrite it.
- Fuzzy semantic duplicate detection as the core concept-thread mechanism: detection should rely on declared/shared distinctive wording instead.
- Inferring feature ownership from prose-only concept phrases: feature IDs and `step.features` tags remain authoritative.
- Changing executor behavior, ticket generation, or implementation code unrelated to audit prompts/docs: the effort is limited to documentation and audit guidance.

## Risks

- Over-aggressive altitude findings can strip load-bearing detail. Severity: not specified in seed. Mitigation: keep findings advisory, ask for demotion rather than deletion, and preserve constraints, rejected alternatives, and accepted-residual rationale. Unresolved gap: none stated.
- A source plan may be weaker than existing step detail. Severity: not specified in seed. Mitigation: require read-existing-step-first behavior before any detail trim recommendation. Unresolved gap: none stated.
- Concept consistency can collapse distinct concepts into one phrase. Severity: not specified in seed. Mitigation: anchor on declared threads or distinctive repeated wording, not broad semantic similarity. Unresolved gap: none stated.
- Concept wording can be confused with feature ownership. Severity: not specified in seed. Mitigation: keep feature IDs authoritative for ownership and use concept phrases only as finding identity/reporting anchors. Unresolved gap: none stated.
- Prompt changes can become noisy. Severity: not specified in seed. Mitigation: use narrow examples and explicit negative cases in tests. Unresolved gap: none stated.

## Testing

Regression coverage should be added for the documentation and audit prompt/builder changes. Stated target files are `tests/test_detail.py` and `tests/test_review.py`.

Test coverage should include positive and negative examples for conceptual altitude, positive and negative examples for concept-thread wording consistency, and fixtures that cover both failures together: brittle mechanical detail demoted to examples, and recurring concept wording kept stable across steps.

The seed does not identify specific test function names, classes, describe blocks, integration tests, or a project test-tier convention.

## Acceptance criteria

- `DETAIL_FORMAT.md` includes a conceptual-altitude keep/cut table and a one-distinctive-phrase concept-thread rule.
- Detail-quality audit output can flag over-prescriptive mechanical prose and recommend demoting it to `e.g.` examples or executor/ticket notes.
- Detail-quality audit does not flag load-bearing constraints, landmines, rejected alternatives, or correctness rationale merely because they are specific.
- Completeness audit output can flag divergent wording for the same recurring concept and recommend a canonical phrase.
- Concept-thread findings are based on declared/shared distinctive wording rather than broad fuzzy synonym matching.
- The plan explains that feature IDs own capability threading, while canonical concept phrases stabilize convergence finding identity and reporting.
- No audit auto-applies text changes, auto-renames concepts, or blocks execution solely because of these findings.
- Tests cover positive and negative examples for both conceptual altitude and concept-thread wording consistency.
