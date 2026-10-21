# Step 5 — Document the `features:` frontmatter field and the advisory smell checks in PLAN_FORMAT.md, and record the deferral of the unfalsifiable-feature check

## Summary

Document, in `PLAN_FORMAT.md`, the optional plan-level `features:` field (added in code by step 1) and the two deterministic advisory smell checks (suppression-shape, self-referential — added by step 2 and surfaced by steps 3/4). This is a **non-code** step touching only `PLAN_FORMAT.md`: extend the frontmatter schema YAML block, the `### Field semantics`, `### Defaults`, and `### Validation rules` sections with `features:`, and add one new `## Smell checks (advisory)` H2 covering both checks plus the explicit deferral of the unfalsifiable-feature check. The key decision is **where each piece lives**: `features:` is a format field, so it threads through the existing frontmatter surfaces beside `steps:`, while the smell checks are *behavior over the format* and so get their own section parallel to the existing `## Body sections (advisory-checked)` — not a fabricated command section (PLAN_FORMAT.md documents no commands). On green: a reader of `PLAN_FORMAT.md` learns the `features:` shape and its three validation rules, learns both smell checks are advisory (never flip the exit code), and sees the unfalsifiable check named as deferred with its blocking reason.

## Table of Contents

- [Why](#why) — what's undocumented and why the doc must land with the feature
- [Files (creates vs edits)](#files-creates-vs-edits) — the single doc file and its five edit sites
- [Implementation](#implementation) — exact placements for `features:` and the smell-checks section
- [Tests](#tests) — verification for a doc-only step
- [Acceptance criteria](#acceptance-criteria) — checkable doc facts
- [References](#references) — pydantic/YAML docs behind the documented behavior
- [Deferred](#deferred) — what this doc step does not cover

## Why

`PLAN_FORMAT.md` is the reference humans and coding agents read to learn the plan-file contract, but it has no entry for the `features:` field steps 1–4 add, and no description of the advisory smell checks that now run in `validate` and `completeness-audit`. Until the doc lands, the only record of `features:` and the smell shapes is in code and detail files — invisible to anyone authoring a plan by hand. This step closes that gap. Because `PLAN_FORMAT.md` opens with "the code wins — fix the doc," the doc must match what steps 1–4 actually land: confirm the real field names, validation messages, config block key, and the exact section/JSON labels at HEAD before writing, rather than copying the symbol names assumed in the sibling detail files.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `PLAN_FORMAT.md` — five edit sites:
    1. **Frontmatter schema YAML block** (the fenced `yaml` block under `## Frontmatter schema`) — add a `features:` entry beside the other plan-level fields.
    2. **`### Field semantics`** — add a `**features**` bullet describing the field, the `Feature` shape, and the per-feature rules.
    3. **`### Defaults`** — extend the prose paragraph after the per-step defaults table (the one naming `lessons`/`test_command`/`enforce_step_tests`/`registered_by`) to include `features` and its empty-list default.
    4. **`### Validation rules`** — add the three feature validation rules to the numbered list.
    5. **New `## Smell checks (advisory)` section** — insert after `## Body sections (advisory-checked)` and before `## Canonical step layout (input shape for create --from-existing)`; document both smell checks and the deferral.

## Implementation

### `PLAN_FORMAT.md` — frontmatter schema YAML block

- **Add a `features:` entry** as a plan-level optional field. Place it directly **after** the `steps:` block in the fenced YAML so a reader sees `steps:` (which features reference) first. Document the `Feature` shape inline with the same comment style as `steps:`:

  ```yaml
  features: # optional. Default []. Named capabilities above the step layer; each maps to the
            # steps that build it. Purely declarative — changes no run/detail/jira behavior.
    - id: string # required. kebab-case slug (e.g. merge-transform), unique within the plan.
      title: string # required. Human-facing capability name.
      steps: [integer, ...] # required. Step ids this feature is built from; each must
                            # match an existing steps[].id. A step may appear in several
                            # features, or none — total coverage is NOT required.
  ```

- **Match the code field names** added in step 1's `plan_tool/schema.py` `Feature` model (`id` / `title` / `steps`) and `Plan.features`. If step 1 renamed any field, the doc follows the code.

### `PLAN_FORMAT.md` — `### Field semantics`

- **Add a `**features**` bullet** after the per-step bullets (after `**steps[].status_note**`, the last semantics bullet). Note that this groups `features` with the per-step bullets even though the section lists the other plan-level fields (`test_command`, `enforce_step_tests`) *before* the per-step bullets — either placement is acceptable; placing it last keeps it adjacent to the `steps[]` bullets it references. State:
  - `features:` is plan-level, optional, default empty list — a layer **above** steps (steps map to *files*; features map to *steps*).
  - Each `Feature` carries `id` (kebab-case, unique within the plan), `title`, and `steps:` (a list of step ids, each resolving to a real `steps[].id`).
  - A step may belong to multiple features or to none — coverage is not required, so small plans carry no busywork.
  - `features:` is **declarative metadata only**: nothing in `run` / `detail` / `jira` reads it. The sole readers are the smell checks (below) and the later feature-health ledger.
  - Left out of frontmatter on rewrite when empty — same as the empty `files`/`gate`/`depends_on` lists, which `write_plan`'s `exclude_defaults` dump drops, so existing plans stay unchanged.

### `PLAN_FORMAT.md` — `### Defaults`

- **Extend the prose paragraph** below the `steps[].X` defaults table (the sentence beginning "No defaults are applied to plan-level…"). Add that `features` is optional and **defaults to an empty list** (not `null`), left out on rewrite when empty. Do **not** add a row to the table — that table is per-step (`steps[].X`); `features` is plan-level, like `lessons`/`test_command`.

### `PLAN_FORMAT.md` — `### Validation rules`

- **Append three rules** to the numbered "The parser rejects the plan when:" list, mirroring how the existing step-graph rules (duplicate id, unknown `depends_on`, cycle) are phrased:
  - A feature `id` is not kebab-case.
  - Two features share the same `id`.
  - A feature's `steps:` entry references a step id that does not exist in the plan.
- **Note** that these three are enforced by step 1's `Plan._validate_features` (`@model_validator(mode="after")`), a sibling of the existing `Plan._validate_graph` — so a `features:` block that dangles after a `split`/`merge` renumber fails loudly rather than silently.

### `PLAN_FORMAT.md` — new `## Smell checks (advisory)` section

- **Insert one H2 section** between `## Body sections (advisory-checked)` and `## Canonical step layout …`. This placement keeps it beside the existing advisory-behavior section rather than minting a command tutorial — PLAN_FORMAT.md documents no commands.
- **Open with the shared contract:** these are deterministic, **no-Claude** heuristics that flag known-brittle plan shapes at author time. They run inside `plan-tool validate` (printed under the `OK:` verdict) and inside the `plan-tool completeness-audit` deterministic battery (a `### Smells (advisory)` report section and a `checks.smells` group in `--json`). They are **advisory**: they never flip the exit code, never enter the `--iterate` apply loop, and `--fail-on-findings` does not fire on them (it keys on validation/blocking findings only). Cite the exit-code convention.
- **Document the suppression / escape-hatch check** (step 2's `detect_suppression_shape`): flags a step or feature whose stated purpose is to *suppress / downgrade / bypass / exempt / silence / disable* **an existing audit gate, check, finding, or severity**. It keys on a **verb→gate-object intent**, not a bare keyword — so a step that merely *describes or implements* suppression handling (including a "suppression-shape detector" step itself) does **not** trip it. Emits the lowest advisory severity with a dismissible rationale; legitimate cases exist (e.g. "suppress duplicate notifications"). Works on a bare step even when no `features:` block is present.
- **Document the self-referential check** (step 2's `detect_self_referential_features`): flags a feature whose set of files overlaps a **configured** validation/convergence-machinery path set. That set is repo-specific, so it is read from project config (`.plan-tool/config.json`, block `smell_checks`, key `validation_machinery_paths`, via `plan_tool/project_config.py:validation_machinery_paths`) and the check is **inert when the set is unconfigured** — plan-tool's own paths are never hardcoded. Requires a `features:` block (it keys on a feature's set of files).
- **Record the deferral of the unfalsifiable-feature check** in the same section: a third smell shape — a declared feature with no acceptance criterion bound to it — is **deferred**, because feature-tagging acceptance criteria (a `[feature-id]` marker convention on acceptance bullets) does not exist today; revisit once that convention is in use. State it as deferred so the doc is the standing record, matching the plan's `## Deferred`.
- **Confirm the exact rendered labels** (`### Smells (advisory)`, `checks.smells`, and validate's advisory block heading) against what steps 3/4 actually land before quoting them — the doc must match the code strings, not the sibling-detail guesses.

## Tests

### Verification (non-code step)

This is a **non-code** step — it changes no production code, so there are no unit tests and no test-ordering directive. Verify the artifact directly:

- **`features:` schema fidelity** — the documented `features:` field names (`id` / `title` / `steps`) match step 1's landed `plan_tool/schema.py` `Feature` model; the three documented validation rules match `Plan._validate_features`.
- **Smell-check fidelity** — the two documented checks match step 2's `detect_suppression_shape` / `detect_self_referential_features` behavior and severity; the config block/key (`smell_checks` / `validation_machinery_paths`) matches `plan_tool/project_config.py:validation_machinery_paths`.
- **Surface labels** — the documented surfaces (`validate` advisory block, completeness `### Smells (advisory)` section and `checks.smells` JSON group) match the strings steps 3/4 render.
- **Advisory claim** — the doc's "never flips the exit code / `--fail-on-findings` does not fire on smells" statement matches the exit-code convention and steps 3/4 behavior.
- **Markdown integrity** — the new H2 anchor and any in-doc links resolve; section ordering (`Body sections` → `Smell checks` → `Canonical step layout`) is intact.
- **Deferral recorded** — the unfalsifiable-feature check appears as deferred with its blocking reason.

## Acceptance criteria

- `PLAN_FORMAT.md`'s frontmatter schema YAML block contains a `features:` entry with `id` / `title` / `steps` sub-fields.
- `### Field semantics` has a `**features**` bullet stating it is plan-level, optional, default empty, declarative-only, and left out on rewrite when empty.
- `### Validation rules` lists the three feature rules: non-kebab id, duplicate id, and a `steps:` entry that doesn't resolve.
- A `## Smell checks (advisory)` section exists, documents both the suppression-shape and self-referential checks, states they are advisory (exit code unaffected, `--fail-on-findings` does not fire on them), and names where each surfaces (`validate`, `completeness-audit` report + `--json`).
- The self-referential check's config source (`.plan-tool/config.json` `smell_checks.validation_machinery_paths`) and its inert-when-unconfigured behavior are documented.
- The unfalsifiable-feature check is documented as **deferred**, with the missing acceptance-criteria tagging convention named as the reason.
- No `docs/cli/` change is made (no new flag or subcommand — `features:` is a frontmatter field).
- All documented symbol/field names and rendered labels match the code that steps 1–4 land at HEAD.

## References

- [Validators — Pydantic Docs](https://docs.pydantic.dev/latest/concepts/validators/) — `@model_validator(mode='after')` semantics behind the three feature validation rules this doc states.
- [Fields — Pydantic Docs](https://docs.pydantic.dev/latest/concepts/fields/) — `Field(default_factory=list)` default semantics, the basis for documenting `features:` as defaulting to empty and being left out on rewrite.
- [YAML Ain't Markup Language (YAML 1.2.2) Specification](https://yaml.org/spec/1.2.2/) — confirms how the `features:` block sequence/mapping is represented in the frontmatter being documented.

## Deferred

- **Adding `features:` to the worked `## Example` block** — left out to avoid churn; the schema block plus the inline example in `### Field semantics` already show the shape. Add a feature to the Example only if a later step proves it's needed for clarity.
- **Documenting the unfalsifiable-feature check as active** — that check is itself deferred in code (it needs the `[feature-id]` acceptance-criteria tagging convention); this doc only records the deferral.
- **`docs/cli/` regeneration** — no CLI flag or subcommand is added by this plan, so no per-subcommand reference change is owed. If a later flag such as `--no-smell-checks` lands, its `docs/cli/` regen is a separate owned step.
- **Documenting the part-2 feature-health ledger / finding→feature attribution** — out of this plan's scope; it ships with the part-2 plan that consumes `features:`.
