> **Auto-archived**: this plan was swept on 2026-06-18 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

---
title: Feature Health Declaration And Smell Checks
status: completed
priority: medium
enforce_step_tests: true
steps:
- id: 1
  title: Add Feature model, optional Plan.features registry, and optional Step.features
    tag to the schema (types only, no semantic validator)
  files:
  - plan_tool/schema.py
  - tests/test_parser.py
  complexity: low
  change_type: feature
  detail: docs/implementation-plans/plan-details/feature-health-declaration-and-smell-checks/01-feature-model-optional-plan-features.md
  status: done
- id: 2
  title: Add advisory feature-ref validation + a suppression-shape smell detector
    in review.py, surfaced via a new collect_smell_findings collector
  files:
  - plan_tool/review.py
  - tests/test_review.py
  complexity: high
  change_type: feature
  depends_on:
  - 1
  detail: docs/implementation-plans/plan-details/feature-health-declaration-and-smell-checks/02-advisory-feature-ref-validation.md
  status: done
- id: 3
  title: Surface smell/feature-ref findings through the completeness-audit post-loop
    deterministic report layer (add a smell_recs bucket to _DeterministicReport across
    console/JSON/persisted-markdown render surfaces; keep them out of collect_deterministic_findings
    so the --iterate apply loop never tries to apply them)
  files:
  - plan_tool/cli/completeness_phases.py
  - plan_tool/completeness_report.py
  - tests/test_completeness_report.py
  - tests/cli/test_completeness_cmd.py
  complexity: medium
  change_type: feature
  depends_on:
  - 2
  detail: docs/implementation-plans/plan-details/feature-health-declaration-and-smell-checks/03-surface-smell-feature-ref-findings.md
  status: done
- id: 4
  title: 'Run the smell/feature-ref checks from plan-tool validate (advisory, on the
    valid path after the OK: print) so they fire before any Claude spend, preserving
    the rc-on-completion contract (--fail-on-findings remains the only rc flip)'
  files:
  - plan_tool/cli/inspect.py
  - tests/cli/test_inspect_cmds.py
  complexity: medium
  change_type: feature
  depends_on:
  - 2
  detail: docs/implementation-plans/plan-details/feature-health-declaration-and-smell-checks/04-run-smell-feature-ref-checks-plan-tool.md
  status: done
- id: 5
  title: 'Document the features: registry, the step.features tag, and the advisory
    smell checks (with the unfalsifiable-feature check recorded as Deferred) in PLAN_FORMAT.md'
  files:
  - PLAN_FORMAT.md
  complexity: low
  change_type: non-code
  depends_on:
  - 1
  - 2
  - 3
  - 4
  detail: docs/implementation-plans/plan-details/feature-health-declaration-and-smell-checks/05-document-features-registry-step.md
  status: done
---
# Feature Health Declaration And Smell Checks

## Overview

Adds a **feature category** layer to plans and the cheap, no-Claude author-time smell checks that ride on it. A feature is a named capability used to **group correctness/conceptual findings across audit runs** — not a functional unit consumed by `run`/`detail`/`jira`. Two pieces ship here: (1) a feature **registry** in plan frontmatter (`features: [{id, title}]`) plus a per-**step** `features: [id, …]` tag, and (2) a set of **deterministic smell checks** (no Claude) that flag steps whose *shape* tends to produce brittle, churning plans. Ownership runs **step → feature**: a step owns the list of features it implements; the registry only supplies the id→title mapping, so a `split`/`merge` renumber cannot dangle a tag. The feature layer is **inert for every parse-based command** — all semantic checks are advisory author-time checks that never raise, so a malformed feature block can't brick commands that ignore it. This is part 1 of 2; part 2 ([`feature-health-2-attribution-and-ledger.md`](feature-health-2-attribution-and-ledger.md)) makes the completeness audit feature-aware and adds the cross-audit brittleness ledger, depending on the feature layer added here. Part 1 ships the registry as inert foundation: its only active reader is `validate_feature_refs` id-hygiene, with all feature-keyed behavior (finding→feature grouping) arriving in part 2.

## Problem statement

The `merge-steps-executor` plan ran four completeness audits. A `type_impure` concept — a persisted flag whose job was to *suppress* the mixed-step finding the merge itself produced — escalated `HIGH → CRITICAL` and fanned out into three sub-findings across three steps before it was cut and replaced with a "dominant `change_type`" rule.

What drove that author-time churn was the concept's **suppression / escape-hatch shape**: a step's own deliverable — the flag it adds — whose stated purpose is to silence an existing quality gate is a bad concept, and the conceptual audit kept re-poking it across runs. This is the **primary** brittleness signal and the one this part leans on — it is detectable at author time, deterministically, and ships as the **default-on** suppression smell check.

