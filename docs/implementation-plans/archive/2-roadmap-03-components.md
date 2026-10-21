> **Auto-archived**: this plan was swept on 2026-08-05 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

---
title: Roadmap 03 Components
intent: '`plan-tool roadmap` writes a gated `03-components.md` that divides the
  domain into logical components, each owning entity ids from `01-domain.md`,
  applying patterns and discharging constraints from `02-constraints.md`, and
  surviving the same revision-against-feedback loop stages 1–2 already use. A
  human can catch a bad decomposition **before** seeds are emitted.'
status: completed
priority: medium
enforce_step_tests: true
steps:
- id: 1
  title: Add the 03-components.md artifact contract with paths, rows, parse, and render
  intent: Give stage 3 a strict, round-trippable shape for component inventory rows
    before any gate or orchestrator can consume them.
  files:
  - plan_tool/roadmap_artifacts.py
  - tests/test_roadmap_artifacts.py
  complexity: high
  change_type: feature
  detail: docs/implementation-plans/plan-details/roadmap-03-components/01-03-components-md-artifact-contract.md
  status: done
- id: 2
  title: Widen the gate envelope and row helpers for a third artifact
  intent: Make the existing table-driven gate runner able to carry domain plus constraints
    plus components without a per-stage orchestrator branch.
  files:
  - plan_tool/roadmap_gates.py
  - tests/test_roadmap_gates.py
  complexity: medium
  change_type: feature
  depends_on:
  - 1
  detail: docs/implementation-plans/plan-details/roadmap-03-components/02-widen-gate-envelope-row-helpers-third.md
  status: done
- id: 3
  title: Add the five components traceability gates and run_components_gates
  intent: Enforce entity coverage, pattern presence, and prioritized-constraint discharge
    as deterministic retry text, not reviewer judgment.
  files:
  - plan_tool/roadmap_gates.py
  - tests/test_roadmap_gates.py
  complexity: high
  change_type: feature
  depends_on:
  - 2
  detail: docs/implementation-plans/plan-details/roadmap-03-components/03-five-components-traceability-gates-run.md
  status: done
- id: 4
  title: Document 03-components.md in ROADMAP_FORMAT.md with gate-clean examples
  intent: Make the third artifact discoverable and copy-safe, with every rule traced
    to the code symbols that enforce it.
  files:
  - ROADMAP_FORMAT.md
  - tests/test_roadmap_format.py
  complexity: medium
  change_type: non-code
  depends_on:
  - 1
  - 2
  - 3
  detail: docs/implementation-plans/plan-details/roadmap-03-components/04-document-03-components-md-roadmap.md
  status: done
- id: 5
  title: Add the components stage with roadmap-components.md and a STAGES table row
  intent: Run a gated third stage that reads domain and constraints off disk and writes
    03-components.md through the existing retry loop.
  files:
  - plan_tool/roadmap.py
  - plan_tool/cli/roadmap_cmd.py
  - tests/test_roadmap.py
  - tests/cli/test_roadmap_cmd.py
  creates:
  - plan_tool/prompts/roadmap-components.md
  complexity: high
  change_type: feature
  depends_on:
  - 3
  - 4
  detail: docs/implementation-plans/plan-details/roadmap-03-components/05-components-stage-roadmap-components-md.md
  status: done
- id: 6
  title: Run stage 3 on an existing brief and record human-review outcomes
  intent: Prove the components artifact is reviewable on a real 01/02 pair before
    the arc docs claim position 03 shipped.
  files:
  - BACKLOG.md
  complexity: medium
  change_type: non-code
  depends_on:
  - 5
  detail: docs/implementation-plans/plan-details/roadmap-03-components/06-run-stage-on-existing-brief-record.md
  status: done
- id: 7
  title: Reconcile BACKLOG 208 and sweep roadmap operator docs for stage 3
  intent: 'Leave every operator-facing doc describing three shipped stages and mark
    arc position 03 done in BACKLOG #208.'
  files:
  - BACKLOG.md
  - CLAUDE.md
  - CAPABILITIES.md
  - RUNBOOK.md
  - USE_CASES.md
  - docs/ARCHITECTURE.md
  - docs/ROADMAP_WALKTHROUGH.md
  complexity: medium
  change_type: non-code
  depends_on:
  - 4
  - 5
  - 6
  detail: docs/implementation-plans/plan-details/roadmap-03-components/07-reconcile-backlog-208-sweep-roadmap.md
  status: done
