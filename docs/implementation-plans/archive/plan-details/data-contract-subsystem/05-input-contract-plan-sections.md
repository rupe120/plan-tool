> **Auto-archived**: this plan was swept on 2026-07-07 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 5 — Add Conditional Input Contract Plan Sections

## Summary

This step adds an optional, conditional `Input` contract section in plan bodies and per-step detail files for work that consumes an existing data structure, persisted schema, API surface, saved audit, or output format. The main edits are `plan_tool/create.py`, `plan_tool/detail.py`, `plan_tool/prompts/detail.md`, `plan_tool/prompts/synthesize-body.md`, `PLAN_FORMAT.md`, `DETAIL_FORMAT.md`, `tests/test_create.py`, and `tests/test_detail.py`. The key design decision is to make `Input` a recognized section when needed, not a globally required section on every plan or detail. On green, create/detail authoring can request and preserve `## Input` for contract-consuming work, unrelated plans do not grow ceremonial `Input` sections, and the docs describe when the section belongs.

## Table of Contents

- [Summary](#summary) — The behavior this step adds and the main files it touches.
- [Why](#why) — Why `Input` needs to be an explicit section.
- [Files (creates vs edits)](#files-creates-vs-edits) — The exact files this step changes.
- [Implementation](#implementation) — The required contract changes and the safest integration points.
- [Tests](#tests) — The focused regression cases for create and detail behavior.
- [Test-creation order (feature step)](#test-creation-order-feature-step) — The order to add tests while building the feature.
- [Acceptance criteria](#acceptance-criteria) — Checkable completion gates.
- [References](#references) — Primary docs relevant to this step.
- [Deferred](#deferred) — Related work that stays outside this step.

## Why

Plan and detail files currently tell an implementer what to build, why it matters, which files are in scope, and how to test it, but they do not reserve a stable place for the existing contracts a step consumes. That omission matters when correctness depends on upstream artifacts, persisted sidecars, saved audit JSON, generated docs, or dependency-step outputs. For unrelated work, however, a mandatory empty `Input` section would be noise. The fix is conditional: when a plan or step consumes an existing contract, `Input` gives authors one checkable place to say what the step reads before it writes; when it does not, the section stays absent.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `plan_tool/create.py` — Add `Input` as a recognized optional plan body section and shape-guidance concept, without adding it to the always-rendered `PLAN_BODY_SECTIONS` required set.
  - `plan_tool/detail.py` — Teach detail parsing to preserve an optional `## Input` section when present, without adding `input` to `_REQUIRED_H2_TOKENS` or required retry wording.
  - `plan_tool/prompts/detail.md` — Add conditional guidance telling generated detail files to include `## Input` only when the step consumes an existing contract.
  - `plan_tool/prompts/synthesize-body.md` — Add conditional prompt guidance for `Input` without making it a mandatory key in the canonical body-section JSON example.
  - `PLAN_FORMAT.md` — Document `## Input` as a conditional plan body section and explain what belongs there.
  - `DETAIL_FORMAT.md` — Document `## Input` as an optional detail H2 used only for contract-consuming steps; keep required-H2 counts unchanged.
  - `tests/test_create.py` — Add focused coverage that `Input` is omitted for unrelated plans, can be rendered/preserved when requested, and is documented as conditional.
  - `tests/test_detail.py` — Add parser/prompt tests that prove `Input` is accepted when present and not required when absent.

## Implementation

- **Foundational logic: conditional input-section contract.** Treat `Input` as a recognized optional section in both plan-body authoring and detail-file authoring. Include it only when a plan or step consumes an existing data contract, persisted schema, API/output format, saved audit, or dependency-step output whose shape affects correctness. The section should answer, in plain language, "what existing contract does this work consume, which fields or code locations are depended on, and what limits apply to that verification?"

- **Recognize `Input` in plan body creation without making it global.** In `plan_tool/create.py`, add shape guidance and rendering support for an optional `## Input` section, but do not add `Input` to the always-required `PLAN_BODY_SECTIONS` list. Unrelated `create` runs should continue to render the existing body skeleton. When the seed or synthesis metadata indicates the plan consumes an existing contract, render or preserve `## Input` near the design context, likely after `## Architecture` and before `## References`.

- **Keep synthesis shape symmetric for required keys.** `_BODY_SECTIONS_CANONICAL_KEYS`, `_canonical_body_section_keys`, `_render_section_shapes_block`, `_parse_body_sections_json`, `_render_distilled_markdown`, `_validate_distilled_sections`, `_canonical_seed_covers_all`, and `_find_placeholder_body_sections` derive from the required plan-body catalog. Do not break their exact-key invariant by adding a sometimes-required key. Instead, model `Input` as optional synthesis output or as conditional prompt guidance that can be rendered when present, while the required JSON keys remain stable for unrelated plans.

- **Update detail parsing as optional.** In `plan_tool/detail.py`, preserve `## Input` when a generated detail includes it, but do not add `input` to `_REQUIRED_H2_TOKENS` or `_REQUIRED_H2_DISPLAY`. Existing parser behavior for required sections stays unchanged: heading matching stays case-insensitive by first word, exactly one missing required section gets `_STUB_SECTION_BODY`, and two or more missing required sections still reject. Missing `Input` alone is not an error.

- **Update the detail authoring prompt.** In `plan_tool/prompts/detail.md`, add conditional guidance for `## Input` near the required structure rather than listing it as required. The guidance should tell authors to cite upstream step outputs by owning step id and outcome, not by restating implementation details from sibling steps. For this plan, that means a future detail can say it consumes step 1's data-contract registry and drift output without re-specifying step 1's internal registry design.

- **Keep docs aligned with code.** In `PLAN_FORMAT.md`, document `## Input` as a conditional plan body section, not part of the ordinary required skeleton. In `DETAIL_FORMAT.md`, document `## Input` as an optional H2 that appears when the step consumes an existing contract; keep required-H2 count, `_REQUIRED_H2_TOKENS` prose, and validation examples aligned with the unchanged required set.

- **Keep the synthesis prompt aligned.** `plan_tool/prompts/synthesize-body.md` contains a literal JSON example listing the canonical required body keys and says it mirrors `PLAN_BODY_SECTIONS`. Do not add `Input` to that required example. Add separate conditional guidance for returning/preserving `Input` only when the seed clearly says the plan consumes an existing contract.

- **Avoid a broad parser redesign.** Do not replace the first-token H2 parser or merge plan-body parsing with detail parsing. `plan_tool/detail.py:parse_detail_file_sections` deliberately differs from the broader plan-body parsing, and `plan_tool/create.py:extract_h2_sections` already owns plan H2 extraction.

## Tests

- `tests/test_create.py:TestRenderPlanBody::test_unrelated_plan_omits_input_section` — asserts default/new plans do not render `## Input` when no contract-consuming signal is present.
- `tests/test_create.py:TestRenderPlanBody::test_contract_consuming_plan_renders_input_section` — asserts a seed or synthesis result that names existing contract consumption can render/preserve `## Input`.
- `tests/test_create.py:TestParseBodySectionsJson::test_happy_path_required_canonical_keys_stay_stable` — asserts `Input` is not part of the exact required canonical JSON key set.
- `tests/test_create.py:TestParseBodySectionsJson::test_optional_input_section_can_be_preserved` — asserts optional `Input` content is accepted through the chosen optional path without rejecting unrelated required keys.
- `tests/test_create.py:TestTestingStrategyEnumeration::test_section_shapes_block_documents_conditional_input` — asserts shape guidance explains when `Input` belongs.
- `tests/test_create.py` prompt coverage — asserts `plan_tool/prompts/synthesize-body.md` names `Input` as conditional and does not place it in the required canonical JSON example.
- `tests/test_detail.py:TestRenderDetailPrompt` — asserts the rendered detail prompt describes conditional `## Input` guidance without adding it to the required output structure.
- `tests/test_detail.py:TestParseDetailResponse::test_accepts_clean_markdown_without_input` — keeps the existing valid detail fixture green without `## Input`.
- `tests/test_detail.py:TestParseDetailResponse::test_accepts_and_preserves_optional_input` — asserts a response with `## Input` is accepted and the section is preserved.
- `tests/test_detail.py:TestParseDetailResponse::test_missing_input_alone_is_not_stubbed_or_rejected` — asserts absence of optional `Input` does not trigger stub behavior.

### Test-creation order (feature step)

This is a **feature** step: add the create and detail tests with the implementation. Start with the regression tests that prove unrelated plans and details do not require `Input`, then add the positive optional-section tests for contract-consuming inputs. The green-before-done gate is that every new and updated test in `tests/test_create.py` and `tests/test_detail.py` passes before the step is complete.

## Acceptance criteria

- `plan_tool/create.py:PLAN_BODY_SECTIONS` does not make `Input` a universally required body section.
- Default/unrelated plan creation omits `## Input`.
- Contract-consuming plan creation can render or preserve exactly one `## Input` section.
- `plan_tool/create.py:_parse_body_sections_json` keeps the required canonical key set stable and does not reject an unrelated body-section JSON object for omitting `Input`.
- `plan_tool/detail.py:parse_detail_response` accepts a detail body that includes `## Input` with the required sections and preserves the section.
- `plan_tool/detail.py:parse_detail_response` accepts a detail body that omits `## Input` when all required sections are present.
- `plan_tool/prompts/detail.md` describes conditional `## Input` guidance without adding it to the required output structure.
- `plan_tool/prompts/synthesize-body.md` describes conditional `Input` guidance without adding it to the required canonical JSON example used by `create --from-existing`.
- `PLAN_FORMAT.md` and `DETAIL_FORMAT.md` document `Input` consistently as conditional.
- `pytest tests/test_create.py tests/test_detail.py` passes.

## References

- [CommonMark Specification](https://spec.commonmark.org/) — Use for the Markdown heading shape that these docs and parsers rely on.
- [Python json](https://docs.python.org/3/library/json.html) — Use for the create body-section synthesis response contract parsed by `json.loads`.
- [pytest Documentation](https://docs.pytest.org/en/stable/) — Use for the focused parser and renderer regression tests.

## Deferred

- Runtime plan schema changes — `Input` is a markdown body/detail section, not a new YAML frontmatter field.
- Data-contract registry behavior — Step 1 owns the registry and drift checks; this step only adds a stable place for plans and details to name their inputs.