This shape is not surfaced today. And there was no unit above the *step* to name the capability ("type-impure convergence") it belongs to — so even when an audit flagged the symptoms, nothing tied them to one capability the operator could choose to extract or cut. The feature category supplies that unit. The suppression check is deliberately feature-agnostic, so a suppression symptom is surfaced step-level with no capability attribution. Tying a suppression symptom back to a feature is part 2's finding→feature attribution and ledger work, which tracks it across runs.

## Architecture

### Part A — the feature registry + per-step tags

Add to `plan_tool/schema.py`:

- a `Feature` model — `id: str`, `title: str` — and an optional `Plan.features: list[Feature]` registry field (`Field(default_factory=list)`);
- an optional `Step.features: list[str]` tag field (`Field(default_factory=list)`) naming the feature ids that step implements.

The `Plan` model at `schema.py:137` declares `model_config = ConfigDict(extra="forbid")`, so both fields must be declared on the models, not relied upon as extras. Defaults are empty, so every existing plan — which declares neither — parses **byte-identically**.

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

A step may tag zero, one, or several features; a feature may be tagged by several steps. Do **not** require total coverage (that would force busywork on small plans).

**Ownership runs step → feature, not feature → step.** A step owns the list of features it implements; the registry only supplies the id→title mapping. This is deliberate and load-bearing: a `step.features` tag references a stable **slug**, so a `split`/`merge` step renumber **cannot dangle it** — the tag rides with the step. Contrast the rejected design where a feature owned a `steps: [1,2]` list of step *numbers*, which a renumber shifts out from under.

**Validation is advisory, not parse-fatal.** The schema enforces only types (`features` is a list of `Feature`; `step.features` is a list of `str`). Everything semantic lives in a single advisory function — `validate_feature_refs(plan)` — invoked from the author-time surfaces this part wires (the `completeness` deterministic layer and `validate`), **never** from a `@model_validator(mode="after")`. Wiring `validate_feature_refs` into the `create`/`detail` write-back is deferred to a follow-up (see Deferred):

- registry `id`s are unique and kebab-case;
- every `step.features` id resolves to a registry `id`.

A violation emits an advisory finding, not a `ValidationError`. Because `run`/`jira`/`detail` all call `parse_plan` and none read features, routing these checks through a parse-time validator would brick those commands on a typo in metadata they ignore — so they don't. (This resolves a real design tension from the predecessor seed, where mirroring `_validate_graph` into a feature validator would have made a drifted feature block a hard `run`/`jira` failure.)

### Part B — deterministic smell checks (no Claude)

Cheap author-time heuristics that catch known-brittle shapes regardless of audit history. All **advisory** — each emits a lowest-severity finding with a plain-language, dismissible rationale; none flips the exit code (exit-code convention; `--fail-on-findings` remains the only opt-in). `completeness-audit` surfaces them in its **post-loop** deterministic report (after the `--iterate` convergence loop has run), kept out of the pre-loop apply layer so they never enter the apply loop; only `validate` runs them **before** any Claude spend.

