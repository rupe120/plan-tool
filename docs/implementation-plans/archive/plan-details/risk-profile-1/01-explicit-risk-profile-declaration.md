> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 1 — Add an explicit risk-profile declaration and a legacy standard fallback

## Summary

`RiskProfile` and two optional top-level `Plan` fields record a tier and its rationale. A legacy plan’s omitted declaration remains distinct from a newly recorded `standard`, explicit null in either declaration field or both is rejected, and one effective-standard fallback serves policy readers. The package export, format reference, parser coverage, and CLI validation coverage enforce the contract: valid declarations round-trip, legacy plans remain valid and unchanged, and malformed declarations fail `validate`.

## Table of Contents

- [Summary](#summary) — Reviewer-level outcome and main design choice.
- [Table of Contents](#table-of-contents) — Links to each section.
- [Why](#why) — Why plan metadata needs a distinct risk declaration.
- [Input](#input) — Existing frontmatter and serialization contracts this step uses.
- [Files (creates vs edits)](#files-creates-vs-edits) — Files changed and their roles.
- [Implementation](#implementation) — Required schema, fallback, and compatibility behavior.
- [Tests](#tests) — Focused parser and CLI validation coverage.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Primary references for Pydantic and YAML behavior.
- [Applicable guardrails](#applicable-guardrails) — Scope boundaries that apply here.
- [Deferred](#deferred) — Follow-up work this step does not perform.

## Why

`plan_tool/schema.py:Plan` carries plan priority and a durable risk declaration. Its stored optional pair preserves the difference between legacy omission and a newly reviewed `standard` decision, while the shared effective-standard accessor gives policy readers one behavior without writing a value into legacy plans. The typed contract keeps later create and review work on one clear representation.

## Input

- **Frontmatter model:** `plan_tool/schema.py:Plan` is the persisted contract. Its optional-field defaults and model validation define whether old plan files remain valid.
- **Generic parser and writer:** `plan_tool/parser.py:parse_plan_text`, `render_plan_text`, and `write_plan` validate through `Plan` and serialize with `exclude_defaults=True` and `exclude_none=True`.
- **CLI validation seam:** `plan_tool/cli/inspect.py:cmd_validate` reports `parse_plan` failures through `format_validation_errors`; this step tests that public path without changing its command behavior.
- **Limit:** This step validates declaration shape and effective fallback only. It does not classify work, choose an operator decision, or write declarations during creation.

## Files (creates vs edits)

- **New files:** None.

- **Existing files (edits only):**
  - `plan_tool/schema.py` — Add `RiskProfile`, the paired plan-frontmatter fields, their shape validation, and the effective-standard accessor.
  - `plan_tool/concept_sync.py` — Preserve a legacy omission when its scope-only rewrite rebuilds a `Plan`.
  - `plan_tool/scope_out.py` — Preserve a legacy omission when its narrow preview rebuilds a `Plan`.
  - `plan_tool/__init__.py` — Re-export `RiskProfile` through the supported package surface.
  - `PLAN_FORMAT.md` — Document the two fields, their closed vocabulary, the legacy omission rule, and new-plan declaration expectations.
  - `tests/test_parser.py` — Add focused schema, fallback, and serializer tests.
  - `tests/test_concept_sync.py` — Prove concept synchronization retains a legacy omission during its plan rebuild.
  - `tests/cli/test_inspect_cmds.py` — Add a public `validate` regression for an invalid risk-profile declaration.
  - `tests/test_scope_out.py` — Prove scope-out retains a legacy omission during its narrow preview rebuild.

## Implementation

- **Foundational logic: paired declaration with an effective fallback.** Add a `RiskProfile` string enum beside `Priority` in `plan_tool/schema.py`, with exactly `low`, `standard`, and `high`.

- **Keep stored declaration separate from policy fallback.** Add optional top-level `Plan.risk_profile` and `Plan.risk_profile_rationale` fields. A legacy plan omits both keys; it must not gain stored fields merely because it is parsed and rewritten. Explicit YAML null is not an omission and must be rejected before optional-field defaults can erase that distinction.

- **Expose one effective-tier rule.** Add a clearly named `Plan` accessor that returns `RiskProfile.STANDARD` when `risk_profile` is absent. Future policy readers should use that accessor when they need behavior, while raw field presence remains available when they need to distinguish legacy omission from an explicit standard declaration.

- **Validate the pair as one declaration.** Accept either both fields omitted or both fields present with values. Reject explicit null in either field or both fields, a lone tier, a lone rationale, an unknown tier, and a rationale that is empty after trimming or spans multiple lines. Do not make parse-time validation judge whether the rationale substantively supports the tier; creation and operator-decision steps own that meaning.

- **Do not derive risk from priority.** `Plan.priority` remains independent planning metadata. Do not infer, rewrite, or silently upgrade a risk declaration from it.

- **Keep `plan_tool/parser.py` generic.** `parse_plan_text`, `render_plan_text`, and `write_plan` should continue to rely on the `Plan` model and existing enum coercion. Do not add a risk-profile-specific YAML branch or a rewrite migration; explicit declarations must serialize, and absent legacy fields must remain absent.

- **Preserve omission across plan rebuilds.** Any existing internal path that rebuilds a legacy `Plan` from `model_dump()` must exclude absent `None` values before revalidation. This keeps an omitted declaration absent instead of converting it into invalid explicit YAML null while preserving the existing concept-sync and scope-out behavior.

- **Keep the package boundary usable.** Export the new enum from `plan_tool/__init__.py` and its `__all__` list so step 2 can use the same vocabulary without reaching into a private implementation detail.

- **Document the contract where readers look for it.** Update `PLAN_FORMAT.md`’s frontmatter schema, field semantics, defaults discussion, and example as needed. State that new plans will record both fields, while only an omitted pair is accepted as a legacy declaration with effective `standard` behavior; explicit null is invalid.

- **Use the existing CLI seam for end-to-end validation.** Add coverage through `tests/cli/test_inspect_cmds.py` and `plan_tool/cli/inspect.py:cmd_validate`; do not change inspection output or add a new risk display in this step.

## Tests

Add focused parser, CLI-validation, and internal-rebuild cases.

### Tests for this step

- `test_risk_profile_legacy_omission_uses_effective_standard_without_declaration` — A plan with neither field parses, reports the effective standard tier, and retains both omitted fields after `write_plan`.
- `test_risk_profile_declaration_accepts_each_closed_tier` — Parametrized explicit `low`, `standard`, and `high` declarations parse with their supplied rationale.
- `test_risk_profile_rejects_unknown_tier` — An unsupported literal raises `ValidationError`.
- `test_risk_profile_requires_tier_and_rationale_together` — Tier-only and rationale-only frontmatter both fail validation.
- `test_risk_profile_rejects_every_explicit_null_shape` — Parameterized raw frontmatter with `risk_profile`, `risk_profile_rationale`, or both set to YAML null fails validation rather than becoming a legacy omission on render.
- `test_risk_profile_rationale_rejects_blank_or_multiline_text` — Empty, whitespace-only, and multi-line rationales cannot become recorded declarations.
- `test_explicit_risk_profile_renders_and_reloads` — `render_plan_text` preserves an explicit declaration in parseable YAML.
- `test_explicit_risk_profile_round_trips_through_write_plan` — `write_plan` preserves both explicit fields and serializes the enum as its YAML value.
- `test_risk_profile_is_exported_from_plan_tool` — The package-level import refers to the schema enum.
- `test_sync_renders_decisions_preserves_markdown_and_maps_steps` — Concept synchronization changes its owned sections without turning a legacy omission into a stored declaration.
- `test_narrow_preserves_legacy_risk_profile_omission` — Scope-out's narrow preview retains an omitted declaration through its internal `Plan` rebuild.
- `test_validate_reports_invalid_risk_profile` — `main(..., "validate", ...)` reports the field error and keeps the existing `--fail-on-findings` exit behavior.

Green-before-done gate: every listed case is green, including `uv run pytest tests/test_parser.py tests/cli/test_inspect_cmds.py tests/test_concept_sync.py tests/test_scope_out.py -q`.

## Acceptance criteria

- A plan may store only `low`, `standard`, or `high` with a non-empty, one-line `risk_profile_rationale`.
- A plan with exactly one of the two declaration fields, explicit null in either field or both, a blank or multi-line rationale, or an unknown tier fails schema validation.
- A legacy plan with neither key remains valid, retains neither field on round-trip, and reports effective `standard` behavior through the shared accessor.
- Concept synchronization and scope-out retain that legacy omission when they rebuild a `Plan` internally.
- An explicit `standard` declaration remains visibly present after rendering and parsing, distinct from legacy omission.
- `RiskProfile` is importable from `plan_tool`.
- `plan-tool validate` reports an invalid risk-profile value through its existing invalid-plan path.
- `PLAN_FORMAT.md` names the persisted fields, legacy fallback, and explicit-declaration rule.

## References

- [Models | Pydantic Docshttps: — Use for typed model defaults, validators, and rejected input behavior.
- [Fields | Pydantic Docshttps: — Use for optional field declarations that preserve legacy plans.
- [Serialization | Pydantic Docshttps: — Use for default and `None` exclusion during frontmatter round-trips.
- [PyYAML Documentationhttps: — Use for the YAML loading and dumping behavior exercised by the parser tests.

## Applicable guardrails

- **The plan’s “Plan intent.”** Keep this step limited to recording a reviewable signal; do not change downstream ceremony, audit behavior, or execution policy.
- **The plan’s “Step intent.”** Preserve the difference between legacy omission and an explicit standard declaration in the stored model, serializer, and tests.
- **The plan’s “## Scope contract,” allowed behavior changes.** Limit behavior changes to the frontmatter contract and validation path; do not reorganize adjacent create or inspection code.
- **The plan’s “## Out of scope.”** Do not add tier consumers, confidence automation, creation-path classification, existing-plan migration, or split/annotate/scope-out behavior changes; preserving a legacy omission through their existing internal plan rebuilds is field compatibility, not new scope-out behavior.

## Deferred

- Creation-time classification and no-source declaration writing — steps 2 and 3 own those create-path behaviors.
- Downstream tier consumption in detail, audit, apply, run, or Jira surfaces — the plan’s “## Out of scope” routes this work to sibling #182.
- Existing-plan migration or reclassification — the plan’s “## Out of scope” excludes it.
