> **Auto-archived**: this plan was swept on 2026-08-18 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

---
title: Bare Plan Audit Altitude
intent: A bare-plan audit no longer blocks convergence on findings that describe implementation
  mechanics a detail file should own, while genuine plan-level defects — including
  an uncovered route for a named property — remain correctness findings. No blocking
  predicate gains a new non-deterministic input.
status: completed
priority: medium
enforce_step_tests: true
steps:
- id: 1
  title: Teach the bare audit to require property coverage and leave delivery mechanisms
    to detail
  intent: Keep named observable-contract coverage actionable in both combined and
    split proposal paths, while omitting an unselected delivery choice from bare findings.
  files:
  - plan_tool/prompts/plan-audit.md
  - plan_tool/review.py
  - tests/test_review.py
  creates:
  - tests/fixtures/convergence/bare-altitude-two-stage-replay.json
  complexity: medium
  change_type: feature
  detail: docs/implementation-plans/plan-details/bare-plan-audit-altitude/01-teach-bare-audit-require-property.md
  status: done
- id: 2
  title: Classify likely bare-plan mechanism findings from persisted recommendation
    text
  intent: Give operators a stable warning for a positive detail-mechanism case without
    misclassifying a named property, route obligation, or textually explicit observable
    contract; leave ambiguous text unlabelled.
  files:
  - plan_tool/review.py
  - plan_tool/convergence_diagnosis.py
  - tests/test_review.py
  - tests/test_convergence_diagnosis.py
  complexity: medium
  change_type: feature
  depends_on:
  - 1
  depends_on_notes:
    1: Supplies the settled property-versus-mechanism boundary and the two-stage replay
      cases the classifier must match.
  detail: docs/implementation-plans/plan-details/bare-plan-audit-altitude/02-classify-likely-bare-plan-mechanism.md
  status: done
- id: 3
  title: Show the mechanism advisory in convergence and combine matching edit drift
  intent: Warn after one eligible bare pass, then compose only the same finding's
    edit-drift signal so unrelated findings retain their own advice.
  files:
  - plan_tool/convergence_diagnosis.py
  - plan_tool/cli/convergence_cmd.py
  - tests/test_convergence_diagnosis.py
  - tests/cli/test_convergence_cmd.py
  complexity: medium
  change_type: feature
  depends_on:
  - 2
  depends_on_notes:
    2: Provides the deterministic per-finding signal consumed by convergence diagnosis
      and advisory composition.
  detail: docs/implementation-plans/plan-details/bare-plan-audit-altitude/03-show-mechanism-advisory-convergence.md
  status: done
- id: 4
  title: Show the same advisory on completeness stderr without changing audit outcomes
  intent: Put the same eligible, standalone, and same-finding-composed guidance beside
    a completed run-grade bare audit without changing its outcome or Jira-grade suppression.
  files:
  - plan_tool/cli/completeness_cmd.py
  - tests/cli/test_completeness_cmd.py
  complexity: low
  change_type: feature
  depends_on:
  - 3
  depends_on_notes:
    3: Provides the shared advisory rendering and edit-drift composition that completeness
      stderr reuses.
  detail: docs/implementation-plans/plan-details/bare-plan-audit-altitude/04-show-same-advisory-on-completeness.md
  status: done
- id: 5
  title: 'Document the policy and retire BACKLOG #290 into the historical record'
  intent: Keep the shipped audit contract discoverable while preserving the provenance
    and live follow-up links that remain useful.
  files:
  - CLAUDE.md
  - integrations/shared/DIRECTIVES.md
  - docs/AUDIT_FLOW.md
  - BACKLOG.md
  - docs/HISTORICAL_BACKLOG_DECISIONS.md
  complexity: medium
  change_type: non-code
  depends_on:
  - 1
  - 3
  - 4
  depends_on_notes:
    1: Supplies the final bare-stage property-versus-mechanism prompt contract.
    3: Supplies the landed convergence advisory and edit-drift composition.
    4: Supplies the landed completeness stderr presentation surface.
  detail: docs/implementation-plans/plan-details/bare-plan-audit-altitude/05-document-policy-retire-backlog-290.md
  status: done
---
# Bare Plan Audit Altitude

## Overview

This plan makes the bare-plan audit distinguish a selected design's required properties from implementation mechanisms that a later detail bundle must choose. The prompt preserves correctness findings for authority, scope, ordering, unsafe invariants, acceptance properties, contradictions, and uncovered grounded routes. It omits a pure unselected delivery-mechanism request from both bare correctness and completeness findings rather than merely lowering its severity. A delivery mechanism remains detail work unless the plan has already made it the externally observable compatibility, safety, ordering, ownership, or bypass contract whose absence contradicts a named acceptance property. A deterministic, recommendation-text-only advisory identifies likely misplaced bare-stage mechanism requests and composes with the existing `edit_drift` signal only for the same finding; it remains advice and does not affect enforcement. No blocking predicate gains a new non-deterministic input.

