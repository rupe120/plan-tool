# Step 2 — Keep guardrail sections separate and out of defer buckets

## Summary

Preserve `Scope guardrails`, `Audit guardrails`, and `Expected placement` as optional, separate plan-body sections when a seed supplies them. Update `plan_tool/create.py` and the distill/synthesis prompt contracts so those known headings are accepted without opening the body format to arbitrary H2 sections. Exclude the same three headings from the create-time concept bootstrap and `plan_tool/detail.py:derive_candidate_buckets`, so no detail response can defer an audit fence. On green, guardrail-bearing seeds retain each heading, ordinary seeds gain none, and neither deferral producer offers a guardrail bucket.

## Table of Contents

- [Summary](#summary) — The delivered preservation and non-deferral behavior.
- [Table of Contents](#table-of-contents) — Quick links through this detail.
- [Why](#why) — Why scope fences must survive creation and resist deferral.
- [Files (creates vs edits)](#files-creates-vs-edits) — The existing surfaces changed in this step.
- [Implementation](#implementation) — Guardrail-section and bucket-exclusion rules.
- [Tests](#tests) — Focused regression coverage.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Markdown heading syntax used by the preservation rule.
- [Deferred](#deferred) — Follow-up work deliberately left outside this step.

## Why

`plan_tool/create.py:PLAN_BODY_SECTIONS` and the closed JSON contracts in `plan_tool/prompts/synthesize-body.md` and `plan_tool/prompts/distill-seed.md` currently leave seed guardrails with no supported destination, so they can be folded into prose or dropped. At the same time, `plan_tool/create.py:create_plan` and `plan_tool/detail.py:derive_candidate_buckets` bootstrap every current H2 as a deferrable concept, which would let a detail defer the very `Audit guardrails` section that constrains later review.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `plan_tool/create.py` — recognize the three optional guardrail headings, preserve them through distillation and synthesis, check exact-heading retention, and exclude them from create-time concept buckets.
  - `plan_tool/detail.py` — omit guardrail headings from `derive_candidate_buckets` and therefore from the detail prompt and envelope validation.
  - `plan_tool/prompts/synthesize-body.md` — document the three conditional JSON keys and their evidence-only preservation rule.
  - `plan_tool/prompts/distill-seed.md` — document the same conditional keys for single-plan distillation.
  - `tests/test_create.py` — cover prompt/parse/render preservation and create-time bucket exclusion.
  - `tests/test_detail.py` — cover the detail-side candidate and envelope rejection behavior.

## Implementation

- **Foundational logic: exact guardrail-heading preservation.** Treat only `Scope guardrails`, `Audit guardrails`, and `Expected placement` as supported optional guardrail sections. Keep them separate H2 sections in the rendered plan when the source supplies them; do not fold their content into `Architecture` or another canonical section.

- **Keep the canonical body closed.** Extend `plan_tool/create.py:OPTIONAL_PLAN_BODY_SECTION_SHAPES` and the related optional-key handling used by `_render_section_shapes_block`, `_parse_body_sections_json`, `_validate_distilled_sections`, `_render_distilled_markdown`, and `_render_plan_body`. Do not add a general “accept unknown H2” path, reorder the eight existing canonical sections, or author guardrail content for seeds that do not contain it.

- **Make guardrails conditional and evidence-only.** Update `plan_tool/prompts/synthesize-body.md` and `plan_tool/prompts/distill-seed.md` so each of the three recognized headings is an optional JSON key, emitted only when supported by the seed. Keep the existing required canonical-key contract intact, and include a worked shape that makes separate heading preservation clear.

- **Preserve exactly, without another model call.** Add deterministic checks at both parsed lossy boundaries, before rendering fallback can mask an omission: compare seed guardrail headings to the distill result, then compare the headings delivered to synthesis to the synthesis result. A recognized H2 lost at either boundary produces the bounded preservation finding; a retained heading does not. Match headings exactly under the project’s H2 parsing rules. Do not attempt to decide whether omitted prose was materially represented elsewhere, and do not add an invoker seam or Claude call.

- **Exclude guardrails at both bucket producers.** Apply the same three-name exclusion before `plan_tool/create.py:create_plan` sends `bootstrap_concepts(...)` results to `_review_create_concepts`, and before `plan_tool/detail.py:derive_candidate_buckets` returns its concept-id-to-section map. The latter exclusion must flow through `_format_concept_scope_block` and `parse_structured_detail_response`, so a guardrail id is neither shown as proposable nor accepted in a deferral envelope.

- **Keep concept storage unchanged.** This is an input exclusion, not a `ConceptTree`, `concepts.json`, or `scope-review` schema change. Existing non-guardrail body sections must retain their current bucket behavior.

- **Respect the dependency boundary.** Step 1 records seed provenance for later audit work; this step preserves the recognized guardrail headings in the plan body and does not extend `source_seed` handling or audit prompting.

## Tests

- `test_synthesis_accepts_optional_guardrail_sections` — asserts `plan_tool.create._parse_body_sections_json` accepts populated `Scope guardrails`, `Audit guardrails`, and `Expected placement` while preserving the required canonical-key rules.
- `test_distill_accepts_optional_guardrail_sections` — asserts the single-plan distill parser accepts the same optional keys and retains their bodies in the distilled markdown.
- `test_guardrail_seed_sections_render_as_separate_h2s` — drives the create rendering path with all three headings and asserts each survives under its own H2.
- `test_seed_without_guardrail_sections_does_not_render_them` — asserts ordinary seeds do not gain empty or invented guardrail headings.
- `test_guardrail_preservation_finding_reports_only_dropped_exact_headings` — covers retained and missing headings at both the distill and synthesis-result boundaries before rendering fallback can mask an omission, without invoking a model.
- `test_create_bootstrap_excludes_guardrail_sections_from_deferral_review` — asserts the create-side concept set excludes `Audit guardrails` while still retaining ordinary section candidates.
- `test_proposable_buckets_omit_guardrail_sections` — asserts `plan_tool.detail.derive_candidate_buckets` and the rendered detail prompt retain ordinary buckets but omit all three guardrails.
- `test_guardrail_bucket_envelope_is_rejected` — asserts a structured detail response targeting a guardrail concept id is not published or persisted.

### Test-creation order (feature step)

Add the parser and render tests in `tests/test_create.py` with the optional-section contract, then add the deterministic dropped-versus-retained preservation tests. Add the create-side and detail-side bucket exclusion tests after the shared guardrail-name rule is in place. Every new test must be green before this step is considered finished.

## Acceptance criteria

- A seed containing all three recognized guardrail headings produces a plan body containing each heading separately.
- A seed containing none of the three headings produces none of them.
- Synthesis and distillation accept only the recognized guardrail keys as conditional additions; unrelated section keys remain shape errors.
- A missing exact guardrail heading produces a deterministic preservation finding without an additional Claude invocation.
- `plan_tool/create.py:create_plan` does not offer any recognized guardrail section to `_review_create_concepts` as a deferral candidate.
- `plan_tool/detail.py:derive_candidate_buckets` does not return a concept id for any recognized guardrail heading.
- A detail envelope naming a recognized guardrail id is rejected, while ordinary body-section deferrals continue to work.
- `tests/test_create.py` and `tests/test_detail.py` pass.

## References

- [CommonMark Specification — ATX Headings](https://spec.commonmark.org/current/#atx-headings) — Use for the exact H2 heading rule behind deterministic guardrail preservation.

## Deferred

- Material-folding judgment for content omitted from its original guardrail heading — BACKLOG #163 requires model judgment and is outside this deterministic check.
- Arbitrary seed H2 passthrough — retain the closed optional-section catalog rather than widening plan-body acceptance.
- Concept-record schema, `scope-review`, and dismiss/remove behavior — this step only prevents new guardrail deferrals.
