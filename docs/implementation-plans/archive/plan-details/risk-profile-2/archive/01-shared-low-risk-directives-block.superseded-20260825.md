> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 1 — Add a shared low-risk directives block with explicit ceremony authorization

## Summary

Create `plan_tool/plan_directives.py` as the single owner of low-risk procedure policy, with focused coverage in `tests/test_plan_directives.py`. Extend `plan_tool/scope_fence.py` so its guardrail selection works from supplied plan text as well as a live file path. Render policy only for an explicitly declared low tier, and authorize ceremony only through exact, eligible guardrail entries. On green, later detail and audit routes can consume one deterministic block without this step changing prompts, findings, or plan frontmatter.

## Table of Contents

- [Summary](#summary) — The module, boundary, and expected result.
- [Table of Contents](#table-of-contents) — Navigation for this detail.
- [Why](#why) — Why low-risk policy needs one owner.
- [Input](#input) — The risk declaration and guardrail contracts this step reads.
- [Files (creates vs edits)](#files-creates-vs-edits) — New policy module, tests, and documented ownership.
- [Implementation](#implementation) — Rendering, authorization, and preservation rules.
- [Tests](#tests) — Focused contract coverage.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Relevant model, Markdown, and test references.
- [Applicable guardrails](#applicable-guardrails) — Plan boundaries for this step.
- [Deferred](#deferred) — Work owned by later steps.

## Why

`plan_tool/schema.py:RiskProfile` stores a declared tier, while `plan_tool/scope_fence.py:render_scope_fence` carries plan intent and guardrails. No shared policy currently defines how a declared-low plan limits added procedure or recognizes an intentional exception. Establish that contract before later detail-writing and audit routes consume it, so they cannot interpret the same guardrail differently.

## Input

- **Risk declaration:** Read the `risk_profile` and `risk_profile_rationale` fields of `plan_tool/schema.py:Plan`. An omitted declaration remains legacy standard behavior; do not treat `Plan.effective_risk_profile` as evidence of an explicit low declaration.

- **Authorization source:** Reuse `plan_tool/scope_fence.py:GUARDRAIL_BODY_SECTIONS`, `extract_h2_sections`, and the existing frontmatter-safe guardrail selection. Only the eligible guardrail sections can authorize ceremony; intent and `## Out of scope` remain scope context.

- **Captured audit input:** Support `render_low_risk_directives(plan, plan_path, *, plan_body=None)` for later snapshot-based audit callers. When supplied, `plan_body` is the sole authorization source for that render.

## Files (creates vs edits)

- **New files:**
  - `plan_tool/plan_directives.py` — Define the low-risk policy vocabulary, authorization selection, and shared renderer.
  - `tests/test_plan_directives.py` — Cover tier gating, authorization syntax, deterministic output, captured-body behavior, and import boundaries.

- **Existing files (edits only):**
  - `docs/ARCHITECTURE.md` — Add a `## Plan directives` section that assigns policy ownership and distinguishes it from `plan_tool/scope_fence.py`.
  - `plan_tool/scope_fence.py` — Expose its existing guardrail selection over supplied text while retaining `extract_plan_guardrails` as the live-path wrapper.

## Implementation

- **Foundational logic:** Render one shared directives block only when `Plan.risk_profile is RiskProfile.LOW`; every other declaration state returns `""`.

- **Keep one policy vocabulary.** In `plan_tool/plan_directives.py`, own the ordered canonical identifiers `credential-custody`, `confirmation-gate`, `deploy-ordering`, and `rollback-procedure`, with their human-readable meanings. Own the `tier-challenge` token, its fixed `standard` minimum, and the low-risk safety floors in the same module.

- **Expose one renderer.** Provide `plan_tool/plan_directives.py:render_low_risk_directives(plan, plan_path, *, plan_body=None)`. Its nonempty output must state the declared tier and rationale, the ceremony rule, authorized exceptions, retained safety floors, and the `tier-challenge` direction. Keep prompt rendering, model calls, finding parsing, and frontmatter mutation outside this module.

- **Authorize exact entries only.** Accept only a standalone `Required ceremony: <id>` entry under a heading named by `plan_tool/scope_fence.py:GUARDRAIL_BODY_SECTIONS`, where `<id>` is exactly one canonical identifier. Ignore aliases, combined values, unknown identifiers, descriptive prose, and requirement-shaped text outside those headings.

- **Treat duplicate valid entries predictably.** Deduplicate individually valid authorization entries and render them in canonical policy order, not source-file order. A duplicate line does not widen the authorization set.

- **Keep the live and captured paths aligned.** Add a text-based guardrail selector in `plan_tool/scope_fence.py` that preserves `_strip_frontmatter`, `extract_h2_sections`, placeholder handling, and heading order. Keep `extract_plan_guardrails(plan_path)` as the file-reading wrapper over that shared selection path; do not create a second plan-body parser in `plan_tool/plan_directives.py`.

- **Do not infer an exception.** Mentions in `Plan.risk_profile_rationale`, plan or step intent, overview prose, `## Out of scope`, audit output, or non-required guardrail prose must never authorize ceremony.

- **Keep the safety floor explicit.** Low risk limits unlisted ceremony only. The directives block must retain declared scope, file and symbol grounding, tests, and evidence-based correctness review; evidence that refutes the declaration belongs on the shared `tier-challenge` route.

- **Keep imports one-way.** `plan_tool/plan_directives.py` may depend on the schema and scope-fence contracts it reads, but must not import authoring, launcher, review, or prompt modules. Later steps consume this policy module rather than duplicating its vocabulary or scraping rendered Markdown.

- **Document ownership.** In `docs/ARCHITECTURE.md`, describe `plan_tool/plan_directives.py` as a policy renderer that does not author detail files or emit, apply, or resolve audit findings.

## Tests

### Tests for this step

- `tests/test_plan_directives.py::test_declared_low_renders_rationale_policy_and_safety_floors` — A declared-low plan renders its rationale, every ceremony class, the `tier-challenge` standard minimum, and the retained scrutiny rules.

- `tests/test_plan_directives.py::test_required_eligible_guardrail_authorizes_matching_ceremony` — A canonical required entry under each eligible guardrail heading authorizes only its matching ceremony class.

- `tests/test_plan_directives.py::test_required_ceremony_syntax_rejects_aliases_combined_and_unknown_values` — Noncanonical or multi-value forms fail closed and never enter the authorization list.

- `tests/test_plan_directives.py::test_authorized_ceremonies_are_deduplicated_in_policy_order` — Repeated and reordered valid entries produce one stable, canonically ordered authorization list.

- `tests/test_plan_directives.py::test_nonrequired_and_outside_guardrail_mentions_do_not_authorize_ceremony` — Intent, rationale, overview, `## Out of scope`, and descriptive guardrail prose cannot create an exception.

- `tests/test_plan_directives.py::test_standard_high_and_undeclared_profiles_render_no_directives` — Standard, high, and field-absent plans return exactly an empty block.

- `tests/test_plan_directives.py::test_captured_body_determines_authorization_without_live_path_mix` — A supplied body remains authoritative after the file changes, while the no-body path still reads current guardrails.

- `tests/test_plan_directives.py::test_guardrail_text_selector_matches_live_path_wrapper` — The supplied-text selector preserves the existing path-based output, including frontmatter and placeholder handling.

- `tests/test_plan_directives.py::test_plan_directives_avoids_authoring_and_audit_imports` — The policy module does not add imports from authoring, launcher, review, or prompt layers.

Every listed test, plus `uv run pytest tests/test_plan_directives.py tests/test_scope_fence.py -q`, must be green before this step is complete.

## Acceptance criteria

- An explicitly low plan produces one shared block containing its rationale, ceremony policy, safety floors, `tier-challenge`, and the `standard` minimum.

- Only canonical `Required ceremony: <id>` entries under eligible guardrail headings authorize ceremony.

- Duplicate canonical entries produce one authorization list in the policy vocabulary’s fixed order.

- Ordinary prose, intent, rationale, `## Out of scope`, and non-required wording cannot authorize ceremony.

- Standard, high, and undeclared plans return no directives.

- A supplied plan body never mixes its authorization result with later live-file content.

- `plan_tool/scope_fence.py:extract_plan_guardrails` retains its path-based behavior while sharing selection logic with the supplied-text path.

- `docs/ARCHITECTURE.md` identifies `plan_tool/plan_directives.py` as the policy owner and distinguishes it from `plan_tool/scope_fence.py`.

- `uv run pytest tests/test_plan_directives.py tests/test_scope_fence.py -q` passes.

## References

- [Models | Pydantic Documentation](https://docs.pydantic.dev/latest/concepts/models/) — Review validated model fields and explicit-field tracking used by `plan_tool/schema.py:Plan`.

- [CommonMark Specification 0.31.2](https://spec.commonmark.org/0.31.2/) — Review heading and list rules embodied by `plan_tool/scope_fence.py:extract_h2_sections`.

- [How to parametrize fixtures and test functions](https://docs.pytest.org/en/stable/how-to/parametrize.html) — Cover non-low profile regressions without repeating setup.

## Applicable guardrails

- **The plan’s “## Plan intent”** — Keep low-risk work proportionate while preserving the evidence-backed route that challenges an unsuitable tier.

- **The plan’s “## Step intent”** — Centralize the tier, rationale, authorized exceptions, and safety floors without wiring a consuming route.

- **The plan’s “## Out of scope”** — Leave risk-profile declaration, generic correctness policy, execution surfaces, and retroactive re-audits unchanged.

- **The plan’s scope contract, allowed behavior changes** — Limit this step to the shared tier-conditioned policy contract; plans without an explicit declaration retain current behavior.

- **The plan’s scope contract, allowed reorganization** — Keep the `plan_tool/scope_fence.py` change limited to the selector needed for captured-body support; do not broaden it into cleanup.

## Deferred

- Detail authoring, quality review, and rewrite prompt integration — Step 2 consumes the shared directives block.

- Finding parsing, blocking, reporting, and manual resolution — Steps 3 and 4 consume the shared `tier-challenge` vocabulary.

- Additional declarative policies — Require a separate scoped decision; this module does not authorize new policy behavior.
