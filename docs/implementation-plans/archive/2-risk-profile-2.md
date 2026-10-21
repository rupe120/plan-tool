> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

---
title: Risk Profile 2
intent: Make an explicitly declared plan risk profile visible as advisory context
  to run-grade detail authoring and review, without turning it into a policy gate.
status: completed
priority: medium
test_command: uv run pytest tests/ -q -n auto
enforce_step_tests: true
source_seed: plan-seeds/archive/risk-profile-2-honoring.replaced.md
steps:
- id: 1
  title: Render one advisory risk context for explicit declarations
  intent: Give detail authors and reviewers a concise, consistent statement of the
    declared tier and rationale while retaining their normal grounding and test duties.
  files:
  - plan_tool/detail.py
  - plan_tool/prompts/detail.md
  - plan_tool/prompts/detail-quality.md
  - tests/test_detail.py
  complexity: low
  change_type: feature
  detail: docs/implementation-plans/plan-details/risk-profile-2/01-render-one-advisory-risk-context.md
  status: done
- id: 2
  title: Supply advisory risk context to every run-grade detail prompt
  intent: Keep initial authoring, quality review, and a detail-loop rewrite equally
    informed, including after an accepted rewrite changes the declaration, without
    changing audit, reconciliation, or Jira behavior.
  files:
  - plan_tool/detail.py
  - plan_tool/launcher.py
  - plan_tool/prompts/apply-finding.md
  - tests/test_detail.py
  - tests/test_launcher.py
  complexity: medium
  change_type: feature
  depends_on:
  - 1
  depends_on_notes:
    1: Provides the single advisory context renderer used by each run-grade detail
      prompt.
  detail: docs/implementation-plans/plan-details/risk-profile-2/02-supply-advisory-risk-context-every-run.md
  status: done
---
# Risk Profile 2

## Problem statement

`PLAN_FORMAT.md` defines the paired `risk_profile` and `risk_profile_rationale`
declaration, but run-grade detail authoring and review prompts do not receive that
explicit context. Authors and reviewers therefore cannot see the declared tier and
rationale when choosing procedural detail, leaving initial authoring, quality review,
and detail-loop rewrites without a consistent advisory risk context.

## Overview

An explicit `risk_profile` and its rationale help a detail author choose an appropriate
level of procedure. This plan places that information in the run-grade detail prompts
where the procedure is written and reviewed. It remains advisory: normal file and
symbol grounding, test requirements, and safety review still apply, and a reviewer may
explain why the declared tier does not fit the work.

The profile does not authorize or forbid a category of prose. It does not alter the
completeness audit, its response grammar, recommendation routing, blocking, or any
other pipeline stage. Jira-grade companion detail remains outside this plan.

## Architecture

### One advisory context, rendered only for an explicit declaration

`plan_tool/detail.py` owns a small renderer that receives the parsed plan and returns
either an empty string or a concise block containing the declared tier, rationale, and
four instructions: keep the work proportionate, preserve grounded requirements, tests,
and safety review, and explain a material mismatch rather than silently overriding the
declaration. It does not parse guardrails, classify ceremony, or return machine-readable
policy.

The context is an input to `detail` prompts, not a durable control state. Each initial
authoring or quality-review invocation reads the current parsed plan. Both prompts in a
quality-loop apply share the context captured for that attempt; after an accepted apply,
later authoring and review observe a changed declaration. This ordering applies between
attempts only; it never replaces the captured context inside the accepted apply. A
rewrite may retain a valid profile–rationale update through its ordinary plan-edit
contract, and this plan adds neither a special rejection nor a frontmatter immutability
rule.

### Prompt boundary

Initial authoring, quality review, and the detail-loop call to `apply_finding` receive
the same optional context. The shared `apply_finding` default remains empty, so create,
completeness-apply, reconcile, and every non-detail caller retain their current prompts.
Its empty default leaves primary and follow-up prompts byte-identical for every
non-detail caller. For plans without an explicit declaration, each affected prompt
remains byte-identical.

## Steps

The machine-readable `steps:` block in the YAML frontmatter defines the ordered
implementation steps and remains authoritative.

## Scope contract (inherited verbatim from BACKLOG.md #182)

- **Outcome:** an explicitly declared `risk_profile` and its rationale appear as
  advisory context in initial run-grade detail authoring, quality review, and the
  detail-loop rewrite. The context asks authors and reviewers to keep procedure
  proportionate while preserving grounded requirements, tests, and safety review, and
  to explain a material tier mismatch rather than silently overriding it. It neither
  authorizes nor forbids a prose category, writes or validates frontmatter, changes
  completeness audit output or routing, nor changes Jira-grade companion detail. A valid
  profile–rationale update accepted through the existing detail loop remains its ordinary
  input and is visible to later detail authoring and review. Plans without an explicit
  declaration retain byte-identical affected prompts; non-detail callers of
  `apply_finding` retain its empty-context behavior. Both prompts in one detail-loop
  apply use their attempt's captured context.
