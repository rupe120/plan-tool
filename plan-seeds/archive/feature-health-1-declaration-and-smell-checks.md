# Plan seed: feature-health (1 of 2) — `features:` declaration + author-time smell checks

This file is a `plan-tool create` input. Use it via:

```
plan-tool create --from-existing plan-seeds/feature-health-1-declaration-and-smell-checks.md
```

It is **not** itself a plan — `plan-tool create` consumes the prose below
and proposes a step decomposition; the author then runs `plan-tool detail`
per step.

> **Order:** this is **part 1 of 2**. It ships the foundation — a feature
> **category** layer steps tag themselves with — plus the cheap, no-Claude
> author-time checks that ride on it. Part 2 —
> [`feature-health-2-attribution-and-ledger.md`](feature-health-2-attribution-and-ledger.md) —
> makes the completeness audit feature-aware and adds the cross-audit
> brittleness ledger that is the actual payoff. Part 2 depends on the feature
> layer this part adds.

---

## Overview

A feature is a **category**, not a functional unit: a named capability used to
**group correctness/conceptual findings across audit runs**, so part 2 can spot
a capability that keeps throwing CRITICAL/HIGH and tell the operator to revisit
the feature request. It is emphatically **not** something `run`/`detail`/`jira`
consume. Two pieces here:

1. a feature **registry** in the plan frontmatter (`features: [{id, title}]`)
   plus a per-**step** `features: [id, …]` tag naming the capabilities that
   step implements;
2. a set of **deterministic smell checks** (no Claude) that flag steps/features
   whose *shape* tends to produce brittle, churning plans.

**Ownership runs step → feature, not feature → step.** A step owns the list of
features it implements; the registry only supplies the id→title mapping. This
is deliberate and load-bearing: a `step.features` tag references a stable
**slug**, so a `split`/`merge` step **renumber cannot dangle it** — the tag
rides with the step. Contrast the rejected design where a feature owned a
`steps: [1,2]` list of step *numbers*, which a renumber shifts out from under.

**The feature layer is inert for every parse-based command.** All semantic
checks (id uniqueness, kebab-case, a `step.features` id resolving to the
registry) are **advisory author-time** checks — they do **not** live in a
parse-time `@model_validator` and never raise. This is intentional: nothing in
`run`/`jira`/`detail` reads features, so a malformed or drifted feature block
must not manufacture a hard failure in commands that ignore it. The schema
validates only *types*; meaning is checked by the advisory layer below.

## Problem statement — grounded in a real case

The `merge-steps-executor` plan ran four completeness audits. A `type_impure`
concept — a persisted flag whose job was to *suppress* the mixed-step finding
the merge itself produced — escalated `HIGH → CRITICAL` and fanned out into
three sub-findings, spreading across three steps, before it was cut and
replaced with a "dominant `change_type`" rule. Two shapes made it brittle and
both are detectable **at author time, deterministically**:

- It was a **suppression / escape-hatch**: its stated purpose was to silence
  an existing quality gate.
- It was **self-referential**: it modified the completeness/convergence
  machinery that was auditing it (`completeness_cmd.py`), so the audit could
  never stabilize.

Neither shape is surfaced today. And there was no unit above the *step* to name
the capability ("type-impure convergence") those shapes belong to — so even
when an audit flagged the symptoms, nothing tied them to one capability the
operator could choose to extract or cut. The feature category supplies that
unit; the smell checks read it; part 2's ledger tracks it across runs.

## Architecture

### Part A — the feature registry + per-step tags

Add to `plan_tool/schema.py`:

- a `Feature` model — `id: str`, `title: str` — and an optional
  `Plan.features: list[Feature]` registry field
  (`Field(default_factory=list)`);
- an optional `Step.features: list[str]` tag field
  (`Field(default_factory=list)`) naming the feature ids that step implements.

The `Plan` model at `schema.py:137` declares `model_config =
ConfigDict(extra="forbid")`, so both fields must be declared on the models, not
relied upon as extras. Defaults are empty, so every existing plan — which
declares neither — parses **byte-identically**.