---
# Roadmap 03 Components

## Overview

Arc position 03 of the `roadmap-NN-*` group (anchor: `BACKLOG.md` **#208**). Positions 01 and 02 shipped stages 1–2, the eleven relation gates, revision-against-feedback, and `--from-stage N` re-entry. This position adds **artifact stage 3** — gated `03-components.md` — so `plan-tool roadmap` partitions the domain into logical components before seeds are emitted. Positions 04 (plan derivation + draft seeds) and 05 (framework lenses) stay unauthored; this one reaches into neither. The plan's final docs/status step reconciles `BACKLOG.md` #208 when the work ships: mark arc position 03 shipped, leave the entry in place until the whole arc ships, and file any deferral this plan creates.

## Problem statement

Two artifacts name what the system is about and what it trades on (`01-domain.md`, `02-constraints.md`). Nothing yet says how that domain **partitions into buildable units**. Today that hop is manual: `docs/ROADMAP_WALKTHROUGH.md` § 5 records the procedure a human applies — slice coherent rule/workflow/entity sets, write seeds by hand with the ids as provenance. #208's headline promise is an *ordered set of plan seeds*; without components there is no reviewable intermediate between constraints and that set, and position 04 would invent the partition while emitting seeds.

The collaborative Framing restored this artifact after a one-shot-quality cut: its value is as a **review surface**, not as a better first draft than a competent human. A confidently-wrong decomposition that a reviewer never sees poisons every seed below it the same way a bad domain model does.

## Architecture

**Stage-as-data holds, or this is where it breaks.** Position 01's bet: a stage is `(prompt file, artifact path, parser, renderer, gate set)` and a further stage appends a row to `STAGES` rather than an orchestrator branch. This is the first stage that must *read two upstream artifacts* and write a third shape. If the table has to widen (fan-out, multi-file output, rewriting an upstream), that is the finding — widen the smallest amount that admits stage 3, and record why. Do not pre-emptively redesign the skeleton.

**Components anchor to entity ids — settled 2026-08-02; do not re-open.** Stage-1 id overlap under regeneration: entities **85%**, workflows 60%, business rules 30%, decisions 25%, field names **0 of 11**. A component that keys on a rule or decision id does not survive a stage-1 re-author; one that keys on entity ids does. Field names are forbidden as anchors. (Under revision mode, continuity gates hold ids in place — the entity-id rule is about what downstream *cites*, including what position 04 will emit.)

**What a component is.** A logical unit of the system: the entities it owns, the patterns (system-level and component-level) that shape it, and the constraint ids those patterns discharge. It is not a plan, not a directory layout, and not a service boundary yet — those judgments belong to position 04's sizing and dispositions. Frontmatter carries the inventory the gates check; prose carries what a reviewer reads.

**Traceability gates — relations over ids, never merit.** Six binary observables land as **five** `check_*` functions (`check_component_pattern_references` covers items 3 and 4 together):

1. Every component names ≥1 entity id that `01-domain.md` defines.
2. Every entity id in `01-domain.md` appears in ≥1 component.
3. Both `system_patterns` and `component_patterns` are non-empty on the artifact as a whole.
4. Every component names ≥1 defined pattern id (from the union of both pattern collections).
5. Every component that claims to discharge constraints names only constraint ids `02-constraints.md` defines.
6. Every constraint whose attribute is `prioritized` is discharged by ≥1 component.

Same shape/relation split stages 1–2 already use: parse accepts dangling refs; gates return violations. No gate may acquire an opinion about whether a partition or pattern choice is *good* — that is the reviewer's role.

**Revision mode is inherited, not rebuilt.** Position 02's predecessor load, continuity gates, feedback lifecycle, and shared `roadmap-revision.md` wrapper already apply to every stage in the table. Stage 3 gets a design-row collection that continuity and feedback-target resolution must include; it does not get a second feedback channel or a second settle/remove contract. The #208 "convergence loop on the components stage" is this stage under that existing loop — bounded gate retry plus human feedback re-entry — not a new completeness-style converge inside the verb.

**Decisions stay typed rows.** Pattern and partition calls that a later reader would question land as `decisions` with rejected alternatives, same contract as stages 1–2. Load-bearing guesses stay `pending`.

**Implementation surfaces:** `roadmap_artifacts.py` (`03-components.md` path, component/pattern row types, parse/render, design-row / feedback-target resolution); `roadmap_gates.py` (five traceability `check_*` functions covering the six Architecture rules above, stage-3 gate runner, continuity/settled/feedback integrity over new design rows); `roadmap.py` (one new `STAGES` entry; prompt assembly feeding domain + constraints as upstream); `prompts/roadmap-components.md` (authoring contract; revision stays the shared wrapper).

**Allowed behavior changes:** A third stage runs after constraints when `from_stage` allows it. New artifact path, new row kinds, new gates, one new prompt file. First-run stages 1–2 unchanged. Revision/feedback semantics unchanged except that component ids are valid design-row / feedback targets. No new flag; `--from-stage 3` re-enters at components the same way `2` re-enters at constraints.

**Allowed reorganization:** Widen `RoadmapStage` / the gate envelope **only** if appending a table row cannot express "read two upstream artifacts." Prefer the smallest additive change. No extraction of a shared seed-emission helper — that is position 04 / #168.

## Input

This plan consumes two upstream roadmap artifacts and the revision infrastructure positions 01–02 already ship.

- **`roadmaps/<slug>/01-domain.md`** — entity ids every component must anchor to (plus the other domain rows decisions may cite); full entity coverage is a gate invariant. System- and component-level patterns live on `03-components.md`, not here.
- **`roadmaps/<slug>/02-constraints.md`** — constraint ids and attributes (`prioritized`, `traded-away`, `not-load-bearing`); only `prioritized` constraints require discharge by ≥1 component.
- **Position 02 revision contract** — predecessor artifact load, continuity gates, feedback lifecycle, and the shared `prompts/roadmap-revision.md` wrapper; stage 3 adds component ids to design-row / feedback-target resolution without a second channel.
- **Existing `STAGES` table (stages 1–2)** — first-run behavior for stages 1–2 must remain unchanged; stage 3 appends one row that reads both upstream artifacts.

Verification limits: gate checks are binary id-relation observables only — no automated judgment of partition or pattern quality.

## References

- [PyYAML Documentation](https://pyyaml.org/wiki/PyYAMLDocumentation) — Official PyYAML API reference for safe_load/safe_dump and error handling when parsing and rendering 03-components.md YAML frontmatter.
- [YAML Ain't Markup Language (YAML) revision 1.2.2](https://yaml.org/spec/1.2.2/) — Normative YAML 1.2 data-language spec for designing component, pattern, and decision row frontmatter that parses consistently.
- [dataclasses — Data Classes](https://docs.python.org/3/library/dataclasses.html) — Python stdlib reference for defining frozen row types (components, patterns, decisions) and generated equality used across roadmap_artifacts.py.
- [enum — Support for enumerations](https://docs.python.org/3/library/enum.html) — Python stdlib reference for StrEnum closed vocabularies (constraint dispositions, feedback states, target kinds) enforced during parse and gate checks.
- [typing — Support for type hints](https://docs.python.org/3/library/typing.html) — Python stdlib reference for Callable and TypeVar annotations on stage parsers, renderers, and the five stage-3 traceability gate runners.
- [string — Template strings](https://docs.python.org/3/library/string.html#template-strings) — Python stdlib reference for Template.safe_substitute used in roadmap.py to assemble the stage-3 prompt from upstream domain and constraints artifacts.
- [pytest: temporary directories (tmp_path)](https://docs.pytest.org/en/stable/how-to/tmp_path.html) — Official pytest guide for hermetic tmp_path fixtures when writing stage-3 parse, gate, and --from-stage 3 revision tests.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

- Position 04 (plan derivation + draft seeds) — unauthored; this plan does not emit seeds or size plans.
- Position 05 (framework lenses) — unauthored; no lens work.
- Shared seed-emission helper extraction (BACKLOG #168 / position 04) — separate arc position.
- A new completeness-style convergence loop inside the `roadmap` verb — stage 3 uses position 02's existing revision loop.
- A second feedback channel or second settle/remove contract for stage 3.
- Pre-emptive redesign of the stage-as-data skeleton beyond the smallest widening that admits stage 3.
- Encoding partition quality or "right-sized" components as a gate — reviewer judgment only.

## Risks

- **Stage-as-data meets a third shape.** First real load of the table bet (position 01 named this unresolved). If the envelope or prompt assembly needs a branch, stop and widen deliberately rather than paper over it.
- **Prose-mention gate scales with row count** (arc lesson 3). Components add inventory ids that must appear in prose; expect retry pressure and keep gates cheap. Do not raise `MAX_STAGE_ATTEMPTS` as the first reach — #215 closed with no action on budget size.
- **Partition subjectivity.** Two reviewers will disagree on seams. That is what feedback is for; resist the urge to encode "right-sized" as a gate.
- **Constraint discharge vs. `traded-away` / `not-load-bearing`.** Only `prioritized` constraints require a discharging component; a gate that demands coverage of every constraint invents work for attributes the ranking already set aside.

## Testing

Hermetic, stubbed invokers per `TESTING.md`:

- Stage 3 writes a parseable artifact.
- Each of the five traceability gate functions rejects its corresponding violation shapes and clears a conforming one (Architecture items 3–4 share `check_component_pattern_references`).
- A component naming a missing entity / constraint fails; an orphan entity fails.
- A `prioritized` constraint with no discharging component fails; a `traded-away` or `not-load-bearing` constraint with none passes.
- Design-row continuity and settled-decision guards cover component ids.
- Feedback targeting a component id resolves.
- A first run of stages 1–2 alone is unchanged.
- `--from-stage 3` revises with predecessor + feedback in the prompt.

One real run: existing gated 01/02 on disk (`cfp-review` or `toollib` brief), stage 3 produces a reviewable decomposition whose entity coverage is total and whose prioritized constraints are named. Read stdout and stderr together (arc lesson 1).

**Per-step test strategy** (derived from each step's `change_type`):

- step 1 (feature) — tests covering the behavior this step changes; green before completion.
- step 2 (feature) — tests covering the behavior this step changes; green before completion.
- step 3 (feature) — tests covering the behavior this step changes; green before completion.
- step 4 (non-code) — verification appropriate to the artifacts rather than unit tests.
- step 5 (feature) — tests covering the behavior this step changes; green before completion.
- step 6 (non-code) — verification appropriate to the artifacts rather than unit tests.
- step 7 (non-code) — verification appropriate to the artifacts rather than unit tests.

## Acceptance criteria

- `plan-tool roadmap <slug> --from-existing <brief>` (or `--from-stage 3` over existing 01/02) writes gated `03-components.md` under `roadmaps/<slug>/`.
- Every entity is in ≥1 component; every component names ≥1 defined entity and ≥1 pattern; every `prioritized` constraint is discharged by ≥1 component.
- Both `system_patterns` and `component_patterns` are non-empty on `03-components.md` (artifact-level half of gate 3).
- Component ids participate in revision continuity and feedback targets.
- `ROADMAP_FORMAT.md` documents the artifact and names the code that enforces each rule.
- Walkthrough § 7 lists position 03 as shipped; § 5 still owns the manual hop to seeds until position 04.
- **`BACKLOG.md` #208 is reconciled when this ships** — position 03 marked shipped; positions 04–05 left as the remaining arc. Authoring does not remove the entry.

## Deferred

- **Emitting seeds and the component→plan mapping** — position 04; this plan
  stops at the gated review surface.
- **Framework lenses and pillar-coverage gates** — position 05; stage 3 ships
  against the generic attribute list already on `02-constraints.md`.
- **A closed pattern catalog** — patterns stay free text the reviewer can
  redirect; a vocabulary is a later lens concern, not this artifact's contract.
- **Whether stage-as-data needed widening** — answer when step 5 lands; step 7's
  deferral-filing records the result (including a negative: no
  `RoadmapStage` / orchestrator branch beyond the step-2 `components`
  envelope slot). Do not close this before that evidence exists.
- **Carve B of the decision-record rule** — settled 2026-08-05, user-confirmed
  **narrow**: must not mint about the removed row itself; a decision on a
  surviving row about a gap the removal opened is the positive branch. Recorded
  in `BACKLOG.md` #208 and `roadmap-revision.md`.
- **BACKLOG #215's retry-budget calibration** — components add
  prose-mention inventory that increases retry pressure; step 6 measures it on
  the real run but does not change `MAX_STAGE_ATTEMPTS`.