- **In scope:** `plan_tool/detail.py`, `plan_tool/launcher.py`,
  `plan_tool/prompts/detail.md`, `plan_tool/prompts/detail-quality.md`,
  `plan_tool/prompts/apply-finding.md`, and focused detail/launcher prompt tests.
- **Out of scope / Non-goals:** risk-profile classification and persistence (#181);
  closed ceremony vocabularies or authorizations; semantic validation of generated
  prose; tier-challenge findings; completeness-audit prompt, parser, report, or
  blocking changes; create, completeness-apply, reconcile, run, or Jira behavior;
  and retroactive detail rewrites.
- **Allowed behavior changes:** optional advisory context in the three named run-grade
  detail prompt routes for an explicit declaration, including later detail contexts
  observing a valid declaration-pair update accepted by the existing detail loop. No
  change to non-detail caller behavior and no new frontmatter mutation or validation.
- **Allowed reorganization:** a local detail-context renderer only.
- **Verification:** focused tests prove the exact context reaches initial authoring,
  quality review, and both prompts in one opted-in detail-loop apply; an absent
  declaration leaves each prompt byte-identical; later authoring and review invocations
  observe a valid declaration-pair update accepted by the existing detail loop; and
  every non-detail `apply_finding` caller remains byte-identical; `uv run pytest
  tests/ -q -n auto` passes.
- **Stop / defer:** revisit enforcement only with evidence that advisory context and
  human review fail to preserve a necessary invariant; design that work as a separate
  cross-pipeline proposal rather than extending this plan.

## Out of scope

- Risk-profile classification and persistence remain in #181 because this plan only
  renders an explicit declaration.
- Closed ceremony vocabularies, authorizations, semantic validation of generated
  prose, and tier-challenge findings remain excluded so advisory context does not
  become policy enforcement.
- Completeness-audit prompts, parsing, reports, routing, and blocking remain unchanged
  because the work affects only run-grade detail prompts.
- Create, completeness-apply, reconcile, run, Jira, and retroactive detail rewrites
  remain outside this plan to keep the prompt-context change local.

## Deferred

- None. Risk-profile enforcement is deliberately excluded; reopening it requires a new,
  evidence-backed cross-pipeline proposal.

## Risks

- **Failure shape:** optional context changes an undeclared-plan or non-detail prompt.
  **Severity:** medium. **Mitigation:** retain the empty shared default and prove
  byte-identical prompts and empty non-detail callers. **Unresolved gap:** prompt
  coverage must include every named route.
- **Failure shape:** authors or reviewers treat the declared tier as a policy gate.
  **Severity:** medium. **Mitigation:** state that context remains advisory and retain
  grounding, test, and safety-review duties. **Unresolved gap:** human judgment can
  still misread advisory wording.

## Test strategy

- Unit-test the renderer for valid explicit low, standard, and high profile–rationale
  pairs and the omitted legacy pair.
- Test every named run-grade detail prompt route with a recording invoker.
- Characterize the empty-context path before wiring the optional value and keep that
  byte-for-byte output for a plan with no explicit declaration and every non-detail
  caller.
- Test an accepted declaration-changing apply followed by both later authoring and
  review, while retaining the captured context in both prompts of that original apply.
- Run the focused detail and launcher tests before the full suite.

## Testing

- Unit tests cover valid explicit profile–rationale pairs, the omitted legacy pair,
  and the full advisory instruction including grounding, tests, and safety review.
- Prompt tests prove initial authoring and quality review receive the same context, an
  absent declaration retains byte-identical prompts, and every non-detail apply caller
  remains byte-identical.
- One detail-loop integration test proves an opted-in rewrite passes the same context to
  both prompts in its apply attempt, then refreshes the declaration before later
  authoring and review.
- Run focused detail and launcher tests before `uv run pytest tests/ -q -n auto`.

## Acceptance criteria

- An explicit risk profile and rationale are visible to each named detail author or
  reviewer as advisory context.
- The context retains grounding, tests, and safety review, and asks for an explanation
  of a material tier mismatch.
- Both prompts in one detail-loop apply use the attempt's captured context, and an
  accepted declaration change is visible to later authoring and review.
- No custom ceremony vocabulary, authorization parser, response marker, or finding kind
  is introduced.
- Completeness audit and Jira-grade companion-detail behavior are unchanged.
- A plan without an explicit declaration and every non-detail apply caller keep their
  current prompt bytes.

## References

- [Plan frontmatter contract — the optional, complete
  `risk_profile`–`risk_profile_rationale` pair is the input to this plan.
- [Detail flow](../how-to/pipeline/detail.md) — Initial authoring, quality review, and detail-loop
  rewrite are the only affected route family.
