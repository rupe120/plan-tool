---
title: Feature Health Declaration And Smell Checks
status: planning
priority: medium
enforce_step_tests: true
steps:
- id: 1
  title: Add Feature model and optional Plan.features field with kebab-id, unique-id,
    and step-resolution validation in the model_validator
  files:
  - plan_tool/schema.py
  - plan_tool/create.py
  - tests/test_parser.py
  complexity: medium
  change_type: feature
  detail: docs/implementation-plans/plan-details/feature-health-declaration-and-smell-checks/01-feature-model-optional-plan-features.md
  status: current
- id: 2
  title: Add deterministic suppression-shape and self-referential smell detectors
    in review.py, reading the validation-machinery path set from project config (inert
    when unconfigured)
  files:
  - plan_tool/review.py
  - plan_tool/project_config.py
  - tests/test_review.py
  - tests/test_project_config.py
  complexity: medium
  change_type: feature
  depends_on:
  - 1
  detail: docs/implementation-plans/plan-details/feature-health-declaration-and-smell-checks/02-deterministic-suppression-shape-self.md
- id: 3
  title: Surface advisory smell findings through the completeness-audit deterministic
    layer (report + JSON), excluded from the blocking-finding gate
  files:
  - plan_tool/cli/completeness_phases.py
  - plan_tool/cli/completeness_cmd.py
  - plan_tool/completeness_report.py
  - tests/cli/test_completeness_cmd.py
  complexity: medium
  change_type: feature
  depends_on:
  - 2
  detail: docs/implementation-plans/plan-details/feature-health-declaration-and-smell-checks/03-surface-advisory-smell-findings-through.md
- id: 4
  title: Run the smell checks from `validate` and print advisory rationales before
    any Claude spend (rc reflects completion, never findings)
  files:
  - plan_tool/cli/inspect.py
  - tests/cli/test_inspect_cmds.py
  complexity: low
  change_type: feature
  depends_on:
  - 2
  detail: docs/implementation-plans/plan-details/feature-health-declaration-and-smell-checks/04-run-smell-checks-validate-print.md
- id: 5
  title: Document the `features:` frontmatter field and the advisory smell checks
    in PLAN_FORMAT.md, and record the deferral of the unfalsifiable-feature check
  files:
  - PLAN_FORMAT.md
  complexity: low
  change_type: non-code
  depends_on:
  - 1
  - 2
  - 3
  - 4
  detail: docs/implementation-plans/plan-details/feature-health-declaration-and-smell-checks/05-document-features-frontmatter-field.md
---
# Feature Health Declaration And Smell Checks

## Overview

Add a **feature layer** to plans plus immediate, deterministic author-time feedback on known-brittle shapes. Two pieces: (1) an optional `features:` declaration in the plan frontmatter — named capabilities, each mapping to the steps that implement it; (2) a set of **deterministic smell checks** (no Claude) that flag features/steps whose *shape* tends to produce brittle, churning plans. All smell checks are **advisory** — none flips the exit code (`--fail-on-findings` remains the only opt-in). `features:` is purely declarative metadata that changes no existing run/detail/jira behavior. This part is self-contained and useful on its own, and is the prerequisite for part 2's feature-aware audit attribution + ledger, which depends on the `features:` field added here.

## Problem statement

The `merge-steps-executor` plan ran four completeness audits. A `type_impure` concept — a persisted flag whose job was to *suppress* the mixed-step finding the merge itself produced — escalated `HIGH → CRITICAL` and fanned out into three sub-findings across three steps before it was cut and replaced with a "dominant `change_type`" rule. Two shapes made it brittle, both detectable **at author time, deterministically**:

- It was a **suppression / escape-hatch**: its stated purpose was to silence an existing quality gate.
- It was **self-referential**: it modified the completeness/convergence machinery that was auditing it (`completeness_cmd.py`), so the audit could never stabilize.

Neither shape is surfaced today. And there is no unit above the *step* to name the capability ("type-impure convergence") that these shapes belong to — so even when an audit flags the symptoms, nothing ties them to one capability the operator could choose to extract or cut. The `features:` declaration adds that unit; the smell checks read it.

## Architecture

### Part A — `features:` in the plan frontmatter

