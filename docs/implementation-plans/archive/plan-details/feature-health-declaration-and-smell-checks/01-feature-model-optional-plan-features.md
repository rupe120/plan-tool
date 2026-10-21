# Step 1 — Add a `Feature` model and optional `Plan.features` field with kebab-id, unique-id, and step-resolution validation

## Summary

Add a `Feature` pydantic submodel (`id` / `title` / `steps`) and an optional `features: list[Feature]` field to `plan_tool/schema.py:Plan`, defaulting to an empty list so every existing plan parses and saves back out unchanged. A new `@model_validator(mode="after")` on `Plan` — modeled on the existing `Plan._validate_graph` — enforces three rules: feature `id`s are unique within the plan, are kebab-case, and every `steps:` entry points to a real step id. The key decision is to **put all three feature checks in one Plan-level validator** (the step-resolution and uniqueness rules need the full step/feature lists, and the kebab check is folded in so all the errors come from one place) rather than splitting the kebab check onto a `Feature` field-validator. When this passes: a `features:` block parses into `Plan.features`, a feature with a duplicate id, a non-kebab id, or a step id that doesn't exist raises `ValidationError`, and `features:` is just declared data — it changes no run/detail/jira behavior. Remapping `features.steps` through a structural step renumber is **out of scope for this step**: the `split`/`merge` step-renumbering functionality is still being implemented, so the transform-side feature-remap is deferred to a follow-up (see Deferred) rather than bound to a surface that is still changing.

## Table of Contents

