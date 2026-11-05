> **Auto-archived**: this plan was swept on 2026-11-05 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 1 — Accept step description and legacy title

<!-- plan-tool:detail-format-version: 1 -->

## Summary

Extend `plan_tool/schema.py:Step` to accept `description` and legacy `title` as input for the existing `Step.title` attribute. Validate both supplied values before accepting equal strings or rejecting a conflict. Add coverage in `tests/test_parser.py` for direct model construction and parsed frontmatter. On green, both spellings retain the supplied text without weakening unrelated validation or changing internal serialization.

## Table of Contents

- [Summary](#summary) — The change and observable result.
- [Why](#why) — Why input compatibility comes first.
- [Input](#input) — Existing schema and parser contracts.
- [Files (creates vs edits)](#files-creates-vs-edits) — The two files this step edits.
- [Implementation](#implementation) — Alias validation and compatibility boundaries.
- [Tests](#tests) — Cases that pin acceptance and rejection.
- [Acceptance criteria](#acceptance-criteria) — Checkable completion conditions.
- [References](#references) — Scope and contract sources.
- [Applicable guardrails](#applicable-guardrails) — Limits on this change.
- [Deferred](#deferred) — Work owned by later steps.

## Why

`plan_tool/schema.py:Step` requires `title` and forbids unknown fields, so frontmatter containing only `description` fails validation. `plan_tool/parser.py:parse_plan_text` delegates step validation to that model. Accepting the preferred spelling at this shared boundary lets new input work while retaining the `Step.title` API that existing consumers use. Explicit dual-key checks prevent an alias preference from silently hiding conflicting text or invalid input.

## Input

- `plan_tool/schema.py:Step` stores step text in `title: str` and uses `ConfigDict(extra="forbid", use_enum_values=False)`.
- `plan_tool/parser.py:parse_plan_text` checks the format version before calling `Plan.model_validate`, then wraps Pydantic failures in the parser’s `ValidationError`.
- `plan_tool/parser.py:render_plan_text` and `plan_tool/parser.py:write_plan` consume `Plan.model_dump` output. This step must preserve that internal dump shape; step 2 owns preferred frontmatter output.
- `plan_tool/schema.py:Plan` and `plan_tool/schema.py:Feature` have independent `title` fields. The step alias must not change their interpretation.

## Files (creates vs edits)

- **New files:** None.
- **Existing files (edits only):**
  - `plan_tool/schema.py` — Add step-text input normalization and explicit dual-key validation while retaining `Step.title`.
  - `tests/test_parser.py` — Add schema and parser cases for both spellings, conflicts, invalid values, and unchanged compatibility boundaries.

## Implementation

- **Foundational logic: validate supplied step-text keys before collapsing them into one value.** Put this rule in `plan_tool/schema.py:Step` so direct construction, `Step.model_validate`, and nested `Plan.model_validate` share it. Do not add a parser-only alias path.

- **Keep one stored field.** Retain `Step.title` as the internal attribute. One recommended approach is a before-model validator that checks a copied input mapping and normalizes accepted `description` input into `title`. Avoid two independently stored fields or alias-choice precedence that discards one supplied value without checking it.

- **Apply this input policy:**
  - `description` alone must accept the same string values as legacy `title`.
  - `title` alone must retain existing acceptance and rejection behavior.
  - Both keys must contain valid strings and compare exactly equal before acceptance.
  - Unequal strings must raise a validation error naming `description` and `title` and explaining how to resolve the conflict.
  - An invalid value under either supplied key must fail even when the other key contains a valid string.
  - Neither key present must remain a missing-required-text error.

- **Preserve text exactly.** Do not trim, case-fold, replace whitespace, or introduce length and nonempty restrictions. Empty strings and multiline strings remain valid where the existing string field accepts them. Equality must not turn distinct supplied strings into an accepted pair.

- **Preserve the caller’s mapping.** Normalization must not remove or replace keys in a dictionary supplied to model validation. Consume the recognized alias only in the model’s own normalized input, leaving unrelated keys available to `extra="forbid"`.

- **Keep output and consumers stable.** Default `Step.model_dump` output must retain `title` and omit `description`. Existing `Step(title=...)` callers must continue working without edits. Do not introduce a serialization alias that changes nested dumps or unrelated persisted payloads.

- **Reuse existing parser behavior unchanged.** `plan_tool/parser.py:parse_plan_text` already reaches the shared model and preserves version-check ordering. `plan_tool/parser.py:parse_plan` must continue reading without rewriting source files. No parser implementation change belongs in this step.

## Tests

Add the following cases in `tests/test_parser.py`, beside its schema and parser validation coverage. Parameterize entry points and value combinations where that keeps the policy readable.

### Tests for this step

- `test_step_accepts_either_text_key_through_shared_validation` — Direct construction, model validation, and parsed frontmatter accept either spelling and expose the exact text through `Step.title`.
- `test_equal_dual_keys_are_accepted_in_either_key_order` — Equal valid strings produce one stored value regardless of mapping order.
- `test_conflicting_dual_keys_name_both_keys_in_error` — Different strings fail through model and parser entry points with actionable conflict text.
- `test_invalid_alias_is_not_hidden_by_valid_peer` — Null, numeric, boolean, list, and mapping values fail under either key, including dual-key cases with a valid peer and equal invalid values.
- `test_missing_both_text_keys_remains_invalid` — A step without either key fails required-field validation.
- `test_step_text_is_preserved_without_new_content_restrictions` — Empty, whitespace-only, Unicode, and multiline strings retain their exact values under either spelling.
- `test_dual_key_equality_does_not_trim_or_fold_text` — Whitespace and case differences remain conflicts.
- `test_alias_validation_does_not_mutate_input_mapping` — Accepted and rejected validation attempts leave caller-owned dictionaries unchanged.
- `test_step_dump_keeps_internal_title_contract` — Default step and nested plan dumps contain `title`, omit `description`, and validate again without losing text.
- `test_step_alias_does_not_allow_unrelated_unknown_fields` — An accepted alias alongside an unrelated unknown step key still fails strict validation.
- `test_step_alias_does_not_change_plan_or_feature_titles` — Plan and feature titles retain their values and remain required independently of step text.
- `test_step_alias_accepts_absent_and_current_format_version` — Description-based plans parse with absent or current version declarations, while unsupported declarations retain the existing version error.
- `test_reading_description_plan_preserves_source_bytes` — `parse_plan` exposes the text without changing the source file.

Every added case and the existing `tests/test_parser.py` suite must be green before this step is finished. Run `uv run pytest tests/test_parser.py -q`; verify targeted regressions by temporarily breaking alias acceptance or dual-key rejection and confirming the corresponding tests fail.

## Acceptance criteria

- Description-only and title-only steps expose unchanged text through `Step.title` across direct and nested validation.
- Equal valid dual-key input succeeds; conflicting or invalid dual-key input fails without silently choosing a value.
- Caller-owned input mappings remain unchanged.
- Default model dumps retain the internal `title` contract.
- Unrelated unknown fields, plan and feature title requirements, and format-version checks retain their existing behavior.
- Reading a description-based plan leaves its source bytes unchanged.
- All tests listed above and the existing `tests/test_parser.py` suite pass.
- The implementation changes only `plan_tool/schema.py` and `tests/test_parser.py`.

## References

- [BACKLOG.md — #517](../../../BACKLOG.md) — Read the alias scope and owner-confirmed version-policy exception.
- [PLAN_FORMAT.md](../../../PLAN_FORMAT.md) — Read step field semantics and current strict validation rules.
- [DATA_CONTRACT.md](../../../DATA_CONTRACT.md) — Read the format-version policy whose narrow documentation amendment belongs to step 4.
- [plan_tool/schema.py](../../../plan_tool/schema.py) — Use `Step`, `Plan`, and `Feature` as the current schema authorities.
- [plan_tool/parser.py](../../../plan_tool/parser.py) — Read `parse_plan_text`, `render_plan_text`, and `write_plan` for validation and serialization boundaries.

## Applicable guardrails

- **The plan’s “Scope guardrails,” alias-only scope:** Keep normalization inside `Step`; do not use this change to restructure unrelated schema validation.
- **The plan’s “Scope guardrails,” version compatibility:** Preserve the existing version constants and parser gate. The alias must work through the current read path.
- **The plan’s “Out of scope,” internal terminology:** Keep `Step.title` and existing consumer APIs unchanged.
- **The plan’s “Scope guardrails,” stored plans:** Tests must use isolated input; this step must not rewrite repository plans.

## Deferred

- Preferred authored serialization — Step 2 owns changes to `plan_tool/parser.py:render_plan_text` and `plan_tool/parser.py:write_plan`, including frontmatter output and write compatibility.
- Proposal ingestion — Step 3 owns the separate raw-response handling in `plan_tool/create.py`, including paths that inspect `item.get("title")` before constructing `Step`. Shared model acceptance alone does not update those paths.
- Format documentation and backlog status — Step 4 owns the amendments to `PLAN_FORMAT.md`, `DATA_CONTRACT.md`, and `BACKLOG.md`.
- Pipeline consumer evidence — Step 2 owns the detail, audit, run, and Jira regression coverage; this step preserves their existing internal attribute contract.