## Problem statement

The bare-stage blocking policy already demotes plan completeness, but a mechanism preference emitted as plan correctness can still block convergence even when it belongs to a detail decision. Because the audit prompt lacks an explicit correctness-versus-completeness altitude rule, the current gate can amplify the last implementation-shaped plan edit instead of testing the plan's design. The existing blocking policy must remain the sole enforcement surface.

## Architecture

Prompt guidance owns what the auditor generates. It keeps authority, scope, ordering, unsafe invariants, acceptance properties, contradictions, and uncovered grounded routes at plan-correctness altitude. It omits a pure unselected delivery-mechanism request at bare stage from both finding axes; it does not demote that request into a high-severity completeness finding. Serializers, parser internals, fixture shape, telemetry values, typed carriers, and dependency-rewrite choices stay in detail. The narrow exception is a mechanism the plan has already made its own externally observable compatibility, safety, ordering, ownership, or bypass contract: omitting that mechanism would contradict a named acceptance property. Naming an internal implementation preference alone does not create that exception.

The existing stage-aware blocking policy evaluates findings unchanged. A pure classifier uses only persisted recommendation text to label a likely mechanism request. It labels only text that asks for an internal delivery choice without textually declaring a compatibility, safety, ordering, ownership, or bypass contract; text that declares such a contract, or text too ambiguous to distinguish the two, remains unlabelled. The advisory consumes that label only for an open `plan-correctness` finding in the completed bare-stage pass; it does not render for detail-stage findings. One eligible finding renders a standalone advisory even when no prior compatible pass exists, and its output never enters blocking, continuation, failure, or exit-code decisions.

When `edit_drift`'s prior-apply-set match contains the same current eligible finding, the operator receives one combined advisory for that intersection instead of duplicate mechanism and edit-drift lines. An eligible finding outside that intersection retains its standalone advisory, and an `edit_drift` match outside it retains the existing drift advisory. Only completed run-grade history can produce this advice: run-grade convergence output and run-grade completeness stderr render it, while Jira-grade convergence and completeness remain suppressed. A legacy or otherwise ungraded saved pass cannot enable the new advice. `edit_drift` remains an apply-set comparison rather than durable causal provenance; #231 owns any future provenance engine.

## Input

The prompt and classifier consume persisted conceptual-finding text produced by the existing bare-plan audit. Advisory rendering consumes the final audit stage, source, and selected run grade; only completed run-grade history may reach the new advisory. Composition consumes the existing `edit_drift` prior-apply-set match for the same current finding. The text-only classifier must not infer a contract that the persisted finding does not state. That match remains an apply-set comparison and cannot establish causal provenance. The existing stage-aware blocking policy remains the authoritative enforcement contract and evaluates findings unchanged. The 2026-08-17 #291 replay supplies the stage-separated acceptance fixture.

## References