- [Why](#why) — what's missing and why the feature layer is added now
- [Files (creates vs edits)](#files-creates-vs-edits) — the declared files and their edits
- [Implementation](#implementation) — the `Feature` model, the `Plan.features` field, and the new validator
- [Tests](#tests) — parse/validation/round-trip cases
- [Test-creation order (feature step)](#test-creation-order-feature-step) — author tests with the code; tests-must-pass-before-done gate
- [Acceptance criteria](#acceptance-criteria) — behaviors to check once it works
- [References](#references) — the pydantic/YAML docs relevant to this step
- [Deferred](#deferred) — items left out of this step's scope (top-level export, downstream consumers)

## Why

Plans today have no unit above the *step* to name a capability (say, "type-impure convergence") that a group of steps builds together — so even when an audit flags fragile code, nothing ties those findings to a single capability someone could pull out or drop. This step adds the smallest, standalone piece of that: an optional `features:` declaration in the plan frontmatter, validated the same way the step graph already is. It is a required building block for step 2's smell check (which looks at a feature's set of files through its steps' `step.files`) and the later part-2 ledger. Adding it as declared data with a `Field(default_factory=list)` default leaves every existing plan unchanged while opening up the feature layer.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/schema.py` — add `import re`; add the `Feature` BaseModel; add a module-level `_FEATURE_ID_RE` kebab-case constant; add `features: list[Feature] = Field(default_factory=list)` to `Plan`; add a `Plan._validate_features` `@model_validator(mode="after")`.
  - `plan_tool/create.py` — re-validate `features` at the iteration-loop reconciliation write-back (`create.py:5652`), where `model_copy` skips validators after the step set is reconciled, so a `features:` entry pointing at a dropped `pending` step fails loudly at the site instead of being written unvalidated.
  - `tests/test_parser.py` — add a `TestFeatures` class (and inline plan-text fixtures) covering parse, the three validation rules, `extra="forbid"`, and the write round-trip (including that an empty `features:` is left out on write).

## Implementation

### `plan_tool/schema.py`

**Add `import re`** at the top alongside the existing `from enum import Enum` / `from typing import Optional`. `re` is stdlib, so `schema.py` stays a stdlib/pydantic leaf (no new import cycle — acceptance criterion).

**Add a module-level kebab constant** near the other module-level declarations:

- `_FEATURE_ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")` — matches `merge-transform`, `type-impurity`; rejects `Merge`, `merge_transform`, leading/trailing hyphen (`-merge`, `merge-`), and double hyphen (`merge--x`). Single-source it as a constant so the validator and any future consumer key off one pattern.
- **Do not** reuse `plan_tool/locator.py:slug_from_filename` — that is a filename→slug *generator*, not an id *validator*, and importing `locator` into `schema.py` would invert the leaf import graph. Keep the regex local to `schema.py`.

**Add the `Feature` model** immediately above `class Plan` (after the `Step` class). Mirror `Step`'s config:

- `model_config = ConfigDict(extra="forbid", use_enum_values=False)` — `extra="forbid"` makes an unknown key inside a feature dict (e.g. `acceptance:`) raise, matching how `Step`/`Plan` reject stray keys.
- `id: str` — the kebab-case slug. No field-level validator here; the kebab check lives in the Plan-level validator (see below) so all feature-graph rules sit in one place and share one error style.
- `title: str` — required human-readable label.
- `steps: list[int] = Field(default_factory=list)` — the step ids this feature covers. `default_factory=list` (no `min_length`): the plan body does not require a feature to name steps, and step 2's check handles a feature with no steps fine. A step may belong to several features or to none — **do not** require every step to be covered (the plan body says not to force that busywork).

**Add the field to `Plan`** — place `features: list[Feature] = Field(default_factory=list)` **immediately before** the existing `steps: list[Step] = Field(min_length=1)` declaration:

- **Leaving the empty default out on write matters.** `default_factory=list` makes the default an empty list; `write_plan`'s `model_dump(exclude_defaults=True, exclude_none=True)` (see `plan_tool/parser.py:write_plan`) then drops `features:` for any plan that declares none — so the output is identical to today, the same way `files`/`creates`/`gate`/`depends_on` (all `default_factory=list`) are already dropped when empty.
- **Placing it before `steps`** makes the saved frontmatter render `features:` above `steps:`, matching the YAML example in the plan body. Field order doesn't affect whether the plan is valid; this is the only reason to choose before vs. after.

**Add `Plan._validate_features`** as a second `@model_validator(mode="after")` on `Plan`, modeled member-for-member on the existing `Plan._validate_graph` (the `@model_validator(mode="after")` that raises `duplicate step ids` / `references unknown id(s)`). Pydantic runs after-validators in definition order; the two are independent, so place `_validate_features` right after `_validate_graph`. It must:

- **Reject non-kebab ids** — for each feature, `if not _FEATURE_ID_RE.match(feature.id): raise ValueError(...)`, naming the offending id and that ids must be kebab-case (lowercase alphanumerics joined by single hyphens).
- **Reject duplicate ids** — collect `feature.id`s, track a `seen`/`dupes` set exactly like `_validate_graph`'s step-id dup detection, and `raise ValueError(f"duplicate feature ids: {sorted(dupes)}")` if any repeat.
- **Reject step references that don't resolve** — build `id_set = {s.id for s in self.steps}` (the same set `_validate_graph` builds) and, for each feature, `unknown = [sid for sid in feature.steps if sid not in id_set]`; raise naming the feature id and the unknown step id(s). This is the backstop that makes a dangling reference fail loudly whenever the plan is parsed or validated.
- **Return `self`** (the `@model_validator(mode="after")` return contract).
- **Does nothing when `features` is empty** — the loops have nothing to iterate, so existing plans pass unchanged.

**Where this logic belongs.** The core rule this step adds is *checking a list of declared ids resolves against the real graph* — the same shape as `Plan._validate_graph`'s `depends_on`→`id_set` membership check and its duplicate-id detection. That logic lives only in `schema.py` (the single dry-run construction tail; see the captured `_validate_graph` fact). There is no other feature-validation code to merge with — `features:` is brand new. Keep the new validator next to `_validate_graph` rather than pulling out a shared helper; the two work on different id spaces (feature ids vs step ids), and sharing would over-abstract two ~10-line loops.

### `plan_tool/create.py`

**Re-validate `features` at the create iteration-loop write-back.** The reconciliation persist at `create.py:5652` does `edited = edited.model_copy(update={"steps": merged_steps})` then `write_plan(plan_path, edited, expect_unchanged=False)`. `model_copy` **skips validators**, so `_validate_features` never runs here even though the step set just changed — and the re-proposal can drop a `pending` step (only `current`/`done` are preserved at `create.py:5631`), leaving a `features:` entry that points at a dropped step on `edited.features`. Today that dangling reference is written to disk unvalidated and only surfaces on the next `parse_plan`. Re-validate before the write so it fails loudly at the site that introduced it: after constructing the merged `edited`, re-run feature validation against the reconciled steps (e.g. `Plan.model_validate(edited.model_dump())`, which re-fires both `@model_validator(mode="after")`s) and let the resulting `ValidationError`/`ValueError` propagate through the loop's existing failure path. Do **not** silently remap or drop the feature here — the operator's intent is re-validation only; repairing the reference through structural renumbers stays deferred (see Deferred). This closes the plan's "`features:` drift after structural edits" Risk at the one in-scope mutation site this step owns; `detail.py`'s `model_copy` split/merge persists remain the deferred follow-up.

**Inertness is scoped to run/detail/jira, not create.** Because `model_validate` re-fires **both** `@model_validator(mode="after")`s, this write-back also re-runs `_validate_graph` against the reconciled steps — so a **feature-less** plan whose reconciled graph is latently invalid (a duplicate or dangling step id introduced by the re-proposal) now raises here too, where `model_copy` previously skipped validators. This is an intended `create --iterate` authoring-time fail-fast at the reconciliation write-back, not a change to parse/run/detail/jira behavior; `parse_plan` on an unchanged plan stays byte-identical. The plan's "no existing run/detail/jira behavior" claim is scoped accordingly.

### `tests/test_parser.py`

- Add a `TestFeatures` class plus inline plan-text constants (module-level, like `_GATED_STEP` / `_THREE_TYPED_STEPS`) — no new fixture files; build `features:` blocks with `parse_plan_text` and `write_plan(tmp_path/...)` mirroring `TestGate` / `TestChangeType`.
- Import `Feature` in the test via `from plan_tool.schema import Feature` (the `Feature` type is needed only to assert parsed instances). `tests/test_parser.py` already imports `Plan`/`StepStatus`/etc. from the top-level `plan_tool`; `Feature` is **not** re-exported from `plan_tool/__init__.py` in this step (see Deferred), so import it from `plan_tool.schema` directly.

## Tests

In `tests/test_parser.py`, new `class TestFeatures`:

- `test_features_absent_defaults_to_empty_list` — `parse_plan(_fixture("well_formed.md")).features == []` (existing no-`features:` plan parses, default applied).
- `test_features_parse_into_models` — a plan-text with two features parses; `plan.features[0].id`, `.title`, `.steps` match the YAML; entries are `Feature` instances.
- `test_feature_step_in_multiple_features_ok` — a step id listed in two features parses without error (multi-membership allowed).
- `test_feature_with_no_steps_ok` — a feature with `steps: []` (or omitted) parses (no total-coverage requirement).
- `test_duplicate_feature_id_rejected` — two features sharing an `id` raise `ValidationError`; message contains `duplicate` and the id.
- `test_non_kebab_feature_id_rejected` — `id: Merge_Transform` (uppercase + underscore) raises; parametrize/repeat the assertion for leading-hyphen (`-merge`), trailing-hyphen (`merge-`), and double-hyphen (`merge--x`) to pin `_FEATURE_ID_RE`.
- `test_feature_step_unresolved_rejected` — `steps: [99]` against a 3-step plan raises; message contains `99` (mirrors `test_invalid_dependency_rejected`).
- `test_feature_extra_field_rejected` — an unknown key inside a feature dict (e.g. `acceptance: foo`) raises (`extra="forbid"`); message mentions the key or `extra`.
- `test_features_round_trip_through_write_plan` — write→reparse preserves feature ids/titles/steps (mirrors `test_gate_round_trips_through_write_plan`).
- `test_features_empty_elided_on_write` — `write_plan` on `well_formed.md` produces frontmatter with no `features:` key (mirrors `test_gate_empty_elided_on_write`) — proves the output stays identical to the input.

### Test-creation order (feature step)

This is a **feature** step. Write every test above **in the same change** as the `schema.py` edits — write the failing test, implement the model/field/validator, watch it pass. The behaviors covered: default-empty parsing, a step in many features or none, the three validation rejections (duplicate / non-kebab / step that doesn't resolve), `extra="forbid"`, and the write round-trip plus dropping an empty `features:`. **Tests-must-pass-before-done gate:** every new `TestFeatures` case must pass (`uv run pytest -m "not integration" tests/test_parser.py -q`) and the whole existing `tests/test_parser.py` suite must stay green before this step counts as finished.

## Acceptance criteria

- `plan_tool/schema.py` exposes a `Feature` BaseModel with `id: str`, `title: str`, `steps: list[int]` and `ConfigDict(extra="forbid")`.
- `Plan` has `features: list[Feature]` defaulting to an empty list; `parse_plan` on a plan with no `features:` block yields `plan.features == []`.
- A plan whose frontmatter declares two features with the **same `id`** raises `ValidationError`.
- A feature `id` that is **not kebab-case** (uppercase, underscore, leading/trailing/double hyphen) raises `ValidationError`.
- A feature `steps:` entry that **does not resolve** to an existing step id raises `ValidationError` naming the bad id.
- An **unknown key inside a feature dict** raises `ValidationError` (`extra="forbid"`).
- `write_plan` on a plan without a `features:` block produces frontmatter with **no `features:` key** (the output matches the input exactly); a plan *with* features round-trips its ids/titles/steps intact.
- The create iteration-loop reconciliation write-back (`create.py:5652`) re-validates the reconciled model before `write_plan` (re-firing both `@model_validator(mode="after")`s), so a re-proposal that drops a step a feature references — or that leaves a feature-less graph latently invalid — raises through the loop's failure path rather than persisting unvalidated. This fail-fast is scoped to `create --iterate` authoring; `parse_plan` on an unchanged plan stays byte-identical.
- No new import cycle: `schema.py` imports only stdlib (`enum`, `typing`, `re`) and `pydantic`.
- All new `TestFeatures` cases pass, and the existing `tests/test_parser.py` suite stays green.

## References

- [Validators — Pydantic Docs](https://docs.pydantic.dev/latest/concepts/validators/) — `@model_validator(mode='after')` semantics and the return-`self` contract — the mechanism for `Plan._validate_features` mirroring `_validate_graph`.
- [Models — Pydantic Docs](https://docs.pydantic.dev/latest/concepts/models/) — defining a nested `BaseModel` (`Feature`) and embedding `list[Feature]` on `Plan`.
- [Fields — Pydantic Docs](https://docs.pydantic.dev/latest/concepts/fields/) — how `Field(default_factory=list)` defaults work, the basis for the empty default plus dropping it on write with `exclude_defaults`.
- [Configuration (ConfigDict) — Pydantic Docs](https://docs.pydantic.dev/latest/api/config/) — `extra='forbid'` ValidationError behavior for the unknown-feature-key rejection.

## Deferred

- **Top-level `Feature` re-export from `plan_tool/__init__.py`** — out of this step's `files:` footprint; tests import `from plan_tool.schema import Feature`. Add the export when a non-test consumer needs `Feature` at the package surface (step 2+).
- **Suppression-shape and smell checks** — step 2 (`plan_tool/review.py`, `plan_tool/project_config.py`); this step only adds the declared `features:` data those checks read.
- **Remapping and re-validating `features:` inside `split`/`merge`** — deferred: the `split`/`merge` step-renumbering functionality is still being implemented, so binding the feature-remap to it is out of scope for this step. Until it lands, `_validate_features` re-checks feature references whenever the plan is parsed/validated; the transform-side remap (mirroring the `depends_on` rewiring in `_apply_step_split`, plus a re-validating persist at `detail.py`'s `model_copy` split sites) is left to a follow-up. The create iteration-loop write-back is **not** in this deferral — it is re-validated in-step (see Implementation → `plan_tool/create.py`); only the `detail.py` split/merge transform-side remap stays out.
- **Check for features that can't be proven true or false** — left out plan-wide on purpose (it needs a way to tag acceptance criteria to features, which doesn't exist yet); recorded in the plan's Deferred section.
- **Requiring full coverage / non-empty `steps`** — deliberately *not* added; the plan body says not to require every step to belong to a feature or every feature to name steps.
