> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 1 — Add a shared low-risk directives block with explicit ceremony authorization

## Summary

Create `plan_tool/plan_directives.py` as the single owner of the low-risk procedure policy and add focused coverage in `tests/test_plan_directives.py`. The module will render a directive block from an explicitly declared low risk profile, its rationale, and only explicitly required ceremony exceptions from the allowed guardrail sections. It will also own the complete ceremony vocabulary and the shared `tier-challenge` token and standard minimum. On green, later detail-writing and audit steps can consume one deterministic policy block without changing any prompt or audit route in this step.

## Table of Contents

- [Summary](#summary) — Reviewer overview of the new policy module and result.
- [Table of Contents](#table-of-contents) — Navigation for this detail.
- [Why](#why) — Why the policy needs one owner before callers use it.
- [Input](#input) — Existing plan declaration and scope-fence contracts this step reads.
- [Files (creates vs edits)](#files-creates-vs-edits) — New module, tests, and architecture update.
- [Implementation](#implementation) — Required policy, authorization, and compatibility behavior.
- [Tests](#tests) — Focused unit coverage for the shared contract.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Relevant upstream documentation.
- [Applicable guardrails](#applicable-guardrails) — Boundaries inherited from the plan.
- [Deferred](#deferred) — Later consumers and deliberately excluded work.

## Why

The plan frontmatter preserves a declared tier and rationale, while `plan_tool/schema.py:RiskProfile` defines the closed tier vocabulary and `plan_tool/scope_fence.py:render_scope_fence` carries intent and guardrails. No shared policy currently defines how low risk limits invented procedure. Without one owner, the initial detail writer, quality rewrite, and audit can each interpret ceremony exceptions differently. Establish the contract before wiring callers so every later route uses the same tier, rationale, safety floors, authorization rule, ceremony vocabulary, and `tier-challenge` identity.

## Input

- **Risk declaration:** Read the plan's validated `risk_profile` and `risk_profile_rationale` frontmatter pair; `plan_tool/schema.py:RiskProfile` supplies the closed tier vocabulary and the declaration's one-line rationale remains the operator-owned explanation.
- **Legacy behavior:** Respect the existing effective-standard behavior for an omitted declaration; the shared renderer must still return no tier-specific block unless the stored declaration is explicitly low.
- **Authorization source:** Use `plan_tool/scope_fence.py:extract_plan_guardrails`, its text-backed companion, `extract_h2_sections`, and `GUARDRAIL_BODY_SECTIONS` to identify the three eligible guardrail sections. `render_scope_fence` also carries intent and `Out of scope`, but neither authorizes ceremony.

## Files (creates vs edits)

- **New files:**
  - `plan_tool/plan_directives.py` — Define and render the shared low-risk policy block.
  - `tests/test_plan_directives.py` — Cover profile gating, authorization selection, vocabulary, and safety floors.

- **Existing files (edits only):**
  - `docs/ARCHITECTURE.md` — Add a `## Plan directives` section describing the module’s ownership, inputs, low-only rendering rule, and relationship to `plan_tool/scope_fence.py:render_scope_fence`.
  - `plan_tool/scope_fence.py` — Expose the existing guardrail-section selection over supplied plan text as well as through its live-path wrapper.

## Implementation

- **Foundational logic:** Add one low-risk directives renderer that returns a policy block only for a declared `low` tier and otherwise returns an empty string.

- **Own the complete vocabulary in `plan_tool/plan_directives.py`.** Define clear module-level policy values for the ceremony classes, the `tier-challenge` finding kind, its fixed `standard` minimum, and the low-risk safety floors. The four ceremony classes are export or credential-custody procedure, confirmation gate, deploy-ordering rule, and rollback procedure beyond version control.

- **Expose one shared renderer.** Add `render_low_risk_directives(plan, plan_path, *, plan_body=None)` as the public entry point. It should return one self-contained Markdown block containing the declared low tier, its rationale, the complete ceremony policy, the safety floors, the authorized exceptions, and the `tier-challenge` rule. Without `plan_body`, it uses the live-path wrapper for detail authoring; with a captured body, it uses the same scope-fence selector over that body. Keep prompt-template substitution and model calls out of this module; steps 2 through 4 own the consuming prompt and finding routes.

- **Render only for declared low risk.** A standard, high, or field-absent plan must receive `""`, preserving existing callers’ prompt text until they deliberately opt into the new block. Do not infer a low tier from plan prose or use a missing declaration as authorization to add tier-specific policy.

- **Make authorization finite and positive.** Derive candidates from `plan_tool/scope_fence.py:extract_plan_guardrails` or its supplied-body companion, then retain only content under headings named by `GUARDRAIL_BODY_SECTIONS`. Authorize a ceremony class only when eligible guardrail prose both names that class and requires it. A mention in plan intent, rationale, overview, `Out of scope`, an audit finding, or historical prose must not become an exception.

- **Keep the safety floor explicit.** The low tier limits unlisted ceremony only. The rendered policy must preserve declared scope, file and symbol grounding, tests, and evidence-based correctness scrutiny. It must say that a contradiction of the low declaration belongs on the shared `tier-challenge` route rather than silently weakening those checks.

- **Reuse the scope-fence contract.** Do not reimplement frontmatter stripping or plan-body extraction in the new module. The scope-fence selector is shared by the live wrapper and supplied-body helper, so `plan_tool/plan_directives.py` has no second authorization parser; `GUARDRAIL_BODY_SECTIONS` remains the source for which sections may authorize an exception.

- **Document the boundary.** In `docs/ARCHITECTURE.md`, describe `plan_tool/plan_directives.py` as the policy owner and make clear that it does not itself author details, rewrite them, emit audit findings, or change plan frontmatter.

## Tests

### Tests for this step

- `test_low_risk_directives_render_rationale_ceremony_policy_and_safety_floors` — A declared low plan renders its rationale, all four ceremony classes, the fixed `tier-challenge`/`standard` rule, and the preserved safety floors.
- `test_explicit_required_allowed_guardrail_authorizes_matching_ceremony` — A recognized ceremony is listed as authorized only when eligible guardrail prose explicitly requires it.
- `test_overview_out_of_scope_and_nonrequired_mentions_do_not_authorize_ceremony` — Similar text outside the allowed guardrail headings, or a non-required mention within one, never creates an exception.
- `test_standard_high_and_undeclared_profiles_render_no_directives` — Parameterized standard, high, and field-absent plans all return an empty block.
- `test_shared_policy_vocabulary_covers_every_ceremony_class_once` — The renderer’s output derives from the module-owned vocabulary, with no separate subset for authorization or challenge wording.
- `test_low_risk_directives_use_the_supplied_captured_body` — After a captured plan body authorizes a ceremony, a later live guardrail edit cannot change that supplied-body result; the no-body detail-authoring path continues to read the live plan.

Every test in `tests/test_plan_directives.py` must be green before this step is complete.

## Acceptance criteria

- A declared-low `Plan` produces one directive block containing its rationale, the four ceremony classes, the `tier-challenge` token, and the `standard` minimum.
- Only explicitly required ceremony classes from `Scope guardrails`, `Audit guardrails`, or `Expected placement` appear in the authorization list.
- A similar requirement in `Out of scope`, intent, rationale, or ordinary plan prose does not authorize ceremony.
- Standard, high, and field-absent plans return no directives.
- A supplied captured plan body produces the same authorization selection as at capture and is never mixed with a later live guardrail edit.
- `docs/ARCHITECTURE.md` names `plan_tool/plan_directives.py` as the single policy owner and identifies `plan_tool/scope_fence.py:extract_plan_guardrails` as its source for authorization text.
- `uv run pytest tests/test_plan_directives.py -q` passes.

## References

- [Models | Pydantic Documentation](https://docs.pydantic.dev/latest/concepts/models/) — Review model fields and validated optional declarations used by `plan_tool/schema.py:Plan`.
- [How to parametrize fixtures and test functions](https://docs.pytest.org/en/stable/how-to/parametrize.html) — Use parametrization for standard, high, and undeclared profile regressions.
- [CommonMark Specification 0.31.2](https://spec.commonmark.org/) — Refer to the heading rules already embodied by `plan_tool/scope_fence.py:extract_h2_sections`.

## Applicable guardrails

- **The plan’s “Plan intent”** — Keep this module focused on proportionate low-risk procedure and the evidence-based route that challenges a bad declaration.
- **The plan’s “Step intent”** — Keep the tier, rationale, authorized exceptions, and safety floors in one reusable contract; do not wire prompt or report consumers here.
- **The plan’s “Out of scope”** — Do not change the classifier, proposal flow, frontmatter schema, existing execution surfaces, or retroactively audit plans.

## Deferred

- Prompt and quality-loop integration — Step 2 consumes the shared block in detail-writing routes.
- Finding, report, blocking, and manual-resolution behavior — Steps 3 and 4 consume the shared `tier-challenge` vocabulary.
- Additional shared directives such as `enforce_step_tests` — The plan’s `## Deferred` section keeps that broader policy work outside this step.
