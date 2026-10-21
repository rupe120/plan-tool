> **Replaced**: this file has been superseded by `docs/implementation-plans/2-roadmap-04-plan-derivation.md`.
> Preserved here for history; do not edit.

## Overview

Arc position **04** of the `roadmap-NN-*` group (anchor: `BACKLOG.md` **#208**). Positions 01–03 shipped stages 1–3, revision-against-feedback, and gated `03-components.md`; this plan adds **artifact stage 4** — gated `04-roadmap.md` plus draft seeds under the roadmap slug — and closes the concept→seeds loop. Position 05 (framework lenses) stays unauthored.

`plan-tool roadmap` writes a gated `04-roadmap.md` that maps components to an ordered plan list (with merge / split / `cross-cutting` dispositions), emits `SEED_FORMAT.md`-conformant draft seeds citing component provenance, and offers a recommend-only `--apply` + confirm path that moves accepted drafts into `plan-seeds/`. Printed next-steps are runnable `create --from-existing` lines; `create`'s distill `SplitProposal` surfaces a recommend-only pointer at this verb. Green stage-4 completion does **not** write `plan-seeds/` unless `--apply` (+ confirm or `-y`). Auto-running `create` is not the hand-off.

## Problem statement

Three gated artifacts name the domain, the tradeoffs, and the logical partition. The hop to *buildable plan seeds* is still manual: `docs/ROADMAP_WALKTHROUGH.md` § 5 is the only written procedure, and a human must invent the component→plan sizing, write each seed by hand, and carry inter-plan assumptions. #208's headline promise is an **ordered set of `create --from-existing` seeds**; without stage 4 the verb stops one review surface short of that set.

The Framing still governs: stage 4 **proposes** a mapping and draft seeds; a human reviews (and may redirect via feedback) before `--apply` mutates the seed directory.

## Architecture

**Stage-as-data again.** Append one `STAGES` row that reads domain + constraints + components and writes `04-roadmap.md`. Same shape/relation split: parse accepts dangling refs; gates return violations. If the table cannot express "write one artifact *and* emit draft seed files beside it," widen the smallest amount that admits dual output and record why — do not pre-emptively redesign the skeleton. Draft seeds are **side products of the stage**, not a fifth Claude call and not a second verb.

**What `04-roadmap.md` carries.** Frontmatter inventory the gates check; prose a reviewer reads. At minimum:

- **Plans** — id, title, disposition (`keep` one component / `merge` several / `split` one component into several plans / `cross-cutting`), the component id(s) each plan owns, sizing rationale keyed to those components.
- **Ordering** — explicit sequence; dependents name what they assume landed.
- **Inter-plan assumptions** — in prose (and optionally typed rows if parse needs them for gates); nothing silently carries them.
- **Accumulated decision log** — citations into upstream `decisions` rows; new partition/sizing calls that a later reader would question land as this artifact's own `decisions` rows (same typed contract as stages 1–3).

**Dispositions are closed vocabulary; sizing rationale is free text.** `cross-cutting` is for CI / observability / auth-plumbing work that is not one component's owner — #208 names this; do not invent a parallel escape.

**Draft seeds inherit the walkthrough's four load-bearing additions** (§ 5): (1) provenance naming all four artifacts and forbidding re-litigation of settled upstream decisions; (2) the domain ids the slice binds to; (3) settled decisions as a fence with rejected alternatives; (4) constraint ids this slice discharges, with dispositions. Shape per `SEED_FORMAT.md` including the full scope-contract fence. Every draft names ≥1 component id (or `cross-cutting`) as provenance — that is the binary gate, not seed quality.

**Where drafts land before `--apply`.** Under the roadmap slug (e.g. `roadmaps/<slug>/seeds/` or a sibling drafts dir the format doc names) — reviewable, gitignored or committed with the artifacts as the operator chooses. **`--apply` is recommend-only by default**, modeled on `scope-out`: preview the move; `--apply` plus TTY confirm (or `--apply -y`) copies/moves accepted drafts into `plan-seeds/`. No silent write into the seed dir on a green stage-4 run.

**Gates — relations over ids, never merit.** Binary observables only:

1. Every plan row names ≥1 component id that `03-components.md` defines, or disposition `cross-cutting`.
2. Every non-`cross-cutting` component id appears in ≥1 plan row (merge and split both count as coverage).
3. Every emitted draft seed names ≥1 component id (or `cross-cutting`) that the roadmap inventory declares.
4. Every draft seed path the artifact advertises exists on disk after the stage write (no dangling seed pointers).

No gate may judge whether a merge/split was *right-sized*, whether a seed's Outcome is good, or whether two plans should have been one. Business-rule and workflow **assignment into plans** may be recorded in prose or inventory here — #208 deferred that mapping from stage 3; stage 4 owns it as *optional inventory*, not as a quality gate on completeness of rule/workflow coverage unless a binary "every rule id appears somewhere" check earns its place during detail.

**Revision mode is inherited.** Stage 4 design rows (plans, and any new decision rows) participate in continuity and feedback targets the same way component ids do. Re-entering `--from-stage 4` revises the mapping against feedback; it does not auto-`--apply` into `plan-seeds/`.

**`create` hand-off is recommend-only.** When distill emits a `SplitProposal` (or the create path that already recommends decomposition), print a next-steps line pointing at `plan-tool roadmap <slug> --from-existing …` — same detect-here / actuate-there shape as `convergence` → `scope-out`. Detection stays unconditional and recommend-only; this position does not make create invoke roadmap.

**Allowed reorganization:** Widen `RoadmapStage` / the write path **only** if a single table row cannot express "artifact + draft seed files." Prefer the smallest additive change. Reuse the `scope-out` confirm/`-y` idiom rather than inventing a second confirm stack. No extraction of a shared "emit seeds for #168" helper beyond what this stage needs.

## Out of scope

- **Framework lenses, `--framework`, lens-driven stage-2 restructuring** — position 05.
- **Auto-running `create` / `detail` / `run` on emitted seeds.** Hand-off is printed lines and optional `--apply` into `plan-seeds/` only.
- **Judging whether a mapping or seed is good**, scoring plan counts, or any gate/finding/exit-code flip keyed on merit or seed prose quality. Enumerated not-allowed: **no** quality judgment of dispositions or Outcomes; **no** agreement check between seed body and roadmap prose beyond inventory id presence; **no** plan-count or seed-length cap; **no** gate keyed on "this should have been one plan / two."
- **Rewriting stages 1–3 or the feedback lifecycle** except the minimum so new design rows participate in continuity and feedback targets.
- **Interactive review walks** for seed content, manifest tracking of roadmap artifacts (#208 already non-goals).
- **Closing Carve B** of the decision-record rule (narrow vs broad mint-on-removal) — open human ruling on the arc; not this position's contract.
- **#235 / #236 / #237** — skill two-stage sweep, unreachable `not-load-bearing` carve, gate cleanups from position 03 review; file or leave as siblings, do not absorb.
- **Reply-bytes sink half of #217.**

## Risks

- **Dual output breaks stage-as-data.** First stage that must leave files *beside* the numbered artifact. If the envelope forces an orchestrator branch, stop and widen deliberately.
- **Seed quality is ungateable; operators will ask for gates.** Hold the enumerated not-allowed list. The review surface is the draft dir + feedback loop, not a prose scorer.
- **`--apply` and dirty trees.** Moving into `plan-seeds/` can collide with existing seeds; define collision policy (refuse / numbered `.replaced.N` / require force) in detail — prefer refuse-by-default matching annotate's archive caution.
- **Prose-mention / inventory scale** (arc lesson 3). More ids; keep gates cheap; do not raise `MAX_STAGE_ATTEMPTS` as the first reach.
- **Frozen rejected-alternative reasons** (walkthrough caveat). Seeds must carry settled *decisions* as fences and let `create` re-ground *reasons* against live docs — say so in the prompt so drafts do not over-copy rationale prose.

## Testing

Hermetic, stubbed invokers per `TESTING.md`:

- Stage 4 writes a parseable artifact and draft seed files.
- Each gate rejects the corresponding violation and clears a conforming case.
- Orphan component / dangling seed path / seed missing component provenance fail.
- `cross-cutting` plans do not require a component id.
- Continuity and feedback cover plan ids.
- Default run does not touch `plan-seeds/`.
- `--apply` without confirm is recommend-only; `--apply -y` moves drafts.
- Collision policy holds.
- Stages 1–3 alone unchanged.
- `--from-stage 4` revises with predecessor + feedback.
- `create`'s `SplitProposal` / next-steps path prints the roadmap pointer without invoking it.

**One real run:** existing gated 01/02/03 on disk (`toollib` or `cfp-review`) → reviewable `04-roadmap.md` + drafts; read stdout and stderr together (arc lesson 1). Optional human `--apply` of one draft is enough to prove the gate; do not batch-apply as the measurement.

## Acceptance criteria

- `plan-tool roadmap <slug> …` (or `--from-stage 4` over existing 01–03) writes gated `04-roadmap.md` and draft seeds under the roadmap slug.
- Every component is covered by ≥1 plan (or explicitly only via documented `cross-cutting` handling if a component is absorbed); every plan traces to component id(s) or `cross-cutting`; every draft seed names that provenance.
- Default completion does not mutate `plan-seeds/`; `--apply` + confirm / `-y` does, with a stated collision policy.
- Operator summary prints runnable `create --from-existing <path>` lines for applied or draft paths as the format specifies.
- Create's distill / split recommend path mentions `plan-tool roadmap`.
- `docs/ROADMAP_WALKTHROUGH.md` § 7 lists position 04 as shipped; § 5 describes the automated hand-off and keeps a short manual fallback.
- **`BACKLOG.md` #208 is reconciled when this ships** — position 04 marked shipped; position 05 left as the remaining arc. Authoring does not remove the entry.

## Deferred

- Framework lenses and pillar-coverage gates (position 05).
- Auto-pipeline from seeds through `create`/`detail`/`run`.
- Merit scoring of mappings or seeds.
- Carve B wording (human A/B on the arc).
- #235–#237 and #217's remaining half.
