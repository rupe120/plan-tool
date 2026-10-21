> **Replaced**: this file has been superseded by `docs/implementation-plans/2-scope-fence-continuity.md`.
> Preserved here for history; do not edit.

## Overview

Preserve supplied `Scope guardrails`, `Audit guardrails`, and `Expected placement` sections through `plan-tool create` distillation, body synthesis, and final rendering. Each supplied section must render under its own H2 heading, while missing guardrails remain absent and all other unknown headings continue to be rejected.

## Problem statement

The `plan-tool create` pipeline can lose supplied guardrail headings at the distillation or synthesis boundaries. Rendering fallback can hide that loss, so `plan_tool/create.py` needs deterministic exact-heading checks before rendering.

## Architecture

Extend `plan_tool/create.py` optional-section parsing and rendering to recognize only `Scope guardrails`, `Audit guardrails`, and `Expected placement`. Preserve existing seed content without generating absent sections, and compare exact supplied headings from seed to distill output and from distill input to synthesis output; emit a deterministic finding for each loss without making a model call.

Update `plan_tool/prompts/distill-seed.md` and `plan_tool/prompts/synthesize-body.md` to contractually preserve the three known optional headings. Keep unknown headings as shape errors and avoid broader section-schema or ordering changes.

## Risks

- A guardrail heading can be silently dropped at a lossy boundary and then hidden by rendering fallback; severity: loss of supplied plan constraints; mitigation: exact-heading preservation checks before rendering.
- Preserving these headings could require a broader section-schema redesign; severity: plan scope expansion; mitigation: stop and file separate work rather than widening this plan.
- Guardrail content may be materially folded into another section rather than retained under its heading; severity: unresolved semantic loss; mitigation: report heading loss only; material-fold detection remains BACKLOG #163.

## Testing

Add focused tests under `tests/test_create.py`.

- A fixture seed containing all three headings yields each under its own H2.
- A fixture seed containing none yields none.
- Mocked distill or synthesis output that drops a heading emits the exact deterministic finding; output retaining it emits none.
- Verify unknown optional keys remain rejected and existing canonical sections retain their current behavior.

## Acceptance criteria

- A seed containing `Scope guardrails`, `Audit guardrails`, and `Expected placement` renders each supplied section under its own H2 heading.
- A seed containing none of the three optional headings renders none of them.
- `plan_tool/create.py` emits an exact deterministic finding when mocked distill output or synthesis output drops a supplied guardrail heading.
- `plan_tool/create.py` emits no preservation finding when supplied guardrail headings are retained.
- Unknown optional keys remain rejected, and existing canonical sections retain their current behavior.

## Deferred

- Decide whether guardrail content was materially folded elsewhere; deferred to BACKLOG #163.