```yaml
features:                        # registry: id → title only
  - id: merge-transform
    title: Pure merge transform
  - id: merge-orchestration
    title: Orchestrator + safety/migration
  - id: type-impurity            # the misfit — visibly tagged on 3 steps below
    title: Type-impure convergence
steps:
- id: 1
  title: Pure merge transform
  features: [merge-transform]
- id: 2
  title: Orchestrator + change_type flag
  features: [merge-orchestration, type-impurity]
- id: 4
  title: …
  features: [type-impurity]
- id: 5
  title: …
  features: [type-impurity]
```

A step may tag zero, one, or several features; a feature may be tagged by
several steps. Do **not** require total coverage (that would force busywork on
small plans).

**Validation is advisory, not parse-fatal.** The schema enforces only types
(`features` is a list of `Feature`; `step.features` is a list of `str`).
Everything semantic lives in a single advisory function —
`validate_feature_refs(plan)` — invoked from the author-time surfaces
(`create`/`detail` write-back, `validate`, and the smell-check layer), **never**
from a `@model_validator(mode="after")`:

- registry `id`s are unique and kebab-case;
- every `step.features` id resolves to a registry `id`.

A violation emits an advisory finding, not a `ValidationError`. Because
`run`/`jira`/`detail` all call `parse_plan` and none read features, routing
these checks through a parse-time validator would brick those commands on a
typo in metadata they ignore — so they don't. (This resolves a real design
tension from the predecessor seed, where mirroring `_validate_graph` into a
feature validator would have made a drifted feature block a hard `run`/`jira`
failure.)

### Part B — deterministic smell checks (no Claude)

Cheap author-time heuristics that catch known-brittle shapes regardless of
audit history. All **advisory** — each emits a lowest-severity finding with a
plain-language, dismissible rationale; none flips the exit code (exit-code
convention; `--fail-on-findings` remains the only opt-in). Run them in the
deterministic layer that already front-runs the conceptual audit (the
correctness/deterministic checks invoked by `completeness-audit`), and surface
them from `validate` too so they fire before any Claude spend.

- **Suppression / escape-hatch shape** — a step or feature whose stated purpose
  is to *suppress / downgrade / bypass / exempt / silence / disable* **an
  existing audit gate, check, finding, or severity**. `type_impure` was
  literally "suppress the mixed-step finding." Precision is the hard part:
  match a **verb → gate-object intent** ("downgrade the mixed-step finding",
  "bypass the purity gate"), **not** a bare keyword — a step that merely
  *describes or implements* suppression handling (this plan's own
  suppression-detector step; rejected-alternative prose) must **not** trip. The
  separating signal: the suppressor is the unit's *own concrete deliverable*
  (the flag it adds, or "this step"), versus a *class of other units the prose
  reasons over* ("any step that suppresses…", "the detector that…"). Scan both
  the title and the step's detail-body (`## Summary`/`## Why`) — the motivating
  `type_impure` shape stated its suppressing purpose in its rationale, not its
  anodyne title, so a title-only check would have near-zero recall. Pin the
  trip/non-trip contract with **detail-body fixtures** using realistic
  third-person phrasing. Works on a bare step even with no `features:` block —
  the one check useful pre-declaration.
