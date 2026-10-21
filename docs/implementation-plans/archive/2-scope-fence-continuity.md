> **Auto-archived**: this plan was swept on 2026-08-03 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

---
title: Scope Fence Continuity
status: completed
priority: medium
enforce_step_tests: true
steps:
- id: 1
  title: Keep supplied guardrail sections in created plans
  files:
  - plan_tool/create.py
  - plan_tool/prompts/distill-seed.md
  - plan_tool/prompts/synthesize-body.md
  - tests/test_create.py
  complexity: medium
  change_type: feature
  detail: docs/implementation-plans/plan-details/scope-fence-continuity/01-keep-supplied-guardrail-sections.md
  status: done
- id: 2
  title: Warn when a create stage drops a supplied guardrail heading
  files:
  - plan_tool/create.py
  - tests/test_create.py
  complexity: medium
  change_type: feature
  depends_on:
  - 1
  detail: docs/implementation-plans/plan-details/scope-fence-continuity/02-warn-when-create-stage-drops-supplied.md
  status: done
---
# Scope Fence Continuity

## Overview

Preserve supplied `Scope guardrails`, `Audit guardrails`, and `Expected placement` sections through `plan-tool create` distillation, body synthesis, and final rendering. Each supplied section must render under its own H2 heading, while missing guardrails remain absent; unknown model/body-contract keys remain rejected, and generic raw-seed H2 extraction retains its current unsupported/ignored behavior.

## Problem statement

The `plan-tool create` pipeline can lose supplied guardrail headings at the distillation or synthesis boundaries. Rendering fallback can hide that loss, so `plan_tool/create.py` needs deterministic exact-heading checks before rendering.

## Architecture

Extend the existing `plan_tool/create.py` optional-section catalog—retaining `Input`—with only `Scope guardrails`, `Audit guardrails`, and `Expected placement` as new optional keys. Preserve existing seed content without generating absent sections, normalize valid ATX closing sequences before exact-name comparison, and compare supplied headings from seed to distill output and from distill input to synthesis output; emit a deterministic finding for each loss without making a model call.

Update `plan_tool/prompts/distill-seed.md` and `plan_tool/prompts/synthesize-body.md` to contractually preserve the three known optional headings. Keep unknown headings as shape errors and avoid broader section-schema or ordering changes.


## Input

`plan_tool/create.py` consumes the seed document and the distillation and body-synthesis outputs as section-heading contracts. Correctness depends on the exact H2 headings `Scope guardrails`, `Audit guardrails`, and `Expected placement` being retained across the seed-to-distill and distill-to-synthesis boundaries; only heading loss is verified, while materially folded content remains outside this plan.

## References

- [Python regular expression operations](https://docs.python.org/3/library/re.html) — Documents exact regular-expression matching needed to recognize only permitted optional H2 headings.
- [pytest monkeypatch guide](https://docs.pytest.org/en/stable/how-to/monkeypatch.html) — Explains safely replacing dependencies so tests can simulate distill or synthesis output that drops headings.
- [unittest.mock](https://docs.python.org/3/library/unittest.mock.html) — Provides the standard-library mocking API for asserting deterministic preservation findings without model calls.
- [CommonMark Specification](https://spec.commonmark.org/current/) — Defines ATX heading syntax and rendering semantics relevant to preserving supplied sections as H2 headings.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

- A broader section-schema or ordering redesign; stop and file separate work rather than widening this plan.
- Detecting guardrail content materially folded into another section; this remains deferred to BACKLOG #163.

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

**Per-step test strategy** (derived from each step's `change_type`):

- step 1 (feature) — unit tests added with the implementation; green before completion.
- step 2 (feature) — unit tests added with the implementation; green before completion.

## Acceptance criteria

- A seed containing `Scope guardrails`, `Audit guardrails`, and `Expected placement` renders each supplied section under its own H2 heading.
- A seed containing none of the three optional headings renders none of them.
- `plan_tool/create.py` emits an exact deterministic finding when mocked distill output or synthesis output drops a supplied guardrail heading.
- `plan_tool/create.py` emits no preservation finding when supplied guardrail headings are retained.
- Unknown optional keys remain rejected, and existing canonical sections retain their current behavior.

## Deferred

- Decide whether guardrail content was materially folded elsewhere; deferred to BACKLOG #163.
