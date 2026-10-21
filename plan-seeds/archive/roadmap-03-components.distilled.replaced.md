> **Replaced**: this file has been superseded by `docs/implementation-plans/2-roadmap-03-components.md`.
> Preserved here for history; do not edit.

## Overview

Arc position 03 of the `roadmap-NN-*` group (anchor: `BACKLOG.md` **#208**). Positions 01 and 02 shipped stages 1–2, the eleven relation gates, revision-against-feedback, and `--from-stage N` re-entry. This position adds **artifact stage 3** — gated `03-components.md` — so `plan-tool roadmap` partitions the domain into logical components before seeds are emitted. Positions 04 (plan derivation + draft seeds) and 05 (framework lenses) stay unauthored; this one reaches into neither. The plan's final docs/status step reconciles `BACKLOG.md` #208 when the work ships: mark arc position 03 shipped, leave the entry in place until the whole arc ships, and file any deferral this plan creates.

## Problem statement

Two artifacts name what the system is about and what it trades on (`01-domain.md`, `02-constraints.md`). Nothing yet says how that domain **partitions into buildable units**. Today that hop is manual: `docs/ROADMAP_WALKTHROUGH.md` § 5 records the procedure a human applies — slice coherent rule/workflow/entity sets, write seeds by hand with the ids as provenance. #208's headline promise is an *ordered set of plan seeds*; without components there is no reviewable intermediate between constraints and that set, and position 04 would invent the partition while emitting seeds.

The collaborative Framing restored this artifact after a one-shot-quality cut: its value is as a **review surface**, not as a better first draft than a competent human. A confidently-wrong decomposition that a reviewer never sees poisons every seed below it the same way a bad domain model does.

## Architecture

**Stage-as-data holds, or this is where it breaks.** Position 01's bet: a stage is `(prompt file, artifact path, parser, renderer, gate set)` and a further stage appends a row to `STAGES` rather than an orchestrator branch. This is the first stage that must *read two upstream artifacts* and write a third shape. If the table has to widen (fan-out, multi-file output, rewriting an upstream), that is the finding — widen the smallest amount that admits stage 3, and record why. Do not pre-emptively redesign the skeleton.

**Components anchor to entity ids — settled 2026-08-02; do not re-open.** Stage-1 id overlap under regeneration: entities **85%**, workflows 60%, business rules 30%, decisions 25%, field names **0 of 11**. A component that keys on a rule or decision id does not survive a stage-1 re-author; one that keys on entity ids does. Field names are forbidden as anchors. (Under revision mode, continuity gates hold ids in place — the entity-id rule is about what downstream *cites*, including what position 04 will emit.)

**What a component is.** A logical unit of the system: the entities it owns, the patterns (system-level and component-level) that shape it, and the constraint ids those patterns discharge. It is not a plan, not a directory layout, and not a service boundary yet — those judgments belong to position 04's sizing and dispositions. Frontmatter carries the inventory the gates check; prose carries what a reviewer reads.

**Traceability gates — relations over ids, never merit.** Binary observables only:

1. Every component names ≥1 entity id that `01-domain.md` defines.
2. Every entity id in `01-domain.md` appears in ≥1 component.
3. Every component names ≥1 pattern (system-level and component-level are both recorded; neither collection may be vacuously absent on the artifact as a whole).
4. Every component that claims to discharge constraints names only constraint ids `02-constraints.md` defines.
5. Every constraint whose attribute is `prioritized` is discharged by ≥1 component.

Same shape/relation split stages 1–2 already use: parse accepts dangling refs; gates return violations. No gate may acquire an opinion about whether a partition or pattern choice is *good* — that is the reviewer's role.

**Revision mode is inherited, not rebuilt.** Position 02's predecessor load, continuity gates, feedback lifecycle, and shared `roadmap-revision.md` wrapper already apply to every stage in the table. Stage 3 gets a design-row collection that continuity and feedback-target resolution must include; it does not get a second feedback channel or a second settle/remove contract. The #208 "convergence loop on the components stage" is this stage under that existing loop — bounded gate retry plus human feedback re-entry — not a new completeness-style converge inside the verb.

**Decisions stay typed rows.** Pattern and partition calls that a later reader would question land as `decisions` with rejected alternatives, same contract as stages 1–2. Load-bearing guesses stay `pending`.

**Implementation surfaces:** `roadmap_artifacts.py` (`03-components.md` path, component/pattern row types, parse/render, design-row / feedback-target resolution); `roadmap_gates.py` (five relation checks, stage-3 gate runner, continuity/settled/feedback integrity over new design rows); `roadmap.py` (one new `STAGES` entry; prompt assembly feeding domain + constraints as upstream); `prompts/roadmap-components.md` (authoring contract; revision stays the shared wrapper).

**Allowed behavior changes:** A third stage runs after constraints when `from_stage` allows it. New artifact path, new row kinds, new gates, one new prompt file. First-run stages 1–2 unchanged. Revision/feedback semantics unchanged except that component ids are valid design-row / feedback targets. No new flag; `--from-stage 3` re-enters at components the same way `2` re-enters at constraints.

**Allowed reorganization:** Widen `RoadmapStage` / the gate envelope **only** if appending a table row cannot express "read two upstream artifacts." Prefer the smallest additive change. No extraction of a shared seed-emission helper — that is position 04 / #168.

## Risks

- **Stage-as-data meets a third shape.** First real load of the table bet (position 01 named this unresolved). If the envelope or prompt assembly needs a branch, stop and widen deliberately rather than paper over it.
- **Prose-mention gate scales with row count** (arc lesson 3). Components add inventory ids that must appear in prose; expect retry pressure and keep gates cheap. Do not raise `MAX_STAGE_ATTEMPTS` as the first reach — #215 closed with no action on budget size.
- **Partition subjectivity.** Two reviewers will disagree on seams. That is what feedback is for; resist the urge to encode "right-sized" as a gate.
- **Constraint discharge vs. `traded-away` / `not-load-bearing`.** Only `prioritized` constraints require a discharging component; a gate that demands coverage of every constraint invents work for attributes the ranking already set aside.

## Testing

Hermetic, stubbed invokers per `TESTING.md`:

- Stage 3 writes a parseable artifact.
- Each of the five gates rejects the corresponding violation and clears a conforming one.
- A component naming a missing entity / constraint fails; an orphan entity fails.
- A `prioritized` constraint with no discharging component fails; a `traded-away` or `not-load-bearing` constraint with none passes.
- Design-row continuity and settled-decision guards cover component ids.
- Feedback targeting a component id resolves.
- A first run of stages 1–2 alone is unchanged.
- `--from-stage 3` revises with predecessor + feedback in the prompt.

One real run: existing gated 01/02 on disk (`cfp-review` or `toollib` brief), stage 3 produces a reviewable decomposition whose entity coverage is total and whose prioritized constraints are named. Read stdout and stderr together (arc lesson 1).

## Acceptance criteria

- `plan-tool roadmap <slug> --from-existing <brief>` (or `--from-stage 3` over existing 01/02) writes gated `03-components.md` under `roadmaps/<slug>/`.
- Every entity is in ≥1 component; every component names ≥1 defined entity and ≥1 pattern; every `prioritized` constraint is discharged by ≥1 component.
- Component ids participate in revision continuity and feedback targets.
- `ROADMAP_FORMAT.md` documents the artifact and names the code that enforces each rule.
- Walkthrough § 7 lists position 03 as shipped; § 5 still owns the manual hop to seeds until position 04.
- **`BACKLOG.md` #208 is reconciled when this ships** — position 03 marked shipped; positions 04–05 left as the remaining arc. Authoring does not remove the entry.
