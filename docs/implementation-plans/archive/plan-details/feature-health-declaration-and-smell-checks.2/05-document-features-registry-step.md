> **Auto-archived**: this plan was swept on 2026-06-18 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 5 — Document the `features` registry, the `step.features` tag, and the advisory smell checks in `PLAN_FORMAT.md`

## Summary

Documents the feature-health layer in `PLAN_FORMAT.md` so the format spec matches the schema steps 1–2 add: the plan-level `features:` registry (`Feature` = `{id, title}`), the per-step `steps[].features` tag, the **advisory** feature-ref checks (unique kebab-case registry ids; every `step.features` id points to a registry id), and the two no-Claude smell heuristics (suppression-shape, self-referential-feature). The single most important design fact the doc must carry: these checks are **advisory, not parse-fatal** — the parser enforces only types, so a malformed feature block never breaks `run`/`jira`/`detail`. This is a **non-code** edit to one file. On green, `PLAN_FORMAT.md` documents `features:` across the four frontmatter surfaces (yaml schema block, Field semantics, Defaults, Validation rules) plus a new `## Smell checks (advisory)` H2, and records the unfalsifiable-feature check explicitly as **Deferred** with its unblock condition.

## Table of Contents

- [Why](#why) — what the spec is missing now and why the doc lands in this step.
- [Files (creates vs edits)](#files-creates-vs-edits) — the one file this step edits.
- [Implementation](#implementation) — the five surfaces in `PLAN_FORMAT.md` and exactly what each gains.
- [Tests](#tests) — verification for a non-code step (no unit tests).
- [Acceptance criteria](#acceptance-criteria) — checkable conditions on green.
- [References](#references) — the pydantic docs subset relevant to documenting the advisory-not-parse-fatal choice.
- [Deferred](#deferred) — the unfalsifiable-feature check and other out-of-scope items.

## Why

`PLAN_FORMAT.md` is the reference humans and coding agents read to learn the frontmatter contract, but steps 1–2 add three new fields (`Plan.features`, `Step.features`, plus the `Feature` model) and an advisory check layer that the spec does not mention. Leaving them undocumented makes the new layer invisible to anyone authoring a plan and breaks the doc's stated job — it claims to mirror the enforced contract in code. This step closes that gap. It also pins the one subtle property a reader could get wrong: the feature checks emit dismissible findings at author time and never raise a `ValidationError`, so they belong in a new advisory-behavior section, not in the parser's reject list.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `PLAN_FORMAT.md` — five edits: (1) add `features:` (plan-level) and `features:` (per-step) to the fenced yaml block under `## Frontmatter schema`; (2) add `features` and `steps[].features` entries to `### Field semantics`; (3) add a `steps[].features` row to the `### Defaults` table and mention plan-level `features` in the prose paragraph after that table; (4) note in `### Validation rules` that feature checks are advisory, not parse-fatal; (5) add a new `## Smell checks (advisory)` H2 between `## Body sections (advisory-checked)` and `## Canonical step layout …`.

## Implementation

**Confirm names against landed code first.** Steps 1–4 are not merged at HEAD — `Feature`, `Plan.features`, `Step.features`, `validate_feature_refs`, and the project-config accessor do not yet exist in `plan_tool/schema.py`, `plan_tool/review.py`, or `plan_tool/project_config.py`, and the completeness-audit report + `validate` surfacing this section's "Where they run" claim describes is wired by steps 3–4 in `plan_tool/cli/completeness_phases.py`, `plan_tool/completeness_report.py`, and `plan_tool/cli/inspect.py`. Step 5 `depends_on: 1, 2, 3, 4`, so before writing, re-grep all of that landed code and copy the **actual** field names, the kebab/uniqueness rule wording, the config key, the rendered labels, and the surfacing behavior from it — do not trust the names below or the sibling detail files (`01-feature-model-optional-plan-features.md`, `02-advisory-feature-ref-validation.md`), which are pre-implementation drafts. The plan's design is fixed (step → feature ownership, advisory checks); only the exact identifiers and wiring need a final read.

### `## Frontmatter schema` — the fenced yaml block

- **Add the plan-level `features:` registry** after the `registered_by:` line and before `steps:`, matching the existing comment style:
  ```yaml
  features: # optional. Registry of capability ids → titles a plan declares.
    - id: string   # required. kebab-case, unique within the plan.
      title: string # required. Human-facing capability name.
  ```
- **Add the per-step tag** inside the `steps[]` block (e.g. after `allowed_mentions:`):
  ```yaml
  features: [string, ...] # default []. Registry ids this step implements.
  ```
- Both default empty, so existing plans declaring neither serialize unchanged.

### `### Field semantics`

- **Add a `**`features`** (plan-level)`** entry near `registered_by`. State:
  - It is a **registry only** — a list of `{id, title}` objects mapping a stable capability `id` (a kebab-case slug) to a human title. It declares no behavior on its own.
  - **Ownership runs step → feature, not feature → step.** Each step owns the ids it implements via `steps[].features`; the registry just supplies the id→title map. There is deliberately **no** `Feature.steps` list — because a tag references a slug, a `split`/`merge` step renumber **cannot dangle it** (the tag rides with the step).
  - The only thing the schema enforces is **types** (a list of `{id, title}` objects). Uniqueness, kebab-case, and reference checks are **advisory** — see the new `## Smell checks (advisory)` section. A typo never breaks parsing, so `run`/`jira`/`detail` (which call `parse_plan` and ignore features) stay inert.
- **Add a `**`steps[].features`**`** entry near `steps[].allowed_mentions`. State:
  - A list of registry `id`s this step implements. A step may tag zero, one, or several; a feature may be tagged by several steps. **Total coverage is not required** (no busywork on small plans).
  - Each id should point to a registry `id`; a dangling tag is an **advisory** finding, never a parse error.
  - Elided on rewrite when empty (inherited from `write_plan`'s `exclude_defaults` — same as `files`/`gate`).

### `### Defaults`

- **Add one table row:** `| steps[].features | [] |`.
- **Do not put plan-level `features` in the table** — that table is per-step (`steps[].X`). Mention plan-level `features` in the prose paragraph after the table (line beginning "No defaults are applied…"), beside `lessons`/`test_command`: `features` is optional, defaults to an empty list, and is left out of frontmatter when empty.

### `### Validation rules`

- This numbered list is the **parser's reject set** (parse-fatal). The feature semantic checks are **not** in it.
- Add a short note after the numbered list: the parser enforces only the **types** of `features` / `steps[].features` (and rule 7's unknown-key rejection still applies inside a `Feature`). Uniqueness, kebab-case ids, and `steps[].features` resolution are **advisory** checks that run at author time and emit findings — never a parse error. Point the reader to `## Smell checks (advisory)`.

### New H2 — `## Smell checks (advisory)`

- **Placement:** insert it between `## Body sections (advisory-checked)` and `## Canonical step layout (input shape for ``create --from-existing``)`. This sits parallel to the other advisory-behavior section, not inside a field's semantics and not as a command tutorial (the spec documents no commands).
- **Lead the section** with the shared contract: these are cheap, no-Claude heuristics over the plan + feature layer. Each emits a **lowest-severity, dismissible** finding. None flips the exit code — the exit code reflects completion, and `--fail-on-findings` remains the only opt-in (link the existing convention if cited elsewhere).
- **Where they run:** the deterministic layer that front-runs the conceptual `completeness-audit` (surfaced in its report) and `plan-tool validate` (so they fire before any Claude spend). State that they surface in the report/`validate` output but are structurally kept out of the apply loop and the blocking gate.
- **Document the feature-ref checks** (`validate_feature_refs`): registry ids must be unique and kebab-case; every `steps[].features` id must point to a registry id. A violation is an advisory finding, not a `ValidationError`.
- **Document the suppression-shape check.** A step or feature whose **own deliverable's** stated purpose is to *suppress / downgrade / bypass / exempt / silence / disable* an existing audit gate, check, finding, or severity. It keys on a **verb → gate-object intent**, not a bare keyword, and scans both the title and the detail body (`## Summary` / `## Why`). It does **not** trip on a unit that merely *describes or implements* suppression handling (a suppression-detector step, rejected-alternative prose). Works on a bare step even with no `features:` block.
- **Document the self-referential-feature check.** A feature whose **file footprint** — the union of each tagged step's **full footprint** (`Step.all_files` = `files` + `creates`, **not** the literal `step.files`, which excludes `creates`) over the steps whose `step.features` tag includes that feature id — overlaps the validation/convergence machinery the audit itself runs through. Confirm the exact derivation against step 2's landed `detect_self_referential_features` and document the footprint it actually computes. The machinery path set is **read from project config** (`.plan-tool/config.json`; confirm the exact key against step 2's landed `project_config.py` accessor — the draft names it `smell_checks.validation_machinery_paths`) and the check is **inert when unconfigured**. Note explicitly: the tool never hardcodes its own paths, so the check is a no-op in any repo that hasn't configured the set. **Document how to populate the key** to turn the check from inert to live: a repo-local `.plan-tool/config.json` path list whose entries are **full repo-relative paths matching `step.all_files`** (e.g. `plan_tool/cli/completeness_cmd.py`), **not basenames** (`completeness_cmd.py` yields zero normalized-path overlap and a silently inert check). This config key is the only switch that activates the self-referential check.
- **Record the unfalsifiable-feature check as Deferred** (see Deferred section below) so the spec is the standing record of the deferral.

## Tests

### Verification (non-code step)

This step changes only `PLAN_FORMAT.md` — no production code, no unit tests, no test-ordering directive. Verify the artifact:

- **Doc-vs-code accuracy** — every field name, default, the kebab/uniqueness rule wording, and the config key in the new prose match the **landed** symbols in `plan_tool/schema.py`, `plan_tool/review.py`, and `plan_tool/project_config.py` (steps 1–2). The new `## Smell checks (advisory)` section's "Where they run" claims (surfacing in the completeness-audit report and in `plan-tool validate` output) describe wiring landed by **steps 3–4**, so also grep `plan_tool/cli/completeness_phases.py`, `plan_tool/completeness_report.py` (step 3), and `plan_tool/cli/inspect.py` (step 4) to confirm the surfacing behavior exists before documenting it (the doc's own rule is "if doc and code disagree, the code wins").
- **Surface completeness** — all four frontmatter surfaces (yaml block, Field semantics, Defaults, Validation rules) mention `features`/`steps[].features`, and the new `## Smell checks (advisory)` H2 exists in the stated position.
- **Markdown / anchor check** — the new H2 renders, its slug (`#smell-checks-advisory`) is valid, and any in-doc links resolve; no broken or duplicate headings.
- **Defaults table scope** — `steps[].features` appears as a table row; plan-level `features` appears only in the post-table prose, not as a `steps[].X` row.
- **Deferred fidelity** — the unfalsifiable-feature check is named as Deferred with its unblock condition (the `[feature-id]` acceptance-criteria tagging convention), matching the plan's `## Deferred`.

## Acceptance criteria

- `PLAN_FORMAT.md`'s fenced yaml schema block shows a plan-level `features:` registry (`{id, title}`) and a per-step `features:` tag, both optional and empty-default.
- `### Field semantics` has a `features` (plan-level) entry and a `steps[].features` entry, each stating step → feature ownership and the advisory-not-parse-fatal property.
- `### Defaults` has a `steps[].features` → `[]` row; plan-level `features` is described in the post-table prose, not as a table row.
- `### Validation rules` states the parser enforces only types for the feature fields and points to the advisory smell-checks section.
- A new `## Smell checks (advisory)` H2 exists between `## Body sections (advisory-checked)` and `## Canonical step layout …`, documenting the feature-ref checks, suppression-shape, self-referential-feature, and the deferred unfalsifiable check.
- The self-referential check's doc states it reads its path set from project config and is inert when unconfigured (no hardcoded plan-tool paths), and documents how to populate the `smell_checks.validation_machinery_paths` key to make the check live (full repo-relative paths matching `step.all_files`, not basenames).
- Every documented identifier matches the landed code of steps 1–2 at the time the doc is written.

## References

- [Models — Pydantic Docs](https://docs.pydantic.dev/latest/concepts/models/) — Confirms how the `Feature` model and `Plan.features` / `Step.features` fields are defined, so the doc describes the real shape.
- [Fields — Pydantic Docs](https://docs.pydantic.dev/latest/concepts/fields/) — `Field(default_factory=list)` and default semantics, behind the "empty-default, elided when empty" wording for both fields.
- [Validators (model_validator / field_validator) — Pydantic Docs](https://docs.pydantic.dev/latest/concepts/validators/) — Explains why the feature checks are plain advisory functions, not a parse-time `@model_validator` — the central design point the doc must convey accurately.

## Deferred

- **Unfalsifiable-feature smell check** — a declared feature with no acceptance criterion bound to it. Documented in the new `## Smell checks (advisory)` section **as deferred**, with the unblock condition: it needs a feature-tagged acceptance-criteria convention (a `[feature-id]` acceptance-bullet tagging scheme) that does not exist today, where criteria are free prose. The reference doc is the standing record of this deferral, mirroring the plan's `## Deferred`.
- **`docs/cli/` changes** — none. `features` / `step.features` are frontmatter fields, not CLI flags, so the generated per-subcommand reference is untouched.
- **Documenting completeness-audit / validate output internals** — the JSON keys and console section labels for how smells render belong to steps 3–4's surfaces; `PLAN_FORMAT.md` documents the format and the advisory behavior, not the command output schema.
