> **Replaced**: this file has been superseded by `docs/implementation-plans/2-feature-health-declaration-and-smell-checks.md`.
> Preserved here for history; do not edit.

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

Validation (mirror `Plan._validate_graph`, the `@model_validator(mode="after")` at `schema.py:191`): feature `id`s unique; every `steps:` entry resolves to a real step id; ids are kebab-case. A step may belong to multiple features and a step may belong to none — do **not** require total coverage (that would force busywork on small plans). `features:` is purely declarative metadata; it changes no existing run/detail/jira behavior. Re-validate `steps:` references after structural edits (`split`/`merge` renumber ids) so a feature naming a vanished step id fails loudly rather than silently dangling.

### Part B — deterministic smell checks (no Claude)

Cheap author-time heuristics that catch known-brittle shapes regardless of audit history. All **advisory** — each emits a finding with a plain-language rationale; none flips the exit code (exit-code convention; `--fail-on-findings` remains the only opt-in). Run them in the deterministic layer that already front-runs the conceptual audit (the correctness/deterministic checks invoked by `completeness-audit`), and surface them from `validate` as well so they fire before any Claude spend.

- **Suppression / escape-hatch shape** — a feature or step whose title/description matches an intent to *suppress / downgrade / bypass / exempt / silence / disable* an existing check. `type_impure` was literally "suppress the mixed-step finding." Keyword + light intent match. Works on a bare step even when no `features:` block is present (so it is the one check that is useful pre-declaration). Advisory — legitimate cases exist (e.g. "suppress duplicate notifications"), so the rationale must let the operator dismiss it.
- **Self-referential feature** — a feature whose files (via its steps' `step.files`) overlap the validation/convergence machinery the audit itself runs through. For *this* repo that set is concrete (`completeness_cmd.py`, `review.py`, `gates.py`, `convergence.py`, `scope_guard.py`, `drift_detection.py`); for an arbitrary repo it is **not** knowable, so this check reads its path set from **project config** (`.plan-tool/config.json`) and is **inert when unconfigured** — never hardcode plan-tool's own paths into the shipped tool. Requires the `features:` block (it keys on a feature's file footprint).
- **Unfalsifiable feature** — a declared feature with no acceptance criterion bound to it. This needs acceptance criteria to be feature-taggable, which is not how they are written today (free prose). **Either** define the minimal tagging convention (acceptance bullets carry a `[feature-id]` marker) as part of this work **or** defer this specific check to a follow-up; do not block parts A/B on it. Flag the choice explicitly in the plan.

## Out of scope

- **Finding → feature attribution and the cross-audit brittleness ledger** — that is part 2 (`feature-health-2-attribution-and-ledger.md`), which depends on the `features:` field this part adds.
- **Changing run / detail / jira behavior.** `features:` is declarative metadata; nothing downstream of authoring reads it except the smell checks here and the part-2 ledger.
- **Auto-inferring a `features:` decomposition** for plans that lack one — a later convenience once the manual field is proven.

## Risks

- **Self-referential check is not general.** Severity: scoping. The validation-machinery path set is repo-specific; shipping hardcoded plan_tool paths would couple the tool to its own source tree. Mitigation: config-driven and inert when unconfigured.
- **Smell-check false positives.** Severity: UX. Suppression-keyword and self-referential checks are heuristics. Mitigation: advisory only, each with a plain-language rationale; never gate the exit code on them.
- **Unfalsifiable check has an unowned dependency.** Severity: scoping. It needs an acceptance-criteria → feature tagging convention that does not exist today. Mitigation: define the minimal convention here or defer the check; don't assume a mechanism that isn't there.
- **`features:` drift after structural edits.** Severity: correctness. A `features:` block can reference a step id that `split`/`merge` renumbered away. Mitigation: validate `steps:` references on every load and after structural edits; a dangling reference fails validation loudly.

## Acceptance criteria

- `plan_tool/schema.py` gains a `Feature` model and an optional `Plan.features: list[Feature]` (default empty); a plan with no `features:` block parses byte-identically to today, and a `features:` block with a duplicate id, a non-kebab id, or a `steps:` entry that doesn't resolve raises a validation error.
- The suppression / escape-hatch smell check runs without Claude and flags a feature or step whose description signals suppressing/bypassing an existing check, with a dismissible rationale; it works on a bare step with no `features:` block.
- The self-referential smell check flags a feature whose file footprint overlaps the configured validation-machinery path set, and is inert when the set is unconfigured.
- The unfalsifiable-feature check is either implemented behind a defined acceptance-criteria tagging convention or explicitly deferred — the plan states which.
- All smell checks are advisory: exit code reflects completion, not findings (exit-code convention); `--fail-on-findings` remains the only way to flip rc.
- `docs/cli/` (drift-guarded) and `PLAN_FORMAT.md`'s frontmatter spec document the `features:` field.
- No new import cycles; `schema.py` stays a stdlib/pydantic leaf.
