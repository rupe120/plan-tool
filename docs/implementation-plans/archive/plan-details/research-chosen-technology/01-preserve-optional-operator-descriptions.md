> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 1 — Preserve operator descriptions and research-disclosure decisions on hosting and store rows

## Summary

`HostingRow` and `StoreRow` carry an optional `description` through parsing, rendering, and stage-revision payloads. Add the paired `research_disclosure` decision so only an explicitly external product can leave the repository for research; absent or local disclosure stays local. The two fields remain attached to their row after a normal roadmap revision changes another property.

## Table of Contents

- [Summary](#summary) — Scope and expected green result.
- [Table of Contents](#table-of-contents) — Quick links to this detail.
- [Why](#why) — Why the row contract needs a durable fallback field.
- [Input](#input) — Existing artifact and revision contracts this step extends.
- [Files (creates vs edits)](#files-creates-vs-edits) — Files changed by the step.
- [Implementation](#implementation) — Required contract and preservation rules.
- [Tests](#tests) — Focused regression coverage.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Relevant primary API references.
- [Applicable guardrails](#applicable-guardrails) — Scope limits that bind this step.

## Why

The hosting and store row contracts provide a durable place for an operator to explain an internal or undocumented product. They also need an explicit boundary on whether a product literal can leave the repository. The closed row payload models in `plan_tool/roadmap_revision.py` carry both fields so a stage revision cannot erase the fallback or widen disclosure while changing an unrelated value. This step keeps the fallback available to later research and refusal work without turning either field into a quality-review surface.

## Input

- **Persisted artifact rows:** `plan_tool/roadmap_artifacts.py:parse_constraints_artifact` reads `hosting:` rows from `02-constraints.md`, and `plan_tool/roadmap_artifacts.py:parse_components_artifact` reads `stores:` rows from `03-components.md`. Both rows currently carry optional `product` and `description` metadata and remain readable when either is absent. This step adds optional `research_disclosure` without changing that compatibility.
- **Stage revision envelope:** `plan_tool/roadmap_revision.py:HostingRowPayload`, `plan_tool/roadmap_revision.py:StoreRowPayload`, and `plan_tool/roadmap_revision.py:parse_stage_revision_operations` decode closed JSON row payloads into the typed artifact rows.
- **Revision merge consumer:** `plan_tool/roadmap_revision_patch.py:merge_stage_revision` replaces typed stage rows without reshaping their fields. It should receive complete rows from the updated payload models and needs no production-code edit in this step.

## Files (creates vs edits)

- **New files:** None.

- **Existing files (edits only):**
  - `plan_tool/roadmap_artifacts.py` — Add and preserve `research_disclosure` beside the optional description on `HostingRow` and `StoreRow` in their parsers and renderers.
  - `plan_tool/roadmap_revision.py` — Carry the field in `HostingRowPayload` and `StoreRowPayload` so stage revisions retain it.
  - `plan_tool/prompts/roadmap-constraints.md` and `plan_tool/prompts/roadmap-components.md` — Name the optional field in each model-facing inventory and show it in the matching artifact example.
  - `ROADMAP_FORMAT.md` — Document the optional field on both row kinds and include it in matching examples.
  - `tests/test_roadmap.py` — Keep each stage prompt's inventory aligned with the parsed row keys.
  - `tests/test_roadmap_artifacts.py` — Cover row construction, parse/render preservation, omission, and type handling.
  - `tests/test_roadmap_revision.py` — Cover stage revision edits that retain an existing description.
  - `tests/test_roadmap_format.py` — Guard the documented hosting and store schema plus executable examples.

## Implementation

- **Foundational logic:** preserve optional operator `description` and `research_disclosure` metadata from hosting and store frontmatter rows through every typed row path, without interpreting a description or broadening disclosure by default.

- **Keep construction compatible:** add `research_disclosure: Optional[ResearchDisclosure] = None` after the existing `description` field on `plan_tool/roadmap_artifacts.py:HostingRow` and `plan_tool/roadmap_artifacts.py:StoreRow`. Existing positional construction and description-only rows keep their current meaning; `None` behaves as local.

- **Treat descriptions as optional raw text:** `plan_tool/roadmap_artifacts.py:_parse_hosting_rows` and `plan_tool/roadmap_artifacts.py:_parse_store_rows` accept a string or `null`/absence for `description`. They preserve strings exactly, including blank and whitespace-only values, and reject non-string, non-null values with the same row- and field-specific error style used by `_optional_product`.

- **Make disclosure fail closed:** accept only `research_disclosure: external` or `local` as a string when present; reject other values and non-strings with a row- and field-specific artifact error. Absence or `null` has the same local meaning as `local`, while only `external` grants step 2 permission to send that row's trimmed product literal to research. The field does not judge a product or description.

- **Render only present values:** `plan_tool/roadmap_artifacts.py:render_constraints_artifact` and `_store_mapping` return a non-`None` description to frontmatter, while missing or `None` values remain omitted rather than rendering `description: null`. Existing key order and the current `product` restriction for recognized non-compute hosting facets remain unchanged.

- **Carry the field through stage revisions:** `plan_tool/roadmap_revision.py:HostingRowPayload` and `StoreRowPayload` pass the optional field through each `to_row` method. A full-row `edit-row` payload that changes hosting `value` or store `category`/`sharing` and omits `description` retains the selected row’s existing description through `_decode_row_payload`, `_bind_edit_operation`, and the generic merge path; an explicit `description: null` clears it.

- **Preserve the disclosure decision:** use the same omitted-versus-explicit-null distinction for `research_disclosure`. An edit that omits it preserves the existing value; `research_disclosure: null` clears it to the local default. Do not allow a stage revision to broaden disclosure by omission.

- **Do not widen revision authority:** keep hosting and store rows out of `plan_tool/roadmap_revision.py:TEXT_FIELDS_BY_ROW_TYPE` and `plan_tool/roadmap_artifacts.py:design_row_collections`. The new field is row metadata, not a local presentation-edit surface; existing `StageRowOperationPolicy` limits, including the fixed hosting facet and identity-only prose rule, remain unchanged.

- **Make the field authorable:** the hosting and store inventory instructions in `plan_tool/prompts/roadmap-constraints.md` and `plan_tool/prompts/roadmap-components.md` name optional `description`, and each matching example includes it without making it a required key, vocabulary, or gate.

- **Make external consent authorable:** the same inventories name optional `research_disclosure`, explain that only `external` permits an outbound product query, and tell the author that local/omitted rows need a description. Examples use `external` only for a product safe to research.

- **Document the contract where operators read it:** update the `## \`02-constraints.md\` — frontmatter schema` and `## \`03-components.md\` — frontmatter schema` sections in `ROADMAP_FORMAT.md`. State that `description` is optional operator text, carries no vocabulary or quality rule, and is distinct from the existing `product` field. Also document `research_disclosure`: `external` is explicit permission to send that row's trimmed product literal to external research; `local`, absence, and `null` keep it local, and a local selected row requires a nonblank description rather than a generic query.

- **Use examples as contract checks:** the matching `02-constraints.md` and `03-components.md` worked examples in `ROADMAP_FORMAT.md` include a description and an explicit disclosure decision, so the existing parser, renderer, and gate-backed example tests exercise both fields without implying that disclosure is required.

## Tests

### Tests for this step

- `tests/test_roadmap_artifacts.py:test_existing_product_only_rows_keep_product_and_default_description` — Existing positional product rows still assign `product` correctly and default `description` to `None`.
- `tests/test_roadmap_artifacts.py:test_hosting_and_store_descriptions_round_trip_and_omit_none` — Both artifact parsers and renderers retain present descriptions and omit absent or null descriptions.
- `tests/test_roadmap_artifacts.py:test_optional_description_preserves_whitespace_and_rejects_non_strings` — Whitespace text is preserved unchanged, while invalid scalar types raise a row-specific artifact error.
- `tests/test_roadmap_artifacts.py:test_research_disclosure_round_trips_and_rejects_invalid_values` — Both row kinds retain `external` or `local`, omit null, and reject malformed disclosure values.
- `tests/test_roadmap_revision.py:test_hosting_and_store_stage_edits_preserve_omitted_descriptions` — A stage revision that changes another hosting or store property carries an omitted description into the merged, rendered artifact.
- `tests/test_roadmap_revision.py:test_hosting_and_store_stage_edits_clear_explicit_null_descriptions` — An explicit null remains a visible request to clear the fallback for both row kinds.
- `tests/test_roadmap_revision.py:test_hosting_and_store_stage_edits_preserve_omitted_research_disclosure` — Omitted disclosure cannot silently broaden or erase the row's decision.
- `tests/test_roadmap_revision.py:test_hosting_and_store_stage_edits_clear_explicit_null_research_disclosure` — An explicit null resets both row kinds to the local default rather than retaining external permission.
- `tests/test_roadmap_format.py:test_hosting_and_store_schema_document_optional_description_and_research_disclosure` — Both schema sections describe the optional fields, their local default, and the outbound boundary without assigning a vocabulary or quality gate to descriptions.
- `tests/test_roadmap.py:TestConstraintsPromptTemplate::test_constraints_prompt_names_every_required_row_key` and `tests/test_roadmap.py:TestComponentsPromptTemplate::test_components_prompt_names_every_required_row_key` — Each model-facing inventory names `description` and `research_disclosure` as row keys.
- `tests/test_roadmap_format.py:test_every_artifact_example_round_trips` — Updated worked examples continue to parse, render, and compare equal.

**Green-before-done:** every listed test, plus the existing `tests/test_roadmap_revision.py:test_text_field_table_covers_every_targetable_row_type`, is green before this step is complete.

## Acceptance criteria

- `HostingRow` and `StoreRow` expose an optional `description` after their existing fields, and product-only construction remains compatible.
- `HostingRow` and `StoreRow` expose optional `research_disclosure` after `description`; only `external` grants outbound-research permission and absence is local.
- `parse_constraints_artifact` and `parse_components_artifact` retain string descriptions; non-string, non-null descriptions raise `RoadmapArtifactError`.
- Rendering a row with `description=None` omits the key, while rendering a present description preserves its exact text.
- A stage `edit-row` that omits `description` while changing a hosting or store property does not drop the existing value; explicit `description: null` clears it.
- A stage `edit-row` preserves an omitted `research_disclosure`, while explicit null resets it to local.
- Hosting and store rows remain outside the local presentation revision table and retain their current gate and revision-policy behavior.
- The constraints and components prompts can author optional descriptions because their inventories name the key and their examples parse with it.
- The constraints and components prompts state the disclosure boundary and their examples exercise an external-safe product.
- `ROADMAP_FORMAT.md` documents both fields on hosting and store rows, including the fail-closed local default and external outbound boundary, and its worked examples pass the parser, renderer, and gate checks.
- `uv run pytest tests/test_roadmap_artifacts.py tests/test_roadmap_revision.py tests/test_roadmap_format.py -q` passes.

## References

- [PyYAML Documentationhttps: — Review safe loading and scalar handling for optional YAML fields.
- [dataclasses — Data Classeshttps: — Review frozen dataclass defaults and field ordering.

## Applicable guardrails

- **The plan’s “## Step intent,” recorded fallback:** preserve an operator-provided description without adding any quality, authority, freshness, or usefulness judgment.
- **The plan’s “## Out of scope,” existing roadmap contracts:** do not redesign hosting/store vocabularies, gates, or their current revision authority while adding the field.
- **The plan’s “## Out of scope,” downstream execution lanes:** keep this step to the roadmap artifact contract; later steps own research selection and refusal behavior.
