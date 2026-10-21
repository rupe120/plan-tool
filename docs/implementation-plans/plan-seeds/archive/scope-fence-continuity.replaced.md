> **Replaced**: this file has been superseded by `docs/implementation-plans/2-scope-fence-continuity.md`.
> Preserved here for history; do not edit.

# Guardrail continuity through plan creation

## Outcome

When an input seed contains `Scope guardrails`, `Audit guardrails`, or
`Expected placement`, each supplied section survives distillation, body
synthesis, and final plan rendering under its own H2 heading. If a supplied
heading is lost at either lossy boundary, create emits a deterministic,
exact-heading finding.

## In scope

- `plan_tool/create.py` optional-section parsing/rendering and deterministic
  preservation checks.
- `plan_tool/prompts/distill-seed.md` and
  `plan_tool/prompts/synthesize-body.md` contracts for the three known
  optional headings.
- Focused tests under `tests/test_create.py`.

## Out of scope / non-goals

- Generating or proposing a missing guardrail section.
- Author approval workflows or persisted approval provenance.
- Source-seed provenance, audit prompt grounding, `completeness-audit --seed`,
  truncation behavior, or any completeness-audit changes.
- General unknown-H2 passthrough, canonical-section reordering, concept
  deferral/bucket changes, or model-based fold detection.

## Decisions

1. The three named guardrails are the only additional optional sections; all
   other unknown headings remain shape errors.
2. Existing seed content is preserved only. A seed that lacks a guardrail does
   not gain one.
3. Compare exact headings before rendering fallback can hide a loss: check
   seed → distill result and distill input → synthesis result. The check is
   bounded by the number of supplied guardrail headings and makes no model
   call.
4. A reported loss is sufficient for this slice; deciding whether content was
   materially folded elsewhere remains BACKLOG #163.

## Verification

- A fixture seed containing all three headings yields each under its own H2.
- A fixture seed containing none yields none.
- Dropping a heading in a mocked distill or synthesis result emits the exact
  deterministic finding; retaining it emits none.
- Unknown optional keys remain rejected and existing canonical sections retain
  their current behavior.

## Stop / defer

- If preserving these three known headings requires a broader section-schema
  redesign, stop and file that separately rather than widening this plan.