- **Suppression / escape-hatch shape** — a step whose stated purpose is to *suppress / downgrade / bypass / exempt / silence / disable* **an existing audit gate, check, finding, or severity**. `type_impure` was literally "suppress the mixed-step finding." Precision is the hard part: match a **verb → gate-object intent** ("downgrade the mixed-step finding", "bypass the purity gate"), **not** a bare keyword — a step that merely *describes or implements* suppression handling (this plan's own suppression-detector step; rejected-alternative prose) must **not** trip. The separating signal is **definite self-reference vs. indefinite class** — the possessive `whose` is shared by both sides and is *not* the discriminator. It trips when the scanned prose names the suppressor with a definite/demonstrative reference to the unit's *own concrete deliverable* ("this step", "the flag it adds"); it does not trip on an *indefinite* class the prose reasons over ("a step", "any step that…") **or a deliverable whose action is to *detect/flag* suppression rather than perform it**. The non-trip families are **illustrative, not a closed enumeration** — they include the `that`-keyed class references ("any step that suppresses…", "the detector that…"), the **indefinite class references** — keyed on the indefinite "a step"/"a feature", not the possessive `whose` ("a step whose purpose is to silence an existing quality gate", "a step/feature whose own deliverable suppresses an existing audit gate") — and **quotation / example references** that name a suppressing purpose as the thing being detected (e.g. prose quoting "suppress the mixed-step finding"). The **binding contract is the suppression self-flag regression**: the landed detector run over every step of this plan's own real detail bundle — including step 5's possessive `whose own deliverable suppresses` documentation prose — must emit **zero** suppression-shape findings — the families above only illustrate the shapes that regression pins, so the guard must cover them rather than match them literally. A suppression-*detector* step, including one whose own `## Summary` describes its deliverable in own-deliverable terms as catching a step "whose own deliverable suppresses an existing audit gate", must **not** trip. Scan both the title and the step's detail-body (`## Summary`/`## Why`) — the motivating `type_impure` shape stated its suppressing purpose in its rationale, not its anodyne title, so a title-only check would have near-zero recall. The detail-body extraction **degrades to title-only when a step has no detail file** (or an empty one) — it does not error — so `validate` (step 4), commonly run on a created-but-not-yet-detailed plan whose steps have no detail file, still runs the check cleanly against titles alone. Pin the trip/non-trip contract with **detail-body fixtures** using realistic third-person phrasing. Works on a bare step even with no `features:` block — the one check useful pre-declaration.
- **Unfalsifiable feature** — a declared feature with no acceptance criterion bound to it. This needs acceptance criteria to be feature-taggable, which is not how they are written today (free prose). **Defer** this check to a follow-up rather than block parts A/B on standing up a `[feature-id]` acceptance-bullet tagging convention. State the deferral explicitly.

### Seam citations (verify at HEAD before building)

- `plan_tool/schema.py:137` — `Plan` model, `extra="forbid"` (the new `features` registry attaches here); `:59` `Step` (where `Step.features` attaches); `:191` `_validate_graph` — the parse-time validator the feature checks deliberately do **not** mirror (semantic checks go to the advisory layer instead).
- The deterministic check layer of `completeness-audit` (the correctness / files-coherence checks that run before the conceptual Claude audit) and `plan-tool validate` — where `validate_feature_refs` and the smell checks attach.
- `PLAN_FORMAT.md` (frontmatter spec) — documents the `features:` registry and the `step.features` tag. No `docs/cli/` change: these are frontmatter fields, not new flags.

## References

- [Models — Pydantic Docs](https://docs.pydantic.dev/latest/concepts/models/) — Canonical reference for defining BaseModel subclasses, which the implementer opens to add the new `Feature` model and the optional `Plan.features` / `Step.features` fields alongside the existing schema models.
- [Fields — Pydantic Docs](https://docs.pydantic.dev/latest/concepts/fields/) — Documents `Field(default_factory=list)` and default semantics, needed to declare the new registry/tag fields as empty-by-default so existing plans parse byte-identically.
- [Configuration (ConfigDict) — Pydantic Docs](https://docs.pydantic.dev/latest/api/config/) — API reference for `ConfigDict`, including `extra='forbid'`, explaining why the new fields must be declared on the models (not passed as extras) and how unknown-key rejection still behaves.
- [Validators (model_validator / field_validator) — Pydantic Docs](https://docs.pydantic.dev/latest/concepts/validators/) — Explains `@model_validator(mode='after')` vs. plain functions, central to the plan's deliberate choice to keep `validate_feature_refs` advisory rather than a parse-time validator that would raise `ValidationError`.
- [Migration Guide (Pydantic V1 → V2) — Pydantic Docs](https://docs.pydantic.dev/latest/migration/) — Maps V2 API names (`ConfigDict`, `model_validator`, `model_config`) used throughout `schema.py`, useful for confirming current idioms when extending the existing pydantic-based schema layer.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

- **Finding → feature attribution and the cross-audit brittleness ledger** — that is part 2 ([`feature-health-2-attribution-and-ledger.md`](feature-health-2-attribution-and-ledger.md)), which depends on the feature layer this part adds.
- **A live consumer of the feature registry in plan-tool's own repo.** Part A (`Plan.features`, `Step.features`) lands **dormant** here: the suppression check is deliberately feature-agnostic and the only feature-keyed check (self-referential) ships inert and is not activated on this repo, so the registry is declarative-only — exercised solely by `validate_feature_refs` id-hygiene and synthetic config in tests. Its end-to-end value waits on part 2's attribution/ledger.
- **Changing run / detail / jira behavior.** The feature layer is declarative category metadata; nothing downstream of authoring reads it except the smell checks here and the part-2 ledger. Parse stays byte-for-byte inert.
- **Remapping through structural renumbers.** Not needed — `step.features` tags reference slugs, not step numbers, so a `split`/`merge` renumber leaves them intact. (This is the whole reason ownership is step → feature.)
- **Auto-inferring a feature decomposition** for plans that lack one — a later convenience once the manual layer is proven.
- **A self-referential / validation-machinery smell check.** Cut by design: in plan-tool the edits a plan proposes target the *plans being developed*, not the tool's own auditing code, so a check that flagged overlap with the audit/run machinery would only create noise. No `validation_machinery_paths` config key, no `project_config.py` accessor, no feature-footprint overlap check ships.

## Risks

- **Smell-check false positives.** Severity: UX. The suppression smell check is a heuristic. Mitigation: advisory only, lowest severity, with a dismissible rationale; never gate the exit code on it.
- **Suppression-check precision over prose.** Severity: UX. The verb→gate-object match can false-positive on units that *describe* suppression. Mitigation: key on whether the suppressor is the unit's own deliverable vs. a class it reasons over; pin with detail-body fixtures.

## Testing

Follow the project's unit-first convention (`tests/test_X.py` mirrors `plan_tool/X.py`); add `@pytest.mark.integration` only for cross-module wiring driven through `main([...])` or an orchestrator.

- **Schema round-trip** (`tests/test_parser.py`): a plan declaring neither `features` nor `step.features` parses **byte-identically** to today; a plan with both parses and exposes `Plan.features` / `Step.features`; `extra="forbid"` still rejects unknown keys.
- **Advisory feature-ref validation** (`tests/test_review.py`): `validate_feature_refs` flags duplicate registry ids, non-kebab-case ids, and a `step.features` id that resolves to no registry id; each as a finding, never a `ValidationError`. Assert `parse_plan` on a malformed feature block returns a valid `Plan` (no raise) so `run`/`jira`/`detail` stay inert.
- **Suppression smell check**: pin the trip/non-trip contract with **detail-body fixtures** using realistic third-person phrasing — a step whose own deliverable suppresses an existing gate trips; a step that merely describes/implements suppression handling (a suppression-detector step, rejected-alternative prose, a "class of units" reference) does **not**. Cover the title-only-anodyne case (purpose stated in `## Summary`/`## Why`, not title), the bare-step-without-`features:` case, and the self-describing-detector body case (a suppression-detector step whose own `## Summary` uses own-deliverable wording like "a step/feature whose own deliverable suppresses an existing audit gate").
- **Suppression self-flag regression** (`tests/test_review.py`): run the landed `collect_smell_findings` over every step of this plan's own real detail bundle (including step 5, whose body carries the possessive `whose own deliverable suppresses` documentation prose) and assert **zero** suppression-shape findings — binds the acceptance bullet to the shipped detector against the actual prose, not a synthetic fixture, so a regex-balance regression that self-flags the plan fails the suite.
- **Exit-code convention**: a plan tripping any smell check still exits 0; only `--fail-on-findings` flips rc.

List existing suites that must still pass: the full `tests/` suite (schema parse, `completeness`, `validate`, `run`/`jira` parse-inertness). When modifying `completeness`/`validate` wiring, run the relevant integration tests for those command paths.

**Per-step test strategy** (derived from each step's `change_type`):

- step 1 (feature) — unit tests added with the implementation; green before completion.
- step 2 (feature) — unit tests added with the implementation; green before completion.
- step 3 (feature) — unit tests added with the implementation; green before completion.
- step 4 (feature) — unit tests added with the implementation; green before completion.
- step 5 (non-code) — verification appropriate to the artifacts; no test-ordering directive.

## Acceptance criteria

- `plan_tool/schema.py` gains a `Feature` model, an optional `Plan.features: list[Feature]` registry, and an optional `Step.features: list[str]` tag (all default empty); a plan with neither parses **byte-identically** to today.
- Semantic feature checks (unique kebab-case registry ids; every `step.features` id resolves to the registry) are **advisory** and run at the author-time surfaces this part wires (`completeness`/`validate`); a violation emits a finding, never a parse-time `ValidationError`. `run`/`jira`/`detail` parse a malformed feature block without error. (`create`/`detail` write-back wiring is deferred — see Deferred.)
- The suppression smell check runs without Claude and flags a step whose *own deliverable's* stated purpose is to suppress/bypass an existing audit gate/check/finding, with a dismissible rationale; it keys on verb→gate-object intent (not a bare keyword), scans title **and** detail-body, and does **not** trip on a step that merely describes/implements suppression handling. Works on a bare step with no `features:` block.
- The landed `collect_smell_findings`, run over every step of this plan's own detail bundle (including step 5's possessive `whose own deliverable suppresses` documentation prose), emits **zero** suppression-shape findings — the shipped detector self-flags no false positive on its own suppression-describing prose.
- All smell checks are advisory: exit code reflects completion, not findings (exit-code convention); `--fail-on-findings` remains the only way to flip rc.
- `PLAN_FORMAT.md`'s frontmatter spec documents the `features:` registry and the `step.features` tag.
- No new import cycles; `schema.py` stays a stdlib/pydantic leaf.

## Deferred

- **`validate_feature_refs` write-back wiring in `create`/`detail`** — this part scopes author-time surfacing to the `completeness` deterministic layer and `validate`; invoking `validate_feature_refs` from the `create`/`detail` write-back is deferred to a follow-up, matching step 2's Deferred.
- **Unfalsifiable-feature check** — a declared feature with no acceptance criterion bound to it. Deferred to a follow-up: it needs a feature-tagged acceptance-criteria convention (a `[feature-id]` acceptance-bullet tagging scheme) that does not exist today, where criteria are written as free prose. Standing up that convention should not block parts A/B.