Add an optional `Feature` model and a `features: list[Feature]` field to `plan_tool/schema.py:Plan` (the `Plan` model at `schema.py:137` declares `model_config = ConfigDict(extra="forbid")`, so the field must be added to the model, not relied upon as an extra). Default `Field(default_factory=list)` so every existing plan — which declares none — parses byte-identically.

A `Feature` is a capability above the step layer (steps map to *files*; features map to *steps*, and may span several):

```yaml
features:
  - id: merge-transform        # kebab-case slug, unique within the plan
    title: Pure merge transform
    steps: [1]
  - id: merge-orchestration
    title: Orchestrator + safety/migration
    steps: [2]
  - id: type-impurity          # the misfit — would have visibly spanned 3 steps
    title: Type-impure convergence
    steps: [2, 4, 5]
```

Validation (mirror `Plan._validate_graph`, the `@model_validator(mode="after")` at `schema.py:191`): feature `id`s unique; every `steps:` entry resolves to a real step id; ids are kebab-case. A step may belong to multiple features and a step may belong to none — do **not** require total coverage (that would force busywork on small plans). `features:` is purely declarative metadata; it changes no existing run/detail/jira behavior. Remapping `features.steps` through a structural step renumber is **out of scope for this part**: the `split`/`merge` step-renumbering functionality is still being implemented, so the feature-remap is deferred to a follow-up rather than bound to a surface that is still changing. Until it lands, `_validate_features` re-checks feature references whenever the plan is parsed/validated.

### Part B — deterministic smell checks (no Claude)

Cheap author-time heuristics that catch known-brittle shapes regardless of audit history. All **advisory** — each emits a finding with a plain-language rationale; none flips the exit code (exit-code convention; `--fail-on-findings` remains the only opt-in). Run them in the deterministic layer that already front-runs the conceptual audit (the correctness/deterministic checks invoked by `completeness-audit`), and surface them from `validate` as well so they fire before any Claude spend.