- **Self-referential feature** — a feature whose **file footprint** overlaps the
  validation/convergence machinery the audit itself runs through. With ownership
  reversed, a feature's footprint is the union of `step.files` over the steps
  whose `step.features` tag includes that feature id. For *this* repo that
  machinery set is concrete (`completeness_cmd.py`, `review.py`, `gates.py`,
  `convergence.py`, `scope_guard.py`, `drift_detection.py`); for an arbitrary
  repo it is **not** knowable, so the check reads its path set from **project
  config** (`.plan-tool/config.json`) and is **inert when unconfigured** — never
  hardcode plan-tool's own paths into the shipped tool. Requires the feature
  layer (it keys on a feature's file footprint).
- **Unfalsifiable feature** — a declared feature with no acceptance criterion
  bound to it. This needs acceptance criteria to be feature-taggable, which is
  not how they are written today (free prose). **Defer** this check to a
  follow-up rather than block parts A/B on standing up a `[feature-id]`
  acceptance-bullet tagging convention. State the deferral explicitly.

## Seam citations (verify at HEAD before building)

- `plan_tool/schema.py:137` — `Plan` model, `extra="forbid"` (the new `features`
  registry attaches here); `:59` `Step` (where `Step.features` attaches; also
  the `step.files` footprint source for the self-referential check); `:191`
  `_validate_graph` — the parse-time validator the feature checks deliberately
  do **not** mirror (semantic checks go to the advisory layer instead).
- The deterministic check layer of `completeness-audit` (the correctness /
  files-coherence checks that run before the conceptual Claude audit) and
  `plan-tool validate` — where `validate_feature_refs` and the smell checks
  attach.
- `plan_tool/project_config.py` — the resolved project-config seam
  (`.plan-tool/config.json`) the self-referential path set reads from.
- `PLAN_FORMAT.md` (frontmatter spec) — documents the `features:` registry and
  the `step.features` tag. No `docs/cli/` change: these are frontmatter fields,
  not new flags.

## Out of scope

- **Finding → feature attribution and the cross-audit brittleness ledger** —
  that is part 2 ([`feature-health-2-attribution-and-ledger.md`](feature-health-2-attribution-and-ledger.md)),
  which depends on the feature layer this part adds.
- **Changing run / detail / jira behavior.** The feature layer is declarative
  category metadata; nothing downstream of authoring reads it except the smell
  checks here and the part-2 ledger. Parse stays byte-for-byte inert.
- **Remapping through structural renumbers.** Not needed — `step.features` tags
  reference slugs, not step numbers, so a `split`/`merge` renumber leaves them
  intact. (This is the whole reason ownership is step → feature.)
- **Auto-inferring a feature decomposition** for plans that lack one — a later
  convenience once the manual layer is proven.

## Risks

- **Self-referential check is not general.** Severity: scoping. The
  validation-machinery path set is repo-specific; shipping hardcoded plan_tool
  paths would couple the tool to its own source tree. Mitigation: config-driven
  and inert when unconfigured.
- **Smell-check false positives.** Severity: UX. Suppression and self-referential
  checks are heuristics. Mitigation: advisory only, lowest severity, each with a
  dismissible rationale; never gate the exit code on them.
- **Suppression-check precision over prose.** Severity: UX. The verb→gate-object
  match can false-positive on units that *describe* suppression. Mitigation: key
  on whether the suppressor is the unit's own deliverable vs. a class it reasons
  over; pin with detail-body fixtures.

## Acceptance criteria

- `plan_tool/schema.py` gains a `Feature` model, an optional
  `Plan.features: list[Feature]` registry, and an optional
  `Step.features: list[str]` tag (all default empty); a plan with neither parses
  **byte-identically** to today.
- Semantic feature checks (unique kebab-case registry ids; every `step.features`
  id resolves to the registry) are **advisory** and run at author time
  (`create`/`detail`/`validate`); a violation emits a finding, never a parse-time
  `ValidationError`. `run`/`jira`/`detail` parse a malformed feature block
  without error.
- The suppression smell check runs without Claude and flags a step/feature whose
  *own deliverable's* stated purpose is to suppress/bypass an existing audit
  gate/check/finding, with a dismissible rationale; it keys on verb→gate-object
  intent (not a bare keyword), scans title **and** detail-body, and does **not**
  trip on a step that merely describes/implements suppression handling. Works on
  a bare step with no `features:` block.
- The self-referential smell check flags a feature whose file footprint (union of
  its tagged steps' `step.files`) overlaps the configured validation-machinery
  path set, and is inert when the set is unconfigured.
- The unfalsifiable-feature check is explicitly **deferred** with the reason
  stated (needs a feature-tagged acceptance-criteria convention that does not
  exist today).
- All smell checks are advisory: exit code reflects completion, not findings
  (exit-code convention); `--fail-on-findings` remains the only way to flip rc.
- `PLAN_FORMAT.md`'s frontmatter spec documents the `features:` registry and the
  `step.features` tag.
- No new import cycles; `schema.py` stays a stdlib/pydantic leaf.
