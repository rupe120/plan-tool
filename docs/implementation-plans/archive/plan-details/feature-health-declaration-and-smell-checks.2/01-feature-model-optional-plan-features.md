> **Auto-archived**: this plan was swept on 2026-06-18 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 1 — Add the `Feature` model and the optional `features` registry/tag fields (types only)

## Summary

Adds three schema additions to `plan_tool/schema.py`: a new `Feature` model (`id: str`, `title: str`), an optional `Plan.features: list[Feature]` registry, and an optional `Step.features: list[str]` tag. All three default to empty, so every existing plan — which declares none — parses and round-trips unchanged. This step ships **types only**: no kebab/uniqueness/reference validation and no `@model_validator`. All semantic checks are advisory and land in step 2's `validate_feature_refs` (in `plan_tool/review.py`), keeping `schema.py` a stdlib/pydantic leaf and keeping `run`/`jira`/`detail` inert on a malformed feature block. On green, `tests/test_parser.py` has a `TestFeatures` class proving the fields parse, round-trip, stay out of frontmatter when empty, reject unknown/typed-wrong keys, and — the key inertness test — that a *semantically* malformed feature block still parses without raising.

## Table of Contents

- [Why](#why) — what the feature layer adds and why step 1 is types-only.
- [Files (creates vs edits)](#files-creates-vs-edits) — the two files this step touches.
- [Implementation](#implementation) — the `Feature` model and the two new fields, plus what is deliberately left out.
- [Tests](#tests) — the `TestFeatures` cases in `tests/test_parser.py`.
- [Acceptance criteria](#acceptance-criteria) — checkable behaviors on green.
- [References](#references) — the pydantic docs subset relevant to this step.
- [Deferred](#deferred) — semantic validation, package re-export, and the smell checks left for later steps.

## Why

Plans today have no unit above the *step* to name a capability that findings cluster around — so when an audit flags a brittle shape (a suppression flag), nothing ties the symptoms to one capability an operator could extract or cut. This step lays the declarative foundation: a `features` registry mapping `id → title`, and a per-step `features` tag listing the ids a step implements. Ownership runs **step → feature** (the step owns the list; the registry is just the id→title map) so a `split`/`merge` renumber can never dangle a tag — the tag rides with the step. Step 1 is intentionally the smallest possible slice: **only the types**. Keeping all semantic checks out of parse time is what matters most — `run`/`jira`/`detail` all call `parse_plan` and none read features, so routing a uniqueness/reference check through a `@model_validator` would brick those commands on a typo in metadata they ignore. The advisory `validate_feature_refs` and the smell checks come in step 2.

**Heads-up on stale guidance.** The accumulated lessons above describe a *different* (superseded) design — a `Feature` with a `steps: [int]` list and a `Plan._validate_features` `@model_validator(mode="after")` doing kebab/dup-id/step-resolution. That is the rejected "feature → step" ownership with parse-fatal validation. The current plan's Architecture (`docs/implementation-plans/2-feature-health-declaration-and-smell-checks.md`, **Part A**) and this step's title (*"types only, no semantic validator"*) explicitly reverse it. Follow the plan: **no `Feature.steps` field, no `Plan._validate_features`, no regex in `schema.py`.**

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/schema.py` — add the `Feature` model; add `features: list[Feature]` to `Plan`; add `features: list[str]` to `Step`.
  - `tests/test_parser.py` — add a `TestFeatures` class (schema parse/round-trip tests live here, mirroring `TestGate`/`TestChangeType`).

## Implementation

### `plan_tool/schema.py`

- **Add the `Feature` model** as a top-level `BaseModel`, placed near the other models (e.g. directly above `class Step`). Mirror the existing config exactly:
  - `model_config = ConfigDict(extra="forbid", use_enum_values=False)` — same line `Step`/`Plan` use. `extra="forbid"` makes a typo'd key (e.g. `titel:` or a stray `steps:`/`description:`) a clear `ValidationError` at parse time rather than silently dropped.
  - `id: str` — required. No format validation in this step (kebab-case is an *advisory* check in step 2).
  - `title: str` — required.
  - No other fields. Do **not** add a `steps` field — ownership is step → feature, so the registry carries only the id→title mapping.

- **Add `Plan.features`** to the `Plan` model (the model at `plan_tool/schema.py` with `class Plan(BaseModel)`):
  - `features: list[Feature] = Field(default_factory=list)` — declare it among the optional plan-level fields (alongside `lessons`, `test_command`, `enforce_step_tests`, `registered_by`). Placement before `steps: list[Step] = Field(min_length=1)` keeps the required-last ordering readable; exact order is cosmetic since YAML keys are matched by name.
  - Empty default → `write_plan`'s `model_dump(exclude_defaults=True, exclude_none=True)` (`plan_tool/parser.py:write_plan`) drops it for plans that don't set it. It is dropped automatically, the same as `files`/`gate`/`depends_on` — **no serializer edit needed**, and existing plans rewrite unchanged.

- **Add `Step.features`** to the `Step` model (`class Step(BaseModel)`):
  - `features: list[str] = Field(default_factory=list)` — the feature ids this step implements, placed beside the other `default_factory=list` fields (`files`, `creates`, `allowed_mentions`, `gate`, `depends_on`).
  - Dropped automatically when empty, the same way.

- **Name collision is intentional and safe.** `Step.features` (`list[str]`) and `Plan.features` (`list[Feature]`) share the key name on two different models — exactly the asymmetry the design wants (a step names ids; the plan defines them). Pydantic resolves each on its own model; no conflict.

- **No validators in this step.** Add no `@model_validator` and no `@field_validator` for features. `_validate_graph` (the dry-run graph validator on `Plan`) stays untouched and is **not** mirrored for features — the seam citation in the plan calls this out as a deliberate non-edit. The `Plan.model_validate(dumped)` round-trip call inside `write_plan` re-runs the (unchanged) graph validators only; it imposes nothing new on features.

- **Serialization is already handled.** `model_dump` recurses into nested `BaseModel`s, so a present `Plan.features` dumps to `[{"id": ..., "title": ...}]` and `yaml.safe_dump` writes it as a normal list of mappings. `_coerce_enums` is a no-op for `Feature` (it has no enum fields). No changes to `plan_tool/parser.py`.

- **Foundational logic + duplication scan.** The core behavior added is *parse and round-trip two new optional collection fields plus a small model*. Grepping for the same shape: `files`/`creates`/`gate`/`depends_on`/`allowed_mentions` are the existing `default_factory=list` precedent on `Step`; `lessons`/`test_command`/`registered_by` are the optional-plan-field precedent on `Plan`. These are *templates to mirror*, not call sites to change — adding a field needs no edit to any consumer because `write_plan` and `parse_plan` are field-generic. No other module hardcodes the plan/step field set in a way this step must update.

## Tests

All new tests go in `tests/test_parser.py` (schema tests live here — there is no `tests/test_schema.py`; the plan's Testing section names one loosely, but this step's `files:` is the authority). Follow the existing pattern: a `TestFeatures` class built from **module-level inline plan-text constants** fed through `parse_plan_text` and round-tripped via `write_plan(tmp_path/...)`, mirroring `TestGate` and `TestChangeType`. Import the new model directly: `from plan_tool.schema import Feature` (it is not re-exported from `plan_tool/__init__.py` in this step).

Add a constant `_FEATURE_PLAN` — a plan with a 2–3 entry `features:` registry and at least one step carrying a `features:` tag — and these cases:

- `test_features_absent_default_empty` — `parse_plan(_fixture("well_formed.md"))`: `plan.features == []` and every `step.features == []`.
- `test_feature_registry_parses` — `_FEATURE_PLAN`: `plan.features` is a list of `Feature` with the expected `id`/`title` pairs.
- `test_step_features_tag_parses` — `_FEATURE_PLAN`: the tagged step's `features` equals the expected list of id strings.
- `test_feature_block_round_trips` — write `_FEATURE_PLAN` to `tmp_path`, `write_plan(parse_plan(...))`, reparse: registry and step tags survive unchanged.
- `test_features_empty_elided_on_write` — round-trip `well_formed.md`; assert `"features:"` does not appear in the rewritten frontmatter (mirrors `test_gate_empty_elided_on_write`).
- `test_unknown_feature_key_rejected` — a registry entry with an extra key (e.g. `steps: [1]` or `description: x`) raises `ValidationError` (proves `extra="forbid"` on `Feature`).
- `test_feature_missing_title_rejected` — a registry entry with only `id:` raises `ValidationError` (title is required).
- `test_step_features_rejects_non_string_entry` — `features: [42]` on a step raises `ValidationError` (list-of-str typing).
- `test_malformed_feature_refs_still_parse` — **the inertness gate.** A plan with a duplicate registry id, a non-kebab id (e.g. `Merge_Transform`), and a `step.features` id with no matching registry entry **parses without raising** and returns a valid `Plan`. This pins that step 1 added no semantic validator and that `run`/`jira`/`detail` stay inert.

### Test-creation order (feature step)

This is a **feature** step. Author every `TestFeatures` case above *with* the schema edit, not after. Green-before-done gate: the full new `TestFeatures` class passes (`uv run pytest tests/test_parser.py -q`) and the existing `tests/test_parser.py` suite stays green before the step is considered finished.

## Acceptance criteria

- `plan_tool/schema.py` defines a `Feature` model with required `id: str` and `title: str`, `extra="forbid"`, and no other fields.
- `Plan` has `features: list[Feature] = Field(default_factory=list)`; `Step` has `features: list[str] = Field(default_factory=list)`.
- `parse_plan` on `well_formed.md` yields `plan.features == []` and `step.features == []` for every step; round-tripping it through `write_plan` produces frontmatter with no `features:` key.
- A plan declaring a `features:` registry and per-step `features:` tags parses, exposes the values, and round-trips unchanged.
- A plan whose feature block is *semantically* malformed (duplicate id, non-kebab id, dangling step ref) still returns a valid `Plan` from `parse_plan` with **no** `ValidationError`.
- `extra="forbid"` rejects an unknown key inside a `Feature`; a non-string `step.features` entry is rejected.
- No new `@model_validator`/`@field_validator` for features; `schema.py` gains no new imports (stays a stdlib/pydantic leaf); no import cycle.

## References

- [Models — Pydantic Docs](https://docs.pydantic.dev/latest/concepts/models/) — defining the `Feature` `BaseModel` and the two new fields alongside `Step`/`Plan`.
- [Fields — Pydantic Docs](https://docs.pydantic.dev/latest/concepts/fields/) — `Field(default_factory=list)` semantics, the basis for empty-by-default elision.
- [Configuration (ConfigDict) — Pydantic Docs](https://docs.pydantic.dev/latest/api/config/) — `extra="forbid"`, why both fields must be declared and why an unknown `Feature` key is rejected.
- [Validators (model_validator / field_validator) — Pydantic Docs](https://docs.pydantic.dev/latest/concepts/validators/) — confirms the deliberate choice to add **no** validator here; semantic checks stay advisory in step 2.

## Deferred

- **All semantic feature validation** (unique ids, kebab-case ids, `step.features` ids resolving to the registry) — step 2's advisory `validate_feature_refs` in `plan_tool/review.py`, never a parse-time validator. A `_FEATURE_ID_RE`/kebab regex belongs there, not in `schema.py`.
- **Smell checks** (suppression-shape) — steps 2–4.
- **Re-exporting `Feature` from `plan_tool/__init__.py`** — `__init__.py` is outside this step's `files:`; tests import `from plan_tool.schema import Feature`, and step 2 can do the same. Add the re-export only if/when a package-surface consumer needs it.
- **`PLAN_FORMAT.md` documentation** of the registry and tag — step 5.
