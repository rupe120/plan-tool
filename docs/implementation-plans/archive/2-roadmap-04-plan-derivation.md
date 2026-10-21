> **Auto-archived**: this plan was swept on 2026-08-05 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

---
title: Roadmap 04 Plan Derivation
intent: '`plan-tool roadmap` writes a gated `04-roadmap.md` that maps components to
  an ordered plan list (with merge / split / `cross-cutting` dispositions), emits
  `SEED_FORMAT.md`-conformant draft seeds citing component provenance, and offers
  a recommend-only `--apply` + confirm path that copies accepted drafts into `plan-seeds/`.
  Printed next-steps are runnable `create --from-existing` lines; `create`''s distill
  `SplitProposal` surfaces a recommend-only pointer at this verb. End-to-end: concept
  brief → reviewed artifacts → seeds.'
status: completed
priority: medium
enforce_step_tests: true
steps:
- id: 1
  title: Add 04-roadmap.md artifact contract with plan rows, disposition vocabulary,
    and draft-seed paths
  intent: Give stage 4 a strict, round-trippable shape for plan inventory rows (id
    matching create's SLUG_RE, title, disposition, component id(s), draft- seed path
    relative to the roadmap slug directory, sizing rationale), ordering sequence plus
    dependency/assumption target fields, an inter-plan assumptions inventory (id,
    statement, consuming plan ids), feedback/ removals/decisions review collections
    (plans + assumptions + decisions all join design-row enumeration), and pinned
    draft provenance frontmatter keys `roadmap_components` and optional `cross_cutting`.
  files:
  - plan_tool/roadmap_artifacts.py
  - tests/test_roadmap_artifacts.py
  complexity: high
  change_type: feature
  detail: docs/implementation-plans/plan-details/roadmap-04-plan-derivation/01-04-roadmap-md-artifact-contract-plan.md
  status: done
- id: 2
  title: Widen the gate envelope and design-row helpers for a fourth artifact
  intent: Let the existing gate table and predecessor feedback-target preflight resolve
    plan ids the same way they already resolve component ids; update artifact_under_check
    / filename_under_check / _rows_of / design_row_ids / _envelope_rows so a plans-filled
    envelope gates 04-roadmap.md and unions plan + assumption + decision ids into
    cross-artifact duplicate/decision checks; and add the envelope field that carries
    the draft-seed side-output bundle (step 5 fills it; gates 3–4 read it).
  files:
  - plan_tool/roadmap_gates.py
  - tests/test_roadmap_gates.py
  complexity: medium
  change_type: feature
  depends_on:
  - 1
  detail: docs/implementation-plans/plan-details/roadmap-04-plan-derivation/02-widen-gate-envelope-design-row-helpers.md
  status: done
- id: 3
  title: Add stage-4 relation gates and run_plans_gates
  intent: Wire run_plans_gates like stages 1–3 — shared shape/revision gates (non-empty
    with a PlansArtifact arm requiring a non-empty plans inventory, duplicate ids,
    decision records, inventory-has-prose, design-row continuity, feedback integrity,
    settled decisions) plus the plan-relation observables over the envelope side-output
    field (gates 3–4; SLUG_RE on plan ids; assumption-row consuming plan ids must
    resolve).
  files:
  - plan_tool/roadmap_gates.py
  - tests/test_roadmap_gates.py
  complexity: high
  change_type: feature
  depends_on:
  - 2
  - 5
  detail: docs/implementation-plans/plan-details/roadmap-04-plan-derivation/03-stage-relation-gates-run-plans-gates.md
  status: done
- id: 4
  title: Document 04-roadmap.md and draft-seed conventions in ROADMAP_FORMAT.md
  intent: Make the fourth artifact and its draft-seed sidecar discoverable, copy-safe,
    and traceable to the code symbols that enforce each rule.
  files:
  - ROADMAP_FORMAT.md
  - tests/test_roadmap_format.py
  complexity: medium
  change_type: non-code
  depends_on:
  - 1
  - 2
  - 3
  detail: docs/implementation-plans/plan-details/roadmap-04-plan-derivation/04-document-04-roadmap-md-draft-seed.md
  status: done
