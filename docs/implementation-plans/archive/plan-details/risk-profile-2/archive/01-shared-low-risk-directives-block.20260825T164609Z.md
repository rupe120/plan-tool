> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 1 — Add a shared low-risk directives block with explicit ceremony authorization

## Summary

Create `plan_tool/plan_directives.py` as the shared owner of low-risk procedure policy, with focused coverage in `tests/test_plan_directives.py`. Extend `plan_tool/scope_fence.py` so its existing guardrail selection works from supplied plan text as well as a live file path. The key decision is that only an explicit `low` declaration renders policy, and only explicit required guardrails authorize a ceremony exception. On green, later detail and audit routes can consume one deterministic block without this step changing any prompt or audit behavior.

## Table of Contents

- [Summary](#summary) — The module, boundary, and expected result.
- [Table of Contents](#table-of-contents) — Navigation for this detail.
- [Why](#why) — Why low-risk policy needs one owner.
- [Input](#input) — The existing risk declaration and guardrail contracts.
- [Files (creates vs edits)](#files-creates-vs-edits) — New policy module, tests, and documented ownership.
- [Implementation](#implementation) — Rendering, authorization, and preservation rules.
- [Tests](#tests) — Focused contract coverage.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Relevant API and test references.
- [Applicable guardrails](#applicable-guardrails) — Plan boundaries for this step.
- [Deferred](#deferred) — Consumers and policy work owned later.

## Why

`plan_tool/schema.py:RiskProfile` preserves a declared tier, while `plan_tool/scope_fence.py:render_scope_fence` carries intent and guardrails. No shared policy currently says how a declared-low plan limits added procedure or how an explicit exception is recognized. Define that contract before callers consume it so detail writing, rewrites, and audits cannot each apply a different ceremony rule.

## Input

- **Risk declaration:** Read the `risk_profile` and `risk_profile_rationale` fields of `plan_tool/schema.py:Plan`. Treat an absent declaration as legacy standard behavior, not as low risk.
- **Authorization source:** Reuse `plan_tool/scope_fence.py:GUARDRAIL_BODY_SECTIONS` and its guardrail extraction behavior. Within those sections, only `Required ceremony: <id>` authorizes a ceremony, using one of the module-owned canonical identifiers; intent and `Out of scope` remain scope context, not authorization.
- **Captured audit input:** Support a supplied plan body for later snapshot-based audit callers. A supplied body must be the sole authorization source for that render.

## Files (creates vs edits)

- **New files:**
  - `plan_tool/plan_directives.py` — Define the low-risk policy vocabulary and render its shared block.
  - `tests/test_plan_directives.py` — Test tier gating, authorization, captured-body behavior, and preserved safety floors.

- **Existing files (edits only):**
  - `docs/ARCHITECTURE.md` — Add a `## Plan directives` section that assigns policy ownership and distinguishes it from the scope-fence renderer.
  - `plan_tool/scope_fence.py` — Expose current guardrail selection for supplied text and retain the live-path wrapper.

## Implementation

- **Foundational logic:** Render one directives block only when `Plan.risk_profile` is the `LOW` member of `plan_tool/schema.py:RiskProfile`; every other declaration state returns `""`.

- **Keep one policy vocabulary.** In `plan_tool/plan_directives.py`, own the canonical `credential-custody`, `confirmation-gate`, `deploy-ordering`, and `rollback-procedure` identifiers, their human-readable meanings, the `tier-challenge` finding token, its fixed `standard` minimum, and the low-risk safety floors. The classes cover credential or export procedure, confirmation gates, deployment ordering, and rollback beyond version control.

- **Expose one renderer.** Provide `plan_tool/plan_directives.py:render_low_risk_directives(plan, plan_path, *, plan_body=None)`. Its nonempty result must contain the declared tier and rationale, the ceremony rule, authorized exceptions, retained safety floors, and the `tier-challenge` direction. Keep prompt rendering, model calls, finding parsing, and frontmatter mutation outside this module.

- **Preserve non-low behavior.** Standard, high, and undeclared plans must render no tier-specific text. Do not use `Plan.effective_risk_profile` as the render gate, infer low risk from prose, or treat a missing declaration as authorization.

- **Authorize positively and narrowly.** In an eligible guardrail section, recognize only a standalone `Required ceremony: <id>` entry with exactly one lowercase canonical identifier after the colon; whitespace around the value is harmless, but an unknown, repeated, combined, or prose-only value is non-authorizing. Keep the entry parser in this shared policy path so detail writers and audit normalization cannot interpret one guardrail differently. Mentions in rationale, intent, overview, `Out of scope`, audit output, or non-required guardrail prose must not authorize it.

- **Make output deterministic.** Deduplicate authorized classes and render them in the policy vocabulary’s canonical order, rather than the order they appear in a plan. An unlisted class remains forbidden for declared-low work.

- **Reuse scope-fence parsing.** Add a supplied-text guardrail selector in `plan_tool/scope_fence.py` and have `extract_plan_guardrails` remain the live-path wrapper around the same selection logic. Preserve its frontmatter handling and its existing rendered output; do not create a second authorization parser in `plan_tool/plan_directives.py`.

- **Keep the safety floor clear.** The directives block limits unlisted ceremony only. It must retain declared scope, file and symbol grounding, tests, and evidence-based correctness review. Evidence that the tier is wrong must route to `tier-challenge`, not weaken those checks.

- **Document ownership.** Describe `plan_tool/plan_directives.py` in `docs/ARCHITECTURE.md` as a policy renderer that neither authors detail files nor emits, applies, or resolves findings.

## Tests

### Tests for this step

- `test_declared_low_renders_rationale_policy_and_safety_floors` — A declared-low plan renders its rationale, every ceremony class, the `tier-challenge` standard minimum, and the retained scrutiny rules.
- `test_required_eligible_guardrail_authorizes_matching_ceremony` — A recognized class becomes an exception only when eligible guardrail prose explicitly requires it.
- `test_required_ceremony_syntax_accepts_only_one_canonical_identifier` — Each canonical entry authorizes its one class, while aliases, combinations, unknown values, and ordinary prose fail closed.
- `test_nonrequired_and_outside_guardrail_mentions_do_not_authorize_ceremony` — Negated, descriptive, or ordinary-plan mentions never create an exception.
- `test_authorized_ceremonies_are_unique_and_follow_policy_order` — Repeated or reordered guardrails yield one deterministic authorization list.
- `test_standard_high_and_undeclared_profiles_render_no_directives` — Standard, high, and field-absent plans return an empty block.
- `test_captured_body_determines_authorization_without_live_path_mix` — A supplied body remains authoritative after the on-disk plan changes, while the no-body path still reads live guardrails.
- `test_guardrail_text_selector_matches_live_path_wrapper` — The new `plan_tool/scope_fence.py` supplied-text path preserves the current live-path rendering contract.

Every test in `tests/test_plan_directives.py` must be green before this step is complete.

## Acceptance criteria

- A plan explicitly declared `low` produces one shared block containing its rationale, ceremony policy, safety floors, `tier-challenge`, and `standard` minimum.
- Only explicitly required ceremony classes from the scope-fence authorization headings appear as exceptions.
- An authorization has the exact `Required ceremony: <id>` form and every reader uses the one shared identifier mapping.
- Ordinary prose, intent, rationale, `Out of scope`, and non-required wording cannot authorize ceremony.
- Standard, high, and undeclared plans return no directives.
- A supplied plan body never mixes its authorization result with later live-file content.
- `plan_tool/scope_fence.py:extract_plan_guardrails` retains its current path-based output while reusing the supplied-text selection logic.
- `docs/ARCHITECTURE.md` identifies `plan_tool/plan_directives.py` as the policy owner and distinguishes it from `plan_tool/scope_fence.py`.
- `uv run pytest tests/test_plan_directives.py tests/test_scope_fence.py -q` passes.

## References

- [Models | Pydantic Documentation](https://docs.pydantic.dev/latest/concepts/models/) — Review validated model fields and `model_fields_set` behavior used by `plan_tool/schema.py:Plan`.
- [CommonMark Specification 0.31.2](https://spec.commonmark.org/0.31.2/) — Refer to heading rules embodied by `plan_tool/scope_fence.py:extract_h2_sections`.
- [How to parametrize fixtures and test functions](https://docs.pytest.org/en/stable/how-to/parametrize.html) — Use parametrization for the non-low rendering regressions.

## Applicable guardrails

- **The plan’s “## Plan intent”** — Keep low-risk work proportionate while preserving the evidence-backed route that challenges an unsuitable tier.
- **The plan’s “## Step intent”** — Centralize the tier, rationale, exceptions, and safety floors without wiring any consumer route.
- **The plan’s “## Out of scope”** — Leave declaration authoring and the excluded workflow surfaces unchanged.

## Deferred

- Detail authoring, quality review, and rewrite prompt integration — Step 2 consumes the shared directives block.
- Finding parsing, blocking, reporting, and manual resolution — Steps 3 and 4 consume the shared `tier-challenge` vocabulary.
- Additional declarative policies — Require a separate scoped decision; this module’s generic shape does not authorize new policy behavior.
