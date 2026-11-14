# Roadmap plan breakdown — review handoff

Review whether stage 4 incorporates the useful lessons from seed breakdown at
roadmap altitude. Treat the plan list in `04-roadmap.md` as a critical design
artifact, analogous to reviewing the step list in a bare plan: its boundaries,
responsibilities and dependencies shape everything authored downstream.

## Pickup state

| Item | State |
| --- | --- |
| Grounding snapshot | `adba0f005`, main after merged PR #153 |
| User concern | The plan-ID list must reflect deliberate decomposition, rather than receive attention only after seeds expose oversized or incomplete plans. |
| Current work | Review handoff only; no confirmed decomposition bug or approved implementation change. |
| Separate completed work | PRs #151–153 clarify seed materialization, plan-row selection and demo workflow. They do not change stage-4 decomposition. |
| Next action | Compare existing rules and representative retained outputs; report evidence-backed gaps or conclude that no change is justified. |

## Current contract and owners

| Surface | What it owns | Read first |
| --- | --- | --- |
| Stage-4 plan mapping | Cohesive plan outcomes, scope boundaries, delivery ownership, prerequisites, ordering and eventual proof | [Stage-4 prompt](../plan_tool/prompts/roadmap-plans.md), especially “Map complete implementation responsibilities”; [roadmap schema](../ROADMAP_FORMAT.md#04-roadmapmd--frontmatter-schema) |
| Roadmap structure checks | Row identity, coverage, references, ordering, intent/non-goal presence and other observable contracts | [Roadmap gates](../plan_tool/roadmap_gates.py), especially `check_plan_review_context`, `check_component_plan_coverage`, `check_plan_ordering_totality` |
| Seed one-plan versus split judgment | Cohesive effort versus independent top-level efforts, grounded in concrete shared implementation when claimed | [Seed distillation prompt](../plan_tool/prompts/distill-seed.md), “Decide: one plan, or many?”; [seed format](../SEED_FORMAT.md) |
| Materialization | Expand the selected accepted row into its draft seed while preserving supplied responsibilities and boundaries | [Seed materializer prompt](../plan_tool/prompts/roadmap-seed.md), [materializer](../plan_tool/roadmap.py), [seed workflow](../docs/how-to/roadmap.md#7-promote-accepted-draft-seeds-or-create-directly-from-them) |
| Accepted roadmap changes | Reviewer ledger input, inert candidates, review and promotion | [Feedback lifecycle](../ROADMAP_FEEDBACK_FORMAT.md), [immutable artifact contract](../ROADMAP_FORMAT.md) |

Stage 4 already requires a cohesive outcome, explicit boundary, identifiable
prerequisites and verifiable completion for every plan. It explicitly says to
split overly broad **plan rows**: splitting the steps of one broad plan is not
a substitute. It allows keep/merge/split/cross-cutting delivery shapes, rejects
fixed plan counts and directory-based boundaries, assigns shared producers and
consumer integration, and names ownership for each required business transition.
The rows collectively stay within the smallest end-to-end proof boundary.

The stage-4 prompt reads the brief and three upstream artifacts only; it forbids
repository inspection. Seed distillation can reason about named implementation
coupling. Do not copy its file/function-based criterion literally into stage 4
or infer that every downstream split proves a stage-4 defect.

Materialization preserves the accepted row and narrative. It must surface an
overly broad mapping through roadmap review, **not repartition accepted rows**.
The later create route can still return a split proposal; trace the reason
before deciding which earlier boundary, if any, needs correction.

## Identity and relationships

- A roadmap plan row's `id` identifies a proposed implementation effort; its
  title is human-facing text. The printed create handoff reuses the row ID as
  its plan slug.
- Component-to-plan coverage can be many-to-many: one component can need several
  plans, and one plan can span components. Do not equate a component with a plan.
- The current schema assigns one `draft_seed_path` to each plan row. Materialize
  selects that existing row ID before its seed file exists. This current
  row-to-draft contract is distinct from broader conceptual relationships among
  roadmap responsibilities, seeds and eventual plans.
- This review does not authorize a new seed-sharing/cardinality contract or
  a repartitioning of accepted roadmaps.

## Review procedure and evidence

1. Compare stage-4, seed-distillation and materialization guidance. Build a small
   matrix: principle, current stage-4 provision, seed-side provision, justified
   altitude difference, and any remaining gap. Check instruction composition in
   `roadmap.py`, not just the standalone prompt text.
2. Inspect the existing `TestPlansPromptTemplate` tests in
   [tests/test_roadmap.py](../tests/test_roadmap.py). They pin responsibility
   guidance, shared production/integration, handoffs, sizing and acceptance;
   prompt-presence assertions do not establish model decomposition quality.
3. Select a small, explicitly named set of retained stage-4 artifacts and their
   source brief/upstream versions, where available. Record exact paths,
   versions and source availability; mark unavailable evidence. Do not silently
   evaluate every roadmap or treat synthetic fixtures as successful live runs.
4. For each reviewed plan row, identify its outcome, non-goals, producer/consumer
   responsibilities, necessary integration, dependency handoffs and completion
   proof. Ask whether the complete plan set delivers the source-required path,
   whether any responsibility lacks an owner, and whether a row combines
   independent efforts or fragments one cohesive effort unnecessarily.
5. If downstream seeds/create split a row, compare the saved evidence and code
   grounding with the original accepted mapping. Distinguish an original mapping
   gap from new code knowledge, source changes or a materializer's own omission.
6. Report findings before applying changes: source, row IDs, failure scenario,
   actual missing principle, existing guidance/tests, and smallest plausible
   remedy. Present consequential scope/decomposition choices to the user.

Use the [roadmap demo's plan-mapping review](../docs/demos/roadmap-demo.md)
as a reading exercise, not evidence that a fresh run passes. The analogy to a
bare plan sets the level of scrutiny; it does not mean `completeness-audit`
accepts a roadmap or that its plan/detail audit loop already reviews stage 4.

## Scope fence and stopping rule

**In scope:** assessment of existing stage-4 decomposition guidance and its
relationship to seed breakdown, prompt assembly/tests, and named retained
outputs. Deliver a comparison matrix, evidence-backed findings and a proposed
bounded follow-up only if a real gap remains.

**Out of scope:** implementing prompt/schema/CLI changes in this handoff task;
repository grounding inside stage 4; new fields, automatic semantic gates,
quality scores, fixed size/plan-count thresholds, changing seed cardinality,
new concurrency, and live generation/rehearsal or publication without a separate
request. Do not turn a judged property into a vocabulary matcher.

If existing rules already cover the observed issue, identify whether the remedy
is clearer review practice, a prompt-delivery defect or an evidenced behavior
failure. Do not add another restatement merely because an output can be bad.
If representative evidence is unavailable, report that limit before proposing
new generation work. If no material gap is established, close the assessment
without an implementation proposal. Structural changes need their own scope
and user decision; use the normal plan/review workflow if work is authorized.

## Requested pickup result

Return the rule comparison, the named evidence examined, findings with source
and responsibility ownership, and unresolved decisions. Separate demonstrated
defects from hypotheses and advisory review questions. Preserve accepted-head
selection and existing roadmap review/promotion authority throughout.

## Handoff verification

All local link targets and heading anchors resolve; whitespace checks pass.
Two independent actual Claude Code `code-review` Skill sessions review
`adba0f005..92a7643f284f045ce1e24775d6085f3eba8b22c5` with
`claude-sonnet-5-5 --effort high` and reach **low-yield convergence**: no
material defects, only optional navigation/retention wording. Those advisories
do not expand the assessment scope or presume a code change. No runtime tests,
live roadmap generation or decomposition assessment occur in this handoff task.

Review 1 session: `3be992df-f64e-4dfe-b50e-00c38967f64c`.

Review 2 session: `b248a04f-9456-4b2d-8e4a-654961fc3bcd`.