- [Prompting best practices — Claude Platform Docs](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices) — Covers explicit instructions, examples, prompt structure, and output constraints for refining the audit's property-versus-mechanism guidance.
- [Define success criteria and build evaluations — Claude Platform Docs](https://platform.claude.com/docs/en/test-and-evaluate/develop-tests) — Explains measurable success criteria and evaluation design for validating the prompt against the stage-separated replay cases.
- [re — Regular expression operations — Python 3.13 documentation](https://docs.python.org/3.13/library/re.html) — Documents Python's deterministic text-matching primitives for implementing the persisted-finding-text classifier.
- [dataclasses — Data Classes — Python 3.13 documentation](https://docs.python.org/3.13/library/dataclasses.html) — Documents frozen data classes and generated value semantics suitable for immutable advisory results.
- [How to parametrize fixtures and test functions — pytest documentation](https://docs.pytest.org/en/stable/how-to/parametrize.html) — Covers parametrized test matrices for property gaps, mechanism preferences, audit stages, and unchanged gate outcomes.
- [How to monkeypatch/mock modules and environments — pytest documentation](https://docs.pytest.org/en/stable/how-to/monkeypatch.html) — Explains scoped substitution of classifier and advisory seams when proving they cannot affect blocking or exit behavior.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

- A new gate, response field, model-assigned altitude label, automatic deferral, automatic apply, or exit-code change; the existing blocking policy remains the sole enforcement surface.
- Changes to existing blocking predicates, convergence continuation, failure behavior, audit-pass counts, arm clustering, or the detail-grounded bar; this work changes bare-altitude guidance and advisory rendering only.
- Jira-grade mechanism-advisory rendering in either convergence or completeness; both existing suppression boundaries remain unchanged.
- Widening the existing domain demotion or reviving an `unknown`-domain carve out; neither is part of this policy.
- A second provenance system or a causal claim from an apply-set match; `edit_drift` remains a comparison signal.
- Work owned by #91, #139, #231, #241, #248, or #262; those concerns remain separate.
- Create-path mechanics; the 2026-08-17 #291 replay supplies acceptance evidence without expanding this policy into that area.

## Risks

- Prompt guidance can still mislabel a mechanism preference as correctness. Preserve an operator advisory and record the measured miss rather than adding a gate-facing classifier.
- A classifier that is not stable for identical text, confuses an explicit contract with a mechanism, or guesses through ambiguous text is unsafe even as a signal. Keep the classifier pure, reproducible, conservative, and advisory-only.
- The policy can hide a real property gap if it confuses route coverage with route mechanics. Keep coverage of a declared outer-boundary, ownership, ordering, or acceptance property as a bare-plan correctness question.

## Testing

Prove that the prompt keeps genuine bare-plan contracts in correctness and leaves delivery mechanics to detail. At bare stage, a requested typed attachment, dependency ordering, or similar unselected internal delivery choice produces no finding in either axis even when its hypothetical severity is high; an uncovered named property route still produces correctness. A paired replay must show that a mechanism the plan has explicitly made its externally observable compatibility, safety, ordering, ownership, or bypass contract remains a bare correctness obligation. Prove that the deterministic classifier returns the same advisory label for identical persisted finding text across repeated calls; it labels a positive internal-mechanism request, rejects a named property or route-coverage request, rejects the same mechanism when its text declares an observable contract, and leaves ambiguous text unlabelled. Neither the classifier nor its composition with `edit_drift` may change any blocking, continuation, failure, or exit-code result.

Retain the #291 stage-separated replay as a canned fixture. Its named property is the refactor boundary rule: behavior-preserving refactor work selects a distinct observable execution boundary, and a repeated inner guard, accumulator, selector, rebuild, callback, or fixture remains with its observable owner unless it independently owns an observable handoff, ordering, or bypass contract. The combined route is `_render_from_prompt(..., omit_foundational_item=False)`, which must carry that property in both Stage 3 and `_PROPOSAL_FOUNDATIONAL_ITEM`. The split route is `_render_from_prompt(..., omit_foundational_item=True)` plus `_render_sweep_context()`, which must carry it in Stage 3 and the separate sweep context. At bare stage, absence from either route is a `plan-correctness` gap because the named property is uncovered; presence on both routes does not require a typed attachment, dependency ordering, or other delivery mechanism. Once a detail selects a delivery mechanism, the detail-grounded audit may require that selected mechanism.

Prove the presentation matrix at both run-grade convergence output and run-grade completeness stderr: an eligible finding receives the standalone advisory after one completed bare pass; a matching `edit_drift` finding receives one combined advisory; an eligible non-match and an `edit_drift` non-match retain their separate existing advice. Detail-stage findings receive no mechanism advisory. Jira-grade or ungraded saved passes cannot enable the advisory, and Jira-grade convergence and completeness retain their existing suppression.

**Per-step test strategy** (derived from each step's `change_type`):

- step 1 (feature) — tests covering the behavior this step changes; green before completion.
- step 2 (feature) — tests covering the behavior this step changes; green before completion.
- step 3 (feature) — tests covering the behavior this step changes; green before completion.
- step 4 (feature) — tests covering the behavior this step changes; green before completion.
- step 5 (non-code) — verification appropriate to the artifacts rather than unit tests.

## Acceptance criteria

- The bare audit distinguishes plan-level properties from implementation mechanisms without creating a new gate or changing a blocking predicate.
- An uncovered grounded route for a named property remains a bare-plan correctness finding, while a pure unselected delivery mechanism produces no bare finding in either axis, including at high or critical severity.
- A mechanism stays a bare correctness obligation only when the plan names it as the externally observable compatibility, safety, ordering, ownership, or bypass contract that satisfies a named acceptance property; an internal implementation preference remains deferred to detail.
- The deterministic advisory is stable for identical finding text, identifies a positive internal-mechanism request without identifying a named property, route obligation, textually declared observable contract, or ambiguous request, appears standalone after one eligible bare pass, and remains outside all blocking, continuation, failure, and exit-code decisions.
- When an eligible current finding is also an `edit_drift` match, only completed run-grade history can make run-grade convergence output and completeness stderr render one combined advisory; unrelated eligible and drift findings retain their own advice, detail-stage findings receive no mechanism advisory, and Jira-grade or ungraded history cannot enable the advisory in either convergence or completeness.
- The #291 replay retains its refactor-boundary property in the combined Stage 3 plus `_PROPOSAL_FOUNDATIONAL_ITEM` route and the split Stage 3 plus `_render_sweep_context()` route. An absent route is a bare `plan-correctness` gap; a present route leaves typed attachment, dependency ordering, or another delivery mechanism to detail, where the detail-grounded audit may require the selected mechanism.
- The resulting plan retires or updates BACKLOG #290 when implementation ships without removing provenance that active follow-up work needs.

## Deferred

- #231 owns durable apply-to-finding provenance.
- #241 owns its separate bare-prompt completeness-generation policy.
- #262 owns a reactive post-churn advisory.
- Run-time attribution is separate from this audit-policy work and is already
  satisfied by the current phase distinction.