- id: 5
  title: Refactor the stage write loop for optional side outputs
  intent: Make dual output expressible as data on the stage row — a reply contract
    that lifts 04-roadmap.md plus N draft-seed fences (labels = plan row draft- seed
    path basename) into an in-memory bundle attached as an explicit ArtifactEnvelope
    field keyed by that basename, so Gate callables still receive only the envelope;
    gates against that field, then writes the artifact and draft set atomically on
    success.
  files:
  - plan_tool/roadmap.py
  - tests/test_roadmap.py
  complexity: medium
  change_type: refactor
  depends_on:
  - 1
  - 2
  detail: docs/implementation-plans/plan-details/roadmap-04-plan-derivation/05-refactor-stage-write-loop-optional-side.md
  status: done
- id: 6
  title: Add stage 4 writing 04-roadmap.md with roadmap-plans.md prompt and draft
    seeds
  intent: Run a gated fourth stage that reads 01/02/03 off disk, writes 04-roadmap.md,
    and emits draft seeds whose prompt contract enumerates all five Architecture additions
    (four-artifact provenance, domain-id binding, settled-decision fences without
    over-copied rejected-alternative rationale, discharged constraints, and inter-plan
    assumptions filtered to rows whose consuming plan ids include that seed's plan
    id), prints ordered create --from-existing lines, and never touches plan-seeds/.
  files:
  - plan_tool/roadmap.py
  - plan_tool/cli/roadmap_cmd.py
  - tests/test_roadmap.py
  - tests/cli/test_roadmap_cmd.py
  creates:
  - plan_tool/prompts/roadmap-plans.md
  complexity: high
  change_type: feature
  depends_on:
  - 3
  - 4
  - 5
  detail: docs/implementation-plans/plan-details/roadmap-04-plan-derivation/06-stage-writing-04-roadmap-md-roadmap.md
  status: done
- id: 7
  title: Add --apply and -y to promote draft seeds into plan-seeds with refuse-by-default
    collisions
  intent: Add an apply-only CLI mode (mutually exclusive with --from-stage) that parses
    on-disk 04-roadmap.md and copies each plan row's advertised draft- seed path (refusing
    missing paths), does not require --from-existing / the concept brief, skips the
    stage table and Claude, and promotes after --apply plus confirm or -y with refuse-by-default
    collisions; operator summary prints create lines for promoted paths.
  files:
  - plan_tool/roadmap.py
  - plan_tool/cli/roadmap_cmd.py
  - tests/test_roadmap.py
  - tests/cli/test_roadmap_cmd.py
  - docs/cli/roadmap.md
  complexity: medium
  change_type: feature
  depends_on:
  - 6
  detail: docs/implementation-plans/plan-details/roadmap-04-plan-derivation/07-apply-promote-draft-seeds-plan-seeds.md
  status: done
- id: 8
  title: Add a recommend-only roadmap pointer to create split-proposal next steps
  intent: When create's SplitProposal path recommends decomposition, print generic
    recommend-only guidance naming the roadmap verb (create has no roadmap slug or
    concept-brief path, so do not invent a runnable roadmap … --from-existing line).
  files:
  - plan_tool/cli/authoring.py
  - tests/cli/test_authoring_cmds.py
  complexity: low
  change_type: feature
  depends_on:
  - 6
  detail: docs/implementation-plans/plan-details/roadmap-04-plan-derivation/08-recommend-only-roadmap-pointer-create.md
  status: done
- id: 9
  title: Run stage 4 on an existing brief and record human-review outcomes
  intent: Prove 04-roadmap.md plus draft seeds are reviewable on a real gated 01/02/03
    pair before the arc docs claim position 04 shipped.
  complexity: medium
  change_type: non-code
  depends_on:
  - 6
  - 7
  detail: docs/implementation-plans/plan-details/roadmap-04-plan-derivation/09-run-stage-on-existing-brief-record.md
  status: done
- id: 10
  title: Reconcile BACKLOG 208 and sweep roadmap operator docs for stage 4
  intent: 'Leave every operator-facing surface describing four shipped stages, automated
    § 5 hand-off with manual fallback, and arc position 04 marked done in BACKLOG
    #208.'
  files:
  - BACKLOG.md
  - CLAUDE.md
  - CAPABILITIES.md
  - RUNBOOK.md
  - USE_CASES.md
  - docs/ARCHITECTURE.md
  - docs/ROADMAP_WALKTHROUGH.md
  - integrations/claude/SKILL.md
  complexity: medium
  change_type: non-code
  depends_on:
  - 4
  - 6
  - 7
  - 8
  - 9
  detail: docs/implementation-plans/plan-details/roadmap-04-plan-derivation/10-reconcile-backlog-208-sweep-roadmap.md
  status: done
---
# Roadmap 04 Plan Derivation

## Overview