- **Suppression / escape-hatch shape** — a feature or step whose stated purpose is to *suppress / downgrade / bypass / exempt / silence / disable* **an existing audit gate, check, or finding**. `type_impure` was literally "suppress the mixed-step finding." **Precision is the hard part, not recall.** A bare keyword match is wrong: it false-positives on any step that merely *describes* or *implements* suppression handling rather than *being* a gate-suppression — including this plan's own "suppression-shape detector" step and the merge plan's rejected-alternative prose, exactly the meta-plans most likely to declare features. So the match must key on a **verb→object intent where the object is a gate/check/finding/severity** (e.g. "downgrade the mixed-step finding", "bypass the purity gate"), **not** a standalone keyword. A co-occurring schema/config signal (the step also touches a schema/config file) is **not** a match input and does not affect the decision — it is appended to the finding's rationale as operator-facing enrichment after a match has already been made; the check emits a single lowest-severity finding with a binary match and carries no confidence dimension. **Scan both the step/feature title and the step's detail-body (`## Summary`/`## Why`) — detail-body scanning is in-scope, not deferred.** Title-only scanning has near-zero recall on the motivating shape: the `type_impure` case stated its suppressing purpose in its rationale/detail, not its title (a real step title reads "Add a persisted `change_type` flag," never "suppress the mixed-step finding"), so a title-only check could never catch the very shape it is built to catch. **The same precision contract must hold over multi-sentence detail-body prose, not just short titles.** Detail-body scanning re-exposes the self-description false positive across longer text: step 2's *own* Summary ("flags a step/feature whose stated purpose is to suppress/bypass an existing audit gate") carries the exact verb→gate-object adjacency the detector keys on, yet is a *description of the check*, not a gate-suppression. To stay precise across prose the match must key on **what the suppress-verb's subject refers to**, not on grammatical person. The motivating `type_impure` prose is third-person — "a persisted flag **whose job was to** suppress the mixed-step finding" — and so is the meta self-description — "flags a step **whose stated purpose is to** suppress an existing audit gate". Person does not separate them; both are the same construction, "[noun] whose [purpose] is to suppress [gate-object]". What separates them is the **referent of the subject**: in the motivating case the suppressing actor *is the concrete artifact this plan unit introduces* (the `change_type` flag the step builds, or the step/feature itself), so the unit is declaring its own deliverable's suppressing purpose — that **trips**. In the detector description the suppressing actor is a *quantified or hypothetical other unit the prose reasons over or matches against* — "a step *that* suppresses…", "any step whose purpose is to bypass…", "the detector/check that…" — where the suppressor is the detector's object, not the unit's own output; that does **not** trip. So the check fires only when the suppress-verb's subject denotes the unit's own concrete deliverable (a named artifact it adds, or "this step/feature"), and stays silent when the subject is a class of units the prose describes — the shape of every detector/audit-machinery description, including this plan's own suppression-detector steps. Step 2 must pin this trip/non-trip contract with **detail-body fixtures**, not title fixtures alone, and the trip fixture must use realistic third-person `type_impure` phrasing (a named artifact whose purpose is to suppress an existing gate), not an invented first-person sentence. Pin it to the **lowest advisory severity** and emit a rationale the operator can dismiss — legitimate cases exist (e.g. "suppress duplicate notifications"). Works on a bare step even when no `features:` block is present (so it is the one check useful pre-declaration).
- **Self-referential feature** — a feature whose files (via its steps' `step.files`) overlap the validation/convergence machinery the audit itself runs through. For *this* repo that set is concrete (`completeness_cmd.py`, `review.py`, `gates.py`, `convergence.py`, `scope_guard.py`, `drift_detection.py`); for an arbitrary repo it is **not** knowable, so this check reads its path set from **project config** (`.plan-tool/config.json`) and is **inert when unconfigured** — never hardcode plan-tool's own paths into the shipped tool. Requires the `features:` block (it keys on a feature's file footprint).
- **Unfalsifiable feature** — a declared feature with no acceptance criterion bound to it. This needs acceptance criteria to be feature-taggable, which is not how they are written today (free prose). **Either** define the minimal tagging convention (acceptance bullets carry a `[feature-id]` marker) as part of this work **or** defer this specific check to a follow-up; do not block parts A/B on it. Flag the choice explicitly in the plan.

## References

- [Validators — Pydantic Docs](https://docs.pydantic.dev/latest/concepts/validators/) — Defines `@model_validator(mode='after')` semantics and return-value contract — the exact mechanism for mirroring `Plan._validate_graph` to enforce unique feature ids, resolvable `steps:` references, and kebab-case ids.
- [Configuration (ConfigDict) — Pydantic Docs](https://docs.pydantic.dev/latest/api/config/) — Documents `model_config = ConfigDict(extra='forbid')` and its ValidationError behavior — explains why the new `features:` field must be declared on the `Plan` model rather than passed as an extra.
- [Fields — Pydantic Docs](https://docs.pydantic.dev/latest/concepts/fields/) — Covers `Field(default_factory=list)` and default semantics — needed so `Plan.features` defaults to empty and existing plans parse byte-identically.
- [Models — Pydantic Docs](https://docs.pydantic.dev/latest/concepts/models/) — Reference for defining nested BaseModel types and model composition — the basis for adding the new `Feature` submodel and embedding a `list[Feature]` on `Plan`.
- [PyYAML Documentation](https://pyyaml.org/wiki/PyYAMLDocumentation) — Canonical PyYAML reference for `safe_load`/`safe_dump` round-tripping — relevant to parsing and re-emitting the plan frontmatter when serializing the new `features:` block.
- [YAML Ain't Markup Language (YAML 1.2.2) Specification](https://yaml.org/spec/1.2.2/) — The authoritative YAML grammar — consulted to confirm how block sequences/mappings (the `features:` list of id/title/steps) are represented in the machine-readable frontmatter.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

- **Finding → feature attribution and the cross-audit brittleness ledger** — that is part 2 (`feature-health-2-attribution-and-ledger.md`), which depends on the `features:` field this part adds.
- **Changing run / detail / jira behavior.** `features:` is declarative metadata; nothing downstream of authoring reads it except the smell checks here and the part-2 ledger.
- **Auto-inferring a `features:` decomposition** for plans that lack one — a later convenience once the manual field is proven.

## Risks

- **Self-referential check is not general.** Severity: scoping. The validation-machinery path set is repo-specific; shipping hardcoded plan_tool paths would couple the tool to its own source tree. Mitigation: config-driven and inert when unconfigured.
- **Smell-check false positives.** Severity: UX. Suppression-keyword and self-referential checks are heuristics. Mitigation: advisory only, each with a plain-language rationale; never gate the exit code on them.
- **Unfalsifiable check has an unowned dependency.** Severity: scoping. It needs an acceptance-criteria → feature tagging convention that does not exist today. Mitigation: define the minimal convention here or defer the check; don't assume a mechanism that isn't there.
- **`features:` drift after structural edits.** Severity: correctness. A `features:` block can reference a step id that a future `split`/`merge` renumber shifts away. Mitigation: the feature-remap through structural renumbers is **out of scope here** (the `split`/`merge` functionality is still being implemented) and deferred to a follow-up; `_validate_features` re-checks references whenever the plan is parsed/validated.

## Testing

**Per-step test strategy** (derived from each step's `change_type`):

- step 1 (feature) — unit tests added with the implementation; green before completion.
- step 2 (feature) — unit tests added with the implementation; green before completion.
- step 3 (feature) — unit tests added with the implementation; green before completion.
- step 4 (feature) — unit tests added with the implementation; green before completion.
- step 5 (non-code) — verification appropriate to the artifacts; no test-ordering directive.

## Acceptance criteria

- `plan_tool/schema.py` gains a `Feature` model and an optional `Plan.features: list[Feature]` (default empty); a plan with no `features:` block parses byte-identically to today, and a `features:` block with a duplicate id, a non-kebab id, or a `steps:` entry that doesn't resolve raises a validation error. The inertness claim is scoped to **run/detail/jira** behavior; `create --iterate` authoring gains a fail-fast — the reconciliation write-back re-validates the reconciled model (re-firing both `@model_validator(mode="after")`s), so even a feature-less plan whose reconciled graph is latently invalid now raises at that site instead of persisting unvalidated.
- The suppression / escape-hatch smell check runs without Claude and flags a feature or step whose stated purpose is to suppress/bypass an existing audit gate/check/finding, with a dismissible rationale; it works on a bare step with no `features:` block. It keys on a verb→gate-object intent, **not** a bare keyword — a step that merely *describes or implements* suppression handling (e.g. this plan's own suppression-detector step) does **not** trip it. It scans both the title and the step's detail-body (`## Summary`/`## Why`), so the motivating `type_impure` shape — whose suppressing purpose lives in its rationale prose, not its anodyne title — is caught; a title-only check would have near-zero recall on that case.
- The self-referential smell check flags a feature whose file footprint overlaps the configured validation-machinery path set, and is inert when the set is unconfigured.
- The unfalsifiable-feature check is either implemented behind a defined acceptance-criteria tagging convention or explicitly deferred — the plan states which.
- All smell checks are advisory: exit code reflects completion, not findings (exit-code convention); `--fail-on-findings` remains the only way to flip rc.
- `PLAN_FORMAT.md`'s frontmatter spec documents the `features:` field and the advisory smell checks. (No `docs/cli/` change: `features:` is a frontmatter field, not a CLI flag, and this plan adds no new subcommand or flag — if a later flag like `--no-smell-checks` is introduced, `docs/cli/` regen becomes a separate owned step.)
- No new import cycles; `schema.py` stays a stdlib/pydantic leaf.

## Deferred

- **Unfalsifiable-feature smell check** — postponed: it needs an acceptance-criteria → feature tagging convention (`[feature-id]` markers on acceptance bullets) that does not exist today, and standing up that convention is a separate concern from parts A/B. Revisit once feature-tagged acceptance criteria are in use.
- **Remapping `features.steps` through `split`/`merge` renumbers** — deferred: the `split`/`merge` step-renumbering functionality is still being implemented, so binding the feature-remap to it is out of scope for this part and left to a follow-up. Until then, `_validate_features` re-checks feature references whenever the plan is parsed/validated.
- **Live self-referential demonstration in plan-tool's own repo** — deferred to operator config: no step seeds plan-tool's own `.plan-tool/config.json` `validation_machinery_paths`, so the self-referential check stays inert here even though steps 2/3 modify that machinery (`review.py`, `completeness_phases.py`, `completeness_cmd.py`, `completeness_report.py`). Exercising the self-referential half end-to-end is left to operator-supplied config.
