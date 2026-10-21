> **Auto-archived**: this plan was swept on 2026-06-27 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

---
title: Detail Authoring Quality
status: completed
priority: medium
enforce_step_tests: true
steps:
- id: 1
  title: Document conceptual altitude and concept phrase rules
  files:
  - DETAIL_FORMAT.md
  complexity: low
  change_type: non-code
  detail: docs/implementation-plans/plan-details/detail-authoring-quality/01-document-conceptual-altitude-concept.md
  status: done
- id: 2
  title: Add advisory-only detail-quality altitude findings and tests
  files:
  - plan_tool/detail.py
  - plan_tool/review.py
  - plan_tool/prompts/detail-quality.md
  - tests/test_detail.py
  - tests/test_review.py
  complexity: medium
  change_type: feature
  depends_on:
  - 1
  detail: docs/implementation-plans/plan-details/detail-authoring-quality/02-advisory-only-detail-quality-altitude.md
  status: done
- id: 3
  title: Add concept phrase consistency guidance to plan audit and tests
  files:
  - plan_tool/review.py
  - plan_tool/prompts/plan-audit.md
  - plan_tool/prompts/apply-finding.md
  - tests/test_review.py
  - tests/test_launcher.py
  complexity: medium
  change_type: feature
  depends_on:
  - 1
  detail: docs/implementation-plans/plan-details/detail-authoring-quality/03-concept-phrase-consistency-guidance.md
  status: done
---
# Detail Authoring Quality

## Overview

This plan adds authoring guidance and advisory audit signals for keeping plan detail at the right level and preserving stable wording for recurring concept threads. `DETAIL_FORMAT.md` becomes the source of truth for what detail should be kept, demoted, or preserved. The audits surface non-blocking findings only: they must not auto-strip detail, auto-rename concepts, infer feature ownership from prose, or turn these judgment calls into blocking lint.

## Problem statement

Plan detail can become falsely authoritative when it over-specifies mechanical choices that belong to the executor, current code, or a ticket, such as exact identifiers, magic constants, API literals, full config/IAM snippets, full pseudo-code, or exhaustive test rosters. At the same time, trimming those mechanics can introduce terminology drift when a recurring concept is reworded into near-synonyms across steps or stages. The missing behavior is a documented authoring standard plus conservative advisory audits that reduce brittle mechanics without fracturing the phrase that anchors a concept thread.

## Architecture

`DETAIL_FORMAT.md` should become the source of truth for both authoring rules. It should include a keep/cut table for conceptual altitude, explain that mechanical details may remain as `e.g.` examples, placeholders, executor notes, or ticket notes, and state that specificity is still allowed when it is itself the invariant, constraint, or contract.

The detail-quality audit prompt/builders should add an advisory conceptual-altitude signal. The signal should flag prose that reads like mandatory implementation mechanics, while preserving the existing read-existing-step-first stance so weaker source plans cannot erase hard-won existing step detail.

The plan/detail completeness audit should add a conservative concept-thread wording consistency dimension. Detection should prefer declared concept threads, repeated distinctive tokens, anchors, or clearly shared phrases, and should avoid fuzzy synonym matching as the primary basis for findings. Phrase drift alone should emit only low/info advisory findings; medium+ correctness/completeness findings are reserved for independent substantive design gaps.

Feature IDs remain the authoritative ownership thread through the plan-level `features:` registry and `step.features` tags. Canonical concept phrases only support finding identity and convergence reporting: feature ID for ownership, canonical concept phrase for finding identity, and convergence region for repeated unresolved evidence.

The same authoring guidance must also shape how conceptual-completeness gaps are applied. `completeness-apply` routes `plan-completeness` findings through the shared `apply_finding` prompt, so the prompt used to build and apply those updates should preserve conceptual altitude, reuse canonical concept phrases, and keep feature ownership tied to explicit feature IDs rather than prose-only inference.

## References

- [GitHub Flavored Markdown Spec](https://github.github.com/gfm/) — Defines GitHub Markdown tables, lists, code fences, and headings for updating DETAIL_FORMAT.md precisely.
- [Claude Prompting Best Practices](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices) — Covers clear prompt instructions, examples, structure, and output formatting for revising audit prompts.
- [OpenAI Structured Outputs Guide](https://developers.openai.com/api/docs/guides/structured-outputs) — Explains schema-constrained model outputs useful when audit findings are expected in structured form.
- [pytest: Parametrize Fixtures and Test Functions](https://docs.pytest.org/en/stable/how-to/parametrize.html) — Documents parametrized test cases for covering positive and negative audit examples without duplication.
- [pytest: Assertions in Tests](https://docs.pytest.org/en/stable/how-to/assert.html) — Documents idiomatic pytest assertions and failure reporting for regression tests in test_detail.py and test_review.py.
- [Python re Module Reference](https://docs.python.org/3/library/re.html) — Defines Python regular expression behavior for conservative phrase, token, and anchor matching logic.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

- Auto-stripping or rewriting detail prose: findings must remain advisory rather than applying edits.
- Hard lint failures for conceptual-altitude judgments: these calls depend on authoring judgment and should not block execution.
- Automatic concept renaming across plan/detail files: audits can recommend a canonical phrase but must not rewrite it.
- Fuzzy semantic duplicate detection as the core concept-thread mechanism: detection should rely on declared/shared distinctive wording instead.
- Inferring feature ownership from prose-only concept phrases: feature IDs and `step.features` tags remain authoritative.
- Changing executor behavior, ticket generation, or implementation code unrelated to audit/apply prompts/docs: the effort is limited to documentation, audit guidance, and the prompt contract that `completeness-apply` uses when applying conceptual gap updates.

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

**Per-step test strategy** (derived from each step's `change_type`):

- step 1 (non-code) — verification appropriate to the artifacts; no test-ordering directive.
- step 2 (feature) — unit tests added with the implementation; green before completion.
- step 3 (feature) — unit tests added with the implementation; green before completion.

## Acceptance criteria

- `DETAIL_FORMAT.md` includes a conceptual-altitude keep/cut table and a one-distinctive-phrase concept-thread rule.
- Detail-quality audit output can flag over-prescriptive mechanical prose and recommend demoting it to `e.g.` examples or executor/ticket notes.
- Detail-quality audit does not flag load-bearing constraints, landmines, rejected alternatives, or correctness rationale merely because they are specific.
- Completeness audit output can flag divergent wording for the same recurring concept as a low/info advisory finding and recommend a canonical phrase.
- Concept-thread findings are based on declared/shared distinctive wording rather than broad fuzzy synonym matching.
- The plan explains that feature IDs own capability threading, while canonical concept phrases stabilize convergence finding identity and reporting.
- `completeness-apply`'s gap-closing update path builds apply prompts that preserve conceptual altitude, preserve canonical concept-thread wording, and do not infer feature ownership from prose alone.
- No audit auto-applies text changes, auto-renames concepts, or blocks execution solely because of these findings.
- Tests cover positive and negative examples for both conceptual altitude and concept-thread wording consistency.
- Tests include a shared regression fixture that covers brittle mechanical detail demotion and stable recurring concept wording in the same plan/detail example.

## Deferred

- No deferred items identified: the seed does not name postponed follow-up work for this plan.