Arc position **04** of the `roadmap-NN-*` group (anchor: `BACKLOG.md` **#208**). Positions 01–03 shipped stages 1–3, revision-against-feedback, and gated `03-components.md`; this plan adds **artifact stage 4** — gated `04-roadmap.md` plus draft seeds under the roadmap slug — and closes the concept→seeds loop. Position 05 (framework lenses) stays unauthored.

`plan-tool roadmap` writes a gated `04-roadmap.md` that maps components to an ordered plan list (with merge / split / `cross-cutting` dispositions), emits `SEED_FORMAT.md`-conformant draft seeds citing component provenance, and offers a recommend-only `--apply` + confirm path that copies accepted drafts into `plan-seeds/`. Printed next-steps are runnable `create --from-existing` lines; `create`'s distill `SplitProposal` surfaces a recommend-only pointer at this verb. Green stage-4 completion does **not** write `plan-seeds/` unless `--apply` (+ confirm or `-y`). Auto-running `create` is not the hand-off.

## Problem statement

Three gated artifacts name the domain, the tradeoffs, and the logical partition. The hop to *buildable plan seeds* is still manual: `docs/ROADMAP_WALKTHROUGH.md` § 5 is the only written procedure, and a human must invent the component→plan sizing, write each seed by hand, and carry inter-plan assumptions. #208's headline promise is an **ordered set of `create --from-existing` seeds**; without stage 4 the verb stops one review surface short of that set.

The Framing still governs: stage 4 **proposes** a mapping and draft seeds; a human reviews (and may redirect via feedback) before `--apply` mutates the seed directory.

## Architecture

**Stage-as-data again.** Append one `STAGES` row that reads domain + constraints + components and writes `04-roadmap.md`. Same shape/relation split: parse accepts dangling refs; gates return violations. Dual output is a **side-output bundle on the stage row**, not an orchestrator branch: the model reply carries the plans artifact plus N draft-seed fences labeled by each plan row's draft-seed **path basename**; the lift path attaches that bundle as an **explicit `ArtifactEnvelope` field** keyed by basename so existing `Gate = Callable[[ArtifactEnvelope], list[Violation]]` and `_run_stage`'s single-envelope call stay valid; **gates run on that field** (matching today's gate-before-`_write_artifact` order); a green attempt then writes `04-roadmap.md` and replaces the draft-seed directory atomically. If the table cannot express that bundle, widen the smallest amount that admits it and record why. Draft seeds are side products of the stage, not a fifth Claude call and not a second verb.

**What `04-roadmap.md` carries.** Frontmatter inventory the gates check; prose a reviewer reads. At minimum:

- **Plans** — id (also the `create` slug in next-steps; must satisfy `create`'s `SLUG_RE`), title, disposition (`keep` one component / `merge` several / `split` one component into several plans / `cross-cutting`), the component id(s) each plan owns, draft-seed path, sizing rationale keyed to those components.
- **Ordering** — frontmatter sequence listing every plan id exactly once; each plan may name `depends_on` / `assumption_targets` plan ids that must appear **earlier** in that sequence (gate 5). `assumption_targets` is **reviewer-facing metadata only** — it does not flow into draft seeds or `--apply` handoff; seeds copy `assumptions` inventory rows filtered by `consuming_plan_ids`.
- **Inter-plan assumptions** — frontmatter rows (`id`, statement, consuming plan ids) the seeds copy into their fences; distinct from ordering's `assumption_targets` metadata.
- **Review collections** — `feedback`, `removals`, and `decisions` on the same contract as stages 1–3 so revision continuity and feedback targets parse.
- **Accumulated decision log** — citations into upstream `decisions` rows; new partition/sizing calls that a later reader would question land as this artifact's own `decisions` rows.

**Dispositions are closed vocabulary; sizing rationale is free text.** `cross-cutting` is for CI / observability / auth-plumbing work that is not one component's owner — #208 names this; do not invent a parallel escape.

**Draft seeds inherit the walkthrough's load-bearing additions** (§ 5): (1) provenance naming all four artifacts and forbidding re-litigation of settled upstream decisions; (2) the domain ids the slice binds to; (3) settled decisions as a fence with rejected alternatives; (4) constraint ids this slice discharges, with dispositions; (5) inter-plan assumptions from the assumptions inventory, copied into a seed's scope-contract fence **only when** that seed's plan id is in the row's consuming plan ids. Body shape per `SEED_FORMAT.md` including the full scope-contract fence; drafts additionally carry an optional YAML frontmatter provenance block documented in `ROADMAP_FORMAT.md` (required `roadmap_components: [id, …]`, optional `cross_cutting: true`) that gate 3 scans — distinct from ordinary `plan-seeds/` prose-only convention after `--apply`. The stage-4 prompt carries settled decisions as fences and **must not** over-copy frozen rejected-alternative rationale into drafts — `create` re-grounds reasons against live docs (walkthrough caveat).

**Where drafts land before `--apply`.** Under the roadmap slug's **`seeds/` directory only** (default `roadmaps/<slug>/seeds/`); every plan row's `draft-seed path` is relative to the slug directory and **must stay under `seeds/`** (**parse** rejects paths that escape it — step 1 shape rule). Gate 4 / atomic rewrite / `--apply` / printed `create --from-existing` lines all resolve against that same root. A successful stage-4 write **stages the full draft set + `04-roadmap.md` off to the side, then commits them together** (temp dir → rename/`seeds/` replace, then artifact, or an equivalent all-or-nothing pair) so a mid-write failure cannot leave a new artifact advertising missing drafts, and `--from-stage 4` cannot leave stale files under `seeds/`. **`--apply` is an apply-only CLI mode**, modeled on `scope-out`: mutually exclusive with `--from-stage`; does **not** require `--from-existing` or the concept brief; reads on-disk `04-roadmap.md` + drafts; skips the stage table and Claude. Default without confirm is recommend-only preview; `--apply` plus TTY confirm (or `--apply -y`) **copies** (does not move) accepted drafts into `plan-seeds/` so the slug's draft set remains the stage output, **stripping the draft provenance frontmatter block** — refuse the promote if that block is present but unparseable (never copy malformed provenance verbatim). Collisions in `plan-seeds/` are refused by default. No silent write into the seed dir on a green stage-4 run. The CLI completion summary prints ordered `plan-tool create <plan-id> --from-existing <path>` lines for draft paths (and again for promoted paths after `--apply`), using each plan row's `id` as the create slug.

**Gates — relations over ids, never merit.** `PLANS_GATES` ordered tuple (mirrors `COMPONENTS_GATES`):

1. `check_artifact_non_empty` (`PlansArtifact` arm: non-empty plans inventory)
2. `check_duplicate_row_ids`
3. Plan-relation 1 — every plan row names ≥1 defined component id, or disposition `cross-cutting` (empty `component_ids` allowed). When a `cross-cutting` row **lists** `component_ids`, every listed id must still resolve in `03-components.md`.
4. Plan-relation 2 — every component id appears on ≥1 plan row; `cross-cutting` alone does not cover a component.
5. Plan-relation 3 — draft provenance `roadmap_components` / optional `cross_cutting`; each component id must be on the owning plan row's `component_ids` (or `cross_cutting: true` on a `cross-cutting` plan). Bundle text from the envelope field.
6. Plan-relation 4 — each plan row's draft-seed **basename** keys exactly one in-memory bundle entry (and conversely). Disk parity after a green write is the write-path contract (step 5), not this gate.
7. Plan-relation 5 — ordering↔plans **bijection** (every plan id exactly once as an ordering `plan_id`; every ordering `plan_id` is a plans-inventory id); `depends_on` / `assumption_targets` name inventory ids that appear **earlier** in the sequence; every plan id matches `create`'s `SLUG_RE`.
8. Plan-relation 6 — every assumption row's `consuming_plan_ids` resolve in the plans inventory.
9. `check_decision_records`
10. `check_inventory_has_prose`
11. `check_design_row_continuity`
12. `check_feedback_integrity`
13. `check_settled_decisions`

**Plan ids are envelope-unique.** `check_duplicate_row_ids` unions ids across every artifact in the envelope, so a plan id must not reuse a component (or other upstream design-row) id — the duplicate-id gate already enforces this; the prompt must not suggest echoing component ids as plan slugs.


No gate may judge whether a merge/split was *right-sized*, whether a seed's Outcome is good, or whether two plans should have been one. Business-rule and workflow **assignment into plans** may be recorded in prose or inventory here — #208 deferred that mapping from stage 3; stage 4 owns it as *optional inventory*, not as a quality gate on completeness of rule/workflow coverage unless a binary "every rule id appears somewhere" check earns its place during detail.

**Revision mode is inherited.** Stage 4 design rows — **plan inventory, assumption inventory, and decision rows** — participate in continuity and feedback targets the same way component ids do. Re-entering `--from-stage 4` revises the mapping against feedback; it does not auto-`--apply` into `plan-seeds/`.

**`create` hand-off is recommend-only.** When distill emits a `SplitProposal` (or the create path that already recommends decomposition), print **generic** next-steps guidance naming the `roadmap` verb — create's split path has the plan slug and seed file, not a roadmap slug or concept-brief path, so it must **not** invent a runnable `plan-tool roadmap <slug> --from-existing …` line. Same detect-here / actuate-there *shape* as `convergence` → `scope-out`, without fabricating missing operands. Detection stays unconditional and recommend-only; this position does not make create invoke roadmap.

**Allowed reorganization:** Widen `RoadmapStage` / the write path **only** if a single table row cannot express "artifact + draft seed files." Prefer the smallest additive change. Reuse the `scope-out` confirm/`-y` idiom rather than inventing a second confirm stack. No extraction of a shared "emit seeds for #168" helper beyond what this stage needs.

## References

- [PyYAML Documentation](https://pyyaml.org/wiki/PyYAMLDocumentation) — Official PyYAML load/dump API reference for parsing and serializing YAML frontmatter inventories in roadmap artifacts and draft seeds.
- [YAML Ain't Markup Language (YAML) revision 1.2.2](https://yaml.org/spec/1.2.2/) — Authoritative YAML 1.2 language specification for frontmatter row syntax, scalars, and collections used in gated markdown artifacts.
- [dataclasses — Data Classes (Python 3.13)](https://docs.python.org/3.13/library/dataclasses.html) — Standard-library reference for @dataclass stage rows, gate envelopes, and typed inventory records in the stage-as-data roadmap pipeline.
- [pathlib — Object-oriented filesystem paths (Python 3.13)](https://docs.python.org/3.13/library/pathlib.html) — Official Path API for roadmap slug directories, draft seed locations, existence checks, and path composition before --apply.
- [shutil — High-level file operations (Python 3.13)](https://docs.python.org/3.13/library/shutil.html) — Official copy semantics for the recommend-only --apply path that copies accepted draft seeds into plan-seeds/.
- [argparse — Parser for command-line options (Python 3.13)](https://docs.python.org/3.13/library/argparse.html) — Standard-library CLI reference for adding roadmap stage-4 flags such as --apply, --from-stage, and -y to the existing parser.
- [enum — Support for enumerations (Python 3.13)](https://docs.python.org/3.13/library/enum.html) — Official Enum/StrEnum reference for implementing closed disposition vocabularies (keep, merge, split, cross-cutting) checked by stage-4 gates.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

- **Framework lenses, `--framework`, lens-driven stage-2 restructuring** — position 05.
- **Auto-running `create` / `detail` / `run` on emitted seeds.** Hand-off is printed lines and optional `--apply` into `plan-seeds/` only.
- **Judging whether a mapping or seed is good**, scoring plan counts, or any gate/finding/exit-code flip keyed on merit or seed prose quality. Enumerated not-allowed: **no** quality judgment of dispositions or Outcomes; **no** agreement check between seed body and roadmap prose beyond inventory id presence; **no** plan-count or seed-length cap; **no** gate keyed on "this should have been one plan / two."
- **Rewriting stages 1–3 or the feedback lifecycle** except the minimum so new design rows participate in continuity and feedback targets.
- **Interactive review walks** for seed content, manifest tracking of roadmap artifacts (#208 already non-goals).
- **Closing Carve B** of the decision-record rule — settled 2026-08-05
  (**narrow**); see `BACKLOG.md` #208. Not this position's contract.
- **#235 / #236 / #237** — skill two-stage sweep, unreachable `not-load-bearing` carve, gate cleanups from position 03 review; file or leave as siblings, do not absorb.
- **Reply-bytes sink half of #217.**

## Risks

- **Dual output breaks stage-as-data.** First stage that must leave files *beside* the numbered artifact. If the envelope forces an orchestrator branch, stop and widen deliberately.
- **Seed quality is ungateable; operators will ask for gates.** Hold the enumerated not-allowed list. The review surface is the draft dir + feedback loop, not a prose scorer.
- **`--apply` and dirty trees.** Copying into `plan-seeds/` can collide with existing seeds; define collision policy (refuse / numbered `.replaced.N` / require force) in detail — prefer refuse-by-default matching annotate's archive caution. `--apply` never re-invokes stage 4.
- **Prose-mention / inventory scale** (arc lesson 3). More ids; keep gates cheap; do not raise `MAX_STAGE_ATTEMPTS` as the first reach.
- **Frozen rejected-alternative reasons** (walkthrough caveat). Seeds must carry settled *decisions* as fences and let `create` re-ground *reasons* against live docs — say so in the prompt so drafts do not over-copy rationale prose.

## Testing

Hermetic, stubbed invokers per `TESTING.md`:

- Stage 4 lifts a multi-fence reply into an in-memory side-output bundle, gates it, then writes a parseable artifact and draft seed files atomically.
- Each gate rejects the corresponding violation and clears a conforming case (gates 3–4 over the bundle, not a pre-write empty disk).
- Orphan component / dangling seed path / seed missing component provenance fail.
- `cross-cutting` plans do not require a component id.
- Continuity and feedback cover plan ids.
- Default run does not touch `plan-seeds/`.
- `--apply` without confirm is recommend-only; `--apply -y` copies on-disk drafts without invoking the stage; it does not move.
- Collision policy holds; a stage-4 rewrite leaves no unlisted draft paths beside the slug.
- Operator summary emits ordered create --from-existing lines.
- Ordering / plan-to-seed / provenance-frontmatter / assumption-consumer gates reject the corresponding holes.
- Per-seed assumption **fence** scoping (only assumptions whose `consuming_plan_ids` include that plan) is verified in step 9's human review of real drafts — not a hermetic seed-body gate (gates refuse merit checks on seed prose).
- Stages 1–3 alone unchanged.
- `--from-stage 4` revises with predecessor + feedback.
- `create`'s `SplitProposal` / next-steps path prints generic roadmap-verb guidance without invoking it or inventing missing slug/brief operands.

**One real run:** existing gated 01/02/03 on disk (`toollib` or `cfp-review`) → reviewable `04-roadmap.md` + drafts; read stdout and stderr together (arc lesson 1). Optional human `--apply` of one draft is enough to prove the gate; do not batch-apply as the measurement.

**Per-step test strategy** (derived from each step's `change_type`):

- step 1 (feature) — tests covering the behavior this step changes; green before completion.
- step 2 (feature) — tests covering the behavior this step changes; green before completion.
- step 3 (feature) — tests covering the behavior this step changes; green before completion.
- step 4 (non-code) — verification appropriate to the artifacts rather than unit tests.
- step 5 (refactor) — tests covering the behavior this step changes; green before completion.
- step 6 (feature) — tests covering the behavior this step changes; green before completion.
- step 7 (feature) — tests covering the behavior this step changes; green before completion.
- step 8 (feature) — tests covering the behavior this step changes; green before completion.
- step 9 (non-code) — verification appropriate to the artifacts rather than unit tests.
- step 10 (non-code) — verification appropriate to the artifacts rather than unit tests.

## Acceptance criteria

- `plan-tool roadmap <slug> …` (or `--from-stage 4` over existing 01–03) writes gated `04-roadmap.md` and draft seeds under the roadmap slug.
- Every component id appears on ≥1 plan row; every plan traces to component id(s) or disposition `cross-cutting`; every plan row's draft-seed path basename is in the gated side-output bundle (and on disk after a green write under the slug-dir root); every draft seed's `roadmap_components` / `cross_cutting` provenance resolves; ordering and plans inventories are the same set (bijection); dependency targets appear earlier in ordering; every plan id matches `create`'s `SLUG_RE` and is envelope-unique vs upstream design-row ids; every assumption row's consuming plan ids resolve; each draft carries only assumptions scoped to its plan (human-verified in step 9; not a hermetic seed-body gate).
- Default completion does not mutate `plan-seeds/`; apply-only `--apply` + confirm / `-y` **copies** on-disk drafts without a Claude stage call or concept brief, with refuse-by-default collisions; stage-4 writes replace the draft set atomically.
- Operator summary prints runnable `create <plan-id> --from-existing <path>` lines for draft paths (and promoted paths after `--apply`).
- Create's distill / split recommend path mentions the `roadmap` verb in generic guidance (not a fabricated runnable roadmap invocation).
- `docs/ROADMAP_WALKTHROUGH.md` § 7 lists position 04 as shipped; § 5 describes the automated hand-off and keeps a short manual fallback.
- **`BACKLOG.md` #208 is reconciled when this ships** — position 04 marked shipped; position 05 left as the remaining arc. Authoring does not remove the entry.

## Deferred

- Framework lenses and pillar-coverage gates (position 05).
- Auto-pipeline from seeds through `create`/`detail`/`run`.
- Merit scoring of mappings or seeds.
- Carve B wording — settled narrow 2026-08-05 (`BACKLOG.md` #208).
- #235–#237 and #217's remaining half.
